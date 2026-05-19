from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Token registry not found: {path}")

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
    with path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")


def revoke_token(args: argparse.Namespace) -> None:
    token_file = os.getenv("AUTH_TOKENS_FILE")
    if not token_file:
        raise RuntimeError("AUTH_TOKENS_FILE must be set (did you forget to load .env?)")

    path = Path(token_file)
    registry = load_registry(path)

    for record in registry["tokens"]:
        if record.get("token_id") == args.token_id:
            if record.get("revoked_at") and not args.force:
                raise RuntimeError(
                    f"Token is already revoked: {args.token_id} at {record.get('revoked_at')}"
                )

            record["active"] = False
            record["revoked_at"] = utc_now_iso()
            save_registry(path, registry)

            print("Token revoked successfully.")
            print(f"Token file: {path}")
            print(f"Token ID: {args.token_id}")
            print(f"revoked_at: {record['revoked_at']}")
            return

    raise ValueError(f"Token id not found: {args.token_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Revoke a bearer token for the textclf API.")
    parser.add_argument("--token-id", required=True)
    parser.add_argument("--force", action="store_true", help="Allow updating an already revoked token")

    args = parser.parse_args()
    revoke_token(args)


if __name__ == "__main__":
    main()
