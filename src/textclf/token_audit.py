from __future__ import annotations

import json

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from textclf.token_store import VALID_SCOPES, load_registry


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
    "overlap_until",
    "rotation_group",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(
    value: object,
    *,
    field: str,
    token_id: str,
) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"{token_id}: {field} must be a non-empty timestamp"
        )

    # ISO 8601 "Z" -> "+00:00" compatibility shim for fromisoformat on python <3.11
    normalized = (
        value[:-1] + "+00:00"
        if value.endswith("Z")
        else value
    )

    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError as e:
        raise ValueError(
            f"{token_id}: invalid {field} timestamp: {value!r}"
        ) from e

    if timestamp.tzinfo is None:
        raise ValueError(
            f"{token_id}: {field} must include a timezone"
        )

    return timestamp.astimezone(timezone.utc)


def threshold_for(
    days_remaining: float,
    thresholds: list[int],
) -> int | None:
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
) -> tuple[
    list[str],
    list[str],
    list[dict[str, Any]],
]:
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
            errors.append(
                f"Record {index} is not a JSON object"
            )
            continue

        token_id = record.get("token_id")
        display_id = (
            token_id
            if isinstance(token_id, str)
            else f"record-{index}"
        )

        missing = sorted(
            REQUIRED_FIELDS - record.keys()
        )

        if missing:
            errors.append(
                f"{display_id}: missing field(s): "
                f"{', '.join(missing)}"
            )
            continue

        if not isinstance(record["active"], bool):
            errors.append(
                f"{display_id}: active must be boolean"
            )

        scopes = record["scopes"]

        if not isinstance(scopes, list) or not all(
            isinstance(scope, str) and scope
            for scope in scopes
        ):
            errors.append(
                f"{display_id}: scopes must be a list of strings"
            )
        else:
            for scope in scopes:
                if scope not in VALID_SCOPES:
                    errors.append(
                        f"{display_id}: invalid scope: {scope}"
                    )

        token_hash = record["token_hash"]

        if (
            not isinstance(token_hash, str)
            or not token_hash.startswith("sha256:")
        ):
            errors.append(
                f"{display_id}: token_hash must use "
                "the sha256: prefix"
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
        except ValueError as e:
            errors.append(str(e))
            continue

        if expires_at <= issued_at:
            errors.append(
                f"{display_id}: expires_at must be "
                "later than issued_at"
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
            except ValueError as e:
                errors.append(str(e))

        if (
            revoked_at is not None
            and record["active"] is True
        ):
            errors.append(
                f"{display_id}: revoked token "
                "is still marked active"
            )

        replaces = record["replaces"]
        replaced_by = record["replaced_by"]

        if replaces is not None:
            predecessor = records_by_id.get(replaces)

            if predecessor is None:
                errors.append(
                    f"{display_id}: replaces missing "
                    f"token {replaces}"
                )

            elif (
                predecessor.get("replaced_by")
                != token_id
            ):
                errors.append(
                    f"{display_id}: predecessor "
                    f"{replaces} does not point back "
                    "through replaced_by"
                )

            elif (
                predecessor.get("rotation_group")
                != record["rotation_group"]
            ):
                errors.append(
                    f"{display_id}: rotation group "
                    "differs from predecessor"
                )

        if replaced_by is not None:
            successor = records_by_id.get(replaced_by)

            if successor is None:
                errors.append(
                    f"{display_id}: replaced_by "
                    "references missing token "
                    f"{replaced_by}"
                )

            elif successor.get("replaces") != token_id:
                errors.append(
                    f"{display_id}: successor "
                    f"{replaced_by} does not point back "
                    "through replaces"
                )

            if record["active"] is True:
                overlap_until_value = record.get("overlap_until")

                if overlap_until_value is None:
                    errors.append(
                        f"{display_id}: replaced token is active "
                        "without an overlap window"
                    )
                else:
                    try:
                        overlap_until = parse_timestamp(
                            overlap_until_value,
                            field="overlap_until",
                            token_id=display_id,
                        )
                    except ValueError as exc:
                        errors.append(str(exc))
                    else:
                        if overlap_until <= now:
                            errors.append(
                                f"{display_id}: rotation overlap expired "
                                f"at {overlap_until_value}"
                            )

        seconds_remaining = (
            expires_at - now
        ).total_seconds()

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
            "days_remaining": round(
                days_remaining,
                2,
            ),
            "expired": expired,
        }

        statuses.append(status)

        if active and expired:
            errors.append(
                f"{display_id}: active token expired "
                f"at {record['expires_at']}"
            )
            continue

        if active and not revoked:
            threshold = threshold_for(
                days_remaining,
                warning_days,
            )

            if threshold is not None:
                warnings.append(
                    f"{display_id}: expires in "
                    f"{days_remaining:.1f} days "
                    f"at {record['expires_at']} "
                    f"(threshold: {threshold} days)"
                )

    return errors, warnings, statuses