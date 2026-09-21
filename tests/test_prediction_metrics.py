"""Regression coverage for the measurements used by error-rate alerts."""

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, Counter, Histogram

from textclf import api


@pytest.fixture
def metrics_client(monkeypatch):
    registry = CollectorRegistry()
    requests = Counter("test_requests", "Calls", registry=registry)
    errors = Counter("test_errors", "Failures", registry=registry)
    latency = Histogram("test_latency", "Duration", registry=registry)
    monkeypatch.setattr(api, "PREDICTIONS", requests)
    monkeypatch.setattr(api, "PREDICTION_ERRORS", errors)
    monkeypatch.setattr(api, "PREDICTION_LATENCY", latency)
    monkeypatch.setattr(api, "AUTH_ENABLED", False)
    monkeypatch.setattr(api, "_resolve_path", lambda *args: ("test-model", None))
    monkeypatch.setattr(api, "STATE", {
        "pipe": object(),
        "state": api.ModelState(path="test-model", pointer="test"),
    })
    monkeypatch.setattr(api, "predict_labels", lambda *args: [0])
    with TestClient(api.app, raise_server_exceptions=False) as client:
        yield client, registry


def assert_counts(registry, calls, failures):
    assert registry.get_sample_value("test_requests_total") == calls
    assert registry.get_sample_value("test_errors_total") == failures
    assert registry.get_sample_value("test_latency_count") == calls


@pytest.mark.parametrize("failure,status", [
    ("success", 200),
    ("missing_model", 404),
    ("load_failure", 404),
    ("too_many", 413),
    ("too_long", 413),
    ("unexpected", 500),
])
def test_each_handler_call_is_counted_once(metrics_client, monkeypatch, failure, status):
    client, registry = metrics_client
    body = {"texts": ["A hockey match."], "return_probabilities": False}

    def missing(*args):
        raise FileNotFoundError("Missing test artifact")

    def unexpected(*args):
        raise RuntimeError("Inference failed")

    if failure == "missing_model":
        monkeypatch.setattr(api, "_resolve_path", missing)
    elif failure == "load_failure":
        monkeypatch.setattr(api, "STATE", {"pipe": None, "state": None})
        monkeypatch.setattr(api, "_load_into_state", missing)
    elif failure == "too_many":
        monkeypatch.setattr(api, "MAX_TEXTS", 0)
    elif failure == "too_long":
        monkeypatch.setattr(api, "MAX_TEXT_LEN", 1)
    elif failure == "unexpected":
        monkeypatch.setattr(api, "predict_labels", unexpected)

    response = client.post("/predict", json=body)
    assert response.status_code == status
    assert_counts(registry, 1, int(status != 200))


@pytest.mark.parametrize("rejection", ["schema", "authentication"])
def test_rejections_before_handler_are_excluded(metrics_client, monkeypatch, rejection):
    client, registry = metrics_client
    body = {"texts": ["A hockey match."]}
    expected = 422
    if rejection == "schema":
        body = {"texts": None}
    else:
        monkeypatch.setattr(api, "AUTH_ENABLED", True)
        expected = 401
    assert client.post("/predict", json=body).status_code == expected
    assert_counts(registry, 0, 0)
