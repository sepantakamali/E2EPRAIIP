import argparse
import logging
from pathlib import Path

from textclf.logging_conf import setup_logging
from textclf.persistence import load_model, _resolve_pointer_path
from textclf.model import predict

def main() -> None:
    parser = argparse.ArgumentParser(description="Load a saved model and run inference.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--use", choices=["latest", "stable"], default="stable", help="Choose which pointer to use")
    group.add_argument("--model-path", type=str, help="Explicit path to a joblib model (overrides --use)")
    parser.add_argument("--text", type=str, nargs="+", required=True, help="One or more input texts to classify")
    args = parser.parse_args()

    setup_logging()
    log = logging.getLogger("textclf")

    # resolve model path
    try:
        if args.model_path:
            path = Path(args.model_path)
        else:
            path = _resolve_pointer_path(args.use)
    except Exception as e:
        raise SystemExit(f"Could not resolve model selection: {e}")

    pipe, meta = load_model(path)
    log.info(
        "Loaded model from %s | model_id=%s release_tag=%s software_version=%s created_at=%s",
        path,
        getattr(meta, "model_id", "?"),
        getattr(meta, "release_tag", "unreleased"),
        getattr(meta, "software_version", "?"),
        getattr(meta, "created_at", "?"),
    )

    preds = predict(pipe, args.text)
    for t, p in zip(args.text, preds):
        log.info(f"{t!r} => class {p}")

if __name__ == "__main__":
    main()