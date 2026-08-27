from openchart import NSEData
import inspect

print("====================================")
print("OPENCHART SEARCH DIAGNOSTIC")
print("====================================")

nse = NSEData()

print("\n=== segments() ===")
try:
    print(nse.segments())
except Exception as e:
    print("ERROR:", type(e).__name__, e)

print("\n=== timeframes() ===")
try:
    print(nse.timeframes())
except Exception as e:
    print("ERROR:", type(e).__name__, e)

print("\n=== search signature ===")
print(inspect.signature(nse.search))

print("\n=== search_url signature ===")
print(inspect.signature(nse.search_url))

print("\n=== search_url ===")
try:
    print(nse.search_url)
except Exception as e:
    print("ERROR:", type(e).__name__, e)

print("\n=== TEST SEARCH ===")

for args in [
    ("RELIANCE",),
    ("RELIANCE", "FO"),
    ("RELIANCE", "NFO"),
]:
    try:
        print("\nCALL:", args)
        result = nse.search(*args)
        print(result)
    except Exception as e:
        print("ERROR:", type(e).__name__, e)

print("\n====================================")
print("DIAGNOSTIC COMPLETE")
print("====================================")
