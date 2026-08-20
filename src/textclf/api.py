from __future__ import annotations

from textclf import __version__

import hashlib
import secrets
import json
import logging
import os
import re
import time
import uuid

from ipaddress import ip_address, ip_network
from typing import Any, Callable, List, Optional, Tuple, cast

from contextlib import asynccontextmanager
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from pydantic import ConfigDict  # pydantic v2
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)
from prometheus_client.core import GaugeMetricFamily
from collections.abc import Iterable

from prometheus_client.metrics_core import Metric
from prometheus_client.registry import Collector

from textclf.logging_conf import setup_logging
from textclf.persistence import load_model, LATEST_PATH, STABLE_PATH, _pkg_version, _resolve_pointer_path, ARTIFACTS_DIR
from textclf.list_models import load_model_registry
from textclf.model import predict as predict_labels

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from limits.storage import RedisStorage

from importlib.metadata import version as pkg_version
from pathlib import Path
from datetime import datetime, timezone

from fastapi.responses import JSONResponse

from textclf.token_audit import (
    DEFAULT_WARNING_DAYS,
    audit_registry,
    load_registry,
    utc_now,
)

PREDICTIONS = Counter("prediction_requests_total", "Total prediction requests")
PREDICTION_LATENCY = Histogram(
    "prediction_latency_seconds",
    "Prediction latency (seconds)",
    # Checking more important percentiles
    buckets=(0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1.0)
)
PREDICTION_ERRORS = Counter("prediction_request_errors_total", "Total prediction errors")

# Optional: Redis-backed limits for distributed deployments
SLOWAPI_STORAGE_URI = os.getenv("SLOWAPI_STORAGE_URI")  # e.g., "redis://redis:6379/0"

def _env_variable_enabled(value: Optional[str], default: bool = False) -> bool:
    """
    An affirmation check for environment variables.
    \nIs this environment variable enabled?.
    """
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Principal(BaseModel):
    subject: str
    client_id: str
    scopes: List[str]
    auth_method: str
    token_id: Optional[str] = None


class TokenRecord(BaseModel):
    token_id: str
    subject: str
    client_id: str
    scopes: List[str]
    active: bool = True
    token_hash: str
    issued_at: Optional[str] = None
    expires_at: Optional[str] = None
    revoked_at: Optional[str] = None
    replaces: Optional[str] = None
    replaced_by: Optional[str] = None
    rotation_group: Optional[str] = None


AUTH_ENABLED = _env_variable_enabled(os.getenv("AUTH_ENABLED"), default=True)
AUTH_TOKENS_FILE = os.getenv("AUTH_TOKENS_FILE")

class TokenAuditCollector(Collector):
    def collect(self) -> Iterable[Metric]:
        registry_valid = GaugeMetricFamily(
            "textclf_token_registry_valid",
            "Whether the token registry passed validation.",
        )

        active_expired = GaugeMetricFamily(
            "textclf_token_active_expired_total",
            "Active tokens that have expired.",
        )

        active_warning = GaugeMetricFamily(
            "textclf_token_active_warning_total",
            "Active tokens inside an expiry warning window.",
        )

        days_remaining = GaugeMetricFamily(
            "textclf_token_days_remaining",
            "Remaining token lifetime in days.",
            labels=[
                "token_id",
                "client_id",
                "rotation_group",
            ],
        )

        if not AUTH_TOKENS_FILE:
            registry_valid.add_metric([], 0)
            active_expired.add_metric([], 0)
            active_warning.add_metric([], 0)

            yield registry_valid
            yield active_expired
            yield active_warning
            yield days_remaining
            return

        try:
            registry = load_registry(Path(AUTH_TOKENS_FILE))

            errors, _, statuses = audit_registry(
                registry,
                now=utc_now(),
                warning_days=list(DEFAULT_WARNING_DAYS),
            )

            expired_count = sum(
                1
                for status in statuses
                if status["active"]
                and not status["revoked"]
                and status["expired"]
            )

            warning_count = sum(
                1
                for status in statuses
                if status["active"]
                and not status["revoked"]
                and not status["expired"]
                and status["days_remaining"] <= max(DEFAULT_WARNING_DAYS)
            )

            registry_valid.add_metric(
                [],
                0 if errors else 1,
            )

            active_expired.add_metric(
                [],
                expired_count,
            )

            active_warning.add_metric(
                [],
                warning_count,
            )

            for status in statuses:
                if (
                    status["active"]
                    and not status["revoked"]
                    and not status["expired"]
                ):
                    days_remaining.add_metric(
                        [
                            str(status["token_id"]),
                            str(status["client_id"]),
                            str(status["rotation_group"]),
                        ],
                        float(status["days_remaining"]),
                    )

        except Exception:
            log.exception(
                "Token audit metrics collection failed"
            )

            registry_valid.add_metric([], 0)
            active_expired.add_metric([], 0)
            active_warning.add_metric([], 0)

        yield registry_valid
        yield active_expired
        yield active_warning
        yield days_remaining

