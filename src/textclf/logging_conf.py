import logging
import os
from pathlib import Path
import datetime as dt
from datetime import timezone

def setup_logging() -> None:
    # idempotent
    if getattr(setup_logging, "_configured", False):
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S%z"

    handlers: list[logging.Handler] = [logging.StreamHandler()]  # stdout for Docker/K8s

    # optional file logging (opt-in)
    if os.getenv("LOG_TO_FILE", "0") == "1":
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        ts = dt.datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        logfile = log_dir / f"textclf_{ts}.log"
        handlers.append(logging.FileHandler(logfile))

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)
    setup_logging._configured = True  # type: ignore[attr-defined]