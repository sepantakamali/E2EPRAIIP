import argparse
from typing import Any

from textclf.persistence import RUNLOG_PATH, publish_model, load_model, ARTIFACTS_DIR


def _format_bool(v: bool) -> str:
    return "yes" if v else "no"


def load_model_registry() -> list[dict[str, Any]]:
    """Load model registry records from the artifact directory.

    The artifact metadata is the source of truth because publish/promote
    operations modify the joblib metadata directly. The run log is only
    historical bookkeeping and may contain stale fields.
    """

    if not ARTIFACTS_DIR.exists():
        return []

    records: list[dict[str, Any]] = []

    for artifact in sorted(ARTIFACTS_DIR.glob("model_*.joblib")):
        try:
            _, meta = load_model(artifact)

            records.append(
                {
                    "model_id": getattr(meta, "model_id", "-") or "-",
                    "release_tag": getattr(meta, "release_tag", "unreleased") or "unreleased",
                    "published": bool(getattr(meta, "published", False)),
                    "software_version": getattr(meta, "software_version", "-") or "-",
                    "created_at": getattr(meta, "created_at", "-") or "-",
                    "artifact": str(artifact),
                }
            )
        except Exception:
            # Ignore corrupted or partially written artifacts
            continue

    return records


def print_model_registry(records: list[dict[str, Any]]) -> None:
    if not records:
        print("No runs yet.")
        return

    header = (
        f"{'MODEL_ID':<32} | {'RELEASE':<10} | {'PUBLISHED':<9} | "
        f"{'SOFTWARE':<10} | {'CREATED_AT':<20} | ARTIFACT"
    )

    print(header)
    print("-" * len(header))

    for rec in records:
        print(
            f"{rec['model_id']:<32} | {rec['release_tag']:<10} | {_format_bool(bool(rec['published'])):<9} | "
            f"{rec['software_version']:<10} | {rec['created_at']:<20} | {rec['artifact']}"
        )


def _cmd_list(_: argparse.Namespace) -> None:
    print_model_registry(load_model_registry())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Model registry CLI")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="List saved model artifacts")
    p_list.set_defaults(func=_cmd_list)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Backwards-compatible default: no subcommand means list
    if not getattr(args, "command", None):
        _cmd_list(args)
        return

    args.func(args)


if __name__ == "__main__":
    main()