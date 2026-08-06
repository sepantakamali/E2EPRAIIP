from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from scripts.issue_token import (
    find_latest_active_token_in_group,
    iso_z,
)


def make_record(
    *,
    token_id: str,
    issued_at: datetime,
    expires_at: datetime,
    active: bool = True,
    revoked_at: str | None = None,
    rotation_group: str = "ui-service",
) -> dict[str, Any]:
    return {
        "token_id": token_id,
        "subject": "ui-service",
        "client_id": "ui-service",
        "scopes": ["predict:run"],
        "active": active,
        "token_hash": "sha256:" + ("a" * 64),
        "issued_at": iso_z(issued_at),
        "expires_at": iso_z(expires_at),
        "revoked_at": revoked_at,
        "replaces": None,
        "replaced_by": None,
        "rotation_group": rotation_group,
    }


def test_find_latest_selects_newest_valid_active_token() -> None:
    now = datetime.now(timezone.utc)

    older = make_record(
        token_id="older",
        issued_at=now - timedelta(days=20),
        expires_at=now + timedelta(days=30),
    )
    newer = make_record(
        token_id="newer",
        issued_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=40),
    )

    registry = {"tokens": [older, newer]}

    selected = find_latest_active_token_in_group(
        registry,
        "ui-service",
    )

    assert selected is not None
    assert selected["token_id"] == "newer"


def test_find_latest_ignores_expired_token() -> None:
    now = datetime.now(timezone.utc)

    expired = make_record(
        token_id="expired-newer",
        issued_at=now - timedelta(days=5),
        expires_at=now - timedelta(days=1),
    )
    valid = make_record(
        token_id="valid-older",
        issued_at=now - timedelta(days=20),
        expires_at=now + timedelta(days=20),
    )

    registry = {"tokens": [valid, expired]}

    selected = find_latest_active_token_in_group(
        registry,
        "ui-service",
    )

    assert selected is not None
    assert selected["token_id"] == "valid-older"


def test_find_latest_ignores_revoked_token() -> None:
    now = datetime.now(timezone.utc)

    revoked = make_record(
        token_id="revoked-newer",
        issued_at=now - timedelta(days=5),
        expires_at=now + timedelta(days=30),
        revoked_at=iso_z(now - timedelta(days=1)),
    )
    valid = make_record(
        token_id="valid-older",
        issued_at=now - timedelta(days=20),
        expires_at=now + timedelta(days=20),
    )

    registry = {"tokens": [valid, revoked]}

    selected = find_latest_active_token_in_group(
        registry,
        "ui-service",
    )

    assert selected is not None
    assert selected["token_id"] == "valid-older"


def test_find_latest_ignores_inactive_token() -> None:
    now = datetime.now(timezone.utc)

    inactive = make_record(
        token_id="inactive-newer",
        issued_at=now - timedelta(days=5),
        expires_at=now + timedelta(days=30),
        active=False,
    )
    valid = make_record(
        token_id="valid-older",
        issued_at=now - timedelta(days=20),
        expires_at=now + timedelta(days=20),
    )

    registry = {"tokens": [valid, inactive]}

    selected = find_latest_active_token_in_group(
        registry,
        "ui-service",
    )

    assert selected is not None
    assert selected["token_id"] == "valid-older"


def test_find_latest_returns_none_without_valid_candidate() -> None:
    now = datetime.now(timezone.utc)

    expired = make_record(
        token_id="expired",
        issued_at=now - timedelta(days=10),
        expires_at=now - timedelta(days=1),
    )

    registry = {"tokens": [expired]}

    selected = find_latest_active_token_in_group(
        registry,
        "ui-service",
    )

    assert selected is None