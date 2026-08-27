from openchart import NSEData
import pandas as pd

print("=" * 60)
print("OPENCHART NSE F&O MASTER TEST")
print("=" * 60)

nse = NSEData()

print("\nSEGMENTS:")
print(nse.segments())

print("\nTIMEFRAMES:")
print(nse.timeframes())

print("\nSEARCH URL:")
print(nse.search_url)

# ---------------------------------------------------------
# TEST FO SEARCH
# ---------------------------------------------------------

symbols = [
    "RELIANCE",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "AXISBANK",
    "INFY",
    "TCS",
    "HCLTECH",
    "WIPRO",
    "LT",
    "ITC",
    "BHARTIARTL",
    "KOTAKBANK",
    "MARUTI",
    "M&M",
    "TATAMOTORS",
    "TATASTEEL",
    "SUNPHARMA",
    "ADANIENT",
    "ADANIPORTS",
]

all_rows = []

print("\n" + "=" * 60)
print("SEARCHING FO")
print("=" * 60)

for name in symbols:

    print("\n--------------------------------")
    print("SYMBOL:", name)
    print("--------------------------------")

    try:

        df = nse.search(name, segment="FO")

        if df is None:
            print("RESULT: None")
            continue

        if df.empty:
            print("RESULT: EMPTY")
            continue

        print("ROWS:", len(df))
        print("COLUMNS:", list(df.columns))

        print(df.to_string(index=False))

        # -------------------------------------------------
        # Detect FUT rows without assuming exact type text
        # -------------------------------------------------

        for _, row in df.iterrows():

            row_text = " ".join(
                str(x) for x in row.tolist()
            ).upper()

            if "FUT" in row_text:

                all_rows.append(row.to_dict())

    except Exception as e:

        print("ERROR:", repr(e))


# ---------------------------------------------------------
# FINAL RESULT
# ---------------------------------------------------------

print("\n" + "=" * 60)
print("FINAL FUTURES DISCOVERY")
print("=" * 60)

if len(all_rows) == 0:

    print("\nNO FUTURES FOUND")

    print("\nIMPORTANT:")
    print("OpenChart search() is currently returning the")
    print("INDEX master even when segment='FO' is supplied.")

    print("\nWe will NOT guess future symbols.")

else:

    final = pd.DataFrame(all_rows)

    final = final.drop_duplicates()

    print("\nTOTAL FUTURE-LIKE RECORDS:", len(final))

    print("\n")
    print(final.to_string(index=False))

    final.to_csv(
        "future_search_results.csv",
        index=False
    )

    print("\nFILE CREATED:")
    print("future_search_results.csv")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
