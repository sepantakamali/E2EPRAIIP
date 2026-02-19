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

# ----- Styling (Streamlit CSS overrides) -----
st.markdown(
    """
    <style>
  [data-testid="stAppViewContainer"] {
#   background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
  max-width: 100% !important;
  }

  [data-testid="stMain"] {
#   background-color: transparent;
  max-width: 100%;
  }

  section[data-testid="stSidebar"] {
  min-width: 30%;
  max-width: 50%;
#   background: linear-gradient(180deg, #1E293B 0%, #0F172A 100%);
#   border-right: 1px solid #334155;
  }

  [data-testid="stSidebar"][aria-expanded="false"] {
  display: None;
#   transition: opacity 0.6s ease, transform 0.6s ease;
#   animation: hideSidebar 0.6s ease forwards;
  }

#   [data-testid="stSidebar"] button[kind="headerNoPadding"] {
# #   border: 1px solid rgba(0, 0, 0, 0.12);
# #   border-radius: 8px;
#   transition:  0.2s ease, transform 0.1s ease;
#   transition-behavior: allow-discrete;
#   }

  [data-testid="stSidebar"] button[kind="headerNoPadding"]:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  transform: translateY(-1px);  /* very subtle lift */
  }

  /* Reduce visual dead-space in sidebar header area */
  section[data-testid="stSidebar"] div[data-testid="stSidebarHeader"] {
    height: 50px !important;
    margin: 1px !important;
    padding: 1px !important;
  }

  /* Make link buttons look uniform */
  section[data-testid="stSidebar"] a {
    width: 100% !important;
    height: 50px !important;
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    min-height: clamp(50px, 2.5cqi, 100px) !important;
    container-type: inline-size !important; 
    overflow: hidden;
    white-space: nowrap;
    margin: 0;
    text-align: center;
  }

  section[data-testid="stSidebar"] a p {
    font-size: clamp(5px, 11cqi, 11px) !important;
  }

  /* Slightly tighten vertical spacing between sidebar widgets */
  *.stVerticalBlock { 
    gap: 10px; 
  }

  .stMarkdown h2 {
    font-size: clamp(15px, 2cqi, 30px) !important;
    margin: 5px;
    margin-bottom: 0px;
    padding: 0px;
    padding-bottom: 5px;
    min-width: 100%;
    min-height: 100%;
  }

  .stMarkdown p {
    font-size: clamp(5px, 1.5cqi, 15px) !important;
    margin: 0px;
    padding: 0px;
    margin-bottom: 10px;
    margin-left: 5px;
    min-width: 100%;
    min-height: 100%;
  }

  .stElementContainer:has(a[href="https://github.com/sepantakamali/E2EPRAIIP"]) {
    width: 100%;
    height: 100%;
  }

  div[data-testid="stLinkButton"] a[href*="github.com/sepantakamali/E2EPRAIIP"] p {
    font-size: clamp(20px, 4cqi, 30px) !important;
  }

  /* Custom GitHub button (HTML anchor) */
  section[data-testid="stSidebar"] a.github-linkButton {
  width: 100% !important;
  height: 50px !important;
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  margin: 10px;
  }

  /* Icon sizing */
  section[data-testid="stSidebar"] a.github-linkButton img.github-icon {
  width: 100%;
  height: 100%;
  }

  /* Custom GitHub button (HTML anchor) */
  section[data-testid="stSidebar"] a.linkedin-linkButton {
  width: 100% !important;
  height: 50px !important;
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  margin: 10px;
  }

  /* Icon sizing */
  section[data-testid="stSidebar"] a.linkedin-linkButton img.linkedin-icon {
  width: 100%;
  height: 100%;
  }

  div[data-testid="stLayoutWrapper"]:has(a[href="http://localhost:8000/docs"]) {
#   background: linear-gradient(135deg, #1E3A5F 0%, #1E293B 100%);
#   border-radius: 10px;
#   padding: 20px;
#   border: 1px so /lid #3B82F6;
#   box-shadow: 
#     0 4px 6px -1px rgba(59, 130, 246, 0.1),
#     inset 0 2px 4px rgba(59, 130, 246, 0.05);
  background-color: rgba(0, 0, 0, 0.04);  /* light mode */
  border-radius: 10px;
  padding: 8px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  }

  div[data-testid="stLayoutWrapper"]:has(a[href="http://localhost:8000/docs"]) .stLinkButton a {
#   background: linear-gradient(135deg, #2563EB 0%, #1E40AF 100%);
#   border: 1px solid #3B82F6;
#   color: #F1F5F9;
#   border-radius: 8px;
#   padding: 12px 24px;
#   transition: all 0.3s ease;
#   box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
  }

  div[data-testid="stLayoutWrapper"]:has(a[href="http://localhost:8000/docs"]) .stLinkButton a:hover {
#   background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
#   box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
#   transform: translateY(-2px);
  }

  </style>
  """,
  unsafe_allow_html=True,
)

