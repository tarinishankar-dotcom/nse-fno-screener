import os
import time
import random
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from openchart import NSEData

# ============================================================
# HYBRID F&O SCREENER (OPENCHART + YFINANCE FALLBACK)
# ============================================================
print("=" * 75)
print("NSE F&O SCREENER (CLOUD BLOCK-PROOF WITH YFINANCE)")
print("=" * 75)

MAX_WORKERS = 3

def load_stock_futures():
    """ Load symbols directly from local stock_futures.csv """
    csv_file = "stock_futures.csv"
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            df.columns = [str(c).strip().lower() for c in df.columns]
            if "symbol" in df.columns:
                symbols = df["symbol"].astype(str).str.strip().unique().tolist()
                print(f"Loaded {len(symbols)} symbols from local {csv_file}")
                return symbols
        except Exception as e:
            print(f"Error reading local CSV: {e}")
            
    return ["RELIANCE", "SBIN", "INFY", "TATAMOTORS", "ICICIBANK"]

symbols = load_stock_futures()
nse = NSEData()

def get_trading_dates():
    now = datetime.now()
    target_date = now.date()
    if target_date.weekday() == 5:
        target_date -= timedelta(days=1)
    elif target_date.weekday() == 6:
        target_date -= timedelta(days=2)
    
    start_dt = datetime.combine(target_date, datetime.strptime("09:15", "%H:%M").time())
    end_dt = datetime.combine(target_date, datetime.strptime("15:30", "%H:%M").time())
    return target_date, start_dt, end_dt

target_date, start_dt, end_dt = get_trading_dates()

def fetch_yfinance_data(symbol):
    """ Fallback fetcher using Yahoo Finance """
    try:
        yf_ticker = f"{symbol}.NS"
        df = yf.download(yf_ticker, period="5d", interval="5m", progress=False)
        if df is None or df.empty:
            return None
        
        # Standardize MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Get latest trading day data
        df.index = pd.to_datetime(df.index)
        latest_date = df.index.max().date()
        df_day = df[df.index.date == latest_date].copy()
        
        return df_day
    except Exception:
        return None

def process_single_symbol(symbol):
    """ Fetch candles with OpenChart + YFinance Fallback """
    time.sleep(random.uniform(0.1, 0.3))
    data = None
    try:
        # Attempt 1: OpenChart API
        for offset in range(3):
            s_dt = start_dt - timedelta(days=offset)
            e_dt = end_dt - timedelta(days=offset)
            try:
                data = nse.historical(symbol, "EQ", s_dt, e_dt, "5m")
                if data is not None and not data.empty:
                    break
            except Exception:
                continue
    except Exception:
        data = None

    # Attempt 2: YFinance Fallback if OpenChart failed / blocked
    if data is None or data.empty:
        data = fetch_yfinance_data(symbol)

    if data is None or data.empty or len(data) < 3:
        return None

    # Standardize DataFrame columns
    data.columns = [str(c).strip().lower() for c in data.columns]
    
    # Datetime column indexing
    if "timestamp" in data.columns:
        data["datetime"] = pd.to_datetime(data["timestamp"])
        data = data.set_index("datetime")
    elif "date" in data.columns:
        data["datetime"] = pd.to_datetime(data["date"])
        data = data.set_index("datetime")

    # Filter Market Hours (09:15 to 15:30)
    if isinstance(data.index, pd.DatetimeIndex):
        data = data[(data.index.time >= pd.Timestamp("09:15").time()) & 
                    (data.index.time <= pd.Timestamp("15:30").time())]

    if len(data) < 3:
        return None

    try:
        orb_candles = data.iloc[:3]
        orb_high = float(orb_candles["high"].max())
        orb_low = float(orb_candles["low"].min())
        day_open = float(data.iloc[0]["open"])

        scan_data = data.iloc[3:].copy()
        for ts, row in scan_data.iterrows():
            high, low, close = float(row["high"]), float(row["low"]), float(row["close"])
            time_str = ts.strftime("%H:%M") if hasattr(ts, 'strftime') else str(ts)
            
            if high >= orb_high:
                pct = round(((close - day_open) / day_open) * 100, 2)
                return {"symbol": symbol, "signal": "BUY", "time": time_str, "price": round(close, 2), "pct": pct}

            if low <= orb_low:
                pct = round(((close - day_open) / day_open) * 100, 2)
                return {"symbol": symbol, "signal": "SELL", "time": time_str, "price": round(close, 2), "pct": pct}
    except Exception:
        return None

    return None

# ============================================================
# SCAN EXECUTION
# ============================================================
results = []
print(f"Scanning {len(symbols)} stocks using {MAX_WORKERS} parallel threads...")

start_time = datetime.now()

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(process_single_symbol, sym): sym for sym in symbols}
    for future in as_completed(futures):
        res = future.result()
        if res:
            results.append(res)
            print(f"-> [{res['signal']}] {res['symbol']} @ {res['time']} (Price: {res['price']})")

duration = (datetime.now() - start_time).total_seconds()
print("\n" + "=" * 75)
print(f"SCAN COMPLETED IN {round(duration, 2)} SECONDS")
print("=" * 75)

if results:
    df_res = pd.DataFrame(results).sort_values(by="time")
    print(df_res.to_string(index=False))
    df_res.to_csv("screener_results.csv", index=False)
else:
    print("NO SIGNALS DETECTED")
