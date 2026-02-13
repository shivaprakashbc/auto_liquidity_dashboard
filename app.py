import streamlit as st
import pandas as pd
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException
import time

# =====================================
# CONFIG
# =====================================
st.set_page_config(page_title="Liquidity Sweep Dashboard", layout="wide")
APP_PASSWORD = "trade123"  # change this

# =====================================
# PASSWORD
# =====================================
def check_password():
    if "auth" not in st.session_state:
        st.session_state.auth = False

    if not st.session_state.auth:
        pwd = st.text_input("Enter Password", type="password")
        if st.button("Login"):
            if pwd == APP_PASSWORD:
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("Wrong password")
        st.stop()

check_password()

# =====================================
# TITLE
# =====================================
st.title("🚀 Binance Futures Liquidity Sweep Dashboard")
timeframe = st.selectbox("Select Timeframe", ["1h", "4h", "1d"])

# =====================================
# INIT SESSION
# =====================================
if "results" not in st.session_state:
    st.session_state.results = pd.DataFrame()

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None

# =====================================
# BINANCE CLIENT (No API Key Needed)
# =====================================
client = Client()

# =====================================
# GET FUTURES SYMBOLS
# =====================================
@st.cache_data(ttl=3600)
def get_symbols():
    try:
        info = client.futures_exchange_info()
        symbols = [
            s["symbol"]
            for s in info["symbols"]
            if s["contractType"] == "PERPETUAL"
            and s["quoteAsset"] == "USDT"
            and s["status"] == "TRADING"
        ]
        return symbols
    except Exception as e:
        st.error(f"Binance connection failed: {e}")
        return []

symbols = get_symbols()
st.write("Total symbols loaded:", len(symbols))

# =====================================
# GET KLINES
# =====================================
def get_klines(symbol):
    try:
        klines = client.futures_klines(
            symbol=symbol,
            interval=timeframe,
            limit=4
        )

        df = pd.DataFrame(klines, columns=[
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

    except BinanceAPIException:
        return None
    except:
        return None

# =====================================
# SWEEP LOGIC
# =====================================
def detect_sweep(df):
    c1 = df.iloc[-3]
    c2 = df.iloc[-2]
    c3 = df.iloc[-1]

    # Volume condition
    if c2["volume"] < c1["volume"] * 1.2:
        return None

    # Bullish
    if (
        c2["low"] < c1["low"] and
        c2["close"] > c1["low"] and
        c3["close"] > c2["high"]
    ):
        entry = c3["close"]
        sl = c2["low"]
        tp = entry + (entry - sl) * 2
        rr = round((tp - entry) / (entry - sl), 2)

        return {
            "Type": "Bullish",
            "Entry": entry,
            "SL": sl,
            "TP(2R)": tp,
            "RR": rr
        }

    # Bearish
    if (
        c2["high"] > c1["high"] and
        c2["close"] < c1["high"] and
        c3["close"] < c2["low"]
    ):
        entry = c3["close"]
        sl = c2["high"]
        tp = entry - (sl - entry) * 2
        rr = round((entry - tp) / (sl - entry), 2)

        return {
            "Type": "Bearish",
            "Entry": entry,
            "SL": sl,
            "TP(2R)": tp,
            "RR": rr
        }

    return None

# =====================================
# SCAN FUNCTION
# =====================================
def run_scan():

    results = []
    progress = st.progress(0)
    status = st.empty()
    live_table = st.empty()

    total = len(symbols)

    for i, symbol in enumerate(symbols):

        status.write(f"Scanning: {symbol}")

        df = get_klines(symbol)
        if df is not None and len(df) >= 3:

            signal = detect_sweep(df)
            if signal:
                signal["Symbol"] = symbol
                results.append(signal)

                live_table.dataframe(pd.DataFrame(results),
                                     use_container_width=True)

        progress.progress((i + 1) / total)
        time.sleep(0.05)

    progress.empty()
    status.empty()

    return pd.DataFrame(results)

# =====================================
# SCANNER CONTROL
# =====================================
st.divider()
st.subheader("Scanner Control")

if st.button("🔍 Scan Now"):

    if len(symbols) == 0:
        st.error("Binance API blocked in this environment.")
    else:
        with st.spinner("Scanning market..."):
            st.session_state.results = run_scan()
            st.session_state.last_scan = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        st.success("Scan Completed")

# =====================================
# RESULTS DISPLAY
# =====================================
st.divider()
st.subheader("Final Results")

if st.session_state.results.empty:
    st.info("No signals found.")
else:
    st.dataframe(st.session_state.results, use_container_width=True)

st.caption(f"Last Scan: {st.session_state.last_scan}")
