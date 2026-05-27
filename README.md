# End-to-End Production-Ready AI Inference Platform

Modern text classification inference platform with a FastAPI backend, Streamlit UI, model artifact versioning, token-based authentication, Docker deployment, Prometheus/Grafana monitoring, and a generated Python SDK.

> Repository: https://github.com/sepantakamali/E2EPRAIIP

---

## What This Project Provides

- A trained text classification model served through a typed FastAPI API
- Versioned model artifacts with metadata, `latest`, and `stable` pointer resolution
- A Streamlit UI for local/product-style interaction with the inference service
- Bearer-token authentication with scoped tokens
- Prometheus metrics and Grafana dashboards for operational monitoring
- Docker Compose stacks for product and monitoring environments
- A generated OpenAPI Python SDK for downstream integration
- Automated quality gates with `pytest`, `mypy`, GitHub Actions, and GHCR image publishing

---

## Architecture

The project is easier to understand as several connected layers rather than one large diagram.

### 1. System Overview

```mermaid
flowchart LR
    Train[Train Model] --> Artifact[Versioned Model Artifact]
    Artifact --> Registry[Artifact Registry]
    Registry --> API[FastAPI API]
    API --> UI[Streamlit UI]
    API --> Metrics[Prometheus Metrics]
    Metrics --> Grafana[Grafana Dashboard]
    API --> Schema[OpenAPI Schema]
    Schema --> SDK[Generated Python SDK]
```

### 2. Model Lifecycle

```mermaid
flowchart TD
    Train[Training Pipeline] --> Build[Build Text Classifier]
    Build --> Save[Save Joblib Artifact]
    Save --> Meta[Write Artifact Metadata]
    Save --> Pointers[Update Pointers File]
    Save --> Runs[Append Run Log]

    Pointers --> Latest[Latest Pointer]
    Pointers --> Stable[Stable Pointer]

    Save --> Promote[Promote Artifact]
    Promote --> Stable
    Promote --> Published[Mark Published]
    Promote --> Release[Optional Release Tag]

    Latest --> Resolve[Model Resolution]
    Stable --> Resolve
    Meta --> Resolve
    Resolve --> API[FastAPI Runtime State]
```

### 3. API, Authentication, and Client Flow

```mermaid
flowchart LR
    TokenScript[Token Issuer Script] --> TokenFile[Client Token File]
    TokenFile --> SDKClient[Authenticated SDK Client]
    SDKClient --> Auth[Bearer Auth Layer]
    Auth --> API[FastAPI API]

    API --> Predict[Predict Endpoint]
    API --> Version[Version Endpoint]
    API --> Models[Models Endpoint]
    API --> Whoami[Whoami Endpoint]
    API --> Health[Health Endpoint]

    API --> OpenAPI[OpenAPI Schema]
    OpenAPI --> Generator[OpenAPI Python Client Generator]
    Generator --> SDKPackage[Generated Python SDK]
```

### 4. Docker and Monitoring Layout

```mermaid
flowchart TD
    ProductCompose[Product Compose Stack] --> UI[Streamlit UI Container]
    ProductCompose --> API[FastAPI API Container]
    ProductCompose --> Proxy[Metrics Proxy Container]

    MonitorCompose[Monitoring Compose Stack] --> Prometheus[Prometheus Container]
    MonitorCompose --> Grafana[Grafana Container]

    UI --> API
    Prometheus --> Proxy
    Proxy --> API
    Prometheus --> Grafana
```

---

## Features

### FastAPI Inference Service

Protected endpoints include:

- `POST /predict`
- `GET /version`
- `GET /models`
- `GET /whoami`

Operational endpoints include:

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `GET /openapi.json` when documentation is enabled
- `GET /docs` when documentation is enabled

Main API features:

- Pydantic v2 request and response schemas
- OpenAPI schema generation
- Bearer-token authentication
- Scoped token support
- Structured request logging
- Request IDs
- Runtime model metadata reporting
- Prometheus metric instrumentation

### Model Versioning and Promotion

The model lifecycle supports:

- versioned `.joblib` artifacts under `artifacts/`
- artifact metadata including model ID, software version, creation time, hash, publication status, and release tag
- `pointers.json` for `latest` and `stable` model resolution
- run logging through `runs.model`
- model promotion from candidate artifact to stable artifact
- model selection by pointer, model ID, or artifact filename

### Streamlit UI

The Streamlit interface supports:

- single text prediction
- batch prediction
- file upload
- model selection
- prediction result display
- raw JSON inspection
- request history
- CSV export
- helpful links to API and monitoring endpoints

### Generated Python SDK

The SDK is generated from the FastAPI OpenAPI schema and lives under:

```text
textclf_client/
```

It provides:

- typed request models
- typed response models
- endpoint wrapper functions
- authenticated client support through `AuthenticatedClient`
- reusable integration code for external Python consumers

### Observability

Monitoring support includes:

- Prometheus scraping
- Grafana dashboards
- prediction request counters
- prediction error counters
- prediction latency histograms
- process CPU and memory metrics
- Python runtime metrics
- file descriptor metrics
- structured application logs

### Deployment

Current deployment-related files:

- `Dockerfile` for building the application image
- `docker-compose.product.yml` for the product stack
- `docker-compose.monitor.yml` for the monitoring stack
- `docker-compose.yml` as a lightweight local development compose setup
- GitHub Actions workflow for tests and type checking
- GitHub Actions workflow for Docker image publishing to GHCR

---

## Project Structure

