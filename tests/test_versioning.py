from pathlib import Path

from textclf.config import DEFAULT
from textclf.data import load_split
from textclf.model import build_pipeline, predict, train
from textclf.persistence import load_model, save_model
import textclf.persistence as p


def test_versioned_save_and_latest(tmp_path: Path):
    orig_dir = p.ARTIFACTS_DIR
    orig_latest = p.LATEST_PATH
    orig_runlog = getattr(p, "RUNLOG_PATH", None)

    try:
        p.ARTIFACTS_DIR = tmp_path
        p.LATEST_PATH = tmp_path / "model_latest.joblib"
        p.RUNLOG_PATH = tmp_path / "runs.jsonl"

        Xtr, Xte, ytr, _ = load_split(
            DEFAULT.categories,
            DEFAULT.test_size,
            DEFAULT.random_state,
            DEFAULT.shuffle,
        )
        pipe = train(build_pipeline(500, 100), Xtr, ytr)

        a1 = save_model(pipe, DEFAULT, tag="t1")
        a2 = save_model(pipe, DEFAULT, tag="t2")
        assert a1.exists() and a2.exists()
        assert a1 != a2

        m1, _ = load_model(a1)
        m2, _ = load_model(a2)

        assert predict(m1, Xte[:5]) == predict(m2, Xte[:5])

    finally:
        p.ARTIFACTS_DIR = orig_dir
        p.LATEST_PATH = orig_latest
        if orig_runlog is not None:
            p.RUNLOG_PATH = orig_runlog