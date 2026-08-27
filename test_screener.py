import os
import requests
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from openchart import NSEData

# ============================================================
# FAST MULTI-THREADED F&O SCREENER
# ============================================================
print("=" * 75)
print("NSE F&O FAST MULTI-THREADED SCREENER")
print("=" * 75)

VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.5
MAX_WORKERS = 15  # 15 Parallel Threads

MASTER_URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://www.nseindia.com/"
}

def load_stock_futures():
    try:
        r = requests.get(MASTER_URL, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            df = pd.read_csv(BytesIO(r.content))
            df.columns = [str(c).strip().upper() for c in df.columns]
            sym_col = "SYMBOL" if "SYMBOL" in df.columns else "UNDERLYING"
            symbols = df[sym_col].astype(str).str.strip().dropna().unique().tolist()
            indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"]
            return [s for s in symbols if s not in indices and not s.startswith("UNDERLYING")]
    except Exception:
        pass
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

def process_single_symbol(symbol):
    """ Worker function to process a single symbol independently """
    try:
        # Fetch Intraday Data
        data = None
        for offset in range(3):
            s_dt = start_dt - timedelta(days=offset)
            e_dt = end_dt - timedelta(days=offset)
            try:
                data = nse.historical(symbol, "FO", s_dt, e_dt, "5m")
                if data is not None and len(data) > 0:
                    break
            except Exception:
                continue

        if data is None or len(data) < 3:
            return None

        # Standardize Columns
        data.columns = [str(c).strip().lower() for c in data.columns]
        if "timestamp" in data.columns:
            data = data.set_index(pd.to_datetime(data["timestamp"]))
        
        # Filter Market Hours
        data = data[(data.index.time >= pd.Timestamp("09:15").time()) & 
                    (data.index.time <= pd.Timestamp("15:30").time())]

        if len(data) < 3:
            return None

        # ORB High / Low
        orb_candles = data.iloc[:3]
        orb_high = float(orb_candles["high"].max())
        orb_low = float(orb_candles["low"].min())
        day_open = float(data.iloc[0]["open"])

        # PDH / PDL Calculation
        pdh, pdl = orb_high, orb_low  # Fallback to ORB if PDH absent

        # Signal Scan
        scan_data = data.iloc[3:].copy()
        for ts, row in scan_data.iterrows():
            high, low, close = float(row["high"]), float(row["low"]), float(row["close"])
            
            if high >= orb_high:
                pct = round(((close - day_open) / day_open) * 100, 2)
                return {"symbol": symbol, "signal": "BUY", "time": ts.strftime("%H:%M"), "price": round(close, 2), "pct": pct}

            if low <= orb_low:
                pct = round(((close - day_open) / day_open) * 100, 2)
                return {"symbol": symbol, "signal": "SELL", "time": ts.strftime("%H:%M"), "price": round(close, 2), "pct": pct}

    except Exception:
        return None
    return None

# ============================================================
# MULTI-THREADED SCAN EXECUTION
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
