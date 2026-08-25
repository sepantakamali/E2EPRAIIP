"""Audit legacy model artifacts and optionally append reconciliation records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from textclf import persistence as p


def _registry_entries() -> list[dict[str, Any]]:
    if not p.RUNLOG_PATH.exists():
        return []

    entries: list[dict[str, Any]] = []
    for line in p.RUNLOG_PATH.read_text().splitlines():
        try:
            entry = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def audit_registry(*, reconcile: bool = False) -> int:
    entries = _registry_entries()
    aliases = {p.LATEST_PATH.name, p.STABLE_PATH.name}
    reconciled = 0

    for artifact in sorted(p.ARTIFACTS_DIR.glob("model_*.joblib")):
        if artifact.name in aliases:
            continue

        _, meta = p.load_model(artifact)
        actual_sha256 = p._sha256(artifact)
        authoritative = any(
            entry.get("model_id") == meta.model_id
            and entry.get("artifact_sha256")
            for entry in entries
        )
        status = "current" if authoritative else "legacy"
        print(
            f"{status:<7} {artifact.name} "
            f"model_id={meta.model_id} sha256={actual_sha256}"
        )

        if reconcile and not authoritative:
            entry = {
                "event": "legacy_reconciled",
                "artifact": str(artifact),
                "artifact_sha256": actual_sha256,
                "updated_at": p._utc_time(),
                "model_id": meta.model_id,
                "published": meta.published,
                "release_tag": meta.release_tag,
            }
            p._append_runlog(entry)
            entries.append(entry)
            reconciled += 1

    if reconcile:
        print(f"Appended {reconciled} reconciliation record(s).")
    return reconciled


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="Append authoritative checksums and current lifecycle state.",
    )
    args = parser.parse_args()
    audit_registry(reconcile=args.reconcile)


if __name__ == "__main__":
    main()
