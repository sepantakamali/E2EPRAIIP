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

import uuid

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


def _latest_registry_entry(model_id: str) -> dict[str, Any] | None:
    """Return the newest registry entry for a model, ignoring bad lines."""
    if not model_id or not RUNLOG_PATH.exists():
        return None

    latest: dict[str, Any] | None = None
    for line in RUNLOG_PATH.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except (TypeError, ValueError):
            continue
        # Only records created under the immutable-artifact design are
        # authoritative mutable state. Older rows used ``sha256`` and may
        # contain publication fields that became stale when artifacts were
        # rewritten later.
        if (
            isinstance(entry, dict)
            and entry.get("model_id") == model_id
            and entry.get("artifact_sha256")
        ):
            latest = entry
    return latest


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
    # Immutable identifier for this model build
    model_id: str
    created_at: str
    config: Any | None = None

    # Legacy field retained for compatibility with existing artifacts.
    # New artifacts do not use this as their integrity checksum.
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

    # Model identity is independent of the serialized artifact bytes.
    model_id = f"{created_at}_{uuid.uuid4().hex}"

    meta = ModelMetadata(
        software_version=_pkg_version(),
        model_id=model_id,
        created_at=created_at,
        config=config_dict,
    )

    fname = f"model_{_time_stamp()}" + (f"-{tag}" if tag else "") + ".joblib"
    target = ARTIFACTS_DIR / fname

    md_dict = asdict(meta)

    # Backwards compatibility for older readers expecting metadata["version"].
    md_dict["version"] = meta.software_version

    payload = {
        "pipeline": pipeline,
        "metadata": md_dict,
    }

    # Write the canonical artifact exactly once.
    joblib.dump(payload, target)

    # Hash the FINAL serialized artifact.
    artifact_sha256 = _sha256(target)

    # The artifact cannot contain its own artifact hash. Store that digest
    # externally in the registry/run log instead.
    run_entry = {
        "artifact": str(target),
        "created_at": meta.created_at,
        "version": meta.software_version,  # legacy
        "software_version": meta.software_version,
        "model_id": meta.model_id,
        "published": meta.published,
        "release_tag": meta.release_tag,
        "tag": tag,
        "artifact_sha256": artifact_sha256,
        "config": meta.config,
    }
    _append_runlog(run_entry)

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
            meta.software_version = str(
                getattr(meta, "version", None) or _pkg_version()
            )

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
        legacy_sha = md.get("sha256")
        model_id = md.get("model_id")

        # Preserve historical identity for older artifacts that embedded a checksum,
        # but do not synthesize an embedded checksum for new artifacts.
        if not model_id and legacy_sha:
            model_id = f"{created_at}_{str(legacy_sha)[:8]}"

        meta = ModelMetadata(
            software_version=str(software_version),
            model_id=str(model_id) if model_id else "",
            created_at=str(created_at),
            config=md.get("config"),
            sha256=str(legacy_sha) if legacy_sha else None,
            published=bool(md.get("published", False)),
            release_tag=str(md.get("release_tag", "unreleased")),
        )
    else:
        created_at = _utc_time()
        meta = ModelMetadata(software_version=_pkg_version(), model_id="", created_at=created_at)

    # Publication is mutable registry state. Overlay the newest values without
    # changing the immutable metadata stored in the artifact itself.
    registry_entry = _latest_registry_entry(meta.model_id)
    if registry_entry is not None:
        if "published" in registry_entry:
            meta.published = bool(registry_entry["published"])
        if "release_tag" in registry_entry:
            meta.release_tag = str(registry_entry["release_tag"] or "unreleased")

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

    legacy_aliases = {LATEST_PATH.name, STABLE_PATH.name}
    for p in ARTIFACTS_DIR.glob("model_*.joblib"):
        if p.name in legacy_aliases:
            continue
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

    _, meta = load_model(_path)

    normalized_tag = str(release_tag).strip() if release_tag is not None else ""

    if unpublish and normalized_tag:
        raise ValueError("Can't pass a release tag while unpublishing.")

    if meta.published and not edit:
        raise ValueError(f"Artifact {_path} is already published as {meta.release_tag}")

    if unpublish:
        meta.published = False
        log.info(f"Unpublished {meta.model_id} | release_tag={meta.release_tag}")

    # If no formal release tag is provided, simply mark as published and keep
    # the default/unreleased tag. This is useful for experimental builds that
    # should appear in the UI without being treated as official releases.
    elif not normalized_tag and not edit:
        meta.published = True
        meta.release_tag = meta.release_tag or "unreleased"
    elif normalized_tag:
        major, minor = _parse_release(normalized_tag)

        # check uniqueness
        releases = _list_published_releases()
        for tag, _ in releases:
            if tag == normalized_tag:
                raise ValueError(f"release_tag '{normalized_tag}' already exists")

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
                    f"Release jump detected: latest={latest_tag}, attempted={normalized_tag}. "
                    "Use force=True and allow_skip=True to override."
                )

        meta.published = True if not edit else meta.published
        meta.release_tag = normalized_tag

    # Append mutable publication state to the external registry. The model
    # artifact is never rewritten, so its original digest remains valid.
    _append_runlog(
        {
            "event": "publication_updated",
            "artifact": str(_path),
            "artifact_sha256": _sha256(_path),
            "updated_at": _utc_time(),
            "model_id": meta.model_id,
            "published": meta.published,
            "release_tag": meta.release_tag,
        }
    )

    log.info(f"\nModel_id={meta.model_id} | published={meta.published} | release_tag={meta.release_tag}")
