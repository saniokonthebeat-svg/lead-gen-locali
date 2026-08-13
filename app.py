import os
import sqlite3
import urllib.parse
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

load_dotenv()


def get_secret(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return default


API_KEY = get_secret("GOOGLE_PLACES_API_KEY")
if not API_KEY:
    st.error("Errore: GOOGLE_PLACES_API_KEY non trovata (env, .env o Streamlit secrets).")
    st.stop()

URL = "https://places.googleapis.com/v1/places:searchText"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.db")

STATI = [
    "Da chiamare",
    "Chiamato - interessato",
    "Chiamato - rifiutato",
    "Richiamare",
    "Chiuso",
]

REFRESH_OPTIONS = ["5s", "10s", "30s", "Off"]
REFRESH_MAP = {"5s": 5000, "10s": 10000, "30s": 30000, "Off": None}

STATO_COLORS = {
    "Da chiamare": "#94a3b8",
    "Chiamato - interessato": "#4facfe",
    "Chiamato - rifiutato": "#f87171",
    "Richiamare": "#fbbf24",
    "Chiuso": "#34d399",
}

CATEGORY_TERMS = [
    "ristoranti",
    "pizzerie",
    "trattorie",
    "hotel",
    "b&b",
    "bar",
    "gelaterie",
    "pasticcerie",
    "parrucchieri",
    "barbieri",
    "centri estetici",
    "studi dentistici",
    "panifici",
    "farmacie",
    "palestre",
    "agriturismo",
    "autofficine",
    "officine meccaniche",
    "fiorai",
    "ottici",
]

CITIES = [
    "Altamura",
    "Bari",
    "Taranto",
    "Foggia",
    "Lecce",
    "Brindisi",
    "Barletta",
    "Andria",
    "Trani",
    "Molfetta",
    "Bitonto",
    "Monopoli",
    "Corato",
]

CATEGORIES = [f"{term} a {city}" for city in CITIES for term in CATEGORY_TERMS]

MAX_PAGES = 2

DATA_VERSION = 4

LEAD_ESCLUSI = [
    "ChIJBYjezjOHRxMRAqarqNIAELk",
]

FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.internationalPhoneNumber,"
    "places.websiteUri,"
    "places.rating,"
    "places.userRatingCount"
)

