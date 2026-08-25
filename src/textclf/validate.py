from __future__ import annotations
import json, sys
from pathlib import Path
from textclf.config import DEFAULT
from textclf.data import load_split
from textclf.model import predict
from textclf.persistence import load_model

def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Validate a saved model on held-out data.")
    p.add_argument("--model-path", type=str, required=True)
    p.add_argument("--min-accuracy", type=float, default=0.90)
    p.add_argument("--report-out", type=str, default="")
    args = p.parse_args()

    Xtr, Xte, ytr, yte = load_split(DEFAULT.categories, DEFAULT.test_size, DEFAULT.random_state, DEFAULT.shuffle)
    pipe, meta = load_model(args.model_path)
    preds = predict(pipe, Xte)
    acc = sum(int(a == b) for a, b in zip(preds, yte)) / len(yte)

    report = {
        "model_path": args.model_path,
        "model_id": getattr(meta, "model_id", "?"),
        "software_version": getattr(meta, "software_version", "?"),
        "created_at": getattr(meta, "created_at", "?"),
        "published": bool(getattr(meta, "published", False)),
        "release_tag": getattr(meta, "release_tag", "unreleased"),
        "accuracy": acc,
        "min_required": args.min_accuracy,
        "passed": acc >= args.min_accuracy,
    }
    if args.report_out:
        Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_out).write_text(json.dumps(report, indent=2))

    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1

if __name__ == "__main__":
    sys.exit(main())
