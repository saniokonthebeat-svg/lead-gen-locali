import os
import sqlite3
import sys
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

CATEGORIES = [
    "ristoranti a Altamura",
    "hotel a Altamura",
    "bar a Altamura",
    "parrucchieri a Altamura",
    "studi dentistici a Altamura",
    "panifici a Altamura",
    "farmacie a Altamura",
    "palestre a Altamura",
    "agriturismo a Altamura",
    "autofficine a Altamura",
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


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, sans-serif;
        }

        .stApp {
            background: linear-gradient(135deg, #0b1020 0%, #141a33 35%, #0e2a47 70%, #0b1020 100%);
            background-size: 300% 300%;
            animation: bgShift 18s ease infinite;
        }
        @keyframes bgShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        h1 {
            background: linear-gradient(90deg, #4facfe, #00f2fe, #a78bfa, #4facfe);
            background-size: 300% 100%;
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: titleFlow 6s ease infinite, fadeIn .8s ease;
        }
        @keyframes titleFlow {
            0% { background-position: 0% 50%; }
            100% { background-position: 300% 50%; }
        }

        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(14px); }
            to { opacity: 1; transform: none; }
        }
        @keyframes pulseGlow {
            0%, 100% { box-shadow: 0 0 0 0 rgba(79, 172, 254, 0.0); }
            50% { box-shadow: 0 0 24px 2px rgba(79, 172, 254, 0.35); }
        }

        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 16px;
            padding: 14px 16px;
            backdrop-filter: blur(10px);
            transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
            animation: fadeUp .6s ease both;
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-4px);
            border-color: rgba(79, 172, 254, 0.6);
            box-shadow: 0 10px 32px rgba(0, 0, 0, 0.45);
        }
        [data-testid="stMetric"]:has(div:first-child div[data-testid="stMetricValue"]) {
            animation: fadeUp .6s ease both, pulseGlow 3s ease infinite;
        }

        [data-testid="stExpander"] {
            border-radius: 14px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(8px);
            transition: border-color .25s ease, transform .2s ease;
            animation: fadeIn .5s ease both;
        }
        [data-testid="stExpander"]:hover {
            border-color: rgba(79, 172, 254, 0.5);
        }

        .stButton > button, .stDownloadButton > button {
            border-radius: 12px;
            background: linear-gradient(135deg, #4facfe, #00f2fe);
            color: #0b1020;
            font-weight: 700;
            border: none;
            transition: transform .2s ease, box-shadow .2s ease, filter .2s ease;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            transform: scale(1.04);
            box-shadow: 0 6px 22px rgba(0, 242, 254, 0.45);
            filter: brightness(1.08);
        }

        [data-testid="stSidebar"] {
            background: rgba(13, 17, 38, 0.85);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(12px);
        }

        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 8px;
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            border-radius: 12px;
            padding: 8px 20px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: all .25s ease;
        }
        [data-testid="stTabs"] [data-baseweb="tab"]:hover {
            border-color: rgba(0, 242, 254, 0.6);
            transform: translateY(-2px);
        }
        [data-testid="stTabs"] [aria-selected="true"] {
            background: linear-gradient(135deg, #4facfe, #00f2fe);
            color: #0b1020;
            font-weight: 700;
        }

        [data-testid="stDataFrame"] {
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: rgba(255, 255, 255, 0.03); }
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #4facfe, #00f2fe);
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def search_all_categories(categories: list[str]) -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    results: list[dict] = []
    for category in categories:
        response = requests.post(URL, json={"textQuery": category}, headers=headers)
        response.raise_for_status()
        for place in response.json().get("places", []):
            rating_count = place.get("userRatingCount") or 0
            nome = place.get("displayName", {}).get("text", "N/D")
            indirizzo = place.get("formattedAddress", "N/D")
            place_id = place.get("id") or ""
            chiave = place_id or f"{nome}|{indirizzo}"
            results.append(
                {
                    "categoria": category,
                    "nome": nome,
                    "indirizzo": indirizzo,
                    "telefono": place.get("internationalPhoneNumber", "N/D"),
                    "website": place.get("websiteUri") or "",
                    "ha_sito": "SÌ" if place.get("websiteUri") else "NO",
                    "rating": place.get("rating") or "",
                    "ha_recensioni": "SÌ" if rating_count > 0 else "NO",
                    "place_id": place_id,
                    "chiave": chiave,
                }
            )
    return results


@st.cache_data(show_spinner="Cerco attività su Google Places...")
def load_data(categories_tuple: tuple[str]) -> pd.DataFrame:
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
    qp["categorie"] = ",".join(st.session_state.get("cat_widget", []))
    qp["sito"] = str(st.session_state.get("sito_widget", "Tutti"))
    qp["cerca"] = str(st.session_state.get("cerca_widget", ""))
    qp["stati"] = ",".join(st.session_state.get("stati_widget", []))
    qp["refresh"] = str(st.session_state.get("refresh_widget", "5s"))
    qp["tab"] = str(st.session_state.get("tabs_key", 0))


def leads_page(full: pd.DataFrame, selected_categories: list[str]) -> None:
    st.sidebar.header("Filtri")

    default_categories = [c for c in CATEGORIES if c in read_qp("categorie", "").split(",")] or CATEGORIES
    sito_options = ["Tutti", "Solo con sito", "Solo senza sito"]
    default_sito = read_qp("sito", "Tutti")
    default_sito = default_sito if default_sito in sito_options else "Tutti"
    default_cerca = read_qp("cerca", "")
    default_stati = [s for s in STATI if s in read_qp("stati", "").split(",")] or STATI

    selected_categories = st.sidebar.multiselect(
        "Categorie",
        options=CATEGORIES,
        default=default_categories,
        key="cat_widget",
        on_change=persist_filters,
    )

    site_filter = st.sidebar.radio(
        "Presenza sito web",
        options=sito_options,
        index=sito_options.index(default_sito),
        key="sito_widget",
        on_change=persist_filters,
    )

    search_text = st.sidebar.text_input(
        "Cerca per nome",
        placeholder="Es. pizzeria...",
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

    refresh_default = read_qp("refresh", "5s")
    refresh_default = refresh_default if refresh_default in REFRESH_OPTIONS else "5s"
    st.sidebar.selectbox(
        "Auto-aggiornamento",
        options=REFRESH_OPTIONS,
        index=REFRESH_OPTIONS.index(refresh_default),
        key="refresh_widget",
        on_change=persist_filters,
    )

    selected = full[full["categoria"].isin(selected_categories)].copy() if selected_categories else full.copy()

    if selected.empty:
        st.info("Nessun lead per i filtri selezionati.")
        return

    filtered = selected.copy()
    if site_filter == "Solo con sito":
        filtered = filtered[filtered["ha_sito"] == "SÌ"]
    elif site_filter == "Solo senza sito":
        filtered = filtered[filtered["ha_sito"] == "NO"]

    if search_text:
        filtered = filtered[filtered["nome"].str.contains(search_text, case=False, na=False)]

    if selected_stati:
        filtered = filtered[filtered["Stato"].isin(selected_stati)]

    priority = {"Da chiamare": 0, "Richiamare": 1}
    filtered["_prio"] = filtered["Stato"].map(priority).fillna(2)
    filtered = filtered.sort_values("_prio", kind="stable").drop(columns="_prio")

    st.metric("Risultati mostrati", len(filtered))

    st.session_state["editor_keys"] = filtered["chiave"].tolist()

    st.data_editor(
        filtered[["categoria", "nome", "indirizzo", "telefono", "ha_sito", "maps_url", "Stato", "richiama_il"]],
        key="stato_editor",
        on_change=on_stato_edit,
        column_config={
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
        disabled=["categoria", "nome", "indirizzo", "telefono", "ha_sito", "maps_url"],
        hide_index=True,
        use_container_width=True,
    )

    st.sidebar.divider()

    csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.sidebar.download_button(
        "Esporta risultati in CSV",
        data=csv,
        file_name="risultati_places.csv",
        mime="text/csv",
        disabled=filtered.empty,
    )

    if filtered.empty:
        st.warning("Nessun risultato corrisponde ai filtri selezionati.")


def dashboard_page(data: pd.DataFrame) -> None:
    if data.empty:
        st.info("Nessun dato disponibile. Fai una ricerca nella pagina Lead.")
        return

    totale = len(data)
    chiamati = int(data["Stato"].ne("Da chiamare").sum())
    chiusi = int((data["Stato"] == "Chiuso").sum())
    da_richiamare = int((data["Stato"] == "Richiamare").sum())
    tasso = (chiusi / chiamati * 100) if chiamati else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Totale lead", totale)
    m2.metric("Chiamati", chiamati)
    m3.metric("Tasso di conversione", f"{tasso:.1f}%")
    m4.metric("Da richiamare", da_richiamare)

    st.markdown("### Contatori per stato")
    counts = data["Stato"].value_counts().reindex(STATI, fill_value=0)
    stato_cols = st.columns(len(STATI))
    for col, (stato, value) in zip(stato_cols, counts.items()):
        col.metric(stato, int(value))

    st.markdown("### Lead per categoria e stato")
    chart_data = data.copy()
    chart_data["categoria_breve"] = chart_data["categoria"].str.replace(" a Altamura", "", regex=False)
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
        height=420,
        transition={"duration": 500, "easing": "cubic-in-out"},
    )
    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

    st.markdown("### Cambi di stato per giorno")
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
            line_color="#00f2fe",
            marker=dict(color="#4facfe", size=8),
            line_shape="spline",
        )
        fig_line.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=400,
            transition={"duration": 500, "easing": "cubic-in-out"},
        )
        st.plotly_chart(fig_line, use_container_width=True, config={"displayModeBar": False})


def main() -> None:
    st.set_page_config(page_title="Lead Gen Locali", layout="wide")
    inject_css()
    st.title("Lead Gen Locali — Altamura")

    full = load_data(tuple(CATEGORIES))
    if full.empty:
        st.info("Nessun dato trovato. Controlla la chiave API di Google Places.")
        return
    full = apply_stati(full.copy())

    refresh_choice = read_qp("refresh", "5s")
    refresh_choice = refresh_choice if refresh_choice in REFRESH_MAP else "5s"
    refresh_interval = REFRESH_MAP.get(st.session_state.get("refresh_widget", refresh_choice))
    if refresh_interval:
        st_autorefresh(interval=refresh_interval, key="global_refresh")

    tab_index = 1 if read_qp("tab", "0") == "1" else 0
    st.session_state["tabs_key"] = tab_index
    tab_lead, tab_dash = st.tabs(["Lead", "Dashboard"], key="tabs_key", on_change=persist_filters)

    with tab_lead:
        leads_page(full, CATEGORIES)

    with tab_dash:
        dashboard_page(full)


if __name__ == "__main__":
    main()