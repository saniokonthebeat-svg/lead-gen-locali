import os
import sqlite3
import urllib.parse
import json
from datetime import datetime
from html import escape as esc

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
    "dots": '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="12" cy="19" r="1.7"/></svg>',
    "copy": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    "trash": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
    "calendar": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    "pin": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
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
        .kpi .num { display: inline-block; }
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

        /* ==========================================================
           LAYER ANIMAZIONI DINAMICHE
           ========================================================== */

        /* ----- Sfere di luce ambientali che fluttuano ----- */
        .stApp::before, .stApp::after {
            content: ""; position: fixed; z-index: 0; pointer-events: none;
            border-radius: 50%; filter: blur(90px);
        }
        .stApp::before {
            width: 520px; height: 520px; top: -160px; right: -140px;
            background: radial-gradient(circle, rgba(79, 172, 254, 0.5), transparent 70%);
            animation: orbA 12s ease-in-out infinite alternate;
        }
        .stApp::after {
            width: 460px; height: 460px; bottom: -180px; left: -140px;
            background: radial-gradient(circle, rgba(167, 139, 250, 0.45), transparent 70%);
            animation: orbB 16s ease-in-out infinite alternate;
        }
        @keyframes orbA { from { transform: translate(0, 0) scale(1); } to { transform: translate(-70px, 50px) scale(1.18); } }
        @keyframes orbB { from { transform: translate(0, 0) scale(1); } to { transform: translate(80px, -60px) scale(1.22); } }

        /* ----- Hero ----- */
        .hero .badge { animation: fadeIn .6s ease both, badgeFloat 5s ease-in-out infinite alternate; }
        @keyframes badgeFloat { from { transform: translateY(0); } to { transform: translateY(-3px); } }
        .hero h1 { animation: titleFlow 8s linear infinite, fadeUp .6s ease both; }
        .hero p { animation: fadeUp .7s .08s ease both, pFade 6s ease-in-out infinite alternate; }
        @keyframes pFade { from { opacity: .9; } to { opacity: 1; } }

        /* ----- KPI: ingresso a cascata + valore "pop" ----- */
        .kpi-grid .kpi { animation: fadeUp .55s cubic-bezier(.16, 1, .3, 1) both; }
        .kpi-grid .kpi:nth-child(1) { animation-delay: .04s; }
        .kpi-grid .kpi:nth-child(2) { animation-delay: .12s; }
        .kpi-grid .kpi:nth-child(3) { animation-delay: .20s; }
        .kpi-grid .kpi:nth-child(4) { animation-delay: .28s; }
        .kpi-grid .kpi:nth-child(5) { animation-delay: .36s; }
        .kpi-grid .kpi:nth-child(6) { animation-delay: .44s; }
        .kpi .value { animation: valuePop .6s cubic-bezier(.16, 1, .3, 1) both; }
        @keyframes valuePop { 0% { transform: scale(.55); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }

        /* ----- KPI: micro-tilt 3D al hover (expo.out) ----- */
        .kpi-grid { perspective: 900px; }
        .kpi { transform-style: preserve-3d; transition: transform .35s cubic-bezier(.16, 1, .3, 1), border-color .22s ease, box-shadow .22s ease; }
        .kpi:hover { transform: translateY(-6px) rotateX(3deg) rotateY(-3deg); }

        /* ----- KPI: riflesso luminoso periodico ----- */
        .kpi::after {
            content: ""; position: absolute; inset: 0; pointer-events: none;
            background: linear-gradient(115deg, transparent 30%, rgba(255, 255, 255, 0.07) 45%, rgba(255, 255, 255, 0.16) 50%, rgba(255, 255, 255, 0.07) 55%, transparent 70%);
            background-size: 250% 100%;
            animation: shimmer 3.2s ease-in-out infinite;
        }
        @keyframes shimmer { 0%, 55% { background-position: 120% 0; } 100% { background-position: -120% 0; } }

        /* ----- KPI: barra accento in scansione continua ----- */
        .kpi::before {
            content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
            background: linear-gradient(90deg, transparent, var(--acc), transparent);
            background-size: 220% 100%;
            animation: topScan 3.2s ease-in-out infinite;
        }
        @keyframes topScan { 0%, 100% { background-position: 220% 0; } 50% { background-position: -220% 0; } }

        /* ----- KPI: barra di avanzamento sotto il valore ----- */
        .kpi-bar { height: 4px; margin-top: 12px; border-radius: 4px; background: rgba(255, 255, 255, 0.08); overflow: hidden; }
        .kpi-bar span { display: block; height: 100%; width: 0; border-radius: 4px; background: linear-gradient(90deg, var(--acc), #ffffff); animation: fillBar 1.3s .35s cubic-bezier(.16, 1, .3, 1) forwards; }
        @keyframes fillBar { to { width: var(--w, 0%); } }

        /* ----- Barra in cima alla pagina: luce che scorre in continuo ----- */
        .topbar { position: fixed; top: 0; left: 0; right: 0; height: 4px; z-index: 999; pointer-events: none; overflow: hidden; }
        .topbar::after { content: ""; position: absolute; top: 0; bottom: 0; width: 35%; background: linear-gradient(90deg, transparent, #22d3ee, #a78bfa, #4facfe, transparent); animation: topbarSweep 2.4s linear infinite; }
        @keyframes topbarSweep { from { left: -35%; } to { left: 100%; } }

        /* ----- Layer ambientale: sfere + particelle ----- */
        .fx { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
        .fx .o { position: absolute; border-radius: 50%; filter: blur(70px); }
        .fx .orb3 { width: 360px; height: 360px; top: 34%; left: 52%; background: radial-gradient(circle, rgba(34, 211, 238, 0.32), transparent 70%); animation: orbC 14s ease-in-out infinite alternate; }
        @keyframes orbC { from { transform: translate(0, 0) scale(1); } to { transform: translate(-140px, 100px) scale(1.35); } }
        .fx .px { position: absolute; bottom: -14px; width: 9px; height: 9px; border-radius: 50%; animation: floatUp linear infinite; }
        .fx .p-cyan { background: #22d3ee; box-shadow: 0 0 14px rgba(34, 211, 238, 0.9); }
        .fx .p-violet { background: #a78bfa; box-shadow: 0 0 14px rgba(167, 139, 250, 0.9); }
        .fx .p-slate { background: #94a3b8; box-shadow: 0 0 10px rgba(148, 163, 184, 0.8); }
        .fx .p1 { left: 4%; animation-duration: 9s; }
        .fx .p2 { left: 12%; animation-duration: 13s; animation-delay: 2.2s; }
        .fx .p3 { left: 20%; animation-duration: 11s; animation-delay: 0.8s; }
        .fx .p4 { left: 29%; animation-duration: 15s; animation-delay: 3.4s; }
        .fx .p5 { left: 37%; animation-duration: 12s; animation-delay: 1.6s; }
        .fx .p6 { left: 45%; animation-duration: 16s; animation-delay: 4.1s; }
        .fx .p7 { left: 53%; animation-duration: 10s; animation-delay: 2.8s; }
        .fx .p8 { left: 61%; animation-duration: 14s; animation-delay: 0.4s; }
        .fx .p9 { left: 69%; animation-duration: 12.5s; animation-delay: 3.8s; }
        .fx .p10 { left: 77%; animation-duration: 17s; animation-delay: 1.2s; }
        .fx .p11 { left: 85%; animation-duration: 11.5s; animation-delay: 5s; }
        .fx .p12 { left: 93%; animation-duration: 14.5s; animation-delay: 2.4s; }
        .fx .p13 { left: 97%; animation-duration: 10.5s; animation-delay: 4.6s; }
        @keyframes floatUp { 0% { transform: translateY(0); opacity: 0; } 12% { opacity: 1; } 85% { opacity: .6; } 100% { transform: translateY(-108vh); opacity: 0; } }

        /* ----- Brand: respiro del logo ----- */
        .brand .mark { animation: brandBreathe 4s ease-in-out infinite; }
        @keyframes brandBreathe { 0%, 100% { box-shadow: 0 8px 22px -6px rgba(79, 172, 254, .6); transform: scale(1); } 50% { box-shadow: 0 8px 32px -4px rgba(34, 211, 238, .85); transform: scale(1.05); } }

        /* ----- Titoli sezione: glow pulsante ----- */
        .section-head .glow { animation: glowPulse 3.2s ease-in-out infinite; }
        @keyframes glowPulse { 0%, 100% { box-shadow: 0 0 8px rgba(34, 211, 238, .35); } 50% { box-shadow: 0 0 22px rgba(34, 211, 238, .8); } }

        /* ----- Tab attivo: pop d'ingresso ----- */
        [data-testid="stTabs"] [aria-selected="true"] { animation: tabPop .35s cubic-bezier(.16, 1, .3, 1); }
        @keyframes tabPop { 0% { transform: scale(.94); } 60% { transform: scale(1.04); } 100% { transform: scale(1); } }

        /* ----- Tabella: alone luminoso pulsante ----- */
        [data-testid="stDataFrame"] {
            animation: fadeUp .6s .05s ease both, tableGlow 6s ease-in-out infinite;
        }
        @keyframes tableGlow {
            0%, 100% { box-shadow: 0 24px 70px -34px rgba(0, 0, 0, .85), 0 0 0 rgba(34, 211, 238, 0); }
            50% { box-shadow: 0 24px 70px -34px rgba(0, 0, 0, .85), 0 0 36px -6px rgba(34, 211, 238, .38); }
        }

        /* ----- Metriche dashboard: ingresso scalato ----- */
        [data-testid="stHorizontalBlock"] > div:nth-child(1) [data-testid="stMetric"] { animation-delay: .05s; }
        [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stMetric"] { animation-delay: .15s; }
        [data-testid="stHorizontalBlock"] > div:nth-child(3) [data-testid="stMetric"] { animation-delay: .25s; }
        [data-testid="stHorizontalBlock"] > div:nth-child(4) [data-testid="stMetric"] { animation-delay: .35s; }

        /* ----- Bottone: riflesso che attraversa ----- */
        .stButton > button, .stDownloadButton > button { position: relative; overflow: hidden; }
        .stButton > button::after, .stDownloadButton > button::after {
            content: ""; position: absolute; top: 0; left: -130%; width: 55%; height: 100%;
            background: linear-gradient(115deg, transparent, rgba(255, 255, 255, 0.55), transparent);
            transform: skewX(-20deg);
            animation: btnShine 4.5s ease-in-out infinite;
        }
        @keyframes btnShine { 0%, 70% { left: -130%; } 100% { left: 140%; } }

        /* ----- Reveal allo scroll (progressivo, solo se supportato) ----- */
        @supports (animation-timeline: view()) {
            .section-head {
                animation: revealIn linear both;
                animation-timeline: view();
                animation-range: entry 0% entry 28%;
            }
            .kpi-grid { animation: revealIn linear both; animation-timeline: view(); animation-range: entry 0% entry 22%; }
            [data-testid="stDataFrame"] { animation: tableGlow 6s ease-in-out infinite, revealIn linear both; animation-timeline: view(); animation-range: entry 0% entry 16%; }
        }
        @keyframes revealIn { from { opacity: 0; transform: translateY(26px); } to { opacity: 1; transform: none; } }

        /* ==========================================================
           TABELLA LEAD PERSONALIZZATA + MENU CONTESTO
           ========================================================== */
        .lead-table {
            border: 1px solid var(--border); border-radius: 16px; overflow: hidden;
            box-shadow: 0 24px 70px -34px rgba(0, 0, 0, .85);
            background: rgba(10, 16, 34, .72); backdrop-filter: blur(10px);
            animation: fadeUp .55s .05s cubic-bezier(.16, 1, .3, 1) both;
        }
        .lt-scroll { max-height: 72vh; overflow: auto; }
        .lt-head, .lt-row {
            display: grid;
            grid-template-columns: minmax(230px, 2.6fr) 1.35fr 1.15fr .7fr 1fr .5fr;
            gap: 12px; align-items: center; padding: 11px 18px;
        }
        .lt-head {
            position: sticky; top: 0; z-index: 3;
            background: rgba(13, 20, 40, .98);
            color: var(--muted); font-size: .72rem; font-weight: 700;
            text-transform: uppercase; letter-spacing: .09em; border-bottom: 1px solid var(--border);
        }
        .lt-row { border-bottom: 1px solid rgba(255, 255, 255, 0.05); cursor: context-menu; transition: background .18s ease; position: relative; }
        .lt-row:last-child { border-bottom: none; }
        .lt-row:hover { background: rgba(255, 255, 255, 0.035); }
        .lt-row.removing { opacity: 0; transform: translateX(14px); transition: opacity .4s ease, transform .4s ease; }
        .lt-cell { min-width: 0; color: var(--text); font-size: .9rem; }
        .lt-nome b { display: block; font-size: .95rem; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .lt-sub { display: block; color: var(--muted); font-size: .76rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .lt-tel a, .lt-map-link { color: var(--cyan); text-decoration: none; font-size: .9rem; }
        .lt-tel a:hover, .lt-map-link:hover { text-decoration: underline; }
        .pill {
            display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px;
            font-size: .76rem; font-weight: 700; white-space: nowrap;
        }
        .pill::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
        .lt-rich { color: var(--amber); font-size: .85rem; font-weight: 600; }
        .lt-more { text-align: right; }
        .lt-more-btn {
            width: 32px; height: 32px; border-radius: 9px; border: 1px solid var(--border);
            background: rgba(255, 255, 255, 0.04); color: var(--muted); cursor: pointer;
            display: inline-grid; place-items: center; transition: all .18s ease;
        }
        .lt-more-btn:hover { color: #fff; border-color: rgba(79, 172, 254, .5); background: rgba(79, 172, 254, .12); }
        .lt-more-btn svg { width: 16px; height: 16px; }

        /* ----- Menu contesto ----- */
        .lt-menu {
            position: fixed; z-index: 10000; min-width: 232px; display: none;
            background: #0f1a30; border: 1px solid var(--border); border-radius: 13px;
            box-shadow: 0 22px 64px -18px rgba(0, 0, 0, .95);
            padding: 6px; animation: fadeIn .14s ease both;
        }
        .lt-menu .mi {
            display: flex; align-items: center; gap: 11px; padding: 8px 12px;
            border-radius: 9px; cursor: pointer; color: var(--text); font-size: .88rem;
            white-space: nowrap; transition: background .12s ease;
        }
        .lt-menu .mi svg { width: 16px; height: 16px; color: var(--muted); flex: none; }
        .lt-menu .mi:hover { background: rgba(79, 172, 254, .14); color: #fff; }
        .lt-menu .mi:hover svg { color: var(--cyan); }
        .lt-menu .mi.st .m-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; box-shadow: 0 0 8px currentColor; }
        .lt-menu .mi.danger { color: #fda4af; }
        .lt-menu .mi.danger svg { color: #f87171; }
        .lt-menu .mi.danger:hover { background: rgba(248, 113, 113, .16); color: #fff; }
        .lt-menu .mi-sep { height: 1px; background: var(--border); margin: 6px 10px; }
        .lt-panel { display: none; padding: 8px 12px; }
        .lt-panel.open { display: block; }
        .lt-confirm { color: var(--text); font-size: .85rem; margin-bottom: 8px; }
        .lt-confirm-btns { display: flex; gap: 8px; }
        .lt-btn {
            flex: 1; padding: 7px 0; border: 1px solid var(--border); border-radius: 9px;
            background: rgba(255, 255, 255, 0.05); color: var(--text); font-weight: 700; font-size: .8rem; cursor: pointer;
        }
        .lt-btn.ok { background: linear-gradient(135deg, #f87171, #ef4444); border: none; color: #fff; }
        .lt-btn:hover { filter: brightness(1.1); }
        .lt-dt { width: 100%; padding: 7px 9px; border-radius: 9px; border: 1px solid var(--border); background: rgba(255, 255, 255, 0.06); color: #fff; color-scheme: dark; font-size: .85rem; }

        /* ----- Toast ----- */
        .lt-toast {
            position: fixed; bottom: 26px; left: 50%; transform: translateX(-50%);
            background: #0e2a3f; border: 1px solid rgba(34, 211, 238, .45); color: #a5f3fc;
            padding: 10px 20px; border-radius: 12px; font-size: .9rem; z-index: 10001;
            opacity: 0; pointer-events: none; transition: opacity .28s ease; box-shadow: 0 14px 40px -12px rgba(0, 0, 0, .8);
        }
        .lt-toast.show { opacity: 1; }

        @media (prefers-reduced-motion: reduce) {
            .fx .px, .fx .o, .stApp::before, .stApp::after { animation: none !important; }
            .kpi, .kpi-grid, [data-testid="stMetric"] { transition: none !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, accent: str, icon: str, pct: int | None = None) -> str:
    num, sep, rest = value.partition("<em>")
    bar = ""
    if pct is not None:
        bar = f'<div class="kpi-bar"><span style="--w:{max(0, min(100, pct)):.0f}%"></span></div>'
    return (
        f'<div class="kpi" style="--acc:{accent}" data-label="{label}">'
        f'<div class="icon">{ICONS[icon]}</div>'
        f'<div class="label">{label}</div>'
        f'<div class="value"><span class="num" data-count="{num.strip()}">{num.strip()}</span>{sep}{rest}</div>'
        f"{bar}"
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
    conn.execute(
        "CREATE TABLE IF NOT EXISTS lead_esclusi (chiave TEXT PRIMARY KEY, data TEXT)"
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


def load_esclusi() -> set[str]:
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT chiave FROM lead_esclusi").fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


def exclude_activity(place_id: str, chiave: str) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS lead_esclusi (chiave TEXT PRIMARY KEY, data TEXT)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO lead_esclusi (chiave, data) VALUES (?, ?)",
            (chiave or place_id, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


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
    esclusi = load_esclusi()
    if esclusi:
        data = data[~data["chiave"].isin(esclusi)]
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


def render_leads_table(data: pd.DataFrame) -> None:
    rows: list[str] = []
    js_rows: list[dict] = []
    for _, r in data.iterrows():
        chiave = str(r.get("chiave", ""))
        place_id = str(r.get("place_id", ""))
        nome = str(r.get("nome", ""))
        indirizzo = str(r.get("indirizzo", ""))
        categoria = str(r.get("categoria", ""))
        telefono = str(r.get("telefono", ""))
        stato = str(r.get("Stato", "Da chiamare"))
        color = STATO_COLORS.get(stato, "#94a3b8")
        maps_url = str(r.get("maps_url", ""))
        rich = r.get("richiama_il")
        rich_txt = ""
        if pd.notna(rich):
            try:
                rich_txt = pd.to_datetime(rich).strftime("%d/%m/%Y %H:%M")
            except Exception:
                rich_txt = ""

        pill = f'<span class="pill" style="color:{color}">{esc(stato)}</span>'
        rich_cell = f'<span class="lt-rich">{esc(rich_txt)}</span>' if rich_txt else "<span class='lt-muted'>—</span>"
        tel_cell = (
            f'<a href="tel:{esc(telefono)}">{esc(telefono)}</a>'
            if telefono and telefono != "N/D"
            else "<span class='lt-muted'>N/D</span>"
        )
        cat_cell = f"<span class='lt-sub'>{esc(categoria)}</span>" if categoria else ""

        rows.append(
            f'<div class="lt-row" data-chiave="{esc(chiave)}" data-place="{esc(place_id)}">'
            f'<div class="lt-cell lt-nome"><b>{esc(nome)}</b>{cat_cell}</div>'
            f'<div class="lt-cell lt-addr">{esc(indirizzo)}</div>'
            f'<div class="lt-cell lt-tel">{tel_cell}</div>'
            f'<div class="lt-cell">{pill}</div>'
            f'<div class="lt-cell">{rich_cell}</div>'
            f'<div class="lt-cell lt-more"><button class="lt-more-btn" title="Azioni">{ICONS["dots"]}</button></div>'
            "</div>"
        )
        js_rows.append(
            {
                "chiave": chiave,
                "place_id": place_id,
                "nome": nome,
                "indirizzo": indirizzo,
                "telefono": telefono,
                "stato": stato,
                "maps_url": maps_url,
            }
        )

    rows_html = "\n".join(rows)
    js_data = json.dumps(js_rows, ensure_ascii=False)
    stati_js = json.dumps(STATI, ensure_ascii=False)
    stati_colors = json.dumps(STATO_COLORS, ensure_ascii=False)

    st.html(
        f"""
        <div class="lead-table">
            <div class="lt-scroll">
                <div class="lt-head">
                    <div>Attività</div><div>Indirizzo</div><div>Telefono</div><div>Stato</div><div>Richiama il</div><div></div>
                </div>
                {rows_html}
            </div>
        </div>
        <div class="lt-menu" id="lt-menu"></div>
        <div class="lt-toast" id="lt-toast"></div>
        <script>
        (function () {{
            var DATA = {js_data};
            var STATI = {stati_js};
            var COLORS = {stati_colors};
            var menu = document.getElementById('lt-menu');
            var toast = document.getElementById('lt-toast');
            var cur = null, curRow = null;

            function escT(s) {{ var d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }}

            function showToast(msg) {{
                toast.textContent = msg;
                toast.classList.add('show');
                clearTimeout(showToast._t);
                showToast._t = setTimeout(function () {{ toast.classList.remove('show'); }}, 2400);
            }}

            function act(payload) {{
                var u = new URL(window.location.href);
                u.searchParams.set('ctx', payload);
                window.location.href = u.toString();
            }}

            function findRow(r) {{ return r && r.closest && r.closest('.lt-row'); }}

            function openMenu(row, x, y) {{
                curRow = row;
                cur = DATA.find(function (d) {{ return d.chiave === row.getAttribute('data-chiave'); }}) || null;
                var mw = 252;
                var mh = 420;
                if (x + mw > window.innerWidth - 8) x = window.innerWidth - mw - 8;
                if (y + mh > window.innerHeight - 8) y = window.innerHeight - mh - 8;
                if (x < 8) x = 8; if (y < 8) y = 8;

                var html = '';
                html += '<div class="mi" data-a="maps">' + ICONS_PIN + '<span>' + escT(cur.nome) + '</span></div>';
                html += '<div class="mi" data-a="tel">' + ICONS_PHONE + '<span>Chiama ' + escT(cur.telefono) + '</span></div>';
                html += '<div class="mi" data-a="copyn">' + ICONS_COPY + '<span>Copia nome</span></div>';
                html += '<div class="mi" data-a="copyi">' + ICONS_COPY + '<span>Copia indirizzo</span></div>';
                html += '<div class="mi" data-a="copyt">' + ICONS_COPY + '<span>Copia telefono</span></div>';
                html += '<div class="mi-sep"></div>';
                html += '<div class="mi st" data-a="st|Da chiamare"><span class="m-dot" style="color:' + COLORS['Da chiamare'] + '"></span><span>Da chiamare</span></div>';
                html += '<div class="mi st" data-a="st|Chiamato - interessato"><span class="m-dot" style="color:' + COLORS['Chiamato - interessato'] + '"></span><span>Interessato</span></div>';
                html += '<div class="mi st" data-a="st|Chiamato - rifiutato"><span class="m-dot" style="color:' + COLORS['Chiamato - rifiutato'] + '"></span><span>Rifiutato</span></div>';
                html += '<div class="mi st" data-a="st|Richiamare"><span class="m-dot" style="color:' + COLORS['Richiamare'] + '"></span><span>Richiamare</span></div>';
                html += '<div class="mi st" data-a="st|Chiuso"><span class="m-dot" style="color:' + COLORS['Chiuso'] + '"></span><span>Chiuso</span></div>';
                html += '<div class="mi-sep"></div>';
                html += '<div class="mi" data-a="rc">' + ICONS_CAL + '<span>Fissa richiamo…</span></div>';
                html += '<div class="mi-sep"></div>';
                html += '<div class="mi danger" data-a="rem">' + ICONS_TRASH + '<span>Rimuovi attività</span></div>';

                menu.innerHTML = html;
                menu.style.display = 'block';
                menu.style.left = x + 'px';
                menu.style.top = y + 'px';
                menu.setAttribute('data-open', '1');
            }}

            function closeMenu() {{
                menu.style.display = 'none';
                menu.removeAttribute('data-open');
            }}

            function copyText(txt) {{
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(txt).then(function () {{ showToast('Copiato: ' + txt); }});
                }} else {{
                    var ta = document.createElement('textarea');
                    ta.value = txt; document.body.appendChild(ta); ta.select();
                    try {{ document.execCommand('copy'); showToast('Copiato: ' + txt); }} catch (e) {{}}
                    document.body.removeChild(ta);
                }}
            }}

            document.addEventListener('contextmenu', function (e) {{
                var row = findRow(e.target);
                if (row) {{
                    e.preventDefault();
                    openMenu(row, e.clientX, e.clientY);
                }} else {{
                    closeMenu();
                }}
            }});

            document.addEventListener('click', function (e) {{
                var btn = e.target.closest('.lt-more-btn');
                if (btn) {{
                    var row = findRow(btn);
                    var r = row.getBoundingClientRect();
                    openMenu(row, r.right - 252, r.top + 12);
                    return;
                }}
                if (menu.getAttribute('data-open') && !menu.contains(e.target)) closeMenu();
                var a2 = e.target.closest('[data-a2]');
                if (a2) {{
                    if (a2.getAttribute('data-a2') === 'rem') {{
                        act('rem|' + encodeURIComponent(cur.place_id) + '|' + encodeURIComponent(cur.chiave));
                        var row = curRow; if (row) row.classList.add('removing');
                        closeMenu();
                    }} else if (a2.getAttribute('data-a2') === 'no') {{
                        closeMenu();
                    }}
                    return;
                }}
                var mi = e.target.closest('.mi');
                if (!mi || !menu.getAttribute('data-open')) return;
                var a = mi.getAttribute('data-a') || '';
                if (a.indexOf('st|') === 0) {{
                    act('st|' + encodeURIComponent(cur.chiave) + '|' + a.slice(3));
                }} else if (a === 'rem') {{
                    if (menu.querySelector('.lt-confirm')) {{
                        act('rem|' + encodeURIComponent(cur.place_id) + '|' + encodeURIComponent(cur.chiave));
                        var row = curRow; if (row) row.classList.add('removing');
                        closeMenu();
                    }} else {{
                        var conf = '<div class="lt-panel open"><div class="lt-confirm">Rimuovere <b>' + escT(cur.nome) + '</b> dalla lista?</div><div class="lt-confirm-btns"><button class="lt-btn ok" data-a2="rem">Sì, rimuovi</button><button class="lt-btn" data-a2="no">Annulla</button></div></div>';
                        var panel = document.createElement('div'); panel.innerHTML = conf;
                        mi.closest('.mi').insertAdjacentHTML('afterend', panel.innerHTML);
                    }}
                }} else if (a === 'no') {{
                    closeMenu();
                }} else if (a === 'maps') {{
                    window.open(cur.maps_url, '_blank');
                    closeMenu();
                }} else if (a === 'tel') {{
                    window.location.href = 'tel:' + cur.telefono;
                    closeMenu();
                }} else if (a === 'copyn') {{ copyText(cur.nome); closeMenu(); }}
                else if (a === 'copyi') {{ copyText(cur.indirizzo); closeMenu(); }}
                else if (a === 'copyt') {{ copyText(cur.telefono); closeMenu(); }}
                else if (a === 'rc') {{
                    var inp = '<div class="lt-panel open"><input type="datetime-local" class="lt-dt" id="lt-dt" value=""><div style="display:flex;gap:8px;margin-top:8px"><button class="lt-btn ok" id="lt-dt-ok">Salva</button><button class="lt-btn" data-a2="no">Annulla</button></div></div>';
                    mi.closest('.mi').insertAdjacentHTML('afterend', inp);
                    var ok = document.getElementById('lt-dt-ok');
                    if (ok) ok.addEventListener('click', function () {{
                        var v = document.getElementById('lt-dt').value;
                        if (!v) return;
                        act('rc|' + encodeURIComponent(cur.chiave) + '|' + v);
                    }});
                }}
            }});

            document.addEventListener('keydown', function (e) {{ if (e.key === 'Escape') closeMenu(); }});

            var ICONS_PIN = '{ICONS["pin"]}';
            var ICONS_PHONE = '{ICONS["phone"]}';
            var ICONS_COPY = '{ICONS["copy"]}';
            var ICONS_CAL = '{ICONS["calendar"]}';
            var ICONS_TRASH = '{ICONS["trash"]}';
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


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
            kpi_card("Totale lead", f"{totale}<em>sel.</em>", "#4facfe", "globe", pct=100 if totale else 0),
            kpi_card("Da chiamare", f"{da_chiamare}<em>priorità</em>", "#94a3b8", "phone", pct=int(da_chiamare / totale * 100) if totale else 0),
            kpi_card("Interessati", f"{interessati}<em>prossimi</em>", "#4facfe", "trend", pct=int(interessati / totale * 100) if totale else 0),
            kpi_card("Richiamare", f"{richiamare}<em>da riprovare</em>", "#fbbf24", "rotate", pct=int(richiamare / totale * 100) if totale else 0),
            kpi_card("Chiusi", f"{chiusi}<em>vinti</em>", "#34d399", "check", pct=int(chiusi / totale * 100) if totale else 0),
        ]
    )

    render_leads_table(filtered)
    st.caption('Clic destro sulla riga o su "⋮" per azioni. Tasto destro su "Rimuovi attività" toglie il locale dalla lista.')

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
                kpi_card(stato, f"{int(value)}", STATO_COLORS[stato], icon, pct=int(value / totale * 100) if totale else 0)
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

    ctx = read_qp("ctx", "")
    if ctx:
        try:
            parts = ctx.split("|", 2)
            if len(parts) == 3:
                kind, arg1, arg2 = parts
                arg1 = urllib.parse.unquote(arg1)
                arg2 = urllib.parse.unquote(arg2)
                if kind == "rem":
                    exclude_activity(arg1, arg2)
                elif kind == "st" and arg2 in STATI:
                    save_state(arg1, arg2)
                elif kind == "rc" and arg2:
                    save_state(arg1, "Richiamare", arg2)
        except Exception:
            pass
        try:
            st.query_params.pop("ctx", None)
        except Exception:
            pass

    full = apply_stati(full.copy())

    refresh_choice = read_qp("refresh", "5s")
    refresh_choice = refresh_choice if refresh_choice in REFRESH_MAP else "5s"
    refresh_interval = REFRESH_MAP.get(st.session_state.get("refresh_widget", refresh_choice))
    if refresh_interval:
        st_autorefresh(interval=refresh_interval, key="global_refresh")

    render_hero(datetime.now().strftime("%H:%M"))

    st.html(
        """
        <div class="topbar"></div>
        <div class="fx">
            <i class="o orb3"></i>
            <span class="px p-cyan p1"></span><span class="px p-violet p2"></span><span class="px p-slate p3"></span>
            <span class="px p-cyan p4"></span><span class="px p-violet p5"></span><span class="px p-slate p6"></span>
            <span class="px p-cyan p7"></span><span class="px p-violet p8"></span><span class="px p-slate p9"></span>
            <span class="px p-cyan p10"></span><span class="px p-violet p11"></span><span class="px p-slate p12"></span>
            <span class="px p-cyan p13"></span>
        </div>
        <script>
        (function () {
            var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            function animateCount(el, target) {
                var start = performance.now(), dur = 1100;
                function tick(now) {
                    var t = Math.min((now - start) / dur, 1);
                    var eased = 1 - Math.pow(1 - t, 4);
                    el.textContent = Math.round(target * eased);
                    if (t < 1) requestAnimationFrame(tick);
                }
                requestAnimationFrame(tick);
            }
            function pulse(el) {
                el.style.transform = 'scale(1.08)';
                setTimeout(function () { el.style.transform = ''; }, 400);
            }
            function init() {
                var nums = document.querySelectorAll('.kpi .num');
                if (!nums.length) { requestAnimationFrame(init); return; }
                window.__kpiState = window.__kpiState || {};
                nums.forEach(function (el) {
                    var card = el.closest('.kpi');
                    var key = card ? card.getAttribute('data-label') : '';
                    var target = parseInt(el.getAttribute('data-count'), 10) || 0;
                    if (window.__kpiState[key] !== target) {
                        window.__kpiState[key] = target;
                        animateCount(el, target);
                    } else if (!reduce) {
                        pulse(el);
                    }
                });
                if (reduce) return;
                document.querySelectorAll('.kpi').forEach(function (card) {
                    card.addEventListener('mousemove', function (e) {
                        var r = card.getBoundingClientRect();
                        var rx = (e.clientX - r.left) / r.width - 0.5;
                        var ry = (e.clientY - r.top) / r.height - 0.5;
                        card.style.transform = 'translateY(-6px) rotateX(' + (-ry * 6).toFixed(2) + 'deg) rotateY(' + (rx * 6).toFixed(2) + 'deg)';
                    });
                    card.addEventListener('mouseleave', function () { card.style.transform = ''; });
                });
            }
            requestAnimationFrame(init);
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )

    tab_index = 1 if read_qp("tab", "0") == "1" else 0
    st.session_state["tabs_key"] = tab_index
    tab_lead, tab_dash = st.tabs(["Lead", "Dashboard"], key="tabs_key", on_change=persist_filters)

    with tab_lead:
        leads_page(full)

    with tab_dash:
        dashboard_page(full)


if __name__ == "__main__":
    main()