from __future__ import annotations

import argparse
import os
from pathlib import Path

from textclf.token_audit import VALID_SCOPES
from admin.token_issuance import issue_token as issue_token_record


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Issue a scoped bearer token for the textclf API."
    )

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

    parser.add_argument(
        "--overlap-minutes",
        type=int,
        default=0,
        help=(
            "Keep the replaced token active for this many minutes "
            "to allow safe consumer migration."
        ),
    )

    args = parser.parse_args()

    if args.list_scopes:
        for scope in sorted(VALID_SCOPES):
            print(scope)
        return

    missing = [
        name
        for name in ("subject", "client_id", "scopes")
        if getattr(args, name) in (None, [])
    ]

    if missing:
        parser.error(
            "missing required arguments: "
            + ", ".join(
                f"--{name.replace('_', '-')}"
                for name in missing
            )
        )

    token_file = os.getenv("AUTH_TOKENS_FILE")

    if not token_file:
        raise RuntimeError(
            "AUTH_TOKENS_FILE must be set"
        )

    result = issue_token_record(
        registry_path=Path(token_file),
        subject=args.subject,
        client_id=args.client_id,
        scopes=args.scopes,
        ttl_days=args.ttl_days,
        token_id=args.token_id,
        token_bytes=args.token_bytes,
        replaces=args.replaces,
        rotation_group=args.rotation_group,
        replace_latest=args.replace_latest,
        overlap_minutes=args.overlap_minutes,
    )

    print("Token issued successfully!")
    print("Raw token: \n")
    print(f"{str(result.raw_token)}")
    print(f"Token file: {token_file}")
    print(f"Token ID: {result.token_id}")
    print(f"Expires at: {result.expires_at}")

    if result.replaced_token_id:
        print(f"Replaces: {result.replaced_token_id}")


if __name__ == "__main__":
    main()