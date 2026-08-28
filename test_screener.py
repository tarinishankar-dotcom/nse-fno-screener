import os
import time
from datetime import datetime
import pandas as pd
from curl_cffi import requests

def get_fno_symbols():
    """Local stock_futures.csv file se symbols load karta hai"""
    csv_file = "stock_futures.csv"
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            df.columns = [str(c).strip().lower() for c in df.columns]
            for col in ["symbol", "ticker", "stock"]:
                if col in df.columns:
                    symbols = df[col].astype(str).str.strip().dropna().unique().tolist()
                    print(f"Loaded {len(symbols)} symbols from {csv_file}")
                    return symbols
        except Exception as e:
            print(f"Error reading stock_futures.csv: {e}")
            
    return ["SBIN", "RELIANCE", "INFY", "TATAMOTORS", "ICICIBANK"]

def scan_market():
    print("Initializing F&O Screener using curl_cffi...")
    symbols = get_fno_symbols()
    print(f"Total symbols to process: {len(symbols)}")
    
    results = []
    
    # Session setup with proper headers to bypass NSE restrictions
    session = requests.Session(impersonate="chrome")
    
    # Pehle NSE cookies set karne ke liye main site hit karte hain
    try:
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(1)
    except Exception as e:
        print(f"Initial NSE handshake warning: {e}")

    for symbol in symbols:
        clean_symbol = symbol.replace("FUT", "").strip()
        url = f"https://www.nseindia.com/api/quote-equity?symbol={clean_symbol}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/"
        }
        
        try:
            response = session.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                price_info = data.get("priceInfo", {})
                
                last_price = price_info.get("lastPrice", 0)
                day_open = price_info.get("open", 0)
                day_high = price_info.get("intraDayHighLow", {}).get("max", 0)
                day_low = price_info.get("intraDayHighLow", {}).get("min", 0)
                
                if last_price > 0:
                    print(f"[SUCCESS] {clean_symbol} -> Price: {last_price} | Open: {day_open}")
                    results.append({
                        "symbol": f"{clean_symbol}FUT",
                        "last_price": last_price,
                        "day_open": day_open,
                        "day_high": day_high,
                        "day_low": day_low,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
            else:
                print(f"Skipping {clean_symbol}: HTTP status {response.status_code}")
                
            time.sleep(0.4) # Server safety delay
            
        except Exception as e:
            print(f"Error fetching {clean_symbol}: {e}")
            continue

    if results:
        df = pd.DataFrame(results)
        df.to_csv("nse_fno_signals.csv", index=False)
        print("\n--- SCAN COMPLETED ---")
        print(df.head(10).to_string(index=False))
        print("Saved to nse_fno_signals.csv")
    else:
        print("NO DATA FETCHED")

if __name__ == "__main__":
    scan_market()
