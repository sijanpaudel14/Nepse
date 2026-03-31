"""
Test https://live.nepsealpha.com/lv_data  — today's live bar endpoint
Run: python3 test_live_nepse.py
"""
import requests
import json
import time
import warnings
from datetime import datetime, timezone

warnings.filterwarnings("ignore")

LIVE_BASE = "https://live.nepsealpha.com/lv_data"

H = {
    "accept": "application/json",
    "origin": "https://nepsealpha.com",
    "referer": "https://nepsealpha.com/",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
    "cache-control": "no-cache",
}

now_utc = datetime.now(timezone.utc)
print(f"Current UTC: {now_utc}")
print(f"Current NST: {now_utc.astimezone()} (approx)")

# ── Build fs param in the format seen in the real curl ─────────────────
# Sample from user: fs=202603310212141220
# Format appears: YYYYMMDDHHMMSS + 4 digits (possibly microseconds/ms or counter)
# Try deriving from current UTC time
fs_from_utc = now_utc.strftime("%Y%m%d%H%M%S") + "0000"
# Also try from NST (UTC+5:45)
from datetime import timedelta
nst = now_utc + timedelta(hours=5, minutes=45)
fs_from_nst = nst.strftime("%Y%m%d%H%M%S") + "0000"
# The sample value verbatim
fs_sample = "202603310212141220"

print(f"\nfs from UTC: {fs_from_utc}")
print(f"fs from NST: {fs_from_nst}")
print(f"fs sample:   {fs_sample}")

# ── STEP 1: Test with sample fs, tck=pass ─────────────────────────────
print("\n" + "="*60)
print("STEP 1: Known-good curl parameters (SGHC, 1D, sample fs)")
print("="*60)

for fs_label, fs_val in [("sample", fs_sample), ("utc_derived", fs_from_utc),
                          ("nst_derived", fs_from_nst), ("empty", ""), ("none", None)]:
    params = {"symbol": "SGHC", "resolution": "1D", "tck": "pass"}
    if fs_val is not None:
        params["fs"] = fs_val
    try:
        r = requests.get(LIVE_BASE, params=params, headers=H, timeout=8, verify=False)
        print(f"\n  fs={fs_label!r:15s} → HTTP {r.status_code}  len={len(r.text)}")
        if r.status_code == 200:
            try:
                d = r.json()
                print(f"  Response: {json.dumps(d, indent=2)[:600]}")
            except Exception:
                print(f"  Raw: {r.text[:300]}")
    except Exception as e:
        print(f"  fs={fs_label!r:15s} → ERROR: {e}")

# ── STEP 2: Test different resolutions ────────────────────────────────
print("\n" + "="*60)
print("STEP 2: Different resolutions (1D, 1H, 60, 15, 1)")
print("="*60)

for res in ["1D", "1H", "60", "15", "1", "D", "W"]:
    try:
        r = requests.get(LIVE_BASE,
                         params={"symbol": "SGHC", "resolution": res, "tck": "pass", "fs": fs_sample},
                         headers=H, timeout=8, verify=False)
        if r.status_code == 200:
            try:
                d = r.json()
                print(f"  resolution={res:5s} → 200  keys={list(d.keys()) if isinstance(d,dict) else type(d).__name__}  {str(d)[:120]}")
            except Exception:
                print(f"  resolution={res:5s} → 200  raw={r.text[:120]}")
        else:
            print(f"  resolution={res:5s} → {r.status_code}")
    except Exception as e:
        print(f"  resolution={res:5s} → ERROR: {e}")

# ── STEP 3: Multiple symbols ───────────────────────────────────────────
print("\n" + "="*60)
print("STEP 3: Multiple symbols (SGHC, NEPSE, NMB, NABIL, SCB)")
print("="*60)

for sym in ["SGHC", "NEPSE", "NMB", "NABIL", "SCB", "UPPER", "NYADI"]:
    try:
        r = requests.get(LIVE_BASE,
                         params={"symbol": sym, "resolution": "1D", "tck": "pass", "fs": fs_sample},
                         headers=H, timeout=8, verify=False)
        if r.status_code == 200:
            try:
                d = r.json()
                print(f"  {sym:8s} → 200  {str(d)[:150]}")
            except Exception:
                print(f"  {sym:8s} → 200  raw={r.text[:150]}")
        else:
            print(f"  {sym:8s} → {r.status_code}  {r.text[:80]}")
    except Exception as e:
        print(f"  {sym:8s} → ERROR: {e}")

# ── STEP 4: Concurrent bulk fetch speed test (12 symbols) ─────────────
print("\n" + "="*60)
print("STEP 4: Concurrent speed test — 12 symbols via ThreadPoolExecutor")
print("="*60)

import concurrent.futures

TEST_SYMS = ["SGHC","NABIL","NMB","SCB","UPPER","NYADI","NHPC","AKJCL","RADHI","RIDI","NGPL","PPCL"]

def fetch_live(sym):
    try:
        r = requests.get(LIVE_BASE,
                         params={"symbol": sym, "resolution": "1D", "tck": "pass", "fs": fs_sample},
                         headers=H, timeout=8, verify=False)
        if r.status_code == 200:
            return sym, r.json()
        return sym, None
    except Exception as e:
        return sym, None

t0 = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    results = dict(ex.map(fetch_live, TEST_SYMS))
elapsed = time.time() - t0

success = sum(1 for v in results.values() if v is not None)
print(f"  {success}/{len(TEST_SYMS)} success in {elapsed:.2f}s")
for sym, d in results.items():
    if d:
        print(f"  {sym:8s}: {str(d)[:100]}")
    else:
        print(f"  {sym:8s}: FAILED")
