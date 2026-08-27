import requests
import pandas as pd
from io import BytesIO

print("=" * 70)
print("CURRENT NSE F&O FUTURES - FULL DISCOVERY")
print("=" * 70)

URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/csv,application/csv,*/*",
    "Referer": "https://www.nseindia.com/"
}

print("\n[1] DOWNLOADING NSE F&O MASTER...")

r = requests.get(URL, headers=HEADERS, timeout=30)

print("HTTP STATUS:", r.status_code)
print("DATA SIZE:", len(r.content), "bytes")

if r.status_code != 200:
    raise Exception(f"NSE returned HTTP {r.status_code}")

df = pd.read_csv(BytesIO(r.content))

# Clean column names
df.columns = [str(c).strip() for c in df.columns]

# Clean text
for col in df.columns:
    if df[col].dtype == "object":
        df[col] = df[col].astype(str).str.strip()

print("\n[2] MASTER DATA")
print("TOTAL ROWS:", len(df))
print("COLUMNS:", list(df.columns))

# ---------------------------------------------------------
# Identify underlying and symbol columns
# ---------------------------------------------------------

underlying_col = df.columns[0]
symbol_col = df.columns[1]

df[underlying_col] = (
    df[underlying_col]
    .astype(str)
    .str.strip()
)

df[symbol_col] = (
    df[symbol_col]
    .astype(str)
    .str.strip()
)

# Remove blank rows
df = df[
    (df[underlying_col] != "") &
    (df[symbol_col] != "") &
    (df[symbol_col].str.lower() != "symbol")
].copy()

# ---------------------------------------------------------
# Separate index and stock futures
# ---------------------------------------------------------

index_symbols = {
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYNXT50",
    "NIFTYFPI"
}

index_rows = df[
    df[symbol_col].str.upper().isin(index_symbols)
].copy()

stock_rows = df[
    ~df[symbol_col].str.upper().isin(index_symbols)
].copy()

# ---------------------------------------------------------
# Create simplified futures list
# ---------------------------------------------------------

index_out = pd.DataFrame({
    "underlying": index_rows[underlying_col],
    "symbol": index_rows[symbol_col],
    "type": "INDEX_FUTURE"
})

stock_out = pd.DataFrame({
    "underlying": stock_rows[underlying_col],
    "symbol": stock_rows[symbol_col],
    "type": "STOCK_FUTURE"
})

# Remove duplicate symbols
index_out = index_out.drop_duplicates(
    subset=["symbol"]
).reset_index(drop=True)

stock_out = stock_out.drop_duplicates(
    subset=["symbol"]
).reset_index(drop=True)

# ---------------------------------------------------------
# Save files
# ---------------------------------------------------------

index_out.to_csv(
    "index_futures.csv",
    index=False
)

stock_out.to_csv(
    "stock_futures.csv",
    index=False
)

all_out = pd.concat(
    [index_out, stock_out],
    ignore_index=True
)

all_out.to_csv(
    "current_futures.csv",
    index=False
)

# ---------------------------------------------------------
# Display result
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("FULL NSE F&O FUTURES RESULT")
print("=" * 70)

print("\nTOTAL UNDERLYINGS:", len(df))
print("INDEX FUTURES:", len(index_out))
print("STOCK FUTURES:", len(stock_out))
print("TOTAL UNIQUE FUTURES:", len(all_out))

print("\n" + "-" * 70)
print("INDEX FUTURES")
print("-" * 70)

if len(index_out):
    print(index_out.to_string(index=False))
else:
    print("NONE FOUND")

print("\n" + "-" * 70)
print("STOCK FUTURES - ALL")
print("-" * 70)

print(stock_out.to_string(index=False))

print("\n" + "=" * 70)
print("FILES CREATED")
print("=" * 70)

print("current_futures.csv")
print("stock_futures.csv")
print("index_futures.csv")

# ---------------------------------------------------------
# Validation
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("VALIDATION")
print("=" * 70)

if len(stock_out) < 150:
    raise Exception(
        f"FAILED: Only {len(stock_out)} stock futures found. "
        "Expected substantially more than 150."
    )

print(
    f"SUCCESS: {len(stock_out)} stock futures found."
)

print("\nSTEP 3 COMPLETE")
print("=" * 70)
