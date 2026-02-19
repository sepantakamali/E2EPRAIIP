from __future__ import annotations

from .__init__ import  __version__

import logging
import os
import time
from typing import List, Literal, Optional, Tuple, Any

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response
from fastapi import Body
from pydantic import BaseModel, Field
from pydantic import ConfigDict # pydantic v2
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from textclf.logging_conf import setup_logging
from textclf.persistence import load_model, LATEST_PATH, STABLE_PATH
from textclf.model import predict as predict_labels # reuse wrapper

from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import cast

from limits.storage import RedisStorage

from importlib.metadata import version as pkg_version

PREDICTIONS = Counter("pred_requests_total", "Total prediction requests")
PRED_LATENCY = Histogram(
    "pred_latency_seconds",
    "Prediction latency (seconds)",
    # Checking more important percentiles
    buckets=(0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1.0)
)
PRED_ERRORS = Counter("pred_request_errors_total", "Total prediction errors")

# Optional: Redis-backed limits for distributed deployments
SLOWAPI_STORAGE_URI = os.getenv("SLOWAPI_STORAGE_URI")  # e.g., "redis://redis:6379/0"

def key_from_header(request):
    # Prefer API key if present; otherwise fall back to client IP
    return request.headers.get("x-api-key") or get_remote_address(request)

def rate_limit_handler(request: Request, exc: Exception):
    return _rate_limit_exceeded_handler(request, cast(RateLimitExceeded, exc))

# Optional: probabilities if your pipeline has predict_proba
def _predict_proba_safe(pipe, texts: List[str]) -> Optional[List[List[float]]]:
    if hasattr(pipe, "predict_proba"):
        try:
            probs = pipe.predict_proba(texts)
            return probs.tolist()  # type: ignore[no-any-return]
        except Exception:
            return None
    return None

# ----------- FastAPI app ----------
setup_logging()
log = logging.getLogger("textclf.api")

# Simple in-memory model state
class ModelState(BaseModel):
    # Keep Python attribute name 'path', but serialize as 'model_path'
    path: str = Field(..., serialization_alias="model_path")
    pointer: Literal["latest", "stable", "custom"]
    meta_version: Optional[str] = None
    meta_created_at: Optional[str] = None

    # allow population by field name even with aliases
    model_config = ConfigDict(populate_by_name=True)

STATE: dict = {"pipe": None, "meta": None, "state": None}

def _resolve_path(pointer: Literal["latest", "stable"] | None, explicit_path: Optional[str]) -> Tuple[str, Literal["latest", "stable", "custom"]]:
    # priority: explicit path > pointer > default (latest)
    env_pointer = os.getenv("MODEL_POINTER")    # "latest" | "stable"
    env_path = os.getenv("MODEL_PATH")          # explicit artifact path

    if explicit_path:
        return explicit_path, "custom"
    if pointer in ("latest", "stable"):
        return (str(LATEST_PATH) if pointer == "latest" else str(STABLE_PATH)), pointer
    if env_path:
        return env_path, "custom"
    if env_pointer == "stable":
        return str(STABLE_PATH), "stable"
    # default
    return str(LATEST_PATH), "latest"

def _load_into_state(pointer: Literal["latest", "stable"] | None = None, explicit_path: Optional[str] = None) -> None:
    path, resolved = _resolve_path(pointer, explicit_path)
    pipe, meta = load_model(path)
    STATE["pipe"] = pipe
    STATE["meta"] = meta
    STATE["state"] = ModelState(
        path=path,
        pointer=resolved,   # type: ignore[arg-type]
        meta_version=getattr(meta, "version", None),
        meta_created_at=getattr(meta, "created_at", None),
    )
    log.info(f"Loaded model pointer={resolved} path={path} version={STATE['state'].meta_version} created_at={STATE['state'].meta_created_at}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        _load_into_state()
    except FileNotFoundError:
        log.warning("No model found at startup; /predict will 503 until a model is mounted/promoted.")
    yield

MAX_TEXTS = int(os.getenv("MAX_TEXTS", "64"))
MAX_TEXT_LEN = int(os.getenv("MAX_TEXT_LEN", "2000"))

ENV = os.getenv("ENV", "local").lower()    # local | dev | prod
# ENV-based default
default_show_docs = "1" if ENV == "local" else "0"
# Explicit override
override_show_docs = os.getenv("SHOW_DOCS")  # No default since we are overriding

if override_show_docs is None:
    show_docs = default_show_docs
else:
    show_docs = override_show_docs.strip().lower() in {"1", "true", "yes", "on"}

log.info(
    "ENV=%s SHOW_DOCS=%r -> show_docs=%s",
    ENV, override_show_docs, show_docs
    )

app = FastAPI(
    title="textclf API",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if show_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if show_docs else None,
    )

# tighten this
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)