IMAGE_PATH: Path = Path(os.getenv("IMAGE_PATH", "img"))

GITHUB_ICON: Path = IMAGE_PATH / "GitHub Logos" / "SVG" / "GitHub_Lockup_Black_Clearspace.svg"
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
    "repo": "https://github.com/sepantakamali/",
    "linkedin": "https://www.linkedin.com/in/sepanta-kamali-ab71691b6",
    "grafana": os.getenv("GRAFANA_DASHBOARD_URL", "").strip(),
    "health": "/health",
    "docs": "/docs",
    "openapi": "/openapi.json",
    "metrics": "/metrics",
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


@st.cache_data(ttl=5)
def _check_health(api_base_url: str) -> APIStatus:
    """
    Lightweight liveness check (cached for a few seconds).
    """
    if not api_base_url:
        return APIStatus(ok=False, detail="Empty base URL")

    url = f"{api_base_url}/health"
    try:
        session = _get_session()
        handshake = session.get(url, timeout=5)
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


def _validate_predict_reponse(data: Any) -> tuple[list[int], Any, dict[str, Any]]:
    """
    Validate /predict response shape.

    Expected:
    - Labels: List[int]
    - probabilities: Optional
    - model: dict
    """
    if not isinstance(data, dict):
        raise ValueError("API schema mismatch: response is not a JSON object")
    
    if "labels" not in data:
        raise ValueError("API schema mismatch: missing 'labels'")
    
    labels = data["labels"]
    if not isinstance(labels, list) or any(not isinstance(x, int) for x in labels):
        raise ValueError("API schema mismatch: 'labels' must be list[int]")
    
    model_info = data.get("model")
    if model_info is None:
        model_info = {}
    if not isinstance(model_info, dict):
        raise ValueError("API schema mismatch: 'model' must be an object")
    
    probabilities = data.get("probabilities")
    return labels, probabilities, model_info


def _post_predict(
        api_base_url: str, 
        texts: list[str], 
        return_prob: bool, 
        model: str
        ) -> dict[str, Any]:
    url = f"{api_base_url}/predict"
    params = {"model": model} if model else None
    payload = {"texts": texts, "return_prob": return_prob}

    session = _get_session()
    response = session.post(url, params=params, json=payload, timeout=15)
    
    if not response.ok:
        detail = _safe_json_detail(response)
        request_id = response.headers.get("x-request-id") or response.headers.get("x-amzn-trace-id")
        message = f"HTTP {response.status_code} from {response.url}"
        if detail:
            message += f"\nDetail: {detail}"
        if request_id:
            message += f"\nRequest-ID: {request_id}"
        message += f"\nBody: {response.text[:1000]}"
        raise requests.HTTPError(message, response=response)
    
    return response.json()

def _label_to_display(label: int) -> str:
    name = LABEL_MAP.get(label, f"Class {label}")
    icon = LABEL_ICON.get(label, "🏷️")
    return f"{icon} {name} (id={label})"


def _format_probs_table(probs_for_one: Any) -> Optional[list[dict[str, Any]]]:
    """
    Convert a single-sample probability vector into a table.
    
    Supports:
        - list[float] (already one sample)
        - list[list[float]] (take first sample)
    """
    vector: Any = probs_for_one

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
                "prob": float(p),
            }
        )

    rows.sort(key=lambda r: r["prob"], reverse=True)
    return rows


def _init_client_logs() -> None:
    if "client_logs" not in st.session_state:
        st.session_state["client_logs"] = []


