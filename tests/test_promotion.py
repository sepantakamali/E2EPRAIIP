import hashlib
import json
from pathlib import Path

import pytest
import joblib

from textclf.cli import build_parser
from textclf.config import DEFAULT
from textclf.data import load_split
from textclf.model import build_pipeline, predict, train
from textclf.persistence import load_model, promote_model, publish_model, save_model
import textclf.persistence as p


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_promote_sets_stable(tmp_path: Path):
    original_dir = p.ARTIFACTS_DIR
    original_latest = p.LATEST_PATH
    original_stable = p.STABLE_PATH
    original_pointers_path = p.POINTERS_PATH
    original_runlog_path = p.RUNLOG_PATH

    try:
        p.ARTIFACTS_DIR = tmp_path
        p.LATEST_PATH = tmp_path / "model_latest.joblib"
        p.STABLE_PATH = tmp_path / "model_stable.joblib"
        p.POINTERS_PATH = tmp_path / "pointers.json"
        p.RUNLOG_PATH = tmp_path / "runs.jsonl"

        Xtr, Xte, ytr, _ = load_split(
            DEFAULT.categories,
            DEFAULT.test_size,
            DEFAULT.random_state,
            DEFAULT.shuffle,
        )
        pipe = train(build_pipeline(200, 50), Xtr, ytr)
        artifact_path = save_model(pipe, DEFAULT, tag="promotion-test")
        assert artifact_path.exists()

        checksum_before_promotion = _file_sha256(artifact_path)

        promoted_path = promote_model(artifact_path, stable_path=p.STABLE_PATH)
        assert promoted_path.exists()

        # Promotion updates only the stable pointer. The canonical artifact is
        # returned directly and its serialized bytes remain unchanged.
        assert promoted_path == artifact_path
        assert _file_sha256(promoted_path) == checksum_before_promotion

        pointers = json.loads(p.POINTERS_PATH.read_text())
        assert pointers["stable"] == artifact_path.name

        saved_model, saved_meta = load_model(artifact_path)
        promoted_model, promoted_meta = load_model(promoted_path)

        # Identity is embedded in the immutable artifact. Its final-byte digest
        # is external registry state rather than self-referential metadata.
        assert saved_meta.model_id == promoted_meta.model_id
        assert saved_meta.sha256 is None
        assert promoted_meta.sha256 is None

        run_entries = [
            json.loads(line)
            for line in p.RUNLOG_PATH.read_text().splitlines()
            if line.strip()
        ]
        saved_entry = next(
            entry
            for entry in reversed(run_entries)
            if entry["model_id"] == saved_meta.model_id
        )
        assert saved_entry["artifact"] == str(artifact_path)
        assert saved_entry["artifact_sha256"] == checksum_before_promotion

        assert predict(promoted_model, Xte[:5]) == predict(saved_model, Xte[:5])

    finally:
        p.ARTIFACTS_DIR = original_dir
        p.LATEST_PATH = original_latest
        p.STABLE_PATH = original_stable
        p.POINTERS_PATH = original_pointers_path
        p.RUNLOG_PATH = original_runlog_path


def test_publish_uses_registry_without_rewriting_artifact(tmp_path: Path):
    original_dir = p.ARTIFACTS_DIR
    original_latest = p.LATEST_PATH
    original_pointers_path = p.POINTERS_PATH
    original_runlog_path = p.RUNLOG_PATH

    try:
        p.ARTIFACTS_DIR = tmp_path
        p.LATEST_PATH = tmp_path / "model_latest.joblib"
        p.POINTERS_PATH = tmp_path / "pointers.json"
        p.RUNLOG_PATH = tmp_path / "runs.model"

        Xtr, _, ytr, _ = load_split(
            DEFAULT.categories,
            DEFAULT.test_size,
            DEFAULT.random_state,
            DEFAULT.shuffle,
        )
        pipe = train(build_pipeline(200, 50), Xtr, ytr)
        artifact_path = save_model(pipe, DEFAULT, tag="publish-test")
        checksum_before_publish = _file_sha256(artifact_path)

        publish_model(artifact_path, release_tag="v1.0")

        assert _file_sha256(artifact_path) == checksum_before_publish
        _, published_meta = load_model(artifact_path)
        assert published_meta.published is True
        assert published_meta.release_tag == "v1.0"
        assert published_meta.sha256 is None

        publish_model(artifact_path, edit=True, unpublish=True)

        assert _file_sha256(artifact_path) == checksum_before_publish
        _, unpublished_meta = load_model(artifact_path)
        assert unpublished_meta.published is False
        assert unpublished_meta.release_tag == "v1.0"

        run_entries = [
            json.loads(line)
            for line in p.RUNLOG_PATH.read_text().splitlines()
            if line.strip()
        ]
        publication_entries = [
            entry
            for entry in run_entries
            if entry.get("event") == "publication_updated"
        ]
        assert [entry["published"] for entry in publication_entries] == [True, False]
        assert all(
            entry["artifact_sha256"] == checksum_before_publish
            for entry in publication_entries
        )
    finally:
        p.ARTIFACTS_DIR = original_dir
        p.LATEST_PATH = original_latest
        p.POINTERS_PATH = original_pointers_path
        p.RUNLOG_PATH = original_runlog_path


