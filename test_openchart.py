from openchart import NSEData

print("OpenChart diagnostic test")

nse = NSEData()

print("\nNSEData available methods:")
print([x for x in dir(nse) if not x.startswith("_")])

print("\nOpenChart object:")
print(nse)
