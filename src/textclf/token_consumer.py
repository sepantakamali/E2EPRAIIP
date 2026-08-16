from __future__ import annotations

import json
import subprocess
import time

from collections.abc import Callable
from typing import Any


def build_restart_callback(
    *,
    consumer_type: str,
    compose_file: str,
    compose_service: str,
    container_name: str,
    health_timeout_seconds: int,
) -> Callable[[], None]:
    if consumer_type != "docker-compose":
        raise ValueError(
            f"Unsupported consumer type: {consumer_type}"
        )

    def restart_consumer() -> None:
        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                compose_file,
                "up",
                "-d",
                "--force-recreate",
                compose_service,
            ],
            check=True,
        )

        deadline = time.monotonic() + health_timeout_seconds

        while time.monotonic() < deadline:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format={{.State.Health.Status}}",
                    container_name,
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                status = result.stdout.strip()

                if status == "healthy":
                    return

                if status == "unhealthy":
                    raise RuntimeError(
                        "Consumer container became unhealthy: "
                        f"{container_name}"
                    )

            time.sleep(1)

        raise TimeoutError(
            "Timed out waiting for healthy consumer: "
            f"{container_name}"
        )

    return restart_consumer


def build_verification_callback(
    *,
    container_secret_path: str,
    verification_type: str,
    container_name: str,
    endpoint: str,
    expected_subject: str,
    expected_client_id: str,
) -> Callable[[], bool]:
    if verification_type != "api-whoami":
        raise ValueError(
            f"Unsupported verification type: {verification_type}"
        )

    def verify_consumer() -> bool:
        code = (
            "import json, pathlib, urllib.request; "
            f"token=pathlib.Path({container_secret_path!r}).read_text("
            "encoding='utf-8').strip(); "
            f"req=urllib.request.Request("
            f"'http://textclf-api:8000{endpoint}', "
            "headers={'Authorization': 'Bearer ' + token}); "
            "resp=urllib.request.urlopen(req, timeout=10); "
            "print(json.dumps(json.load(resp)))"
        )

        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "python",
                "-c",
                code,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return False

        try:
            payload: dict[str, Any] = json.loads(
                result.stdout
            )
        except json.JSONDecodeError:
            return False

        return (
            payload.get("subject") == expected_subject
            and payload.get("client_id") == expected_client_id
        )

    return verify_consumer