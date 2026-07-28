import datetime
import streamlit as st
import pandas as pd
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

# Import tvDatafeed with fallback import handling
try:
    from tvDatafeed import TvDatafeed, Interval
except ImportError:
    from tvdatafeed import TvDatafeed, Interval

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="XAUUSD SK TERMINAL",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Auto refresh set to 10 seconds (10,000 ms)
st_autorefresh(interval=10000, key="terminal_v1_autorefresh")

# Initialize session state stores
if "reached_timestamps" not in st.session_state:
    st.session_state["reached_timestamps"] = {}

# -----------------------------------------------------------------------------
# CUSTOM CSS STYLING
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp {
        background-color: #FFFFFF;
    }
    .header-title {
        background-color: #1E3A8A;
        color: #FFFFFF;
        padding: 14px;
        text-align: center;
        border-radius: 8px;
        font-weight: bold;
        font-size: 22px;
        margin-bottom: 16px;
        letter-spacing: 1px;
    }
    .top-card {
        padding: 14px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 16px;
    }
    .price-card {
        background-color: #EFF6FF;
        border: 2px solid #3B82F6;
        color: #1E3A8A;
    }
    .card-label {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 2px;
    }
    .card-val {
        font-size: 24px;
        font-weight: 800;
        line-height: 1.1;
    }
    .card-subtext {
        font-size: 11px;
        font-weight: 600;
        margin-top: 4px;
        opacity: 0.85;
    }
    .status-bull {
        background-color: #DCFCE7;
        border: 2px solid #22C55E;
        color: #15803D;
    }
    .status-bear {
        background-color: #FEE2E2;
        border: 2px solid #EF4444;
        color: #B91C1C;
    }
    .section-header {
        font-size: 17px;
        font-weight: 800;
        color: #1E3A8A;
        margin-top: 10px;
        margin-bottom: 12px;
        text-align: center;
        letter-spacing: 0.5px;
    }
    .terminal-footer {
        text-align: center;
        font-size: 11px;
        font-weight: 600;
        color: #6B7280;
        padding: 12px 0;
        margin-top: 20px;
        border-top: 1px solid #E5E7EB;
    }
    div[data-testid="stTable"], div[data-testid="stDataFrame"] {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# DATA ENGINE (ANONYMOUS TRADINGVIEW WITH YFINANCE FALLBACK)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=5)
def fetch_market_data():
    """Fetch live market price and historical closes from TradingView (Anonymous) or Yahoo Finance."""
    last_update_str = datetime.datetime.now().strftime("%H:%M:%S")

    # 1. TRY ANONYMOUS TRADINGVIEW FIRST
    try:
        tv = TvDatafeed()  # Anonymous connection (no login required)
        
        # Fetch 1-min intraday for current price & day range
        df_1m = tv.get_hist(symbol="XAUUSD", exchange="OANDA", interval=Interval.in_1_minute, n_bars=100)
        if df_1m is not None and not df_1m.empty:
            current_price = float(df_1m['close'].iloc[-1])
            today_high = float(df_1m['high'].max())
            today_low = float(df_1m['low'].min())

            # Daily Close
            df_daily = tv.get_hist(symbol="XAUUSD", exchange="OANDA", interval=Interval.in_daily, n_bars=10)
            prev_day_close = float(df_daily['close'].iloc[-2]) if len(df_daily) >= 2 else current_price

            # Weekly Close
            df_weekly = tv.get_hist(symbol="XAUUSD", exchange="OANDA", interval=Interval.in_weekly, n_bars=10)
            prev_week_close = float(df_weekly['close'].iloc[-2]) if len(df_weekly) >= 2 else prev_day_close

            # Monthly Close
            df_monthly = tv.get_hist(symbol="XAUUSD", exchange="OANDA", interval=Interval.in_monthly, n_bars=10)
            prev_month_close = float(df_monthly['close'].iloc[-2]) if len(df_monthly) >= 2 else prev_day_close

            return current_price, today_high, today_low, prev_day_close, prev_week_close, prev_month_close, last_update_str, "TradingView (Anonymous)"
    except Exception:
        pass

    # 2. FALLBACK TO YAHOO FINANCE IF TRADINGVIEW FAILS
    symbols_to_try = ["GC=F", "XAUUSD=X"]
    for sym in symbols_to_try:
        try:
            ticker = yf.Ticker(sym)
            hist_1d = ticker.history(period="1d", interval="1m")
            if hist_1d.empty:
                hist_1d = ticker.history(period="5d", interval="5m")

            if not hist_1d.empty:
                current_price = float(hist_1d['Close'].iloc[-1])
                today_high = float(hist_1d['High'].max())
                today_low = float(hist_1d['Low'].min())

                hist_daily = ticker.history(period="1mo", interval="1d")
                completed_daily = hist_daily[hist_daily.index.date < datetime.date.today()]
                prev_day_close = float(completed_daily['Close'].iloc[-1]) if len(completed_daily) > 0 else current_price

                hist_weekly = ticker.history(period="3mo", interval="1wk")
                completed_weekly = hist_weekly[:-1] if len(hist_weekly) > 1 else hist_weekly
                prev_week_close = float(completed_weekly['Close'].iloc[-1]) if len(completed_weekly) > 0 else prev_day_close

                hist_monthly = ticker.history(period="1y", interval="1mo")
                completed_monthly = hist_monthly[:-1] if len(hist_monthly) > 1 else hist_monthly
                prev_month_close = float(completed_monthly['Close'].iloc[-1]) if len(completed_monthly) > 0 else prev_day_close

                return current_price, today_high, today_low, prev_day_close, prev_week_close, prev_month_close, last_update_str, f"Yahoo Finance ({sym})"
        except Exception:
            continue

    return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, last_update_str, "No Feed"


# -----------------------------------------------------------------------------
# SK FORMULA ENGINE
# -----------------------------------------------------------------------------
def calculate_sk_levels(pc: float, timeframe_prefix: str) -> list:
    """Calculate SK Levels (R3, R2, R1, Pivot, S1, S2, S3) using standard formula."""
    if pc <= 0:
        return []
    
    base_step = pc / 31.4

    r3 = pc + base_step
    r2 = pc + (base_step / 4.0)
    r1 = pc + (base_step / 22.0)
    pivot = pc
    s1 = pc - (base_step / 22.0)
    s2 = pc - (base_step / 4.0)
    s3 = pc - base_step

    return [
        {"level": f"{timeframe_prefix} R3", "price": r3},
        {"level": f"{timeframe_prefix} R2", "price": r2},
        {"level": f"{timeframe_prefix} R1", "price": r1},
        {"level": f"{timeframe_prefix} Pivot", "price": pivot},
        {"level": f"{timeframe_prefix} S1", "price": s1},
        {"level": f"{timeframe_prefix} S2", "price": s2},
        {"level": f"{timeframe_prefix} S3", "price": s3},
    ]


def build_fixed_trading_ladder(daily_levels, weekly_levels, monthly_levels):
    """Merges and deduplicates levels bounded inside [Daily S3, Daily R3]."""
    daily_s3 = next((lvl["price"] for lvl in daily_levels if "S3" in lvl["level"]), None)
    daily_r3 = next((lvl["price"] for lvl in daily_levels if "R3" in lvl["level"]), None)

    if daily_s3 is None or daily_r3 is None:
        min_bound, max_bound = 0.0, float('inf')
    else:
        min_bound = min(daily_s3, daily_r3)
        max_bound = max(daily_s3, daily_r3)

    combined = list(daily_levels)
    for lvl in weekly_levels + monthly_levels:
        if min_bound <= lvl["price"] <= max_bound:
            combined.append(lvl)

    sorted_ladder = sorted(combined, key=lambda x: x["price"])
    unique_ladder = []
    seen_prices = set()

    for lvl in sorted_ladder:
        rounded_p = round(lvl["price"], 2)
        if rounded_p not in seen_prices:
            seen_prices.add(rounded_p)
            unique_ladder.append(lvl)

    return unique_ladder


# -----------------------------------------------------------------------------
# TARGET & STATUS ENGINE
# -----------------------------------------------------------------------------
def evaluate_target_status(current_price: float, today_high: float, today_low: float, target_price: float, is_buy: bool, level_name: str) -> tuple:
    """Evaluates target status using precedence order."""
    if is_buy:
        if current_price >= target_price:
            status = "✅ Achieved"
        elif today_high >= target_price:
            status = "🎯 Reached"
        else:
            status = "⏳ Pending"
    else:
        if current_price <= target_price:
            status = "✅ Achieved"
        elif today_low <= target_price:
            status = "🎯 Reached"
        else:
            status = "⏳ Pending"

    target_key = f"{level_name}_{target_price:.2f}"

    if status in ["🎯 Reached", "✅ Achieved"]:
        if target_key not in st.session_state["reached_timestamps"]:
            st.session_state["reached_timestamps"][target_key] = datetime.datetime.now().strftime("%H:%M:%S")
        time_str = st.session_state["reached_timestamps"][target_key]
    else:
        time_str = "-"

    return status, time_str


def build_target_dataframe(current_price: float, today_high: float, today_low: float, fixed_ladder: list, daily_pivot: float):
    """Generates nearest BUY T1..T5, BASE (Daily Pivot), and SELL T1..T5."""
    buy_candidates = [lvl for lvl in fixed_ladder if lvl["price"] > daily_pivot]
    buy_candidates = sorted(buy_candidates, key=lambda x: x["price"])[:5]

    sell_candidates = [lvl for lvl in fixed_ladder if lvl["price"] < daily_pivot]
    sell_candidates = sorted(sell_candidates, key=lambda x: x["price"], reverse=True)[:5]

    rows = []

    # BUY Targets (T1 to T5)
    for i in range(5):
        target_name = f"BUY T{i+1}"
        if i < len(buy_candidates):
            lvl = buy_candidates[i]
            target_price = lvl["price"]
            level_name = lvl["level"]
            status, time_str = evaluate_target_status(current_price, today_high, today_low, target_price, True, level_name)
            price_str = f"{target_price:.2f}"
        else:
            level_name, price_str, status, time_str = "-", "-", "-", "-"

        rows.append({"Target": target_name, "Level": level_name, "Price": price_str, "Status": status, "Time": time_str})

    # BASE ROW
    rows.append({"Target": "BASE", "Level": "Daily Pivot", "Price": f"{daily_pivot:.2f}", "Status": "📌 Pivot", "Time": "-"})

    # SELL Targets (T1 to T5)
    for i in range(5):
        target_name = f"SELL T{i+1}"
        if i < len(sell_candidates):
            lvl = sell_candidates[i]
            target_price = lvl["price"]
            level_name = lvl["level"]
            status, time_str = evaluate_target_status(current_price, today_high, today_low, target_price, False, level_name)
            price_str = f"{target_price:.2f}"
        else:
            level_name, price_str, status, time_str = "-", "-", "-", "-"

        rows.append({"Target": target_name, "Level": level_name, "Price": price_str, "Status": status, "Time": time_str})

    df = pd.DataFrame(rows)
    
    # NEXT markers
    for idx, row in df.iterrows():
        if "BUY" in row["Target"] and row["Status"] == "⏳ Pending":
            df.at[idx, "Status"] = "🔥 NEXT"
            break
            
    for idx, row in df.iterrows():
        if "SELL" in row["Target"] and row["Status"] == "⏳ Pending":
            df.at[idx, "Status"] = "🔥 NEXT"
            break

    return df


def style_target_table(df: pd.DataFrame):
    """Apply styling rules based on target types and status."""
    def row_styler(row):
        target = str(row["Target"])
        status = str(row["Status"])

        if target == "BASE":
            bg_color = "background-color: #DBEAFE; color: #1E40AF; font-weight: bold;"
        elif "BUY" in target:
            bg_color = "background-color: #F0FDF4; color: #166534;"
        elif "SELL" in target:
            bg_color = "background-color: #FEF2F2; color: #991B1B;"
        else:
            bg_color = ""

        if "🔥 NEXT" in status:
            bg_color = "background-color: #FEF9C3; color: #854D0E; font-weight: bold;"
        elif "🎯 Reached" in status:
            bg_color = "background-color: #FFEDD5; color: #C2410C; font-weight: bold;"
        elif "✅ Achieved" in status:
            bg_color = "background-color: #DCFCE7; color: #14532D; font-weight: bold;"

        return [bg_color] * len(row)

    return df.style.apply(row_styler, axis=1)


# -----------------------------------------------------------------------------
# MAIN APPLICATION ROUTINE
# -----------------------------------------------------------------------------
def main():
    today_date = datetime.date.today()

    # 1. Fetch live market data (Anonymous TV)
    current_price, today_high, today_low, auto_d_close, auto_w_close, auto_m_close, last_update, data_source = fetch_market_data()

    # 2. Sidebar Manual Pivot Overrides
    st.sidebar.header("⚙️ Manual Pivot Overrides")
    override = st.sidebar.checkbox("Override Auto Closes", value=False)
    
    if override:
        prev_day_close = st.sidebar.number_input("Daily Prev Close", value=4076.52, step=0.1)
        prev_week_close = st.sidebar.number_input("Weekly Prev Close", value=4052.78, step=0.1)
        prev_month_close = st.sidebar.number_input("Monthly Prev Close", value=4007.41, step=0.1)
    else:
        prev_day_close = auto_d_close
        prev_week_close = auto_w_close
        prev_month_close = auto_m_close

    todays_pivot = prev_day_close

    # Recalculate ladder dynamically
    ladder_key = f"{today_date}_{prev_day_close}_{prev_week_close}_{prev_month_close}"
    if st.session_state.get("ladder_key") != ladder_key:
        daily_levels = calculate_sk_levels(prev_day_close, "Daily")
        weekly_levels = calculate_sk_levels(prev_week_close, "Weekly")
        monthly_levels = calculate_sk_levels(prev_month_close, "Monthly")

        st.session_state["trading_ladder"] = build_fixed_trading_ladder(daily_levels, weekly_levels, monthly_levels)
        st.session_state["ladder_key"] = ladder_key
        st.session_state["reached_timestamps"] = {}

    fixed_ladder = st.session_state["trading_ladder"]
    is_bullish = current_price >= todays_pivot

    # 3. Main Dashboard UI
    st.markdown('<div class="header-title">XAUUSD SK TERMINAL</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f'''
        <div class="top-card price-card">
            <div class="card-label">Current Price</div>
            <div class="card-val">{current_price:.2f} USD</div>
            <div class="card-subtext">Last Update: {last_update}</div>
        </div>
        ''', unsafe_allow_html=True)

    with col2:
        if is_bullish:
            st.markdown('''
            <div class="top-card status-bull">
                <div class="card-label" style="color: #15803D;">Market Status</div>
                <div class="card-val">🟢 BULLISH</div>
                <div class="card-subtext">Above Daily Pivot</div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown('''
            <div class="top-card status-bear">
                <div class="card-label" style="color: #B91C1C;">Market Status</div>
                <div class="card-val">🔴 BEARISH</div>
                <div class="card-subtext">Below Daily Pivot</div>
            </div>
            ''', unsafe_allow_html=True)

    st.markdown('<div class="section-header">TODAY\'S TARGETS</div>', unsafe_allow_html=True)

    df_targets = build_target_dataframe(current_price, today_high, today_low, fixed_ladder, todays_pivot)
    styled_df = style_target_table(df_targets)

    st.dataframe(
        styled_df,
        column_config={
            "Target": st.column_config.TextColumn("Target"),
            "Level": st.column_config.TextColumn("Level"),
            "Price": st.column_config.TextColumn("Price"),
            "Status": st.column_config.TextColumn("Status"),
            "Time": st.column_config.TextColumn("Time"),
        },
        hide_index=True,
        use_container_width=True
    )

    st.markdown(f'''
    <div class="terminal-footer">
        Data Source : {data_source} &nbsp;|&nbsp; Auto Refresh : 10 Seconds
    </div>
    ''', unsafe_allow_html=True)


if __name__ == "__main__":
    main()