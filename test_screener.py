import os
import time
import random
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from openchart import NSEData

# ============================================================
# FIXED F&O SCREENER (OPENCHART COMPATIBLE)
# ============================================================
print("=" * 75)
print("NSE F&O SCREENER (OPENCHART SYSTEM)")
print("=" * 75)

MAX_WORKERS = 3

# Step 1: Initialize & Download Master DB
print("Initializing OpenChart Master Data...")
nse = NSEData()
try:
    nse.download()
    print("Master data updated successfully!")
except Exception as e:
    print(f"Warning during master download: {e}")

# Step 2: Load Symbols from local CSV
def load_stock_futures():
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
    """ Safe worker function using standard exchange tag """
    time.sleep(random.uniform(0.1, 0.3))
    try:
        data = None
        for offset in range(3):
            s_dt = start_dt - timedelta(days=offset)
            e_dt = end_dt - timedelta(days=offset)
            try:
                # Correct exchange parameter set to 'NSE'
                data = nse.historical(
                    symbol=symbol,
                    exchange='NSE',
                    start=s_dt,
                    end=e_dt,
                    interval='5m'
                )
                if data is not None and not data.empty:
                    break
            except Exception:
                continue

        if data is None or data.empty or len(data) < 3:
            return None

        data.columns = [str(c).strip().lower() for c in data.columns]
        if "timestamp" in data.columns:
            data = data.set_index(pd.to_datetime(data["timestamp"]))
        
        data = data[(data.index.time >= pd.Timestamp("09:15").time()) & 
                    (data.index.time <= pd.Timestamp("15:30").time())]

        if len(data) < 3:
            return None

        orb_candles = data.iloc[:3]
        orb_high = float(orb_candles["high"].max())
        orb_low = float(orb_candles["low"].min())
        day_open = float(data.iloc[0]["open"])

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
