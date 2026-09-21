# Optional Python client for E2EPRAIIP

This package is generated from the FastAPI OpenAPI schema. It lets another
Python application call the existing inference API using request and response
models. It does not contain the classifier or run an inference server.

The Streamlit UI uses `requests.Session` directly. The SDK is an optional
integration example; adopting it is useful when several Python consumers need
the same API contract, but is not required for this small UI.

## Install and run the demo

From the repository root, in the development virtual environment:

```bash
pip install -e ./textclf_client
export CLIENT_DEMO_API_BASE_URL=http://127.0.0.1:8000
export CLIENT_DEMO_TOKEN_FILE=/absolute/path/to/local-client-token.txt
python client_demo.py
```

Run the API separately with authentication configured. The demo token needs
`predict:run`, `models:read`, `version:read`, and `whoami:read`. The SDK needs a
network route to the API: the production public website does not expose the API
routes. Do not use the website URL as though it were a public SDK API endpoint.

## Make a prediction

```python
import os
from pathlib import Path

from textclf_api_client import AuthenticatedClient
from textclf_api_client.api.default import predict_predict_post
from textclf_api_client.models.predict_request import PredictRequest

token = Path(os.environ["CLIENT_DEMO_TOKEN_FILE"]).read_text().strip()
with AuthenticatedClient(
    base_url="http://127.0.0.1:8000", token=token, timeout=10.0
) as client:
    response = predict_predict_post.sync_detailed(
        client=client,
        model="stable",
        body=PredictRequest(
            texts=["The hockey team won the final."],
            return_probabilities=True,
        ),
    )
    if response.status_code == 200 and response.parsed is not None:
        print(response.parsed.labels)
    else:
        print("Request failed:", response.status_code)
```

The example assumes `stable` selects an available model. `client_demo.py`
provides configurable model selection and exercises health, identity, model
listing, version, and prediction endpoints.

## Regenerate

With the local API running and its OpenAPI document enabled:

```bash
pip install openapi-python-client
make sdk
```

Generation overwrites `textclf_client/`, including this README. Review generated
changes, restore project-specific documentation, and run the client demo after
schema changes. The generator is not pinned by the current project configuration.

Generated endpoint modules offer synchronous and asynchronous calls. The
`*_detailed` forms return status, headers, raw content, and a parsed response
when available. Keep HTTPS verification enabled for HTTPS endpoints.
