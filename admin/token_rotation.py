from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from textclf.token_store import (
    find_latest_active_token_in_group,
    load_registry,
    save_registry,
    validate_scopes,
)

from admin.token_issuance import IssuedToken, issue_token

import os
import tempfile

from collections.abc import Callable

def install_consumer_secret(
    *,
    path: Path,
    raw_token: str,
) -> str:
    stat_result = path.stat()
    previous_token = path.read_text(
        encoding="utf-8"
    ).strip()

    fd, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(raw_token)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        os.chmod(
            temporary_path,
            stat_result.st_mode & 0o777,
        )

        os.chown(
            temporary_path,
            stat_result.st_uid,
            stat_result.st_gid,
        )

        os.replace(
            temporary_path,
            path,
        )

        return previous_token

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise 


@dataclass(frozen=True)
class RotationPlan:
    principal: str
    current_token_id: str
    subject: str
    client_id: str
    rotation_group: str
    scopes: list[str]
    ttl_days: int
    overlap_minutes: int
    consumer_type: str
    consumer_secret_path: Path
    container_secret_path: Path
    compose_file: str
    compose_service: str
    container_name: str
    health_timeout_seconds: int
    verification_type: str
    verification_endpoint: str
    expected_subject: str
    expected_client_id: str


@dataclass(frozen=True)
class PreparedRotation:
    plan: RotationPlan
    issued: IssuedToken


