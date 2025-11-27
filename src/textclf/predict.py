import argparse
import logging
from typing import List
from textclf.logging_conf import setup_logging
from textclf.persistence import load_model, LATEST_PATH, STABLE_PATH
from textclf.model import predict

def main() -> None:
    parser = argparse.ArgumentParser(description="Load a saved model and run inference.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--use", choices=["latest", "stable"], help="Choose which pointer to use")
    group.add_argument("--model-path", type=str, help="Explicit path to a joblib model (overrides --use)")
    parser.add_argument("--text", type=str, nargs="+", required=True, help="One or more input texts to classify")
    args = parser.parse_args()

    setup_logging()
    log = logging.getLogger("textclf")

    # resolve model path
    if args.model_path:
        path = args.model_path
    elif args.use == "stable":
        path = str(STABLE_PATH)
    else:
        # default behavior: latest
        path = str(LATEST_PATH)

    pipe, meta = load_model(path)
    log.info(f"Loaded model from {path} | version={getattr(meta,'version','?')} created_at={getattr(meta,'created_at','?')}")

    preds: List[int] = predict(pipe, args.text)
    for t, p in zip(args.text, preds):
        log.info(f"{t!r} => class {p}")

if __name__ == "__main__":
    main()