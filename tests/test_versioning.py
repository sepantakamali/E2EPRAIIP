from pathlib import Path
from textclf.config import DEFAULT
from textclf.data import load_split
from textclf.model import build_pipeline, train, predict
from textclf.persistence import save_model, load_model, ARTIFACTS_DIR, LATEST_PATH
import textclf.persistence as p

def test_versioned_save_and_latest(tmp_path: Path):
    # snapshot originals from the module
    orig_dir = ARTIFACTS_DIR
    orig_latest = p.LATEST_PATH
    orig_runlog = getattr(p, "RUNLOG_PATH", None)
    try:
        p.ARTIFACTS_DIR = tmp_path
        p.LATEST_PATH = tmp_path / "model_latest.joblib"
        p.RUNLOG_PATH = tmp_path / "runs.jsonl"

        Xtr, Xte, ytr, yte = load_split(DEFAULT.categories, DEFAULT.test_size, DEFAULT.random_state)
        pipe = train(build_pipeline(500, 100), Xtr, ytr)

        # save twice with tags
        a1 = save_model(pipe, DEFAULT, tag="t1")
        a2 = save_model(pipe, DEFAULT, tag="t2")
        assert a1.exists() and a2.exists()
        assert p.LATEST_PATH.exists()

        # latest should load and predict the same as a2 (same model in this test)
        m_latest, _ = load_model(p.LATEST_PATH)
        preds_latest = predict(m_latest, Xte[:5])
        m2, _ = load_model(a2)
        preds2 = predict(m2, Xte[:5])
        assert preds_latest == preds2
    finally:
        p.ARTIFACTS_DIR = orig_dir