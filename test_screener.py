import os
import time
import requests
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
from openchart import NSEData

# ============================================================
# NSE F&O BUY / SELL SCREENER (AUTO DATE FALLBACK FIX)
# ============================================================
print("=" * 75)
print("NSE F&O BUY / SELL SCREENER")
print("=" * 75)

VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.5
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"

MASTER_URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "text/csv,application/csv,*/*",
    "Referer": "https://www.nseindia.com/"
}

def load_stock_futures():
    print("\n[1] Fetching F&O Symbols from NSE Master...")
    try:
        r = requests.get(MASTER_URL, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            df = pd.read_csv(BytesIO(r.content))
            df.columns = [str(c).strip().upper() for c in df.columns]
            
            sym_col = "SYMBOL" if "SYMBOL" in df.columns else ("UNDERLYING" if "UNDERLYING" in df.columns else None)
            if sym_col:
                symbols = df[sym_col].astype(str).str.strip().dropna().unique().tolist()
                indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "NIFTYFPI", "SYMBOL"]
                stocks = [s for s in symbols if s not in indices and not s.startswith("UNDERLYING")]
                print(f"FETCHED {len(stocks)} VALID STOCK SYMBOLS")
                return stocks
    except Exception as e:
        print(f"Master download error: {str(e)[:100]}")
        
    if os.path.exists("stock_futures.csv"):
        f_df = pd.read_csv("stock_futures.csv")
        f_df.columns = [str(c).strip().lower() for c in f_df.columns]
        return f_df["symbol"].dropna().unique().tolist()
        
    raise RuntimeError("No symbols available.")

symbols = load_stock_futures()
nse = NSEData()

def get_trading_dates():
    """ Determines current trading day or shifts back if weekend/after-hours """
    now = datetime.now()
    target_date = now.date()
    
    # If Sunday (6) or Saturday (5), shift back to Friday
    if target_date.weekday() == 5:
        target_date -= timedelta(days=1)
    elif target_date.weekday() == 6:
        target_date -= timedelta(days=2)
        
    start_dt = datetime.combine(target_date, datetime.strptime(MARKET_OPEN, "%H:%M").time())
    end_dt = datetime.combine(target_date, datetime.strptime(MARKET_CLOSE, "%H:%M").time())
    return target_date, start_dt, end_dt

target_date, start_dt, end_dt = get_trading_dates()
print(f"TARGET SCAN DATE: {target_date}")

def clean_columns(df):
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def normalize_timestamp(df):
    if not isinstance(df.index, pd.DatetimeIndex):
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.set_index("timestamp")
        elif "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
            df = df.set_index("datetime")
        else:
            return None

    idx = pd.to_datetime(df.index)
    try:
        if idx.tz is not None:
            idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)
    except Exception:
        pass
    df.index = idx
    return df

def fetch_data_robust(symbol, start, end, tf):
    """ Tries FO first, then EQ fallback, across last 5 days if today is blank """
    for offset in range(5):
        curr_start = start - timedelta(days=offset)
        curr_end = end - timedelta(days=offset)
        
        # Try FO Segment
        try:
            data = nse.historical(symbol, "FO", curr_start, curr_end, tf)
            if data is not None and len(data) > 0:
                return data, curr_start.date()
        except Exception:
            pass
            
        # Try Equity Segment Fallback
        try:
            data = nse.historical(symbol, "EQ", curr_start, curr_end, tf)
            if data is not None and len(data) > 0:
                return data, curr_start.date()
        except Exception:
            pass
            
    return None, None

def get_pdh_pdl(symbol, active_date):
    try:
        prev_start = active_date - timedelta(days=7)
        prev_end = datetime.combine(active_date - timedelta(days=1), datetime.strptime(MARKET_CLOSE, "%H:%M").time())
        data, _ = fetch_data_robust(symbol, prev_start, prev_end, "1d")

        if data is None or len(data) == 0:
            return None, None

        data = clean_columns(data)
        data = normalize_timestamp(data)
        if data is None or "high" not in data.columns:
            return None, None

        data = data[data.index.date < active_date]
        if len(data) == 0:
            return None, None

        last_day = data.index.date[-1]
        day_data = data[data.index.date == last_day]
        return float(day_data["high"].max()), float(day_data["low"].min())
    except Exception:
        return None, None

