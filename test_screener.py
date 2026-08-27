import os
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests

MAX_WORKERS = 8

def load_stock_futures():
    csv_file = "stock_futures.csv"
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            df.columns = [str(c).strip().lower() for c in df.columns]
            if "symbol" in df.columns:
                return df["symbol"].astype(str).str.strip().unique().tolist()
        except Exception:
            pass
    return ["RELIANCE", "SBIN", "INFY", "TATAMOTORS", "ICICIBANK"]

symbols = load_stock_futures()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/"
}

def fetch_data(symbol):
    url = f"https://www.nseindia.com/api/chart-databyindex?index={symbol}EQ"
    try:
        res = requests.get(url, headers=headers, impersonate="chrome120", timeout=4)
        if res.status_code == 200:
            raw_data = res.json()
            if "grapthData" in raw_data and raw_data["grapthData"]:
                df = pd.DataFrame(raw_data["grapthData"], columns=["timestamp", "price"])
                df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df.set_index("datetime")
                
                # Resampling Timeframes
                df_1m = df["price"].resample("1min").ohlc().dropna()
                df_5m = df["price"].resample("5min").ohlc().dropna()
                
                return df_1m, df_5m
    except Exception:
        return None, None
    return None, None

def process_single_symbol(symbol):
    df_1m, df_5m = fetch_data(symbol)
    if df_5m is None or len(df_5m) < 3:
        return None

    try:
        # Day Metrics
        day_open = float(df_1m.iloc[0]["open"])
        day_high = float(df_1m["high"].max())
        day_low = float(df_1m["low"].min())
        latest_price = float(df_1m.iloc[-1]["close"])

        # 5-Min Opening Range (First 15 Mins)
        orb_candles = df_5m.iloc[:3]
        orb_high = float(orb_candles["high"].max())
        orb_low = float(orb_candles["low"].min())

        # Scan 1-Min Data after 15 mins for exact breakout timing
        scan_1m = df_1m.iloc[15:].copy()
        for ts, row in scan_1m.iterrows():
            high, low, close = float(row["high"]), float(row["low"]), float(row["close"])
            time_str = ts.strftime("%H:%M")

            # Day Change Percentage
            day_pct = round(((latest_price - day_open) / day_open) * 100, 2)

            if high >= orb_high:
                return {
                    "symbol": symbol,
                    "signal": "BUY",
                    "time": time_str,
                    "price": round(close, 2),
                    "day_open": day_open,
                    "day_high": day_high,
                    "day_low": day_low,
                    "day_change_%": day_pct
                }

            if low <= orb_low:
                return {
                    "symbol": symbol,
                    "signal": "SELL",
                    "time": time_str,
                    "price": round(close, 2),
                    "day_open": day_open,
                    "day_high": day_high,
                    "day_low": day_low,
                    "day_change_%": day_pct
                }
    except Exception:
        return None

    return None

results = []
print(f"Scanning {len(symbols)} F&O stocks across 1M, 5M & Day levels...")
start_time = datetime.now()

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(process_single_symbol, sym): sym for sym in symbols}
    for future in as_completed(futures):
        res = future.result()
        if res:
            results.append(res)

duration = (datetime.now() - start_time).total_seconds()
print(f"\nCompleted in {round(duration, 2)} seconds\n")

if results:
    df_res = pd.DataFrame(results).sort_values(by="time")
    print(df_res.to_string(index=False))
else:
    print("NO SIGNALS DETECTED")
