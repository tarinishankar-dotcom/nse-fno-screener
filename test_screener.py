import os
import time
import pandas as pd
from datetime import datetime, timedelta
from openchart import NSEData

# ============================================================
# NSE F&O PDH + PDL + ORB + 20 PERIOD 1.5X VOLUME SCREENER
# ============================================================

print("=" * 70)
print("NSE F&O BUY / SELL SCREENER")
print("=" * 70)

# ============================================================
# SETTINGS
# ============================================================

ORB_START = "09:15"
ORB_END = "09:20"

VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.5

MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"

# ============================================================
# LOAD CURRENT FUTURES
# ============================================================

print("\n[1] Loading current futures...")

if not os.path.exists("stock_futures.csv"):
    raise FileNotFoundError(
        "stock_futures.csv not found."
    )

futures = pd.read_csv("stock_futures.csv")

futures.columns = [
    str(c).strip()
    for c in futures.columns
]

if "symbol" not in futures.columns:
    raise ValueError(
        "symbol column missing in stock_futures.csv"
    )

symbols = (
    futures["symbol"]
    .astype(str)
    .str.strip()
    .drop_duplicates()
    .tolist()
)

print("STOCK FUTURES FOUND:", len(symbols))

# ============================================================
# OPENCHART
# ============================================================

nse = NSEData()

print("OpenChart initialized")

# ============================================================
# DATE / TIME
# ============================================================

today = datetime.now().date()

start = datetime.combine(
    today,
    datetime.strptime(
        MARKET_OPEN,
        "%H:%M"
    ).time()
)

end = datetime.combine(
    today,
    datetime.strptime(
        MARKET_CLOSE,
        "%H:%M"
    ).time()
)

print("DATE:", today)
print("START:", start)
print("END:", end)

# ============================================================
# CLEAN COLUMNS
# ============================================================

def clean_columns(df):

    df = df.copy()

    df.columns = [
        str(c).strip().lower()
        for c in df.columns
    ]

    return df


# ============================================================
# NORMALIZE TIMESTAMP
# ============================================================

def normalize_timestamp(df):

    df = df.copy()

    if not isinstance(
        df.index,
        pd.DatetimeIndex
    ):

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

            raise ValueError(
                "Timestamp not found"
            )

    idx = pd.to_datetime(df.index)

    try:

        if idx.tz is not None:

            idx = (
                idx
                .tz_convert("Asia/Kolkata")
                .tz_localize(None)
            )

    except Exception:
        pass

    df.index = idx

    return df


# ============================================================
# PREVIOUS TRADING DAY PDH / PDL
# ============================================================

def get_previous_day_high_low(symbol):

    try:

        # Get enough days to find previous trading day
        prev_start = today - timedelta(days=10)

        data = nse.historical(
            symbol,
            "FO",
            prev_start,
            end,
            "1d"
        )

        if data is None:
            return None, None

        if len(data) == 0:
            return None, None

        data = clean_columns(data)
        data = normalize_timestamp(data)

        if "high" not in data.columns:
            return None, None

        if "low" not in data.columns:
            return None, None

        # Only dates before today
        data = data[
            data.index.date < today
        ].copy()

        if len(data) == 0:
            return None, None

        # Last available trading day
        previous_day = max(
            data.index.date
        )

        day_data = data[
            data.index.date == previous_day
        ]

        if len(day_data) == 0:
            return None, None

        pdh = float(
            day_data["high"].max()
        )

        pdl = float(
            day_data["low"].min()
        )

        return pdh, pdl

    except Exception as e:

        print(
            f" PDH/PDL ERROR: {str(e)[:100]}"
        )

        return None, None


# ============================================================
# FIND EXACT CANDLE
# ============================================================

def get_candle(data, hour, minute):

    result = data[
        (data.index.hour == hour)
        &
        (data.index.minute == minute)
    ]

    if result.empty:
        return None

    return result.iloc[0]


# ============================================================
# CALCULATE SIGNAL
# ============================================================

