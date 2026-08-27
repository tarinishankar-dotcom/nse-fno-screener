import os
import time
import pandas as pd
from datetime import datetime, timedelta
from openchart import NSEData

# ============================================================
# NSE F&O PDH/PDL + ORB + VOLUME SCREENER
# ============================================================

print("=" * 70)
print("NSE F&O BUY/SELL SCREENER")
print("=" * 70)

# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------

ORB_START = "09:15"
ORB_END = "09:20"

VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.5

MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"

# ------------------------------------------------------------
# LOAD CURRENT FUTURES
# ------------------------------------------------------------

print("\n[1] Loading current futures...")

if not os.path.exists("stock_futures.csv"):
    raise FileNotFoundError(
        "stock_futures.csv not found. Run the futures discovery step first."
    )

futures = pd.read_csv("stock_futures.csv")

print("STOCK FUTURES FOUND:", len(futures))

# Detect columns
futures.columns = [str(c).strip() for c in futures.columns]

if "symbol" not in futures.columns:
    raise ValueError("symbol column missing in stock_futures.csv")

symbols = (
    futures["symbol"]
    .astype(str)
    .str.strip()
    .dropna()
    .drop_duplicates()
    .tolist()
)

print("UNIQUE STOCK FUTURES:", len(symbols))

# ------------------------------------------------------------
# OPENCHART
# ------------------------------------------------------------

nse = NSEData()

print("\n[2] OpenChart initialized")

# ------------------------------------------------------------
# DATE
# ------------------------------------------------------------

today = datetime.now().date()

start = datetime.combine(today, datetime.strptime("09:15", "%H:%M").time())
end = datetime.combine(today, datetime.strptime("15:30", "%H:%M").time())

print("DATE:", today)
print("START:", start)
print("END:", end)

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def clean_columns(df):
    df = df.copy()

    df.columns = [
        str(c).strip().lower()
        for c in df.columns
    ]

    return df


def normalize_timestamp(df):

    if not isinstance(df.index, pd.DatetimeIndex):

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(
                df["timestamp"],
                errors="coerce"
            )
            df = df.set_index("timestamp")

        elif "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(
                df["datetime"],
                errors="coerce"
            )
            df = df.set_index("datetime")

        else:
            raise ValueError("Timestamp column/index not found")

    idx = pd.to_datetime(df.index)

    # Convert timezone if present
    try:
        if idx.tz is not None:
            idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)
    except Exception:
        pass

    df.index = idx

    return df


def get_previous_day_high_low(symbol):

    try:

        prev_date = today - timedelta(days=7)

        data = nse.historical(
            symbol,
            "FO",
            prev_date,
            end,
            "1d"
        )

        if data is None or len(data) == 0:
            return None, None

        data = clean_columns(data)

        if "high" not in data.columns or "low" not in data.columns:
            return None, None

        data = normalize_timestamp(data)

        data = data[data.index.date < today]

        if len(data) == 0:
            return None, None

        last_day = data.index.date[-1]

        day_data = data[data.index.date == last_day]

        if len(day_data) == 0:
            return None, None

        pdh = float(day_data["high"].max())
        pdl = float(day_data["low"].min())

        return pdh, pdl

    except Exception as e:

        print(
            f"PDH/PDL ERROR {symbol}: {str(e)[:100]}"
        )

        return None, None


