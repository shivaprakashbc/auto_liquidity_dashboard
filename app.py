import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import time

# =====================================
# CONFIG
# =====================================
st.set_page_config(page_title="Liquidity Sweep Dashboard", layout="wide")
APP_PASSWORD = "trade123"   # CHANGE THIS

# =====================================
# PASSWORD
# =====================================
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        password = st.text_input("Enter Password", type="password")
        if st.button("Login"):
            if password == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Wrong Password")
        st.stop()

check_password()

# =====================================
# TITLE
# =====================================
st.title("🚀 Binance Futures Liquidity Sweep Dashboard")
st.caption("Live Scan | Auto Candle Close Scan | Volume Confirmed")

timeframe = st.selectbox("Select Timeframe", ["1h", "4h", "1d"])

# =====================================
# SESSION STATE
# =====================================
if "results" not in st.session_state:
    st.session_state.results = pd.DataFrame()

if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = None

# =====================================
# GET SYMBOLS
# =====================================
@st.cache_data(ttl=3600)
def get_symbols():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

        if "symbols" not in data:
            return []

        return [
            s["symbol"]
            for s in data["symbols"]
            if s.get("contractType") == "PERPETUAL"
            and s.get("status") == "TRADING"
        ]
    except:
        return []

symbols = get_symbols()

# =====================================
# GET KLINES
# =====================================
def get_klines(symbol):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": timeframe, "limit": 4}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        if not isinstance(data, list):
            return None

        df = pd.DataFrame(data, columns=[
            "open_time","open","high","low","close","volume",
            "close_time","qav","trades","taker_base","taker_quote","ignore"
        ])

        df = df.astype({
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "volume": float
        })

        return df
    except:
        return None

# =====================================
# DETECT SWEEP
# =====================================
def detect_sweep(df):
    c1 = df.iloc[-3]
    c2 = df.iloc[-2]
    c3 = df.iloc[-1]

    # Volume filter
    if c2["volume"] < c1["volume"] * 1.2:
        return None

    # ===== Bullish =====
    if (
        c2["low"] < c1["low"] and
        c2["close"] > c1["low"] and
        c3["close"] > c2["high"]
    ):
        entry = c3["close"]
        sl = c2["low"]
        tp = entry + (entry - sl) * 2
        rr = round((tp - entry) / (entry - sl), 2)

        return "Bullish", entry, sl, tp, rr

    # ===== Bearish =====
    if (
        c2["high"] > c1["high"] and
        c2["close"] < c1["high"] and
        c3["close"] < c2["low"]
    ):
        entry = c3["close"]
        sl = c2["high"]
        tp = entry - (sl - entry) * 2
        rr = round((entry - tp) / (sl - entry), 2)

        return "Bearish", entry, sl, tp, rr

    return None

# =====================================
# LIVE SCAN FUNCTION
# =====================================
def run_scan_live():

    results = []
    progress = st.progress(0)
    status_text = st.empty()
    table_placeholder = st.empty()

    total = len(symbols)

    for i, symbol in enumerate(symbols):
        status_text.write(f"Scanning: {symbol}")

        df = get_klines(symbol)
        if df is not None and len(df) >= 3:
            signal = detect_sweep(df)
            if signal:
                signal_type, entry, sl, tp, rr = signal
                results.append({
                    "Symbol": symbol,
                    "Type": signal_type,
                    "Entry": entry,
                    "StopLoss": sl,
                    "Target(2R)": tp,
                    "RR": rr
                })

                table_placeholder.dataframe(pd.DataFrame(results), use_container_width=True)

        progress.progress((i + 1) / total)

    progress.empty()
    status_text.empty()

    return pd.DataFrame(results)

# =====================================
# AUTO REFRESH (60 sec)
# =====================================
st_autorefresh(interval=60000, key="auto_refresh")

# =====================================
# SCANNER CONTROL
# =====================================
st.divider()
st.subheader("Scanner Control")

scan_now = st.button("🔍 Scan Now")

def perform_scan():
    with st.spinner("Scanning entire market..."):
        st.session_state.results = run_scan_live()
        st.session_state.last_scan_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

if scan_now:
    perform_scan()

# ===== AUTO SCAN AT CANDLE CLOSE =====
now = datetime.utcnow()
trigger = False

if timeframe == "1h":
    trigger = now.minute == 0
elif timeframe == "4h":
    trigger = now.hour % 4 == 0 and now.minute == 0
elif timeframe == "1d":
    trigger = now.hour == 0 and now.minute == 0

if trigger:
    if st.session_state.last_scan_time != now.strftime("%Y-%m-%d %H"):
        perform_scan()

# =====================================
# DISPLAY RESULTS
# =====================================
st.divider()
st.subheader("Final Scan Results")

if st.session_state.results.empty:
    st.info("No signals found.")
else:
    st.dataframe(st.session_state.results, use_container_width=True)

st.caption(f"Last Scan: {st.session_state.last_scan_time}")