def calculate_signal(symbol):

    try:

        # ====================================================
        # 1. FETCH 5 MINUTE DATA
        # ====================================================

        data = nse.historical(
            symbol,
            "FO",
            start,
            end,
            "5m"
        )

        if data is None:
            return None

        if len(data) == 0:
            return None

        data = clean_columns(data)
        data = normalize_timestamp(data)

        # ====================================================
        # REQUIRED COLUMNS
        # ====================================================

        required_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]

        for column in required_columns:

            if column not in data.columns:
                return None

        # ====================================================
        # MARKET HOURS
        # ====================================================

        data = data[
            (data.index.time >= pd.Timestamp(
                MARKET_OPEN
            ).time())
            &
            (data.index.time <= pd.Timestamp(
                MARKET_CLOSE
            ).time())
        ].copy()

        if len(data) < 25:
            return None

        # ====================================================
        # 2. PREVIOUS DAY HIGH / LOW
        # ====================================================

        pdh, pdl = get_previous_day_high_low(
            symbol
        )

        if pdh is None or pdl is None:
            return None

        # ====================================================
        # 3. GET 9:15 / 9:20 / 9:25 CANDLES
        # ====================================================

        c915 = get_candle(
            data,
            9,
            15
        )

        c920 = get_candle(
            data,
            9,
            20
        )

        c925 = get_candle(
            data,
            9,
            25
        )

        if c915 is None:
            return None

        if c920 is None:
            return None

        if c925 is None:
            return None

        # ====================================================
        # 4. ORB 9:15 - 9:20
        #
        # ORB consists of first TWO 5-min candles:
        #
        # 9:15 candle
        # 9:20 candle
        # ====================================================

        orb_high = max(
            float(c915["high"]),
            float(c920["high"])
        )

        orb_low = min(
            float(c915["low"]),
            float(c920["low"])
        )

        # ====================================================
        # 5. 20 PERIOD VOLUME
        #
        # IMPORTANT:
        #
        # Each candle compares its volume against the
        # PREVIOUS 20 COMPLETED candles.
        #
        # 1.5X condition can happen in:
        #
        # 9:15
        # OR
        # 9:20
        # OR
        # 9:25
        #
        # ANY ONE IS ENOUGH.
        # ====================================================

        data["volume_avg_20"] = (
            data["volume"]
            .rolling(
                VOLUME_LOOKBACK
            )
            .mean()
            .shift(1)
        )

        volume_pass = False

        volume_check_times = [
            c915.name,
            c920.name,
            c925.name
        ]

        for candle_time in volume_check_times:

            if candle_time not in data.index:
                continue

            row = data.loc[candle_time]

            current_volume = float(
                row["volume"]
            )

            avg_volume = row[
                "volume_avg_20"
            ]

            if pd.isna(avg_volume):
                continue

            volume_threshold = (
                float(avg_volume)
                * VOLUME_MULTIPLIER
            )

            if (
                current_volume
                >= volume_threshold
            ):

                volume_pass = True
                break

        # ====================================================
        # IF NO VOLUME CANDLE PASSES
        # ====================================================

        if not volume_pass:
            return None

        # ====================================================
        # 6. DAY OPEN
        # ====================================================

        day_open = float(
            c915["open"]
        )

        # ====================================================
        # 7. SCAN AFTER 9:25
        #
        # PDH + ORB HIGH can happen on different candles.
        #
        # PDL + ORB LOW can happen on different candles.
        #
        # Once BOTH conditions have occurred,
        # signal is generated.
        # ====================================================

        pdh_broken = False
        orb_high_broken = False

        pdl_broken = False
        orb_low_broken = False

        buy_signal = None
        sell_signal = None

        scan_data = data[
            data.index >= c925.name
        ].copy()

        for ts, row in scan_data.iterrows():

            high = float(
                row["high"]
            )

            low = float(
                row["low"]
            )

            close = float(
                row["close"]
            )

            # =================================================
            # BUY
            # =================================================

            if high >= pdh:

                pdh_broken = True

            if high >= orb_high:

                orb_high_broken = True

            if (
                pdh_broken
                and orb_high_broken
            ):

                buy_signal = {
                    "symbol": symbol,
                    "signal": "BUY",
                    "signal_time": ts,
                    "signal_price": close
                }

                break

            # =================================================
            # SELL
            # =================================================

            if low <= pdl:

                pdl_broken = True

            if low <= orb_low:

                orb_low_broken = True

            if (
                pdl_broken
                and orb_low_broken
            ):

                sell_signal = {
                    "symbol": symbol,
                    "signal": "SELL",
                    "signal_time": ts,
                    "signal_price": close
                }

                break

        # ====================================================
        # 8. SELECT FIRST SIGNAL
        # ====================================================

        if (
            buy_signal is None
            and sell_signal is None
        ):

            return None

        if (
            buy_signal is not None
            and sell_signal is not None
        ):

            if (
                buy_signal["signal_time"]
                <= sell_signal["signal_time"]
            ):

                signal = buy_signal

            else:

                signal = sell_signal

        elif buy_signal is not None:

            signal = buy_signal

        else:

            signal = sell_signal

        # ====================================================
        # 9. PRICE MOVEMENT %
        #
        # From 9:15 OPEN to SIGNAL PRICE
        # ====================================================

        signal_price = float(
            signal["signal_price"]
        )

        movement_pct = (
            (
                signal_price
                - day_open
            )
            / day_open
        ) * 100

        # ====================================================
        # 10. FINAL RESULT
        #
        # NO VOLUME COLUMN
        # ====================================================

        return {
            "symbol": signal["symbol"],
            "signal": signal["signal"],
            "signal_time": signal[
                "signal_time"
            ].strftime("%H:%M"),
            "signal_price": round(
                signal_price,
                2
            ),
            "movement_pct": round(
                movement_pct,
                2
            )
        }

    except Exception as e:

        print(
            f" ERROR: {str(e)[:150]}"
        )

        return None


