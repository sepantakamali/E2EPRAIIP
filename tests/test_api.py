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
    # Saving original global state
    original_internal = api.INTERNAL_ONLY_ENABLED
    original_auth = api.AUTH_ENABLED
    original_pipe = api.STATE["pipe"]
    original_meta = api.STATE["meta"]
    original_model_state = api.STATE["state"]
    original_artifacts_dir = p.ARTIFACTS_DIR
    original_latest = p.LATEST_PATH
    original_pointers_path = p.POINTERS_PATH
    original_runlog_path = p.RUNLOG_PATH

    try:
        # Changing it to temporary testing state
        api.INTERNAL_ONLY_ENABLED = False
        api.AUTH_ENABLED = False
        p.ARTIFACTS_DIR = tmp_path
        p.LATEST_PATH = tmp_path / "model_latest.joblib"
        p.POINTERS_PATH = tmp_path / "pointers.json"
        p.RUNLOG_PATH = tmp_path / "runs.jsonl"

        # Using default config values
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

        get_health = client.get("/health")
        assert get_health.status_code == 200 and get_health.json()["status"] == "ok"

        payload = {
            "texts": ["Hockey fans were ecstatic after the playoff win."],
            "return_probabilities": False,
        }

        post_predict = client.post("/predict", json=payload)
        assert post_predict.status_code == 200

        data = post_predict.json()
        assert "labels" in data and isinstance(data["labels"], list)
        assert "model" in data and "model_path" in data["model"]

    finally:
        # Reapplying the default values
        api.INTERNAL_ONLY_ENABLED = original_internal
        api.AUTH_ENABLED = original_auth
        api.STATE["pipe"] = original_pipe
        api.STATE["meta"] = original_meta
        api.STATE["state"] = original_model_state
        p.ARTIFACTS_DIR = original_artifacts_dir
        p.LATEST_PATH = original_latest
        p.POINTERS_PATH = original_pointers_path
        p.RUNLOG_PATH = original_runlog_path