from openchart import NSEData
from datetime import datetime, timedelta

print("Starting OpenChart test...")

nse = NSEData()

print("Searching NIFTY futures...")

fo = nse.search("NIFTY", "FO")

print("\nNIFTY Futures:")
print(fo.head(10).to_string(index=False))

print("\nOpenChart import + NSE search = OK")
