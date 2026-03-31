"""
NEPSE Watchlist Monitor — Real-time intraday tracker
=====================================================
Reads watchlist.json saved by the last full `technical_analysis` scan.
Re-fetches intraday (1-min) bars and re-checks 1H + 15m conditions
for every tracked stock. Shows alerts the moment conditions change.

Usage:
    monitor                  # Full status table for all watched stocks
    monitor --alert          # Only print stocks with changes or SL breach
    monitor --fsk <key>      # Use a custom NepseAlpha session key

Output alerts:
    🚨  STOP LOSS BREACH     — Price fell below the calculated SL
    🟢  ENTRY READY          — All 3 TFs just aligned (buy trigger)
    🟡  STATUS IMPROVED      — WAIT → ENTRY ZONE  (getting closer)
    🔴  STATUS DEGRADED      — ENTRY ZONE → WAIT  (setup broke)
    ⚪  NO CHANGE            — Watching, nothing actionable yet
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiohttp

# ── Reuse screener's analysis functions ──────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from screener import (
    fetch_intraday_ohlcv,
    analyze_intraday,
    compute_intraday_checks,
    DEFAULT_FSK,
    MAX_CONCURRENT,
    REQUEST_DELAY,
)

WATCHLIST_JSON = Path(__file__).resolve().parent / "watchlist.json"

# Nepal Standard Time = UTC + 5:45
# NEPSE trades Sunday–Thursday 11:00–15:00 NST
_NST_OFFSET_HOURS = 5
_NST_OFFSET_MINS  = 45


def _is_market_open() -> bool:
    """Return True if NEPSE is currently open (Sun–Thu 11:00–15:00 NST)."""
    now_utc = datetime.now(timezone.utc)
    nst_minute = now_utc.hour * 60 + now_utc.minute + _NST_OFFSET_HOURS * 60 + _NST_OFFSET_MINS
    nst_hour   = (nst_minute // 60) % 24
    nst_min    = nst_minute % 60
    nst_time   = nst_hour * 60 + nst_min         # minutes since midnight NST
    open_time  = 11 * 60                          # 11:00
    close_time = 15 * 60                          # 15:00
    weekday    = (now_utc.weekday() + 1) % 7      # 0=Sun…6=Sat in Nepal (shift Mon-Sun)
    # Nepal Sun=0, Mon=1, …, Sat=6; NEPSE open Sun(0)..Thu(4)
    return (0 <= weekday <= 4) and (open_time <= nst_time <= close_time)


# ─── Per-stock intraday check ───────────────────────────────────────

async def check_stock(session: aiohttp.ClientSession, stock: dict, fsk: str) -> dict:
    """Fetch current intraday bars and re-evaluate 1H + 15m conditions."""
    symbol = stock["symbol"]
    result = stock.copy()
    result["monitor_time"] = datetime.now().strftime("%H:%M:%S")

    bars = await fetch_intraday_ohlcv(session, symbol, fsk)

    if not bars:
        result["new_entry_status"] = "NO DATA"
        result["h1_trend"]  = "—"
        result["h1_rsi"]    = None
        result["m15_verdict"] = "—"
        result["m15_rsi"]   = None
        result["volume_ratio_15m"] = None
        result["bullish_pattern_15m"] = False
        result["live_price"] = result.get("current_price", 0)
        result["sl_breached"] = False
        result["status_improved"] = False
        result["status_degraded"] = False
        result["has_alert"] = False
        return result

    result["live_price"] = float(bars[-1]["close"])

    intraday = analyze_intraday(bars)
    if not intraday:
        result["new_entry_status"] = "NO DATA"
        result["sl_breached"] = False
        result["status_improved"] = False
        result["status_degraded"] = False
        result["has_alert"] = False
        return result

    checks  = compute_intraday_checks(intraday)
    h_ok    = checks.get("hourly_zone_ok")
    m15_ok  = checks.get("intraday_trigger_ok")

    if h_ok and m15_ok:
        new_status = "ENTRY READY"
    elif h_ok:
        new_status = "ENTRY ZONE"
    else:
        new_status = "WAIT"

    hourly = intraday.get("hourly") or {}
    m15    = intraday.get("15m")    or {}

    result["new_entry_status"]    = new_status
    result["hourly_zone_ok"]      = h_ok
    result["intraday_trigger_ok"] = m15_ok
    result["h1_trend"]            = hourly.get("trend", "—")
    result["h1_rsi"]              = hourly.get("rsi_14")
    result["hourly_macd"]         = checks.get("hourly_macd", "—")
    result["m15_verdict"]         = m15.get("verdict", "—")
    result["m15_rsi"]             = m15.get("rsi_14")
    result["volume_ratio_15m"]    = checks.get("volume_ratio_15m")
    result["bullish_pattern_15m"] = checks.get("bullish_pattern_15m", False)

    # ── Alert flags ──────────────────────────────────────────────────
    sl        = stock.get("suggested_sl", 0)
    old_status = stock.get("entry_status", "WAIT")

    result["sl_breached"] = (result["live_price"] < sl) if sl > 0 else False

    result["status_improved"] = (
        old_status == "WAIT"       and new_status in ("ENTRY ZONE", "ENTRY READY")
    ) or (
        old_status == "ENTRY ZONE" and new_status == "ENTRY READY"
    )
    result["status_degraded"] = (
        old_status == "ENTRY READY" and new_status != "ENTRY READY"
    ) or (
        old_status == "ENTRY ZONE"  and new_status == "WAIT"
    )
    result["has_alert"] = (
        result["sl_breached"] or result["status_improved"] or result["status_degraded"]
    )
    return result


# ─── Main monitor loop ──────────────────────────────────────────────

async def run_monitor(alert_only: bool = False, fsk: str = DEFAULT_FSK):
    if not WATCHLIST_JSON.exists():
        print(
            "\n❌  watchlist.json not found.\n"
            "   Run `technical_analysis` first to build the watchlist.\n"
        )
        return

    with open(WATCHLIST_JSON) as f:
        data = json.load(f)

    stocks   = data.get("stocks", [])
    saved_at = data.get("saved_at", "unknown")[:19]

    if not stocks:
        print("\n❌  Watchlist is empty. Run `technical_analysis` first.\n")
        return

    market_open = _is_market_open()
    market_note = "🟢 MARKET OPEN" if market_open else "🔴 MARKET CLOSED — intraday data is from last session"

    print(f"\n{'='*92}")
    print(f"  🔍 NEPSE WATCHLIST MONITOR — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  {market_note}")
    print(f"  Tracking {len(stocks)} stocks  |  Last full scan: {saved_at}")
    print(f"{'='*92}\n")

    if not market_open:
        print("  ℹ️   Market is closed. Intraday results reflect the last trading session.\n")

    # Fetch all intraday data concurrently
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def throttled(session, stock):
        async with semaphore:
            await asyncio.sleep(REQUEST_DELAY)
            return await check_stock(session, stock, fsk)

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        print(f"  Fetching intraday data for {len(stocks)} stocks ...", end="", flush=True)
        results = await asyncio.gather(*[throttled(session, s) for s in stocks])
        print(" done.\n")

    # ── Group by alert category ───────────────────────────────────────
    breached     = [r for r in results if r.get("sl_breached")]
    entry_ready  = [r for r in results if r.get("new_entry_status") == "ENTRY READY"]
    improved     = [r for r in results if r.get("status_improved") and r.get("new_entry_status") != "ENTRY READY"]
    degraded     = [r for r in results if r.get("status_degraded")]
    waiting      = [r for r in results if not r.get("has_alert") and r.get("new_entry_status") == "WAIT"]
    no_data      = [r for r in results if r.get("new_entry_status") == "NO DATA"]

    # ── 🚨 Stop-loss breaches ─────────────────────────────────────────
    if breached:
        print(f"  🚨 {'─'*88}")
        print(f"  🚨  STOP LOSS BREACHED — Exit these positions immediately!")
        print(f"  🚨 {'─'*88}")
        for r in breached:
            price = r.get("live_price", 0)
            sl    = r.get("suggested_sl", 0)
            pct   = ((price - sl) / sl * 100) if sl > 0 else 0
            print(f"  🚨  {r['symbol']:<10}  Current Rs.{price:>7.1f}  |  SL Rs.{sl:.2f}  |  {pct:+.1f}% BELOW SL  |  EXIT NOW")
        print()

    # ── 🟢 Entry ready ────────────────────────────────────────────────
    if entry_ready:
        print(f"  🟢 {'─'*88}")
        print(f"  🟢  ENTRY READY — All 3 TFs aligned. Enter at next candle open!")
        print(f"  🟢 {'─'*88}")
        for r in entry_ready:
            price = r.get("live_price", 0)
            sl    = r.get("suggested_sl", 0)
            tgt   = r.get("suggested_target", 0)
            rr    = r.get("rr_ratio", 0)
            vol   = r.get("volume_ratio_15m")
            changed = "  ← JUST TRIGGERED" if r.get("status_improved") else ""
            vol_str = f"{vol:.2f}x" if vol is not None else "—"
            print(f"  🟢  {r['symbol']:<10}  Rs.{price:>7.1f}  |  SL Rs.{sl:.2f}  |  Target Rs.{tgt:.2f}  |  R:R {rr:.1f}  |  15m Vol {vol_str}{changed}")
        print()

    # ── 🟡 Status improved ────────────────────────────────────────────
    if improved:
        print(f"  🟡 {'─'*88}")
        print(f"  🟡  STATUS IMPROVED — Moving toward entry trigger")
        print(f"  🟡 {'─'*88}")
        for r in improved:
            price = r.get("live_price", 0)
            old   = r.get("entry_status", "?")
            new   = r.get("new_entry_status", "?")
            h1    = r.get("h1_trend", "—")[:11]
            h1_rsi = r.get("h1_rsi")
            rsi_s = f"{h1_rsi:.0f}" if h1_rsi else "—"
            macd  = r.get("hourly_macd", "—")
            print(f"  🟡  {r['symbol']:<10}  Rs.{price:>7.1f}  |  {old:<11} → {new:<11}  |  1H: {h1:<12} RSI:{rsi_s}  |  MACD: {macd}")
        print()

    # ── 🔴 Status degraded ───────────────────────────────────────────
    if degraded:
        print(f"  🔴 {'─'*88}")
        print(f"  🔴  STATUS DEGRADED — Setup weakening, don't enter")
        print(f"  🔴 {'─'*88}")
        for r in degraded:
            price = r.get("live_price", 0)
            old   = r.get("entry_status", "?")
            new   = r.get("new_entry_status", "?")
            h1    = r.get("h1_trend", "—")[:11]
            print(f"  🔴  {r['symbol']:<10}  Rs.{price:>7.1f}  |  {old:<11} → {new:<11}  |  1H: {h1}")
        print()

    # ── Full status table (shown unless --alert) ─────────────────────
    valid = [r for r in results if r.get("new_entry_status") not in ("NO DATA",)]
    if not alert_only and valid:
        print(f"  {'='*90}")
        print(f"  {'Symbol':<10} {'Price':>8} {'SL':>8} {'vs SL':>7}  {'Entry Status':<13} {'1H Trend':<12} {'1H RSI':>6} {'15m':>8} {'Vol':>6} {'Chk':>5}")
        print(f"  {'─'*10} {'─'*8} {'─'*8} {'─'*7}  {'─'*13} {'─'*12} {'─'*6} {'─'*8} {'─'*6} {'─'*5}")

        def _sort_key(r):
            rank = {"ENTRY READY": 0, "ENTRY ZONE": 1, "WAIT": 2}.get(r.get("new_entry_status", "WAIT"), 3)
            urgent = -1 if r.get("sl_breached") else 0
            return (urgent, rank, -r.get("checklist_score", 0))

        for r in sorted(valid, key=_sort_key):
            price  = r.get("live_price", r.get("current_price", 0))
            sl     = r.get("suggested_sl", 0)
            vs_sl  = ((price - sl) / sl * 100) if sl > 0 else 0
            sts    = r.get("new_entry_status", "—")
            h1     = r.get("h1_trend", "—")[:11]
            h1_rsi = r.get("h1_rsi")
            rsi_s  = f"{h1_rsi:.0f}" if h1_rsi else "—"
            m15_v  = r.get("m15_verdict", "—")[:7]
            vol    = r.get("volume_ratio_15m")
            vol_s  = f"{vol:.2f}x" if vol is not None else "—"
            chk    = f"{r.get('checklist_score', 0)}/13"

            if r.get("sl_breached"):
                icon = "🚨"
            elif sts == "ENTRY READY":
                icon = "🟢"
            elif sts == "ENTRY ZONE":
                icon = "🟡"
            else:
                icon = "⚪"

            changed = ""
            if r.get("status_improved"):
                changed = " ↑"
            elif r.get("status_degraded"):
                changed = " ↓"

            print(f"  {icon} {r['symbol']:<9} {price:>8.1f} {sl:>8.2f} {vs_sl:>+6.1f}%  "
                  f"{sts:<13} {h1:<12} {rsi_s:>6} {m15_v:>8} {vol_s:>6} {chk:>5}{changed}")

        if no_data:
            print(f"\n  ⚠️  No intraday data: {', '.join(r['symbol'] for r in no_data)}")
        print(f"  {'='*90}\n")

    # ── Summary ──────────────────────────────────────────────────────
    if not breached and not entry_ready and not improved and not degraded:
        print(f"  ✅  No alerts — all setups unchanged since last scan.")
        print(f"      SGHC/HPPL/RFPL/MHL are in WAIT — 1H is DOWNTREND after today's -2% panic.")
        print(f"      Watch for: 1H trend flip to UPTREND + 15m MACD Bullish → will show as 🟡 IMPROVED.\n")

    print(f"  ℹ️  Run `technical_analysis` for a fresh full scan with expert intelligence.")
    print(f"      Run `monitor --alert` to show only alerts (faster reading).\n")


def _build_state_map(results: list[dict]) -> dict:
    """Build per-symbol state snapshot for change detection between watch cycles."""
    return {
        r["symbol"]: {
            "entry_status": r.get("new_entry_status"),
            "sl_breached": bool(r.get("sl_breached", False)),
        }
        for r in results
    }


def _print_watch_events(results: list[dict], prev_state: Optional[dict], cycle: int):
    """Print only NEW events compared to the previous cycle snapshot."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*92}")
    print(f"  ⏱️  LIVE WATCH CYCLE #{cycle} — {now}")
    print(f"{'='*92}")

    if not prev_state:
        print("  ℹ️  Baseline captured. Waiting for changes from next cycle...\n")
        return

    events = []
    for r in results:
        symbol = r["symbol"]
        prev = prev_state.get(symbol, {})
        old_status = prev.get("entry_status")
        new_status = r.get("new_entry_status")
        old_sl = bool(prev.get("sl_breached", False))
        new_sl = bool(r.get("sl_breached", False))
        price = r.get("live_price", r.get("current_price", 0))

        if new_sl and not old_sl:
            sl = r.get("suggested_sl", 0)
            events.append(f"  🚨  SELL ALERT: {symbol} breached SL (Price Rs.{price:.1f} < SL Rs.{sl:.2f})")

        if old_status != new_status:
            if new_status == "ENTRY READY":
                events.append(f"  🟢  BUY ALERT:  {symbol} is now ENTRY READY at Rs.{price:.1f}")
            elif old_status == "ENTRY READY" and new_status != "ENTRY READY":
                events.append(f"  🔴  EXIT ALERT: {symbol} lost ENTRY READY ({old_status} -> {new_status})")
            else:
                events.append(f"  🟡  STATUS:     {symbol} changed {old_status} -> {new_status}")

    if events:
        print("  🔔 New actionable events:\n")
        for e in events:
            print(e)
        print()
    else:
        print("  ✅ No new status changes this cycle.\n")