def calculate_signal(symbol):

    try:

        # ----------------------------------------------------
        # FETCH 5 MINUTE DATA
        # ----------------------------------------------------

        data = nse.historical(
            symbol,
            "FO",
            start,
            end,
            "5m"
        )

        if data is None or len(data) == 0:
            return None

        data = clean_columns(data)
        data = normalize_timestamp(data)

        required = [
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]

        for col in required:
            if col not in data.columns:
                return None

        # ----------------------------------------------------
        # MARKET HOURS
        # ----------------------------------------------------

        data = data[
            (data.index.time >= pd.Timestamp("09:15").time())
            &
            (data.index.time <= pd.Timestamp("15:30").time())
        ].copy()

        if len(data) < 25:
            return None

        # ----------------------------------------------------
        # PDH / PDL
        # ----------------------------------------------------

        pdh, pdl = get_previous_day_high_low(symbol)

        if pdh is None or pdl is None:
            return None

        # ----------------------------------------------------
        # FIND 9:15 / 9:20 / 9:25
        # ----------------------------------------------------

        candle_915 = data[
            (data.index.hour == 9) &
            (data.index.minute == 15)
        ]

        candle_920 = data[
            (data.index.hour == 9) &
            (data.index.minute == 20)
        ]

        candle_925 = data[
            (data.index.hour == 9) &
            (data.index.minute == 25)
        ]

        if (
            candle_915.empty
            or candle_920.empty
            or candle_925.empty
        ):
            return None

        c915 = candle_915.iloc[0]
        c920 = candle_920.iloc[0]
        c925 = candle_925.iloc[0]

        # ----------------------------------------------------
        # ORB
        # ----------------------------------------------------

        orb_high = max(
            float(c915["high"]),
            float(c920["high"])
        )

        orb_low = min(
            float(c915["low"]),
            float(c920["low"])
        )

        # ----------------------------------------------------
        # VOLUME CONDITION
        #
        # ANY ONE OF 9:15 / 9:20 / 9:25
        # MUST HAVE >= 20 PERIOD AVG * 1.5
        # ----------------------------------------------------

        data["vol_avg_20"] = (
            data["volume"]
            .rolling(VOLUME_LOOKBACK)
            .mean()
            .shift(1)
        )

        volume_pass = False

        for ts in [
            c915.name,
            c920.name,
            c925.name
        ]:

            row = data.loc[ts]

            avg20 = row["vol_avg_20"]

            if pd.isna(avg20):
                continue

            threshold = avg20 * VOLUME_MULTIPLIER

            if float(row["volume"]) >= threshold:
                volume_pass = True
                break

        # ----------------------------------------------------
        # IF VOLUME NOT PASSED
        # ----------------------------------------------------

        if not volume_pass:
            return None

        # ----------------------------------------------------
        # 9:15 OPEN
        # ----------------------------------------------------

        day_open = float(c915["open"])

        # ----------------------------------------------------
        # CONDITIONS TRACKING
        # ----------------------------------------------------

        pdh_break = False
        pdl_break = False

        orb_high_break = False
        orb_low_break = False

        buy_time = None
        buy_price = None

        sell_time = None
        sell_price = None

        # ----------------------------------------------------
        # SCAN CANDLES AFTER ORB
        # ----------------------------------------------------

        scan_data = data[
            data.index >= c925.name
        ].copy()

        for ts, row in scan_data.iterrows():

            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])

            # -----------------------------------------------
            # BUY CONDITIONS
            # -----------------------------------------------

            if high >= pdh:
                pdh_break = True

            if high >= orb_high:
                orb_high_break = True

            if (
                pdh_break
                and orb_high_break
            ):

                buy_time = ts
                buy_price = close
                break

            # -----------------------------------------------
            # SELL CONDITIONS
            # -----------------------------------------------

            if low <= pdl:
                pdl_break = True

            if low <= orb_low:
                orb_low_break = True

            if (
                pdl_break
                and orb_low_break
            ):

                sell_time = ts
                sell_price = close
                break

        # ----------------------------------------------------
        # RETURN FIRST VALID SIGNAL
        # ----------------------------------------------------

        if buy_time is not None:

            movement = (
                (buy_price - day_open)
                / day_open
            ) * 100

            return {
                "symbol": symbol,
                "signal": "BUY",
                "signal_time": buy_time.strftime("%H:%M"),
                "signal_price": round(buy_price, 2),
                "movement_pct": round(movement, 2)
            }

        if sell_time is not None:

            movement = (
                (sell_price - day_open)
                / day_open
            ) * 100

            return {
                "symbol": symbol,
                "signal": "SELL",
                "signal_time": sell_time.strftime("%H:%M"),
                "signal_price": round(sell_price, 2),
                "movement_pct": round(movement, 2)
            }

        return None

    except Exception as e:

        print(
            f"ERROR {symbol}: {str(e)[:150]}"
        )

        return None


# ============================================================
# SCAN 210 STOCK FUTURES
# ============================================================

print("\n" + "=" * 70)
print("STARTING 210 STOCK FUTURES SCAN")
print("=" * 70)

results = []

total = len(symbols)

for i, symbol in enumerate(symbols, start=1):

    print(
        f"[{i}/{total}] {symbol}",
        end=" ... "
    )

    result = calculate_signal(symbol)

    if result is not None:

        results.append(result)

        print(
            f"{result['signal']} "
            f"{result['signal_time']} "
            f"{result['signal_price']}"
        )

    else:

        print("NO SIGNAL")

    # Small delay
    time.sleep(0.15)


# ============================================================
# RESULT
# ============================================================

print("\n" + "=" * 70)
print("FINAL SCREENER RESULT")
print("=" * 70)

if results:

    result_df = pd.DataFrame(results)

    result_df = result_df[
        [
            "symbol",
            "signal",
            "signal_time",
            "signal_price",
            "movement_pct"
        ]
    ]

    # Sort latest signal first
    result_df = result_df.sort_values(
        by="signal_time",
        ascending=True
    )

    print(result_df.to_string(index=False))

else:

    result_df = pd.DataFrame(
        columns=[
            "symbol",
            "signal",
            "signal_time",
            "signal_price",
            "movement_pct"
        ]
    )

    print("NO SIGNALS FOUND")


# ============================================================
# SAVE
# ============================================================

result_df.to_csv(
    "screener_results.csv",
    index=False
)

print("\n" + "=" * 70)
print("FILE CREATED: screener_results.csv")
print("=" * 70)

print("\nTOTAL SIGNALS:", len(result_df))

if len(result_df):

    print(
        "BUY:",
        len(result_df[result_df["signal"] == "BUY"])
    )

    print(
        "SELL:",
        len(result_df[result_df["signal"] == "SELL"])
    )

print("\nSTEP 4 COMPLETE")
