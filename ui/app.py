import os
from pathlib import Path
import base64
import textwrap
import time
from typing import Any, Optional

from dataclasses import dataclass
from urllib.parse import urlparse
import re

import requests
import streamlit as st
import pandas as pd

import io


st.set_page_config(
    page_title="Text Classification Inference Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----- Styling (Streamlit CSS overrides) -----
st.markdown(
    """
<style>
/* ----- Design tokens ----- */
:root {
  --radius: 14px;
  --radius-sm: 10px;
  --accent: #2563EB;
  --accent2: #3B82F6;
}

@media (prefers-color-scheme: light) {
  :root {
    --bg: #F6F8FC;
    --bg-grad1: rgba(37,99,235,0.05);
    --bg-grad2: rgba(59,130,246,0.04);

    --text: #0F172A;
    --muted: #475569;

    --surface: #FFFFFF;
    --surface2: rgba(2,6,23,0.03);

    --border: rgba(15,23,42,0.12);
    --border2: rgba(15,23,42,0.10);

    --input-bg: #FFFFFF;
    --input-border: rgba(15,23,42,0.16);
    
    --sidebar-bg: #F9FAFB;
    --sidebar-surface: #FFFFFF;
    --shadow: 0 10px 28px rgba(2,6,23,0.06);
  }
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0B1220;
    --bg-grad1: rgba(37,99,235,0.14);
    --bg-grad2: rgba(59,130,246,0.10);

    --text: #F9FAFB;
    --muted: #9CA3AF;

    --surface: rgba(17,24,39,0.78);
    --surface2: rgba(255,255,255,0.05);

    --border: rgba(255,255,255,0.12);
    --border2: rgba(255,255,255,0.10);

    --input-bg: rgba(15,23,42,0.55);
    --input-border: rgba(255,255,255,0.14);

    --sidebar-bg: rgba(11,18,32,0.92);
    --sidebar-surface: rgba(17,24,39,0.78);
    --shadow: 0 12px 34px rgba(0,0,0,0.22);
  }
}

/* ----- App background ----- */
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(900px 520px at 25% 0%, var(--bg-grad1), transparent 62%),
    radial-gradient(820px 520px at 85% 18%, var(--bg-grad2), transparent 62%),
    var(--bg);
  color: var(--text);
}

[data-testid="stMain"] { background: transparent; padding-top: 1rem; }
.ui-wrap { max-width: 1200px; margin: 0 auto; }

/* ----- Typography ----- */
h1,h2,h3,h4,h5,h6 { color: var(--text) !important; font-weight: 700 !important; }
h1 { font-size: 28px !important; }
.stMarkdown, .stMarkdown p, .stText { color: var(--text) !important; }
.ui-muted, .stCaption { color: var(--muted) !important; }
label, [data-testid="stWidgetLabel"] { color: var(--text) !important; }

/* ----- Hide Streamlit chrome (safe) ----- */
#MainMenu, footer { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

/* Keep Streamlit’s default header/toolbar so sidebar toggle works across versions */
[data-testid="stHeader"] { background: transparent !important; }



/* ----- Sidebar ----- */
[data-testid="stSidebar"] {
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border2);
  box-shadow: 10px 0 30px rgba(2,6,23,0.04);
}

[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
  padding-top: 1.25rem;
}

.ui-side-title {
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted) !important;
  margin-top: 0.8rem;
  margin-bottom: 0.35rem;
}

/* Brand links in sidebar */
.github-linkButton, .linkedin-linkButton {
  display: block;
  width: 100%;
  text-decoration: none;
  padding: 10px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--sidebar-surface);
  margin-bottom: 10px;
}

.github-linkButton:hover, .linkedin-linkButton:hover {
  filter: brightness(0.985);
}

.github-icon, .linkedin-icon {
  display: block;
  width: min(200px, 100%);
  height: auto;
  margin: 0 auto;
  opacity: 0.95;
}

/* ----- Cards (border=True containers) ----- */
div[data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  padding: 16px !important;
  background: var(--surface) !important;
  box-shadow: var(--shadow);
}

/* ----- Status strip ----- */
.ui-status {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
  margin-bottom: 1.2rem;
}

.ui-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 650;
  border: 1px solid var(--border);
  background: var(--surface2);
  color: var(--text);
  margin-right: 8px;
  margin-bottom: 8px;
}

/* ----- Inputs ----- */
input, textarea {
  border-radius: var(--radius-sm) !important;
  background: var(--input-bg) !important;
  color: var(--text) !important;
  border: 1px solid var(--input-border) !important;
}

[data-baseweb="select"] > div {
  border-radius: var(--radius-sm) !important;
  background: var(--input-bg) !important;
  border: 1px solid var(--input-border) !important;
  color: var(--text) !important;
}

/* ----- Primary button ----- */
div[data-testid="stButton"] button[kind="primary"] {
  background: linear-gradient(90deg, var(--accent), var(--accent2)) !important;
  border: none !important;
  font-weight: 700 !important;
  border-radius: var(--radius-sm) !important;
  height: 44px;
}
div[data-testid="stButton"] button:disabled { opacity: 0.58; }

/* ----- Link buttons (endpoints) ----- */
a[data-testid="stLinkButton"] {
  border-radius: var(--radius-sm) !important;
  border: 1px solid var(--border) !important;
  background: var(--surface) !important;
  color: var(--text) !important;
  font-weight: 600 !important;
}

a[data-testid="stLinkButton"]:hover {
  background: var(--surface2) !important;
}

/* ----- Expanders ----- */
details {
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface);
}
details summary { color: var(--text); }

/* ----- Alerts ----- */
[data-testid="stAlert"] {
  border-radius: 12px;
  border: 1px solid var(--border);
}
</style>
    """,
    unsafe_allow_html=True,
)

IMAGE_PATH: Path = Path(os.getenv("IMAGE_PATH", "img"))

GITHUB_ICON_BLACK: Path = IMAGE_PATH / "GitHub Logos" / "SVG" / "GitHub_Lockup_Black_Clearspace.svg"
GITHUB_ICON_WHITE: Path = IMAGE_PATH / "GitHub Logos" / "SVG" / "GitHub_Lockup_White_Clearspace.svg"
LINKEDIN_ICON: Path = IMAGE_PATH / "linkedin-logo" / "LI-Logo.png"

def _svg_as_data_uri(path: Path) -> str:
    svg_bytes = path.read_bytes()
    b64 = base64.b64encode(svg_bytes).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"

def _png_as_data_uri(path: Path) -> str:
    png_bytes = path.read_bytes()
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"

# ----- Personalisation -----
APP_TITLE = "Text Classification Inference Platform"
APP_SUBTITLE = "Built by Sepanta Kamali • Artificial Intelligence Engineer"


LINKS = {
    "github": "https://github.com/sepantakamali/",
    "linkedin": "https://www.linkedin.com/in/sepanta-kamali-ab71691b6",
    "grafana": os.getenv("GRAFANA_DASHBOARD_URL", "").strip(),
}

# ----- UX Config -----

LABEL_MAP: dict[int, str] = {
    0: "Hockey / Sports",
    1: "Middle East Politics",
}

LABEL_ICON: dict[int, str] = {
    0: "🏒🥅",
    1: "🤝🌍",
}


@dataclass(frozen=True)
class APIStatus:
    ok: bool
    status_code: Optional[int] = None
    detail: Optional[str] = None
    url: Optional[str] = None


def _default_api_base_url() -> str:
    # Local dev default; on Render set API_BASE_URL to your API service URL
    return os.getenv("API_BASE_URL", "http://localhost:8000").strip().rstrip("/")


def _default_api_bearer_token() -> str:
    token_file = os.getenv("API_BEARER_TOKEN_FILE", "").strip()
    if token_file:
        try:
            return Path(token_file).read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return os.getenv("API_BEARER_TOKEN", "").strip()


def _normalise_base_url(raw: str) -> str:
    """
    Normalise user input into a safe base URL.

    - Strips whitespace
    - If scheme is missing, assumes https:// (local http://)
    - Removes trailing '/'

    """
    address = (raw or "").strip()
    if not address:
        return ""

    # If user didn't provide a scheme, assume https:// (but keep localhost on http://)
    if not re.search(r"^https?://", address):
        is_local = address.startswith("localhost") or address.startswith("127.")
        address = ("http://" if is_local else "https://") + address

    parsed = urlparse(address)

    # If URL scheme or host is invalid, return empty string
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _get_session() -> requests.Session:
    if "http" not in st.session_state:
        st.session_state["http"] = requests.Session()
    return st.session_state["http"]


def _auth_headers(api_bearer_token: str = "") -> dict[str, str]:
    token = api_bearer_token.strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


@st.cache_data(ttl=5)
def _check_health(api_base_url: str, api_bearer_token: str = "") -> APIStatus:
    """
    Lightweight liveness check (cached for a few seconds).
    """
    if not api_base_url:
        return APIStatus(ok=False, detail="Empty base URL")

    url = f"{api_base_url}/health"
    try:
        session = _get_session()
        handshake = session.get(url, headers=_auth_headers(api_bearer_token), timeout=5)
        if handshake.status_code != 200:
            return APIStatus(ok=False, status_code=handshake.status_code, detail=handshake.text[:500], url=url)
        # FastAPI health in this project returns: {"status": "ok"}
        try:
            data = handshake.json()
            if isinstance(data, dict) and data.get("status") == "ok":
                return APIStatus(ok=True, status_code=200, url=url)
        except Exception:
            pass
        return APIStatus(ok=True, status_code=200, url=url)
    except requests.RequestException as e:
        return APIStatus(ok=False, detail=str(e), url=url)


@st.cache_data(ttl=10)
def _model_info(api_base_url: str, model: Optional[str] = None, api_bearer_token: str = "") -> Optional[dict[str, Any]]:
    """Return pointer-specific model metadata from /version."""
    if not api_base_url:
        return None

    url = f"{api_base_url}/version"
    params = {"model": model} if model else None

    try:
        session = _get_session()
        response = session.get(url, params=params, headers=_auth_headers(api_bearer_token), timeout=5)
        if response.status_code != 200:
            return None

        data = response.json()
        if not isinstance(data, dict):
            return None

        model_id = data.get("model_id") or data.get("model_version") or data.get("version")
        pointer = data.get("model_pointer") or model
        release_tag = data.get("release_tag") or "unreleased"
        published = bool(data.get("published", False))
        software_version = data.get("software_version")
        created_at = data.get("model_created_at")
        model_path = data.get("model_path")

        return {
            "model_id": str(model_id) if model_id else None,
            "model_pointer": str(pointer) if pointer else None,
            "release_tag": str(release_tag) if release_tag else "unreleased",
            "published": published,
            "software_version": str(software_version) if software_version else None,
            "created_at": str(created_at) if created_at else None,
            "model_path": str(model_path) if model_path else None,
        }
    except Exception:
        return None


# ----- Published models registry loader -----
@st.cache_data(ttl=10)
def _models_registry(api_base_url: str, api_bearer_token: str = "") -> list[dict[str, Any]]:
    """Fetch published model registry records from /models."""
    if not api_base_url:
        return []
    try:
        session = _get_session()
        _request = session.get(f"{api_base_url}/models", headers=_auth_headers(api_bearer_token), timeout=5)
        if _request.status_code != 200:
            return []
        data = _request.json()
        if not isinstance(data, dict):
            return []
        models = data.get("models")
        return models if isinstance(models, list) else []
    except Exception:
        return []


def _safe_json_detail(response: requests.Response) -> Optional[str]:
    """
    Extract FastAPI-style error detail if present.
    """
    try:
        data = response.json()
        if isinstance(data, dict):
            detail = data.get("detail")
            if isinstance(detail, str):
                return detail
            if detail is not None:
                return str(detail)
    except Exception:
        return None
    return None

def _summarise_connection_error(detail: Optional[str]) -> str:
    """Return a short, user-friendly connection error string."""
    if not detail:
        return "Connection error"

    content = str(detail)
    lowercased = content.lower()

    if "connection refused" in lowercased:
        return "Connection refused"
    if "name or service not known" in lowercased or "nodename nor servname provided" in lowercased:
        return "DNS lookup failed"
    if "timed out" in lowercased:
        return "Request timed out"
    if "max retries exceeded" in lowercased:
        return "Max retries exceeded"

    return (content[:120] + "…") if len(content) > 120 else content


def _model_compact(pointer: Optional[str], release_tag: Optional[str]) -> str:
    pointer = (pointer or "").strip()
    release_tag = (release_tag or "").strip() or "unreleased"
    if pointer and release_tag:
        return f"{pointer}:{release_tag}"
    return "-"


def _validate_predict_response(data: Any) -> tuple[list[int], Any, dict[str, Any]]:
    """
    Validate /predict response shape.

    Expected:
    - Labels: List[int]
    - probabilities: Optional
    - model: dict
    """
    if not isinstance(data, dict):
        raise ValueError("API schema mismatch: response is not a dict object")
    
    if "labels" not in data:
        raise ValueError("API schema mismatch: missing 'labels'")
    
    labels = data["labels"]
    if not isinstance(labels, list) or any(not isinstance(x, int) for x in labels):
        raise ValueError("API schema mismatch: 'labels' must be list[int]")
    
    model_info = data.get("model")
    if model_info is None:
        model_info = {}
    if not isinstance(model_info, dict):
        raise ValueError("API schema mismatch: 'model' must be a dict object")
    
    probabilities = data.get("probabilities")
    return labels, probabilities, model_info


def _post_predict(
        api_base_url: str,
        api_bearer_token: str,
        texts: list[str],
        return_probabilities: bool,
        model: str
        ) -> dict[str, Any]:
    url = f"{api_base_url}/predict"
    params = {"model": model} if model else None
    payload = {"texts": texts, "return_probabilities": return_probabilities}

    session = _get_session()
    response = session.post(url, params=params, json=payload, headers=_auth_headers(api_bearer_token), timeout=15)
    
    if not response.ok:
        detail = _safe_json_detail(response)
        request_id = response.headers.get("X-Request-ID")
        message = f"HTTP {response.status_code} from {response.url}"
        if detail:
            message += f"\nDetail: {detail}"
        if request_id:
            message += f"\nRequest-ID: {request_id}"
        message += f"\nBody: {response.text[:1000]}"
        raise requests.HTTPError(message, response=response)
    
    data = response.json()
    # Capture request id if provided by gateway/proxy for traceability
    request_id = response.headers.get("X-Request-ID")
    
    if isinstance(data, dict) and request_id:
        data["_request_id"] = request_id
    
    data["http_status"] = response.status_code

    return data


def _label_to_display(label: int) -> str:
    name = LABEL_MAP.get(label, f"Class {label}")
    icon = LABEL_ICON.get(label, "")
    icon_prefix = f"{icon} " if icon else ""
    return f"{icon_prefix}{name} (id={label})"


def _format_probabilities_table(probabilities_for_one: Any) -> Optional[list[dict[str, Any]]]:
    """
    Convert a single-sample probability vector into a table.
    
    Supports:
        - list[float] (already one sample)
        - list[list[float]] (take first sample)
    """
    vector: Any = probabilities_for_one

    # If API returns list[list[float]] for batch, take the first element
    if isinstance(vector, list) and vector and isinstance(vector[0], list):
        vector = vector[0]
    
    if not (isinstance(vector, list) and all(isinstance(x, (int, float)) for x in vector)):
        return None

    rows: list[dict[str, Any]] = []
    for c, p in enumerate(vector):
        rows.append(
            {
                "class": c,
                "label": LABEL_MAP.get(c, f"Class {c}"),
                "probability": round(float(p), 4),
            }
        )

    rows.sort(key=lambda r: r["probability"], reverse=True)
    return rows


def _format_probabilities_tables(probabilities: Any) -> Optional[list[list[dict[str, Any]]]]:
    """
    Return per-sample probability tables.
    - list[float] -> one table
    - list[list[float]] -> one table per sample
    """
    if probabilities is None:
        return None

    # Single prediction
    if isinstance(probabilities, list) and (not probabilities or isinstance(probabilities[0], (int, float))):
        table = _format_probabilities_table(probabilities)
        return [table] if table is not None else None

    # Multi prediction
    if isinstance(probabilities, list) and probabilities and isinstance(probabilities[0], list):
        tables = []
        for vector in probabilities:
            table = _format_probabilities_table(vector)
            if table is None:
                return None
            tables.append(table)
        return tables

    return None


def _confidence_for_prediction(probabilities: Any, i: int, label: int) -> Optional[float]:
    try:
        # Multi prediction
        if isinstance(probabilities, list) and probabilities and isinstance(probabilities[0], list):
            record = probabilities[i] # Lable probabilities vector for record i (prediction i)
            return float(record[label]) if 0 <= label < len(record) else None # confidence for each label
        # Single prediction
        if isinstance(probabilities, list):
            return float(probabilities[label]) if 0 <= label < len(probabilities) else None
    except Exception:
        return None
    return None


def _init_client_logs() -> None:
    if "client_logs" not in st.session_state:
        st.session_state["client_logs"] = []


def _log_client_event(event: dict[str, Any]) -> None:
    _init_client_logs()
    st.session_state["client_logs"].append(event)
    # Keep last 200
    st.session_state["client_logs"] = st.session_state["client_logs"][-200:]


# ----- Streamlit UI -----
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

if "is_running" not in st.session_state:
    st.session_state["is_running"] = False

st.divider()

# Persist base URL and API service token across reruns so status/result feel stable.
if "raw_base_url" not in st.session_state:
    st.session_state["raw_base_url"] = _default_api_base_url()

if "api_bearer_token" not in st.session_state:
    st.session_state["api_bearer_token"] = _default_api_bearer_token()

api_base_url = _normalise_base_url(st.session_state.get("raw_base_url", ""))
api_bearer_token = str(st.session_state.get("api_bearer_token", "")).strip()

# Health/readiness gating
status = _check_health(api_base_url, api_bearer_token) if api_base_url else APIStatus(ok=False, detail="Invalid base URL")

# Last response state (rendered in the Output column)
if "latest_result" not in st.session_state:
    st.session_state["latest_result"] = None

if "previous_result" not in st.session_state:
    st.session_state["previous_result"] = None

with st.sidebar:
    st.markdown("## Sepanta Kamali")
    st.caption("AI Engineer • Production ML Systems")

    try:
        html = textwrap.dedent(f"""
        <a class="github-linkButton" href="{LINKS["github"]}" target="_blank" rel="noreferrer">
            <picture>
                <source srcset="{_svg_as_data_uri(GITHUB_ICON_WHITE)}" media="(prefers-color-scheme: dark)">
                <img class="github-icon" src="{_svg_as_data_uri(GITHUB_ICON_BLACK)}" alt="GitHub" />
            </picture>
        </a>
        """).strip()   
        st.markdown(html, unsafe_allow_html=True)
    except Exception:
        # Fallback if icon file missing or can't be read
        st.link_button("GitHub", LINKS["github"], width="stretch")
    
    try:
        html = textwrap.dedent(f"""
        <a class="linkedin-linkButton" href="{LINKS['linkedin']}" target="_blank" rel="noreferrer">
            <img class="linkedin-icon" src="{_png_as_data_uri(LINKEDIN_ICON)}" alt="LinkedIn" />
        </a>
        """).strip()   
        st.markdown(html, unsafe_allow_html=True)
    except Exception:
        # Fallback if icon file missing or can't be read
        st.link_button("LinkedIn", LINKS["linkedin"], width="stretch")

    st.divider()
    st.markdown("<div class='ui-side-title'>Service status</div>", unsafe_allow_html=True)
    if api_base_url:
        if status.ok:
            st.success("✅ Inference API online")
        else:
            st.error("❌ Inference API unavailable")
    else:
        st.warning("API endpoint is not configured")

    st.caption("Authenticated model inference with health, readiness, and metrics monitoring.")

    st.divider()
    st.markdown("<div class='ui-side-title'>Project</div>", unsafe_allow_html=True)
    st.caption("Model lifecycle • Inference API • Observability • Client SDK")

    if LINKS["grafana"]:
        st.link_button("Grafana Dashboard", LINKS["grafana"], width="stretch")


with st.expander("About this system", expanded=False):
    st.markdown(
        """
        This interface is the client for a containerized NLP inference service built with FastAPI.

        - Authenticated single, batch, and file-based predictions
        - Published model selection with immutable `model_id` identity
        - Optional probabilities, structured results, CSV export, and raw JSON
        - Health and readiness checks, request validation, and rate limiting
        - Internal Prometheus metrics, Grafana dashboards, and email alerts
        - An OpenAPI-generated Python client SDK for downstream integrations
        """
    )

with st.expander("Engineering Notes", expanded=False):
    st.markdown(
        """
        - **Artifact lifecycle:** immutable model files are saved once; publish and promotion events are recorded separately
        - **Runtime resolution:** `latest` and `stable` pointers select models without modifying their artifacts
        - **Metadata:** immutable build identity is stored with the artifact; mutable release state is reconciled from the registry log
        - **Security:** scoped bearer tokens, rate limiting, and internal-only operational endpoints
        - **Reliability:** typed contracts, response validation, automated tests, containerized deployment, and rollback-aware releases
        - **Observability:** request metrics and IDs, version-controlled dashboards, and Grafana-managed email alerts
        """
    )

# ----- Product panel (Status strip + 2 columns) -----
status_strip_placeholder = st.empty()
conn_details_placeholder = st.empty()

st.write("")

left_column, right_column = st.columns([1, 1], gap="large")

# ----- Left column (Input) -----
with left_column:
    with st.container(border=True):
        st.subheader("Request")
        
        st.text_input(
            "API base URL",
            key="raw_base_url",
            help="e.g. https://e2epraiip.onrender.com (scheme optional)",
        )

        if st.session_state.get("api_bearer_token"):
            st.caption("API service token loaded from environment or secret file.")
        else:
            st.warning("API service token is missing. Set API_BEARER_TOKEN_FILE or API_BEARER_TOKEN.")

        if st.session_state.get("api_bearer_token"):
            st.caption("API service authentication is configured.")
        else:
            st.warning(
                "API service authentication is not configured. "
                "Set API_BEARER_TOKEN_FILE or API_BEARER_TOKEN in the Streamlit service environment."
            )

        api_bearer_token = str(st.session_state.get("api_bearer_token", "")).strip()

        # Recompute derived URL + status after edits
        api_base_url = _normalise_base_url(st.session_state.get("raw_base_url", ""))
        status = _check_health(api_base_url, api_bearer_token) if api_base_url else APIStatus(ok=False, detail="Invalid base URL")

        if st.session_state.get("raw_base_url") and not api_base_url:
            st.error("Invalid API base URL. Use http(s)://host or just host (scheme defaults to https).")

        # ----- Build model options: stable, latest, plus published models -----
        registry = _models_registry(api_base_url, api_bearer_token) if api_bearer_token else []

        stable_info = (_model_info(api_base_url, "stable", api_bearer_token) or {}) if api_bearer_token else {}
        latest_info = (_model_info(api_base_url, "latest", api_bearer_token) or {}) if api_bearer_token else {}

        stable_id = stable_info.get("model_id")
        latest_id = latest_info.get("model_id")

        options = ["stable", "latest"]

        for _model in registry:
            if not _model.get("published"):
                continue
            _model_id = _model.get("model_id")
            if not _model_id:
                continue
            if _model_id in {stable_id, latest_id}:
                continue
            options.append(f"model::{_model_id}")

        def _format_model_option(_version: str) -> str:
            if _version == "stable":
                tag = stable_info.get("release_tag") or "unreleased"
                return f"Stable:{tag} (recommended)"
            if _version == "latest":
                tag = latest_info.get("release_tag") or "unreleased"
                return f"Latest:{tag}"
            if _version.startswith("model::"):
                _model_id = _version.split("::", 1)[1]
                _model = next((x for x in registry if x.get("model_id") == _model_id), None)
                tag = _model.get("release_tag") if _model else "unreleased"
                suffix = _model.get("model_id") if _model else ""
                return f"TextCLF:{tag} • {suffix[-8:]}"
            return _version

        model = st.selectbox(
            "Model",
            options=options, # We can limit legacy models ...
            key="selected_model",
            format_func=_format_model_option,
        )

        if model == "stable":
            st.caption("Recommended for reliable results. Updated only when promoted.")
        elif model == "latest":
            st.caption("Most recent model. May change more frequently.")
        else:
            st.caption("Published model artifact selected.")

        if model in {"stable", "latest"}:
            selected_info = (_model_info(api_base_url, model, api_bearer_token) or {}) if api_bearer_token else {}
            selected_pointer = model
        else:
            selected_mid = model.split("::", 1)[1]
            selected_info = next((x for x in registry if x.get("model_id") == selected_mid), {}) if api_bearer_token else {}
            selected_pointer = "TextCLF"

        selected_release_tag = selected_info.get("release_tag") or "unreleased"
        selected_model_id = selected_info.get("model_id")

        st.caption(f"Selected build: {_model_compact(selected_pointer, selected_release_tag)}")
        if selected_model_id:
            st.caption(f"Model ID: {selected_model_id}")

        return_probabilities = st.checkbox("Return probabilities", value=False)

        st.markdown("#### Input")
        mode = st.radio(
            "Input mode",
            ["Single text", "Batch (one per line)", "Upload file"],
            index=0,
            horizontal=True,
        )
        # Examples
        example1 = "The team won 3-2 in overtime after a great power play."
        example2 = "Politicians are divided based on their views on West Asian politics."

        example1_column, example2_column = st.columns(2)
        with example1_column:
            if st.button("Insert example (Sports)"):
                st.session_state["text_area"] = example1
        with example2_column:
            if st.button("Insert example (Politics)"):
                st.session_state["text_area"] = example2

        texts: list[str] = []

        if mode in {"Single text", "Batch (one per line)"}:
            label = "Text" if mode == "Single text" else "One text per line (blank lines are ignored)"
            placeholder = "Paste a single text (can be multi-line)…" if mode == "Single text" else "Paste multiple lines to run batch prediction…"

            text_block = st.text_area(
                label=label,
                height=210,
                placeholder=placeholder,
                key="text_area",
            )

            if mode == "Single text":
                text = (text_block or "").strip()
                texts = [text] if text else [] # we use 'texts' for compatibilitiy
            else:
                texts = [text.strip() for text in (text_block or "").splitlines() if text.strip()]

        else:
            upload = st.file_uploader(
                "Upload a .txt (one per line) or .csv (text column)",
                type=["txt", "csv"],
                accept_multiple_files=False,
            )

            if upload is not None and getattr(upload, "type", "") == "application/x-iwork-numbers-sffnumbers":
                st.error("Apple Numbers (.numbers) files are not supported. Export as CSV or TXT.")
                upload = None

            if upload is not None:
                name = (upload.name or "").lower()
                try:
                    if name.endswith(".txt"):
                        content = upload.getvalue().decode("utf-8", errors="replace")
                        texts = [text.strip() for text in content.splitlines() if text.strip()]

                    elif name.endswith(".csv"):
                        raw = upload.getvalue()

                        # Try both header=0 and header=None; choose the one that yields more rows.
                        dataframe_0_header = pd.read_csv(io.BytesIO(raw), header=0)
                        dataframe_None_header = pd.read_csv(io.BytesIO(raw), header=None)

                        dataframe = dataframe_0_header if dataframe_0_header.shape[0] >= dataframe_None_header.shape[0] else dataframe_None_header

                        # Prefer a 'text' column if present; otherwise use the first column.
                        if "text" in dataframe.columns:
                            series = dataframe["text"].astype(str)
                        else:
                            series = dataframe.iloc[:, 0].astype(str)

                        series = series.str.strip()
                        texts = [text for text in series.tolist() if text]

                except Exception as e:
                    st.error(f"Could not parse the file: {e}")
                    texts = []

        if texts:
            st.caption(f"Batch size: {len(texts)}")

        token_missing = not str(st.session_state.get("api_bearer_token", "")).strip()
        button_disabled = (not status.ok) or (len(texts) == 0) or token_missing

        if token_missing:
            st.info("Enter an API bearer token before running prediction.")
        
        button = st.button(
            "Predict",
            type="primary",
            disabled=button_disabled or st.session_state.get("is_running", False),
            use_container_width=True,
        )

# -------- Prediction handler (stores output into session state) --------
if button:
    with st.spinner("Calling API..."):
        start = time.perf_counter()
        ok = False
        http_status: Optional[int] = None
        err: Optional[str] = None
        payload: Optional[dict[str, Any]] = None
        request_id: Optional[str] = None
        model_version: Optional[str] = None
        model_info: dict[str, Any] = {}
        api_model: Optional[str] = None

        try:
            st.session_state["is_running"] = True
            api_model = model
            if model.startswith("model::"):
                api_model = model.split("::", 1)[1]

            data = _post_predict(
                api_base_url=api_base_url,
                api_bearer_token=api_bearer_token,
                texts=texts,
                return_probabilities=return_probabilities,
                model=api_model,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0

            if isinstance(data, dict):
                if data.get("_request_id"):
                    request_id = str(data.get("_request_id"))
                if data.get("http_status"):
                    http_status = int(data.get("http_status"))

            labels, probabilities, model_info = _validate_predict_response(data)
            ok = True

            # For legacy version adaptability and different versions' compatibility
            # Attribute any variation of model version to model_version
            if isinstance(model_info, dict):
                for _key in ("version", "model_version", "id", "tag"):
                    if _key in model_info and model_info.get(_key):
                        model_version = str(model_info.get(_key))
                        break

            payload = {
                "texts": texts,
                "labels": labels,
                "probabilities": probabilities,
                "model": model_info,
            }

        except requests.HTTPError as e:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            response = getattr(e, "response", None)
            if response is not None:
                http_status = response.status_code
            err = str(e)

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            err = str(e)

        finally:
            st.session_state["is_running"] = False
            # Replace previous result with the latest
            st.session_state["previous_result"] = st.session_state.get("latest_result")
            # Register the new result as the latest
            st.session_state["latest_result"] = {
                "ok": ok,
                "status": http_status,
                "error": err,
                "elapsed_ms": elapsed_ms,
                "base_url": api_base_url,
                "model_pointer": model if model in {"stable", "latest"} else "TextCLF",
                "model_selector": api_model,
                "release_tag": (model_info.get("release_tag") if isinstance(model_info, dict) else None) or "unreleased",
                "model_id": (model_info.get("model_id") if isinstance(model_info, dict) else None) or model_version,
                "software_version": (model_info.get("software_version") if isinstance(model_info, dict) else None),
                "request_id": request_id,
                "batch": len(texts),
                "payload": payload,
            }

            _log_client_event(
                {
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "ok": ok,
                    "status": http_status,
                    "base_url": api_base_url,
                    "pointer": model if model in {"stable", "latest"} else "TextCLF",
                    "release_tag": (model_info.get("release_tag") if isinstance(model_info, dict) else None) or "unreleased",
                    "model_id": (model_info.get("model_id") if isinstance(model_info, dict) else None) or model_version,
                    "elapsed_ms": elapsed_ms,
                    "batch": len(texts),
                    "request_id": request_id,
                    "error": err,
                }
            )

# ----- Render status strip (after Request recompute + prediction handler) -----
previous_result = st.session_state.get("previous_result")
previous_latency = (
    f"{previous_result.get('elapsed_ms', 0):.0f} ms"
    if previous_result and previous_result.get("elapsed_ms") is not None
    else "-"
)
previous_compact = _model_compact(
    previous_result.get("model_pointer") if previous_result else None,
    previous_result.get("release_tag") if previous_result else None,
)

base_badge = api_base_url if api_base_url else "Invalid base URL"
selected_model = st.session_state.get("selected_model", "stable")

if selected_model in {"stable", "latest"}:
    selected_info = (_model_info(api_base_url, selected_model, api_bearer_token) or {}) if api_bearer_token else {}
    selected_pointer = selected_model
else:
    selected_mid = selected_model.split("::", 1)[1]
    selected_info = next((x for x in _models_registry(api_base_url, api_bearer_token) if x.get("model_id") == selected_mid), {}) if api_bearer_token else {}
    selected_pointer = "TextCLF"

selected_release_tag = selected_info.get("release_tag") or "unreleased"
selected_compact = _model_compact(selected_pointer, selected_release_tag)

status_strip_placeholder.markdown(
    f"""
    <div class="ui-status">
        <span class="ui-badge">{'🟢 Online' if status.ok else '🔴 Offline'}</span>
        <span class="ui-badge">Base: {base_badge}</span>
        <span class="ui-badge">Selected: {selected_compact}</span>
        <span class="ui-badge">Previous Prediction: {previous_compact}</span>
        <span class="ui-badge">Previous Latency: {previous_latency}</span>
        <div class="ui-muted">
            {'Health endpoint reachable' if status.ok else _summarise_connection_error(status.detail)}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not status.ok and status.detail:
    with conn_details_placeholder.expander("Connection details", expanded=False):
        st.code(status.detail)
else:
    conn_details_placeholder.empty()

# ----- Right column (Output) -----
with right_column:
    with st.container(border=True):
        st.subheader("Result")

        latest = st.session_state.get("latest_result")
        if not latest:
            st.markdown("""
                <div style='padding:40px;text-align:center;color:var(--muted);'>
                    <h4 style='margin-bottom:10px;'>No inference run yet</h4>
                    Enter text on the left and click <b>Predict</b> to run inference.
                </div>
            """, unsafe_allow_html=True)
        else:
            if latest.get("ok"):
                st.success(f"OK ({latest.get('elapsed_ms', 0):.0f} ms)")

                st.markdown(
                    f"""<div class='ui-muted'>Model: {_model_compact(latest.get('model_pointer'), latest.get('release_tag'))}</div>
                        <div class='ui-muted' style='margin-bottom:14px;'>Latency: {latest.get('elapsed_ms', 0):.0f} ms</div>
                    """,
                    unsafe_allow_html=True,
                )

                payload = latest.get("payload") or {}
                labels = payload.get("labels", [])
                probabilities = payload.get("probabilities")
                inputs = payload.get("texts", [])

                # Primary outcome (single input)
                if len(labels) == 1:
                    prediction = labels[0]
                    confidence = None
                    if probabilities is not None:
                        confidence = _confidence_for_prediction(probabilities, 0, prediction) if probabilities is not None else None
                        confidence = round(confidence, 3) if isinstance(confidence, (int, float)) else None
                    headline = _label_to_display(prediction)
                    st.markdown(
                        f"<h2 style='margin-bottom:6px;'>{headline}</h2>",
                        unsafe_allow_html=True,
                    )
                    if confidence is not None:
                        st.caption(f"Confidence: {confidence:.3f}")


                rows: list[dict[str, Any]] = []
                for i, (text, label) in enumerate(zip(inputs, labels), start=1):
                    confidences = _confidence_for_prediction(probabilities, i - 1, label) if probabilities is not None else None
                    confidences = round(confidences, 3) if isinstance(confidences, (int, float)) else None
                    rows.append({
                        "#": i,
                        "label": _label_to_display(label),
                        "confidence": confidences,
                        "text": text,
                        "label_id": label,
                    })

                # Single input: avoid duplicating the headline label
                if len(rows) == 1:
                    st.markdown("#### Input")
                    st.caption(rows[0]["text"])
                else:
                    st.markdown("#### Predictions")

                if len(rows) > 1:
                    view = pd.DataFrame(rows)
                    compact = view[["#", "label", "confidence"]].copy() if probabilities is not None else view[["#", "label"]].copy()
                    st.dataframe(compact, use_container_width=True, hide_index=True)

                    with st.expander("Show inputs", expanded=False):
                        for r in rows:
                            st.markdown(f"**{r['#']}.** {r['label']}")
                            st.caption(r["text"])

                # Download results CSV
                try:
                    dataframe = pd.DataFrame(rows)

                    export = dataframe.drop(columns=["#"], errors="ignore").copy()
                    export["pointer"] = latest.get("model_pointer")
                    export["release_tag"] = latest.get("release_tag")
                    export["model_id"] = latest.get("model_id")
                    export["request_id"] = latest.get("request_id")
                    export["latency_ms"] = round(float(latest.get("elapsed_ms", 0.0)), 0)
                    export["base_url"] = latest.get("base_url")

                    _columns = [
                        "text",
                        "label",
                        "label_id",
                        "confidence",
                        "pointer",
                        "release_tag",
                        "model_id",
                        "request_id",
                        "latency_ms",
                        "base_url",
                    ] if probabilities is not None else [
                        "text",
                        "label",
                        "label_id",
                        "pointer",
                        "release_tag",
                        "model_id",
                        "request_id",
                        "latency_ms",
                        "base_url",
                    ]
                    export = export[[column for column in _columns if column in export.columns]]

                    csv = export.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "Download results (CSV)",
                        data=csv,
                        file_name="inference_results.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                except Exception:
                    pass

                if probabilities is not None:
                    st.markdown("#### Probabilities")
                    tables = _format_probabilities_tables(probabilities)
                    if tables is None:
                        st.warning("Probabilities returned, but could not be parsed.")
                        st.json(probabilities)
                    else:
                        if len(tables) == 1:
                            st.dataframe(tables[0], use_container_width=True)
                        else:
                            for i, table in enumerate(tables, start=1):
                                with st.expander(f"Entry {i}'s probability table", expanded=False):
                                    st.dataframe(table, use_container_width=True)

                with st.expander("Raw JSON", expanded=False):
                    st.json(payload)

            else:
                st.error("Request failed")
                if latest.get("elapsed_ms") is not None:
                    st.caption(f"Client-perceived latency: {latest.get('elapsed_ms', 0):.0f} ms")
                if latest.get("error"):
                    st.code(latest["error"])


st.divider()
with st.expander("Request history (last 200)", expanded=False):
    _init_client_logs()
    logs = list(st.session_state.get("client_logs", []))

    if not logs:
        st.caption("No requests yet.")
    else:
        # Newest first
        logs = list(reversed(logs))

        view_rows: list[dict[str, Any]] = []
        for e in logs:
            _request_id = (e.get("request_id") or "")
            err = (e.get("error") or "")
            view_rows.append(
                {
                    "ts": e.get("ts"),
                    "ok": bool(e.get("ok")),
                    "http": e.get("status"),
                    "pointer": e.get("pointer"),
                    "release_tag": e.get("release_tag") or "unreleased",
                    "model_id": e.get("model_id") or "-",
                    "batch": e.get("batch"),
                    "request": (_request_id[:8] + "…") if _request_id else "-",
                    "error": (err[:80] + "…") if len(err) > 80 else (err or "-"),
                }
            )

        st.dataframe(pd.DataFrame(view_rows), use_container_width=True, hide_index=True)

        with st.expander("Raw request events", expanded=False):
            st.json(list(reversed(logs)))

with st.expander("Label mapping (edit in ui/app.py)", expanded=False):
    st.write("Class IDs are mapped to human-readable labels/icons in the UI for readability.")
    st.json({"LABEL_MAP": LABEL_MAP, "LABEL_ICON": LABEL_ICON})

st.divider()
st.caption("© 2025–2026 Sepanta Kamali • Built with FastAPI, Docker, Prometheus, Streamlit")
