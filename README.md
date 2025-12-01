# End-to-End Production-Ready AI Inference Platform

Modern, production-style text classification service with:

- FastAPI + Pydantic v2 for a typed, OpenAPI-compliant HTTP API  
- Dockerized deployment with model versioning and promotion (latest / stable)  
- Structured logging, Prometheus metrics, and optional Grafana Cloud integration  
- Strong type safety and testing (mypy, pytest)  
- A generated Python client SDK for downstream integration

> Repository: https://github.com/sepantakamali/E2EPRAIIP

---

## Features

- **FastAPI inference microservice**  
  - `/health` and `/predict` endpoints  
  - Built-in request validation (Pydantic v2)  
  - Automatic OpenAPI / Swagger docs at `/docs` and `/redoc`

- **Model versioning & promotion**  
  - Versioned artifacts stored under `artifacts/`  
  - Pointers for `latest` and `stable` models (`model_latest.joblib`, `model_stable.joblib`)  
  - CLI and helper scripts to train, save, and promote models

- **Production-style deployment**  
  - Dockerfile for building `textclf-api` images  
  - `docker-compose.yml` for running the API container with mounted artifacts  
  - `docker-compose.monitor.yml` for running Prometheus + API locally

- **Observability & rate limiting**  
  - `/metrics` endpoint with Prometheus client metrics  
  - Custom application metrics:
    - `pred_requests_total`
    - `pred_request_errors_total`
    - `pred_latency_seconds` (histogram)
  - Optional integration with Grafana Cloud via `remote_write`  
  - SlowAPI-based rate limiting on `/predict` (IP-based)

- **Quality gates**  
  - `pytest` test suite, including API tests (`tests/test_api.py`)  
  - `mypy` static type checking across `src/`  
  - Configurable logging via `logging_conf.py`

- **Client SDK**  
  - OpenAPI schema exposed at `/openapi.json`  
  - Generated Python client in `textclf_client/` for programmatic use  
  - Install locally with: `pip install -e textclf_client`
  - Example usage in `client_demo.py`

## Production deployment (Render)

A public demo deployment is available on Render:

- Current demo: https://e2epraiip.onrender.com

- Base URL: `https://e2epraiip.onrender.com`
- Health check: `GET /health`
- OpenAPI docs: `GET /docs`
- Metrics: `GET /metrics` (if exposed)

Example request:

```bash
curl -X POST "https://e2epraiip.onrender.com/predict?model=stable" \
  -H "Content-Type: application/json" \
  -d '{"texts":["Hockey fans were ecstatic after the playoff win."],"return_prob":false}'
```

---

## Tech Stack

- **Language**: Python 3.11+
- **Web Framework**: FastAPI
- **Validation**: Pydantic v2
- **Model Persistence**: joblib
- **Containerization**: Docker
- **Rate Limiting**: SlowAPI
- **Monitoring**: Prometheus, optional Grafana Cloud
- **Testing**: pytest
- **Typing**: mypy

---

## Project Structure

```text
.
├── src/
│   └── textclf/
│       ├── api.py             # FastAPI application & endpoints
│       ├── cli.py             # CLI for training/promoting models
│       ├── persistence.py     # Model save/load, runlog, promotion logic
│       ├── logging_conf.py    # Logging configuration
│       ├── predict.py         # CLI prediction tool
│       └── ...
├── monitoring/
│   ├── prometheus.yml         # Prometheus config (local + remote_write)
│   └── alerts.yml             # Example alert rules
├── tests/
│   ├── test_api.py
│   ├── test_versioning.py
│   └── test_promotion.py
├── docker-compose.yml         # Run API container
├── docker-compose.monitor.yml # Run API + Prometheus for monitoring
├── Dockerfile                 # Build textclf-api image
├── client_demo.py             # Example usage of the generated Python client
├── .env.example               # Example environment variables (no secrets)
└── README.md