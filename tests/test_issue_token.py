from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import argparse
import json


from textclf.token_store import find_latest_active_token_in_group
from admin.token_issuance import iso_z

from admin.token_issuance import issue_token


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
        "overlap_until": None,
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
        now=now,
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
        now=now,
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
        now=now,
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
        now=now,
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
        now=now,
    )

    assert selected is None


def test_issue_replacement_without_overlap_deactivates_old_token(
    tmp_path,
    monkeypatch,
) -> None:
    now = datetime.now(timezone.utc)

    old = make_record(
        token_id="old-token",
        issued_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=30),
    )

    registry_path = tmp_path / "tokens.json"
    registry_path.write_text(
        json.dumps({"tokens": [old]}),
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "AUTH_TOKENS_FILE",
        str(registry_path),
    )

    issue_token(
        registry_path=registry_path,
        subject="ui-service",
        client_id="ui-service",
        scopes=["predict:run"],
        ttl_days=90,
        token_id="new-token",
        token_bytes=32,
        replaces="old-token",
        rotation_group="ui-service",
        replace_latest=False,
        overlap_minutes=0,
    )

    registry = json.loads(
        registry_path.read_text(encoding="utf-8")
    )

    old_record = registry["tokens"][0]
    new_record = registry["tokens"][1]

    assert old_record["active"] is False
    assert old_record["replaced_by"] == "new-token"
    assert old_record["overlap_until"] is None

    assert new_record["active"] is True
    assert new_record["replaces"] == "old-token"
    assert new_record["overlap_until"] is None


def test_issue_replacement_with_overlap_keeps_old_token_temporarily_active(
    tmp_path,
    monkeypatch,
) -> None:
    now = datetime.now(timezone.utc)

    old = make_record(
        token_id="old-token",
        issued_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=30),
    )

    registry_path = tmp_path / "tokens.json"
    registry_path.write_text(
        json.dumps({"tokens": [old]}),
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "AUTH_TOKENS_FILE",
        str(registry_path),
    )

    before_issue = datetime.now(timezone.utc)

    issue_token(
        registry_path=registry_path,
        subject="ui-service",
        client_id="ui-service",
        scopes=["predict:run"],
        ttl_days=90,
        token_id="new-token",
        token_bytes=32,
        replaces="old-token",
        rotation_group="ui-service",
        replace_latest=False,
        overlap_minutes=15,
    )

    registry = json.loads(
        registry_path.read_text(encoding="utf-8")
    )

    old_record = registry["tokens"][0]
    new_record = registry["tokens"][1]

    assert old_record["active"] is True
    assert old_record["replaced_by"] == "new-token"
    assert old_record["overlap_until"] is not None

    overlap_until = datetime.fromisoformat(
        old_record["overlap_until"].replace("Z", "+00:00")
    )

    assert overlap_until > before_issue
    assert overlap_until <= before_issue + timedelta(minutes=16)

    assert new_record["active"] is True
    assert new_record["replaces"] == "old-token"
    assert new_record["overlap_until"] is None