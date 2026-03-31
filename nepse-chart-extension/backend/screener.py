"""
NEPSE Market Screener — Automated Stock Scanner
================================================
Fetches OHLCV data for all 269 NEPSE stocks from NepseAlpha,
runs the full analysis pipeline, applies the strict WIDGET_GUIDE
3-Timeframe rules, and outputs top 5 picks per sector.

Usage:
    python screener.py                  # Full scan, all sectors
    python screener.py --sector "Commercial Banks"  # One sector only
    python screener.py --top 10         # Top 10 per sector
    python screener.py --json           # JSON output (for API)

Architecture:
    1. Load stocks.json + sector_name.json
    2. Fetch 1D bars (1000 candles) for all stocks via NepseAlpha API (concurrent)
    3. Run full analysis per stock (reuses main.py pipeline)
    4. Score each stock against the 7-Point Checklist + 3-TF confluence
    5. Group by sector → rank → output top N per sector
"""

import asyncio
import json
import sys
import time
import os
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiohttp
import pandas as pd
import numpy as np

# ── Import analysis functions from the existing backend ──────────────
# This avoids duplicating 1800 lines of indicator/pattern/verdict logic.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from main import (
    _build_dataframe,
    _compute_indicators,
    _detect_patterns,
    _detect_operator_activity,
    _determine_trend,
    _generate_verdict,
    _compute_support_resistance,
    _calculate_stop_loss,
    _calculate_target,
    _compute_fibonacci,
    _compute_obv_trend,
    _compute_52w_range,
    _compute_ma_crossover,
    _multi_timeframe_analysis,
    _resample_ohlcv,
    _mini_analysis,
    _detect_breakout,
    _detect_market_structure,
    _detect_momentum_status,
    _detect_volume_profile,
    _detect_bb_position,
    _detect_rsi_divergence,
    _detect_market_phase,
    _compute_nearest_sr,
    _compute_signal_summaries,
    _summarize_signals,
    _overall_summary,
    CandleBar,
    TimeframeAnalysis,
)


# ─── Configuration ──────────────────────────────────────────────────

NEPSEALPHA_BASE = "https://nepsealpha.com/trading/1/history"
def _fsk() -> str:
    """NepseAlpha FSK = current Unix timestamp in milliseconds."""
    import time
    return str(int(time.time() * 1000))

DEFAULT_FSK = _fsk()  # module-level fallback; callers should use _fsk() directly
FRAME = 1000         # 1000 daily bars ≈ 4 years
INTRADAY_FRAME = 1000  # 1000 1-min bars ≈ 4 NEPSE days (1H: ~16 bars, 15m: ~66 bars)
MAX_CONCURRENT = 12  # parallel HTTP requests
REQUEST_DELAY = 0.15  # seconds between batches (be polite)
TIMEOUT_SECONDS = 20  # per-request timeout

STOCKS_JSON = Path(__file__).resolve().parent.parent.parent / "details_stocks" / "stocks.json"
SECTOR_JSON = Path(__file__).resolve().parent.parent.parent / "details_stocks" / "sector_name.json"
NEPSE_AI_PATH = str(Path(__file__).resolve().parent.parent.parent / "nepse_ai_trading")
WATCHLIST_JSON = Path(__file__).resolve().parent / "watchlist.json"

import random

# 25 rotating user-agents across Chrome/Firefox/Edge/Safari on Windows/Mac/Linux/Android/iOS
# Rotated per-request so each fetch looks like a different device/browser.
_USER_AGENTS = [
    # Chrome – Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Chrome – macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Chrome – Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    # Chrome – Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Redmi Note 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
    # Firefox – Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Firefox – macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:131.0) Gecko/20100101 Firefox/131.0",
    # Firefox – Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    # Firefox – Android
    "Mozilla/5.0 (Android 14; Mobile; rv:131.0) Gecko/131.0 Firefox/131.0",
    # Edge – Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Edge – macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Safari – macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Safari – iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    # Opera – Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/116.0.0.0",
    # Brave – macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Brave/1.71",
    # Samsung Internet – Android
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/26.0 Chrome/122.0.0.0 Mobile Safari/537.36",
]

_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-US,en;q=0.8,ne;q=0.6",
    "en;q=0.9",
    "en-US,en;q=0.7,ne-NP;q=0.5",
]