def load_principal_policy(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError("Token-principals policy must be a YAML object")

    principals = data.get("principals")
    if not isinstance(principals, dict):
        raise ValueError(
            "Token-principals policy must contain a 'principals' mapping"
        )

    return principals


def build_rotation_plan(
    *,
    principal: str,
    policy_path: Path,
    registry_path: Path,
    now: datetime | None = None,
) -> RotationPlan:
    current_time = now or datetime.now(timezone.utc)

    principals = load_principal_policy(policy_path)
    config = principals.get(principal)

    if not isinstance(config, dict):
        raise ValueError(f"Unknown token principal: {principal}")

    if config.get("auto_rotation_supported") is not True:
        raise ValueError(
            f"Automated rotation is not supported for principal: {principal}"
        )

    subject = config.get("subject")
    client_id = config.get("client_id")
    rotation_group = config.get("rotation_group")
    scopes = config.get("default_scopes")
    ttl_days = config.get("ttl_days")
    overlap_minutes = config.get("overlap_minutes")
    consumer = config.get("consumer")

    if not isinstance(subject, str) or not subject:
        raise ValueError(
            f"{principal}: subject must be a non-empty string"
        )

    if not isinstance(client_id, str) or not client_id:
        raise ValueError(
            f"{principal}: client_id must be a non-empty string"
        )

    if not isinstance(rotation_group, str) or not rotation_group:
        raise ValueError(
            f"{principal}: rotation_group must be a non-empty string"
        )

    registry = load_registry(registry_path)

    rotation_in_progress = any(
        record.get("rotation_group") == rotation_group
        and record.get("active") is True
        and record.get("replaced_by") is not None
        and record.get("overlap_until") is not None
        for record in registry["tokens"]
    )

    if rotation_in_progress:
        raise ValueError(
            f"Rotation already in progress for rotation group: "
            f"{rotation_group}"
        )

    if not isinstance(scopes, list) or not all(
        isinstance(scope, str) and scope
        for scope in scopes
    ):
        raise ValueError(
            f"{principal}: default_scopes must be a list of strings"
        )

    validate_scopes(scopes)

    if not isinstance(ttl_days, int) or ttl_days <= 0:
        raise ValueError(
            f"{principal}: ttl_days must be a positive integer"
        )

    if (
        not isinstance(overlap_minutes, int)
        or overlap_minutes < 0
    ):
        raise ValueError(
            f"{principal}: overlap_minutes cannot be negative"
        )

    if not isinstance(consumer, dict):
        raise ValueError(
            f"{principal}: consumer configuration is required"
        )

    consumer_type = consumer.get("type")
    secret_path = consumer.get("secret_path")
    container_secret_path = consumer.get("container_secret_path")
    compose_file = consumer.get("compose_file")
    compose_service = consumer.get("compose_service")
    container_name = consumer.get("container_name")
    health_timeout_seconds = consumer.get(
        "health_timeout_seconds"
    )

    if consumer_type != "docker-compose":
        raise ValueError(
            f"{principal}: unsupported consumer type: "
            f"{consumer_type}"
        )

    if not isinstance(secret_path, str) or not secret_path:
        raise ValueError(
            f"{principal}: consumer.secret_path must be set"
        )

    if (
        not isinstance(container_secret_path, str)
        or not container_secret_path
    ):
        raise ValueError(
            f"{principal}: consumer.container_secret_path must be set"
        )

    if not isinstance(compose_file, str) or not compose_file:
        raise ValueError(
            f"{principal}: consumer.compose_file must be set"
        )

    if not isinstance(compose_service, str) or not compose_service:
        raise ValueError(
            f"{principal}: consumer.compose_service must be set"
        )

    if not isinstance(container_name, str) or not container_name:
        raise ValueError(
            f"{principal}: consumer.container_name must be set"
        )

    if (
        not isinstance(health_timeout_seconds, int)
        or health_timeout_seconds <= 0
    ):
        raise ValueError(
            f"{principal}: consumer.health_timeout_seconds "
            "must be a positive integer"
        )

    verification = config.get("verification")
    if not isinstance(verification, dict):
        raise ValueError(
            f"{principal}: verification configuration is required"
        )
    verification_type = verification.get("type")
    if verification_type != "api-whoami":
        raise ValueError(
            f"{principal}: unsupported verification type: "
            f"{verification_type}"
        )

    endpoint = verification.get("endpoint")
    expected_subject = verification.get("expected_subject")
    expected_client_id = verification.get("expected_client_id")

    if not isinstance(endpoint, str) or not endpoint.startswith("/"):
        raise ValueError(
            f"{principal}: verification.endpoint must start with '/'"
        )

    if not isinstance(expected_subject, str) or not expected_subject:
        raise ValueError(
            f"{principal}: verification.expected_subject must be set"
        )

    if (
        not isinstance(expected_client_id, str)
        or not expected_client_id
    ):
        raise ValueError(
            f"{principal}: verification.expected_client_id must be set"
        )

    current = find_latest_active_token_in_group(
        registry,
        rotation_group,
        now=current_time,
    )

    if current is None:
        raise ValueError(
            f"No active token found for rotation group: {rotation_group}"
        )

    if current.get("subject") != subject:
        raise ValueError(
            f"{principal}: current token subject does not match policy"
        )

    if current.get("client_id") != client_id:
        raise ValueError(
            f"{principal}: current token client_id does not match policy"
        )

    current_token_id = current.get("token_id")

    if not isinstance(current_token_id, str) or not current_token_id:
        raise ValueError(
            f"{principal}: current token has no valid token_id"
        )

    return RotationPlan(
        principal=principal,
        current_token_id=current_token_id,
        subject=subject,
        client_id=client_id,
        rotation_group=rotation_group,
        scopes=list(scopes),
        ttl_days=ttl_days,
        overlap_minutes=overlap_minutes,
        consumer_type=consumer_type,
        consumer_secret_path=Path(secret_path),
        container_secret_path=Path(container_secret_path),
        compose_file=compose_file,
        compose_service=compose_service,
        container_name=container_name,
        health_timeout_seconds=health_timeout_seconds,
        verification_type=verification_type,
        verification_endpoint=endpoint,
        expected_subject=expected_subject,
        expected_client_id=expected_client_id,
    )


def prepare_rotation(
    *,
    plan: RotationPlan,
    registry_path: Path,
    now: datetime | None = None,
) -> PreparedRotation:
    issued = issue_token(
        registry_path=registry_path,
        subject=plan.subject,
        client_id=plan.client_id,
        scopes=plan.scopes,
        ttl_days=plan.ttl_days,
        replaces=plan.current_token_id,
        rotation_group=plan.rotation_group,
        replace_latest=False,
        overlap_minutes=plan.overlap_minutes,
        now=now,
    )

    return PreparedRotation(
        plan=plan,
        issued=issued,
    )


def finalize_rotation(
    *,
    prepared: PreparedRotation,
    registry_path: Path,
) -> None:
    registry = load_registry(registry_path)

    old = next(
        (
            record
            for record in registry["tokens"]
            if record.get("token_id") == prepared.plan.current_token_id
        ),
        None,
    )
    new = next(
        (
            record
            for record in registry["tokens"]
            if record.get("token_id") == prepared.issued.token_id
        ),
        None,
    )

    if old is None:
        raise ValueError(
            f"Predecessor token not found: {prepared.plan.current_token_id}"
        )

    if new is None:
        raise ValueError(
            f"Successor token not found: {prepared.issued.token_id}"
        )

    if old.get("replaced_by") != prepared.issued.token_id:
        raise ValueError("Predecessor replacement link is invalid")

    if new.get("replaces") != prepared.plan.current_token_id:
        raise ValueError("Successor replacement link is invalid")

    old["active"] = False
    old["overlap_until"] = None

    save_registry(registry_path, registry)


def abort_rotation(
    *,
    prepared: PreparedRotation,
    registry_path: Path,
) -> None:
    registry = load_registry(registry_path)

    old = next(
        (
            record
            for record in registry["tokens"]
            if record.get("token_id") == prepared.plan.current_token_id
        ),
        None,
    )

    if old is None:
        raise ValueError(
            f"Predecessor token not found: {prepared.plan.current_token_id}"
        )

    registry["tokens"] = [
        record
        for record in registry["tokens"]
        if record.get("token_id") != prepared.issued.token_id
    ]

    old["active"] = True
    old["replaced_by"] = None
    old["overlap_until"] = None

    save_registry(registry_path, registry)


@dataclass(frozen=True)
class RotationResult:
    old_token_id: str
    new_token_id: str


def execute_rotation(
    *,
    plan: RotationPlan,
    registry_path: Path,
    restart_consumer: Callable[[], None],
    verify_consumer: Callable[[], bool],
) -> RotationResult:
    prepared = prepare_rotation(
        plan=plan,
        registry_path=registry_path,
    )

    previous_token: str | None = None

    try:
        previous_token = install_consumer_secret(
            path=plan.consumer_secret_path,
            raw_token=prepared.issued.raw_token,
        )

        restart_consumer()

        if not verify_consumer():
            raise RuntimeError(
                "New token failed consumer verification"
            )

        finalize_rotation(
            prepared=prepared,
            registry_path=registry_path,
        )

        return RotationResult(
            old_token_id=plan.current_token_id,
            new_token_id=prepared.issued.token_id,
        )

    except Exception:
        if previous_token is not None:
            install_consumer_secret(
                path=plan.consumer_secret_path,
                raw_token=previous_token,
            )

        abort_rotation(
            prepared=prepared,
            registry_path=registry_path,
        )

        if previous_token is not None:
            restart_consumer()

        raise