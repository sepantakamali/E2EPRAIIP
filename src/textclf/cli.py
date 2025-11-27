import argparse
import logging
from textclf.config import DEFAULT
from textclf.logging_conf import setup_logging
from textclf.data import load_split
from textclf.model import build_pipeline, train, predict
from textclf.evaluate import evaluate
from textclf.persistence import save_model, LATEST_PATH
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import os

MAX_TEXTS = int(os.getenv("MAX_TEXTS", "64"))
MAX_TEXT_LEN = int(os.getenv("MAX_TEXT_LEN", "2000"))

def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate a tiny text classifier.")
    parser.add_argument(
        "--sample", type=str, 
        default="The team played a great game last night and scored twice.",
        help="Sample text to classify"
        )
    parser.add_argument(
        "--save", action = "store_true",
        help="Save the trained model to disk",
    )
    parser.add_argument(
        "--model-path", type=str, default="",
        help="Explicit output path; if omitted a versioned name is generated",
    )
    parser.add_argument("--tag", type=str, default="",
                        help="Optional tag to include in generated filename")
    args = parser.parse_args()

    setup_logging()
    log = logging.getLogger("textclf")

    cfg = DEFAULT
    log.info(f"Using categories: {cfg.categories}")

    X_train, X_test, y_train, y_test = load_split(cfg.categories, cfg.test_size, cfg.random_state)
    
    pipe = build_pipeline(cfg.max_features, cfg.max_iter)
    pipe = train(pipe, X_train, y_train)

    y_pred = predict(pipe, X_test)
    metrics = evaluate(y_test, y_pred)

    log.info(f"Accuracy: {metrics['accuracy']:.4f}")
    log.info("\n" + metrics["report"])

    pred = predict(pipe, [args.sample])[0]
    log.info(f"Sample -> {args.sample!r} => class {pred}")

    if args.save:
        save_path = args.model_path if args.model_path else None
        tag = args.tag if args.tag else None
        path = save_model(pipe, DEFAULT, tag=args.tag)
        log.info(f"Saved model to: {path}")

if __name__ == "__main__":
    main()