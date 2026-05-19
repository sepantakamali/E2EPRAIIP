import argparse
import logging
import os
from pathlib import Path

from textclf.config import DEFAULT
from textclf.logging_conf import setup_logging
from textclf.data import load_split
from textclf.model import build_pipeline, train, predict
from textclf.evaluate import evaluate
from textclf.persistence import (
    save_model,
    publish_model,
    promote_model,
)

MAX_TEXTS = int(os.getenv("MAX_TEXTS", "64"))
MAX_TEXT_LEN = int(os.getenv("MAX_TEXT_LEN", "2000"))


def cmd_train(args: argparse.Namespace) -> None:
    setup_logging()
    log = logging.getLogger("textclf")

    cfg = DEFAULT # Not the ideal way but lets keep it working for now...
    
    log.info(f"Using categories: {cfg.categories}")

    X_train, X_test, y_train, y_test = load_split(
        cfg.categories,
        cfg.test_size,
        cfg.random_state,
        cfg.shuffle,
    )

    pipe = build_pipeline(cfg.max_features, cfg.max_iter)
    pipe = train(pipe, X_train, y_train)

    y_pred = predict(pipe, X_test)
    metrics = evaluate(y_test, y_pred)

    log.info(f"Accuracy: {metrics['accuracy']:.4f}")
    log.info("\n" + metrics["report"])

    pred = predict(pipe, [args.sample])[0]
    log.info(f"Sample -> {args.sample!r} => class {pred}")

    if args.save:
        path = save_model(pipe, DEFAULT, tag=args.tag if args.tag else None)
        log.info(f"Saved model to: {path}")


def cmd_publish(args: argparse.Namespace) -> None:
    publish_model(
        artifact=Path(args.artifact),
        force=args.force,
        allow_skip=args.allow_skip,
        edit=args.edit,
        unpublish=args.unpublish,
        release_tag=args.release_tag,
    )


def cmd_promote(args: argparse.Namespace) -> None:
    promote_model(Path(args.artifact))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Text classifier CLI")
    sub = parser.add_subparsers(dest="command")

    # train
    p_train = sub.add_parser("train", help="Train and optionally save a model")
    p_train.add_argument(
        "--sample",
        type=str,
        default="The team played a great game last night and scored twice.",
        help="Sample text to classify",
    )
    p_train.add_argument("--save", action="store_true", help="Save the trained model")
    p_train.add_argument("--tag", type=str, default="", help="Optional tag for artifact")
    p_train.set_defaults(func=cmd_train)

    # publish
    p_publish = sub.add_parser("publish", help="Publish a model artifact with release tag")
    p_publish.add_argument("artifact", help="Path to artifact")
    p_publish.add_argument("--edit", help="Change publish status or release tag")
    p_publish.add_argument("--unpublish", help="Discontinue a published model")
    p_publish.add_argument("--release-tag", help="Release tag (vMAJOR.MINOR)")
    p_publish.add_argument("--force", action="store_true")
    p_publish.add_argument("--allow-skip", action="store_true")
    p_publish.set_defaults(func=cmd_publish)

    # promote
    p_promote = sub.add_parser("promote", help="Promote artifact to stable pointer")
    p_promote.add_argument("artifact", help="Path to artifact")
    p_promote.set_defaults(func=cmd_promote)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # default behaviour: run train if no subcommand provided
    if not getattr(args, "command", None):
        cmd_train(args)
        return

    args.func(args)


if __name__ == "__main__":
    main()