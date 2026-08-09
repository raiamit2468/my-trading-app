import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="AI Trading Assistant", layout="wide")

def fetch_json(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API error: {e}")
        return None

def fetch_crypto_price(coin_id, vs="usd"):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id, "vs_currencies": vs}
    return fetch_json(url, params)

def fetch_crypto_chart(coin_id, vs="usd", days=1):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": vs, "days": days}
    data = fetch_json(url, params)
    if not data or "prices" not in data:
        return None

    df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

def fetch_gold_price():
    url = "https://www.coingecko.com/en/commodities/gold"
    return fetch_json(url)

st.title("AI Trading Assistant")

col1, col2 = st.columns(2)

with col1:
    st.subheader("BTC/USD")
    btc_price = fetch_crypto_price("bitcoin", "usd")
    btc_df = fetch_crypto_chart("bitcoin", "usd", 1)

    if btc_price and "bitcoin" in btc_price:
        st.metric("BTC Price", f"${btc_price['bitcoin']['usd']}")
    else:
        st.warning("BTC price unavailable")

    if btc_df is not None:
        st.line_chart(btc_df.set_index("timestamp")["price"])
    else:
        st.warning("BTC chart unavailable")

with col2:
    st.subheader("Gold")
    gold_data = fetch_gold_price()
    if gold_data:
        st.info("Gold source loaded")
    else:
        st.warning("Gold data unavailable")
