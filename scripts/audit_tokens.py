from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_WARNING_DAYS = (30, 14, 7, 1)

REQUIRED_FIELDS = {
    "token_id",
    "subject",
    "client_id",
    "scopes",
    "active",
    "token_hash",
    "issued_at",
    "expires_at",
    "revoked_at",
    "replaces",
    "replaced_by",
    "rotation_group",
}

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


def parse_timestamp(value: object, *, field: str, token_id: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{token_id}: {field} must be a non-empty timestamp")

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value

    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError as e:
        raise ValueError(
            f"{token_id}: invalid {field} timestamp: {value!r}"
        ) from e

    if timestamp.tzinfo is None:
        raise ValueError(f"{token_id}: {field} must include a timezone")

    return timestamp.astimezone(timezone.utc)


def load_registry(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        registry = json.load(file)

    if isinstance(registry, list):
        registry = {"tokens": registry}

    if not isinstance(registry, dict):
        raise ValueError("Registry must be a JSON object")

    records = registry.get("tokens")
    if not isinstance(records, list):
        raise ValueError("Registry must contain a 'tokens' list")

    return registry


def threshold_for(days_remaining: float, thresholds: list[int]) -> int | None:
    applicable = [
        threshold
        for threshold in thresholds
        if days_remaining <= threshold
    ]
    return min(applicable) if applicable else None


def audit_registry(
    registry: dict[str, Any],
    *,
    now: datetime,
    warning_days: list[int],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    warnings: list[str] = []
    statuses: list[dict[str, Any]] = []

    records = registry["tokens"]

    token_ids = [
        record.get("token_id")
        for record in records
        if isinstance(record, dict)
    ]

    duplicate_ids = sorted(
        token_id
        for token_id, count in Counter(token_ids).items()
        if token_id is not None and count > 1
    )

    for token_id in duplicate_ids:
        errors.append(f"Duplicate token_id: {token_id}")

    records_by_id = {
        record.get("token_id"): record
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("token_id"), str)
    }

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"Record {index} is not a JSON object")
            continue

        token_id = record.get("token_id")
        display_id = token_id if isinstance(token_id, str) else f"record-{index}"

        missing = sorted(REQUIRED_FIELDS - record.keys())
        if missing:
            errors.append(
                f"{display_id}: missing field(s): {', '.join(missing)}"
            )
            continue

        if not isinstance(record["active"], bool):
            errors.append(f"{display_id}: active must be boolean")

        scopes = record["scopes"]

        if not isinstance(scopes, list) or not all(
            isinstance(scope, str) and scope
            for scope in scopes
        ):
            errors.append(f"{display_id}: scopes must be a list of strings")
        else:
            for scope in scopes:
                if scope not in VALID_SCOPES:
                    errors.append(f"{display_id}: invalid scope: {scope}")

        token_hash = record["token_hash"]
        if not isinstance(token_hash, str) or not token_hash.startswith("sha256:"):
            errors.append(
                f"{display_id}: token_hash must use the sha256: prefix"
            )

        try:
            issued_at = parse_timestamp(
                record["issued_at"],
                field="issued_at",
                token_id=display_id,
            )
            expires_at = parse_timestamp(
                record["expires_at"],
                field="expires_at",
                token_id=display_id,
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue

        if expires_at <= issued_at:
            errors.append(
                f"{display_id}: expires_at must be later than issued_at"
            )

        revoked_at_value = record["revoked_at"]
        revoked_at: datetime | None = None

        if revoked_at_value is not None:
            try:
                revoked_at = parse_timestamp(
                    revoked_at_value,
                    field="revoked_at",
                    token_id=display_id,
                )
            except ValueError as exc:
                errors.append(str(exc))

        if revoked_at is not None and record["active"] is True:
            errors.append(
                f"{display_id}: revoked token is still marked active [ALARMING]"
            )

        replaces = record["replaces"]
        replaced_by = record["replaced_by"]

        if replaces is not None:
            predecessor = records_by_id.get(replaces)

            if predecessor is None:
                errors.append(
                    f"{display_id}: replaces missing token {replaces}"
                )
            elif predecessor.get("replaced_by") != token_id:
                errors.append(
                    f"{display_id}: predecessor {replaces} does not point back "
                    f"through replaced_by"
                )
            elif predecessor.get("rotation_group") != record["rotation_group"]:
                errors.append(
                    f"{display_id}: rotation group differs from predecessor"
                )

        if replaced_by is not None:
            successor = records_by_id.get(replaced_by)

            if successor is None:
                errors.append(
                    f"{display_id}: replaced_by references missing token "
                    f"{replaced_by}"
                )
            elif successor.get("replaces") != token_id:
                errors.append(
                    f"{display_id}: successor {replaced_by} does not point back "
                    f"through replaces"
                )

            if record["active"] is True:
                errors.append(
                    f"{display_id}: replaced token is still marked active [ALARMING]"
                )

        seconds_remaining = (expires_at - now).total_seconds()
        days_remaining = seconds_remaining / 86400

        expired = seconds_remaining <= 0
        active = record["active"] is True
        revoked = revoked_at is not None

        status = {
            "token_id": display_id,
            "subject": record["subject"],
            "client_id": record["client_id"],
            "rotation_group": record["rotation_group"],
            "active": active,
            "revoked": revoked,
            "expires_at": record["expires_at"],
            "days_remaining": round(days_remaining, 2),
            "expired": expired,
        }
        statuses.append(status)

        if active and expired:
            errors.append(
                f"{display_id}: active token expired at "
                + f"{record['expires_at']}"
                + "[ALARMING]"
            )
            continue

        if active and not revoked:
            threshold = threshold_for(days_remaining, warning_days)

            if threshold is not None:
                warnings.append(
                    f"{display_id}: expires in {days_remaining:.1f} days "
                    f"at {record['expires_at']} "
                    f"(threshold: {threshold} days)"
                )

    return errors, warnings, statuses


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