TRUST_PROXY_HEADERS = _env_variable_enabled(os.getenv("TRUST_PROXY_HEADERS"), default=False)
INTERNAL_ONLY_ENABLED = _env_variable_enabled(os.getenv("INTERNAL_ONLY_ENABLED"), default=True)
# Add internal networks ...
INTERNAL_NETWORKS = [
    ip_network(value.strip())
    for value in os.getenv(
        "INTERNAL_NETWORKS",
        "127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
    ).split(",")
    if value.strip()
]
http_bearer = HTTPBearer(auto_error=False)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _load_token_records() -> List[TokenRecord]:
    if not AUTH_TOKENS_FILE:
        raise ValueError("AUTH_TOKENS_FILE must be configured")

    with open(AUTH_TOKENS_FILE, "r", encoding="utf-8") as handle:
        payload: Any = json.load(handle)

    if isinstance(payload, dict):
        payload = payload.get("tokens", [])
    if not isinstance(payload, list):
        raise ValueError("AUTH_TOKENS_FILE must define a list of token records")

    return [TokenRecord.model_validate(item) for item in payload]


def _token_records() -> List[TokenRecord]:
    try:
        return _load_token_records()
    except FileNotFoundError:
        log.exception("AUTH_TOKENS_FILE was configured but the file was not found")
        return []
    except json.JSONDecodeError:
        log.exception("Failed to parse auth token configuration")
        return []
    except ValueError:
        log.exception("Invalid auth token configuration")
        return []


def _token_is_usable(record: TokenRecord) -> bool:
    if not record.active:
        return False
    if record.revoked_at:
        return False
    if record.expires_at:
        try:
            expires_at = record.expires_at.replace("Z", "+00:00")
            if datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc):
                return False
        except ValueError:
            return False
    return True


def _find_token_record(presented_token: str) -> Optional[TokenRecord]:
    hashed = _hash_token(presented_token)
    for record in _token_records():
        expected = record.token_hash.removeprefix("sha256:")
        if secrets.compare_digest(expected, hashed):
            return record
    return None


def _extract_client_ip(request: Request) -> str:
    if TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


def _is_internal_request(request: Request) -> bool:
    candidate = _extract_client_ip(request)
    try:
        parsed_ip = ip_address(candidate)
    except ValueError:
        return False
    return any(parsed_ip in network for network in INTERNAL_NETWORKS)


def key_from_header(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        presented_token = auth_header.split(" ", 1)[1].strip()
        record = _find_token_record(presented_token)
        if record and _token_is_usable(record):
            return record.client_id

    return request.headers.get("x-api-key") or _extract_client_ip(request)


def rate_limit_handler(request: Request, exc: Exception) -> Response:
    return _rate_limit_exceeded_handler(request, cast(RateLimitExceeded, exc))


def _principal_from_credentials(
    credentials: Optional[HTTPAuthorizationCredentials],
    request: Request,
) -> Principal:
    if not AUTH_ENABLED:
        principal = Principal(
            subject="anonymous-dev",
            client_id="anonymous-dev",
            scopes=["predict:run", "models:read", "version:read", "whoami:read"],
            auth_method="disabled",
            token_id=None,
        )
        request.state.principal = principal
        return principal

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not _token_records():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured; set AUTH_TOKENS_FILE",
        )

    record = _find_token_record(credentials.credentials)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not _token_is_usable(record):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired or revoked bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    principal = Principal(
        subject=record.subject,
        client_id=record.client_id,
        scopes=record.scopes,
        auth_method="bearer",
        token_id=record.token_id,
    )
    request.state.principal = principal
    log.info(
        "Authentication succeeded token_id=%s client_id=%s request_id=%s",
        principal.token_id,
        principal.client_id,
        getattr(request.state, "request_id", None),
    )
    return principal


