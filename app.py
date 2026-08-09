import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import time
import requests
import plotly.graph_objects as go
from datetime import datetime, timezone

st.set_page_config(page_title="AI Trading Assistant", layout="centered")

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
except Exception:
    client = None
    st.error("API Key secrets me set nahi hai!")

st.title("AI Trading Assistant")

tab1, tab2 = st.tabs(["📸 Chart Analyzer", "📡 Live Signals"])

# ==================== TAB 1: Screenshot Analyzer ====================
with tab1:
    st.write("Upload chart screenshot for Buy/Sell signals")
    uploaded_file = st.file_uploader("Upload Chart Image", type=["jpg", "png", "jpeg"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        max_width = 1024
        if image.width > max_width:
            ratio = max_width / image.width
            image = image.resize((max_width, int(image.height * ratio)))
        st.image(image, caption='Uploaded Chart', use_container_width=True)

        if st.button('Analyze Chart'):
            prompt = """
            You are an expert technical analyst. Analyze this chart image:
            1. Current Trend & Patterns identified
            2. Signal: BUY / SELL / WAIT
            3. Entry Price, Target Price, and Stop Loss
            4. Risk to Reward Ratio
            Keep it clear and precise.
            """
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with st.spinner(f"Analyzing... (attempt {attempt + 1}/{max_retries})"):
                        response = client.models.generate_content(
                            model='gemini-3.5-flash',
                            contents=[prompt, image],
                            config=types.GenerateContentConfig(
                                http_options=types.HttpOptions(timeout=60000)
                            ),
                        )
                    st.subheader("Analysis & Signal:")
                    st.write(response.text)
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        st.warning(f"Server busy hai, retry ho raha hai... ({attempt + 1}/{max_retries})")
                        time.sleep(3)
                    else:
                        st.error("Gemini server abhi available nahi hai. Thodi der baad try karo.")
                        st.exception(e)

# ==================== TAB 2: Live Signals + RRG ====================

def fetch_klines(symbol, interval, limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    raw = r.json()
    candles = []
    for k in raw:
        candles.append({
            "time": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
            "open": float(k[1]), "high": float(k[2]),
            "low": float(k[3]), "close": float(k[4]),
        })
    return candles


def compute_indicators(candles):
    closes = [c["close"] for c in candles]
    n = len(closes)
    if n < 51:
        return None

    def sma(period, end_idx):
        return sum(closes[end_idx - period + 1:end_idx + 1]) / period

    sma20_now, sma50_now = sma(20, n - 1), sma(50, n - 1)
    sma20_prev, sma50_prev = sma(20, n - 2), sma(50, n - 2)

    gains = losses = 0
    for i in range(n - 14, n):
        diff = closes[i] - closes[i - 1]
        gains += max(diff, 0)
        losses += max(-diff, 0)
    avg_gain, avg_loss = gains / 14, losses / 14
    rsi = 100 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)

    ranges = [c["high"] - c["low"] for c in candles[-14:]]
    avg_range = sum(ranges) / len(ranges)
    price = closes[-1]
    recent_high = max(c["high"] for c in candles[-20:])
    recent_low = min(c["low"] for c in candles[-20:])

    return {
        "price": price, "sma20": sma20_now, "sma50": sma50_now,
        "sma20_prev": sma20_prev, "sma50_prev": sma50_prev,
        "rsi": rsi, "avg_range": avg_range,
        "recent_high": recent_high, "recent_low": recent_low,
        "time": candles[-1]["time"],
    }


def ai_signal(symbol, interval_label, ind):
    prompt = f"""You are a crypto technical analyst. Based ONLY on this data for {symbol} ({interval_label} chart), give a trading signal.

Current price: {ind['price']:.2f}
SMA20: {ind['sma20']:.2f} (previous candle: {ind['sma20_prev']:.2f})
SMA50: {ind['sma50']:.2f} (previous candle: {ind['sma50_prev']:.2f})
RSI(14): {ind['rsi']:.1f}
Average candle range (volatility, last 14): {ind['avg_range']:.2f}
Recent 20-candle high: {ind['recent_high']:.2f}
Recent 20-candle low: {ind['recent_low']:.2f}

Reply in this exact format, nothing else:
SIGNAL: BUY or SELL or WAIT
CONFIDENCE: Low or Medium or High
ENTRY: <price or N/A>
TARGET: <price or N/A>
STOPLOSS: <price or N/A>
REASON: <one short sentence>"""

    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=[prompt],
        config=types.GenerateContentConfig(http_options=types.HttpOptions(timeout=30000)),
    )
    return response.text


def parse_ai_response(text):
    result = {"signal": "WAIT", "confidence": "-", "entry": "-", "target": "-", "stoploss": "-", "reason": text}
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("SIGNAL:"):
            result["signal"] = line.split(":", 1)[1].strip().upper()
        elif line.upper().startswith("CONFIDENCE:"):
            result["confidence"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("ENTRY:"):
            result["entry"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("TARGET:"):
            result["target"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("STOPLOSS:"):
            result["stoploss"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("REASON:"):
            result["reason"] = line.split(":", 1)[1].strip()
    return result


def render_card(symbol, interval_label, ind, ai_result):
    if ind is None:
        st.warning(f"{symbol} ({interval_label}): abhi data kaafi nahi hai")
        return
    icon = {"BUY": "🟢", "SELL": "🔴", "WAIT": "🟡"}.get(ai_result["signal"], "🟡")
    with st.container(border=True):
        st.markdown(f"**{icon} {symbol} · {interval_label} · {ai_result['signal']}** (confidence: {ai_result['confidence']})")
        st.caption(ai_result["reason"])
        c1, c2 = st.columns(2)
        c1.metric("Price", f"${ind['price']:,.2f}")
        c2.metric("RSI", f"{ind['rsi']:.0f}")
        if ai_result["signal"] in ("BUY", "SELL"):
            c3, c4 = st.columns(2)
            c3.metric("Target", ai_result["target"])
            c4.metric("Stop Loss", ai_result["stoploss"])
        st.caption(f"Updated: {ind['time'].strftime('%H:%M UTC')}")


# ---------- RRG (Relative Rotation Graph) ----------
def sma_of(lst, period, idx):
    return sum(lst[idx - period + 1:idx + 1]) / period


def rrg_series(price_norm, benchmark, period=14):
    n = len(price_norm)
    rs = [p / b for p, b in zip(price_norm, benchmark)]
    rs_ratio = [None] * n
    for i in range(period - 1, n):
        rs_ratio[i] = 100 * rs[i] / sma_of(rs, period, i)
    rs_momentum = [None] * n
    for i in range(period - 1, n):
        window = rs_ratio[i - period + 1:i + 1]
        if any(v is None for v in window):
            continue
        rs_momentum[i] = 100 * rs_ratio[i] / (sum(window) / period)
    return rs_ratio, rs_momentum


def build_rrg_figure(btc_candles, eth_candles, tail=8):
    n = min(len(btc_candles), len(eth_candles))
    btc_closes = [c["close"] for c in btc_candles[-n:]]
    eth_closes = [c["close"] for c in eth_candles[-n:]]
    btc_norm = [c / btc_closes[0] for c in btc_closes]
    eth_norm = [c / eth_closes[0] for c in eth_closes]
    benchmark = [(b + e) / 2 for b, e in zip(btc_norm, eth_norm)]

    btc_ratio, btc_mom = rrg_series(btc_norm, benchmark)
    eth_ratio, eth_mom = rrg_series(eth_norm, benchmark)

    def valid_tail(ratio, mom):
        pts = [(r, m) for r, m in zip(ratio, mom) if r is not None and m is not None]
        return pts[-tail:] if len(pts) >= 2 else None

    btc_pts = valid_tail(btc_ratio, btc_mom)
    eth_pts = valid_tail(eth_ratio, eth_mom)
    if not btc_pts or not eth_pts:
        return None

    fig = go.Figure()
    all_x = [p[0] for p in btc_pts] + [p[0] for p in eth_pts]
    all_y = [p[1] for p in btc_pts] + [p[1] for p in eth_pts]
    pad = max(max(all_x) - min(all_x), max(all_y) - min(all_y), 2) * 0.6 + 1
    xr = [100 - pad, 100 + pad]
    yr = [100 - pad, 100 + pad]

    fig.add_shape(type="rect", x0=100, x1=xr[1], y0=100, y1=yr[1], fillcolor="rgba(63,182,139,0.12)", line_width=0)
    fig.add_shape(type="rect", x0=xr[0], x1=100, y0=100, y1=yr[1], fillcolor="rgba(232,163,61,0.12)", line_width=0)
    fig.add_shape(type="rect", x0=xr[0], x1=100, y0=yr[0], y1=100, fillcolor="rgba(224,87,76,0.12)", line_width=0)
    fig.add_shape(type="rect", x0=100, x1=xr[1], y0=yr[0], y1=100, fillcolor="rgba(63,182,139,0.06)", line_width=0)

    fig.add_annotation(x=xr[1] - pad * 0.15, y=yr[1] - pad * 0.15, text="LEADING", showarrow=False, font=dict(color="#3FB68B", size=11))
    fig.add_annotation(x=xr[0] + pad * 0.2, y=yr[1] - pad * 0.15, text="IMPROVING", showarrow=False, font=dict(color="#5B8DEF", size=11))
    fig.add_annotation(x=xr[0] + pad * 0.15, y=yr[0] + pad * 0.15, text="LAGGING", showarrow=False, font=dict(color="#E0574C", size=11))
    fig.add_annotation(x=xr[1] - pad * 0.15, y=yr[0] + pad * 0.15, text="WEAKENING", showarrow=False, font=dict(color="#E8A33D", size=11))

    for label, pts, color in [("BTC", btc_pts, "#F7931A"), ("ETH", eth_pts, "#627EEA")]:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=label,
                                  line=dict(color=color, width=2),
                                  marker=dict(size=[6] * (len(xs) - 1) + [12], color=color)))
        fig.add_annotation(x=xs[-1], y=ys[-1], text=label, showarrow=False,
                            font=dict(color=color, size=13, family="monospace"), yshift=14)

    fig.update_layout(
        xaxis=dict(title="RS-Ratio (strength)", range=xr, gridcolor="#232B36", zeroline=False),
        yaxis=dict(title="RS-Momentum", range=yr, gridcolor="#232B36", zeroline=False),
        plot_bgcolor="#0E1319", paper_bgcolor="#0E1319",
        font=dict(color="#E8ECEF"), height=380, margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    return fig


with tab2:
    st.write("BTC/USDT aur ETH/USDT ke live signals — AI reasoning + real price data pe based")
    refresh_seconds = st.selectbox(
        "Refresh interval", [900, 1800, 3600],
        format_func=lambda s: f"Har {s // 60} minute", index=0
    )

    @st.fragment(run_every=refresh_seconds)
    def live_signals():
        st.caption(f"Last checked: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
        candles_cache = {}
        for symbol in ["BTCUSDT", "ETHUSDT"]:
            cols = st.columns(2)
            for col, interval, label in zip(cols, ["15m", "1h"], ["15 min", "1 hour"]):
                with col:
                    try:
                        candles = fetch_klines(symbol, interval, limit=100)
                        candles_cache[(symbol, interval)] = candles
                        ind = compute_indicators(candles)
                        if ind is None:
                            render_card(symbol.replace("USDT", "/USDT"), label, None, None)
                            continue
                        raw_text = ai_signal(symbol, label, ind)
                        ai_result = parse_ai_response(raw_text)
                        render_card(symbol.replace("USDT", "/USDT"), label, ind, ai_result)
                    except Exception as e:
                        st.error(f"{symbol} {label}: error — {e}")

        st.markdown("---")
        st.subheader("🔄 RRG — Relative Rotation (BTC vs ETH)")
        st.caption("Leading = dono strong & outperforming · Weakening = strength kam ho rahi · Lagging = weak · Improving = recover ho raha")
        try:
            btc_1h = candles_cache.get(("BTCUSDT", "1h")) or fetch_klines("BTCUSDT", "1h", 60)
            eth_1h = candles_cache.get(("ETHUSDT", "1h")) or fetch_klines("ETHUSDT", "1h", 60)
            fig = build_rrg_figure(btc_1h, eth_1h)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("RRG ke liye abhi kaafi data nahi hai.")
        except Exception as e:
            st.error(f"RRG load nahi ho paya: {e}")

    live_signals()

    st.caption("⚠️ Ye AI-generated technical signals hain, financial advice nahi. Koi bhi system 100% accurate nahi hota — apna risk khud manage karo.")
