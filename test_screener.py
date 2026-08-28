import os
import time
from datetime import datetime
import pandas as pd
from jugaad_data.nse import NSELive

def get_fno_symbols():
    """Pehle live NSE se symbols fetch karne ki koshish karega, fail hone par stock_futures.csv use karega"""
    try:
        nse = NSELive()
        q = nse.stock_watch("SECURITIES IN F&O")
        data = q.get("data", [])
        symbols = [item.get("symbol") for item in data if item.get("symbol")]
        if symbols:
            print("Successfully loaded symbols from live NSE.")
            return list(dict.fromkeys(symbols))
    except Exception as e:
        print(f"Live fetch warning: {e}. Falling back to local stock_futures.csv...")

    # Fallback to local stock_futures.csv present in the repository
    csv_file = "stock_futures.csv"
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            df.columns = [str(c).strip().lower() for c in df.columns]
            if "symbol" in df.columns:
                symbols = df["symbol"].astype(str).str.strip().dropna().unique().tolist()
                print(f"Loaded {len(symbols)} symbols from stock_futures.csv")
                return symbols
        except Exception as e:
            print(f"Error reading stock_futures.csv: {e}")

    return ["SBIN", "RELIANCE", "INFY", "TATAMOTORS", "ICICIBANK"]

def scan_market():
    print("Initializing F&O Screener using jugaad-data...")
    nse = NSELive()
    symbols = get_fno_symbols()
    print(f"Total symbols to process: {len(symbols)}")
    
    results = []
    
    for symbol in symbols:
        try:
            quote = nse.stock_quote(symbol)
            price_info = quote.get("priceInfo", {})
            
            last_price = price_info.get("lastPrice", 0)
            day_open = price_info.get("open", 0)
            day_high = price_info.get("intraDayHighLow", {}).get("max", 0)
            day_low = price_info.get("intraDayHighLow", {}).get("min", 0)
            
            if last_price > 0:
                print(f"[SUCCESS] {symbol} -> Price: {last_price} | Open: {day_open}")
                results.append({
                    "symbol": f"{symbol}FUT",
                    "last_price": last_price,
                    "day_open": day_open,
                    "day_high": day_high,
                    "day_low": day_low,
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
            
            time.sleep(0.3) # Server safety delay
            
        except Exception as e:
            print(f"Skipping {symbol}: error fetching quote")
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
