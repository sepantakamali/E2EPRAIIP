from __future__ import annotations

import hashlib
import json

from datetime import datetime, timezone
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


def hash_token(token: str) -> str:
    return "sha256:" + hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"tokens": []}

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return {"tokens": data}

    if (
        not isinstance(data, dict)
        or "tokens" not in data
    ):
        raise ValueError(
            "Token registry must be a JSON object "
            "with a 'tokens' list"
        )

    if not isinstance(data["tokens"], list):
        raise ValueError("'tokens' must be a list")

    return data


def save_registry(
    path: Path,
    registry: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            registry,
            file,
            indent=2,
        )
        file.write("\n")

    temporary.replace(path)


def validate_scopes(scopes: list[str]) -> None:
    unknown = sorted(
        set(scopes) - VALID_SCOPES
    )

    if unknown:
        valid = ", ".join(
            sorted(VALID_SCOPES)
        )
        invalid = ", ".join(unknown)

        raise ValueError(
            f"\n\tUnknown scope(s): {invalid}."
            f"\n\tValid scopes: {valid}"
        )


def parse_iso_timestamp(
    value: object,
) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None

    normalized = (
        value[:-1] + "+00:00"
        if value.endswith("Z")
        else value
    )

    try:
        timestamp = datetime.fromisoformat(
            normalized
        )
    except ValueError:
        return None

    if timestamp.tzinfo is None:
        return None

    return timestamp.astimezone(timezone.utc)


def find_latest_active_token_in_group(
    registry: dict[str, Any],
    rotation_group: str,
    *,
    now: datetime,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []

    for record in registry["tokens"]:
        if (
            record.get("rotation_group")
            != rotation_group
        ):
            continue

        if record.get("active") is not True:
            continue

        if record.get("revoked_at") is not None:
            continue

        expires_at = parse_iso_timestamp(
            record.get("expires_at")
        )

        if (
            expires_at is None
            or expires_at <= now
        ):
            continue

        candidates.append(record)

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda record: str(
            record.get("issued_at", "")
        ),
    )