def require_scopes(*required_scopes: str) -> Callable[..., Principal]:
    def _dependency(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    ) -> Principal:
        principal = _principal_from_credentials(credentials, request)
        missing = [scope for scope in required_scopes if scope not in principal.scopes]
        if missing:
            log.warning(
                "Authorization failed token_id=%s client_id=%s missing_scopes=%s request_id=%s",
                principal.token_id,
                principal.client_id,
                ",".join(missing),
                getattr(request.state, "request_id", None),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope(s): {', '.join(missing)}",
            )
        return principal

    return _dependency


def enforce_internal_only(request: Request) -> None:
    if INTERNAL_ONLY_ENABLED and not _is_internal_request(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Internal access only")

# Optional: probabilities if your pipeline has predict_proba
def _predict_probabilities_safe(pipe: Any, texts: List[str]) -> Optional[List[List[float]]]:
    if hasattr(pipe, "predict_proba"):
        try:
            probabilities = pipe.predict_proba(texts)
            return probabilities.tolist()
        except Exception:
            return None
    return None

# ----------- FastAPI app ----------
setup_logging()
log = logging.getLogger("textclf.api")

# Registering token auditer
REGISTRY.register(TokenAuditCollector())

# Simple in-memory model state
class ModelState(BaseModel):
    # Keep Python attribute name 'path', but serialize as 'model_path'
    path: str = Field(..., serialization_alias="model_path")
    pointer: str
    # Model identity (immutable per build). NOTE: kept variations for backward-compatibility.
    meta_version: Optional[str] = None  # Now holds model_id / previously software version
    meta_created_at: Optional[str] = None # New key
    meta_software_version: Optional[str] = None # Previously meta_version
    meta_release_tag: Optional[str] = None # New key
    meta_published: bool = False # New key

    # Allow population by field name even with aliases
    model_config = ConfigDict(populate_by_name=True)

STATE: dict = {"pipe": None, "meta": None, "state": None}

def _resolve_path(model_selector: Optional[str], explicit_path: Optional[str]) -> Tuple[str, str]:
    """Resolve the correct path to the selected artifact.

    Supported selectors:
    - "latest" / "stable" -> resolve via pointers.json
    - absolute path -> use directly
    - relative artifact filename (e.g. model_x.joblib) -> ARTIFACTS_DIR / filename
    - model_id -> look up the artifact in the registry returned by load_model_registry()

    The second returned value is the logical selector label used for reporting.
    """

    env_pointer = os.getenv("MODEL_POINTER")
    env_path = os.getenv("MODEL_PATH")

    if explicit_path:
        return explicit_path, "custom"

    selector = model_selector.strip() if isinstance(model_selector, str) else None

    if selector in ("latest", "stable"):
        resolved = _resolve_pointer_path(selector)
        return str(resolved), selector

    if selector:
        _path = Path(selector)

        if _path.is_absolute():
            return str(_path), "custom"

        candidate = ARTIFACTS_DIR / _path
        if candidate.exists():
            return str(candidate), selector

        if selector.endswith(".joblib"):
            candidate = ARTIFACTS_DIR / selector
            if candidate.exists():
                return str(candidate), selector

        for record in load_model_registry():
            if record.get("model_id") == selector:
                artifact = record.get("artifact")
                if artifact:
                    return str(artifact), selector

        raise FileNotFoundError(f"Model selector not found: {selector}")

    if env_path:
        return env_path, "custom"

    if env_pointer:
        if env_pointer in ("latest", "stable"):
            resolved = _resolve_pointer_path(env_pointer)
            return str(resolved), env_pointer
        return env_pointer, "custom"

    resolved = _resolve_pointer_path("latest")
    return str(resolved), "latest"


def _load_into_state(pointer: Optional[str] = None, explicit_path: Optional[str] = None) -> None:
    path, resolved = _resolve_path(pointer, explicit_path)
    pipe, meta = load_model(path)
    STATE["pipe"] = pipe
    STATE["meta"] = meta
    # persistence.ModelMetadata now provides model_id + software_version
    STATE["state"] = ModelState(
        path=path,
        pointer=resolved,
        meta_version=getattr(meta, "model_id", None) or getattr(meta, "version", None),
        meta_created_at=getattr(meta, "created_at", None),
        meta_software_version=getattr(meta, "software_version", None) or _pkg_version(),
        meta_release_tag=getattr(meta, "release_tag", "unreleased"),
        meta_published=bool(getattr(meta, "published", False)),
    )
    log.info(
        "Loaded model pointer=%s path=%s model_id=%s created_at=%s software_version=%s release_tag=%s published=%s",
        resolved,
        path,
        STATE["state"].meta_version,
        STATE["state"].meta_created_at,
        STATE["state"].meta_software_version,
        STATE["state"].meta_release_tag,
        STATE["state"].meta_published,
    )

def _model_state_from_artifact_path(path: str, resolved: str) -> ModelState:
    """Load metadata for a specific resolved artifact path without mutating global STATE."""
    _, meta = load_model(path)
    return ModelState(
        path=path,
        pointer=resolved,
        meta_version=getattr(meta, "model_id", None) or getattr(meta, "version", None),
        meta_created_at=getattr(meta, "created_at", None),
        meta_software_version=getattr(meta, "software_version", None) or _pkg_version(),
        meta_release_tag=getattr(meta, "release_tag", "unreleased"),
        meta_published=bool(getattr(meta, "published", False)),
    )

@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    try:
        _load_into_state()
    except FileNotFoundError:
        log.warning("No model found at startup; /predict will 503 until a model is mounted/promoted.")
    yield

MAX_TEXTS = int(os.getenv("MAX_TEXTS", "64"))
MAX_TEXT_LEN = int(os.getenv("MAX_TEXT_LEN", "2000"))

ENV = os.getenv("ENV", "local").lower()    # local | dev | prod
# ENV-based default
default_show_docs = ENV == "local"
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


REQUEST_ID_MAX_LEN = 128
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]+$")