def _log_client_event(event: dict[str, Any]) -> None:
    _init_client_logs()
    st.session_state["client_logs"].append(event)
    # Keep last 200
    st.session_state["client_logs"] = st.session_state["client_logs"][-200:]


# ----- Streamlit UI -----

st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)
 # Lightweight badges (visual polish). These are just images and don't require any secrets.
st.markdown(
    """
    <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-blue" />
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-API-green" />
    <img alt="Docker" src="https://img.shields.io/badge/Docker-Containerized-informational" />
    <img alt="Prometheus" src="https://img.shields.io/badge/Prometheus-Metrics-orange" />
    <img alt="Grafana" src="https://img.shields.io/badge/Grafana-Dashboards-yellow" />
    """,
    unsafe_allow_html=True,
)
st.divider()

raw_base_url = st.text_input(
    "API base URL",
    value=_default_api_base_url(),
    help="e.g. https://e2epraiip.onrender.com (scheme optional)",
)
api_base_url = _normalise_base_url(raw_base_url)

# Health / readiness gating
status = _check_health(api_base_url) if api_base_url else APIStatus(ok=False, detail="Invalid base URL")

if raw_base_url and not api_base_url:
    st.error(
        "Invalid API base URL. Use http(s)://host or just host "
        "(scheme will default to https)."
        )

with st.sidebar:
    st.markdown("## Sepanta Kamali")
    st.caption("AI Engineer • Production ML Systems")

    try:
        html = textwrap.dedent(f"""
        <a class="github-linkButton" href="{LINKS['repo']}" target="_blank" rel="noreferrer">
            <img class="github-icon" src="{_svg_as_data_uri(GITHUB_ICON)}" alt="GitHub" />
        </a>
        """).strip()   
        st.markdown(html, unsafe_allow_html=True)
    except Exception as e:
        st.error(e)
        # Fallback if icon file missing or can't be read
        st.link_button("GitHub", LINKS['repo'], width="stretch")
    
    try:
        html = textwrap.dedent(f"""
        <a class="linkedin-linkButton" href="{LINKS['linkedin']}" target="_blank" rel="noreferrer">
            <img class="linkedin-icon" src="{_png_as_data_uri(LINKEDIN_ICON)}" alt="LinkedIn" />
        </a>
        """).strip()   
        st.markdown(html, unsafe_allow_html=True)
    except Exception as e:
        st.error(e)
        # Fallback if icon file missing or can't be read
        st.link_button("LinkedIn", LINKS['linkedin'], width="stretch")

    st.divider()
    st.markdown("### API")
    if api_base_url:
        if status.ok:
            st.success("✅ Reachable")
        else:
            st.error("❌ Unreachable")

        st.markdown("#### Endpoints")
        btn_col1, btn_col2 = st.columns(2)

        health_url = f"{api_base_url}{LINKS['health']}"
        docs_url = f"{api_base_url}{LINKS['docs']}"
        openapi_url = f"{api_base_url}{LINKS['openapi']}"
        metrics_url = f"{api_base_url}{LINKS['metrics']}"

        with btn_col1:
            st.link_button("API Health", health_url, width="stretch")
            st.link_button("OpenAPI Spec", openapi_url, width="stretch")

        with btn_col2:
            st.link_button("Swagger Docs", docs_url, width="stretch")
            st.link_button("Prometheus Metrics", metrics_url, width="stretch")

    st.divider()
    st.markdown("### Project")
    st.caption("Inference API • MLOps • Observability • Client SDK")

    if LINKS["grafana"]:
        st.link_button("Grafana Dashboard", LINKS["grafana"], width="stretch")


with st.expander("About this system", expanded=False):
    st.markdown(
        """
        This interface connects to a production-style NLP inference API built with FastAPI and Docker.

        **Backend capabilities**
        - Model state switching: `latest` / `stable` / custom artifact path  
        - Health & readiness endpoints (`/health`, `/ready`)  
        - Rate limiting and request validation  
        - Prometheus metrics (`/metrics`) and Grafana dashboards  
        - OpenAPI schema used to generate a typed Python client SDK
        
        """
    )

with st.expander("Engineering Notes", expanded=False):
    st.markdown(
        """
        - **Observability:** request rate, p95 latency, error rate  
        - **Reliability:** schema validation (Pydantic v2), tests (pytest), type checking (mypy)  
        - **Deployment:** containerized service (Docker), cloud deploy (Render), image registry (GHCR)  
        - **MLOps:** artifact promotion (`promote_model`) and stable pointer strategy  
        """
    )

