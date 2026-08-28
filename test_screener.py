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
        session.get(
            "https://www.nseindia.com/",
            headers=headers,
            impersonate="chrome120",
            timeout=REQUEST_TIMEOUT,
        )
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

    csv_file = "stock_futures.csv"
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            df.columns = [str(c).strip().lower() for c in df.columns]
            if "symbol" in df.columns:
                return df["symbol"].astype(str).str.strip().dropna().unique().tolist()
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


def parse_chart(symbol):
    url = f"https://www.nseindia.com/api/chart-databyindex?index={symbol}EQ"
    raw, status, wait = fetch_json(url)

    if status == 429:
        return {"symbol": symbol, "status": "rate_limited", "cooldown_s": wait}

    if not raw:
        return None

    gd = raw.get("grapthData") or raw.get("graphData") or []
    if not gd:
        return None

    if len(gd[0]) >= 3:
        df = pd.DataFrame(gd, columns=["timestamp", "price", "volume"])
    else:
        df = pd.DataFrame(gd, columns=["timestamp", "price"])
        df["volume"] = 0

    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", errors="coerce")
    df = df.dropna(subset=["datetime"]).set_index("datetime").sort_index()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df = df.dropna(subset=["price"])
    if df.empty:
        return None

    df_1m = df["price"].resample("1min").ohlc()
    df_1m["volume"] = df["volume"].resample("1min").sum()
    df_1m = df_1m.dropna()

    df_5m = df["price"].resample("5min").ohlc()
    df_5m["volume"] = df["volume"].resample("5min").sum()
    df_5m = df_5m.dropna()

    if len(df_5m) < 3 or len(df_1m) < 16:
        return None

    day_open = float(df_1m.iloc[0]["open"])
    day_high = float(df_1m["high"].max())
    day_low = float(df_1m["low"].min())
    day_close = float(df_1m.iloc[-1]["close"])

    orb_candles = df_5m.iloc[:3]
    orb_high = float(orb_candles["high"].max())
    orb_low = float(orb_candles["low"].min())
    avg_vol = orb_candles["volume"].mean()
    has_volume_spike = any(orb_candles["volume"] >= (1.5 * avg_vol)) if avg_vol > 0 else True

    if not has_volume_spike:
        return None

    scan_1m = df_1m.iloc[15:].copy()
    for ts, row in scan_1m.iterrows():
        high, low, close = float(row["high"]), float(row["low"]), float(row["close"])
        time_str = ts.strftime("%H:%M")

        signal_move_pct = round(((close - day_open) / day_open) * 100, 2)
        day_change_pct = round(((day_close - day_open) / day_open) * 100, 2)

        if high >= orb_high:
            return {
                "symbol": f"{symbol}FUT",
                "signal": "BUY",
                "time": time_str,
                "price": round(close, 2),
                "signal_move_%": signal_move_pct,
                "day_open": day_open,
                "day_high": day_high,
                "day_low": day_low,
                "day_close": day_close,
                "day_change_%": day_change_pct,
            }

        if low <= orb_low:
            return {
                "symbol": f"{symbol}FUT",
                "signal": "SELL",
                "time": time_str,
                "price": round(close, 2),
                "signal_move_%": signal_move_pct,
                "day_open": day_open,
                "day_high": day_high,
                "day_low": day_low,
                "day_close": day_close,
                "day_change_%": day_change_pct,
            }

    return None


def scan_symbols(symbols):
    results = []
    cooldown_until = 0

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]

        while time.time() < cooldown_until:
            time.sleep(1)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            fut_map = {executor.submit(parse_chart, s): s for s in batch}
            for fut in as_completed(fut_map):
                res = fut.result()
                if isinstance(res, dict) and res.get("status") == "rate_limited":
                    cooldown_until = time.time() + int(res.get("cooldown_s") or COOLDOWN_AFTER_429)
                    break
                if res:
                    results.append(res)

        time.sleep(BASE_SLEEP + random.uniform(0.2, 0.8))

    return results


if __name__ == "__main__":
    symbols = get_live_fno_futures()[:210]
    print(f"Scanning {len(symbols)} symbols...")
    start = datetime.now()

    results = scan_symbols(symbols)

    duration = (datetime.now() - start).total_seconds()
    print(f"Completed in {duration:.2f}s")

    if results:
        df_res = pd.DataFrame(results).sort_values(by="time")
        df_res.to_csv("nse_fno_signals.csv", index=False)
        print(df_res.to_string(index=False))
        print("Saved: nse_fno_signals.csv")
    else:
        print("NO SIGNALS MATCHING VOLUME & ORB CRITERIA")
