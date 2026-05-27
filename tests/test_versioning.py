from pathlib import Path

from textclf.config import DEFAULT
from textclf.data import load_split
from textclf.model import build_pipeline, predict, train
from textclf.persistence import load_model, save_model
import textclf.persistence as p


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

        artifact_v1_model, _ = load_model(artifact_v1)
        artifact_v2_model, _ = load_model(artifact_v2)

        assert predict(artifact_v1_model, Xte[:5]) == predict(artifact_v2_model, Xte[:5])

    finally:
        p.ARTIFACTS_DIR = original_dir
        p.LATEST_PATH = original_latest
        p.POINTERS_PATH = original_pointers_path
        p.RUNLOG_PATH = original_runlog
        