def _is_request_id_valid(value: str) -> bool:
    return 0 < len(value) <= REQUEST_ID_MAX_LEN and bool(REQUEST_ID_PATTERN.fullmatch(value))


def _resolve_request_id(request: Request) -> tuple[str, bool]:
    """Resolve a safe request correlation ID."""
    incoming = request.headers.get("X-Request-ID")
    if incoming:
        candidate = incoming.strip()
        if _is_request_id_valid(candidate):
            return candidate, True

    return str(uuid.uuid4()), False


@app.middleware("http")
async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Any],
) -> Response:
    request_id, request_id_from_client = _resolve_request_id(request)
    request.state.request_id = request_id
    request.state.request_id_from_client = request_id_from_client
    request.state.principal = None

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    response.headers["X-Request-ID"] = request_id

    log.info(
        "HTTP request completed. method=%s path=%s status_code=%s duration_ms=%.2f request_id=%s request_id_source=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
        "client" if request_id_from_client else "api",
    )

    return response

# tighten this
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # fallback should never happen — middleware always sets request_id
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    log.exception("Unhandled exception request_id=%s", request_id)

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers={"X-Request-ID": request_id},
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


def limit_value() -> str:
    return os.getenv("RATE_LIMIT_PREDICT", "60/minute")

def limit_if_enabled_dynamic() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        if os.getenv("RATE_LIMIT_ENABLED", "1") == "1":
            return limiter.limit(limit_value)(fn)
        return fn
    return _wrap

# ---------- Schemas ----------

class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")  # ignore unexpected keys (prevents 422)
    texts: List[str] = Field(...)
    return_probabilities: bool = False

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
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/details")
def health_details(request: Request) -> dict[str, Any]:
    enforce_internal_only(request)
    state = STATE["state"]
    return {
        "status": "ok",
        "version": pkg_version("textclf"),
        "model": state.model_dump(by_alias=True) if state else None,
    }


@app.get("/ready")
def ready() -> dict[str, bool]:
    return {"ready": STATE["pipe"] is not None}


@app.get("/version")
def version(
    model: Optional[str] = Query(
        default=None,
        description='Resolve metadata for a specific selector: pointer ("latest"/"stable"), model_id, or artifact filename.',
    ),
    model_path: Optional[str] = Query(
        default=None, description="Explicit artifact path (overrides 'model')."
    ),
    principal: Principal = Depends(require_scopes("version:read")),
) -> dict:
    try:
        path, resolved = _resolve_path(model, model_path)
        state = _model_state_from_artifact_path(path, resolved)
    except FileNotFoundError:
        return {
            "package_version": app.version,
            "model_version": None,
            "model_id": None,
            "software_version": None,
            "release_tag": None,
            "published": None,
            "model_created_at": None,
            "model_pointer": None,
            "model_path": None,
        }

    return {
        "package_version": app.version,
        # Backwards-compatible keys for UIs
        "model_version": state.meta_version,
        "model_id": state.meta_version,
        "software_version": state.meta_software_version,
        "release_tag": state.meta_release_tag,
        "published": state.meta_published,
        "model_created_at": state.meta_created_at,
        "model_pointer": state.pointer,
        "model_path": state.path,
    }


