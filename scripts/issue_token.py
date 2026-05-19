

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


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


def issue_token(args: argparse.Namespace) -> None:
    token_file = os.getenv("AUTH_TOKENS_FILE")
    if not token_file:
        raise RuntimeError("AUTH_TOKENS_FILE must be set")

    path = Path(token_file)
    registry = load_registry(path)

    now = utc_now()
    expires_at = now + timedelta(days=args.ttl_days)

    raw_token = secrets.token_urlsafe(args.token_bytes)

    token_id = args.token_id or f"{args.client_id}-{now.strftime('%Y%m%d%H%M%S')}"

    existing_ids = {record.get("token_id") for record in registry["tokens"]}
    if token_id in existing_ids:
        raise ValueError(f"Token id already exists: {token_id}")

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
        "rotation_group": args.rotation_group or args.client_id,
    }

    if args.replaces:
        found_old = False
        for old in registry["tokens"]:
            if old.get("token_id") == args.replaces:
                old["replaced_by"] = token_id
                found_old = True
                break
        if not found_old:
            raise ValueError(f"--replaces token not found: {args.replaces}")

    registry["tokens"].append(record)
    save_registry(path, registry)

    print("Token issued successfully.")
    print(f"Token file: {path}")
    print(f"Token ID: {token_id}")
    print("")
    print("RAW TOKEN — copy now; it is not stored again:")
    print(raw_token)


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue a scoped bearer token for the textclf API.")

    parser.add_argument("--subject", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--scopes", nargs="+", required=True)
    parser.add_argument("--ttl-days", type=int, default=90)
    parser.add_argument("--token-id")
    parser.add_argument("--token-bytes", type=int, default=32)

    parser.add_argument("--replaces")
    parser.add_argument("--rotation-group")

    args = parser.parse_args()
    issue_token(args)


if __name__ == "__main__":
    main()