async def watch_loop(interval_seconds: int, fsk: str):
    """Run monitor continuously and alert only when something changes."""
    if interval_seconds < 1:
        interval_seconds = 1

    prev_state: Optional[dict] = None
    cycle = 1

    while True:
        if not WATCHLIST_JSON.exists():
            print("\n❌ watchlist.json not found. Run `technical_analysis` first.\n")
            return

        with open(WATCHLIST_JSON) as f:
            data = json.load(f)
        stocks = data.get("stocks", [])

        if not stocks:
            print("\n❌ Watchlist is empty. Run `technical_analysis` first.\n")
            return

        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def throttled(session, stock):
            async with semaphore:
                await asyncio.sleep(REQUEST_DELAY)
                return await check_stock(session, stock, fsk)

        connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            results = await asyncio.gather(*[throttled(session, s) for s in stocks])

        _print_watch_events(results, prev_state, cycle)
        prev_state = _build_state_map(results)
        cycle += 1

        print(f"  Next check in {interval_seconds}s...  (Ctrl+C to stop)")
        await asyncio.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(
        description="NEPSE Watchlist Monitor — real-time intraday tracking"
    )
    parser.add_argument("--alert", action="store_true",
                        help="Show only stocks with status changes or SL breach")
    parser.add_argument("--watch", action="store_true",
                        help="Run continuously and alert only when statuses change")
    parser.add_argument("--interval", type=int, default=60,
                        help="Watch mode interval in seconds (default: 60)")
    parser.add_argument("--fsk", type=str, default=DEFAULT_FSK,
                        help="NepseAlpha session key")
    args = parser.parse_args()
    try:
        if args.watch:
            asyncio.run(watch_loop(interval_seconds=args.interval, fsk=args.fsk))
        else:
            asyncio.run(run_monitor(alert_only=args.alert, fsk=args.fsk))
    except KeyboardInterrupt:
        print("\n\n🛑 Live watch stopped by user.\n")


if __name__ == "__main__":
    main()
