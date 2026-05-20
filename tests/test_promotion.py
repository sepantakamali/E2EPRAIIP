from pathlib import Path

from textclf.config import DEFAULT
from textclf.data import load_split
from textclf.model import build_pipeline, predict, train
from textclf.persistence import load_model, promote_model, save_model
import textclf.persistence as p


def test_promote_sets_stable(tmp_path: Path):
    orig_dir = p.ARTIFACTS_DIR
    orig_latest = p.LATEST_PATH
    orig_stable = p.STABLE_PATH

    try:
        p.ARTIFACTS_DIR = tmp_path
        p.LATEST_PATH = tmp_path / "model_latest.joblib"
        p.STABLE_PATH = tmp_path / "model_stable.joblib"

        Xtr, Xte, ytr, _ = load_split(
            DEFAULT.categories,
            DEFAULT.test_size,
            DEFAULT.random_state,
            DEFAULT.shuffle,
        )
        pipe = train(build_pipeline(200, 50), Xtr, ytr)
        artifact_path = save_model(pipe, DEFAULT, tag="t1")

        promoted_path = promote_model(artifact_path, stable_path=p.STABLE_PATH)
        assert promoted_path.exists()

        stable_model, _ = load_model(promoted_path)
        original_model, _ = load_model(artifact_path)

        assert predict(stable_model, Xte[:5]) == predict(original_model, Xte[:5])

    finally:
        p.ARTIFACTS_DIR = orig_dir
        p.LATEST_PATH = orig_latest
        p.STABLE_PATH = orig_stable