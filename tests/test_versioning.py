import hashlib
import json
from pathlib import Path

from textclf.config import DEFAULT
from textclf.data import load_split
from textclf.model import build_pipeline, predict, train
from textclf.persistence import load_model, save_model
import textclf.persistence as p

def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def test_versioned_save_and_latest(tmp_path: Path):
    original_dir = p.ARTIFACTS_DIR
    original_latest = p.LATEST_PATH
    original_pointers_path = p.POINTERS_PATH
    original_runlog = p.RUNLOG_PATH

    try:
        p.ARTIFACTS_DIR = tmp_path
        p.LATEST_PATH = tmp_path / "model_latest.joblib"
        p.POINTERS_PATH = tmp_path / "pointers.json"
        p.RUNLOG_PATH = tmp_path / "runs.jsonl"

        Xtr, Xte, ytr, _ = load_split(
            DEFAULT.categories,
            DEFAULT.test_size,
            DEFAULT.random_state,
            DEFAULT.shuffle,
        )
        pipe = train(build_pipeline(500, 100), Xtr, ytr)

        artifact_v1 = save_model(pipe, DEFAULT, tag="versioning-test-1")
        artifact_v2 = save_model(pipe, DEFAULT, tag="versioning-test-2")
        assert artifact_v1.exists() and artifact_v2.exists()
        assert artifact_v1 != artifact_v2

        artifact_v1_model, meta_v1 = load_model(artifact_v1)
        artifact_v2_model, meta_v2 = load_model(artifact_v2)

        assert predict(artifact_v1_model, Xte[:5]) == predict(artifact_v2_model, Xte[:5])

        # Each saved model has an independent immutable identity.
        assert meta_v1.model_id
        assert meta_v2.model_id
        assert meta_v1.model_id != meta_v2.model_id

        # New artifacts do not embed the checksum of their final serialized bytes.
        assert meta_v1.sha256 is None
        assert meta_v2.sha256 is None

        # The run log records the checksum of the final artifact bytes on disk.
        entries = [
            json.loads(line)
            for line in p.RUNLOG_PATH.read_text().splitlines()
            if line.strip()
        ]

        entry_v1 = next(
            entry
            for entry in reversed(entries)
            if entry["model_id"] == meta_v1.model_id
        )

        entry_v2 = next(
            entry
            for entry in reversed(entries)
            if entry["model_id"] == meta_v2.model_id
        )

        assert entry_v1["artifact"] == str(artifact_v1)
        assert entry_v2["artifact"] == str(artifact_v2)

        assert entry_v1["artifact_sha256"] == _file_sha256(artifact_v1)
        assert entry_v2["artifact_sha256"] == _file_sha256(artifact_v2)

    finally:
        p.ARTIFACTS_DIR = original_dir
        p.LATEST_PATH = original_latest
        p.POINTERS_PATH = original_pointers_path
        p.RUNLOG_PATH = original_runlog
