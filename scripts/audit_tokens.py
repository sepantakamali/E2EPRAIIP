from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from textclf.token_audit import (
    DEFAULT_WARNING_DAYS,
    VALID_SCOPES,
    audit_registry,
    load_registry,
    threshold_for,
    utc_now,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and audit the textclf bearer-token registry.",
        # Add valid scopes to the Help
        epilog="Valid scopes:\n  " + "\n  ".join(sorted(VALID_SCOPES)),
        formatter_class=argparse.RawDescriptionHelpFormatter,  # Preserves newlines in epilog
    )
    parser.add_argument(
        "--registry",
        type=Path,
        help="Registry path. Defaults to AUTH_TOKENS_FILE.",
    )
    parser.add_argument(
        "--warning-days",
        type=int,
        nargs="+",
        default=list(DEFAULT_WARNING_DAYS),
        help="Expiry warning thresholds. Default: 30 14 7 1.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Return exit code 1 when warnings are present.",
    )
    parser.add_argument(
        "--prometheus-file",
        type=Path,
        help="Write Prometheus text-format metrics atomically to this file.",
    )
    args = parser.parse_args()

    registry_path = args.registry
    if registry_path is None:
        configured_path = os.getenv("AUTH_TOKENS_FILE")
        if not configured_path:
            parser.error(
                "--registry or AUTH_TOKENS_FILE must be provided"
            )
        registry_path = Path(configured_path)

    warning_days = sorted(set(args.warning_days), reverse=True)

    if any(value <= 0 for value in warning_days):
        parser.error("--warning-days values must be positive")

    try:
        registry = load_registry(registry_path)
        errors, warnings, statuses = audit_registry(
            registry,
            now=utc_now(),
            warning_days=warning_days,
        )
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"Token audit failed: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "registry": str(registry_path),
                    "errors": errors,
                    "warnings": warnings,
                    "tokens": statuses,
                },
                indent=2,
            )
        )
    else:
        print(f"Registry: {registry_path}")
        print(f"Tokens checked: {len(statuses)}")

        for warning in warnings:
            print(f"WARNING: {warning}")

        for error in errors:
            print(f"ERROR: {error}")

        if not warnings and not errors:
            print("✅ Token registry audit passed.")

    if args.prometheus_file is not None:
        active_tokens = [
            status
            for status in statuses
            if status["active"]
            and not status["revoked"]
            and not status["expired"]
        ]

        expired_active = sum(
            1
            for status in statuses
            if status["active"]
            and not status["revoked"]
            and status["expired"]
        )

        warning_active = sum(
            1
            for status in active_tokens
            if threshold_for(
                status["days_remaining"],
                warning_days,
            )
            is not None
        )

        audit_timestamp = int(utc_now().timestamp())

        lines = [
            "# HELP textclf_token_registry_valid Whether the token registry passed validation.",
            "# TYPE textclf_token_registry_valid gauge",
            f"textclf_token_registry_valid {0 if errors else 1}",

            "# HELP textclf_token_active_expired_total Active tokens that have expired.",
            "# TYPE textclf_token_active_expired_total gauge",
            f"textclf_token_active_expired_total {expired_active}",

            "# HELP textclf_token_active_warning_total Active tokens inside an expiry warning window.",
            "# TYPE textclf_token_active_warning_total gauge",
            f"textclf_token_active_warning_total {warning_active}",

            "# HELP textclf_token_audit_timestamp_seconds Unix timestamp of the latest token audit.",
            "# TYPE textclf_token_audit_timestamp_seconds gauge",
            f"textclf_token_audit_timestamp_seconds {audit_timestamp}",

            "# HELP textclf_token_days_remaining Remaining token lifetime in days.",
            "# TYPE textclf_token_days_remaining gauge",
        ]

        for status in active_tokens:
            token_id = str(status["token_id"]).replace("\\", "\\\\").replace('"', '\\"')
            client_id = str(status["client_id"]).replace("\\", "\\\\").replace('"', '\\"')
            rotation_group = str(status["rotation_group"]).replace("\\", "\\\\").replace('"', '\\"')

            lines.append(
                (
                    'textclf_token_days_remaining{'
                    f'token_id="{token_id}",'
                    f'client_id="{client_id}",'
                    f'rotation_group="{rotation_group}"'
                    f'}} {status["days_remaining"]}'
                )
            )

        destination = args.prometheus_file
        destination.parent.mkdir(parents=True, exist_ok=True)

        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temporary.replace(destination)

    if errors:
        return 2

    if warnings and args.fail_on_warning:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())