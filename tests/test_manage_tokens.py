from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.manage_tokens as manage_tokens

from typing import cast

from textclf.token_rotation import RotationPlan


def write_registry(path: Path) -> Path:
    registry = {
        "tokens": [
            {
                "token_id": "ui-service-current",
                "subject": "ui-service",
                "client_id": "ui-service",
                "scopes": [
                    "predict:run",
                    "models:read",
                    "version:read",
                    "whoami:read",
                ],
                "active": True,
                "token_hash": "sha256:" + ("a" * 64),
                "issued_at": "2026-08-01T00:00:00Z",
                "expires_at": "2026-11-01T00:00:00Z",
                "revoked_at": None,
                "replaces": None,
                "replaced_by": None,
                "overlap_until": None,
                "rotation_group": "ui-service",
            }
        ]
    }

    path.write_text(
        json.dumps(registry),
        encoding="utf-8",
    )

    return path


def write_policy(path: Path) -> Path:
    path.write_text(
        """
principals:
  ui-service:
    rotation_group: ui-service
    subject: ui-service
    client_id: ui-service
    default_scopes:
      - predict:run
      - models:read
      - version:read
      - whoami:read
    ttl_days: 90
    overlap_minutes: 15

    consumer:
      type: docker-compose
      secret_path: /tmp/ui_api_token.txt
      container_secret_path: /run/secrets/ui_api_token
      compose_file: /tmp/docker-compose.product.yml
      compose_service: ui
      container_name: textclf-ui
      health_timeout_seconds: 60

    verification:
      type: api-whoami
      endpoint: /whoami
      expected_subject: ui-service
      expected_client_id: ui-service

    auto_rotation_supported: true
""",
        encoding="utf-8",
    )

    return path


def test_rotate_cancel_does_not_execute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = write_registry(
        tmp_path / "tokens.json"
    )
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )

    monkeypatch.setenv(
        "AUTH_TOKENS_FILE",
        str(registry_path),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "manage_tokens.py",
            "rotate",
            "ui-service",
            "--policy",
            str(policy_path),
        ],
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _: "n",
    )

    def fail_execute_rotation(**kwargs: object) -> None:
        raise AssertionError(
            "execute_rotation should not be called"
        )

    monkeypatch.setattr(
        manage_tokens,
        "execute_rotation",
        fail_execute_rotation,
    )

    manage_tokens.main()


def test_rotate_approved_calls_execute_rotation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = write_registry(
        tmp_path / "tokens.json"
    )
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )

    monkeypatch.setenv(
        "AUTH_TOKENS_FILE",
        str(registry_path),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "manage_tokens.py",
            "rotate",
            "ui-service",
            "--policy",
            str(policy_path),
        ],
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _: "y",
    )

    monkeypatch.setattr(
        manage_tokens,
        "build_restart_callback",
        lambda **kwargs: lambda: None,
    )

    monkeypatch.setattr(
        manage_tokens,
        "build_verification_callback",
        lambda **kwargs: lambda: True,
    )

    captured: dict[str, object] = {}

    def fake_execute_rotation(
        **kwargs: object,
    ) -> SimpleNamespace:
        captured.update(kwargs)

        return SimpleNamespace(
            old_token_id="ui-service-current",
            new_token_id="ui-service-new",
        )

    monkeypatch.setattr(
        manage_tokens,
        "execute_rotation",
        fake_execute_rotation,
    )

    manage_tokens.main()

    plan = cast(RotationPlan, captured["plan"])

    assert plan.principal == "ui-service"
    assert plan.ttl_days == 90
    assert plan.overlap_minutes == 15


def test_rotate_uses_admin_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = write_registry(
        tmp_path / "tokens.json"
    )
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )

    monkeypatch.setenv(
        "AUTH_TOKENS_FILE",
        str(registry_path),
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "manage_tokens.py",
            "rotate",
            "ui-service",
            "--policy",
            str(policy_path),
            "--ttl-days",
            "120",
            "--overlap-minutes",
            "30",
            "--scopes",
            "predict:run",
            "whoami:read",
        ],
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _: "yes",
    )

    monkeypatch.setattr(
        manage_tokens,
        "build_restart_callback",
        lambda **kwargs: lambda: None,
    )

    monkeypatch.setattr(
        manage_tokens,
        "build_verification_callback",
        lambda **kwargs: lambda: True,
    )

    captured: dict[str, object] = {}

    def fake_execute_rotation(
        **kwargs: object,
    ) -> SimpleNamespace:
        captured.update(kwargs)

        return SimpleNamespace(
            old_token_id="ui-service-current",
            new_token_id="ui-service-new",
        )

    monkeypatch.setattr(
        manage_tokens,
        "execute_rotation",
        fake_execute_rotation,
    )

    manage_tokens.main()

    plan = cast(RotationPlan, captured["plan"])

    assert plan.ttl_days == 120
    assert plan.overlap_minutes == 30
    assert plan.scopes == [
        "predict:run",
        "whoami:read",
    ]