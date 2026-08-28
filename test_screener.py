import os
from datetime import datetime, timedelta
import pandas as pd
import requests
import io
import zipfile

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
    print("Initializing F&O Futures Screener via Direct NSE Bhavcopy...")
    symbols = get_fno_symbols()
    
    # Pichle kuch dino mein se sabse recent trading date nikalna (weekend/holiday handle karne ke liye)
    target_date = datetime.now().date() - timedelta(days=1)
    df_stk_fut = None
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/"
    }

    # Pichle 5 dino ka data check karega jab tak bhavcopy zip file na mil jaye
    for _ in range(5):
        try:
            date_str = target_date.strftime("%d%b%Y").upper()
            year_str = target_date.strftime("%Y")
            month_str = target_date.strftime("%b").upper()
            
            # NSE derivatives bhavcopy URL format
            url = f"https://archives.nseindia.com/content/historical/DERIVATIVES/{year_str}/{month_str}/fo{date_str}bhav.csv.zip"
            print(f"Trying to download Bhavcopy for: {target_date}")
            
            session = requests.Session()
            # Pehle cookies set karne ke liye main site hit karte hain
            session.get("https://www.nseindia.com", headers=headers, timeout=10)
            
            res = session.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                z = zipfile.ZipFile(io.BytesIO(res.content))
                csv_filename = z.namelist()[0]
                with z.open(csv_filename) as f:
                    df_stk_fut = pd.read_csv(f)
                break
        except Exception as e:
            pass
            
        target_date -= timedelta(days=1)
        
    if df_stk_fut is None or df_stk_fut.empty:
        print("NO DATA FETCHED: Could not retrieve derivatives bhavcopy zip.")
        return

    # Columns ko clean karna
    df_stk_fut.columns = [str(c).strip().upper() for c in df_stk_fut.columns]
    
    # Sirf Stock Futures (FUTSTK) ko filter karna
    if 'INSTRUMENT' in df_stk_fut.columns:
        df_stk_fut = df_stk_fut[df_stk_fut['INSTRUMENT'].str.contains('FUTSTK', na=False)]

    results = []
    for symbol in symbols:
        match = df_stk_fut[df_stk_fut['SYMBOL'].str.strip() == symbol]
        if not match.empty:
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
