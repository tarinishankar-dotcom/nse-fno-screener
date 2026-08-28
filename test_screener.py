import os
import time
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from curl_cffi import requests

MAX_WORKERS = 3
BATCH_SIZE = 30
REQUEST_TIMEOUT = 6
BASE_SLEEP = 0.8
MAX_RETRIES = 4
COOLDOWN_AFTER_429 = 600

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

session = requests.Session()

def init_session():
    try:
        session.get("https://www.nseindia.com/", headers=headers, impersonate="chrome120", timeout=REQUEST_TIMEOUT)
        return True
    except Exception:
        return False

def get_live_fno_futures():
    try:
        if not init_session():
            raise RuntimeError("session init failed")
        url = "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O"
        res = session.get(url, headers=headers, impersonate="chrome120", timeout=REQUEST_TIMEOUT)
        if res.status_code == 200:
            data = res.json().get("data", [])
            syms = [x.get("symbol") for x in data if x.get("symbol")]
            return list(dict.fromkeys(syms))
    except Exception:
        pass
    return ["SBIN", "RELIANCE", "INFY", "TATAMOTORS", "ICICIBANK"]

def fetch_json(url):
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, headers=headers, impersonate="chrome120", timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return r.json(), 200, None
            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                wait = int(ra) if ra and ra.isdigit() else min(COOLDOWN_AFTER_429, 2 ** attempt + random.uniform(0.5, 1.5))
                return None, 429, wait
            time.sleep(min(8, (2 ** attempt) + random.uniform(0.2, 1.2)))
        except Exception:
            time.sleep(min(8, (2 ** attempt) + random.uniform(0.2, 1.2)))
    return None, None, None

def check_price_only(symbol):
    url = f"https://www.nseindia.com/api/chart-databyindex?index={symbol}EQ"
    raw, status, wait = fetch_json(url)

    if status == 429:
        return {"symbol": symbol, "status": "rate_limited", "cooldown_s": wait}
    if not raw:
        return None

    gd = raw.get("grapthData") or raw.get("graphData") or []
    if not gd:
        return None

    df = pd.DataFrame(gd, columns=["timestamp", "price", "volume"] if len(gd[0]) >= 3 else ["timestamp", "price"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", errors="coerce")
    df = df.dropna(subset=["datetime"]).set_index("datetime").sort_index()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price"])
    
    if df.empty:
        return None

    latest_price = float(df.iloc[-1]["price"])
    total_candles = len(df)
    
    print(f"[PRICE CHECK] {symbol} -> Latest Price: {latest_price} | Total Data Points: {total_candles}")
    
    return {
        "symbol": f"{symbol}FUT",
        "latest_price": latest_price,
        "total_candles": total_candles
    }

if __name__ == "__main__":
    symbols = get_live_fno_futures()[:210]
    print(f"Checking live prices for {len(symbols)} symbols...")
    start = datetime.now()

    results = []
    cooldown_until = 0

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        while time.time() < cooldown_until:
            time.sleep(1)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            fut_map = {executor.submit(check_price_only, s): s for s in batch}
            for fut in as_completed(fut_map):
                res = fut.result()
                if isinstance(res, dict) and res.get("status") == "rate_limited":
                    cooldown_until = time.time() + int(res.get("cooldown_s") or COOLDOWN_AFTER_429)
                    break
                if res:
                    results.append(res)

        time.sleep(BASE_SLEEP + random.uniform(0.2, 0.8))

    duration = (datetime.now() - start).total_seconds()
    print(f"\nCompleted in {duration:.2f}s. Successfully fetched prices for {len(results)} symbols.")
