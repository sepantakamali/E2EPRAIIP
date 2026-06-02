#!/usr/bin/env python3
"""Provision monitoring authentication secrets.

This script generates:
- A Prometheus scrape password
- An nginx htpasswd entry for /metrics Basic Auth
- Optional Grafana admin password

Generated files are written into the configured secrets directory.

This script is intentionally separate from API bearer-token issuance because
monitoring/reverse-proxy credentials are infrastructure secrets, not API
authorization tokens.
"""

from __future__ import annotations

import argparse
import bcrypt
import secrets
from pathlib import Path


DEFAULT_SECRETS_DIR = Path("../practice_sprint_secrets")
PROM_USERNAME = "prometheus"


def _write_secret(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.strip() + "\n", encoding="utf-8")


def _generate_password(length_bytes: int = 32) -> str:
    return secrets.token_urlsafe(length_bytes)


def _generate_htpasswd(username: str, password: str) -> str:
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return f"{username}:{password_hash.decode('utf-8')}"


def provision_monitoring_auth(args: argparse.Namespace) -> None:
    secrets_dir = args.secrets_dir.resolve()
    secrets_dir.mkdir(parents=True, exist_ok=True)

    prometheus_password = _generate_password()
    grafana_password = _generate_password()

    prometheus_password_path = secrets_dir / "prometheus_metrics_password.txt"
    metrics_htpasswd_path = secrets_dir / "metrics.htpasswd"
    grafana_password_path = secrets_dir / "grafana_admin_password.txt"

    _write_secret(prometheus_password_path, prometheus_password)

    htpasswd_entry = _generate_htpasswd(PROM_USERNAME, prometheus_password)
    _write_secret(metrics_htpasswd_path, htpasswd_entry)

    if args.generate_grafana_password:
        _write_secret(grafana_password_path, grafana_password)

    print("Monitoring authentication secrets provisioned successfully:\n")
    print(f"\tPrometheus password:\t {prometheus_password_path}\n")
    print(f"\tnginx htpasswd:\t {metrics_htpasswd_path}")

    if args.generate_grafana_password:
        print(f"\n\tGrafana password:\t {grafana_password_path}")

    print("\nGenerated credentials:")
    print(f"\tPrometheus username:\t {PROM_USERNAME}")

    if args.generate_grafana_password:
        print("\tGrafana username: admin")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision monitoring authentication secrets"
    )

    parser.add_argument(
        "--secrets-dir",
        type=Path,
        default=DEFAULT_SECRETS_DIR,
        help="Directory for generated monitoring secret files",
    )

    parser.add_argument(
        "--generate-grafana-password",
        action="store_true",
        help="Generate a Grafana admin password secret file",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    provision_monitoring_auth(args)


if __name__ == "__main__":
    main()
