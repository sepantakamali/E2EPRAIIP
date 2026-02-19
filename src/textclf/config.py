import re
from urllib.parse import urlparse
import requests
import streamlit as st


def _normalize_base_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    # If user entered host without scheme, default to https
    if not re.match(r"^https?://", raw):
        raw = "https://" + raw
    # Remove trailing slash
    return raw.rstrip("/")


def _health_url(base_url: str) -> str:
    return f"{base_url}/health"


def _predict_url(base_url: str) -> str:
    return f"{base_url}/predict"


def _get_session() -> requests.Session:
    sess = st.session_state.get("_http_session")
    if sess is None:
        sess = requests.Session()
        st.session_state["_http_session"] = sess
    return sess


def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return None


# UI label mapping (icons + human-friendly names)
# NOTE: The numeric label -> category mapping depends on how the model was trained.
# This mapping assumes label 0 maps to the first category, label 1 to the second.
LABEL_CATEGORIES = [
    "rec.sport.hockey",
    "talk.politics.mideast",
]
LABEL_ICONS = {
    "rec.sport.hockey": "🏒",
    "talk.politics.mideast": "🌍",
}
LABEL_TITLES = {
    "rec.sport.hockey": "Hockey (rec.sport.hockey)",
    "talk.politics.mideast": "Middle East Politics (talk.politics.mideast)",
}


def _format_label(label_value):
    # label_value is usually an int (e.g., 0/1). Fall back gracefully.
    try:
        idx = int(label_value)
        if 0 <= idx < len(LABEL_CATEGORIES):
            cat = LABEL_CATEGORIES[idx]
            icon = LABEL_ICONS.get(cat, "")
            title = LABEL_TITLES.get(cat, cat)
            return f"{icon} {title}".strip()
    except Exception:
        pass
    return str(label_value)


st.sidebar.header("Settings")
base_url_raw = st.sidebar.text_input(
    "API Base URL",
    value=st.session_state.get("_base_url_raw", "https://e2epraiip.onrender.com"),
)
st.session_state["_base_url_raw"] = base_url_raw
base_url = _normalize_base_url(base_url_raw)

st.sidebar.subheader("API Status")
api_ok = False
api_detail = ""
if base_url:
    try:
        sess = _get_session()
        r = sess.get(_health_url(base_url), timeout=5)
        api_ok = r.status_code == 200
        api_detail = r.text.strip()[:200]
    except Exception as e:
        api_ok = False
        api_detail = str(e)

if api_ok:
    st.sidebar.success("Reachable")
else:
    st.sidebar.error("Not reachable")
    if api_detail:
        st.sidebar.caption(api_detail)


st.subheader("Input")
text_raw = st.text_area(
    "Enter one or more texts (one per line)",
    height=180,
    placeholder="Hockey fans were ecstatic after the playoff win.\nThe conflict escalated after renewed tensions in the region.",
)
texts = [ln.strip() for ln in text_raw.splitlines() if ln.strip()]


def _post_predict(base_url: str, texts: list[str], return_prob: bool) -> requests.Response:
    sess = _get_session()
    payload = {"texts": texts, "return_prob": return_prob}
    return sess.post(_predict_url(base_url), json=payload, timeout=15)


return_prob = st.checkbox("Return probabilities", value=False)

can_predict = bool(base_url) and api_ok and bool(texts)

if not texts:
    st.info("Add at least one line of text to enable prediction.")

if st.button("Predict", disabled=not can_predict):
    with st.spinner("Calling /predict ..."):
        resp = _post_predict(base_url, texts, return_prob)

    st.write("HTTP status:", resp.status_code)

    if resp.status_code != 200:
        j = _safe_json(resp)
        if isinstance(j, dict) and "detail" in j:
            st.error(j["detail"])
        else:
            st.error(resp.text)
        st.stop()

    data = _safe_json(resp)
    if not isinstance(data, dict):
        st.error("Expected JSON object response.")
        st.write(resp.text)
        st.stop()

    labels = data.get("labels")
    probs = data.get("probabilities")
    model_info = data.get("model")

    st.subheader("Results")

    if model_info:
        st.caption(f"Model: {model_info}")

    if isinstance(labels, list):
        for i, lv in enumerate(labels):
            st.markdown(f"**#{i+1}:** {_format_label(lv)}")
    else:
        st.warning("No 'labels' returned.")

    if return_prob and isinstance(probs, list) and probs:
        st.subheader("Probabilities")
        # probs can be shape [n, k] or [k] depending on backend; handle both.
        if probs and isinstance(probs[0], list):
            # [n, k]
            for i, row in enumerate(probs):
                if isinstance(row, list) and len(row) == len(LABEL_CATEGORIES):
                    st.markdown(f"**#{i+1}**")
                    tbl = {LABEL_TITLES.get(cat, cat): float(p) for cat, p in zip(LABEL_CATEGORIES, row)}
                    st.json(tbl)
                else:
                    st.json(row)
        else:
            # [k]
            if isinstance(probs, list) and len(probs) == len(LABEL_CATEGORIES):
                tbl = {LABEL_TITLES.get(cat, cat): float(p) for cat, p in zip(LABEL_CATEGORIES, probs)}
                st.json(tbl)
            else:
                st.json(probs)