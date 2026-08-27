import os
import time
import random
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests

print("=" * 75)
print("NSE DIRECT F&O SCREENER (FAST BROWSER ENGINE)")
print("=" * 75)

MAX_WORKERS = 5  # Speed badhane ke liye workers 5 kar diye hain

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

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/"
}

def fetch_intraday_candles(symbol):
    url = f"https://www.nseindia.com/api/chart-databyindex?index={symbol}EQ"
    try:
        # Fast 3 second timeout taaki hang na ho
        res = requests.get(url, headers=headers, impersonate="chrome120", timeout=3)
        if res.status_code == 200:
            raw_data = res.json()
            if "grapthData" in raw_data and raw_data["grapthData"]:
                df = pd.DataFrame(raw_data["grapthData"], columns=["timestamp", "price"])
                df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df.set_index("datetime")
                df_5m = df["price"].resample("5min").ohlc().dropna()
                return df_5m
    except Exception:
        return None
    return None

def process_single_symbol(symbol):
    data = fetch_intraday_candles(symbol)
    if data is None or len(data) < 3:
        return None

    try:
        orb_candles = data.iloc[:3]
        orb_high = float(orb_candles["high"].max())
        orb_low = float(orb_candles["low"].min())
        day_open = float(data.iloc[0]["open"])

        scan_data = data.iloc[3:].copy()
        for ts, row in scan_data.iterrows():
            high, low, close = float(row["high"]), float(row["low"]), float(row["close"])
            time_str = ts.strftime("%H:%M")
            
            if high >= orb_high:
                pct = round(((close - day_open) / day_open) * 100, 2)
                return {"symbol": symbol, "signal": "BUY", "time": time_str, "price": round(close, 2), "pct": pct}

            if low <= orb_low:
                pct = round(((close - day_open) / day_open) * 100, 2)
                return {"symbol": symbol, "signal": "SELL", "time": time_str, "price": round(close, 2), "pct": pct}
    except Exception:
        return None

    return None

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
