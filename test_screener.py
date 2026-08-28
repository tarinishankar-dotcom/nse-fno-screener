import os
from datetime import datetime, timedelta
import pandas as pd
from jugaad_data.nse import bhavcopy_save, nse_derivatives_bhavcopy

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
    print("Initializing F&O Futures Screener using jugaad-data Bhavcopy...")
    symbols = get_fno_symbols()
    
    # Pichle kuch dino mein se sabse recent trading date nikalna (weekend ya holiday handle karne ke liye)
    target_date = datetime.now().date() - timedelta(days=1)
    
    df_futures = None
    for i in range(5):  # Pichle 5 dino tak try karega jab tak data na mil jaye
        try:
            print(f"Trying to fetch F&O Bhavcopy for date: {target_date}")
            df_futures = nse_derivatives_bhavcopy(target_date)
            if df_futures is not None and not df_futures.empty:
                break
        except Exception as e:
            pass
        target_date -= timedelta(days=1)
        
    if df_futures is None or df_futures.empty:
        print("NO DATA FETCHED: Could not retrieve derivatives bhavcopy.")
        return

    # Columns ko clean karna
    df_futures.columns = [str(c).strip().upper() for c in df_futures.columns]
    
    # Sirf Stock Futures (FUTSTK) ko filter karna (Index futures ko chhod kar)
    if 'INSTRUMENT' in df_futures.columns:
        df_stk_fut = df_futures[df_futures['INSTRUMENT'].str.contains('FUTSTK', na=False)]
    else:
        df_stk_fut = df_futures

    results = []
    for symbol in symbols:
        match = df_stk_fut[df_stk_fut['SYMBOL'].str.strip() == symbol]
        if not match.empty:
            # Nearest expiry contract ko pehle lena
            row = match.iloc[0]
            results.append({
                "symbol": f"{symbol}FUT",
                "expiry": row.get("EXPIRY_DT", ""),
                "last_price": row.get("CLOSE_PRICE", row.get("SETTLE_PR", 0)),
                "day_open": row.get("OPEN_PRICE", 0),
                "day_high": row.get("HIGH_PRICE", 0),
                "day_low": row.get("LOW_PRICE", 0),
                "timestamp": datetime.now().strftime("%Y-%m-%d")
            })
            print(f"[SUCCESS] {symbol}FUT -> Close: {row.get('CLOSE_PRICE', 0)}")

    if results:
        out_df = pd.DataFrame(results)
        out_df.to_csv("nse_fno_signals.csv", index=False)
        print("\n--- SCAN COMPLETED ---")
        print(out_df.head(10).to_string(index=False))
        print("Saved to nse_fno_signals.csv")
    else:
        print("NO DATA FETCHED for given symbols.")

if __name__ == "__main__":
    scan_market()