ICONS = {
    "zap": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    "globe": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    "layers": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>',
    "phone": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 7 23 1 17 1"/><line x1="16" y1="8" x2="23" y2="1"/><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
    "rotate": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
    "check": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    "trend": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Sora:wght@600;700;800&display=swap');

        :root {
            --bg0: #070b18;
            --bg1: #0c1226;
            --bg2: #101a33;
            --card: rgba(255, 255, 255, 0.045);
            --border: rgba(255, 255, 255, 0.09);
            --text: #e6edf7;
            --muted: #8b96ad;
            --cyan: #22d3ee;
            --blue: #4facfe;
            --violet: #a78bfa;
            --green: #34d399;
            --amber: #fbbf24;
            --red: #f87171;
            --gray: #94a3b8;
        }

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, sans-serif;
            color: var(--text);
        }

        .stApp {
            background:
                radial-gradient(1200px 800px at 85% -10%, rgba(79, 172, 254, 0.14), transparent 60%),
                radial-gradient(1000px 700px at -10% 110%, rgba(167, 139, 250, 0.12), transparent 60%),
                radial-gradient(900px 600px at 50% 120%, rgba(34, 211, 238, 0.08), transparent 60%),
                linear-gradient(160deg, var(--bg0) 0%, var(--bg1) 45%, var(--bg2) 100%);
            background-attachment: fixed;
        }

        /* ---------- Hero ---------- */
        .hero { padding: 4px 2px 10px; }
        .hero .badge {
            display: inline-flex; align-items: center; gap: 9px;
            padding: 6px 14px; border-radius: 999px;
            background: rgba(52, 211, 153, 0.08);
            border: 1px solid rgba(52, 211, 153, 0.3);
            color: #6ee7b7; font-size: .8rem; font-weight: 600; letter-spacing: .04em;
            animation: fadeIn .6s ease both;
        }
        .hero .badge .dot { position: relative; width: 8px; height: 8px; border-radius: 50%; background: var(--green); }
        .hero .badge .dot::after { content: ""; position: absolute; inset: -3px; border-radius: 50%; border: 1px solid var(--green); animation: ping 1.6s ease-out infinite; }
        @keyframes ping { 0% { transform: scale(.8); opacity: .9; } 80%, 100% { transform: scale(1.9); opacity: 0; } }
        .hero h1 {
            font-family: 'Sora', sans-serif;
            font-size: 2.6rem; font-weight: 800; margin: 14px 0 8px; letter-spacing: -0.02em;
            background: linear-gradient(92deg, #7dd3fc, var(--cyan), var(--violet), #7dd3fc);
            background-size: 300% 100%;
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: titleFlow 8s linear infinite, fadeUp .6s ease both;
        }
        @keyframes titleFlow { 0% { background-position: 0% 50%; } 100% { background-position: 300% 50%; } }
        .hero p { color: var(--muted); font-size: 1.02rem; max-width: 700px; margin: 0; animation: fadeUp .7s .05s ease both; }

        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }

        /* ---------- KPI cards ---------- */
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin: 16px 0 22px; }
        .kpi {
            position: relative; overflow: hidden;
            background: var(--card); border: 1px solid var(--border);
            border-radius: 18px; padding: 16px 18px;
            backdrop-filter: blur(12px);
            transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
            animation: fadeUp .5s ease both;
        }
        .kpi:hover { transform: translateY(-4px); border-color: color-mix(in srgb, var(--acc) 55%, transparent); box-shadow: 0 16px 44px -16px rgba(0, 0, 0, .7); }
        .kpi::before { content: ""; position: absolute; inset: 0 0 auto 0; height: 3px; background: linear-gradient(90deg, transparent, var(--acc), transparent); opacity: .75; }
        .kpi .icon {
            width: 38px; height: 38px; border-radius: 12px; display: grid; place-items: center;
            background: color-mix(in srgb, var(--acc) 16%, transparent); color: var(--acc); margin-bottom: 12px;
        }
        .kpi .icon svg { width: 20px; height: 20px; }
        .kpi .label { color: var(--muted); font-size: .74rem; letter-spacing: .07em; text-transform: uppercase; font-weight: 700; }
        .kpi .value { font-family: 'Sora', sans-serif; font-size: 1.95rem; font-weight: 800; color: #fff; line-height: 1.1; margin-top: 2px; }
        .kpi .value em { font-style: normal; font-size: 1rem; font-weight: 600; color: var(--acc); margin-left: 2px; }

        /* ---------- Section titles ---------- */
        .section-head { display: flex; align-items: center; gap: 9px; margin: 8px 0 12px; animation: fadeIn .5s ease both; }
        .section-head .glow { width: 22px; height: 5px; border-radius: 4px; background: linear-gradient(90deg, var(--cyan), var(--violet)); box-shadow: 0 0 14px rgba(34, 211, 238, .5); }
        .section-head h3 { margin: 0; font-family: 'Sora', sans-serif; font-size: 1.18rem; font-weight: 700; color: var(--text); }

        .sidebar-label {
            display: flex; align-items: center; gap: 8px;
            color: var(--muted); font-size: .72rem; font-weight: 700;
            text-transform: uppercase; letter-spacing: .12em; margin: 16px 0 6px;
        }
        .sidebar-label::before { content: ""; width: 16px; height: 2px; border-radius: 2px; background: linear-gradient(90deg, var(--cyan), var(--violet)); }

        .brand { display: flex; align-items: center; gap: 12px; padding: 2px 2px 8px; animation: fadeIn .5s ease both; }
        .brand .mark {
            width: 42px; height: 42px; border-radius: 13px; display: grid; place-items: center; color: #06132b;
            background: linear-gradient(135deg, var(--blue), var(--cyan)); box-shadow: 0 8px 22px -6px rgba(79, 172, 254, .65);
        }
        .brand .mark svg { width: 22px; height: 22px; }
        .brand b { font-family: 'Sora', sans-serif; font-size: 1.12rem; letter-spacing: -0.01em; }
        .brand small { color: var(--muted); display: block; font-size: .78rem; }

        .legend { display: grid; gap: 7px; margin: 8px 0 4px; animation: fadeIn .5s ease both; }
        .legend .li { display: flex; align-items: center; gap: 9px; color: #cdd6e4; font-size: .84rem; }
        .legend .dot { width: 10px; height: 10px; border-radius: 50%; box-shadow: 0 0 8px currentColor; }

        /* ---------- Sidebar ---------- */
        [data-testid="stSidebar"] {
            background: rgba(10, 14, 30, 0.88);
            border-right: 1px solid var(--border);
            backdrop-filter: blur(16px);
        }

        /* ---------- Tabs (segmented) ---------- */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 6px; width: fit-content; padding: 6px;
            background: rgba(255, 255, 255, 0.04); border: 1px solid var(--border);
            border-radius: 14px; animation: fadeIn .5s ease both;
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            border-radius: 10px; padding: 8px 22px; font-weight: 600;
            color: var(--muted); transition: all .22s ease; border: none;
        }
        [data-testid="stTabs"] [data-baseweb="tab"]:hover { color: var(--text); background: rgba(255, 255, 255, 0.06); }
        [data-testid="stTabs"] [aria-selected="true"] {
            background: linear-gradient(135deg, var(--blue), var(--cyan));
            color: #06132b; font-weight: 700;
        }

        /* ---------- Metrics ---------- */
        [data-testid="stMetric"] {
            background: var(--card); border: 1px solid var(--border); border-radius: 18px;
            padding: 16px 18px; backdrop-filter: blur(12px);
            transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
            animation: fadeUp .55s ease both;
        }
        [data-testid="stMetric"]:hover { transform: translateY(-4px); border-color: rgba(79, 172, 254, .55); box-shadow: 0 16px 44px -16px rgba(0, 0, 0, .7); }
        [data-testid="stMetricLabel"] { color: var(--muted) !important; }
        [data-testid="stMetricValue"] { font-family: 'Sora', sans-serif; }

        /* ---------- Data editor ---------- */
        [data-testid="stDataFrame"] { border-radius: 16px; overflow: hidden; border: 1px solid var(--border); box-shadow: 0 24px 70px -34px rgba(0, 0, 0, .85); animation: fadeUp .6s .05s ease both; }

        /* ---------- Buttons ---------- */
        .stButton > button, .stDownloadButton > button {
            border-radius: 12px; font-weight: 700; border: none;
            background: linear-gradient(135deg, var(--blue), var(--cyan)); color: #06132b;
            transition: transform .18s ease, box-shadow .18s ease, filter .18s ease;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            transform: scale(1.03); filter: brightness(1.08); box-shadow: 0 8px 26px -8px rgba(0, 242, 254, .55);
        }

        /* ---------- Inputs ---------- */
        [data-testid="stTextInput"] input, [data-testid="stSelectbox"] [data-baseweb="select"] > div, [data-baseweb="select"] .css-1dimb5e-singleValue, [data-baseweb="select"] [class*="control"] {
            border-radius: 10px;
        }

        /* ---------- Alerts / empty states ---------- */
        [data-testid="stAlert"] { border-radius: 14px; border: 1px solid var(--border); background: var(--card); }

        /* ---------- Plotly ---------- */
        .js-plotly-plot { border-radius: 16px; overflow: hidden; }

        /* ---------- Scrollbar ---------- */
        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: rgba(255, 255, 255, 0.03); }
        ::-webkit-scrollbar-thumb { background: linear-gradient(180deg, var(--blue), var(--cyan)); border-radius: 8px; }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, accent: str, icon: str) -> str:
    return (
        f'<div class="kpi" style="--acc:{accent}">'
        f'<div class="icon">{ICONS[icon]}</div>'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        "</div>"
    )


