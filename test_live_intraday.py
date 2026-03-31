#!/usr/bin/env python3
"""Test live.nepsealpha.com with intraday resolutions and from/to params."""
import subprocess, json
from datetime import datetime, timezone

utc = datetime.now(timezone.utc)
now_ts = int(utc.timestamp())
# NEPSE market open today: 05:15 UTC
market_open = int(utc.replace(hour=5, minute=15, second=0, microsecond=0).timestamp())
fs = utc.strftime("%Y%m%d%H%M%S") + "0000"

HEADERS = [
    "-H", "accept: application/json",
    "-H", "origin: https://nepsealpha.com",
    "-H", "referer: https://nepsealpha.com/",
    "-H", "user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
]

print(f"now={now_ts} market_open={market_open} fs={fs}")
print(f"NST now = {utc.hour+5}:{utc.minute+45 if utc.minute < 15 else utc.minute-15} approx\n")

for res in ["1D", "60", "15", "5", "1"]:
    url = f"https://live.nepsealpha.com/lv_data?symbol=SGHC&resolution={res}&from={market_open}&to={now_ts}&fs={fs}&tck=pass"
    r = subprocess.run(["curl", "-s", "-k", url] + HEADERS, capture_output=True, text=True, timeout=10)
    raw = r.stdout.strip()[:300]
    try:
        d = json.loads(r.stdout)
        t = d.get("t", [])
        c = d.get("c", [])
        s = d.get("s", "?")
        print(f"res={res:3s}: status={s} bars={len(t)}", end="")
        if t:
            print(f" first_t={t[0]} last_t={t[-1]} first_c={c[0] if c else '?'} last_c={c[-1] if c else '?'}")
        else:
            print()
    except Exception as e:
        print(f"res={res:3s}: raw={raw[:200]} err={e}")

# Also try without from/to for comparison
print("\n--- Without from/to (original) ---")
for res in ["1D", "60", "15"]:
    url = f"https://live.nepsealpha.com/lv_data?symbol=SGHC&resolution={res}&fs={fs}&tck=pass"
    r = subprocess.run(["curl", "-s", "-k", url] + HEADERS, capture_output=True, text=True, timeout=10)
    try:
        d = json.loads(r.stdout)
        t = d.get("t", []); c = d.get("c", [])
        s = d.get("s", "?")
        print(f"res={res:3s}: status={s} bars={len(t)}", end="")
        if t:
            print(f" first_t={t[0]} last_t={t[-1]} last_c={c[-1] if c else '?'}")
        else:
            print()
    except Exception as e:
        print(f"res={res}: raw={r.stdout[:200]} err={e}")
