from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from textclf.token_issuance import iso_z

from textclf.token_rotation import (
    RotationPlan,
    abort_rotation,
    build_rotation_plan,
    execute_rotation,
    finalize_rotation,
    install_consumer_secret,
    prepare_rotation,
)


def write_policy(
    path: Path,
    *,
    auto_rotation_supported: bool = True,
) -> Path:
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
    
    auto_rotation_supported: """
        + ("true" if auto_rotation_supported else "false")
        + "\n",
        encoding="utf-8",
    )
    return path


def write_registry(
    path: Path,
    *,
    active: bool = True,
    expires_in_days: int = 30,
) -> Path:
    now = datetime.now(timezone.utc)

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
                "active": active,
                "token_hash": "sha256:" + ("a" * 64),
                "issued_at": iso_z(now - timedelta(days=10)),
                "expires_at": iso_z(
                    now + timedelta(days=expires_in_days)
                ),
                "revoked_at": None,
                "replaces": None,
                "replaced_by": None,
                "overlap_until": None,
                "rotation_group": "ui-service",
            }
        ]
    }

    path.write_text(json.dumps(registry), encoding="utf-8")
    return path


def test_build_rotation_plan_from_valid_policy(
    tmp_path: Path,
) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )
    registry_path = write_registry(tmp_path / "tokens.json")
    now = datetime.now(timezone.utc)

    plan = build_rotation_plan(
        principal="ui-service",
        policy_path=policy_path,
        registry_path=registry_path,
        now=now,
    )

    assert plan.principal == "ui-service"
    assert plan.current_token_id == "ui-service-current"
    assert plan.subject == "ui-service"
    assert plan.client_id == "ui-service"
    assert plan.rotation_group == "ui-service"
    assert plan.scopes == [
        "predict:run",
        "models:read",
        "version:read",
        "whoami:read",
    ]
    assert plan.ttl_days == 90
    assert plan.overlap_minutes == 15
    assert plan.consumer_secret_path == Path(
        "/tmp/ui_api_token.txt"
    )
    assert plan.compose_service == "ui"
    assert plan.verification_endpoint == "/whoami"
    assert plan.expected_subject == "ui-service"
    assert plan.expected_client_id == "ui-service"


def test_unknown_principal_is_rejected(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )
    registry_path = write_registry(tmp_path / "tokens.json")

    with pytest.raises(
        ValueError,
        match="Unknown token principal: unknown-service",
    ):
        build_rotation_plan(
            principal="unknown-service",
            policy_path=policy_path,
            registry_path=registry_path,
        )


def test_principal_without_rotation_support_is_rejected(
    tmp_path: Path,
) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml",
        auto_rotation_supported=False,
    )
    registry_path = write_registry(tmp_path / "tokens.json")

    with pytest.raises(
        ValueError,
        match=(
            "Automated rotation is not supported for principal: "
            "ui-service"
        ),
    ):
        build_rotation_plan(
            principal="ui-service",
            policy_path=policy_path,
            registry_path=registry_path,
        )


def test_invalid_scope_in_policy_is_rejected(
    tmp_path: Path,
) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )
    registry_path = write_registry(tmp_path / "tokens.json")

    policy_text = policy_path.read_text(encoding="utf-8")
    policy_path.write_text(
        policy_text.replace(
            "      - whoami:read\n",
            "      - whoami:read\n"
            "      - admin:everything\n",
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"Unknown scope\(s\): admin:everything",
    ):
        build_rotation_plan(
            principal="ui-service",
            policy_path=policy_path,
            registry_path=registry_path,
        )


def test_no_active_token_is_rejected(tmp_path: Path) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )
    registry_path = write_registry(
        tmp_path / "tokens.json",
        active=False,
    )

    with pytest.raises(
        ValueError,
        match=(
            "No active token found for rotation group: ui-service"
        ),
    ):
        build_rotation_plan(
            principal="ui-service",
            policy_path=policy_path,
            registry_path=registry_path,
        )


def test_invalid_consumer_configuration_is_rejected(
    tmp_path: Path,
) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )
    registry_path = write_registry(tmp_path / "tokens.json")

    policy_text = policy_path.read_text(encoding="utf-8")
    policy_path.write_text(
        policy_text.replace(
            "      type: docker-compose\n",
            "      type: unsupported\n",
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="unsupported consumer type: unsupported",
    ):
        build_rotation_plan(
            principal="ui-service",
            policy_path=policy_path,
            registry_path=registry_path,
        )


def test_prepare_rotation_creates_successor_with_overlap(
    tmp_path: Path,
) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )
    registry_path = write_registry(
        tmp_path / "tokens.json"
    )

    now = datetime.now(timezone.utc)

    plan = build_rotation_plan(
        principal="ui-service",
        policy_path=policy_path,
        registry_path=registry_path,
        now=now,
    )

    prepared = prepare_rotation(
        plan=plan,
        registry_path=registry_path,
        now=now,
    )

    registry = json.loads(
        registry_path.read_text(encoding="utf-8")
    )

    old = next(
        record
        for record in registry["tokens"]
        if record["token_id"] == "ui-service-current"
    )

    new = next(
        record
        for record in registry["tokens"]
        if record["token_id"] == prepared.issued.token_id
    )

    assert old["active"] is True
    assert old["replaced_by"] == new["token_id"]
    assert old["overlap_until"] is not None

    assert new["active"] is True
    assert new["replaces"] == old["token_id"]
    assert new["rotation_group"] == "ui-service"

    assert prepared.issued.raw_token
    assert prepared.issued.raw_token not in registry_path.read_text(
        encoding="utf-8"
    )


def test_prepare_rotation_uses_plan_overrides(
    tmp_path: Path,
) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )
    registry_path = write_registry(
        tmp_path / "tokens.json"
    )

    now = datetime.now(timezone.utc)

    plan = build_rotation_plan(
        principal="ui-service",
        policy_path=policy_path,
        registry_path=registry_path,
        now=now,
    )

    plan = RotationPlan(
        principal=plan.principal,
        current_token_id=plan.current_token_id,
        subject=plan.subject,
        client_id=plan.client_id,
        rotation_group=plan.rotation_group,
        scopes=["predict:run", "whoami:read"],
        ttl_days=120,
        overlap_minutes=30,
        consumer_secret_path=plan.consumer_secret_path,
        compose_service=plan.compose_service,
        verification_endpoint=plan.verification_endpoint,
        expected_subject=plan.expected_subject,
        expected_client_id=plan.expected_client_id,
        consumer_type=plan.consumer_type,
        container_secret_path=plan.container_secret_path,
        compose_file=plan.compose_file,
        container_name=plan.container_name,
        health_timeout_seconds=plan.health_timeout_seconds,
        verification_type=plan.verification_type,
    )

    prepared = prepare_rotation(
        plan=plan,
        registry_path=registry_path,
        now=now,
    )

    registry = json.loads(
        registry_path.read_text(encoding="utf-8")
    )

    new = next(
        record
        for record in registry["tokens"]
        if record["token_id"] == prepared.issued.token_id
    )

    assert new["scopes"] == [
        "predict:run",
        "whoami:read",
    ]
    assert new["expires_at"] == iso_z(
        now + timedelta(days=120)
    )


def test_install_consumer_secret_replaces_token_and_preserves_mode(
    tmp_path: Path,
) -> None:
    secret_path = tmp_path / "ui_api_token.txt"
    secret_path.write_text("old-token\n", encoding="utf-8")
    secret_path.chmod(0o640)

    original = secret_path.stat()

    previous = install_consumer_secret(
        path=secret_path,
        raw_token="new-token",
    )

    updated = secret_path.stat()

    assert previous == "old-token"
    assert secret_path.read_text(encoding="utf-8") == "new-token\n"
    assert updated.st_mode & 0o777 == 0o640
    assert updated.st_uid == original.st_uid
    assert updated.st_gid == original.st_gid


def test_install_consumer_secret_does_not_leave_temp_file(
    tmp_path: Path,
) -> None:
    secret_path = tmp_path / "ui_api_token.txt"
    secret_path.write_text("old-token\n", encoding="utf-8")
    secret_path.chmod(0o640)

    install_consumer_secret(
        path=secret_path,
        raw_token="new-token",
    )

    leftovers = list(
        tmp_path.glob(".ui_api_token.txt.*")
    )

    assert leftovers == []


def test_finalize_rotation_deactivates_predecessor(
    tmp_path: Path,
) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )
    registry_path = write_registry(
        tmp_path / "tokens.json"
    )
    now = datetime.now(timezone.utc)

    plan = build_rotation_plan(
        principal="ui-service",
        policy_path=policy_path,
        registry_path=registry_path,
        now=now,
    )

    prepared = prepare_rotation(
        plan=plan,
        registry_path=registry_path,
        now=now,
    )

    finalize_rotation(
        prepared=prepared,
        registry_path=registry_path,
    )

    registry = json.loads(
        registry_path.read_text(encoding="utf-8")
    )

    old = next(
        record
        for record in registry["tokens"]
        if record["token_id"] == "ui-service-current"
    )

    new = next(
        record
        for record in registry["tokens"]
        if record["token_id"] == prepared.issued.token_id
    )

    assert old["active"] is False
    assert old["overlap_until"] is None
    assert old["replaced_by"] == new["token_id"]
    assert new["active"] is True


def test_abort_rotation_restores_predecessor_and_removes_successor(
    tmp_path: Path,
) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )
    registry_path = write_registry(
        tmp_path / "tokens.json"
    )
    now = datetime.now(timezone.utc)

    plan = build_rotation_plan(
        principal="ui-service",
        policy_path=policy_path,
        registry_path=registry_path,
        now=now,
    )

    prepared = prepare_rotation(
        plan=plan,
        registry_path=registry_path,
        now=now,
    )

    abort_rotation(
        prepared=prepared,
        registry_path=registry_path,
    )

    registry = json.loads(
        registry_path.read_text(encoding="utf-8")
    )

    assert len(registry["tokens"]) == 1

    old = registry["tokens"][0]

    assert old["token_id"] == "ui-service-current"
    assert old["active"] is True
    assert old["replaced_by"] is None
    assert old["overlap_until"] is None


def test_execute_rotation_successfully_commits(
    tmp_path: Path,
) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )
    registry_path = write_registry(
        tmp_path / "tokens.json"
    )

    secret_path = tmp_path / "ui_api_token.txt"
    secret_path.write_text(
        "old-raw-token\n",
        encoding="utf-8",
    )
    secret_path.chmod(0o640)

    now = datetime.now(timezone.utc)

    plan = build_rotation_plan(
        principal="ui-service",
        policy_path=policy_path,
        registry_path=registry_path,
        now=now,
    )

    plan = RotationPlan(
        principal=plan.principal,
        current_token_id=plan.current_token_id,
        subject=plan.subject,
        client_id=plan.client_id,
        rotation_group=plan.rotation_group,
        scopes=plan.scopes,
        ttl_days=plan.ttl_days,
        overlap_minutes=plan.overlap_minutes,
        consumer_secret_path=secret_path,
        compose_service=plan.compose_service,
        verification_endpoint=plan.verification_endpoint,
        expected_subject=plan.expected_subject,
        expected_client_id=plan.expected_client_id,
        consumer_type=plan.consumer_type,
        container_secret_path=plan.container_secret_path,
        compose_file=plan.compose_file,
        container_name=plan.container_name,
        health_timeout_seconds=plan.health_timeout_seconds,
        verification_type=plan.verification_type,
    )

    restart_calls = 0

    def restart_consumer() -> None:
        nonlocal restart_calls
        restart_calls += 1

    def verify_consumer() -> bool:
        return (
            secret_path.read_text(
                encoding="utf-8"
            ).strip()
            != "old-raw-token"
        )

    result = execute_rotation(
        plan=plan,
        registry_path=registry_path,
        restart_consumer=restart_consumer,
        verify_consumer=verify_consumer,
    )

    registry = json.loads(
        registry_path.read_text(encoding="utf-8")
    )

    old = next(
        record
        for record in registry["tokens"]
        if record["token_id"] == result.old_token_id
    )

    new = next(
        record
        for record in registry["tokens"]
        if record["token_id"] == result.new_token_id
    )

    assert restart_calls == 1
    assert old["active"] is False
    assert old["replaced_by"] == new["token_id"]
    assert old["overlap_until"] is None
    assert new["active"] is True
    assert secret_path.read_text(
        encoding="utf-8"
    ).strip() != "old-raw-token"


def test_execute_rotation_rolls_back_on_verification_failure(
    tmp_path: Path,
) -> None:
    policy_path = write_policy(
        tmp_path / "token-principals.yml"
    )
    registry_path = write_registry(
        tmp_path / "tokens.json"
    )

    secret_path = tmp_path / "ui_api_token.txt"
    secret_path.write_text(
        "old-raw-token\n",
        encoding="utf-8",
    )
    secret_path.chmod(0o640)

    now = datetime.now(timezone.utc)

    plan = build_rotation_plan(
        principal="ui-service",
        policy_path=policy_path,
        registry_path=registry_path,
        now=now,
    )

    plan = RotationPlan(
        principal=plan.principal,
        current_token_id=plan.current_token_id,
        subject=plan.subject,
        client_id=plan.client_id,
        rotation_group=plan.rotation_group,
        scopes=plan.scopes,
        ttl_days=plan.ttl_days,
        overlap_minutes=plan.overlap_minutes,
        consumer_secret_path=secret_path,
        compose_service=plan.compose_service,
        verification_endpoint=plan.verification_endpoint,
        expected_subject=plan.expected_subject,
        expected_client_id=plan.expected_client_id,
        consumer_type=plan.consumer_type,
        container_secret_path=plan.container_secret_path,
        compose_file=plan.compose_file,
        container_name=plan.container_name,
        health_timeout_seconds=plan.health_timeout_seconds,
        verification_type=plan.verification_type,
    )

    restart_calls = 0

    def restart_consumer() -> None:
        nonlocal restart_calls
        restart_calls += 1

    def verify_consumer() -> bool:
        return False

    with pytest.raises(
        RuntimeError,
        match="New token failed consumer verification",
    ):
        execute_rotation(
            plan=plan,
            registry_path=registry_path,
            restart_consumer=restart_consumer,
            verify_consumer=verify_consumer,
        )

    registry = json.loads(
        registry_path.read_text(encoding="utf-8")
    )

    assert restart_calls == 2
    assert len(registry["tokens"]) == 1

    old = registry["tokens"][0]

    assert old["token_id"] == "ui-service-current"
    assert old["active"] is True
    assert old["replaced_by"] is None
    assert old["overlap_until"] is None

    assert secret_path.read_text(
        encoding="utf-8"
    ) == "old-raw-token\n"