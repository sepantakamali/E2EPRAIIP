from __future__ import annotations

import secrets

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from textclf.token_store import (
    find_latest_active_token_in_group,
    hash_token,
    load_registry,
    save_registry,
    validate_scopes,
)


@dataclass(frozen=True)
class IssuedToken:
    raw_token: str
    token_id: str
    replaced_token_id: str | None
    expires_at: str


def iso_z(dt: datetime) -> str:
    return (
        dt.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def issue_token(
    *,
    registry_path: Path,
    subject: str,
    client_id: str,
    scopes: list[str],
    ttl_days: int = 90,
    token_id: str | None = None,
    token_bytes: int = 32,
    replaces: str | None = None,
    rotation_group: str | None = None,
    replace_latest: bool = False,
    overlap_minutes: int = 0,
    now: datetime | None = None,
) -> IssuedToken:
    if ttl_days <= 0:
        raise ValueError(
            "ttl_days must be positive"
        )

    if token_bytes < 32:
        raise ValueError(
            "token_bytes must be at least 32"
        )

    if overlap_minutes < 0:
        raise ValueError(
            "overlap_minutes cannot be negative"
        )

    if replaces and replace_latest:
        raise ValueError(
            "Use either replaces or "
            "replace_latest, not both"
        )

    validate_scopes(scopes)

    issued_at = (
        now
        if now is not None
        else datetime.now(timezone.utc)
    )

    expires_at = issued_at + timedelta(
        days=ttl_days
    )

    registry = load_registry(
        registry_path
    )

    selected_rotation_group = (
        rotation_group or client_id
    )

    if replace_latest:
        latest = (
            find_latest_active_token_in_group(
                registry,
                selected_rotation_group,
                now=issued_at,
            )
        )

        if latest is None:
            raise ValueError(
                "No active token found in "
                "rotation group: "
                f"{selected_rotation_group}"
            )

        replaces = str(
            latest["token_id"]
        )

    selected_token_id = (
        token_id
        or (
            f"{client_id}-"
            f"{issued_at.strftime('%Y%m%d%H%M%S')}"
        )
    )

    existing_ids = {
        record.get("token_id")
        for record in registry["tokens"]
    }

    if selected_token_id in existing_ids:
        raise ValueError(
            "Token ID already exists: "
            f"{selected_token_id}"
        )

    if replaces == selected_token_id:
        raise ValueError(
            "A token cannot replace itself"
        )

    raw_token = secrets.token_urlsafe(
        token_bytes
    )

    record = {
        "token_id": selected_token_id,
        "subject": subject,
        "client_id": client_id,
        "scopes": list(scopes),
        "active": True,
        "token_hash": hash_token(
            raw_token
        ),
        "issued_at": iso_z(
            issued_at
        ),
        "expires_at": iso_z(
            expires_at
        ),
        "revoked_at": None,
        "replaces": replaces,
        "replaced_by": None,
        "overlap_until": None,
        "rotation_group": (
            selected_rotation_group
        ),
    }

    if replaces:
        old = next(
            (
                record
                for record
                in registry["tokens"]
                if record.get("token_id")
                == replaces
            ),
            None,
        )

        if old is None:
            raise ValueError(
                "Replaced token not found: "
                f"{replaces}"
            )

        if (
            old.get("rotation_group")
            != selected_rotation_group
        ):
            raise ValueError(
                "Rotation group mismatch: "
                f"{old.get('rotation_group')} "
                "!= "
                f"{selected_rotation_group}"
            )

        old["replaced_by"] = (
            selected_token_id
        )

        if overlap_minutes > 0:
            old["active"] = True
            old["overlap_until"] = iso_z(
                issued_at
                + timedelta(
                    minutes=overlap_minutes
                )
            )
        else:
            old["active"] = False
            old["overlap_until"] = None

    registry["tokens"].append(record)

    save_registry(
        registry_path,
        registry,
    )

    return IssuedToken(
        raw_token=raw_token,
        token_id=selected_token_id,
        replaced_token_id=replaces,
        expires_at=iso_z(expires_at),
    )