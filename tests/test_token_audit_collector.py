from __future__ import annotations

import json

from datetime import datetime, timedelta, timezone
from pathlib import Path

import textclf.api as api


def iso_z(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def write_token_registry(
    path: Path,
    *,
    expires_in_days: int,
) -> Path:
    now = datetime.now(timezone.utc)

    registry = {
        "tokens": [
            {
                "token_id": "collector-test-token",
                "subject": "collector-test",
                "client_id": "collector-test",
                "scopes": ["predict:run"],
                "active": True,
                "token_hash": "sha256:" + ("a" * 64),
                "issued_at": iso_z(now - timedelta(days=1)),
                "expires_at": iso_z(
                    now + timedelta(days=expires_in_days)
                ),
                "revoked_at": None,
                "replaces": None,
                "replaced_by": None,
                "overlap_until": None,
                "rotation_group": "collector-test",
            }
        ]
    }

    path.write_text(
        json.dumps(registry),
        encoding="utf-8",
    )

    return path


def metric_value(metric_family) -> float:
    assert len(metric_family.samples) == 1
    return float(metric_family.samples[0].value)

def test_collector_exports_valid_token_metrics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry_path = write_token_registry(
        tmp_path / "tokens.json",
        expires_in_days=10,
    )

    monkeypatch.setattr(
        api,
        "AUTH_TOKENS_FILE",
        str(registry_path),
    )

    collector = api.TokenAuditCollector()

    families = {
        metric.name: metric
        for metric in collector.collect()
    }

    assert metric_value(
        families["textclf_token_registry_valid"]
    ) == 1

    assert metric_value(
        families["textclf_token_active_expired_total"]
    ) == 0

    assert metric_value(
        families["textclf_token_active_warning_total"]
    ) == 1

    remaining = families[
        "textclf_token_days_remaining"
    ]

    assert len(remaining.samples) == 1

    sample = remaining.samples[0]

    assert sample.labels == {
        "token_id": "collector-test-token",
        "client_id": "collector-test",
        "rotation_group": "collector-test",
    }

    assert 9 < float(sample.value) <= 10

def test_collector_exports_expired_token(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry_path = write_token_registry(
        tmp_path / "tokens.json",
        expires_in_days=-1,
    )

    monkeypatch.setattr(
        api,
        "AUTH_TOKENS_FILE",
        str(registry_path),
    )

    families = {
        metric.name: metric
        for metric in api.TokenAuditCollector().collect()
    }

    assert metric_value(
        families["textclf_token_registry_valid"]
    ) == 0

    assert metric_value(
        families["textclf_token_active_expired_total"]
    ) == 1

    assert (
        families[
            "textclf_token_days_remaining"
        ].samples
        == []
    )


def test_collector_does_not_raise_for_invalid_registry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry_path = tmp_path / "tokens.json"

    registry_path.write_text(
        "{ definitely-not-json",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        api,
        "AUTH_TOKENS_FILE",
        str(registry_path),
    )

    families = {
        metric.name: metric
        for metric in api.TokenAuditCollector().collect()
    }

    assert metric_value(
        families["textclf_token_registry_valid"]
    ) == 0

    assert metric_value(
        families["textclf_token_active_expired_total"]
    ) == 0

    assert metric_value(
        families["textclf_token_active_warning_total"]
    ) == 0


def test_collector_handles_missing_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        api,
        "AUTH_TOKENS_FILE",
        None,
    )

    families = {
        metric.name: metric
        for metric in api.TokenAuditCollector().collect()
    }

    assert metric_value(
        families["textclf_token_registry_valid"]
    ) == 0

    assert metric_value(
        families["textclf_token_active_expired_total"]
    ) == 0

    assert metric_value(
        families["textclf_token_active_warning_total"]
    ) == 0