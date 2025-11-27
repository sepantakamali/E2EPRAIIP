from pathlib import Path
import textclf.persistence as p
from textclf.config import DEFAULT
from textclf.data import load_split
from textclf.model import build_pipeline, train, predict
from textclf.persistence import save_model, promote_model

def test_promote_sets_stable(tmp_path: Path):
    # redirect all artifact paths to tmp
    orig_dir, orig_latest, orig_stable = p.ARTIFACTS_DIR, p.LATEST_PATH, p.STABLE_PATH
    try:
        p.ARTIFACTS_DIR = tmp_path
        p.LATEST_PATH = tmp_path / "model_latest.joblib"
        p.STABLE_PATH = tmp_path / "model_stable.joblib"

        Xtr, Xte, ytr, yte = load_split(DEFAULT.categories, DEFAULT.test_size, DEFAULT.random_state)
        pipe = train(build_pipeline(200, 50), Xtr, ytr)
        a1 = save_model(pipe, DEFAULT, tag="t1")
        # promote a1
        promote_model(a1, stable_path=p.STABLE_PATH)
        assert p.STABLE_PATH.exists()
    finally:
        p.ARTIFACTS_DIR, p.LATEST_PATH, p.STABLE_PATH = orig_dir, orig_latest, orig_stable