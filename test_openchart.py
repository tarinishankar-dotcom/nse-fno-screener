from openchart import NSEData

print("Starting FULL NSE F&O FUTURES discovery...")

nse = NSEData()

print("\n=== AVAILABLE SEGMENTS ===")
print(nse.segments)

print("\n=== AVAILABLE TIMEFRAMES ===")
print(nse.timeframes)

print("\n=== FULL F&O SEARCH TEST ===")

queries = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
    "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
    "U", "V", "W", "X", "Y", "Z"
]

all_results = []

for q in queries:
    try:
        result = nse.search(q, "FO")

        if result is not None and not result.empty:
            print(f"\n===== {q} =====")
            print(result.to_string(index=False))
            all_results.append(result)

    except Exception as e:
        print(f"{q}: ERROR -> {type(e).__name__}: {e}")

print("\n====================================")
print("FULL F&O DISCOVERY FINISHED")
print("====================================")

print("Successful searches:", len(all_results))

if not all_results:
    print("NO F&O DATA FOUND")
    raise SystemExit(1)

print("\nOPENCHART FULL F&O SEARCH = OK")
