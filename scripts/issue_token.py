from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

VALID_SCOPES = {
    "health:read",
    "metrics:read",
    "models:read",
    "predict:run",
    "version:read",
    "whoami:read",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def hash_token(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"tokens": []}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return {"tokens": data}

    if not isinstance(data, dict) or "tokens" not in data:
        raise ValueError("Token registry must be a JSON object with a 'tokens' list")

    if not isinstance(data["tokens"], list):
        raise ValueError("'tokens' must be a list")

    return data


def save_registry(path: Path, registry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")


def validate_scopes(scopes: list[str]) -> None:
    unknown = sorted(set(scopes) - VALID_SCOPES)
    if unknown:
        valid = ", ".join(sorted(VALID_SCOPES))
        invalid = ", ".join(unknown)
        raise ValueError(f"\n\tUnknown scope(s): {invalid}.\n\tValid scopes: {valid}")


def find_latest_active_token_in_group(
    registry: dict[str, Any],
    rotation_group: str,
) -> dict[str, Any] | None:
    candidates = [
        record for record in registry["tokens"]
        if record.get("rotation_group") == rotation_group and record.get("active") is True
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda record: str(record.get("issued_at", "")))


def issue_token(args: argparse.Namespace) -> None:
    token_file = os.getenv("AUTH_TOKENS_FILE")
    if not token_file:
        raise RuntimeError("AUTH_TOKENS_FILE must be set")

    path = Path(token_file)
    registry = load_registry(path)

    validate_scopes(args.scopes)

    now = utc_now()
    expires_at = now + timedelta(days=args.ttl_days)

    raw_token = secrets.token_urlsafe(args.token_bytes)

    rotation_group = args.rotation_group or args.client_id

    if args.replace_latest:
        latest = find_latest_active_token_in_group(registry, rotation_group)
        if latest is None:
            raise ValueError(f"No active token found in rotation group: {rotation_group}")
        args.replaces = latest["token_id"]

    token_id = args.token_id or f"{args.client_id}-{now.strftime('%Y%m%d%H%M%S')}"

    existing_ids = {record.get("token_id") for record in registry["tokens"]}
    if token_id in existing_ids:
        raise ValueError(f"Token ID already exists: {token_id}")

    record = {
        "token_id": token_id,
        "subject": args.subject,
        "client_id": args.client_id,
        "scopes": args.scopes,
        "active": True,
        "token_hash": hash_token(raw_token),
        "issued_at": iso_z(now),
        "expires_at": iso_z(expires_at),
        "revoked_at": None,
        "replaces": args.replaces,
        "replaced_by": None,
        "rotation_group": rotation_group,
    }

    # Self-replacement is not allowed because token rotation must create
    # a new successor token. Allowing a token to replace itself would
    # corrupt the rotation history and create an invalid lifecycle chain.
    if args.replaces == token_id:
        raise ValueError("A token cannot replace itself")

    if args.replaces:
        found_old = False
        for old in registry["tokens"]:
            if old.get("token_id") == args.replaces:
                if rotation_group == old.get("rotation_group"):
                    old["replaced_by"] = token_id
                    old["active"] = False
                    found_old = True
                    break
                else:
                    raise ValueError(
                        f"\n\tRotation group mismatch\n"
                        f"\tReplaced token belongs to '{old.get("rotation_group")}'\n"
                        f"\tNew token belongs to '{rotation_group}'\n"
                        )
        if not found_old:
            raise ValueError(f"Replaced token not found: {args.replaces}")

    registry["tokens"].append(record)
    save_registry(path, registry)

    print("✅ Token issued successfully!")
    print(f"Token file: {path}")
    print(f"Token ID: {token_id}")
    print("")
    print("RAW TOKEN—¡COPY NOW! IT IS NOT SHOWN AGAIN:")
    print(raw_token)


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue a scoped bearer token for the textclf API.")

    parser.add_argument(
        "--list-scopes",
        action="store_true",
        help="List valid scopes and exit.",
    )

    parser.add_argument("--subject")
    parser.add_argument("--client-id")
    parser.add_argument("--scopes", nargs="+")
    parser.add_argument("--ttl-days", type=int, default=90)
    parser.add_argument("--token-id")
    parser.add_argument("--token-bytes", type=int, default=32)

    parser.add_argument("--replaces")
    parser.add_argument("--rotation-group")
    parser.add_argument(
        "--replace-latest",
        action="store_true",
        help="Replace the latest active token in the selected rotation group.",
    )

    args = parser.parse_args()

    if args.list_scopes:
        for scope in sorted(VALID_SCOPES):
            print(scope)
        return

    missing = [
        name
        for name in ("subject", "client_id", "scopes") # Required arguments
        if getattr(args, name) in (None, [])
    ]
    if missing:
        parser.error("missing required arguments: " + ", ".join(f"--{name.replace('_', '-')}" for name in missing))

    if args.ttl_days <= 0:
        raise ValueError("--ttl-days must be positive")

    if args.token_bytes < 32:
        raise ValueError("--token-bytes must be at least 32")
    
    if args.replaces and args.replace_latest:
        raise ValueError("Use either --replaces or --replace-latest, not both")

    issue_token(args)


if __name__ == "__main__":
    main()