def test_publish_cli_uses_boolean_edit_flags():
    args = build_parser().parse_args(
        [
            "publish",
            "artifacts/model.joblib",
            "--edit",
            "--unpublish",
        ]
    )

    assert args.edit is True
    assert args.unpublish is True
    assert args.release_tag is None


def test_release_rules_use_latest_registry_state(tmp_path: Path):
    original_dir = p.ARTIFACTS_DIR
    original_latest = p.LATEST_PATH
    original_pointers_path = p.POINTERS_PATH
    original_runlog_path = p.RUNLOG_PATH

    try:
        p.ARTIFACTS_DIR = tmp_path
        p.LATEST_PATH = tmp_path / "model_latest.joblib"
        p.POINTERS_PATH = tmp_path / "pointers.json"
        p.RUNLOG_PATH = tmp_path / "runs.model"

        artifact_v1 = save_model({"model": 1}, DEFAULT, tag="release-one")
        artifact_v2 = save_model({"model": 2}, DEFAULT, tag="release-two")
        publish_model(artifact_v1, release_tag="v1.0")

        with pytest.raises(ValueError, match="already exists"):
            publish_model(artifact_v2, release_tag="v1.0")

        with pytest.raises(ValueError, match="Release jump detected"):
            publish_model(artifact_v2, release_tag="v1.2")

        publish_model(
            artifact_v2,
            release_tag="v1.2",
            force=True,
            allow_skip=True,
        )
        _, meta_v2 = load_model(artifact_v2)
        assert meta_v2.published is True
        assert meta_v2.release_tag == "v1.2"
    finally:
        p.ARTIFACTS_DIR = original_dir
        p.LATEST_PATH = original_latest
        p.POINTERS_PATH = original_pointers_path
        p.RUNLOG_PATH = original_runlog_path


def test_registry_reader_ignores_malformed_lines(tmp_path: Path):
    original_dir = p.ARTIFACTS_DIR
    original_latest = p.LATEST_PATH
    original_pointers_path = p.POINTERS_PATH
    original_runlog_path = p.RUNLOG_PATH

    try:
        p.ARTIFACTS_DIR = tmp_path
        p.LATEST_PATH = tmp_path / "model_latest.joblib"
        p.POINTERS_PATH = tmp_path / "pointers.json"
        p.RUNLOG_PATH = tmp_path / "runs.model"

        artifact = save_model({"model": "malformed-log"}, DEFAULT)
        publish_model(artifact, release_tag="v1.0")
        with p.RUNLOG_PATH.open("a") as runlog:
            runlog.write("{this is not valid json}\n")

        _, meta = load_model(artifact)
        assert meta.published is True
        assert meta.release_tag == "v1.0"
    finally:
        p.ARTIFACTS_DIR = original_dir
        p.LATEST_PATH = original_latest
        p.POINTERS_PATH = original_pointers_path
        p.RUNLOG_PATH = original_runlog_path


def test_legacy_log_does_not_override_embedded_publication_state(tmp_path: Path):
    original_runlog_path = p.RUNLOG_PATH

    try:
        p.RUNLOG_PATH = tmp_path / "runs.model"
        artifact = tmp_path / "model_legacy.joblib"
        model_id = "2026-01-01T00:00:00Z_legacy01"
        joblib.dump(
            {
                "pipeline": {"model": "legacy"},
                "metadata": {
                    "version": "0.1.0",
                    "model_id": model_id,
                    "created_at": "2026-01-01T00:00:00Z",
                    "sha256": "legacy-self-referential-checksum",
                    "published": True,
                    "release_tag": "v1.0",
                },
            },
            artifact,
        )
        p.RUNLOG_PATH.write_text(
            json.dumps(
                {
                    "artifact": str(artifact),
                    "model_id": model_id,
                    "sha256": "legacy-self-referential-checksum",
                    "published": False,
                    "release_tag": "unreleased",
                }
            )
            + "\n"
        )

        _, meta = load_model(artifact)

        assert meta.published is True
        assert meta.release_tag == "v1.0"
    finally:
        p.RUNLOG_PATH = original_runlog_path
