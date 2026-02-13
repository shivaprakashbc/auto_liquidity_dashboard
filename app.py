import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone

# =====================================
# PASSWORD PROTECTION (FREE METHOD)
# =====================================

APP_PASSWORD = "ChangeThisPassword123"   # <-- CHANGE THIS

def check_password():
    def password_entered():
        if st.session_state["password"] == APP_PASSWORD:
            st.session_state["password_correct"] = True
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Password", type="password",
                      key="password", on_change=password_entered)
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Password", type="password",
                      key="password", on_change=password_entered)
        st.error("Incorrect Password")
        return False
    else:
        return True

if not check_password():
    st.stop()

# =====================================
# PAGE CONFIG
# =====================================

st.set_page_config(layout="wide")
st.title("🚀 Binance Futures Liquidity Sweep Dashboard")

# =====================================
# SETTINGS
# =====================================

TIMEFRAME = st.selectbox("Select Timeframe", ["1h", "4h", "1d"])
RR_MULTIPLIER = st.slider("Risk Reward", 1.0, 5.0, 2.0)

API_URL = "https://fapi.binance.com/fapi/v1/klines"

# =====================================
# SESSION STATE STORAGE
# =====================================

if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = None

if "results" not in st.session_state:
    st.session_state.results = pd.DataFrame()

# =====================================
# FETCH SYMBOLS
# =====================================

@st.cache_data(ttl=3600)
def get_symbols():
    info = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo").json()
    return [s["symbol"] for s in info["symbols"] if s["contractType"] == "PERPETUAL"]

symbols = get_symbols()

# =====================================
# TIME CHECK (AUTO SCAN)
# =====================================

def is_new_candle_close():
    now = datetime.now(timezone.utc)

    if TIMEFRAME == "1h":
        return now.minute == 0 and now.second < 20

    if TIMEFRAME == "4h":
        return now.hour % 4 == 0 and now.minute == 0 and now.second < 20

    if TIMEFRAME == "1d":
        return now.hour == 0 and now.minute == 0 and now.second < 20

    return False

# =====================================
# FETCH LAST 3 CLOSED CANDLES
# =====================================

def get_last_3(symbol):
    params = {"symbol": symbol, "interval": TIMEFRAME, "limit": 4}
    data = requests.get(API_URL, params=params).json()

    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume",
        "_1","_2","_3","_4","_5","_6"
    ])

    df = df.astype(float)

    # Ignore currently forming candle
    return df.iloc[-4:-1]

# =====================================
# WICK LOGIC
# =====================================

def long_upper(c):
    body = abs(c["close"] - c["open"])
    wick = c["high"] - max(c["open"], c["close"])
    return wick > body * 1.5

def long_lower(c):
    body = abs(c["close"] - c["open"])
    wick = min(c["open"], c["close"]) - c["low"]
    return wick > body * 1.5

# =====================================
# SCANNER LOGIC
# =====================================

def run_scan():
    found = []

    for symbol in symbols:
        try:
            df = get_last_3(symbol)
            c1, c2, c3 = df.iloc[0], df.iloc[1], df.iloc[2]

            # -------------------
            # BULLISH SETUP
            # -------------------
            if (
                c1["close"] > c1["open"] and
                c2["high"] > c1["high"] and
                c2["close"] < c1["high"] and
                c2["volume"] >= 1.2 * c1["volume"] and
                long_upper(c2) and
                c3["close"] > c2["close"] and
                c3["low"] >= c2["low"]
            ):
                entry = c3["close"]
                sl = c2["low"]
                risk = entry - sl
                tp = entry + risk * RR_MULTIPLIER
                rr = (tp - entry) / risk

                found.append([symbol, "Bullish", entry, sl, tp, round(rr,2)])

            # -------------------
            # BEARISH SETUP
            # -------------------
            if (
                c1["close"] < c1["open"] and
                c2["low"] < c1["low"] and
                c2["close"] > c1["low"] and
                c2["volume"] >= 1.2 * c1["volume"] and
                long_lower(c2) and
                c3["close"] < c2["close"] and
                c3["high"] <= c2["high"]
            ):
                entry = c3["close"]
                sl = c2["high"]
                risk = sl - entry
                tp = entry - risk * RR_MULTIPLIER
                rr = (entry - tp) / risk

                found.append([symbol, "Bearish", entry, sl, tp, round(rr,2)])

        except:
            pass

    return pd.DataFrame(
        found,
        columns=["Symbol","Type","Entry","SL","TP","RR"]
    )

# =====================================
# UI SECTION
# =====================================

st.divider()
st.subheader("Scanner Control")

scan_now = st.button("🔍 Scan Now")

# Manual scan
if scan_now:
    with st.spinner("Scanning Binance Futures..."):
        st.session_state.results = run_scan()
        st.session_state.last_scan_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

# Auto scan at candle close
if is_new_candle_close():
    current_key = datetime.utcnow().strftime("%Y-%m-%d %H")
    if st.session_state.last_scan_time != current_key:
        st.session_state.results = run_scan()
        st.session_state.last_scan_time = current_key

# =====================================
# DISPLAY RESULTS
# =====================================

st.divider()
st.subheader("Scan Results")

if st.session_state.results.empty:
    st.info("No signals yet. Click 'Scan Now' or wait for next candle close.")
else:
    st.dataframe(st.session_state.results, use_container_width=True)

st.caption(f"Last Scan (UTC): {st.session_state.last_scan_time}")
