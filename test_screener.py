import os
import time
from datetime import datetime
import pandas as pd
from nsepython import nse_eq

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
                    return [s.replace("FUT", "").strip() for s in symbols]
        except Exception as e:
            print(f"Error reading stock_futures.csv: {e}")
            
    return ["SBIN", "RELIANCE", "INFY", "TATAMOTORS", "ICICIBANK"]

def scan_market():
    print("Initializing F&O Futures Screener using nsepython...")
    symbols = get_fno_symbols()
    print(f"Total symbols to process: {len(symbols)}")
    
    results = []
    
    for symbol in symbols:
        clean_symbol = symbol.replace("FUT", "").strip()
        try:
            # nsepython ka use karke equity/derivative details lena
            data = nse_eq(clean_symbol)
            if data and "priceInfo" in data:
                price_info = data["priceInfo"]
                last_price = price_info.get("lastPrice", 0)
                day_open = price_info.get("open", 0)
                day_high = price_info.get("intraDayHighLow", {}).get("max", 0)
                day_low = price_info.get("intraDayHighLow", {}).get("min", 0)
                
                if last_price > 0:
                    print(f"[SUCCESS] {clean_symbol}FUT -> Price: {last_price} | Open: {day_open}")
                    results.append({
                        "symbol": f"{clean_symbol}FUT",
                        "last_price": last_price,
                        "day_open": day_open,
                        "day_high": day_high,
                        "day_low": day_low,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
            else:
                print(f"Skipping {clean_symbol}: No data found")
                
            time.sleep(0.3) # Server throttling se bachne ke liye chota delay
            
        except Exception as e:
            print(f"Error fetching {clean_symbol}: {e}")
            continue

    if results:
        out_df = pd.DataFrame(results)
        out_df.to_csv("nse_fno_signals.csv", index=False)
        print("\n--- SCAN COMPLETED ---")
        print(out_df.head(10).to_string(index=False))
        print("Saved to nse_fno_signals.csv")
    else:
        print("NO DATA FETCHED")

if __name__ == "__main__":
    scan_market()
