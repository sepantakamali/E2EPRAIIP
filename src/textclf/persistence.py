# textclf.persistence — model persistence, pointers, and run logging
from __future__ import annotations

import os
import dataclasses as _dc
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Tuple

import joblib

# ----- Artifact locations -----
ARTIFACTS_DIR: Path = Path(os.getenv("ARTIFACTS_DIR", "artifacts"))

LATEST_PATH: Path = ARTIFACTS_DIR / "model_latest.joblib"  # legacy alias only
STABLE_PATH: Path = ARTIFACTS_DIR / "model_stable.joblib"  # legacy alias only
POINTERS_PATH: Path = ARTIFACTS_DIR / "pointers.json"
RUNLOG_PATH: Path = ARTIFACTS_DIR / "runs.model"  # JSON Lines file

# Backwards-compat alias used in some older scripts/tests
DEFAULT_MODEL_PATH: Path = LATEST_PATH


# ----- Helpers -----

def _pkg_version() -> str:
    try:
        return metadata.version("textclf")
    except Exception:
        # fallback for local dev before package is installed
        return "0.1.0"


def _utc_time() -> str:
    # RFC3339 / ISO8601 with Z suffix
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _time_stamp() -> str:
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


def _read_pointers() -> dict[str, str]:
    if not POINTERS_PATH.exists():
        return {}
    try:
        data = json.loads(POINTERS_PATH.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_pointers(pointers: dict[str, str]) -> None:
    POINTERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = POINTERS_PATH.with_suffix(POINTERS_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(pointers, indent=2, sort_keys=True))
    tmp.replace(POINTERS_PATH)


def _set_pointer(name: str, target: Path) -> None:
    pointers = _read_pointers()
    # store canonical relative artifact path
    try:
        artifact = str(target.relative_to(ARTIFACTS_DIR))
    except Exception:
        # Fall-back in case of error
        artifact = str(target)
    pointers[name] = artifact
    _write_pointers(pointers)


def _resolve_pointer_path(name: str) -> Path:
    pointers = _read_pointers()
    artifact = pointers.get(name)
    if not artifact:
        raise FileNotFoundError(f"Pointer '{name}' is not set in {POINTERS_PATH}")
    __path = Path(artifact)
    return __path if __path.is_absolute() else (ARTIFACTS_DIR / __path)


# ----- Metadata Format -----

@dataclass
class ModelMetadata:
    # Software/package version (SemVer) of the code that produced this artifact
    software_version: str
    # Immutable identifier for this model build (created_at + short content hash)
    model_id: str
    created_at: str
    config: Any | None = None
    # Full content hash of the saved artifact (hex)
    sha256: str | None = None
    # Release metadata
    published: bool = False
    release_tag: str = "unreleased"


# ----- Public API -----

def save_model(
    pipeline: Any,
    cfg: Any,
    tag: str | None = None,
    make_latest: bool = True,
) -> Path:
    """Persist a trained pipeline and update the *latest* pointer.

    The saved artifact is the canonical model file under `artifacts/model_<...>.joblib`.
    Pointer state is maintained in `artifacts/pointers.json`, where `latest`
    automatically resolves to the newest saved artifact.

    Returns the path to the canonical versioned artifact.
    """
    log = logging.getLogger("textclf")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # Build a JSON-serializable config snapshot
    config_dict = None
    # Guard: is_dataclass() returns True for both classes and instances, but asdict() only works on instances
    if _dc.is_dataclass(cfg) and not isinstance(cfg, type): # Instance, not the class
        config_dict = asdict(cfg)
    elif hasattr(cfg, "__dict__"):
        try:
            config_dict = vars(cfg)
        except TypeError:
            config_dict = None

    created_at = _utc_time()
    meta = ModelMetadata(
        software_version=_pkg_version(),
        model_id="",  # filled after artifact is written and hashed
        created_at=created_at,
        config=config_dict,
    )

    fname = f"model_{_time_stamp()}" + (f"-{tag}" if tag else "") + ".joblib"
    target = ARTIFACTS_DIR / fname

    md_dict = asdict(meta)
    # Backwards-compat for older readers/tests expecting metadata['version']
    md_dict["version"] = meta.software_version

    payload = {"pipeline": pipeline, "metadata": md_dict}
    joblib.dump(payload, target)

    # compute checksum AFTER final write
    checksum = _sha256(target)
    meta.sha256 = checksum
    content_hash = checksum[:8]
    meta.model_id = f"{meta.created_at}_{content_hash}"

    run_entry = {
        "artifact": str(target),
        "created_at": meta.created_at,
        "version": meta.software_version,  # legacy
        "software_version": meta.software_version,
        "model_id": meta.model_id,
        "published": meta.published,
        "release_tag": meta.release_tag,
        "tag": tag,
        "sha256": checksum,
        "config": meta.config,
    }
    _append_runlog(run_entry)

    # Persist updated metadata (model_id + sha256) into the artifact itself
    md_dict = asdict(meta)
    md_dict["version"] = meta.software_version  # legacy
    payload = {"pipeline": pipeline, "metadata": md_dict}
    joblib.dump(payload, target)

    # Maintain latest pointer in the manifest.
    if make_latest:
        _set_pointer("latest", target)
        log.info(f"Updated latest pointer -> {target}")

    log.info(f"Saved model to: {target}")
    return target


def load_model(path: Path | str) -> Tuple[Any, ModelMetadata]:
    """Load a persisted pipeline + metadata from a joblib artifact."""

    p = Path(path)

    # Common user mistake: passing a directory instead of artifact address.
    # Resolve to the canonical artifact referenced by the latest pointer.
    if p.is_dir():
        p = _resolve_pointer_path("latest")

    # Support legacy callers that still pass LATEST_PATH / STABLE_PATH.
    if p == LATEST_PATH:
        p = _resolve_pointer_path("latest")
    elif p == STABLE_PATH:
        p = _resolve_pointer_path("stable")

    if not p.exists():
        raise FileNotFoundError(f"Model file not found: {p}")

    payload = joblib.load(p)
    pipe = payload["pipeline"]
    md = payload.get("metadata")

    if isinstance(md, ModelMetadata):
        meta = md

        # Backfill missing fields for older pickled dataclass instances
        if not getattr(meta, "software_version", None):
            meta.software_version = _pkg_version()

        if not getattr(meta, "created_at", None):
            meta.created_at = _utc_time()

        if not hasattr(meta, "published"):
            meta.published = False

        if not getattr(meta, "release_tag", None):
            meta.release_tag = "unreleased"

        if not hasattr(meta, "sha256"):
            meta.sha256 = None

        if not getattr(meta, "model_id", ""):
            sha = getattr(meta, "sha256", None)
            if not sha:
                try:
                    sha = _sha256(p)
                    meta.sha256 = sha
                except Exception:
                    sha = None
            if sha:
                meta.model_id = f"{meta.created_at}_{str(sha)[:8]}"
            else:
                meta.model_id = ""

    elif isinstance(md, dict):
        created_at = md.get("created_at", _utc_time())
        software_version = md.get("software_version") or md.get("version") or _pkg_version()
        sha = md.get("sha256")
        model_id = md.get("model_id")

        # Best-effort backfill for older artifacts
        if not sha:
            try:
                sha = _sha256(p)
            except Exception:
                sha = None
        if not model_id and sha:
            model_id = f"{created_at}_{sha[:8]}"

        meta = ModelMetadata(
            software_version=str(software_version),
            model_id=str(model_id) if model_id else "",
            created_at=str(created_at),
            config=md.get("config"),
            sha256=str(sha) if sha else None,
            published=bool(md.get("published", False)),
            release_tag=str(md.get("release_tag", "unreleased")),
        )
    else:
        created_at = _utc_time()
        meta = ModelMetadata(software_version=_pkg_version(), model_id="", created_at=created_at)

    return pipe, meta


def promote_model(artifact: Path | str, stable_path: Path | str = STABLE_PATH) -> Path:
    """Promote a specific canonical artifact to the *stable* pointer.

    Pointer's artifact's name is stored in `artifacts/pointers.json`.
    This does not touch *latest*.
    """
    _path = Path(artifact)
    if not _path.exists():
        raise FileNotFoundError(f"Artifact not found: {_path}")

    _set_pointer("stable", _path)

    logging.getLogger("textclf").info(f"Promoted {_path} -> stable")
    return _path


# ----- Controlled Release Tagging -----

import re

_RELEASE_RE = re.compile(r"^v(\d+)\.(\d+)$") # e.g. v1.0


def _parse_release(tag: str) -> tuple[int, int]:
    m = _RELEASE_RE.match(tag)
    if not m:
        raise ValueError(f"Invalid release_tag '{tag}'. Expected format vMAJOR.MINOR (e.g., v1.2)")
    return int(m.group(1)), int(m.group(2))


def _list_published_releases() -> list[tuple[str, tuple[int, int]]]:
    """Return list of (release_tag, parsed_version) for all published artifacts."""
    releases: list[tuple[str, tuple[int, int]]] = []

    if not ARTIFACTS_DIR.exists():
        return releases

    for p in ARTIFACTS_DIR.glob("model_*.joblib"):
        try:
            _, meta = load_model(p)
            if meta.published and meta.release_tag and meta.release_tag != "unreleased":
                releases.append((meta.release_tag, _parse_release(meta.release_tag)))
        except Exception:
            continue

    return releases


def publish_model(
    artifact: Path | str,
    *,
    force: bool = False,
    allow_skip: bool = False,
    edit: bool = False,
    unpublish: bool = False,
    release_tag: str | None = None,
) -> None:
    """Mark a model artifact as published and optionally assign a formal release tag.

    Modes:
    - publish only: `published=True`, keep `release_tag="unreleased"`
    - publish + release: assign `release_tag` in vMAJOR.MINOR format with checks

    Rules for formal releases:
    - release_tag must follow vMAJOR.MINOR
    - release_tag must be unique
    - version jumps are blocked unless force=True and allow_skip=True
    """

    log = logging.getLogger("textclf")

    _path = Path(artifact)
    if not _path.exists():
        raise FileNotFoundError(f"Artifact not found: {_path}")

    pipe, meta = load_model(_path)

    if meta.published and not edit:
        raise ValueError(f"Artifact {_path} is already published as {meta.release_tag}")
    elif meta.published and edit:
        if unpublish and (release_tag is None or str(release_tag).strip() == ""):
            meta.published = False
            log.info(f"Unpublished {meta.model_id} | release_tag={meta.release_tag}")
        elif unpublish and (release_tag != None or str(release_tag).strip() != ""):
            raise ValueError("Can't pass a release tag for unpublishing")

    # If no formal release tag is provided, simply mark as published and keep
    # the default/unreleased tag. This is useful for experimental builds that
    # should appear in the UI without being treated as official releases.
    if (release_tag is None or str(release_tag).strip() == "") and not edit:
        meta.published = True
        meta.release_tag = meta.release_tag or "unreleased"
    elif release_tag != None:
        release_tag = str(release_tag).strip()
        major, minor = _parse_release(release_tag)

        # check uniqueness
        releases = _list_published_releases()
        for tag, _ in releases:
            if tag == release_tag:
                raise ValueError(f"release_tag '{release_tag}' already exists")

        # determine latest release
        if releases:
            latest_tag, (latest_major, latest_minor) = max(releases, key=lambda x: x[1])

            jump = False

            if major == latest_major:
                if minor != latest_minor + 1:
                    jump = True
            elif major == latest_major + 1:
                if minor != 0:
                    jump = True
            else:
                jump = True

            if jump and not (force and allow_skip):
                raise ValueError(
                    f"Release jump detected: latest={latest_tag}, attempted={release_tag}. "
                    "Use force=True and allow_skip=True to override."
                )

        meta.published = True if not edit else meta.published
        meta.release_tag = release_tag

    # rewrite artifact with updated metadata
    md_dict = asdict(meta)
    md_dict["version"] = meta.software_version  # legacy

    payload = {"pipeline": pipe, "metadata": md_dict}

    tmp = _path.with_suffix(_path.suffix + ".tmp")
    joblib.dump(payload, tmp)
    tmp.replace(_path)

    log.info(f"\nModel_id={meta.model_id} | published={meta.published} | release_tag={meta.release_tag}")
