import argparse, logging, subprocess, sys
from pathlib import Path
from textclf.logging_conf import setup_logging
from textclf.persistence import promote_model, STABLE_PATH

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and promote a model to 'stable'.")
    parser.add_argument("artifact", type=str, help="Path to a versioned artifact to promote")
    parser.add_argument("--min-accuracy", type=float, default=0.90)
    parser.add_argument("--force", action="store_true", help="Skip validation gate")
    parser.add_argument("--stable-path", type=str, default=str(STABLE_PATH))
    args = parser.parse_args()

    setup_logging()
    log = logging.getLogger("textclf")

    if not args.force:
        r = subprocess.run(
            [sys.executable, "-m", "textclf.validate",
             "--model-path", args.artifact,
             "--min-accuracy", str(args.min_accuracy)],
            capture_output=True, text=True,
        )
        print(r.stdout)
        if r.returncode != 0:
            log.error("Validation failed. Use --force to override.")
            sys.exit(1)

    path = promote_model(Path(args.artifact), stable_path=Path(args.stable_path))
    log.info(f"Stable model updated at: {path}")

if __name__ == "__main__":
    main()