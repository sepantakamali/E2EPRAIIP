from fastapi.testclient import TestClient
from textclf.api import app, _load_into_state

client = TestClient(app)

def test_health_and_predict_smoke():
    # Ensure a model is loaded (defaults to latest pointer)
    _load_into_state()
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"

    payload = {"texts": ["Hockey fans were ecstatic after the playoff win."], "return_prob": False}
    pr = client.post("/predict", json=payload)
    assert pr.status_code == 200
    data = pr.json()
    assert "labels" in data and isinstance(data["labels"], list)
    assert "model" in data and "model_path" in data["model"]