@app.get("/whoami")
def whoami(principal: Principal = Depends(require_scopes("whoami:read"))) -> dict[str, Any]:
    state = STATE.get("state")
    return {
        "principal": principal.model_dump(),
        "pointer": getattr(state, "pointer", None),
        "model_path": getattr(state, "path", None),
        "model_version": getattr(state, "meta_version", None),
        "version": getattr(state, "meta_version", None),
        "model_id": getattr(state, "meta_version", None),
        "software_version": getattr(state, "meta_software_version", None),
        "release_tag": getattr(state, "meta_release_tag", None),
        "published": getattr(state, "meta_published", False),
        "model_created_at": getattr(state, "meta_created_at", None),
        "package_version": app.version,
    }


@app.get("/models")
def models(principal: Principal = Depends(require_scopes("models:read"))) -> dict[str, Any]:
    return {"models": load_model_registry()}


@app.get("/metrics")
def metrics(request: Request) -> Response:
    enforce_internal_only(request)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@limit_if_enabled_dynamic()
@app.post("/predict", response_model=PredictResponse)
def predict(
    request: Request,
    payload: PredictRequest,
    model: Optional[str] = Query(
        default=None,
        description='Model selector: pointer ("latest"/"stable"), model_id, or artifact filename.',
    ),
    model_path: Optional[str] = Query(
        default=None, description="Explicit artifact path (overrides 'model')."
    ),
    principal: Principal = Depends(require_scopes("predict:run")),
) -> PredictResponse:
    start = time.perf_counter()
    # Accumulate all errors together--server/client... enough for now.
    try:
        # Resolve desired model and (re)load if needed
        try:
            desired_path, _ = _resolve_path(model, model_path)
        except FileNotFoundError as e:
            PREDICTION_ERRORS.inc()
            raise HTTPException(status_code=404, detail=str(e))

        state = STATE["state"]
        if STATE["pipe"] is None or state is None or state.path != desired_path:
            try:
                _load_into_state(model, model_path)
            except FileNotFoundError as e:
                PREDICTION_ERRORS.inc()
                raise HTTPException(status_code=404, detail=str(e))

        # Validate inputs
        if not payload.texts:
            PREDICTION_ERRORS.inc()
            raise HTTPException(status_code=422, detail="No texts provided.")
        if len(payload.texts) > MAX_TEXTS:
            PREDICTION_ERRORS.inc()
            raise HTTPException(status_code=413, detail=f"Too many texts; max is {MAX_TEXTS}.")
        too_long = [text for text in payload.texts if len(text) > MAX_TEXT_LEN]
        if too_long:
            PREDICTION_ERRORS.inc()
            raise HTTPException(status_code=413, detail=f"Some texts exceed {MAX_TEXT_LEN} characters.")

        # Predict
        pipe = STATE["pipe"]
        labels = predict_labels(pipe, payload.texts)
        _probabilities = (
            _predict_probabilities_safe(pipe, payload.texts)
            if payload.return_probabilities
            else None
        )

        # Record successful prediction
        PREDICTIONS.inc()
        log.info(
            "Prediction succeeded token_id=%s client_id=%s texts=%s request_id=%s",
            principal.token_id,
            principal.client_id,
            len(payload.texts),
            getattr(request.state, "request_id", None),
        )

        model_dict = STATE["state"].model_dump(by_alias=True)  # pydantic v2: serialize with aliases

        # Provide version fields under common keys used by UIs/clients
        meta_version = model_dict.get("meta_version")
        if meta_version:
            # Backwards-compatible keys: treat model_id as the model "version" in the UI
            model_dict["model_version"] = meta_version
            model_dict["version"] = meta_version
            model_dict["model_id"] = meta_version

        software_version = model_dict.get("meta_software_version")
        if software_version:
            model_dict["software_version"] = software_version

        release_tag = model_dict.get("meta_release_tag")
        if release_tag is not None:
            model_dict["release_tag"] = release_tag

        model_dict["published"] = bool(model_dict.get("meta_published", False))

        created_at = model_dict.get("meta_created_at")
        if created_at:
            model_dict["created_at"] = created_at

        # Also include the resolved pointer explicitly (stable/latest/custom)
        model_dict["pointer"] = model_dict.get("pointer")

        return PredictResponse(labels=labels, probabilities=_probabilities, model=model_dict)    
    except Exception:
        # catch unexpected exceptions too
        PREDICTION_ERRORS.inc()
        log.exception(
            "Prediction failed request_id=%s client_id=%s",
            getattr(request.state, "request_id", None),
            getattr(principal, "client_id", None),
        )
        raise
    finally:
        PREDICTION_LATENCY.observe(time.perf_counter() - start)