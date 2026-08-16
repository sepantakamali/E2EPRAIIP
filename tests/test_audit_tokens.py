from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "audit_tokens.py"


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def make_token(
    *,
    token_id: str = "test-token-1",
    active: bool = True,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    revoked_at: str | None = None,
    replaces: str | None = None,
    replaced_by: str | None = None,
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    issued = issued_at or now - timedelta(days=1)
    expires = expires_at or now + timedelta(days=90)

    return {
        "token_id": token_id,
        "subject": "test-service",
        "client_id": "test-service",
        "scopes": scopes or ["predict:run"],
        "active": active,
        "token_hash": "sha256:" + ("a" * 64),
        "issued_at": iso_z(issued),
        "expires_at": iso_z(expires),
        "revoked_at": revoked_at,
        "replaces": replaces,
        "replaced_by": replaced_by,
        "overlap_until": None,
        "rotation_group": "test-service",
    }


def write_registry(
    tmp_path: Path,
    tokens: list[dict[str, Any]],
) -> Path:
    registry_path = tmp_path / "tokens.json"
    registry_path.write_text(
        json.dumps({"tokens": tokens}, indent=2),
        encoding="utf-8",
    )
    return registry_path


def run_audit(
    registry_path: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry_path),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_registry_returns_zero(tmp_path: Path) -> None:
    token = make_token(expires_at=datetime.now(timezone.utc) + timedelta(days=90))
    registry = write_registry(tmp_path, [token])

    result = run_audit(registry)

    assert result.returncode == 0
    assert "Token registry audit passed" in result.stdout


def test_warning_without_fail_on_warning_returns_zero(
    tmp_path: Path,
) -> None:
    token = make_token(expires_at=datetime.now(timezone.utc) + timedelta(days=10))
    registry = write_registry(tmp_path, [token])

    result = run_audit(registry)

    assert result.returncode == 0
    assert "WARNING:" in result.stdout


def test_warning_with_fail_on_warning_returns_one(
    tmp_path: Path,
) -> None:
    token = make_token(expires_at=datetime.now(timezone.utc) + timedelta(days=10))
    registry = write_registry(tmp_path, [token])

    result = run_audit(registry, "--fail-on-warning")

    assert result.returncode == 1
    assert "WARNING:" in result.stdout


def test_active_expired_token_returns_two(tmp_path: Path) -> None:
    token = make_token(
        active=True,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    registry = write_registry(tmp_path, [token])

    result = run_audit(registry)

    assert result.returncode == 2
    assert "active token expired" in result.stdout


def test_inactive_expired_token_is_not_active_expiry_error(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)

    token = make_token(
        active=False,
        issued_at=now - timedelta(days=10),
        expires_at=now - timedelta(days=1),
    )
    registry = write_registry(tmp_path, [token])

    result = run_audit(registry)

    assert result.returncode == 0
    assert "active token expired" not in result.stdout


def test_duplicate_token_id_returns_two(tmp_path: Path) -> None:
    first = make_token(token_id="duplicate")
    second = make_token(token_id="duplicate")
    registry = write_registry(tmp_path, [first, second])

    result = run_audit(registry)

    assert result.returncode == 2
    assert "Duplicate token_id: duplicate" in result.stdout


def test_invalid_scope_returns_two(tmp_path: Path) -> None:
    token = make_token(scopes=["predict:run", "admin:everything"])
    registry = write_registry(tmp_path, [token])

    result = run_audit(registry)

    assert result.returncode == 2
    assert "invalid scope: admin:everything" in result.stdout


def test_broken_replacement_link_returns_two(tmp_path: Path) -> None:
    predecessor = make_token(
        token_id="old-token",
        active=False,
        replaced_by="new-token",
    )
    successor = make_token(
        token_id="new-token",
        replaces=None,
    )
    registry = write_registry(tmp_path, [predecessor, successor])

    result = run_audit(registry)

    assert result.returncode == 2
    assert "does not point back through replaces" in result.stdout


def test_timezone_naive_timestamp_returns_two(tmp_path: Path) -> None:
    token = make_token()
    token["expires_at"] = "2026-12-01T12:00:00"
    registry = write_registry(tmp_path, [token])

    result = run_audit(registry)

    assert result.returncode == 2
    assert "must include a timezone" in result.stdout


def test_prometheus_output_contains_expected_metrics(
    tmp_path: Path,
) -> None:
    token = make_token(
        token_id="prometheus-test",
        expires_at=datetime.now(timezone.utc) + timedelta(days=10),
    )
    registry = write_registry(tmp_path, [token])
    metrics_file = tmp_path / "token-expiry.prom"

    result = run_audit(
        registry,
        "--prometheus-file",
        str(metrics_file),
    )

    metrics = metrics_file.read_text(encoding="utf-8")

    assert result.returncode == 0
    assert "textclf_token_registry_valid 1" in metrics
    assert "textclf_token_active_expired_total 0" in metrics
    assert "textclf_token_active_warning_total 1" in metrics
    assert 'token_id="prometheus-test"' in metrics
    assert "textclf_token_audit_timestamp_seconds" in metrics

    assert "token_hash" not in metrics
    assert "sha256:" not in metrics


def test_prometheus_registry_valid_is_zero_on_error(
    tmp_path: Path,
) -> None:
    token = make_token(
        active=True,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    registry = write_registry(tmp_path, [token])
    metrics_file = tmp_path / "token-expiry.prom"

    result = run_audit(
        registry,
        "--prometheus-file",
        str(metrics_file),
    )

    metrics = metrics_file.read_text(encoding="utf-8")

    assert result.returncode == 2
    assert "textclf_token_registry_valid 0" in metrics
    assert "textclf_token_active_expired_total 1" in metrics


def test_non_list_scopes_returns_two(tmp_path: Path) -> None:
    token = make_token()
    token["scopes"] = None
    registry = write_registry(tmp_path, [token])

    result = run_audit(registry)

    assert result.returncode == 2
    assert "scopes must be a list of strings" in result.stdout


def test_active_replaced_token_with_valid_overlap_is_allowed(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)

    old = make_token(
        token_id="old",
        active=True,
        replaced_by="new",
    )
    old["overlap_until"] = iso_z(
        now + timedelta(minutes=15)
    )

    new = make_token(
        token_id="new",
        replaces="old",
    )

    registry = write_registry(
        tmp_path,
        [old, new],
    )

    result = run_audit(registry)

    assert result.returncode == 0


def test_expired_rotation_overlap_is_invalid(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)

    old = make_token(
        token_id="old",
        active=True,
        replaced_by="new",
    )
    old["overlap_until"] = iso_z(
        now - timedelta(minutes=1)
    )

    new = make_token(
        token_id="new",
        replaces="old",
    )

    registry = write_registry(
        tmp_path,
        [old, new],
    )

    result = run_audit(registry)

    assert result.returncode == 2
    assert "rotation overlap expired" in result.stdout