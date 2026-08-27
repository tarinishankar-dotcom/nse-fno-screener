import openchart
import pandas as pd

print("=" * 60)
print("CURRENT NSE F&O FUTURES DISCOVERY - OPENCHART")
print("=" * 60)

# ---------------------------------------------------------
# OPENCHART
# ---------------------------------------------------------
nse = openchart.NSEData()

print("\n[1] SEGMENTS")
print(nse.segments())

print("\n[2] TIMEFRAMES")
print(nse.timeframes())

# ---------------------------------------------------------
# TEST SYMBOL SEARCH
# ---------------------------------------------------------
symbols = [
    "RELIANCE",
    "HDFCBANK",
    "ICICIBANK",
    "INFY",
    "TCS",
    "SBIN",
    "AXISBANK",
    "TATAMOTORS",
]

print("\n" + "=" * 60)
print("SYMBOL SEARCH TEST")
print("=" * 60)

for symbol in symbols:
    print("\n----------------------------------------")
    print("SEARCH:", symbol)
    print("----------------------------------------")

    try:
        result = nse.search(symbol, segment="FO")

        print(result)

        if result is not None:
            print("ROWS:", len(result))
            print("COLUMNS:", list(result.columns))

    except Exception as e:
        print("ERROR:", repr(e))


# ---------------------------------------------------------
# TRY DIRECT FO SEARCH
# ---------------------------------------------------------
print("\n" + "=" * 60)
print("FO MASTER DISCOVERY")
print("=" * 60)

test_symbols = [
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "RELIANCE",
    "HDFCBANK",
    "ICICIBANK",
    "INFY",
    "TCS",
    "SBIN",
    "AXISBANK",
]

all_data = []

for symbol in test_symbols:

    try:
        df = nse.search(symbol, segment="FO")

        if df is not None and len(df) > 0:

            print(
                f"{symbol:15} -> {len(df)} records"
            )

            df = df.copy()
            df["search_symbol"] = symbol

            all_data.append(df)

        else:
            print(
                f"{symbol:15} -> 0 records"
            )

    except Exception as e:
        print(
            f"{symbol:15} -> ERROR: {e}"
        )


# ---------------------------------------------------------
# COMBINE
# ---------------------------------------------------------
print("\n" + "=" * 60)
print("COMBINING RESULTS")
print("=" * 60)

if all_data:

    combined = pd.concat(
        all_data,
        ignore_index=True
    )

    print("TOTAL RECORDS:", len(combined))

    print("\nCOLUMNS:")
    print(list(combined.columns))

    print("\nFIRST RECORDS:")
    print(combined.head(30).to_string())

    combined.to_csv(
        "fo_search_results.csv",
        index=False
    )

    print("\nFILE CREATED:")
    print("fo_search_results.csv")

else:

    print("NO FO RECORDS FOUND")


print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
