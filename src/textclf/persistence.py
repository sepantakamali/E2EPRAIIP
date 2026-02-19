# textclf.persistence — model persistence, pointers, and run logging
from __future__ import annotations

import os
import dataclasses as _dc
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib import metadata as _im
from pathlib import Path
from typing import Any, Tuple

import joblib

# ---- Artifact locations -----------------------------------------------------
ARTIFACTS_DIR: Path = Path(os.getenv("ARTIFACTS_DIR", "artifacts"))

LATEST_PATH: Path = ARTIFACTS_DIR / "model_latest.joblib"
STABLE_PATH: Path = ARTIFACTS_DIR / "model_stable.joblib"
RUNLOG_PATH: Path = ARTIFACTS_DIR / "runs.model"  # JSON Lines file

# Backwards-compat alias used in some older scripts/tests
DEFAULT_MODEL_PATH: Path = LATEST_PATH


# ---- Helpers ----------------------------------------------------------------

def _pkg_version() -> str:
    try:
        return _im.version("textclf")
    except Exception:
        # fallback for local dev before package is installed
        return "0.1.0"


def _now_utc() -> str:
    # RFC3339 / ISO8601 with Z suffix
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _append_runlog(entry: dict[str, Any]) -> None:
    RUNLOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNLOG_PATH.open("a").write(json.dumps(entry) + "\n")


# ---- Metadata container -----------------------------------------------------

@dataclass
class ModelMetadata:
    version: str
    created_at: str
    config: Any | None = None
    sha256: str | None = None


# ---- Public API -------------------------------------------------------------

def save_model(
    pipeline: Any,
    cfg: Any,
    tag: str | None = None,
    make_latest: bool = True,
    keep_copy_for_latest: bool = True,
) -> Path:
    """Persist a trained pipeline and update the *latest* pointer.

    Returns the path to the versioned artifact: artifacts/model_<ts>-<tag>.joblib
    """
    log = logging.getLogger("textclf")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # Build a JSON-serializable config snapshot
    config_dict = None
    # Guard: is_dataclass() returns True for both classes and instances, but asdict() only works on instances
    if _dc.is_dataclass(cfg) and not isinstance(cfg, type):
        config_dict = asdict(cfg)
    elif hasattr(cfg, "__dict__"):
        try:
            config_dict = vars(cfg)
        except TypeError:
            config_dict = None

    meta = ModelMetadata(
        version=_pkg_version(),
        created_at=_now_utc(),
        config=config_dict,
    )

    fname = f"model_{_ts()}" + (f"-{tag}" if tag else "") + ".joblib"
    target = ARTIFACTS_DIR / fname

    payload = {"pipeline": pipeline, "metadata": asdict(meta)}
    joblib.dump(payload, target)

    # compute checksum AFTER final write and log it
    checksum = _sha256(target)
    run_entry = {
        "artifact": str(target),
        "created_at": meta.created_at,
        "version": meta.version,
        "tag": tag,
        "sha256": checksum,
        "config": meta.config,
    }
    _append_runlog(run_entry)

    # Maintain latest pointer atomically (copy/symlink via temp + replace)
    if make_latest:
        tmp_latest = LATEST_PATH.with_suffix(LATEST_PATH.suffix + ".tmp")
        if keep_copy_for_latest:
            joblib.dump(payload, tmp_latest)  # keep an independent copy for latest
        else:
            try:
                if tmp_latest.exists():
                    tmp_latest.unlink()
                tmp_latest.symlink_to(target.resolve())
            except Exception:
                # fall back to copy if symlink unsupported
                joblib.dump(payload, tmp_latest)
        tmp_latest.replace(LATEST_PATH)
        log.info(f"Updated latest pointer -> {LATEST_PATH}")

    log.info(f"Saved model to: {target}")
    return target


def load_model(path: Path | str) -> Tuple[Any, ModelMetadata]:
    """Load a persisted pipeline + metadata from a joblib artifact."""

    p = Path(path)
    # Common user mistake: passing a directory instead of artifact address
    # Solution: set pointer to the 'latest's' path
    if p.is_dir():
        p = LATEST_PATH
    if not p.exists():
        raise FileNotFoundError(f"Model file not found: {p}")

    payload = joblib.load(p)
    pipe = payload["pipeline"]
    md = payload.get("metadata")

    if isinstance(md, ModelMetadata):
        meta = md
    elif isinstance(md, dict):
        meta = ModelMetadata(
            version=md.get("version", _pkg_version()),
            created_at=md.get("created_at", _now_utc()),
            config=md.get("config"),
            sha256=md.get("sha256"),
        )
    else:
        meta = ModelMetadata(version=_pkg_version(), created_at=_now_utc())

    return pipe, meta


def promote_model(artifact: Path | str, stable_path: Path | str = STABLE_PATH) -> Path:
    """Promote a specific versioned artifact to the *stable* pointer.

    This does not touch *latest*.
    """
    src = Path(artifact)
    if not src.exists():
        raise FileNotFoundError(f"Artifact not found: {src}")

    dst = Path(stable_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    tmp_dst = dst.with_suffix(dst.suffix + ".tmp")
    # copy bytes (not link) so stable is independent, then atomic replace
    joblib.dump(joblib.load(src), tmp_dst)
    tmp_dst.replace(dst)

    logging.getLogger("textclf").info(f"Promoted {src} -> {dst}")
    return dst