def _random_headers() -> dict:
    """Return a fresh set of browser-like headers with a randomly chosen user-agent."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": random.choice(_ACCEPT_LANGUAGES),
        "Referer": "https://nepsealpha.com/trading/chart",
        "Origin": "https://nepsealpha.com",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

# ─── Data Fetcher ───────────────────────────────────────────────────

async def fetch_ohlcv(
    session: aiohttp.ClientSession,
    symbol: str,
    resolution: str = "1D",
    fsk: str = DEFAULT_FSK,
) -> Optional[list[dict]]:
    """Fetch OHLCV bars from NepseAlpha for one stock."""
    url = (
        f"{NEPSEALPHA_BASE}"
        f"?fsk={_fsk()}"
        f"&symbol={symbol}"
        f"&resolution={resolution}"
        f"&frame={FRAME}"
    )
    try:
        async with session.get(
            url,
            headers=_random_headers(),
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
            if not data or data.get("s") != "ok":
                return None
            # Convert TradingView UDF format → list of CandleBar dicts
            timestamps = data.get("t", [])
            opens = data.get("o", [])
            highs = data.get("h", [])
            lows = data.get("l", [])
            closes = data.get("c", [])
            volumes = data.get("v", [])
            n = len(timestamps)
            if n < 30:
                return None
            bars = []
            for i in range(n):
                bars.append({
                    "time": int(timestamps[i]),
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(closes[i]),
                    "volume": float(volumes[i]) if i < len(volumes) else 0.0,
                })
            return bars
    except Exception:
        return None


async def fetch_intraday_ohlcv(
    session: aiohttp.ClientSession,
    symbol: str,
    fsk: str = DEFAULT_FSK,
) -> Optional[list[dict]]:
    """Fetch 1-minute OHLCV bars for 1H + 15m intraday analysis.
    NepseAlpha only supports frame=1000 — gives ~4 trading days of 1-min bars
    (~16 hourly bars for trend/RSI, ~66 15-min bars for full indicators)."""
    url = (
        f"{NEPSEALPHA_BASE}"
        f"?fsk={_fsk()}"
        f"&symbol={symbol}"
        f"&resolution=1"
        f"&frame={INTRADAY_FRAME}"
    )
    try:
        async with session.get(
            url,
            headers=_random_headers(),
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json(content_type=None)
            if not data or data.get("s") != "ok":
                return None
            timestamps = data.get("t", [])
            opens = data.get("o", [])
            highs = data.get("h", [])
            lows = data.get("l", [])
            closes = data.get("c", [])
            volumes = data.get("v", [])
            n = len(timestamps)
            if n < 60:
                return None
            bars = []
            for i in range(n):
                bars.append({
                    "time": int(timestamps[i]),
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(closes[i]),
                    "volume": float(volumes[i]) if i < len(volumes) else 0.0,
                })
            return bars
    except Exception:
        return None


def analyze_intraday(bars: list[dict]) -> Optional[dict]:
    """Resample 1-min bars to 1H and 15m, run mini-analysis on each.
    Returns dict with hourly + 15m verdicts for WIDGET_GUIDE Step 2 & 3."""
    try:
        candle_bars = [CandleBar(**b) for b in bars]
        df_1min = _build_dataframe(candle_bars)
        if len(df_1min) < 60:
            return None

        current_price = float(df_1min["close"].iloc[-1])

        # Resample to 1H
        df_hourly = _resample_ohlcv(df_1min, "h")
        hourly_analysis = _mini_analysis(df_hourly) if len(df_hourly) >= 14 else None
        hourly_sma20 = (
            float(df_hourly["close"].rolling(20).mean().iloc[-1])
            if hourly_analysis and len(df_hourly) >= 20
            else None
        )

        # Resample to 15m
        df_15m = _resample_ohlcv(df_1min, "15min")
        analysis_15m = _mini_analysis(df_15m) if len(df_15m) >= 14 else None
        sma20_15m = (
            float(df_15m["close"].rolling(20).mean().iloc[-1])
            if analysis_15m and len(df_15m) >= 20
            else None
        )

        # Bullish pattern on 15m?
        bullish_pattern_15m = False
        if analysis_15m:
            for p in analysis_15m.get("patterns", []):
                if p.direction == "bullish":
                    bullish_pattern_15m = True
                    break

        # 15m volume ratio (last 15m bar vs 20-bar average) — WIDGET_GUIDE Step 3
        volume_ratio_15m = None
        if analysis_15m and len(df_15m) >= 20:
            vol_ma = df_15m["volume"].rolling(20).mean().iloc[-1]
            last_vol = df_15m["volume"].iloc[-1]
            if vol_ma > 0 and not pd.isna(vol_ma):
                volume_ratio_15m = round(float(last_vol) / float(vol_ma), 2)

        return {
            "current_price": current_price,
            "hourly": hourly_analysis,
            "hourly_sma20": hourly_sma20,
            "15m": analysis_15m,
            "sma20_15m": sma20_15m,
            "bullish_pattern_15m": bullish_pattern_15m,
            "volume_ratio_15m": volume_ratio_15m,
        }
    except Exception:
        return None


def compute_intraday_checks(intraday: Optional[dict]) -> dict:
    """Check WIDGET_GUIDE Section 7 Step 2 (1H zone) and Step 3 (15m trigger).
    Returns dict with hourly_zone_ok + intraday_trigger_ok booleans (None = no data)."""
    if not intraday:
        return {"hourly_zone_ok": None, "intraday_trigger_ok": None}

    # Step 2: 1H entry zone — trend ≠ DOWNTREND and RSI < 65
    # (1H MACD is stored for display but not a hard blocker per WIDGET_GUIDE "ideal" phrasing)
    hourly = intraday.get("hourly") or {}
    h_trend = hourly.get("trend", "UNKNOWN")
    h_rsi = hourly.get("rsi_14")
    h_macd = hourly.get("macd_signal")  # informational — shown in output
    hourly_zone_ok = (h_trend != "DOWNTREND") and (h_rsi is not None and h_rsi < 65)

    # Step 3: 15m trigger — ALL 4 conditions required (WIDGET_GUIDE Section 17 Step 3)
    m15 = intraday.get("15m") or {}
    m15_verdict = m15.get("verdict", "")
    m15_rsi = m15.get("rsi_14")
    sma20_15m = intraday.get("sma20_15m")
    current_price = intraday.get("current_price", 0)
    volume_ratio_15m = intraday.get("volume_ratio_15m")

    verdict_ok = m15_verdict in ("BUY", "STRONG BUY")
    rsi_ok = m15_rsi is not None and m15_rsi > 50
    above_sma20 = (sma20_15m is None) or (current_price >= sma20_15m * 0.99)
    bullish_pattern_ok = intraday.get("bullish_pattern_15m", False)  # required by WIDGET_GUIDE
    volume_ok_15m = volume_ratio_15m is not None and volume_ratio_15m >= 1.0  # required
    intraday_trigger_ok = verdict_ok and rsi_ok and above_sma20 and bullish_pattern_ok and volume_ok_15m

    return {
        "hourly_zone_ok": hourly_zone_ok,
        "intraday_trigger_ok": intraday_trigger_ok,
        "hourly_macd": h_macd,
        "volume_ratio_15m": volume_ratio_15m,
        "bullish_pattern_15m": bullish_pattern_ok,
    }


# ─── Full Analysis Pipeline (reuses main.py) ───────────────────────

def run_analysis(symbol: str, bars: list[dict], resolution: str = "1D") -> Optional[dict]:
    """Run the complete analysis pipeline on raw bars.
    Returns a flat dict with all key fields for scoring."""
    try:
        candle_bars = [CandleBar(**b) for b in bars]
        df = _build_dataframe(candle_bars)
        if len(df) < 30:
            return None

        indicators = _compute_indicators(df)
        patterns = _detect_patterns(df)
        operator_activity, volume_ratio = _detect_operator_activity(df)
        trend, trend_strength = _determine_trend(df, indicators)

        current_price = float(df["close"].iloc[-1])
        prev_close = float(df["close"].iloc[-2]) if len(df) > 1 else current_price
        price_change_pct = round(((current_price - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0

        atr_val = indicators.get("atr_14")
        support_levels, resistance_levels = _compute_support_resistance(df)
        suggested_sl = _calculate_stop_loss(current_price, atr_val, trend, support_levels)
        suggested_target = _calculate_target(current_price, suggested_sl, resistance_levels)
        _risk = abs(current_price - suggested_sl)
        _reward = abs(suggested_target - current_price)
        rr_ratio = round(_reward / _risk, 2) if _risk > 0 else 0.0
        obv_trend = _compute_obv_trend(df)
        high_52w, low_52w, pct_high, pct_low = _compute_52w_range(df, current_price)
        ma_crossover = _compute_ma_crossover(df)
        multi_tf = _multi_timeframe_analysis(df, resolution)

        # Enhanced
        breakout_status = _detect_breakout(df, current_price, resistance_levels, support_levels, volume_ratio, indicators)
        market_structure = _detect_market_structure(df)
        momentum_status = _detect_momentum_status(indicators)
        volume_profile = _detect_volume_profile(df)
        bb_position = _detect_bb_position(current_price, indicators)
        rsi_divergence = _detect_rsi_divergence(df)
        market_phase = _detect_market_phase(trend, volume_profile, indicators, market_structure)
        nearest_s, nearest_r, s_dist_pct, r_dist_pct = _compute_nearest_sr(current_price, support_levels, resistance_levels)
        volatility_pct = round(indicators["atr_14"] / current_price * 100, 2) if indicators.get("atr_14") and current_price > 0 else None

        oscillator_signals, ma_signals = _compute_signal_summaries(indicators, current_price)
        osc_summary = _summarize_signals(oscillator_signals)
        ma_summary_str = _summarize_signals(ma_signals)
        overall = _overall_summary(osc_summary, ma_summary_str)

        verdict, confidence = _generate_verdict(
            patterns=patterns, indicators=indicators,
            operator_activity=operator_activity, trend=trend,
            trend_strength=trend_strength, volume_ratio=volume_ratio,
            multi_tf=multi_tf,
        )

        vol_sma = df["volume"].rolling(20).mean().iloc[-1] if len(df) >= 20 else None
        avg_volume = round(float(vol_sma), 0) if vol_sma is not None and not pd.isna(vol_sma) else None

        # Multi-TF verdicts for composite scoring and output
        tf_verdict_map = {tf.timeframe: tf.verdict for tf in multi_tf}
        biweekly_verdict  = tf_verdict_map.get("Bi-Weekly")
        weekly_verdict    = tf_verdict_map.get("Weekly")
        monthly_verdict   = tf_verdict_map.get("Monthly")
        quarterly_verdict = tf_verdict_map.get("Quarterly")
        semi_yearly_verdict = tf_verdict_map.get("Semi-Yearly")
        yearly_verdict    = tf_verdict_map.get("Yearly")

        return {
            "symbol": symbol,
            "current_price": current_price,
            "price_change_pct": price_change_pct,
            "verdict": verdict,
            "confidence": confidence,
            "trend": trend,
            "trend_strength": trend_strength,
            "rsi_14": indicators.get("rsi_14"),
            "macd_signal": indicators.get("macd_signal"),
            "adx_14": indicators.get("adx_14"),
            "di_plus": indicators.get("di_plus"),
            "di_minus": indicators.get("di_minus"),
            "volume_ratio": round(volume_ratio, 2),
            "obv_trend": obv_trend,
            "rr_ratio": rr_ratio,
            "suggested_sl": round(suggested_sl, 2),
            "suggested_target": round(suggested_target, 2),
            "ma_crossover": ma_crossover,
            "sma_50": indicators.get("sma_50"),
            "sma_200": indicators.get("sma_200"),
            "ema_10": indicators.get("ema_10"),
            "ema_30": indicators.get("ema_30"),
            "bb_pct_b": indicators.get("bb_pct_b"),
            "breakout_status": breakout_status,
            "market_structure": market_structure,
            "momentum_status": momentum_status,
            "volume_profile": volume_profile,
            "rsi_divergence": rsi_divergence,
            "market_phase": market_phase,
            "bb_position": bb_position,
            "nearest_support": nearest_s,
            "nearest_resistance": nearest_r,
            "support_distance_pct": s_dist_pct,
            "resistance_distance_pct": r_dist_pct,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "pct_from_52w_high": pct_high,
            "pct_from_52w_low": pct_low,
            "avg_volume": avg_volume,
            "volatility_pct": volatility_pct,
            "patterns": [{"name": p.name, "direction": p.direction, "strength": p.strength} for p in patterns],
            "oscillator_summary": osc_summary,
            "ma_summary": ma_summary_str,
            "overall_summary": overall,
            "biweekly_verdict":    biweekly_verdict,
            "weekly_verdict":      weekly_verdict,
            "monthly_verdict":     monthly_verdict,
            "quarterly_verdict":   quarterly_verdict,
            "semi_yearly_verdict": semi_yearly_verdict,
            "yearly_verdict":      yearly_verdict,
            "multi_tf": [
                {"timeframe": tf.timeframe, "verdict": tf.verdict, "confidence": tf.confidence,
                 "rsi_14": tf.rsi_14, "macd_signal": tf.macd_signal, "trend": tf.trend}
                for tf in multi_tf
            ],
        }
    except Exception as e:
        return None


# ─── 7-Point Checklist Scorer (from WIDGET_GUIDE) ──────────────────

def compute_checklist_score(result: dict) -> dict:
    """Apply the strict WIDGET_GUIDE 13-Point Buy Checklist (Section 17, Steps 1 + 4).
    Returns individual check results + total score out of max_score=13."""
    checks = {}
    max_score = 13

    rsi = result.get("rsi_14")
    price = result.get("current_price", 0)

    # 1. Verdict = BUY or STRONG BUY
    checks["verdict_buy"] = result["verdict"] in ("BUY", "STRONG BUY")

    # 2. Trend = UPTREND + ADX > 20 + EMA10 > EMA30
    ema10 = result.get("ema_10") or 0
    ema30 = result.get("ema_30") or 0
    checks["trend_confirmed"] = (
        result.get("trend") == "UPTREND"
        and result.get("adx_14") is not None
        and result["adx_14"] > 20
        and ema10 > ema30
    )

    # 3. RSI between 40–70 (not overbought, has room to run — WIDGET_GUIDE Step 1)
    checks["rsi_safe"] = rsi is not None and 40 <= rsi <= 70

    # 4. Price above SMA50 (medium-term structural bull)
    sma50 = result.get("sma_50")
    checks["price_above_sma50"] = sma50 is not None and price > sma50

    # 5. MACD Bullish (momentum confirming)
    checks["macd_bullish"] = result.get("macd_signal") == "Bullish"

    # 6. Multi-TF Aligned: majority of the 6 higher TFs = BUY
    all_tf_verdicts = [
        result["verdict"],
        result.get("biweekly_verdict"),
        result.get("weekly_verdict"),
        result.get("monthly_verdict"),
        result.get("quarterly_verdict"),
        result.get("semi_yearly_verdict"),
        result.get("yearly_verdict"),
    ]
    tf_buy_count = sum(1 for v in all_tf_verdicts if v in ("BUY", "STRONG BUY"))
    tf_total     = sum(1 for v in all_tf_verdicts if v is not None)
    checks["multi_tf_aligned"] = tf_total > 0 and tf_buy_count / tf_total >= 0.5

    # 7. No red flags: no Death Cross, no RSI >= 80, no bearish RSI divergence
    has_death_cross = result.get("ma_crossover") == "Death Cross"
    has_extreme_rsi = rsi is not None and rsi >= 80
    has_bearish_div = result.get("rsi_divergence") and "Bearish" in str(result.get("rsi_divergence", ""))
    checks["no_red_flags"] = not (has_death_cross or has_extreme_rsi or has_bearish_div)

    # 8. Volume confirmed: volume_ratio >= 1.2
    volume_ratio = result.get("volume_ratio", 0) or 0
    checks["volume_confirmed"] = volume_ratio >= 1.2

    # 9. Entry timing: near support (≤ 8%) OR confirmed bullish breakout
    s_dist = result.get("support_distance_pct")
    breakout = result.get("breakout_status", "") or ""
    confirmed_breakout = "Bullish Breakout" in str(breakout)
    near_support = s_dist is not None and s_dist <= 8.0
    checks["entry_timing"] = near_support or confirmed_breakout

    # 10. Wyckoff phase = Accumulation or Markup (Section 17 Step 1)
    phase = result.get("market_phase", "") or ""
    checks["wyckoff_favorable"] = "Accumulation" in str(phase) or "Markup" in str(phase)

    # 11. No operator distribution warning
    vol_profile = result.get("volume_profile", "") or ""
    checks["no_operator_distribution"] = "Distribution" not in str(vol_profile)

    # 12. Not chasing 52-week top (pct_from_52w_high: negative = above 52w high; positive = below)
    #     Dangerous: 0 < pct_high <= 5.0 → approaching resistance without confirmed breakout
    pct_high = result.get("pct_from_52w_high")
    if pct_high is None or pct_high <= 0:
        # No data OR price above 52w high (confirmed breakout territory) → safe
        checks["not_chasing_52w_top"] = True
    else:
        # pct_high > 0 means price is below 52w high by that percentage
        dangerous = 0 < pct_high <= 5.0
        checks["not_chasing_52w_top"] = not dangerous or confirmed_breakout

    # 13. R:R ratio >= 1.5 — WIDGET_GUIDE Step 4: "Never take a trade where R:R < 1.5"
    rr = result.get("rr_ratio", 0) or 0
    checks["rr_ratio_ok"] = rr >= 1.5

    score = sum(1 for k, v in checks.items() if k not in ("total_score", "max_score") and v is True)
    checks["total_score"] = score
    checks["max_score"] = max_score
    return checks


def compute_composite_score(result: dict, checklist: dict) -> float:
    """Compute a composite ranking score (0–100) for sorting stocks.
    Combines: checklist score, confidence, trend quality, momentum, R:R."""
    score = 0.0

    # 12-point checklist × 3 pts each = 36 max
    score += checklist["total_score"] * 3.0

    # Confidence (0-95) → scaled (0-19 pts)
    score += (result.get("confidence", 0) / 95.0) * 19.0

    # Trend quality (0-10 pts)
    if result.get("trend") == "UPTREND":
        score += 5.0
        adx = result.get("adx_14", 0) or 0
        if adx > 25:
            score += 3.0
        elif adx > 20:
            score += 1.5
        # DI+ > DI-
        di_plus = result.get("di_plus", 0) or 0
        di_minus = result.get("di_minus", 0) or 0
        if di_plus > di_minus:
            score += 1.5

    # RSI quality (0-8 pts): sweet spot 35-55
    rsi = result.get("rsi_14")
    if rsi is not None:
        if 35 <= rsi <= 55:
            score += 8.0  # Perfect zone
        elif 30 <= rsi < 35 or 55 < rsi <= 65:
            score += 5.0  # Acceptable
        elif 25 <= rsi < 30:
            score += 3.0  # Oversold bounce potential
        elif rsi > 70:
            score -= 5.0  # Overbought penalty

    # Momentum status (0-5 pts)
    momentum = result.get("momentum_status", "")
    if momentum and "Strong Bullish" in momentum:
        score += 5.0
    elif momentum and "Bullish" in momentum:
        score += 3.0
    elif momentum and "Bearish" in momentum:
        score -= 3.0

    # Market phase (0-5 pts)
    phase = result.get("market_phase", "")
    if phase and "Accumulation" in str(phase):
        score += 5.0  # Best phase to buy
    elif phase and "Markup" in str(phase):
        score += 3.0
    elif phase and "Distribution" in str(phase):
        score -= 5.0
    elif phase and "Markdown" in str(phase):
        score -= 8.0

    # Volume profile (0-4 pts)
    vol_profile = result.get("volume_profile", "")
    if vol_profile and "Accumulation" in str(vol_profile):
        score += 4.0
    elif vol_profile and "Distribution" in str(vol_profile):
        score -= 4.0

    # OBV trend (0-3 pts)
    if result.get("obv_trend") == "Rising":
        score += 3.0
    elif result.get("obv_trend") == "Falling":
        score -= 2.0

    # Risk:Reward (0-5 pts)
    rr = result.get("rr_ratio", 0) or 0
    if rr >= 3.0:
        score += 5.0
    elif rr >= 2.0:
        score += 3.0
    elif rr >= 1.5:
        score += 1.0
    elif rr < 1.0:
        score -= 2.0

    # Market structure bonus (0-3 pts)
    structure = result.get("market_structure", "")
    if structure and "HH/HL" in str(structure):
        score += 3.0
    elif structure and "LH/LL" in str(structure):
        score -= 3.0

    # Breakout bonus (0-3 pts)
    breakout = result.get("breakout_status", "")
    if breakout and "Bullish Breakout" in str(breakout):
        score += 3.0
    elif breakout and "Bearish Breakdown" in str(breakout):
        score -= 3.0

    # Multi-TF alignment bonus — all 6 higher TFs, ±1.5 pts each (max ±9 pts)
    # Longer timeframes carry more weight (Quarterly=2, Semi-Yearly=2.5, Yearly=3)
    tf_weights = [
        ("biweekly_verdict",    1.0),
        ("weekly_verdict",      1.5),
        ("monthly_verdict",     1.5),
        ("quarterly_verdict",   2.0),
        ("semi_yearly_verdict", 2.5),
        ("yearly_verdict",      3.0),
    ]
    for key, weight in tf_weights:
        v = result.get(key, "")
        if v in ("BUY", "STRONG BUY"):
            score += weight
        elif v in ("SELL", "STRONG SELL"):
            score -= weight

    # Golden Cross bonus
    if result.get("ma_crossover") == "Golden Cross":
        score += 2.0
    elif result.get("ma_crossover") == "Death Cross":
        score -= 4.0

    # Bullish candlestick pattern bonus
    for p in result.get("patterns", []):
        if p.get("direction") == "bullish" and p.get("strength", 0) >= 200:
            score += 2.0
            break  # Only count one

    return round(max(score, 0), 1)


# ─── Watchlist Persistence ─────────────────────────────────────────

def save_watchlist(scan_result: dict):
    """Save all top-N candidates to watchlist.json so `monitor` can track them."""
    stocks = []
    seen: set = set()
    for sec_name, sec_stocks in scan_result.get("sectors", {}).items():
        for s in sec_stocks:
            sym = s["symbol"]
            if sym in seen:
                continue
            seen.add(sym)
            stocks.append({
                "symbol":          sym,
                "company_name":    s.get("company_name", sym),
                "sector":          s.get("sector", sec_name),
                "current_price":   s["current_price"],
                "suggested_sl":    s.get("suggested_sl", 0),
                "suggested_target": s.get("suggested_target", 0),
                "rr_ratio":        s.get("rr_ratio", 0),
                "checklist_score": s.get("checklist_score", 0),
                "entry_status":    s.get("entry_status", "DAILY ONLY"),
                "composite_score": s.get("composite_score", 0),
            })
    stocks.sort(key=lambda x: (x["checklist_score"], x["composite_score"]), reverse=True)
    data = {
        "saved_at":      scan_result.get("scan_time", datetime.now(timezone.utc).isoformat()),
        "total_scanned": scan_result.get("total_scanned", 0),
        "stocks":        stocks,
    }
    with open(WATCHLIST_JSON, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  📋 Watchlist saved: {len(stocks)} stocks → Run `monitor` to track them live.\n")


# ─── Expert 4-Pillar Enrichment ────────────────────────────────────

def enrich_expert(result: dict) -> dict:
    """
    Phase 3 — Expert Intelligence Layer.

    Adds 4-Pillar MasterStockScreener analysis to shortlisted TA candidates:
      Pillar 1: Broker/Smart-Money (30%)
      Pillar 2: Unlock/Lock-up Risk (20%)
      Pillar 3: Fundamental Safety PE/EPS/ROE (20%)
      Pillar 4: Technical & Momentum (30%)

    Also checks NEPSE market regime (BULL / BEAR / PANIC kill-switch).
    Bear market: flags high distribution / manipulation stocks to AVOID.
    Gracefully degrades — full TA output is preserved even if this fails.
    """
    if NEPSE_AI_PATH not in sys.path:
        sys.path.insert(0, NEPSE_AI_PATH)

    # Load .env from nepse_ai_trading (ShareHub token, OpenAI key, etc.)
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=Path(NEPSE_AI_PATH) / ".env", override=True)
    except Exception:
        pass

    try:
        from analysis.master_screener import MasterStockScreener
    except ImportError as e:
        print(f"  ⚠️  Expert mode unavailable (import failed): {e}")
        result["market_regime"] = "UNKNOWN"
        return result

    print(f"\n{'='*70}")
    print(f"  🧠 EXPERT INTELLIGENCE — 4-Pillar MasterStockScreener")
    print(f"  Broker(30%) + Unlock(20%) + Fundamental(20%) + Technical(30%)")
    print(f"{'='*70}")

    try:
        ms = MasterStockScreener(strategy="value")  # replaced below after sector detection

        # ── Step 1: Market Regime (BULL / BEAR / PANIC) ──────────────
        print(f"  Checking NEPSE market regime...")
        regime, regime_reason = ms.check_market_regime()
        result["market_regime"] = regime
        result["market_regime_reason"] = regime_reason

        if regime == "PANIC":
            print(f"\n  🚨 {'─'*60}")
            print(f"  🚨  KILL SWITCH: PANIC MODE ACTIVE")
            print(f"  🚨  {regime_reason}")
            print(f"  🚨  DO NOT TRADE TODAY. No buy signals generated.")
            print(f"  🚨 {'─'*60}\n")
            return result

        regime_icon = "🐻" if regime == "BEAR" else "🐂"
        print(f"  {regime_icon}  Regime: {regime} — {regime_reason}")

        # ── Step 2: Collect TA candidates (checklist ≥ 7/13) ─────────
        candidates = []
        for sec_stocks in result["sectors"].values():
            for s in sec_stocks:
                if s.get("checklist_score", 0) >= 7:
                    candidates.append(s)

        if not candidates:
            print(f"  ℹ️   No candidates with daily score ≥ 7/13 to enrich.")
            return result

        # ── Auto-detect strategy: Hydro → momentum, everything else → value ──
        # Hydro stocks are driven by broker accumulation + technical momentum
        # (water doesn't stop flowing — earnings are stable, so PE/ROE matter less).
        # Bear market -15 penalty still applies for all strategies (correct risk mgmt).
        sector_counts: dict = {}
        for s in candidates:
            sec = s.get("sector", "").lower()
            sector_counts[sec] = sector_counts.get(sec, 0) + 1
        dominant_sector = max(sector_counts, key=sector_counts.get) if sector_counts else ""
        is_hydro_scan = any(kw in dominant_sector for kw in ("hydro", "power"))
        expert_strategy = "momentum" if is_hydro_scan else "value"
        if is_hydro_scan:
            print(f"  ⚡  Hydro-dominant scan → using MOMENTUM strategy (Pillar4=40pts, Pillar3=10pts)")

        # ── Step 3: Re-init with correct strategy, then pre-load ─────
        ms.strategy = expert_strategy  # apply detected strategy before scoring
        print(f"  Loading broker/unlock/fundamental data for all stocks...")
        ms._preload_market_data()  # player_favorites, unlock_risks, broker_accumulation

        print(f"  Running 4-Pillar scoring on {len(candidates)} shortlisted stocks...")

        for idx, s in enumerate(candidates, 1):
            symbol = s["symbol"]
            ltp = float(s["current_price"])
            print(f"\r    [{idx:2d}/{len(candidates)}] Scoring {symbol:<12}", end="", flush=True)

            # Pre-populate distribution risk cache BEFORE _score_stock reads it
            try:
                holdings_1d = ms._broker_accumulation.get(symbol, {})
                ms._calculate_distribution_risk(symbol, ltp, holdings_1d, {})
            except Exception:
                pass

            market_row = {
                "symbol": symbol,
                "securityName": s.get("company_name", symbol),
                "sectorName": s.get("sector", ""),
                "lastTradedPrice": ltp,
                "totalTradeQuantity": 0,
            }

            try:
                screened = ms._score_stock(market_row)
                if screened is None:
                    continue

                op_phase   = str(getattr(screened, "operator_phase", "UNKNOWN") or "UNKNOWN")
                manip_sev  = str(getattr(screened, "manipulation_severity", "NONE") or "NONE")
                dist_risk  = str(getattr(screened, "distribution_risk", "N/A") or "N/A")
                days_unlock = int(getattr(screened, "days_until_unlock", 999) or 999)

                s["expert"] = {
                    "master_score":          round(screened.total_score, 1),
                    "pillar1_broker":        round(screened.pillar1_broker, 1),
                    "pillar2_unlock":        round(screened.pillar2_unlock, 1),
                    "pillar3_fundamental":   round(screened.pillar3_fundamental, 1),
                    "pillar4_technical":     round(screened.pillar4_technical, 1),
                    "strategy":              expert_strategy,
                    "distribution_risk":     dist_risk,
                    "distribution_warning":  str(getattr(screened, "distribution_warning", "") or ""),
                    "operator_phase":        op_phase,
                    "is_safe_to_trade":      bool(getattr(screened, "is_safe_to_trade", True)),
                    "manipulation_severity": manip_sev,
                    "pe_ratio":              float(getattr(screened, "pe_ratio", 0) or 0),
                    "eps":                   float(getattr(screened, "eps", 0) or 0),
                    "roe":                   float(getattr(screened, "roe", 0) or 0),
                    "pbv":                   float(getattr(screened, "pbv", 0) or 0),
                    "winner":                str(getattr(screened, "winner", "") or "—"),
                    "buyer_dominance_pct":   float(getattr(screened, "buyer_dominance_pct", 0) or 0),
                    "is_bear_market":        bool(getattr(screened, "is_bear_market", False)),
                    "days_until_unlock":     days_unlock,
                    "unlock_type":           str(getattr(screened, "unlock_type", "None") or "None"),
                    "locked_percentage":     float(getattr(screened, "locked_percentage", 0) or 0),
                    "broker_profit_pct":     float(getattr(screened, "broker_profit_pct", 0) or 0),
                    "hard_reject":           None,
                }

                # Hard reject rules (ordered by severity)
                if dist_risk == "CRITICAL":
                    s["expert"]["hard_reject"] = "🚨 CRITICAL DISTRIBUTION — Operators actively dumping"
                elif manip_sev in ("HIGH", "CRITICAL"):
                    s["expert"]["hard_reject"] = f"⚠️  {manip_sev} MANIPULATION RISK — Avoid"
                elif 0 < days_unlock <= 30:
                    pct_locked = s["expert"]["locked_percentage"]
                    s["expert"]["hard_reject"] = f"⚠️  UNLOCK IN {days_unlock}d — {pct_locked:.0f}% shares will unlock"

            except Exception:
                pass  # Per-stock failure — TA output is still preserved

        print(f"\n  ✅ Expert enrichment complete.\n")

    except Exception as e:
        print(f"\n  ⚠️  Expert enrichment failed: {e}")
        result.setdefault("market_regime", "UNKNOWN")

    return result


# ─── Main Scanner ───────────────────────────────────────────────────

_LIVE_CURL_HEADERS = [
    "-H", "accept: application/json",
    "-H", "origin: https://nepsealpha.com",
    "-H", "referer: https://nepsealpha.com/",
    "-H", "user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
]


def _is_market_hours() -> bool:
    """Return True if NEPSE market is currently open (05:15–09:15 UTC, Sun–Thu)."""
    utc = datetime.now(timezone.utc)
    # NEPSE trades Sun–Thu; Fri and Sat are weekend
    if utc.weekday() in (4, 5):  # Friday=4, Saturday=5 in Python (Mon=0)
        return False
    market_open  = utc.replace(hour=5,  minute=15, second=0, microsecond=0)
    market_close = utc.replace(hour=9,  minute=15, second=0, microsecond=0)
    return market_open <= utc <= market_close


def _fetch_today_bars_bulk(symbols: list[str]) -> dict[str, dict]:
    """Fetch today's live OHLCV for all symbols via live.nepsealpha.com/lv_data.

    Uses subprocess curl (Cloudflare-safe) with concurrent workers.
    Returns {symbol: {open, high, low, close, vol}} for stocks trading today.
    Falls back gracefully — missing symbols simply won't get today's bar injected.
    """
    import subprocess
    import concurrent.futures as _cf

    # fs param: any value works — using a fixed placeholder
    _fs = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "0000"

    def _fetch_one(sym):
        url = (
            f"https://live.nepsealpha.com/lv_data"
            f"?symbol={sym}&resolution=1D&fs={_fs}&tck=pass"
        )
        try:
            r = subprocess.run(
                ["curl", "-s", "-k", url] + _LIVE_CURL_HEADERS,
                capture_output=True, text=True, timeout=8,
            )
            d = json.loads(r.stdout)
            ts = d.get("t", [])
            c = d.get("c", [])
            if not ts or not c:
                return sym, None
            return sym, {
                "open":  float(d["o"][0]) if d.get("o") else None,
                "high":  float(d["h"][0]) if d.get("h") else None,
                "low":   float(d["l"][0]) if d.get("l") else None,
                "close": float(c[0]),
                "vol":   float(str(d["v"][0]).replace(",", "")) if d.get("v") else 0.0,
                "ts":    int(ts[0]),
            }
        except Exception:
            return sym, None

    result = {}
    with _cf.ThreadPoolExecutor(max_workers=12) as ex:
        for sym, data in ex.map(_fetch_one, symbols):
            if data:
                result[sym] = data
    return result


async def scan_all_stocks(
    sector_filter: Optional[str] = None,
    top_n: int = 5,
    fsk: str = DEFAULT_FSK,
) -> dict:
    """Scan all NEPSE stocks and return top picks per sector."""

    # Load stock universe
    with open(STOCKS_JSON) as f:
        all_stocks = json.load(f)

    equities = [
        s for s in all_stocks
        if s.get("instrumentType") == "Equity" and s.get("status") == "A"
    ]

    if sector_filter:
        equities = [s for s in equities if s.get("sectorName", "").lower() == sector_filter.lower()]

    total = len(equities)
    print(f"\n{'='*70}")
    print(f"  NEPSE MARKET SCREENER — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Scanning {total} stocks across {len(set(s.get('sectorName','') for s in equities))} sectors")
    print(f"{'='*70}\n")

    # ── Pre-fetch today's OHLCV ──────────────────────────────────────────
    # live.nepsealpha.com/lv_data only works during market hours (Cloudflare
    # blocks it after close).  After close, NepseAlpha history already
    # contains today's completed bar — no injection needed.
    all_symbols = [s["symbol"] for s in equities]
    if _is_market_hours():
        print(f"  Fetching today's live OHLCV for {total} stocks (market open)...", flush=True)
        today_ohlcv = await asyncio.get_event_loop().run_in_executor(
            None, _fetch_today_bars_bulk, all_symbols
        )
        print(f"  Got live bars for {len(today_ohlcv)}/{total} stocks.\n")
    else:
        today_ohlcv = {}
        print(f"  Market closed — NepseAlpha history includes today's completed bar.\n")

    # Fetch + Analyze concurrently
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    results = []
    fetched = 0
    failed = 0
    analyzed = 0

    async def process_stock(session: aiohttp.ClientSession, stock: dict):
        nonlocal fetched, failed, analyzed
        symbol = stock["symbol"]
        sector = stock.get("sectorName", "Unknown")

        async with semaphore:
            # Small delay to be respectful
            await asyncio.sleep(REQUEST_DELAY)
            bars = await fetch_ohlcv(session, symbol, "1D", fsk)

        if bars is None:
            failed += 1
            return None

        fetched += 1

        # ── Inject today's live bar if available ─────────────────────
        # NepseAlpha only has yesterday's close; append today's running
        # bar so RSI/MACD/trend/indicators all reflect live price action.
        td = today_ohlcv.get(symbol)
        if td and td.get("close") is not None:
            # Build today's bar timestamp in UTC (NepseAlpha daily bars are at 05:45 UTC = 11:30 NST)
            # Using UTC explicitly so this works correctly on NST machines (UTC+5:45)
            _utc = datetime.now(timezone.utc)
            today_ts = int(datetime(_utc.year, _utc.month, _utc.day, 5, 45, 0,
                                    tzinfo=timezone.utc).timestamp())
            # Only append if today is genuinely newer than last bar
            if today_ts > bars[-1]["time"]:
                bars = bars + [{
                    "time":   today_ts,
                    "open":   td["open"]  or bars[-1]["close"],
                    "high":   td["high"]  or td["close"],
                    "low":    td["low"]   or td["close"],
                    "close":  td["close"],
                    "volume": td["vol"],
                }]

        # Run analysis (CPU-bound, but fast enough inline)
        analysis = run_analysis(symbol, bars, "1D")
        if analysis is None:
            failed += 1
            return None

        analyzed += 1
        analysis["sector"] = sector
        analysis["company_name"] = stock.get("companyName", symbol)

        # Print progress
        pct = int((fetched + failed) / total * 100)
        print(f"\r  [{pct:3d}%] Analyzed: {analyzed} | Failed: {failed} | Current: {symbol:<10}", end="", flush=True)

        return analysis

    # Run all fetches — headers are rotated per-request inside fetch_ohlcv
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [process_stock(session, stock) for stock in equities]
        raw_results = await asyncio.gather(*tasks)

    results = [r for r in raw_results if r is not None]
    print(f"\n\n  Scan complete: {analyzed} stocks analyzed, {failed} failed\n")

    # Score and rank
    for r in results:
        checklist = compute_checklist_score(r)
        r["checklist"] = checklist
        r["checklist_score"] = checklist["total_score"]
        r["composite_score"] = compute_composite_score(r, checklist)
        r["entry_status"] = "DAILY ONLY"  # default before intraday

    # Phase 2: Intraday (1H + 15m) analysis for top daily candidates
    # Only candidates with daily checklist >= 9/13 (~69%) to avoid unnecessary API calls
    top_candidates = [r for r in results if r.get("checklist_score", 0) >= 9]
    if top_candidates:
        print(f"  Phase 2: 1H + 15m analysis for {len(top_candidates)} top candidates...")

        intraday_sem = asyncio.Semaphore(MAX_CONCURRENT)

        async def fetch_intraday_for(session: aiohttp.ClientSession, r: dict):
            symbol = r["symbol"]
            async with intraday_sem:
                await asyncio.sleep(REQUEST_DELAY)
                bars = await fetch_intraday_ohlcv(session, symbol, fsk)
            if bars:
                intraday_data = analyze_intraday(bars)
                r["intraday"] = intraday_data
                r["intraday_checks"] = compute_intraday_checks(intraday_data)
                h_ok = r["intraday_checks"].get("hourly_zone_ok")
                m15_ok = r["intraday_checks"].get("intraday_trigger_ok")
                if h_ok and m15_ok:
                    r["entry_status"] = "ENTRY READY"
                elif h_ok:
                    r["entry_status"] = "ENTRY ZONE"
                else:
                    r["entry_status"] = "WAIT"
            else:
                r["intraday"] = None
                r["intraday_checks"] = {}
                r["entry_status"] = "NO DATA"

        conn2 = aiohttp.TCPConnector(limit=MAX_CONCURRENT, ssl=False)
        async with aiohttp.ClientSession(connector=conn2) as sess2:
            await asyncio.gather(*[fetch_intraday_for(sess2, r) for r in top_candidates])
        print(f"  Intraday analysis complete.\n")

    # Group by sector
    sectors = {}
    for r in results:
        sec = r.get("sector", "Unknown")
        sectors.setdefault(sec, []).append(r)

    # Sort each sector by composite score (descending)
    output = {}
    for sec_name, stocks in sorted(sectors.items()):
        ranked = sorted(stocks, key=lambda x: x["composite_score"], reverse=True)
        output[sec_name] = ranked[:top_n]

    return {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "total_scanned": analyzed,
        "total_failed": failed,
        "top_n": top_n,
        "sectors": output,
    }


# ─── Pretty Print ──────────────────────────────────────────────────

def print_results(scan_result: dict):
    """Print a beautiful terminal report with full 3-TF analysis."""
    sectors = scan_result["sectors"]
    top_n = scan_result["top_n"]

    print(f"\n{'='*100}")
    print(f"  TOP {top_n} STOCKS PER SECTOR — WIDGET_GUIDE 3-Timeframe Rules")
    print(f"  Scanned: {scan_result['total_scanned']} stocks | {scan_result['scan_time'][:19]}")
    print(f"{'='*100}")

    # ── Market Regime Banner ─────────────────────────────────────────
    regime = scan_result.get("market_regime")
    regime_reason = scan_result.get("market_regime_reason", "")
    if regime:
        if regime == "PANIC":
            print(f"\n  🚨{'═'*96}🚨")
            print(f"  🚨  KILL SWITCH: PANIC MODE — DO NOT BUY ANYTHING TODAY")
            print(f"  🚨  {regime_reason}")
            print(f"  🚨{'═'*96}🚨\n")
        elif regime == "BEAR":
            print(f"\n  🐻  BEAR MARKET — {regime_reason}")
            print(f"      ↳ All scores penalized -15. Use tight stops. Reduce position sizes. Prefer VALUE stocks.\n")
        else:
            print(f"\n  🐂  BULL MARKET — {regime_reason}\n")
    # ────────────────────────────────────────────────────────────────

    for sec_name, stocks in sectors.items():
        print(f"\n{'─'*100}")
        print(f"  📊 {sec_name.upper()}")
        print(f"{'─'*100}")

        if not stocks:
            print("  No stocks with sufficient data in this sector.")
            continue

        # Header — includes Entry status column
        print(f"  {'Rank':<5} {'Symbol':<10} {'Price':>8} {'Verdict':<12} {'Conf':>5} {'Score':>6} "
              f"{'RSI':>5} {'Trend':<10} {'R:R':>5} {'Chk':>5} {'Entry':<12}")
        print(f"  {'─'*5} {'─'*10} {'─'*8} {'─'*12} {'─'*5} {'─'*6} "
              f"{'─'*5} {'─'*10} {'─'*5} {'─'*5} {'─'*12}")

        for i, s in enumerate(stocks, 1):
            verd = s["verdict"]
            if verd == "STRONG BUY":
                verd_display = "★ STR BUY"
            elif verd == "BUY":
                verd_display = "▲ BUY"
            elif verd == "HOLD":
                verd_display = "— HOLD"
            elif verd == "SELL":
                verd_display = "▼ SELL"
            else:
                verd_display = "✕ STR SELL"

            rsi_str = f"{s['rsi_14']:.0f}" if s.get("rsi_14") else "—"
            trend_s = s.get("trend", "—")[:9]
            rr_s = f"{s.get('rr_ratio', 0):.1f}"
            chk = f"{s.get('checklist_score', 0)}/13"
            entry = s.get("entry_status", "—")[:11]

            print(f"  {i:<5} {s['symbol']:<10} {s['current_price']:>8.1f} {verd_display:<12} "
                  f"{s['confidence']:>4}% {s['composite_score']:>5.1f} "
                  f"{rsi_str:>5} {trend_s:<10} {rr_s:>5} {chk:>5} {entry:<12}")

        # Show detailed analysis for the #1 stock
        best = stocks[0]
        chk = best.get("checklist", {})
        intraday_checks = best.get("intraday_checks", {})
        intraday = best.get("intraday")

        print(f"\n  🏆 Top Pick: {best['symbol']} ({best.get('company_name', '')})")
        print(f"     Price: Rs.{best['current_price']:.2f} | SL: Rs.{best['suggested_sl']:.2f} | "
              f"Target: Rs.{best['suggested_target']:.2f} | R:R {best.get('rr_ratio', 0):.1f}")

        # Entry Status Banner
        entry_st = best.get("entry_status", "—")
        if entry_st == "ENTRY READY":
            print(f"     🟢 ENTRY STATUS: ENTRY READY — All 3 timeframes aligned. Enter now.")
        elif entry_st == "ENTRY ZONE":
            print(f"     🟡 ENTRY STATUS: ENTRY ZONE — 1H ok, wait for 15m trigger.")
        elif entry_st == "WAIT":
            print(f"     🔴 ENTRY STATUS: WAIT — 1H not ready. Hold off.")
        else:
            print(f"     ⚪ ENTRY STATUS: {entry_st} (only daily analysis available)")

        # 13-Point Daily Checklist (WIDGET_GUIDE Section 17, Steps 1 + 4)
        print(f"     13-Point Daily Checklist (Section 17 Steps 1 + 4):")
        check_labels = {
            "verdict_buy":              "Verdict BUY/STRONG BUY",
            "trend_confirmed":          "Trend UPTREND + ADX>20 + EMA10>EMA30",
            "rsi_safe":                 "RSI 40–70 (not overbought, room to run)",
            "price_above_sma50":        "Price above SMA50 (structural bull)",
            "macd_bullish":             "MACD Bullish (momentum confirming)",
            "multi_tf_aligned":         "Multi-TF Aligned (majority of 7 TFs BUY)",
            "no_red_flags":             "No Death Cross / RSI 80+ / Bearish Div",
            "volume_confirmed":         "Volume confirmed (ratio ≥ 1.2)",
            "entry_timing":             "Entry timing (near support ≤8% OR breakout)",
            "wyckoff_favorable":        "Wyckoff phase = Accumulation or Markup",
            "no_operator_distribution": "No operator distribution warning",
            "not_chasing_52w_top":      "Not chasing 52w top (unless breakout)",
            "rr_ratio_ok":              "R:R ratio ≥ 1.5 (minimum viable trade)",
        }
        for key, label in check_labels.items():
            passed = chk.get(key, False)
            icon = "✅" if passed else "❌"
            print(f"       {icon} {label}")
        print(f"       SCORE: {chk.get('total_score', 0)}/13")

        # 1H + 15m analysis (WIDGET_GUIDE Section 7, Step 2 & 3)
        if intraday:
            hourly = intraday.get("hourly") or {}
            m15 = intraday.get("15m") or {}
            h_rsi = hourly.get("rsi_14")
            m15_rsi = m15.get("rsi_14")
            h_trend = hourly.get("trend", "—")
            m15_verdict = m15.get("verdict", "—")
            h_ok = intraday_checks.get("hourly_zone_ok")
            m15_ok = intraday_checks.get("intraday_trigger_ok")

            print(f"\n     Section 7 Step 2 — 1H Entry Zone:  ⚠ (prior session data — NepseAlpha streams after market close)")
            print(f"       {'✅' if h_ok else '❌'} 1H Trend: {h_trend} | "
                  f"1H RSI: {f'{h_rsi:.1f}' if h_rsi else '—'} | "
                  f"1H SMA20: Rs.{intraday.get('hourly_sma20') or 0:.2f}")
            print(f"       {'✅' if h_ok else '❌'} 1H zone {'OK — entry approaching' if h_ok else 'NOT ready — wait'}")

            h_macd_disp = intraday_checks.get("hourly_macd") or "—"
            print(f"       ℹ️  1H MACD: {h_macd_disp} (ideal: Bullish)")

            vol_r15 = intraday_checks.get("volume_ratio_15m")
            has_bullish_pat = intraday_checks.get("bullish_pattern_15m", False)
            print(f"\n     Section 7 Step 3 — 15m Entry Trigger (ALL 4 required):  ⚠ (prior session data)")
            print(f"       {'✅' if m15_ok else '❌'} 15m Verdict: {m15_verdict} | "
                  f"15m RSI: {f'{m15_rsi:.1f}' if m15_rsi else '—'} | "
                  f"15m SMA20: Rs.{intraday.get('sma20_15m') or 0:.2f}")
            print(f"       {'✅' if has_bullish_pat else '❌'} Bullish candlestick pattern on 15m")
            vol_r15_str = f"{vol_r15:.2f}x" if vol_r15 is not None else "—"
            print(f"       {'✅' if (vol_r15 is not None and vol_r15 >= 1.0) else '❌'} 15m volume: {vol_r15_str} (need ≥ 1.0x avg)")
            print(f"       {'✅' if m15_ok else '❌'} 15m trigger {'ACTIVE — enter at next candle open' if m15_ok else 'NOT triggered — wait'}")
        else:
            print(f"\n     ⚪ Intraday (1H/15m) data not available — check extension manually.")

        # Multi-TF overview
        def _v(key): return best.get(key) or "—"
        print(f"\n     Multi-TF: Daily={best['verdict']} | Wkly={_v('weekly_verdict')} | Bi-Wk={_v('biweekly_verdict')}"
              f" | Mon={_v('monthly_verdict')} | Qtr={_v('quarterly_verdict')}"
              f" | Semi-Yr={_v('semi_yearly_verdict')} | Yr={_v('yearly_verdict')}")
        print(f"     Structure: {best.get('market_structure', '—')} | Momentum: {best.get('momentum_status', '—')}")
        print(f"     Wyckoff: {(best.get('market_phase') or '—')[:40]}")
        print(f"     Volume Profile: {best.get('volume_profile', '—')} | OBV: {best.get('obv_trend', '—')}")
        if best.get("rsi_divergence"):
            print(f"     ⚠ RSI Divergence: {best['rsi_divergence']}")
        if best.get("ma_crossover") == "Death Cross":
            print(f"     ⚠ Death Cross active!")
        elif best.get("ma_crossover") == "Golden Cross":
            print(f"     ✅ Golden Cross active")

        # ── 4-Pillar Expert Intelligence ──────────────────────────────
        expert = best.get("expert")
        if expert:
            ms = expert.get("master_score", 0)
            bar = "█" * int(ms / 10) + "░" * (10 - int(ms / 10))
            print(f"\n     🧠 4-PILLAR EXPERT INTELLIGENCE  [{bar}]  {ms:.1f}/100")
            print(f"     {'─'*62}")

            hard_reject = expert.get("hard_reject")
            if hard_reject:
                print(f"     🚫 HARD REJECT: {hard_reject}")
                print(f"     ⛔  SKIP THIS STOCK — the risk/reward is unfavourable right now")

            p1 = expert.get("pillar1_broker", 0)
            p2 = expert.get("pillar2_unlock", 0)
            p3 = expert.get("pillar3_fundamental", 0)
            p4 = expert.get("pillar4_technical", 0)
            p4_max = 40 if expert.get("strategy") == "momentum" else 30
            p3_max = 10 if expert.get("strategy") == "momentum" else 20
            print(f"     Pillar 1 — Broker/Smart-Money : {p1:5.1f}/30")
            print(f"     Pillar 2 — Unlock/Lockup Risk : {p2:5.1f}/20")
            print(f"     Pillar 3 — Fundamentals       : {p3:5.1f}/{p3_max}")
            print(f"     Pillar 4 — Technical/Momentum : {p4:5.1f}/{p4_max}")

            pe  = expert.get("pe_ratio", 0) or 0
            eps = expert.get("eps", 0) or 0
            roe = expert.get("roe", 0) or 0
            pbv = expert.get("pbv", 0) or 0
            pe_str  = f"{pe:.1f}x"   if pe  > 0 else "N/A"
            eps_str = f"Rs.{eps:.2f}" if eps != 0 else "N/A"
            roe_str = f"{roe:.1f}%"  if roe > 0 else "N/A"
            pbv_str = f"{pbv:.2f}x"  if pbv > 0 else "N/A"
            print(f"\n     Fundamentals: PE {pe_str} | EPS {eps_str} | ROE {roe_str} | PBV {pbv_str}")

            dist_risk = expert.get("distribution_risk", "N/A")
            dist_icons = {"LOW": "✅", "MEDIUM": "🟡", "HIGH": "🔴", "CRITICAL": "🚨"}
            dist_icon = dist_icons.get(dist_risk, "⚪")
            broker_profit = expert.get("broker_profit_pct", 0)
            print(f"     Distribution Risk: {dist_icon} {dist_risk}  (brokers {broker_profit:+.1f}% above avg cost)")
            dist_warn = expert.get("distribution_warning", "")
            if dist_warn and len(dist_warn) > 4:
                print(f"     {dist_warn[:90]}")

            op_phase = expert.get("operator_phase", "UNKNOWN")
            winner   = expert.get("winner", "—")
            buyer_pct = expert.get("buyer_dominance_pct", 0) or 0
            manip    = expert.get("manipulation_severity", "NONE")
            winner_str = f"{winner} ({buyer_pct:.0f}% dominance)" if buyer_pct > 0 else winner
            print(f"     Operator Phase: {op_phase} | Broker Dominance: {winner_str}")
            if manip not in ("NONE", "LOW", ""):
                print(f"     ⚠️  Manipulation Risk: {manip}")

            days_unlock = expert.get("days_until_unlock", 999) or 999
            if 0 < days_unlock <= 90:
                pct_locked  = expert.get("locked_percentage", 0) or 0
                unlock_type = expert.get("unlock_type", "")
                print(f"     ⏳ Unlock Warning: {pct_locked:.0f}% {unlock_type} shares unlock in {days_unlock} days")
        # ─────────────────────────────────────────────────────────────

    # Overall best picks across all sectors
    all_stocks_flat = []
    for stks in sectors.values():
        all_stocks_flat.extend(stks)

    if all_stocks_flat:
        top_global = sorted(all_stocks_flat, key=lambda x: x["composite_score"], reverse=True)[:10]
        print(f"\n{'='*100}")
        print(f"  🌟 OVERALL TOP 10 — BEST BUY OPPORTUNITIES ACROSS ALL SECTORS")
        print(f"{'='*100}")
        print(f"  {'Rank':<5} {'Symbol':<10} {'Sector':<22} {'Verdict':<12} {'Conf':>5} {'Score':>6} "
              f"{'RSI':>5} {'R:R':>5} {'Chk':>5} {'Entry':<12}")
        print(f"  {'─'*5} {'─'*10} {'─'*22} {'─'*12} {'─'*5} {'─'*6} {'─'*5} {'─'*5} {'─'*5} {'─'*12}")

        for i, s in enumerate(top_global, 1):
            verd = s["verdict"]
            if verd == "STRONG BUY":
                verd_display = "★ STR BUY"
            elif verd == "BUY":
                verd_display = "▲ BUY"
            elif verd == "HOLD":
                verd_display = "— HOLD"
            elif verd == "SELL":
                verd_display = "▼ SELL"
            else:
                verd_display = "✕ STR SELL"
            rsi_str = f"{s['rsi_14']:.0f}" if s.get("rsi_14") else "—"
            rr_s = f"{s.get('rr_ratio', 0):.1f}"
            chk = f"{s.get('checklist_score', 0)}/13"
            sec = (s.get("sector", "—"))[:21]
            entry = s.get("entry_status", "—")[:11]
            print(f"  {i:<5} {s['symbol']:<10} {sec:<22} {verd_display:<12} "
                  f"{s['confidence']:>4}% {s['composite_score']:>5.1f} {rsi_str:>5} {rr_s:>5} {chk:>5} {entry:<12}")

    # Summary stats
    buy_stocks = [s for s in all_stocks_flat if s["verdict"] in ("BUY", "STRONG BUY")]
    strong_buys = [s for s in all_stocks_flat if s["verdict"] == "STRONG BUY"]
    perfect = [s for s in all_stocks_flat if s.get("checklist_score", 0) >= 11]
    entry_ready = [s for s in all_stocks_flat if s.get("entry_status") == "ENTRY READY"]
    entry_zone = [s for s in all_stocks_flat if s.get("entry_status") == "ENTRY ZONE"]

    print(f"\n{'='*100}")
    print(f"  MARKET SUMMARY")
    print(f"{'='*100}")
    print(f"  Total analyzed:       {scan_result['total_scanned']}")
    print(f"  STRONG BUY:           {len(strong_buys)}")
    print(f"  BUY:                  {len(buy_stocks) - len(strong_buys)}")
    print(f"  11+/13 Checklist:     {len(perfect)} stocks (elite daily setups)")
    print(f"  🟢 ENTRY READY:       {len(entry_ready)} stocks (all 3 TFs confirmed — buy now)")
    print(f"  🟡 ENTRY ZONE:        {len(entry_zone)} stocks (1H ready, wait for 15m trigger)")
    print(f"  Market Sentiment:  ", end="")
    buy_pct = len(buy_stocks) / len(all_stocks_flat) * 100 if all_stocks_flat else 0
    if buy_pct > 60:
        print(f"🟢 BULLISH ({buy_pct:.0f}% of stocks are BUY)")
    elif buy_pct > 40:
        print(f"🟡 MIXED ({buy_pct:.0f}% of stocks are BUY)")
    else:
        print(f"🔴 BEARISH ({buy_pct:.0f}% of stocks are BUY)")
    print(f"{'='*100}\n")

    # ── Bear Market / Expert Avoids Section ──────────────────────────
    all_enriched = [s for s in all_stocks_flat if s.get("expert")]
    hard_rejects = [s for s in all_enriched if s["expert"].get("hard_reject")]
    bear_warnings = [
        s for s in all_enriched
        if not s["expert"].get("hard_reject")
        and s["expert"].get("distribution_risk") in ("HIGH", "CRITICAL")
    ]

    if hard_rejects or bear_warnings or (regime and regime in ("BEAR", "PANIC")):
        print(f"\n{'='*100}")
        if regime == "PANIC":
            print(f"  🚨 PANIC MODE — AVOID ALL STOCKS. WAIT FOR MARKET TO STABILIZE.")
        elif regime == "BEAR":
            print(f"  🐻 BEAR MARKET RISK REPORT — Stocks to AVOID or SELL")
        else:
            print(f"  ⚠️  RISK REPORT — Hard Rejects & High Distribution Stocks")
        print(f"{'='*100}")

        if hard_rejects:
            print(f"\n  🚫 HARD REJECTS (Do NOT buy these):")
            for s in hard_rejects:
                ex = s["expert"]
                print(f"     {s['symbol']:<10} Rs.{s['current_price']:>7.1f} | "
                      f"{ex['hard_reject']}")
                dist_warn = ex.get("distribution_warning", "")
                if dist_warn and len(dist_warn) > 10:
                    print(f"               ↳ {dist_warn[:80]}")

        if bear_warnings:
            print(f"\n  ⚠️  HIGH DISTRIBUTION RISK (Proceed with extreme caution):")
            for s in bear_warnings:
                ex = s["expert"]
                print(f"     {s['symbol']:<10} Rs.{s['current_price']:>7.1f} | "
                      f"Risk: {ex['distribution_risk']:<8} | Profit above cost: {ex['broker_profit_pct']:+.1f}%")

        if regime == "BEAR":
            print(f"\n  📋 BEAR MARKET STRATEGY:")
            print(f"     • Keep positions small (max 50% of normal size)")
            print(f"     • ONLY buy stocks with R:R ≥ 2.0 (higher bar in bear)")
            print(f"     • Prefer VALUE stocks (PE < 15, ROE > 15%)")
            print(f"     • Wide stops allowed — use 2x ATR stop-loss")
            print(f"     • Take profits early at 10%–15% (don't be greedy)")
            print(f"     • Cash is a position — it's OK to stay out")

        print(f"{'='*100}\n")
    # ─────────────────────────────────────────────────────────────────


def save_json_report(scan_result: dict, output_path: str):
    """Save the full scan result as JSON for API/web consumption."""
    # Clean non-serializable data
    clean = {
        "scan_time": scan_result["scan_time"],
        "total_scanned": scan_result["total_scanned"],
        "total_failed": scan_result["total_failed"],
        "sectors": {},
    }
    for sec, stocks in scan_result["sectors"].items():
        clean["sectors"][sec] = []
        for s in stocks:
            entry = {
                "symbol": s["symbol"],
                "company_name": s.get("company_name", ""),
                "current_price": s["current_price"],
                "price_change_pct": s["price_change_pct"],
                "verdict": s["verdict"],
                "confidence": s["confidence"],
                "composite_score": s["composite_score"],
                "checklist_score": s.get("checklist_score", 0),
                "checklist": s.get("checklist", {}),
                "trend": s["trend"],
                "rsi_14": s.get("rsi_14"),
                "macd_signal": s.get("macd_signal"),
                "adx_14": s.get("adx_14"),
                "rr_ratio": s.get("rr_ratio"),
                "suggested_sl": s["suggested_sl"],
                "suggested_target": s["suggested_target"],
                "obv_trend": s.get("obv_trend"),
                "ma_crossover": s.get("ma_crossover"),
                "market_phase": s.get("market_phase"),
                "market_structure": s.get("market_structure"),
                "momentum_status": s.get("momentum_status"),
                "volume_profile": s.get("volume_profile"),
                "rsi_divergence": s.get("rsi_divergence"),
                "breakout_status": s.get("breakout_status"),
                "biweekly_verdict":    s.get("biweekly_verdict"),
                "weekly_verdict":      s.get("weekly_verdict"),
                "monthly_verdict":     s.get("monthly_verdict"),
                "quarterly_verdict":   s.get("quarterly_verdict"),
                "semi_yearly_verdict": s.get("semi_yearly_verdict"),
                "yearly_verdict":      s.get("yearly_verdict"),
                "multi_tf": s.get("multi_tf", []),
            }
            clean["sectors"][sec].append(entry)

    with open(output_path, "w") as f:
        json.dump(clean, f, indent=2, default=str)
    print(f"  📁 JSON report saved: {output_path}")


# ─── FastAPI Endpoint (adds /scan to the existing backend) ─────────

def register_screener_routes(app):
    """Register the /scan endpoint on the existing FastAPI app."""
    from fastapi import Query

    @app.get("/scan")
    async def scan_market(
        sector: Optional[str] = Query(None, description="Filter by sector name"),
        top: int = Query(5, ge=1, le=20, description="Top N per sector"),
        fsk: str = Query(DEFAULT_FSK, description="NepseAlpha session key"),
    ):
        result = await scan_all_stocks(sector_filter=sector, top_n=top, fsk=fsk)
        # Convert to JSON-safe format
        clean_sectors = {}
        for sec, stocks in result["sectors"].items():
            clean_sectors[sec] = []
            for s in stocks:
                clean_sectors[sec].append({
                    "symbol": s["symbol"],
                    "company_name": s.get("company_name", ""),
                    "current_price": s["current_price"],
                    "verdict": s["verdict"],
                    "confidence": s["confidence"],
                    "composite_score": s["composite_score"],
                    "checklist_score": s.get("checklist_score", 0),
                    "trend": s["trend"],
                    "rsi_14": s.get("rsi_14"),
                    "rr_ratio": s.get("rr_ratio"),
                    "suggested_sl": s["suggested_sl"],
                    "suggested_target": s["suggested_target"],
                    "biweekly_verdict":    s.get("biweekly_verdict"),
                    "weekly_verdict":      s.get("weekly_verdict"),
                    "monthly_verdict":     s.get("monthly_verdict"),
                    "quarterly_verdict":   s.get("quarterly_verdict"),
                    "semi_yearly_verdict": s.get("semi_yearly_verdict"),
                    "yearly_verdict":      s.get("yearly_verdict"),
                    "market_phase": s.get("market_phase"),
                })
        return {
            "scan_time": result["scan_time"],
            "total_scanned": result["total_scanned"],
            "sectors": clean_sectors,
        }


# ─── CLI Entry Point ───────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="NEPSE Market Screener — Scan all stocks, find top picks per sector"
    )
    parser.add_argument("--sector", type=str, default=None,
                        help="Filter to one sector (e.g. 'Commercial Banks')")
    parser.add_argument("--top", type=int, default=5,
                        help="Number of top stocks per sector (default: 5)")
    parser.add_argument("--json", action="store_true",
                        help="Save results as JSON file")
    parser.add_argument("--output", type=str, default=None,
                        help="JSON output file path")
    parser.add_argument("--fsk", type=str, default=DEFAULT_FSK,
                        help="NepseAlpha session key (fsk)")
    parser.add_argument("--no-expert", action="store_true",
                        help="Skip 4-Pillar expert enrichment (faster, TA-only output)")
    args = parser.parse_args()

    start = time.time()
    result = await scan_all_stocks(
        sector_filter=args.sector,
        top_n=args.top,
        fsk=args.fsk,
    )
    elapsed = time.time() - start

    # Always save watchlist so `monitor` works even when expert is skipped or PANIC fires
    save_watchlist(result)

    # Phase 3: Expert 4-Pillar enrichment (market regime + broker/fundamental/manipulation)
    if not args.no_expert:
        result = enrich_expert(result)

    print_results(result)
    print(f"  ⏱  Total scan time: {elapsed:.1f}s\n")

    if args.json:
        out_path = args.output or f"scan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        save_json_report(result, out_path)


if __name__ == "__main__":
    asyncio.run(main())