```text
.
├── artifacts/                  # Model artifacts, pointers, and run logs
├── monitoring/                 # Prometheus and Grafana configuration
├── nginx/                      # Metrics proxy configuration
├── logs/                       # Local application log files
├── scripts/                    # Token, setup, and utility scripts
├── src/
│   └── textclf/
│       ├── api.py              # FastAPI app, routes, auth integration, runtime state
│       ├── cli.py              # CLI utilities for model operations
│       ├── config.py           # Project configuration defaults
│       ├── data.py             # Dataset loading and train/test splitting
│       ├── logging_conf.py     # Logging configuration
│       ├── metrics.py          # Prometheus metrics
│       ├── model.py            # ML pipeline construction and prediction helpers
│       ├── persistence.py      # Save/load, metadata, pointers, promotion logic
│       └── ...
├── tests/                      # pytest test suite
├── textclf_client/             # Generated Python SDK package
├── ui/                         # Streamlit frontend
├── Dockerfile
├── docker-compose.product.yml
├── docker-compose.monitor.yml
├── docker-compose.yml
├── client_demo.py              # Example SDK consumer
├── client_config.yaml          # Client-side configuration example
├── pyproject.toml
├── requirements.txt
├── Makefile
├── .env.example
└── README.md
```

---

## Authentication

Protected routes use Bearer token authentication.

Tokens are issued with:

```bash
python scripts/issue_token.py \
  --subject client-demo \
  --client-id client-demo \
  --scopes predict:run version:read whoami:read health:read \
  --rotation-group client-demo
```

The raw token should be stored outside the repository. For the demo client, the token path is configured through:

```env
CLIENT_DEMO_TOKEN_FILE=../practice_sprint_secrets/client_demo_token.txt
```

Before running local scripts that depend on `.env`, load environment variables:

```bash
set -a
source .env
set +a
```

---

## Generated Python SDK

Regenerate the SDK from a running local API with documentation enabled:

```bash
openapi-python-client generate \
  --url http://127.0.0.1:8000/openapi.json \
  --overwrite \
  --output-path textclf_client
```

Run the demo client:

```bash
python client_demo.py
```

The demo client uses:

- `AuthenticatedClient`
- `PredictRequest`
- bearer token loaded from `CLIENT_DEMO_TOKEN_FILE`
- explicit model selection

---

## Local Development

Load environment variables:

```bash
set -a
source .env
set +a
```

Run the API locally:

```bash
SHOW_DOCS=1 INTERNAL_ONLY_ENABLED=false RATE_LIMIT_ENABLED=0 \
uvicorn textclf.api:app \
  --host 127.0.0.1 \
  --port 8000 \
  --loop asyncio \
  --reload
```

Run the Streamlit UI locally:

```bash
streamlit run ui/app.py
```

Run tests:

```bash
pytest
```

Run type checking:

```bash
mypy src
```

---

## Docker Usage

Start the product stack:

```bash
docker compose -p textclf-product -f docker-compose.product.yml up -d
```

Start the monitoring stack:

```bash
docker compose -p textclf-monitor -f docker-compose.monitor.yml up -d
```

Stop the product stack:

```bash
docker compose -p textclf-product -f docker-compose.product.yml down
```

Stop the monitoring stack:

```bash
docker compose -p textclf-monitor -f docker-compose.monitor.yml down
```

The product stack exposes the UI to the host. The API is intended to remain internal to the Docker network in production-style compose usage, while the UI and monitoring tools are the main user-facing entry points.

---

## Monitoring

Typical local endpoints:

```text
Streamlit UI: http://localhost:8501
Prometheus:   http://localhost:9090
Grafana:      http://localhost:3000
```

When running the API directly outside Docker, these are also available if docs are enabled:

```text
API:          http://127.0.0.1:8000
Swagger Docs: http://127.0.0.1:8000/docs
OpenAPI JSON: http://127.0.0.1:8000/openapi.json
```

Useful Prometheus queries:

```promql
up{job="textclf-api"}
```

```promql
prediction_requests_total{job="textclf-api"}
```

```promql
sum(rate(prediction_requests_total{job="textclf-api"}[5m]))
```

```promql
histogram_quantile(
  0.95,
  sum(rate(prediction_latency_seconds_bucket{job="textclf-api"}[5m])) by (le)
)
```

---

## API Example

Example authenticated request:

```bash
TOKEN="$(cat ../practice_sprint_secrets/client_demo_token.txt)"

curl -X POST "http://127.0.0.1:8000/predict?model=stable" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "texts": ["Hockey fans were ecstatic after the playoff win."],
    "return_probabilities": false
  }'
```

---

## Testing

Current tests cover:

- API smoke path with isolated temporary model artifacts
- dataset loading and split invariants
- model training and prediction
- artifact save/load/versioning behavior
- promotion behavior

Run all checks:

```bash
pytest
mypy src
```

---

## CI/CD

GitHub Actions currently provide:

- CI workflow:
  - dependency installation
  - `mypy src`
  - `pytest -q`
- Docker workflow:
  - Docker build
  - login to GHCR
  - push image tags to GitHub Container Registry

Planned CI/CD work:

- dependency pinning refinement
- release tagging
- deployment workflow
- branch protection and required checks
- production deployment automation

---

## Current Status

Implemented:

- FastAPI inference API
- typed request/response schemas
- model versioning and promotion
- artifact metadata and pointer resolution
- generated Python SDK
- token-based authentication and scopes
- Streamlit UI
- Docker product and monitoring stacks
- Prometheus monitoring
- Grafana integration
- structured logging
- pytest and mypy quality gates
- GitHub Actions CI
- GHCR image publishing

Remaining work:

- dependency pinning refinement
- Makefile modernization
- client utility cleanup
- final CI/CD polish
- production deployment automation
- cloud deployment hardening