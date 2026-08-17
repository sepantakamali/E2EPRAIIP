from __future__ import annotations

import argparse
import os
from pathlib import Path

from textclf.token_store import load_registry, validate_scopes
from admin.token_rotation import (
    build_rotation_plan,
    execute_rotation,
)
from admin.token_consumer import (
    build_restart_callback,
    build_verification_callback,
)

from dataclasses import replace

import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage textclf service-token lifecycle operations."
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "list",
        help="List tokens in the configured token registry.",
    )

    plan_parser = subparsers.add_parser(
        "plan",
        help="Build and display a token rotation plan.",
    )
    plan_parser.add_argument("principal")
    plan_parser.add_argument(
        "--policy",
        default="deploy/token-principals.yml",
    )

    plan_parser.add_argument(
    "--scopes",
    nargs="+",
    )
    plan_parser.add_argument(
        "--ttl-days",
        type=int,
    )
    plan_parser.add_argument(
        "--overlap-minutes",
        type=int,
    )

    rotate_parser = subparsers.add_parser(
        "rotate",
        help="Rotate a managed service token after admin approval.",
    )
    rotate_parser.add_argument("principal")
    rotate_parser.add_argument(
        "--policy",
        default="deploy/token-principals.yml",
    )
    rotate_parser.add_argument(
        "--scopes",
        nargs="+",
    )
    rotate_parser.add_argument(
        "--ttl-days",
        type=int,
    )
    rotate_parser.add_argument(
        "--overlap-minutes",
        type=int,
    )

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify the currently deployed service token.",
    )

    verify_parser.add_argument("principal")
    verify_parser.add_argument(
        "--policy",
        default="deploy/token-principals.yml",
    )

    args = parser.parse_args()

    if args.command == "list":
        token_file = os.getenv("AUTH_TOKENS_FILE")
        if not token_file:
            raise RuntimeError("AUTH_TOKENS_FILE must be set")

        registry = load_registry(Path(token_file))

        for record in registry["tokens"]:
            print(
                f"{record.get('token_id')}  "
                f"client={record.get('client_id')}  "
                f"active={record.get('active')}  "
                f"expires={record.get('expires_at')}"
            )
    
    if args.command == "plan":
        token_file = os.getenv("AUTH_TOKENS_FILE")
        if not token_file:
            raise RuntimeError("AUTH_TOKENS_FILE must be set")

        plan = build_rotation_plan(
            principal=args.principal,
            policy_path=Path(args.policy),
            registry_path=Path(token_file),
        )

        if args.scopes is not None:
            validate_scopes(args.scopes)
            plan = replace(plan, scopes=args.scopes)

        if args.ttl_days is not None:
            if args.ttl_days <= 0:
                raise ValueError("--ttl-days must be positive")
            plan = replace(plan, ttl_days=args.ttl_days)

        if args.overlap_minutes is not None:
            if args.overlap_minutes < 0:
                raise ValueError("--overlap-minutes cannot be negative")
            plan = replace(
                plan,
                overlap_minutes=args.overlap_minutes,
            )

        print(f"Principal: {plan.principal}")
        print(f"Current token: {plan.current_token_id}")
        print(f"Subject: {plan.subject}")
        print(f"Client ID: {plan.client_id}")
        print(f"Rotation group: {plan.rotation_group}")
        print(f"TTL: {plan.ttl_days} days")
        print(f"Overlap: {plan.overlap_minutes} minutes")
        print(f"Compose service: {plan.compose_service}")
        print(f"Consumer secret: {plan.consumer_secret_path}")
        print("Scopes:")
        for scope in plan.scopes:
            print(f"  - {scope}")
    
    if args.command == "rotate":
        token_file = os.getenv("AUTH_TOKENS_FILE")

        if not token_file:
            raise RuntimeError("AUTH_TOKENS_FILE must be set")

        plan = build_rotation_plan(
            principal=args.principal,
            policy_path=Path(args.policy),
            registry_path=Path(token_file),
        )

        if args.scopes is not None:
            validate_scopes(args.scopes)
            plan = replace(plan, scopes=args.scopes)

        if args.ttl_days is not None:
            if args.ttl_days <= 0:
                raise ValueError("--ttl-days must be positive")

            plan = replace(
                plan,
                ttl_days=args.ttl_days,
            )

        if args.overlap_minutes is not None:
            if args.overlap_minutes < 0:
                raise ValueError(
                    "--overlap-minutes cannot be negative"
                )

            plan = replace(
                plan,
                overlap_minutes=args.overlap_minutes,
            )

        print("Rotation proposal")
        print(f"Principal: {plan.principal}")
        print(f"Current token: {plan.current_token_id}")
        print(f"TTL: {plan.ttl_days} days")
        print(f"Overlap: {plan.overlap_minutes} minutes")
        print(f"Consumer: {plan.container_name}")
        print("Scopes:")

        for scope in plan.scopes:
            print(f"  - {scope}")

        answer = input(
            "Proceed with rotation? [y/N]: "
        ).strip().lower()

        if answer not in {"y", "yes"}:
            print("Rotation cancelled.")
            return

        restart_consumer = build_restart_callback(
            consumer_type=plan.consumer_type,
            env_file=plan.env_file,
            compose_file=plan.compose_file,
            compose_service=plan.compose_service,
            container_name=plan.container_name,
            health_timeout_seconds=plan.health_timeout_seconds,
        )

        verify_consumer = build_verification_callback(
            verification_type=plan.verification_type,
            container_name=plan.container_name,
            container_secret_path=str(
                plan.container_secret_path
            ),
            endpoint=plan.verification_endpoint,
            expected_subject=plan.expected_subject,
            expected_client_id=plan.expected_client_id,
        )

        result = execute_rotation(
            plan=plan,
            registry_path=Path(token_file),
            restart_consumer=restart_consumer,
            verify_consumer=verify_consumer,
        )

        print("Rotation completed successfully.")
        print(f"Old token: {result.old_token_id}")
        print(f"New token: {result.new_token_id}")

        backup_script = Path(
            "/home/deploy/textclf/admin/backup_secrets.sh"
        )

        if backup_script.exists():
            subprocess.run(
                [str(backup_script)],
                check=True,
            )
            print("Secrets backup completed.")

    if args.command == "verify":
        token_file = os.getenv("AUTH_TOKENS_FILE")

        if not token_file:
            raise RuntimeError("AUTH_TOKENS_FILE must be set")

        plan = build_rotation_plan(
            principal=args.principal,
            policy_path=Path(args.policy),
            registry_path=Path(token_file),
        )

        verify_consumer = build_verification_callback(
            verification_type=plan.verification_type,
            container_name=plan.container_name,
            container_secret_path=str(
                plan.container_secret_path
            ),
            endpoint=plan.verification_endpoint,
            expected_subject=plan.expected_subject,
            expected_client_id=plan.expected_client_id,
        )

        if not verify_consumer():
            raise RuntimeError(
                f"Consumer verification failed: {plan.principal}"
            )

        print(
            f"Consumer verification passed: {plan.principal}"
        )


if __name__ == "__main__":
    main()