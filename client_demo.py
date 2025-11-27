from textclf_client import Client
from textclf_client.api.default import predict_predict_post
from textclf_client.models import PredictRequest

def main() -> None:
    client = Client(base_url="http://localhost:8000")

    body = PredictRequest(
        texts=["Hockey fans were ecstatic after the playoff win."],
        return_prob=False,
    )

    response = predict_predict_post.sync(client=client, body=body)

    print("Labels:", response.labels)
    print("Probabilities:", response.probabilities)
    print("Model info:", response.model)

if __name__ == "__main__":
    main()