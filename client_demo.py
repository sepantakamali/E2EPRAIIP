from textclf_client import Client
from textclf_client.api.default import predict_predict_post
from textclf_client.models import PredictRequest

def main() -> None:
    # If you want to test locally instead, use "http://localhost:8000"
    client = Client(
        base_url="https://textclf-api-manual.onrender.com",
        timeout=10.0,
        # This keeps errors as "None" instead of raising — we'll inspect manually
        raise_on_unexpected_status=False,
    )

    body = PredictRequest(
        texts=["Hello from Render via SDK"],
        return_prob=False,
    )

    # Use sync_detailed so we can see status, headers, raw content, and parsed body
    response = predict_predict_post.sync_detailed(client=client, body=body)

    print("HTTP status:", response.status_code)
    print("Raw content:", response.content)
    print("Parsed object:", response.parsed)

if __name__ == "__main__":
    main()