def calculate_signal(symbol):
    try:
        data, active_date = fetch_data_robust(symbol, start_dt, end_dt, "5m")

        if data is None or len(data) == 0:
            return "DATA_ERROR"

        data = clean_columns(data)
        data = normalize_timestamp(data)
        if data is None:
            return "DATA_ERROR"

        req_cols = ["open", "high", "low", "close", "volume"]
        if not all(col in data.columns for col in req_cols):
            return "DATA_ERROR"

        data = data[
            (data.index.time >= pd.Timestamp("09:15").time()) &
            (data.index.time <= pd.Timestamp("15:30").time())
        ].copy()

        if len(data) < 3:
            return "INSUFFICIENT_BARS"

        pdh, pdl = get_pdh_pdl(symbol, active_date)
        if pdh is None or pdl is None:
            return "NO_PDH_PDL"

        c915 = data[(data.index.hour == 9) & (data.index.minute == 15)]
        c920 = data[(data.index.hour == 9) & (data.index.minute == 20)]
        c925 = data[(data.index.hour == 9) & (data.index.minute == 25)]

        if c915.empty or c920.empty or c925.empty:
            return "NO_ORB_CANDLES"

        c915_r, c920_r, c925_r = c915.iloc[0], c920.iloc[0], c925.iloc[0]
        orb_high = max(float(c915_r["high"]), float(c920_r["high"]))
        orb_low = min(float(c915_r["low"]), float(c920_r["low"]))

        # Volume Condition (9:15, 9:20, or 9:25)
        data["vol_avg_20"] = data["volume"].rolling(VOLUME_LOOKBACK).mean().shift(1)
        volume_pass = False

        for ts in [c915_r.name, c920_r.name, c925_r.name]:
            row = data.loc[ts]
            avg20 = row["vol_avg_20"]
            if not pd.isna(avg20) and avg20 > 0:
                if float(row["volume"]) >= (avg20 * VOLUME_MULTIPLIER):
                    volume_pass = True
                    break
            else:
                volume_pass = True

        if not volume_pass:
            return "LOW_VOLUME"

        day_open = float(c915_r["open"])
        pdh_break, pdl_break = False, False
        orb_high_break, orb_low_break = False, False

        scan_data = data[data.index >= c925_r.name].copy()

        for ts, row in scan_data.iterrows():
            high, low, close = float(row["high"]), float(row["low"]), float(row["close"])

            if high >= pdh: pdh_break = True
            if high >= orb_high: orb_high_break = True

            if pdh_break and orb_high_break:
                pct = ((close - day_open) / day_open) * 100
                return {
                    "symbol": symbol,
                    "signal": "BUY",
                    "signal_time": ts.strftime("%H:%M"),
                    "signal_price": round(close, 2),
                    "movement_pct": round(pct, 2)
                }

            if low <= pdl: pdl_break = True
            if low <= orb_low: orb_low_break = True

            if pdl_break and orb_low_break:
                pct = ((close - day_open) / day_open) * 100
                return {
                    "symbol": symbol,
                    "signal": "SELL",
                    "signal_time": ts.strftime("%H:%M"),
                    "signal_price": round(close, 2),
                    "movement_pct": round(pct, 2)
                }

        return "NO_SIGNAL"

    except Exception:
        return "ERROR"

# ------------------------------------------------------------
# EXECUTE SCREENER
# ------------------------------------------------------------
results = []
total = len(symbols)

for i, symbol in enumerate(symbols, start=1):
    print(f"[{i}/{total}] {symbol}", end=" ... ")
    res = calculate_signal(symbol)

    if isinstance(res, dict):
        results.append(res)
        print(f"[{res['signal']}] Time: {res['signal_time']} | Price: {res['signal_price']} ({res['movement_pct']}%)")
    else:
        print(res)

    time.sleep(0.05)

# ------------------------------------------------------------
# WRITE OUTPUT
# ------------------------------------------------------------
if results:
    df_res = pd.DataFrame(results)
    df_res = df_res[["symbol", "signal", "signal_time", "signal_price", "movement_pct"]]
    df_res = df_res.sort_values(by="signal_time", ascending=True)
    print("\n" + "=" * 75)
    print(df_res.to_string(index=False))
else:
    df_res = pd.DataFrame(columns=["symbol", "signal", "signal_time", "signal_price", "movement_pct"])
    print("\nNO SIGNALS GENERATED")

df_res.to_csv("screener_results.csv", index=False)
print("\n[COMPLETE] Saved results to screener_results.csv")
