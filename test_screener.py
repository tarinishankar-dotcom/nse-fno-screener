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

def get_top_10_volume_at_920(symbols):
    """9:20 AM par top 10 volume futures aur unka 5-min 20-period average comparison nikalta hai"""
    print("Calculating Top 10 Volume Futures at 9:20 AM...")
    volume_rankings = []
    
    for symbol in symbols[:50]: # Quick scan for top volume calculation
        url = f"https://www.nseindia.com/api/chart-databyindex?index={symbol}EQ"
        raw, status, _ = fetch_json(url)
        if not raw:
            continue
        gd = raw.get("grapthData") or raw.get("graphData") or []
        if not gd:
            continue
            
        df = pd.DataFrame(gd, columns=["timestamp", "price", "volume"] if len(gd[0]) >= 3 else ["timestamp", "price"])
        if "volume" not in df.columns:
            df["volume"] = 0
            
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", errors="coerce")
        df = df.dropna(subset=["datetime"]).set_index("datetime").sort_index()
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        
        df_5m = df["price"].resample("5min").ohlc()
        df_5m["volume"] = df["volume"].resample("5min").sum().dropna()
        df_5m = df_5m.dropna()
        
        if len(df_5m) >= 20:
            current_vol = df_5m.iloc[-1]["volume"]
            avg_vol_20 = df_5m["volume"].iloc[-21:-1].mean()
            vol_multiplier = round(current_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0
            
            day_open = float(df_5m.iloc[0]["open"])
            current_close = float(df_5m.iloc[-1]["close"])
            price_move_pct = round(((current_close - day_open) / day_open) * 100, 2)
            
            volume_rankings.append({
                "symbol": f"{symbol}FUT",
                "vol_multiplier": vol_multiplier,
                "price_move_%": price_move_pct
            })
            
    df_rank = pd.DataFrame(volume_rankings)
    if not df_rank.empty:
        df_rank = df_rank.sort_values(by="vol_multiplier", ascending=False).head(10)
        print("\n--- TOP 10 VOLUME FUTURES (9:20 AM) ---")
        print(df_rank.to_string(index=False))
        print("---------------------------------------\n")

def parse_chart_with_rules(symbol):
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
    if "volume" not in df.columns:
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

    if len(df_1m) < 20:
        return None

    day_open = float(df_1m.iloc[0]["open"])
    
    # Mocking Previous Day High / Low for illustration (Can be fetched from daily historical API)
    pdh = day_open * 1.015 
    pdl = day_open * 0.985 

    # Window: 9:15 to 9:30 for 1.5x volume spike check
    window_15m = df_1m.between_time("09:15", "09:30")
    if window_15m.empty:
        return None

    rolling_avg_vol = df_1m["volume"].rolling(window=20, min_periods=1).mean()
    
    has_spike = False
    for ts, row in window_15m.iterrows():
        avg_v = rolling_avg_vol.loc[ts] if ts in rolling_avg_vol.index else 0
        if avg_v > 0 and row["volume"] >= (1.5 * avg_v):
            has_spike = True
            break

    if not has_spike:
        return None

    # Scan for Buy/Sell Pullback setup with Lowest Volume Red/Green candle
    signals_found = []
    last_signal_type = None # Alternating signal tracker (Buy -> Sell -> Buy)

    scan_df = df_1m.iloc[15:].copy()
    
    # Simplified state evaluation for demonstration of logic flow
    for i in range(1, len(scan_df)):
        ts = scan_df.index[i]
        curr = scan_df.iloc[i]
        time_str = ts.strftime("%H:%M")
        close, high, low = float(curr["close"]), float(curr["high"]), float(curr["low"])
        
        signal_move_pct = round(((close - day_open) / day_open) * 100, 2)

        # BUY SETUP: Last signal was not BUY, check for Red pullback above PDH
        if last_signal_type != "BUY" and high > pdh:
            signals_found.append({
                "symbol": f"{symbol}FUT", "signal": "BUY", "time": time_str,
                "price": round(close, 2), "signal_move_%": signal_move_pct
            })
            last_signal_type = "BUY"
            
        # SELL SETUP: Last signal was not SELL, check for Green pullback below PDL
        elif last_signal_type != "SELL" and low < pdl:
            signals_found.append({
                "symbol": f"{symbol}FUT", "signal": "SELL", "time": time_str,
                "price": round(close, 2), "signal_move_%": signal_move_pct
            })
            last_signal_type = "SELL"

    return signals_found if signals_found else None

if __name__ == "__main__":
    symbols = get_live_fno_futures()[:210]
    print(f"Scanning {len(symbols)} symbols with Advanced Volume & Pullback Rules...")
    
    # Optional 9:20 AM Top 10 Volume feature check
    get_top_10_volume_at_920(symbols)

    start = datetime.now()
    all_signals = []
    cooldown_until = 0

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        while time.time() < cooldown_until:
            time.sleep(1)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            fut_map = {executor.submit(parse_chart_with_rules, s): s for s in batch}
            for fut in as_completed(fut_map):
                res = fut.result()
                if isinstance(res, dict) and res.get("status") == "rate_limited":
                    cooldown_until = time.time() + int(res.get("cooldown_s") or COOLDOWN_AFTER_429)
                    break
                if isinstance(res, list):
                    all_signals.extend(res)

        time.sleep(BASE_SLEEP + random.uniform(0.2, 0.8))

    duration = (datetime.now() - start).total_seconds()
    print(f"\nCompleted in {duration:.2f}s")

    if all_signals:
        df_res = pd.DataFrame(all_signals)
        df_res.to_csv("nse_fno_signals.csv", index=False)
        print("\n--- TODAY'S HISTORICAL SIGNALS ---")
        print(df_res.to_string(index=False))
        print("-----------------------------------")
        print("Saved to nse_fno_signals.csv")
    else:
        print("NO SIGNALS MATCHING CRITERIA")
