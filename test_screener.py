import os
import time
import pandas as pd
from datetime import datetime, timedelta
from openchart import NSEData

print("=" * 70)
print("NSE F&O BUY / SELL SCREENER")
print("SEP-26 FUTURES + PDH/PDL + ORB + VOLUME")
print("=" * 70)

# ============================================================
# SETTINGS
# ============================================================

ORB_START = "09:15"
ORB_SECOND = "09:20"
VOLUME_CHECK = ["09:15", "09:20", "09:25"]

VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.5

# ============================================================
# LOAD FUTURES MASTER
# ============================================================

print("\n[1] DOWNLOADING NSE F&O MASTER...")

URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/csv,application/csv,*/*",
    "Referer": "https://www.nseindia.com/"
}

import requests
from io import BytesIO

r = requests.get(URL, headers=HEADERS, timeout=30)

print("HTTP STATUS:", r.status_code)

if r.status_code != 200:
    raise Exception("NSE master download failed")

master = pd.read_csv(BytesIO(r.content))
master.columns = [str(c).strip() for c in master.columns]

# ============================================================
# CLEAN MASTER
# ============================================================

underlying_col = master.columns[0]
symbol_col = master.columns[1]

master[underlying_col] = (
    master[underlying_col]
    .astype(str)
    .str.strip()
)

master[symbol_col] = (
    master[symbol_col]
    .astype(str)
    .str.strip()
)

# Remove header accidentally read as data
master = master[
    master[symbol_col].str.lower() != "symbol"
].copy()

# Remove blanks
master = master[
    (master[symbol_col] != "") &
    (master[symbol_col].notna())
].copy()

# ============================================================
# INDEX SYMBOLS
# ============================================================

index_symbols = {
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYNXT50",
    "NIFTYFPI"
}

stock_master = master[
    ~master[symbol_col].str.upper().isin(index_symbols)
].copy()

symbols = (
    stock_master[symbol_col]
    .astype(str)
    .str.strip()
    .drop_duplicates()
    .tolist()
)

print("STOCK FUTURES FOUND:", len(symbols))

# ============================================================
# OPENCHART
# ============================================================

print("\n[2] INITIALIZING OPENCHART...")

nse = NSEData()

print("OpenChart initialized")

# ============================================================
# DATE
# ============================================================

today = datetime.now().date()

start = datetime.combine(
    today,
    datetime.strptime("09:15", "%H:%M").time()
)

end = datetime.combine(
    today,
    datetime.strptime("15:30", "%H:%M").time()
)

print("DATE:", today)
print("START:", start)
print("END:", end)

# ============================================================
# HELPERS
# ============================================================

def clean_columns(df):

    df = df.copy()

    df.columns = [
        str(c).strip().lower()
        for c in df.columns
    ]

    return df


def normalize_timestamp(df):

    df = df.copy()

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
            return None

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

    df = df[~df.index.isna()]

    return df


# ============================================================
# FUTURES CONTRACT
# ============================================================

def get_near_future(symbol):

    """
    Current near-month contract.

    On 27-Aug-2026 this should select SEP-26.
    After September expiry it should automatically move
    to the next available contract.
    """

    row = stock_master[
        stock_master[symbol_col].str.upper()
        == symbol.upper()
    ]

    if row.empty:
        return None

    row = row.iloc[0]

    # Futures expiry columns are after first two columns.
    expiry_columns = list(master.columns[2:])

    for col in expiry_columns:

        value = row[col]

        if pd.isna(value):
            continue

        value = str(value).strip()

        if value == "":
            continue

        # First available contract = near month
        return value

    return None


# ============================================================
# FETCH DATA
# ============================================================

def get_intraday(symbol):

    """
    Try OpenChart using the underlying symbol first.
    If OpenChart supports expiry-specific symbol,
    try symbol + expiry.
    """

    expiry = get_near_future(symbol)

    if expiry is None:
        return None, None

    # --------------------------------------------------------
    # TRY UNDERLYING
    # --------------------------------------------------------

    try:

        data = nse.historical(
            symbol,
            "FO",
            start,
            end,
            "5m"
        )

        if data is not None and len(data) > 0:

            return data, expiry

    except Exception as e:

        pass

    # --------------------------------------------------------
    # TRY SYMBOL + EXPIRY
    # --------------------------------------------------------

    candidates = [
        f"{symbol}{expiry}",
        f"{symbol}-{expiry}",
        f"{symbol} {expiry}",
    ]

    for contract in candidates:

        try:

            data = nse.historical(
                contract,
                "FO",
                start,
                end,
                "5m"
            )

            if data is not None and len(data) > 0:

                return data, expiry

        except Exception:

            continue

    return None, expiry


# ============================================================
# PREVIOUS DAY HIGH / LOW
# ============================================================

def get_previous_day_high_low(symbol):

    try:

        prev_start = today - timedelta(days=10)

        data, expiry = get_intraday(symbol)

        if data is None or len(data) == 0:
            return None, None

        data = clean_columns(data)
        data = normalize_timestamp(data)

        if data is None:
            return None, None

        if "high" not in data.columns:
            return None, None

        if "low" not in data.columns:
            return None, None

        # Since current-day request may only return today's
        # candles, request daily history separately.

        daily_start = datetime.combine(
            prev_start,
            datetime.strptime("09:15", "%H:%M").time()
        )

        daily_end = datetime.combine(
            today,
            datetime.strptime("15:30", "%H:%M").time()
        )

        daily = nse.historical(
            symbol,
            "FO",
            daily_start,
            daily_end,
            "1d"
        )

        if daily is None or len(daily) == 0:
            return None, None

        daily = clean_columns(daily)
        daily = normalize_timestamp(daily)

        if daily is None:
            return None, None

        daily = daily[daily.index.date < today]

        if daily.empty:
            return None, None

        last_date = daily.index.date[-1]

        previous = daily[
            daily.index.date == last_date
        ]

        if previous.empty:
            return None, None

        pdh = float(previous["high"].max())
        pdl = float(previous["low"].min())

        return pdh, pdl

    except Exception as e:

        return None, None


# ============================================================
# SIGNAL CALCULATION
# ============================================================

def calculate_signal(symbol):

    try:

        # ----------------------------------------------------
        # GET 5-MIN DATA
        # ----------------------------------------------------

        data, expiry = get_intraday(symbol)

        if data is None or len(data) == 0:

            print("NO DATA", end=" ")
            return None

        data = clean_columns(data)
        data = normalize_timestamp(data)

        if data is None:
            return None

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
            (data.index.time >= pd.Timestamp(
                "09:15"
            ).time())
            &
            (data.index.time <= pd.Timestamp(
                "15:30"
            ).time())
        ].copy()

        if data.empty:
            return None

        # ----------------------------------------------------
        # PDH / PDL
        # ----------------------------------------------------

        pdh, pdl = get_previous_day_high_low(symbol)

        if pdh is None or pdl is None:
            return None

        # ----------------------------------------------------
        # FIRST 3 CANDLES
        # 09:15 / 09:20 / 09:25
        # ----------------------------------------------------

        candles = {}

        for t in VOLUME_CHECK:

            hh, mm = map(int, t.split(":"))

            temp = data[
                (data.index.hour == hh)
                &
                (data.index.minute == mm)
            ]

            if not temp.empty:
                candles[t] = temp.iloc[0]

        if not all(
            t in candles
            for t in VOLUME_CHECK
        ):
            return None

        c915 = candles["09:15"]
        c920 = candles["09:20"]
        c925 = candles["09:25"]

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
        # VOLUME 20 PERIOD
        #
        # ANY ONE OF FIRST 3 CANDLES MUST BE >= 1.5X
        # ----------------------------------------------------

        data["avg20"] = (
            data["volume"]
            .rolling(VOLUME_LOOKBACK)
            .mean()
            .shift(1)
        )

        volume_pass = False

        for t in VOLUME_CHECK:

            row = candles[t]

            avg20 = row.get("avg20")

            if pd.isna(avg20):
                continue

            required_volume = (
                float(avg20)
                * VOLUME_MULTIPLIER
            )

            actual_volume = float(
                row["volume"]
            )

            if actual_volume >= required_volume:

                volume_pass = True
                break

        if not volume_pass:
            return None

        # ----------------------------------------------------
        # 9:15 OPEN
        # ----------------------------------------------------

        day_open = float(c915["open"])

        # ----------------------------------------------------
        # SCAN AFTER 9:25
        # ----------------------------------------------------

        scan = data[
            data.index >= c925.name
        ].copy()

        buy_pdh = False
        buy_orb = False

        sell_pdl = False
        sell_orb = False

        for ts, row in scan.iterrows():

            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])

            # =================================================
            # BUY
            # =================================================

            if high >= pdh:
                buy_pdh = True

            if high >= orb_high:
                buy_orb = True

            if buy_pdh and buy_orb:

                movement = (
                    (close - day_open)
                    / day_open
                ) * 100

                return {
                    "symbol": symbol,
                    "signal": "BUY",
                    "signal_time": ts.strftime("%H:%M"),
                    "signal_price": round(close, 2),
                    "movement_pct": round(
                        movement,
                        2
                    )
                }

            # =================================================
            # SELL
            # =================================================

            if low <= pdl:
                sell_pdl = True

            if low <= orb_low:
                sell_orb = True

            if sell_pdl and sell_orb:

                movement = (
                    (close - day_open)
                    / day_open
                ) * 100

                return {
                    "symbol": symbol,
                    "signal": "SELL",
                    "signal_time": ts.strftime("%H:%M"),
                    "signal_price": round(close, 2),
                    "movement_pct": round(
                        movement,
                        2
                    )
                }

        return None

    except Exception as e:

        print(
            f"ERROR: {str(e)[:100]}",
            end=" "
        )

        return None


# ============================================================
# SCAN
# ============================================================

print("\n")
print("=" * 70)
print("STARTING STOCK FUTURES SCAN")
print("=" * 70)

results = []

total = len(symbols)

for i, symbol in enumerate(symbols, 1):

    print(
        f"[{i}/{total}] {symbol} ...",
        end=" "
    )

    result = calculate_signal(symbol)

    if result:

        results.append(result)

        print(
            result["signal"],
            result["signal_time"],
            result["signal_price"]
        )

    else:

        print("NO SIGNAL")

    time.sleep(0.10)


# ============================================================
# FINAL RESULT
# ============================================================

print("\n")
print("=" * 70)
print("FINAL SCREENER RESULT")
print("=" * 70)

columns = [
    "symbol",
    "signal",
    "signal_time",
    "signal_price",
    "movement_pct"
]

if results:

    result_df = pd.DataFrame(results)

    result_df = result_df[columns]

    result_df = result_df.sort_values(
        by="signal_time"
    )

    print(
        result_df.to_string(
            index=False
        )
    )

else:

    result_df = pd.DataFrame(
        columns=columns
    )

    print("NO SIGNALS FOUND")


# ============================================================
# SAVE
# ============================================================

result_df.to_csv(
    "screener_results.csv",
    index=False
)

print("\n")
print("=" * 70)
print("FILE CREATED: screener_results.csv")
print("=" * 70)

print(
    "TOTAL SIGNALS:",
    len(result_df)
)

if len(result_df):

    print(
        "BUY:",
        len(
            result_df[
                result_df["signal"] == "BUY"
            ]
        )
    )

    print(
        "SELL:",
        len(
            result_df[
                result_df["signal"] == "SELL"
            ]
        )
    )

print("\nSTEP 4 COMPLETE")
