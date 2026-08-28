from curl_cffi import requests
import pprint

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

session = requests.Session()
session.get("https://www.nseindia.com/", headers=headers, impersonate="chrome120", timeout=6)

symbol = "SBIN"
url = f"https://www.nseindia.com/api/chart-databyindex?index={symbol}EQ"
r = session.get(url, headers=headers, impersonate="chrome120", timeout=6)
print("Status:", r.status_code)
pprint.pprint(r.json())