def render_kpi_row(cards: list[str]) -> None:
    st.markdown(f'<div class="kpi-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(
        f'<div class="section-head"><span class="glow"></span><h3>{title}</h3></div>',
        unsafe_allow_html=True,
    )


def render_hero(updated_at: str) -> None:
    st.markdown(
        f"""
        <div class="hero">
            <span class="badge"><span class="dot"></span>Dati live · aggiornati alle {updated_at}</span>
            <h1>Agent Locali</h1>
            <p>I locali senza sito web in Puglia, pronti da chiamare. Filtra per città e categoria, aggiorna lo stato di ogni trattativa e tieni traccia di tutto.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_brand() -> None:
    st.markdown(
        f"""
        <div class="brand">
            <div class="mark">{ICONS["zap"]}</div>
            <div><b>Agent Locali</b><small>Lead engine · Puglia</small></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_label(text: str) -> None:
    st.markdown(f'<div class="sidebar-label">{text}</div>', unsafe_allow_html=True)


def render_legend() -> None:
    items = "".join(
        f'<div class="li"><span class="dot" style="color:{color};background:{color}"></span>{stato}</div>'
        for stato, color in STATO_COLORS.items()
    )
    st.markdown(f'<div class="legend">{items}</div>', unsafe_allow_html=True)


def style_map(styler: "pd.io.formats.style.Styler", func, subset) -> "pd.io.formats.style.Styler":
    try:
        return styler.map(func, subset=subset)
    except TypeError:
        return styler.applymap(func, subset=subset)


def search_category(category: str) -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    places: list[dict] = []
    page_token: str | None = None
    for _ in range(MAX_PAGES):
        payload = {"textQuery": category}
        if page_token:
            payload["pageToken"] = page_token
        response = requests.post(URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        places.extend(data.get("places", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return places


def search_all_categories(categories: list[str]) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for category in categories:
        for place in search_category(category):
            if place.get("websiteUri"):
                continue
            if not place.get("internationalPhoneNumber"):
                continue
            rating_count = place.get("userRatingCount") or 0
            nome = place.get("displayName", {}).get("text", "N/D")
            indirizzo = place.get("formattedAddress", "N/D")
            place_id = place.get("id") or ""
            if place_id:
                if place_id in seen:
                    continue
                seen.add(place_id)
            chiave = place_id or f"{nome}|{indirizzo}"
            results.append(
                {
                    "categoria": category,
                    "nome": nome,
                    "indirizzo": indirizzo,
                    "telefono": place.get("internationalPhoneNumber", "N/D"),
                    "website": place.get("websiteUri") or "",
                    "rating": place.get("rating") or "",
                    "ha_recensioni": "SÌ" if rating_count > 0 else "NO",
                    "place_id": place_id,
                    "chiave": chiave,
                }
            )
    return results


@st.cache_data(show_spinner="Cerco i locali senza sito in Puglia… la prima volta può richiedere qualche minuto")
def load_data(categories_tuple: tuple[str], version: int) -> pd.DataFrame:
    return pd.DataFrame(search_all_categories(list(categories_tuple)))


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS lead_stato (chiave TEXT PRIMARY KEY, stato TEXT NOT NULL, data_aggiornamento TEXT, data_richiamo TEXT)"
    )
    columns = [row[1] for row in conn.execute("PRAGMA table_info(lead_stato)").fetchall()]
    if "data_aggiornamento" not in columns:
        conn.execute("ALTER TABLE lead_stato ADD COLUMN data_aggiornamento TEXT")
    if "data_richiamo" not in columns:
        conn.execute("ALTER TABLE lead_stato ADD COLUMN data_richiamo TEXT")
    return conn


def load_stati() -> dict[str, tuple[str, str | None, str | None]]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT chiave, stato, data_aggiornamento, data_richiamo FROM lead_stato"
        ).fetchall()
    finally:
        conn.close()
    return {chiave: (stato, data, richiamo) for chiave, stato, data, richiamo in rows}


def save_state(chiave: str, stato: str, data_richiamo: str | None = None) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO lead_stato (chiave, stato, data_aggiornamento, data_richiamo) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(chiave) DO UPDATE SET stato = excluded.stato, "
            "data_aggiornamento = excluded.data_aggiornamento, data_richiamo = excluded.data_richiamo",
            (chiave, stato, datetime.now().isoformat(timespec="seconds"), data_richiamo),
        )
        conn.commit()
    finally:
        conn.close()


def build_maps_url(nome: str, indirizzo: str, place_id: str) -> str:
    query = urllib.parse.quote_plus(f"{nome}, {indirizzo}")
    if place_id:
        return f"https://www.google.com/maps/search/?api=1&query={query}&query_place_id={place_id}"
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def normalize_dt(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, str):
        try:
            return pd.to_datetime(value).isoformat(timespec="seconds")
        except Exception:
            return None
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        try:
            return datetime(*value[:6]).isoformat(timespec="seconds")
        except Exception:
            return None
    return None


def apply_stati(data: pd.DataFrame) -> pd.DataFrame:
    if "chiave" not in data.columns:
        data["chiave"] = data["place_id"].where(
            data["place_id"].astype(str).ne(""),
            data["nome"] + "|" + data["indirizzo"],
        )
    stati = load_stati()
    if LEAD_ESCLUSI:
        data = data[~data["chiave"].isin(LEAD_ESCLUSI)]
    data = data[data["website"] == ""]
    data = data[data["telefono"] != "N/D"]
    data["Stato"] = data["chiave"].map(lambda k: stati.get(k, ("Da chiamare", None, None))[0]).fillna("Da chiamare")
    data["data_aggiornamento"] = data["chiave"].map(lambda k: stati.get(k, (None, None, None))[1])
    data["richiama_il"] = pd.to_datetime(
        data["chiave"].map(lambda k: stati.get(k, (None, None, None))[2]),
        errors="coerce",
    )
    data["maps_url"] = data.apply(
        lambda r: build_maps_url(r["nome"], r["indirizzo"], r["place_id"]),
        axis=1,
    )
    return data


def on_stato_edit() -> None:
    editor = st.session_state.get("stato_editor")
    if not editor or not editor.get("edited_rows"):
        return
    keys = st.session_state.get("editor_keys", [])
    current = load_stati()
    for row_index, changes in editor["edited_rows"].items():
        key = keys[row_index]
        stato_old, _, data_old = current.get(key, ("Da chiamare", None, None))
        stato = changes.get("Stato", stato_old)
        if "richiama_il" in changes:
            data_richiamo = normalize_dt(changes["richiama_il"])
        else:
            data_richiamo = data_old
        if stato != "Richiamare":
            data_richiamo = None
        if "Stato" in changes or "richiama_il" in changes:
            save_state(key, stato, data_richiamo)


def read_qp(name: str, default: str) -> str:
    try:
        return str(st.query_params.get(name, default))
    except Exception:
        return default


def persist_filters() -> None:
    qp = st.query_params
    qp["citta"] = ",".join(st.session_state.get("citta_widget", []))
    qp["termini"] = ",".join(st.session_state.get("termini_widget", []))
    qp["cerca"] = str(st.session_state.get("cerca_widget", ""))
    qp["stati"] = ",".join(st.session_state.get("stati_widget", []))
    qp["refresh"] = str(st.session_state.get("refresh_widget", "5s"))
    qp["tab"] = str(st.session_state.get("tabs_key", 0))


def leads_page(full: pd.DataFrame) -> None:
    sidebar_label("Zona di ricerca")
    default_cities = [c for c in CITIES if c in read_qp("citta", "").split(",")] or CITIES
    default_terms = [t for t in CATEGORY_TERMS if t in read_qp("termini", "").split(",")] or CATEGORY_TERMS
    default_cerca = read_qp("cerca", "")
    default_stati = [s for s in STATI if s in read_qp("stati", "").split(",")] or STATI

    selected_cities = st.sidebar.multiselect(
        "Città",
        options=CITIES,
        default=default_cities,
        key="citta_widget",
        on_change=persist_filters,
    )

    selected_terms = st.sidebar.multiselect(
        "Categorie",
        options=CATEGORY_TERMS,
        default=default_terms,
        key="termini_widget",
        on_change=persist_filters,
    )

    sidebar_label("Filtri")
    search_text = st.sidebar.text_input(
        "Cerca per nome",
        placeholder="Es. pizzeria…",
        value=default_cerca,
        key="cerca_widget",
        on_change=persist_filters,
    )

    selected_stati = st.sidebar.multiselect(
        "Stato lead",
        options=STATI,
        default=default_stati,
        key="stati_widget",
        on_change=persist_filters,
    )

    sidebar_label("Legenda stati")
    render_legend()

    refresh_default = read_qp("refresh", "5s")
    refresh_default = refresh_default if refresh_default in REFRESH_OPTIONS else "5s"
    st.sidebar.selectbox(
        "Auto-aggiornamento",
        options=REFRESH_OPTIONS,
        index=REFRESH_OPTIONS.index(refresh_default),
        key="refresh_widget",
        on_change=persist_filters,
    )

    sidebar_label("Azioni")
    if st.sidebar.button("Aggiorna dati", width="stretch"):
        load_data.clear()
        st.rerun()

    selected = full[full["categoria"].isin(
        [f"{t} a {c}" for c in selected_cities for t in selected_terms]
    )].copy() if selected_cities and selected_terms else full.copy()

    if selected.empty:
        st.info("Nessun lead per i filtri selezionati.")
        return

    filtered = selected.copy()
    if search_text:
        filtered = filtered[filtered["nome"].str.contains(search_text, case=False, na=False)]

    if selected_stati:
        filtered = filtered[filtered["Stato"].isin(selected_stati)]

    priority = {"Da chiamare": 0, "Richiamare": 1}
    filtered["_prio"] = filtered["Stato"].map(priority).fillna(2)
    filtered = filtered.sort_values("_prio", kind="stable").drop(columns="_prio")

    section("Lead senza sito")
    totale = len(filtered)
    da_chiamare = int((filtered["Stato"] == "Da chiamare").sum())
    interessati = int((filtered["Stato"] == "Chiamato - interessato").sum())
    richiamare = int((filtered["Stato"] == "Richiamare").sum())
    chiusi = int((filtered["Stato"] == "Chiuso").sum())

    render_kpi_row(
        [
            kpi_card("Totale lead", f"{totale}<em>sel.</em>", "#4facfe", "globe"),
            kpi_card("Da chiamare", f"{da_chiamare}<em>priorità</em>", "#94a3b8", "phone"),
            kpi_card("Interessati", f"{interessati}<em>prossimi</em>", "#4facfe", "trend"),
            kpi_card("Richiamare", f"{richiamare}<em>da riprovare</em>", "#fbbf24", "rotate"),
            kpi_card("Chiusi", f"{chiusi}<em>vinti</em>", "#34d399", "check"),
        ]
    )

    st.session_state["editor_keys"] = filtered["chiave"].tolist()

    editor_df = filtered[["categoria", "nome", "indirizzo", "telefono", "maps_url", "Stato", "richiama_il"]]

    def _color_stato(value):
        if value in STATO_COLORS:
            return f"color:{STATO_COLORS[value]};font-weight:700;"
        return ""

    def _color_richiamo(value):
        if pd.notna(value):
            return "color:#fbbf24;font-weight:700;"
        return ""

    styler = editor_df.style
    styler = style_map(styler, _color_stato, subset=["Stato"])
    styler = style_map(styler, _color_richiamo, subset=["richiama_il"])

    st.data_editor(
        styler,
        key="stato_editor",
        on_change=on_stato_edit,
        height=1000,
        column_config={
            "categoria": st.column_config.TextColumn("Categoria", width="medium"),
            "nome": st.column_config.TextColumn("Nome", width="large"),
            "indirizzo": st.column_config.TextColumn("Indirizzo", width="large"),
            "maps_url": st.column_config.LinkColumn(
                "Google Maps",
                display_text="Apri",
            ),
            "Stato": st.column_config.SelectboxColumn(
                "Stato",
                options=STATI,
                required=True,
            ),
            "richiama_il": st.column_config.DatetimeColumn(
                "Richiama il",
                format="DD/MM/YYYY HH:mm",
            ),
        },
        disabled=["categoria", "nome", "indirizzo", "telefono", "maps_url"],
        hide_index=True,
        width="stretch",
    )
    st.caption("In cima: lead \"Da chiamare\" e \"Richiamare\". Clicca sullo stato per cambiarlo, sulla colonna \"Richiama il\" per fissare il richiamo.")

    st.sidebar.divider()

    csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.sidebar.download_button(
        "Esporta risultati in CSV",
        data=csv,
        file_name="risultati_places.csv",
        mime="text/csv",
        disabled=filtered.empty,
        width="stretch",
    )

    if filtered.empty:
        st.warning("Nessun risultato corrisponde ai filtri selezionati.")


def dashboard_page(data: pd.DataFrame) -> None:
    if data.empty:
        st.info("Nessun dato disponibile.")
        return

    totale = len(data)
    chiamati = int(data["Stato"].ne("Da chiamare").sum())
    chiusi = int((data["Stato"] == "Chiuso").sum())
    da_richiamare = int((data["Stato"] == "Richiamare").sum())
    tasso = (chiusi / chiamati * 100) if chiamati else 0.0

    section("Panoramica")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Totale lead", totale)
    m2.metric("Chiamati", chiamati)
    m3.metric("Tasso di conversione", f"{tasso:.1f}%")
    m4.metric("Da richiamare", da_richiamare)

    counts = data["Stato"].value_counts().reindex(STATI, fill_value=0)

    donut_col, list_col = st.columns([1, 1.4])
    with donut_col:
        section("Distribuzione stati")
        fig_donut = px.pie(
            names=counts.index,
            values=counts.values,
            hole=0.62,
            color=counts.index,
            color_discrete_map=STATO_COLORS,
        )
        fig_donut.update_traces(
            textinfo="value",
            textfont_color="#e6edf7",
            hovertemplate="%{label}<br>%{value} lead (%{percent})<extra></extra>",
        )
        fig_donut.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=True,
            legend=dict(orientation="h", font=dict(color="#cdd6e4", size=12)),
            height=360,
            transition={"duration": 500, "easing": "cubic-in-out"},
        )
        st.plotly_chart(fig_donut, width="stretch", config={"displayModeBar": False})

    with list_col:
        section("Stato del funnel")
        funnel_items = [
            ("Da chiamare", counts["Da chiamare"], "phone"),
            ("Chiamato - interessato", counts["Chiamato - interessato"], "trend"),
            ("Chiamato - rifiutato", counts["Chiamato - rifiutato"], "rotate"),
            ("Richiamare", counts["Richiamare"], "rotate"),
            ("Chiuso", counts["Chiuso"], "check"),
        ]
        render_kpi_row(
            [
                kpi_card(stato, f"{int(value)}", STATO_COLORS[stato], icon)
                for stato, value, icon in funnel_items
            ]
        )

    section("Lead per categoria e stato")
    chart_data = data.copy()
    chart_data["categoria_breve"] = chart_data["categoria"].str.split(" a ").str[0]
    pivot = (
        chart_data.pivot_table(
            index="categoria_breve",
            columns="Stato",
            values="chiave",
            aggfunc="count",
            fill_value=0,
        )
        .reindex(columns=STATI, fill_value=0)
    )
    fig_bar = px.bar(
        pivot,
        barmode="group",
        color_discrete_map=STATO_COLORS,
        labels={"value": "Lead", "variable": "Stato", "index": "Categoria"},
    )
    fig_bar.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="Stato",
        font=dict(color="#cdd6e4"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
        height=440,
        transition={"duration": 500, "easing": "cubic-in-out"},
    )
    fig_bar.update_traces(marker_line_width=0, opacity=0.92)
    st.plotly_chart(fig_bar, width="stretch", config={"displayModeBar": False})

    section("Attività nel tempo")
    days = data.dropna(subset=["data_aggiornamento"]).copy()
    if days.empty:
        st.info("Nessun cambio di stato registrato finora.")
    else:
        days["giorno"] = pd.to_datetime(days["data_aggiornamento"]).dt.normalize()
        daily = (
            days.groupby("giorno")
            .size()
            .reset_index(name="cambi")
            .sort_values("giorno")
        )
        full_range = pd.date_range(daily["giorno"].min(), daily["giorno"].max(), freq="D")
        daily = daily.set_index("giorno").reindex(full_range, fill_value=0).reset_index()
        daily.columns = ["giorno", "cambi"]
        fig_line = px.line(
            daily,
            x="giorno",
            y="cambi",
            markers=True,
            labels={"giorno": "Data", "cambi": "Cambi di stato"},
        )
        fig_line.update_traces(
            line_color="#22d3ee",
            marker=dict(color="#4facfe", size=8, line=dict(width=1, color="#22d3ee")),
            line_shape="spline",
            fill="tozeroy",
            fillcolor="rgba(34,211,238,0.08)",
        )
        fig_line.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#cdd6e4"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
            height=400,
            transition={"duration": 500, "easing": "cubic-in-out"},
        )
        st.plotly_chart(fig_line, width="stretch", config={"displayModeBar": False})


def main() -> None:
    st.set_page_config(page_title="Agent Locali", layout="wide")
    inject_css()

    with st.sidebar:
        render_brand()

    full = load_data(tuple(CATEGORIES), DATA_VERSION)
    if full.empty:
        st.info("Nessun dato trovato. Controlla la chiave API di Google Places.")
        return
    full = apply_stati(full.copy())

    refresh_choice = read_qp("refresh", "5s")
    refresh_choice = refresh_choice if refresh_choice in REFRESH_MAP else "5s"
    refresh_interval = REFRESH_MAP.get(st.session_state.get("refresh_widget", refresh_choice))
    if refresh_interval:
        st_autorefresh(interval=refresh_interval, key="global_refresh")

    render_hero(datetime.now().strftime("%H:%M"))

    tab_index = 1 if read_qp("tab", "0") == "1" else 0
    st.session_state["tabs_key"] = tab_index
    tab_lead, tab_dash = st.tabs(["Lead", "Dashboard"], key="tabs_key", on_change=persist_filters)

    with tab_lead:
        leads_page(full)

    with tab_dash:
        dashboard_page(full)


if __name__ == "__main__":
    main()