health_column, meta_column = st.columns([1, 2])
with health_column:
    if status.ok:
        st.success("API: reachable")
    else:
        st.error("API: unreachable")

with meta_column:
    if status.ok:
        st.caption(f"Health endpoint: {status.url}")
    else:
        if status.status_code is not None:
            st.caption(f"{status.url} returned {status.status_code}")
        elif status.detail:
            st.caption(status.detail)

# A two columned section to create two objects in the same row (customizations)
column1, column2 = st.columns(2)
with column1:
    model = st.selectbox("Model pointer", options=["stable", "latest"], index=0, accept_new_options=False)
with column2:
    return_prob = st.checkbox("Return probabilities", value=False)

st.subheader("Input")

# Examples
example1 = "The team won 3-2 in overtime after a great power play."
example2 = "Politicians are divided based on their views on West Asian politics."

example_column1, example_column2, example_column3 = st.columns([1, 1, 2])
with example_column1:
    if st.button("Example: Sports"):
        st.session_state["text_area"] = example1
with example_column2:
    if st.button("Example: Politics"):
        st.session_state["text_area"] = example2

text_block = st.text_area(
    "One text per line (blank lines are ignored)",
    height=185,
    placeholder="Paste multiple lines to run batch prediction...",
    key="text_area",
)

texts = [text.strip() for text in (text_block or "").splitlines() if text.strip()]

if texts:
    st.caption(f"Batch size: {len(texts)}")

button_disabled = (not status.ok) or (len(texts) == 0)
button = st.button("Predict", type="primary", disabled= button_disabled)

if button:
    with st.spinner("Calling API..."):
        start = time.perf_counter()
        ok = False
        http_status: Optional[int] = None
        err: Optional[str] = None
        try:
            data = _post_predict(
                api_base_url=api_base_url,
                texts=texts,
                return_prob=return_prob,
                model=model,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0

            labels, probs, model_info = _validate_predict_reponse(data)

            ok = True
            st.success(f"OK ({elapsed_ms:.0f} ms)")

            st.subheader("Predictions")
            # Show each input line with its label
            for i, (text, label) in enumerate(zip(texts, labels), start=1):
                st.markdown(f"**{i}.** {_label_to_display(label)}")
                st.caption(text)
            
            # Probabilities formatting (if present)
            if probs is not None:
                st.subheader("Probabilities (top-k)")
                rows = _format_probs_table(probs)
                if rows is None:
                    st.warning("Probabilities returned, but could not be parsed into a numeric vector.")
                    st.json(probs)
                else:
                    topk = rows[: min(5, len(rows))]
                    st.table(topk)
                    # Optional chart (topk)
                    try:
                        import pandas as pd

                        dataframe = pd.DataFrame(topk)
                        st.bar_chart(dataframe.set_index("label")["prob"])
                    except Exception:
                        pass

                    st.subheader("Model info")
                    st.json(model_info)

        except requests.HTTPError as e:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            response = getattr(e, "response", None)
            if response is not None:
                http_status = response.status_code
            err = str(e)
            st.error("Request failed")
            st.code(err)
            st.caption(f"Client-perceived latency: {elapsed_ms:.0f} ms")
        
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000.0      
            err = str(e)
            st.error("Error")
            st.code(err)
            st.caption(f"Client-perceived latency: {elapsed_ms:.0f} ms")

        finally:
            # Client-side observability hook
            _log_client_event(
                {
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "ok": ok,
                    "status": http_status,
                    "base_url": api_base_url,
                    "model": model,
                    "batch": len(texts),
                    "error": err,
                }
            )

st.divider()

with st.expander("Client logs (last 200)", expanded=False):
    _init_client_logs()
    st.json(st.session_state["client_logs"])

with st.expander("Label mapping (edit in ui/app.py)", expanded=False):
    st.write("Class IDs are mapped to human-readable labels/icons in the UI for readability.")
    st.json({"LABEL_MAP": LABEL_MAP, "LABEL_ICON": LABEL_ICON})

st.divider()
st.caption("© 2025 Sepanta Kamali • Built with FastAPI, Docker, Prometheus, Streamlit")