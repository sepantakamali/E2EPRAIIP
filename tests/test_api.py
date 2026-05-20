from pathlib import Path

from fastapi.testclient import TestClient
from textclf import api
from textclf.api import app
from textclf.config import DEFAULT
from textclf.data import load_split
from textclf.model import build_pipeline, train
from textclf.persistence import load_model, save_model
import textclf.persistence as p


client = TestClient(app)


def test_health_and_predict_smoke(tmp_path: Path):
    orig_internal = api.INTERNAL_ONLY_ENABLED
    orig_auth = api.AUTH_ENABLED
    orig_pipe = api.STATE["pipe"]
    orig_meta = api.STATE["meta"]
    orig_model_state = api.STATE["state"]
    orig_artifacts_dir = p.ARTIFACTS_DIR
    orig_latest = p.LATEST_PATH
    orig_runlog = getattr(p, "RUNLOG_PATH", None)

    try:
        api.INTERNAL_ONLY_ENABLED = False
        api.AUTH_ENABLED = False
        p.ARTIFACTS_DIR = tmp_path
        p.LATEST_PATH = tmp_path / "model_latest.joblib"
        p.RUNLOG_PATH = tmp_path / "runs.jsonl"

        X_train, _, y_train, _ = load_split(
            DEFAULT.categories,
            DEFAULT.test_size,
            DEFAULT.random_state,
            DEFAULT.shuffle,
        )
        pipe = train(build_pipeline(200, 50), X_train, y_train)
        artifact_path = save_model(pipe, DEFAULT, tag="api-smoke")
        pipe_loaded, meta_loaded = load_model(artifact_path)
        api.STATE["pipe"] = pipe_loaded
        api.STATE["meta"] = meta_loaded
        api.STATE["state"] = api.ModelState(
            path=str(artifact_path),
            pointer="test",
            meta_version=getattr(meta_loaded, "model_id", None) or getattr(meta_loaded, "version", None),
            meta_created_at=getattr(meta_loaded, "created_at", None),
            meta_software_version=getattr(meta_loaded, "software_version", None),
            meta_release_tag=getattr(meta_loaded, "release_tag", "unreleased"),
            meta_published=bool(getattr(meta_loaded, "published", False)),
        )

        r = client.get("/health")
        assert r.status_code == 200 and r.json()["status"] == "ok"

        payload = {
            "texts": ["Hockey fans were ecstatic after the playoff win."],
            "return_probabilities": False,
        }

        pr = client.post("/predict", json=payload)
        assert pr.status_code == 200

        data = pr.json()
        assert "labels" in data and isinstance(data["labels"], list)
        assert "model" in data and "model_path" in data["model"]

    finally:
        api.INTERNAL_ONLY_ENABLED = orig_internal
        api.AUTH_ENABLED = orig_auth
        api.STATE["pipe"] = orig_pipe
        api.STATE["meta"] = orig_meta
        api.STATE["state"] = orig_model_state
        p.ARTIFACTS_DIR = orig_artifacts_dir
        p.LATEST_PATH = orig_latest
        if orig_runlog is not None:
            p.RUNLOG_PATH = orig_runlog