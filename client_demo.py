import os
from pathlib import Path
from textclf_api_client import AuthenticatedClient
from textclf_api_client.api.default import (
    health_health_get,
    models_models_get,
    predict_predict_post,
    version_version_get,
    whoami_whoami_get,
)
from textclf_api_client.models.predict_request import PredictRequest


API_BASE_URL = "http://127.0.0.1:8000"
client_demo_token_file = os.getenv("CLIENT_DEMO_TOKEN_FILE")
if not client_demo_token_file:
    raise EnvironmentError(
        "CLIENT_DEMO_TOKEN_FILE is not set. Load .env first with: "
        "set -a && source .env && set +a"
    )
CLIENT_DEMO_TOKEN_FILE = Path(client_demo_token_file)
MODEL_SELECTOR = os.getenv("CLIENT_DEMO_MODEL", "stable")


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

    print("=== CLIENT CONFIG ===")
    print("Base URL:", API_BASE_URL)
    print("Model selector:", MODEL_SELECTOR)
    print("Token file:", CLIENT_DEMO_TOKEN_FILE)
    print()

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

    print("=== MODELS ===")
    models = models_models_get.sync_detailed(client=client)
    print("Status:", models.status_code)
    print("Parsed:", models.parsed)
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
    if prediction.parsed is None:
        print("Raw content:", prediction.content)
        return

    print("Labels:", prediction.parsed.labels)
    print("Probabilities:", prediction.parsed.probabilities)
    print("Model:", prediction.parsed.model)


if __name__ == "__main__":
    main()