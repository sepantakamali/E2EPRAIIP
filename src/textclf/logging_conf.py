import logging
import os
from pathlib import Path
import datetime as dt
from datetime import timezone

def setup_logging() -> None:
    # Idempotency
    if getattr(setup_logging, "_configured", False):
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    _format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    date_format = "%Y-%m-%dT%H:%M:%S%z"

    handlers: list[logging.Handler] = [logging.StreamHandler()]  # stdout for Docker/K8s

    # optional file logging (opt-in)
    if os.getenv("LOG_TO_FILE", "0") == "1":
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        timestamp = dt.datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        logfile = log_dir / f"textclf_{timestamp}.log"
        handlers.append(logging.FileHandler(logfile))

    logging.basicConfig(level=level, format=_format, datefmt=date_format, handlers=handlers)
    setup_logging._configured = True  # type: ignore[attr-defined]