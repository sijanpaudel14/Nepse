"""
entry_confirm.py — Live Entry Confirmation Checker
===================================================
Answers the single question: "Should I enter this trade RIGHT NOW?"

Checks three real-time triggers:
  1. Volume spike  — is today's volume >= 1.5x the 20-day average?
  2. Broker flip   — are top 3 brokers net buying > threshold today?
  3. Price status  — has price broken the key level with a green move?

Usage:
  python tools/entry_confirm.py SGHC
  python tools/entry_confirm.py SGHC --breakout-level 430
  python tools/entry_confirm.py SGHC --broker-threshold 300000   # Rs. 3L instead of 5L

Must be run from nepse_ai_trading/ directory with venv active.
Must run during market hours (11 AM – 3 PM) for live data.
After close: uses today's completed bar (volume/price data available, intraday 15m not).
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime, time as dtime
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "nepse-chart-extension" / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT.parent / ".env")

# ── Imports ───────────────────────────────────────────────────────────────────
try:
    import aiohttp
    from screener import fetch_ohlcv, run_analysis, fetch_intraday_ohlcv, DEFAULT_FSK
    _HAS_SCREENER = True
except ImportError as e:
    _HAS_SCREENER = False
    _SCREENER_ERR = str(e)

try:
    from data.sharehub_api import ShareHubAPI
    _HAS_SHAREHUB = True
except ImportError:
    _HAS_SHAREHUB = False

try:
    sys.path.insert(0, str(ROOT.parent / "NepseUnofficialApi"))
    from nepse import Nepse as _NepseAPI
    _HAS_NEPSE_API = True
except ImportError:
    _HAS_NEPSE_API = False


# ──────────────────────────────────────────────────────────────────────────────

def _get_live_quote(symbol: str) -> dict | None:
    """
    Fetch real-time market data via NepseUnofficialApi.getLiveMarket().
    Returns dict with: lastTradedPrice, previousClose, percentageChange,
                       totalTradeQuantity, openPrice, highPrice, lowPrice
    Returns None if unavailable or market is closed.
    """
    if not _HAS_NEPSE_API or not _is_market_hours():
        return None
    try:
        n = _NepseAPI()
        n.setTLSVerification(False)
        live = n.getLiveMarket()
        sym = symbol.upper()
        for item in (live or []):
            if isinstance(item, dict) and item.get("symbol") == sym:
                return item
    except Exception:
        pass
    return None


async def _fetch_sharehub_live_1min(
    session: aiohttp.ClientSession,
    symbol: str,
    countback: int = 390,          # 390 min = full NEPSE session (6.5h)
) -> list[dict] | None:
    """
    Fetch today's live 1-minute OHLCV bars from ShareHub's live API.
    Works during market hours — returns today's bars as they form in real-time.

    Uses SHAREHUB_AUTH_TOKEN from .env (same JWT that the broker API uses — works as auth-data header).

    Returns list of dicts: {time (ms), open, high, low, close, volume}
    Returns None if token missing or request fails.
    """
    auth = os.getenv("SHAREHUB_AUTH_TOKEN", "")
    if not auth:
        return None
    now_epoch = int(datetime.now().timestamp())
    url = (
        f"https://live.nepsesharehub.com/v1/daily-graph/candle-chart/history"
        f"?symbol={symbol}&resolution=1&countback={countback}&isAdjust=true&time={now_epoch}"
    )
    headers = {
        "accept": "*/*",
        "auth-data": auth,
        "content-type": "application/json",
        "access-control-allow-origin": "*",
        "origin": "https://sharehubnepal.com",
        "referer": "https://sharehubnepal.com/",
    }
    try:
        async with session.get(
            url, headers=headers, ssl=False,
            timeout=aiohttp.ClientTimeout(total=8)
        ) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                if data.get("success") and data.get("data"):
                    return data["data"]
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────────────────────────────────

def _is_market_hours() -> bool:
    now = datetime.now().time()
    return dtime(10, 55) <= now <= dtime(15, 5)


def _bar(filled: int, total: int = 10, char: str = "█") -> str:
    n = round(filled / total * 10) if total else 0
    return char * n + "░" * (10 - n)


# ── Trigger 1: Volume ─────────────────────────────────────────────────────────

async def check_volume(symbol: str, threshold: float = 1.5) -> dict:
    """
    Fetch daily analysis and compute today's volume vs 20-day average.
    During market hours: uses live intraday bars for both LTP and today's volume
    so yesterday's daily close is never shown as the current price.
    """
    if not _HAS_SCREENER:
        return {"ok": None, "error": _SCREENER_ERR}

    try:
        async with aiohttp.ClientSession() as session:
            bars = await fetch_ohlcv(session, symbol, fsk=DEFAULT_FSK)
            intraday_bars = None
            if _is_market_hours():
                intraday_bars = await fetch_intraday_ohlcv(session, symbol, DEFAULT_FSK)
        if not bars:
            return {"ok": None, "error": "No data from NepseAlpha"}
        result = run_analysis(symbol, bars)
        if not result:
            return {"ok": None, "error": "Analysis failed"}

        avg_vol = result.get("avg_volume") or 0
        vol_ratio = result.get("volume_ratio") or 0
        today_vol = round(avg_vol * vol_ratio) if avg_vol and vol_ratio else None
        ltp = result.get("current_price")
        change_pct = result.get("price_change_pct")

        # Live override: during market hours use NepseUnofficialApi for real-time LTP + volume
        live_quote = _get_live_quote(symbol)
        if live_quote:
            live_ltp = live_quote.get("lastTradedPrice")
            today_vol_live = live_quote.get("totalTradeQuantity")
            prev_close = live_quote.get("previousClose") or ltp
            if live_ltp:
                ltp = float(live_ltp)
                change_pct = round(((ltp - prev_close) / prev_close) * 100, 2) if prev_close else change_pct
            if today_vol_live:
                today_vol = int(today_vol_live)
                vol_ratio = round(today_vol / avg_vol, 2) if avg_vol else vol_ratio
        elif intraday_bars and len(intraday_bars) >= 2:
            # Fallback: try intraday bars (works after market close for same-day data)
            import pandas as pd
            df = pd.DataFrame(intraday_bars)
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert("Asia/Kathmandu")
            today_str = datetime.now().strftime("%Y-%m-%d")
            today_df = df[df["time"].dt.strftime("%Y-%m-%d") == today_str]
            if not today_df.empty:
                live_ltp = float(today_df["close"].iloc[-1])
                today_vol_live = int(today_df["volume"].sum())
                vol_ratio = round(today_vol_live / avg_vol, 2) if avg_vol else vol_ratio
                prev_close = result.get("current_price") or ltp
                change_pct = round(((live_ltp - prev_close) / prev_close) * 100, 2) if prev_close else change_pct
                ltp = live_ltp
                today_vol = today_vol_live

        return {
            "ok": vol_ratio >= threshold,
            "volume_ratio": vol_ratio,
            "avg_volume": avg_vol,
            "today_volume": today_vol,
            "threshold": threshold,
            "ltp": ltp,
            "change_pct": change_pct,
            # resistance data — used by auto-detect in main()
            "nearest_resistance": result.get("nearest_resistance"),
            "resistance_distance_pct": result.get("resistance_distance_pct"),
            "high_52w": result.get("high_52w"),
            "breakout_status": result.get("breakout_status"),
            "_raw": result,
        }
    except Exception as e:
        return {"ok": None, "error": str(e)}


# ── Trigger 2: Broker flip ────────────────────────────────────────────────────

def check_broker_flip(symbol: str, threshold_rs: float = 500_000) -> dict:
    """
    Pull today's (1D) floorsheet broker analysis from ShareHub.
    Returns top-3 brokers' net Rs. amount and whether the sum exceeds threshold.
    """
    if not _HAS_SHAREHUB:
        return {"ok": None, "error": "ShareHub not available"}

    token = os.getenv("SHAREHUB_AUTH_TOKEN", "")
    if not token:
        return {"ok": None, "error": "SHAREHUB_AUTH_TOKEN not set in .env"}

    try:
        api = ShareHubAPI(auth_token=token)
        brokers = api.get_broker_analysis(symbol, duration="1D")
        if not brokers:
            return {"ok": None, "error": "No broker data returned (market may be closed or token expired)"}

        # Sort by net_amount descending — top net buyers first
        sorted_brokers = sorted(brokers, key=lambda b: b.net_amount, reverse=True)
        top3 = sorted_brokers[:3]

        top3_net_rs = sum(b.net_amount for b in top3)
        all_net_rs = sum(b.net_amount for b in brokers)

        return {
            "ok": top3_net_rs >= threshold_rs,
            "top3_net_rs": top3_net_rs,
            "all_net_rs": all_net_rs,
            "threshold_rs": threshold_rs,
            "top3": [
                {
                    "code": b.broker_code,
                    "name": b.broker_name[:30],
                    "net_qty": b.net_quantity,
                    "net_rs": b.net_amount,
                    "buy_qty": b.buy_quantity,
                    "sell_qty": b.sell_quantity,
                }
                for b in top3
            ],
            "all_brokers": len(brokers),
        }
    except Exception as e:
        return {"ok": None, "error": str(e)}


# ── Trigger 3: Price status ───────────────────────────────────────────────────

async def check_price_breakout(symbol: str, breakout_level: float) -> dict:
    """
    Check if price has crossed and is holding above the breakout level.
    Uses:
    - Daily bar: current LTP vs breakout level
    - Intraday 15m: last closed candle green + above level (market hours only)
    """
    if not _HAS_SCREENER:
        return {"ok": None, "error": _SCREENER_ERR}

    try:
        async with aiohttp.ClientSession() as session:
            bars = await fetch_ohlcv(session, symbol, fsk=DEFAULT_FSK)
            intraday_bars = None
            live_1min = None
            if _is_market_hours():
                intraday_bars = await fetch_intraday_ohlcv(session, symbol, DEFAULT_FSK)
                live_1min = await _fetch_sharehub_live_1min(session, symbol)
        result = run_analysis(symbol, bars) if bars else None

        if not result:
            return {"ok": None, "error": "No data from NepseAlpha"}

        # Live LTP — priority: ShareHub live bars > NepseUnofficialApi > daily close
        ltp = result.get("current_price") or 0
        live_quote = _get_live_quote(symbol)

        # Parse ShareHub live 1-min bars: filter to today, get last close
        import pandas as pd
        today_str = datetime.now().strftime("%Y-%m-%d")
        live_today_df = None
        if live_1min:
            _df_live = pd.DataFrame(live_1min)
            # ShareHub time is in milliseconds
            _df_live["time"] = pd.to_datetime(_df_live["time"], unit="ms", utc=True).dt.tz_convert("Asia/Kathmandu")
            _today = _df_live[_df_live["time"].dt.strftime("%Y-%m-%d") == today_str]
            if not _today.empty:
                live_today_df = _today.sort_values("time")
                ltp = float(live_today_df["close"].iloc[-1])   # live LTP from 1-min bars
        elif live_quote and live_quote.get("lastTradedPrice"):
            ltp = float(live_quote["lastTradedPrice"])
        elif intraday_bars and len(intraday_bars) >= 2:
            _df = pd.DataFrame(intraday_bars)
            _df["time"] = pd.to_datetime(_df["time"], unit="s", utc=True).dt.tz_convert("Asia/Kathmandu")
            _today_df = _df[_df["time"].dt.strftime("%Y-%m-%d") == today_str]
            if not _today_df.empty:
                ltp = float(_today_df["close"].iloc[-1])

        above_level = ltp > breakout_level

        # 15-min confirmation — prefer ShareHub live bars (market hours), fall back to NepseAlpha
        last_15m_green = None
        last_15m_close = None
        last_15m_above = None
        live_1min_available = live_today_df is not None and len(live_today_df) >= 2

        if live_1min_available:
            # Resample today's live 1-min bars into 15-min candles
            df_15 = (
                live_today_df
                .set_index("time")
                .resample("15min")
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
            )
            if len(df_15) >= 1:
                last = df_15.iloc[-1]
                last_15m_close = float(last["close"])
                last_15m_green = last["close"] > last["open"]
                last_15m_above = last["close"] > breakout_level

        elif intraday_bars and len(intraday_bars) >= 15:
            # Fallback to NepseAlpha intraday (stale during market hours but better than nothing)
            df = pd.DataFrame(intraday_bars)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df = df.sort_values("time")
            df_15 = df.set_index("time").resample("15min").agg({
                "open": "first", "high": "max", "low": "min",
                "close": "last", "volume": "sum"
            }).dropna()
            if len(df_15) >= 2:
                last = df_15.iloc[-1]
                last_15m_close = float(last["close"])
                last_15m_green = last["close"] > last["open"]
                last_15m_above = last["close"] > breakout_level

        # Status determination
        intraday_available = live_1min_available or (intraday_bars is not None)
        if intraday_available:
            ok = above_level and (last_15m_green is True) and (last_15m_above is True)
        else:
            ok = above_level

        # 3-timeframe confluence
        tf_data = _analyse_timeframes(live_today_df, result)

        return {
            "ok": ok,
            "ltp": ltp,
            "breakout_level": breakout_level,
            "above_level": above_level,
            "last_15m_close": last_15m_close,
            "last_15m_green": last_15m_green,
            "last_15m_above_level": last_15m_above,
            "intraday_available": intraday_available,
            "live_1min_active": live_1min_available,   # shows if ShareHub live bars were used
            "tf_data": tf_data,
        }
    except Exception as e:
        return {"ok": None, "error": str(e)}


# ── 3-Timeframe confluence helper ────────────────────────────────────────────

def _analyse_timeframes(live_today_df, daily_result: dict) -> dict:
    """
    Derive 1D bias, 1H zone, and 15m trigger from available data.
    Returns a flat dict consumed by _print_results().
    """
    import pandas as pd

    out = {
        "daily_bias": "", "daily_rsi": None, "daily_trend": "", "daily_macd_bull": None,
        "h1_green": None, "h1_trend": "", "h1_rsi": None, "h1_bars_count": 0,
        "h1_vol_ratio": None, "h1_vol_above_avg": None,
        "m15_green": None, "m15_rsi": None, "m15_vol_ratio": None,
        "m15_vol_above_avg": None, "m15_bars_count": 0,
        "confluence_score": 0, "confluence_signals": [],
    }

    # ── 1D bias ───────────────────────────────────────────────────────────────
    if daily_result:
        rsi_d = daily_result.get("rsi")
        trend_d = daily_result.get("trend") or ""
        macd_val = daily_result.get("macd") or 0
        out["daily_rsi"] = round(rsi_d, 1) if rsi_d else None
        out["daily_trend"] = trend_d
        out["daily_macd_bull"] = macd_val > 0
        rsi_ok = rsi_d is not None and 40 <= rsi_d <= 70
        bias_ok = "UPTREND" in trend_d.upper() and rsi_ok
        out["daily_bias"] = "LONG" if bias_ok else "WAIT"

    # ── Intraday TFs (needs live bars) ────────────────────────────────────────
    if live_today_df is None or len(live_today_df) < 4:
        # Skip intraday scoring; score only daily
        score, signals = 0, []
        if "LONG" in out["daily_bias"]:
            score += 1
            signals.append("1D: LONG ✅")
        else:
            signals.append("1D: WAIT ⚠️")
        signals.append("1H: no data ⚪")
        signals.append("15m: no data ⚪")
        out["confluence_score"] = score
        out["confluence_signals"] = signals
        return out

    df = live_today_df.copy().set_index("time")

    # ── 1H candles ────────────────────────────────────────────────────────────
    df_1h = df.resample("1h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    out["h1_bars_count"] = len(df_1h)
    if len(df_1h) >= 1:
        last_h1 = df_1h.iloc[-1]
        out["h1_green"] = bool(last_h1["close"] > last_h1["open"])
        if len(df_1h) >= 2:
            out["h1_trend"] = "UP" if df_1h["close"].iloc[-1] > df_1h["close"].iloc[0] else "DOWN"
        # 1H volume: is the last hour's volume above the average of prior hours?
        vols_1h = df_1h["volume"].values
        if len(vols_1h) >= 2:
            avg_h1_vol = float(sum(vols_1h[:-1])) / (len(vols_1h) - 1)
            out["h1_vol_ratio"] = round(float(vols_1h[-1]) / avg_h1_vol, 2) if avg_h1_vol > 0 else None
            out["h1_vol_above_avg"] = (out["h1_vol_ratio"] is not None and out["h1_vol_ratio"] >= 1.2)
        closes_1h = df_1h["close"].values
        if len(closes_1h) >= 3:
            gains = [max(closes_1h[i] - closes_1h[i-1], 0) for i in range(1, len(closes_1h))]
            losses = [max(closes_1h[i-1] - closes_1h[i], 0) for i in range(1, len(closes_1h))]
            avg_g = sum(gains) / len(gains) if gains else 0
            avg_l = sum(losses) / len(losses) if losses else 0
            if avg_l == 0:
                out["h1_rsi"] = 100.0
            else:
                rs = avg_g / avg_l
                out["h1_rsi"] = round(100 - 100 / (1 + rs), 1)

    # ── 15m candles ───────────────────────────────────────────────────────────
    df_15 = df.resample("15min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    out["m15_bars_count"] = len(df_15)
    if len(df_15) >= 2:
        last_15 = df_15.iloc[-1]
        out["m15_green"] = bool(last_15["close"] > last_15["open"])
        closes_15 = df_15["close"].values
        if len(closes_15) >= 3:
            gains = [max(closes_15[i] - closes_15[i-1], 0) for i in range(1, len(closes_15))]
            losses = [max(closes_15[i-1] - closes_15[i], 0) for i in range(1, len(closes_15))]
            avg_g = sum(gains) / len(gains) if gains else 0
            avg_l = sum(losses) / len(losses) if losses else 0
            if avg_l == 0:
                out["m15_rsi"] = 100.0
            else:
                rs = avg_g / avg_l
                out["m15_rsi"] = round(100 - 100 / (1 + rs), 1)
        vols = df_15["volume"].values
        if len(vols) >= 3:
            avg_vol = float(sum(vols[:-1])) / (len(vols) - 1)
            out["m15_vol_ratio"] = round(float(vols[-1]) / avg_vol, 2) if avg_vol > 0 else None
            out["m15_vol_above_avg"] = (out["m15_vol_ratio"] is not None and out["m15_vol_ratio"] >= 1.2)

    # ── Confluence scoring ────────────────────────────────────────────────────
    score, signals = 0, []
    if "LONG" in out["daily_bias"]:
        score += 1
        signals.append("1D: LONG ✅")
    else:
        signals.append("1D: WAIT ⚠️")

    if out.get("h1_green") and out.get("h1_trend") == "UP" and out.get("h1_vol_above_avg"):
        score += 1
        signals.append("1H: green + uptrend + volume ✅")
    elif out.get("h1_green") and out.get("h1_trend") == "UP":
        signals.append("1H: green + uptrend (volume weak ⚠️)")
    elif out.get("h1_green") is False:
        signals.append("1H: red candle ❌")
    else:
        signals.append("1H: neutral ⚪")

    if out.get("m15_green") and out.get("m15_vol_above_avg"):
        score += 1
        signals.append("15m: green + volume ✅")
    elif out.get("m15_green"):
        signals.append("15m: green (volume weak) ⚠️")
    elif out.get("m15_green") is False:
        signals.append("15m: red candle ❌")
    else:
        signals.append("15m: no data ⚪")

    out["confluence_score"] = score
    out["confluence_signals"] = signals
    return out


# ── Print helpers ─────────────────────────────────────────────────────────────

def _tick(ok) -> str:
    if ok is True:
        return "✅"
    if ok is False:
        return "❌"
    return "⚪"


def _print_results(
    symbol: str,
    vol: dict,
    broker: dict,
    price: dict,
    breakout_level: float,
    broker_threshold: float,
    vol_threshold: float,
    breakout_source: str = "",
):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    mkt = "🟢 MARKET OPEN" if _is_market_hours() else "🔴 MARKET CLOSED — using today's completed bar"

    print(f"\n{'═' * 62}")
    print(f"  📊 ENTRY CONFIRMATION CHECK — {symbol}")
    print(f"  {now_str}  |  {mkt}")
    print(f"{'═' * 62}")

    # ── Trigger 1: Volume ──────────────────────────────────────────
    print(f"\n  TRIGGER 1 — Volume Spike  {_tick(vol.get('ok'))}")
    print(f"  {'─' * 58}")
    if vol.get("error"):
        print(f"  ⚠️  Error: {vol['error']}")
    else:
        vr = vol.get("volume_ratio", 0)
        avg = vol.get("avg_volume", 0)
        today = vol.get("today_volume")
        pct = vr * 100
        bar_filled = min(int(vr * 5), 15)  # bar scale: 2.0x = full
        status = "PASS — volume confirmed" if vol.get("ok") else f"WAIT — need ≥{vol_threshold:.1f}x average"
        print(f"  Today vs 20-day avg:  {vr:.2f}x  [{_bar(bar_filled, 15)}]")
        print(f"  20-day avg volume:    {avg:,.0f} shares")
        if today:
            print(f"  Today's volume:       {today:,.0f} shares  ({pct:.0f}% of average)")
        print(f"  Threshold:            {vol_threshold:.1f}x  →  {status}")

        if vol.get("ltp"):
            chg = vol.get("change_pct") or 0
            chg_icon = "🟢" if chg > 0 else "🔴" if chg < 0 else "⚪"
            print(f"  LTP:                  Rs. {vol['ltp']:,.2f}  {chg_icon} {chg:+.2f}%")

    # ── Trigger 2: Broker flip ──────────────────────────────────────
    print(f"\n  TRIGGER 2 — Broker Flip (Today's Floorsheet)  {_tick(broker.get('ok'))}")
    print(f"  {'─' * 58}")
    if broker.get("error"):
        print(f"  ⚠️  Error: {broker['error']}")
        if "token" in broker["error"].lower():
            print(f"  → Set SHAREHUB_AUTH_TOKEN in .env to enable this check")
            print(f"     How-to: chrome → sharehub.com → F12 → Network → any request")
            print(f"             → Headers → Authorization: Bearer <paste here>")
    else:
        threshold_l = broker_threshold / 100_000
        top3_l = broker.get("top3_net_rs", 0) / 100_000
        all_l = broker.get("all_net_rs", 0) / 100_000
        status = "PASS — brokers accumulating" if broker.get("ok") else f"WAIT — need top-3 net > Rs.{threshold_l:.1f}L"
        print(f"  Top-3 net today:      Rs. {top3_l:+.2f}L  →  {status}")
        print(f"  All brokers net:      Rs. {all_l:+.2f}L  ({broker.get('all_brokers',0)} brokers)")
        print()
        print(f"  {'Code':<8} {'Broker':<30} {'Net Qty':>9} {'Net Rs.':>12}")
        print(f"  {'─'*7} {'─'*30} {'─'*9} {'─'*12}")
        for b in broker.get("top3", []):
            net_rs_l = b["net_rs"] / 100_000
            icon = "🟢" if b["net_rs"] > 0 else "🔴"
            print(f"  {icon} {b['code']:<6}  {b['name']:<30} {b['net_qty']:>+9,} {net_rs_l:>+11.2f}L")

    # ── Trigger 3: Price ────────────────────────────────────────────
    src_label = f"  ({breakout_source})" if breakout_source and breakout_source != "user-supplied" else ""
    print(f"\n  TRIGGER 3 — Price Above Rs.{breakout_level:.0f}  {_tick(price.get('ok'))}")
    if src_label:
        print(f"  📍 Source: {breakout_source}")
    print(f"  {'─' * 58}")
    if price.get("error"):
        print(f"  ⚠️  Error: {price['error']}")
    else:
        ltp = price.get("ltp", 0)
        diff = ltp - breakout_level
        diff_pct = (diff / breakout_level * 100) if breakout_level else 0
        above_icon = "✅" if price.get("above_level") else "❌"
        print(f"  LTP:                  Rs. {ltp:,.2f}  ({diff:+.2f}, {diff_pct:+.1f}% vs Rs.{breakout_level:.0f})")
        print(f"  Above breakout level: {above_icon}")

        if price.get("intraday_available"):
            m15c = price.get("last_15m_close")
            m15g = price.get("last_15m_green")
            m15a = price.get("last_15m_above_level")
            g_icon = "🟢 Green" if m15g else "🔴 Red"
            a_icon = "✅" if m15a else "❌"
            src_tag = "🔴 LIVE" if price.get("live_1min_active") else "📊 hist"
            print(f"  Last 15m candle:      Rs. {m15c:,.2f}  {g_icon}  [{src_tag}]")
            print(f"  15m above Rs.{breakout_level:.0f}:     {a_icon}")
        else:
            print(f"  15m intraday:         ⚪ Not available (market closed)")
            print(f"                        Re-run during market hours for full check")

    # ── 3-Timeframe Confluence ─────────────────────────────────────
    tf = price.get("tf_data") or {}
    if tf:
        print(f"\n{'═' * 62}")
        print(f"  🔬 3-TIMEFRAME CONFLUENCE")
        print(f"{'─' * 62}")

        # 1D
        d_bias = tf.get("daily_bias", "")
        d_rsi = tf.get("daily_rsi")
        d_trend = tf.get("daily_trend", "")
        d_macd = tf.get("daily_macd_bull")
        d_icon = "🟢" if "LONG" in d_bias else "🔴"
        d_macd_str = "MACD ✅" if d_macd else "MACD ❌"
        d_rsi_str = f"RSI {d_rsi}" if d_rsi else "RSI —"
        print(f"  1D  BIAS:     {d_icon} {d_bias:<6} — {d_trend} | {d_rsi_str} | {d_macd_str}")

        # 1H
        h1_bars = tf.get("h1_bars_count", 0)
        if h1_bars >= 1:
            h1_green = tf.get("h1_green")
            h1_trend = tf.get("h1_trend", "")
            h1_rsi = tf.get("h1_rsi")
            h1_candle = "🟢 Green" if h1_green else "🔴 Red"
            h1_rsi_str = f"RSI {h1_rsi}" if h1_rsi else "RSI —"
            if h1_green and h1_trend == "UP":
                h1_icon, h1_label = "🟢", "ALIGNED"
            elif h1_green is False or h1_trend == "DOWN":
                h1_icon, h1_label = "🔴", "WEAK"
            else:
                h1_icon, h1_label = "🟡", "WATCH"
            h1_trend_str = f"trend {h1_trend}" if h1_trend else "trend —"
            h1_vol_ratio = tf.get("h1_vol_ratio")
            h1_vol_ok = tf.get("h1_vol_above_avg")
            h1_vol_str = (f"Vol {h1_vol_ratio:.1f}x {'✅' if h1_vol_ok else '⚠️'}" if h1_vol_ratio else "Vol —")
            print(f"  1H  ZONE:     {h1_icon} {h1_label:<8} — {h1_candle} | {h1_trend_str} | {h1_vol_str} | {h1_rsi_str}  ({h1_bars} bars)")
        else:
            print(f"  1H  ZONE:     ⚪ NO DATA (need ShareHub live bars)")

        # 15m
        m15_bars = tf.get("m15_bars_count", 0)
        if m15_bars >= 2:
            m15_green = tf.get("m15_green")
            m15_rsi = tf.get("m15_rsi")
            m15_vol = tf.get("m15_vol_ratio")
            m15_vol_ok = tf.get("m15_vol_above_avg")
            m15_candle = "🟢 Green" if m15_green else "🔴 Red"
            m15_rsi_str = f"RSI {m15_rsi}" if m15_rsi else "RSI —"
            m15_vol_str = f"Vol {m15_vol:.1f}x" if m15_vol else "Vol —"
            if m15_green and m15_vol_ok:
                m15_icon, m15_label = "🟢", "TRIGGER ✅"
            elif m15_green:
                m15_icon, m15_label = "🟡", "PARTIAL  "
            else:
                m15_icon, m15_label = "🔴", "NOT YET  "
            vol_note = " (vol weak ⚠️)" if m15_green and not m15_vol_ok else ""
            print(f"  15m TRIGGER:  {m15_icon} {m15_label} — {m15_candle} | {m15_vol_str}{vol_note} | {m15_rsi_str}  ({m15_bars} bars)")
        else:
            print(f"  15m TRIGGER:  ⚪ NO DATA (need market hours + live bars)")

        # Score summary
        score = tf.get("confluence_score", 0)
        if score == 3:
            cf_label = "🟢 FULL CONFLUENCE — conditions met, ready to act"
        elif score == 2:
            cf_label = "🟡 PARTIAL — 2/3 aligned, watch remaining TF"
        elif score == 1:
            cf_label = "🔴 LOW — only 1/3 aligned, MONITOR only"
        else:
            cf_label = "🔴 NONE — all TFs misaligned, stand aside"
        print(f"  {'─' * 58}")
        print(f"  Confluence:   {score}/3  →  {cf_label}")

    # ── Summary ────────────────────────────────────────────────────
    results = [vol.get("ok"), broker.get("ok"), price.get("ok")]
    confirmed = [r for r in results if r is True]
    available = [r for r in results if r is not None]
    n_confirmed = len(confirmed)
    n_available = len(available)

    print(f"\n{'═' * 62}")
    print(f"  SUMMARY: {n_confirmed}/{n_available} triggers confirmed")
    print(f"{'─' * 62}")

    if n_confirmed >= 2:
        print(f"  🟢 GO  — {n_confirmed} triggers confirmed. Entry conditions met.")
        print(f"  → Place limit buy at Rs. {price.get('ltp', 0):,.0f}–{price.get('ltp', 0) + 3:,.0f}")
        print(f"  → Set stop-loss immediately at Rs. 385")
        print(f"  → Target: Rs. 487")
    elif n_confirmed == 1:
        unfired = []
        checks = [
            (vol.get("ok"), "volume ≥ 1.5x"),
            (broker.get("ok"), "broker net > threshold"),
            (price.get("ok"), f"price > Rs.{breakout_level:.0f} with green 15m"),
        ]
        for ok, label in checks:
            if ok is False:
                unfired.append(label)
        print(f"  🟡 NOT YET — 1 trigger confirmed. Wait for:")
        for u in unfired:
            print(f"      → {u}")
        print(f"  → Re-run this command in 30–60 minutes")
    else:
        print(f"  🔴 WAIT — No triggers confirmed yet.")
        print(f"  → Check again at 11:30 AM and 12:00 PM")

    print(f"{'═' * 62}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

async def _run(symbol: str, breakout_level: float, broker_threshold: float, vol_threshold: float,
              breakout_source: str = ""):
    print(f"\n  ⏳ Fetching live data for {symbol}...")

    # Run volume + price checks concurrently (both need aiohttp)
    vol_task = asyncio.create_task(check_volume(symbol, vol_threshold))
    price_task = asyncio.create_task(check_price_breakout(symbol, breakout_level))
    vol, price = await asyncio.gather(vol_task, price_task)

    # Broker is sync (ShareHub REST)
    print(f"  ⏳ Fetching broker floorsheet...")
    broker = check_broker_flip(symbol, broker_threshold)

    _print_results(symbol, vol, broker, price, breakout_level, broker_threshold, vol_threshold,
                   breakout_source=breakout_source)


def main():
    parser = argparse.ArgumentParser(
        description="Live entry confirmation: checks volume, broker flip, price breakout"
    )
    parser.add_argument("symbol", help="Stock symbol e.g. SGHC, NABIL")
    parser.add_argument(
        "--breakout-level", type=float, default=None,
        help="Price level to check breakout above (default: auto from LTP + 1.5%%)"
    )
    parser.add_argument(
        "--broker-threshold", type=float, default=500_000,
        help="Rs. threshold for top-3 broker net buying (default: 500000 = Rs. 5L)"
    )
    parser.add_argument(
        "--volume-threshold", type=float, default=1.5,
        help="Volume ratio threshold vs 20-day average (default: 1.5x)"
    )
    args = parser.parse_args()

    symbol = args.symbol.upper()
    vol_threshold = args.volume_threshold
    broker_threshold = args.broker_threshold

    # Breakout level: user-supplied or auto-detected from technical levels
    breakout_source = ""
    if args.breakout_level:
        breakout_level = args.breakout_level
        breakout_source = "user-supplied"
    else:
        # Auto-detect: nearest swing-high resistance → 52w high → LTP+1.5% fallback
        print(f"\n  ⏳ Auto-detecting breakout level for {symbol}...")
        async def _get_analysis():
            async with aiohttp.ClientSession() as s:
                b = await fetch_ohlcv(s, symbol, fsk=DEFAULT_FSK)
                return run_analysis(symbol, b) if b else None
        analysis = asyncio.run(_get_analysis()) if _HAS_SCREENER else None
        if analysis:
            ltp = analysis.get("current_price", 0)
            nearest_r = analysis.get("nearest_resistance")
            high_52w   = analysis.get("high_52w")
            r_dist = analysis.get("resistance_distance_pct") or 0
            bstatus = analysis.get("breakout_status", "")

            if nearest_r and nearest_r > ltp:
                breakout_level = nearest_r
                breakout_source = f"nearest swing-high resistance ({r_dist:+.1f}% above LTP)"
            elif high_52w and high_52w > ltp:
                breakout_level = high_52w
                breakout_source = f"52-week high ({round((high_52w - ltp) / ltp * 100, 1):+.1f}% above LTP, no swing resistance found)"
            else:
                breakout_level = round(ltp * 1.015, 1)
                breakout_source = f"LTP + 1.5% (price already above all computed resistance levels)"

            print(f"  📍 Breakout level: Rs. {breakout_level}  ({breakout_source})")
            if bstatus:
                print(f"  📊 Current status:  {bstatus}")
        else:
            print("  Could not auto-detect breakout level. Use --breakout-level explicitly.")
            sys.exit(1)

    asyncio.run(_run(symbol, breakout_level, broker_threshold, vol_threshold, breakout_source))


if __name__ == "__main__":
    main()
