import os
import time
import requests
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta, time as dt_time
from openchart import NSEData

# ============================================================
# NSE F&O BUY / SELL SCREENER
# PDH + PDL + ORB + 20 PERIOD 1.5X VOLUME
# ============================================================

print("=" * 75)
print("NSE F&O BUY / SELL SCREENER")
print("=" * 75)

# ============================================================
# SETTINGS
# ============================================================

ORB_FIRST = "09:15"
ORB_SECOND = "09:20"
VOLUME_CHECK_CANDLES = ["09:15", "09:20", "09:25"]

VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.5

MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"

IST = "Asia/Kolkata"

# ============================================================
# NSE MASTER
# ============================================================

MASTER_URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/csv,application/csv,*/*",
    "Referer": "https://www.nseindia.com/"
}


def load_stock_futures():

    print("\n[1] DOWNLOADING NSE F&O MASTER...")

    r = requests.get(
        MASTER_URL,
        headers=HEADERS,
        timeout=30
    )

    print("HTTP STATUS:", r.status_code)
    print("DATA SIZE:", len(r.content), "bytes")

    if r.status_code != 200:
        raise Exception(
            f"NSE master download failed: HTTP {r.status_code}"
        )

    df = pd.read_csv(BytesIO(r.content))

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
            )

    underlying_col = df.columns[0]
    symbol_col = df.columns[1]

    df = df[
        (df[underlying_col].notna()) &
        (df[symbol_col].notna())
    ].copy()

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

    index_symbols = {
        "NIFTY",
        "BANKNIFTY",
        "FINNIFTY",
        "MIDCPNIFTY",
        "NIFTYNXT50",
        "NIFTYFPI"
    }

    stocks = df[
        ~df[symbol_col]
        .str.upper()
        .isin(index_symbols)
    ].copy()

    stocks = stocks.drop_duplicates(
        subset=[symbol_col]
    )

    symbols = (
        stocks[symbol_col]
        .tolist()
    )

    print("STOCK FUTURES FOUND:", len(symbols))

    return symbols


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

start_dt = datetime.combine(
    today,
    datetime.strptime(
        MARKET_OPEN,
        "%H:%M"
    ).time()
)

end_dt = datetime.combine(
    today,
    datetime.strptime(
        MARKET_CLOSE,
        "%H:%M"
    ).time()
)

print("DATE:", today)
print("START:", start_dt)
print("END:", end_dt)


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

    idx = pd.to_datetime(
        df.index,
        errors="coerce"
    )

    try:

        if idx.tz is not None:

            idx = (
                idx
                .tz_convert(IST)
                .tz_localize(None)
            )

    except Exception:
        pass

    df.index = idx

    df = df[
        ~df.index.isna()
    ]

    return df.sort_index()


def get_ohlcv(symbol, start, end, interval):

    try:

        data = nse.historical(
            symbol,
            "FO",
            start,
            end,
            interval
        )

        if data is None:
            return None

        if len(data) == 0:
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

        return data

    except Exception as e:

        print(
            "DATA ERROR:",
            str(e)[:100]
        )

        return None


# ============================================================
# CURRENT FUTURE CONTRACT DISCOVERY
# ============================================================

def discover_future_contract(underlying):

    """
    Try OpenChart search for current FO contract.

    Different OpenChart versions may return slightly
    different structures, therefore this function handles
    common response formats.
    """

    try:

        result = nse.search(
            underlying,
            "FO"
        )

        if result is None:
            return None

        # ----------------------------------------------------
        # DataFrame response
        # ----------------------------------------------------

        if isinstance(result, pd.DataFrame):

            if len(result) == 0:
                return None

            temp = result.copy()

            temp.columns = [
                str(c).strip().lower()
                for c in temp.columns
            ]

            # Look for rows containing FUT
            text = temp.astype(str).agg(
                " ".join,
                axis=1
            )

            fut_rows = temp[
                text.str.upper().str.contains(
                    "FUT",
                    na=False
                )
            ]

            if len(fut_rows) == 0:
                fut_rows = temp

            # Try symbol columns
            possible_symbol_cols = [
                "symbol",
                "tradingsymbol",
                "name",
                "ticker"
            ]

            for col in possible_symbol_cols:

                if col in fut_rows.columns:

                    for value in fut_rows[col]:

                        value = str(value).strip()

                        if "FUT" in value.upper():

                            return value

        # ----------------------------------------------------
        # Dictionary / list response
        # ----------------------------------------------------

        if isinstance(result, dict):

            values = [result]

        elif isinstance(result, list):

            values = result

        else:

            values = []

        candidates = []

        for item in values:

            if isinstance(item, dict):

                for key, value in item.items():

                    text = str(value).strip()

                    if (
                        "FUT" in text.upper()
                        and underlying.upper()
                        in text.upper()
                    ):

                        candidates.append(text)

            else:

                text = str(item).strip()

                if (
                    "FUT" in text.upper()
                    and underlying.upper()
                    in text.upper()
                ):

                    candidates.append(text)

        if candidates:

            # Prefer the first current-looking contract
            return candidates[0]

    except Exception as e:

        print(
            f"SEARCH ERROR {underlying}:",
            str(e)[:100]
        )

    return None


# ============================================================
# PREVIOUS TRADING DAY PDH / PDL
# ============================================================

def get_pdh_pdl(contract):

    try:

        start_prev = (
            datetime.combine(
                today,
                dt_time(9, 15)
            )
            - timedelta(days=10)
        )

        end_prev = datetime.combine(
            today,
            dt_time(15, 30)
        )

        data = get_ohlcv(
            contract,
            start_prev,
            end_prev,
            "1d"
        )

        if data is None:
            return None, None

        data = data[
            data.index.date < today
        ]

        if len(data) == 0:
            return None, None

        last_date = data.index.date[-1]

        day_data = data[
            data.index.date == last_date
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
            "PDH/PDL ERROR:",
            str(e)[:100]
        )

        return None, None


# ============================================================
# SIGNAL CALCULATION
# ============================================================

def calculate_signal(underlying, contract):

    try:

        # ----------------------------------------------------
        # 5 MIN DATA
        # ----------------------------------------------------

        data = get_ohlcv(
            contract,
            start_dt,
            end_dt,
            "5m"
        )

        if data is None:
            return None

        if len(data) < 25:
            return None

        # ----------------------------------------------------
        # MARKET HOURS
        # ----------------------------------------------------

        data = data[
            (
                data.index.time
                >= dt_time(9, 15)
            )
            &
            (
                data.index.time
                <= dt_time(15, 30)
            )
        ].copy()

        if len(data) < 3:
            return None

        # ----------------------------------------------------
        # REQUIRED CANDLES
        # ----------------------------------------------------

        candles = {}

        for clock in VOLUME_CHECK_CANDLES:

            hh, mm = map(
                int,
                clock.split(":")
            )

            rows = data[
                (data.index.hour == hh)
                &
                (data.index.minute == mm)
            ]

            if rows.empty:
                return None

            candles[clock] = rows.iloc[0]

        c915 = candles["09:15"]
        c920 = candles["09:20"]
        c925 = candles["09:25"]

        # ----------------------------------------------------
        # ORB
        #
        # 9:15 + 9:20
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
        # 20 PERIOD VOLUME
        #
        # IMPORTANT:
        # ANY ONE OF 9:15 / 9:20 / 9:25
        # MUST BE >= 1.5 X 20 PERIOD AVG
        # ----------------------------------------------------

        data["volume_avg20"] = (
            data["volume"]
            .rolling(
                VOLUME_LOOKBACK
            )
            .mean()
            .shift(1)
        )

        volume_pass = False

        for clock in VOLUME_CHECK_CANDLES:

            row = candles[clock]

            ts = row.name

            if ts not in data.index:
                continue

            avg20 = data.loc[
                ts,
                "volume_avg20"
            ]

            if pd.isna(avg20):
                continue

            threshold = (
                float(avg20)
                * VOLUME_MULTIPLIER
            )

            actual_volume = float(
                row["volume"]
            )

            if actual_volume >= threshold:

                volume_pass = True

                break

        if not volume_pass:
            return None

        # ----------------------------------------------------
        # PDH / PDL
        # ----------------------------------------------------

        pdh, pdl = get_pdh_pdl(
            contract
        )

        if pdh is None or pdl is None:
            return None

        # ----------------------------------------------------
        # DAY OPEN
        # ----------------------------------------------------

        day_open = float(
            c915["open"]
        )

        # ----------------------------------------------------
        # SCAN FROM 9:25 ONWARD
        #
        # PDH + ORB HIGH
        # OR
        # PDL + ORB LOW
        #
        # Conditions may occur on different candles.
        # Both must eventually be satisfied.
        # ----------------------------------------------------

        pdh_broken = False
        orb_high_broken = False

        pdl_broken = False
        orb_low_broken = False

        buy_signal = None
        sell_signal = None

        scan_data = data[
            data.index >= c925.name
        ]

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

            # BUY
            if high >= pdh:
                pdh_broken = True

            if high >= orb_high:
                orb_high_broken = True

            if (
                pdh_broken
                and orb_high_broken
                and buy_signal is None
            ):

                buy_signal = {
                    "time": ts,
                    "price": close
                }

            # SELL
            if low <= pdl:
                pdl_broken = True

            if low <= orb_low:
                orb_low_broken = True

            if (
                pdl_broken
                and orb_low_broken
                and sell_signal is None
            ):

                sell_signal = {
                    "time": ts,
                    "price": close
                }

            # First signal only
            if (
                buy_signal is not None
                or sell_signal is not None
            ):
                break

        # ----------------------------------------------------
        # SELECT FIRST SIGNAL
        # ----------------------------------------------------

        selected = None

        if buy_signal is not None:
            selected = (
                "BUY",
                buy_signal
            )

        if sell_signal is not None:

            if selected is None:

                selected = (
                    "SELL",
                    sell_signal
                )

            elif (
                sell_signal["time"]
                < selected[1]["time"]
            ):

                selected = (
                    "SELL",
                    sell_signal
                )

        if selected is None:
            return None

        signal, info = selected

        signal_time = info["time"]
        signal_price = float(
            info["price"]
        )

        movement = (
            (
                signal_price
                - day_open
            )
            / day_open
        ) * 100

        return {
            "symbol": underlying,
            "signal": signal,
            "signal_time": signal_time.strftime(
                "%H:%M"
            ),
            "signal_price": round(
                signal_price,
                2
            ),
            "movement_pct": round(
                movement,
                2
            )
        }

    except Exception as e:

        print(
            f"CALC ERROR {underlying}:",
            str(e)[:120]
        )

        return None


# ============================================================
# MAIN
# ============================================================

symbols = load_stock_futures()

print("\n" + "=" * 75)
print("STARTING FULL STOCK FUTURES SCAN")
print("=" * 75)

results = []

total = len(symbols)

for i, underlying in enumerate(
    symbols,
    start=1
):

    print(
        f"[{i}/{total}] {underlying} ...",
        end=""
    )

    # --------------------------------------------------------
    # DISCOVER ACTUAL FUTURES CONTRACT
    # --------------------------------------------------------

    contract = discover_future_contract(
        underlying
    )

    if contract is None:

        print(
            " FUT CONTRACT NOT FOUND"
        )

        continue

    print(
        f" {contract} ...",
        end=""
    )

    # --------------------------------------------------------
    # CALCULATE
    # --------------------------------------------------------

    result = calculate_signal(
        underlying,
        contract
    )

    if result is not None:

        results.append(result)

        print(
            f" {result['signal']} "
            f"{result['signal_time']} "
            f"{result['signal_price']} "
            f"{result['movement_pct']}%"
        )

    else:

        print(" NO SIGNAL")

    time.sleep(0.20)


# ============================================================
# FINAL RESULT
# ============================================================

print("\n" + "=" * 75)
print("FINAL SCREENER RESULT")
print("=" * 75)

columns = [
    "symbol",
    "signal",
    "signal_time",
    "signal_price",
    "movement_pct"
]

if results:

    result_df = pd.DataFrame(
        results,
        columns=columns
    )

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

print("\n" + "=" * 75)
print("FILE CREATED: screener_results.csv")
print("=" * 75)

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
print("=" * 75)