# ============================================================
# SCAN ALL 210 STOCK FUTURES
# ============================================================

print("\n" + "=" * 70)
print("STARTING FULL STOCK FUTURES SCAN")
print("=" * 70)

results = []

total = len(symbols)

for i, symbol in enumerate(
    symbols,
    start=1
):

    print(
        f"[{i}/{total}] {symbol}",
        end=" ..."
    )

    result = calculate_signal(
        symbol
    )

    if result is not None:

        results.append(
            result
        )

        print(
            f" {result['signal']} "
            f"{result['signal_time']} "
            f"{result['signal_price']} "
            f"{result['movement_pct']}%"
        )

    else:

        print(" NO SIGNAL")

    time.sleep(0.15)


# ============================================================
# FINAL RESULT
# ============================================================

print("\n" + "=" * 70)
print("FINAL SCREENER RESULT")
print("=" * 70)

result_columns = [
    "symbol",
    "signal",
    "signal_time",
    "signal_price",
    "movement_pct"
]

if results:

    result_df = pd.DataFrame(
        results
    )

    result_df = result_df[
        result_columns
    ]

    # Sort by signal time
    result_df = result_df.sort_values(
        by="signal_time",
        ascending=True
    )

    print(
        result_df.to_string(
            index=False
        )
    )

else:

    result_df = pd.DataFrame(
        columns=result_columns
    )

    print(
        "NO SIGNALS FOUND"
    )


# ============================================================
# SAVE CSV
# ============================================================

result_df.to_csv(
    "screener_results.csv",
    index=False
)

print("\n" + "=" * 70)
print("FILE CREATED")
print("=" * 70)

print(
    "screener_results.csv"
)

print(
    "TOTAL SIGNALS:",
    len(result_df)
)

if len(result_df) > 0:

    print(
        "BUY:",
        len(
            result_df[
                result_df["signal"]
                == "BUY"
            ]
        )
    )

    print(
        "SELL:",
        len(
            result_df[
                result_df["signal"]
                == "SELL"
            ]
        )
    )

print("\nSTEP 4 COMPLETE")
print("=" * 70)
