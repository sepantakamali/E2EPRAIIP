# API and Security

## Routes

| Route | Access | Purpose |
|---|---|---|
| `GET /health` | Public | Basic liveness |
| `GET /ready` | Public | Runtime readiness |
| `GET /health/details` | Internal | Detailed diagnostics |
| `GET /metrics` | Internal | Prometheus exposition |
| `POST /predict` | `predict:run` | Single or batch inference |
| `GET /models` | `models:read` | Published model discovery |
| `GET /version` | `version:read` | Resolved runtime identity |
| `GET /whoami` | `whoami:read` | Authenticated principal details |

FastAPI and Pydantic provide typed request validation and response contracts.
The service can return probabilities and resolved model identity alongside
predictions.

## Authentication

Protected requests use scoped bearer tokens. The token registry describes
principals, token hashes, scopes, issue and expiry times, and enabled state;
plain credentials are not committed to Git.

Production consumers use separate identities. The Streamlit UI reads its token
from a mounted secret file or environment variable, while the Prometheus path
uses a narrowly scoped monitoring credential through the internal proxy.

## Token lifecycle

Host-side administration in `admin/manage_tokens.py` supports listing registry
state without revealing credentials, planning and policy validation, mounted
credential verification, controlled successor issuance and overlap, atomic
secret installation, consumer restart, health verification, rollback,
finalisation, and immediate encrypted backup after successful rotation.

Production policy is defined in `deploy/token-principals.yml`. Audit collectors
export registry validity and expiry metrics without exporting token values.

## Streamlit UI

The UI supports authenticated single, batch, and file predictions; published
model selection; optional probabilities; structured results; CSV export; raw
JSON inspection; request history; and visible service/model status.

The displayed API base URL may be the internal Compose hostname. This does not
expose the API directly to the public network.

## Generated SDK

The FastAPI OpenAPI document is used to generate the Python package under
`textclf_client/`. The SDK supplies typed endpoint methods and models, while
`client_demo.py` demonstrates authenticated consumption with its own scoped
token. See [`../textclf_client/README.md`](../textclf_client/README.md).

## Request example

```bash
curl -X POST 'http://127.0.0.1:8000/predict?model=stable' \
  -H "Authorization: Bearer ${TEXTCLF_API_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"texts":["The team scored during the final."]}'
```

Use a locally issued token with `predict:run`; do not place a production token
in shell history, source files, screenshots, or documentation.

## Security boundaries

- No raw bearer token is displayed in the UI or committed to Git.
- Internal diagnostic and metrics routes are not exposed through the public proxy.
- Rate limiting and request validation protect application routes.
- Runtime secrets are mounted independently from application images.
- Rotation verifies the new consumer credential before retiring its predecessor.
