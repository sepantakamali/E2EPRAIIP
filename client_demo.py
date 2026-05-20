import os
from pathlib import Path
from textclf_api_client import AuthenticatedClient
from textclf_api_client.api.default import (
    health_health_get,
    predict_predict_post,
    version_version_get,
    whoami_whoami_get,
)
from textclf_api_client.models.predict_request import PredictRequest


API_BASE_URL = "http://127.0.0.1:8000"
CLIENT_DEMO_TOKEN_FILE = Path(os.getenv("CLIENT_DEMO_TOKEN_FILE"))
MODEL_SELECTOR = "model_20260313_175256-experiment5.joblib"


def read_token(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(
            f"Client demo token file not found: {path}. "
            "Set CLIENT_DEMO_TOKEN_FILE in .env or export it before running the demo."
        )
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError(f"Client demo token file is empty: {path}")
    return token


def main() -> None:
    token = read_token(CLIENT_DEMO_TOKEN_FILE)
    client = AuthenticatedClient(
        base_url=API_BASE_URL,
        token=token,
        timeout=10.0,
        raise_on_unexpected_status=False,
    )

    print("=== HEALTH CHECK ===")
    health = health_health_get.sync_detailed(client=client)
    print("Status:", health.status_code)
    print("Parsed:", health.parsed)
    print()

    print("=== WHOAMI ===")
    whoami = whoami_whoami_get.sync_detailed(client=client)
    print("Status:", whoami.status_code)
    print("Parsed:", whoami.parsed)
    print()

    print("=== VERSION ===")
    version = version_version_get.sync_detailed(
        client=client,
        model=MODEL_SELECTOR,
    )
    print("Status:", version.status_code)
    print("Parsed:", version.parsed)
    print()

    print("=== PREDICTION ===")
    body = PredictRequest(
        texts=[
            "The hockey team secured a dramatic playoff victory last night.",
            "NASA announced a new mission to explore deep space.",
        ],
        return_probabilities=True,
    )

    prediction = predict_predict_post.sync_detailed(
        client=client,
        body=body,
        model=MODEL_SELECTOR,
    )

    print("Status:", prediction.status_code)
    print("Raw content:", prediction.content)
    print("Parsed:", prediction.parsed)


if __name__ == "__main__":
    main()