if SLOWAPI_STORAGE_URI:
    # Use shared backend only if configured
    limiter = Limiter(key_func=key_from_header, storage_uri=SLOWAPI_STORAGE_URI)
else:
    # Default to in-memory (no extra deps; fine for tests & single instance)
    limiter = Limiter(key_func=key_from_header)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


def limit_value():
    return os.getenv("RATE_LIMIT_PREDICT", "60/minute")

def limit_if_enabled_dynamic():
    def _wrap(fn):
        if os.getenv("RATE_LIMIT_ENABLED", "1") == "1":
            return limiter.limit(limit_value)(fn)  # pass callable
        return fn
    return _wrap

# ---------- Schemas ----------

class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")  # ignore unexpected keys (prevents 422)
    texts: List[str] = Field(...)
    return_prob: bool = False

class PredictResponse(BaseModel):
    labels: List[int]
    probabilities: Optional[List[List[float]]] = None
    model: dict

# Ensure models are fully built when using postponed annotations + Body(...)
try:
    PredictRequest.model_rebuild()
    PredictResponse.model_rebuild()
except Exception:
    pass

# ---------- Endpoints ----------
@app.get("/health")
def health() -> dict[str, Any]:
    st = STATE["state"]
    return {
        "status": "ok",
        "version": pkg_version("textclf"),
        "model": st.dict() if st else None,
    }

@app.get("/version")
def version() -> dict:
    st = STATE["state"]
    if st is None:
        return {
            "package_version": app.version,
            "model_version": None,
            "model_created_at": None,
            "model_pointer": None,
            "model_path": None,
        }
    return {
        "package_version": app.version,
        "model_version": st.meta_version,
        "model_created_at": st.meta_created_at,
        "model_pointer": st.pointer,
        "model_path": st.path,
    }

@app.get("/ready")
def ready():
    return {"ready": STATE["pipe"] is not None}

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/whoami")
def whoami():
    st = STATE.get("state")
    return {
        "pointer": getattr(st, "pointer", None),
        "model_path": getattr(st, "path", None),
        "model_version": getattr(st, "meta_version", None),
        "model_created_at": getattr(st, "meta_created_at", None),
        "package_version": app.version,
    }

@limit_if_enabled_dynamic()
@app.post("/predict", response_model=PredictResponse)
def predict(
    request: Request,   # REQUIRED for SlowAPI
    payload: dict = Body(...),
    model: Optional[Literal["latest", "stable"]] = Query(
        default=None, description='Override which model pointer to use ("latest" or "stable").'
    ),
    model_path: Optional[str] = Query(
        default=None, description="Explicit artifact path (overrides 'model')."
    ),
) -> PredictResponse:
    body = PredictRequest.model_validate(payload)
    start = time.perf_counter()
    try:
        # Resolve desired model and (re)load if needed
        desired_path, _ = _resolve_path(model, model_path)
        st = STATE["state"]
        if STATE["pipe"] is None or st is None or st.path != desired_path:
            try:
                _load_into_state(model, model_path)
            except FileNotFoundError:
                PRED_ERRORS.inc()
                raise HTTPException(status_code=404, detail=f"Model file not found: {desired_path}")

        # Validate inputs
        if not body.texts:
            PRED_ERRORS.inc()
            raise HTTPException(status_code=422, detail="No texts provided.")
        if len(body.texts) > MAX_TEXTS:
            PRED_ERRORS.inc()
            raise HTTPException(status_code=413, detail=f"Too many texts; max is {MAX_TEXTS}.")
        too_long = [t for t in body.texts if len(t) > MAX_TEXT_LEN]
        if too_long:
            PRED_ERRORS.inc()
            raise HTTPException(status_code=413, detail=f"Some texts exceed {MAX_TEXT_LEN} characters.")

        # Predict
        pipe = STATE["pipe"]
        labels = predict_labels(pipe, body.texts)
        probs = _predict_proba_safe(pipe, body.texts) if body.return_prob else None

        # Record successful prediction
        PREDICTIONS.inc()

        model_dict = STATE["state"].model_dump(by_alias=True)  # pydantic v2: serialize with aliases
        return PredictResponse(labels=labels, probabilities=probs, model=model_dict)
    except Exception:
        # catch unexpected exceptions too
        PRED_ERRORS.inc()
        raise
    finally:
        PRED_LATENCY.observe(time.perf_counter() - start)