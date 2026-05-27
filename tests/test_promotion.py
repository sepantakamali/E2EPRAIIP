from pathlib import Path

from textclf.config import DEFAULT
from textclf.data import load_split
from textclf.model import build_pipeline, predict, train
from textclf.persistence import load_model, promote_model, save_model
import textclf.persistence as p


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

        promoted_path = promote_model(artifact_path, stable_path=p.STABLE_PATH)
        assert promoted_path.exists()

        saved_model, saved_meta = load_model(artifact_path)
        promoted_model, promoted_meta = load_model(promoted_path)

        assert saved_meta.sha256 == promoted_meta.sha256 # Same artifact
        # Proper functionality
        assert predict(promoted_model, Xte[:5]) == predict(saved_model, Xte[:5])

    finally:
        p.ARTIFACTS_DIR = original_dir
        p.LATEST_PATH = original_latest
        p.STABLE_PATH = original_stable
        p.POINTERS_PATH = original_pointers_path
        p.RUNLOG_PATH = original_runlog_path