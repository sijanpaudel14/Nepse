"""
NEPSE Chart Analyzer — FastAPI Backend
=======================================
Receives intercepted OHLCV chart data from the Chrome Extension,
runs full technical analysis using pandas-ta, and returns a
simplified trading verdict with actionable levels.

Endpoints:
    POST /analyze  — Analyze OHLCV candle data
    GET  /health   — Health check
"""

import math
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd
import pandas_ta as ta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator


# ─── Pydantic Models ────────────────────────────────────────────────

class CandleBar(BaseModel):
    """Single OHLCV bar from the ShareHub chart API."""
    time: int              # Unix timestamp (seconds)
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class ChartMetadata(BaseModel):
    """URL parameters extracted from the intercepted ShareHub request."""
    symbol: str
    resolution: str = "1D"
    countback: str = "300"
    isAdjust: str = "false"
    time: str = ""

    @field_validator("symbol")
    @classmethod
    def symbol_must_be_nonempty(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("symbol must not be empty")
        return v


class AnalyzeRequest(BaseModel):
    """Payload sent from Chrome Extension → Backend."""
    metadata: ChartMetadata
    data: list[CandleBar] = Field(..., min_length=5)


class PatternInfo(BaseModel):
    """Detected candlestick pattern."""
    name: str
    direction: str          # Bullish / Bearish
    bar_index: int          # Which bar triggered it (0 = latest)
    strength: int           # pandas-ta value (100 / 200 / -100 / -200)


class AnalyzeResponse(BaseModel):
    """Full analysis result sent back to the extension."""
    symbol: str
    resolution: str
    verdict: str                        # STRONG BUY, BUY, HOLD, SELL, STRONG SELL
    confidence: int                     # 0-100
    pattern_detected: str               # Primary pattern name (human-readable)
    patterns: list[PatternInfo]         # All detected patterns on recent bars
    operator_activity: bool             # Volume anomaly detected
    volume_ratio: float                 # Latest volume / 20-SMA(volume)

    # Price levels
    current_price: float
    suggested_sl: float                 # Dynamic ATR-based stop loss
    suggested_target: float             # Risk:Reward based target
    risk_reward_ratio: float

    # Indicators
    rsi_14: Optional[float] = None
    atr_14: Optional[float] = None
    ema_10: Optional[float] = None
    ema_30: Optional[float] = None
    macd_signal: Optional[str] = None   # Bullish / Bearish / Neutral
    bb_pct_b: Optional[float] = None    # Bollinger %B (0-1)

    # Trend
    trend: str                          # UPTREND, DOWNTREND, SIDEWAYS
    trend_strength: Optional[float] = None  # ADX value

    # NEPSE-specific warnings
    warnings: list[str] = []


# ─── FastAPI App ─────────────────────────────────────────────────────

app = FastAPI(
    title="NEPSE Chart Analyzer",
    version="1.0.0",
    description="Backend for the NEPSE ShareHub Chrome Extension",
)

# Allow requests from the background service worker (localhost origin)
# and from any chrome-extension:// origin. Using ["*"] is safe here because
# this server only listens on 127.0.0.1 and is not externally reachable.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "nepse-chart-analyzer"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_chart(req: AnalyzeRequest):
    """
    Core analysis endpoint.

    Receives intercepted OHLCV data from the Chrome Extension,
    computes indicators, detects patterns, and returns a verdict.
    """
    try:
        df = _build_dataframe(req.data)
        if len(df) < 14:
            raise HTTPException(status_code=422, detail="Need at least 14 bars for analysis")

        # ── 1. Compute Indicators ────────────────────────────────
        indicators = _compute_indicators(df)

        # ── 2. Detect Candlestick Patterns ───────────────────────
        patterns = _detect_patterns(df)

        # ── 3. Detect Operator Activity (Volume Anomaly) ─────────
        operator_activity, volume_ratio = _detect_operator_activity(df)

        # ── 4. Determine Trend ───────────────────────────────────
        trend, trend_strength = _determine_trend(df, indicators)

        # ── 5. Calculate Price Levels ────────────────────────────
        current_price = float(df["close"].iloc[-1])
        atr_val = indicators.get("atr_14")
        suggested_sl = _calculate_stop_loss(current_price, atr_val, trend)
        suggested_target = _calculate_target(current_price, suggested_sl)
        risk = abs(current_price - suggested_sl)
        reward = abs(suggested_target - current_price)
        rr_ratio = round(reward / risk, 2) if risk > 0 else 0.0

        # ── 6. Generate Verdict ──────────────────────────────────
        verdict, confidence = _generate_verdict(
            patterns=patterns,
            indicators=indicators,
            operator_activity=operator_activity,
            trend=trend,
            trend_strength=trend_strength,
            volume_ratio=volume_ratio,
        )

        # ── 7. NEPSE-Specific Warnings ───────────────────────────
        warnings = _generate_warnings(
            df, indicators, operator_activity, volume_ratio, req.metadata.resolution
        )

        # Primary pattern for the headline
        primary_pattern = patterns[0].name if patterns else "None"

        return AnalyzeResponse(
            symbol=req.metadata.symbol,
            resolution=req.metadata.resolution,
            verdict=verdict,
            confidence=confidence,
            pattern_detected=primary_pattern,
            patterns=patterns,
            operator_activity=operator_activity,
            volume_ratio=round(volume_ratio, 2),
            current_price=round(current_price, 2),
            suggested_sl=round(suggested_sl, 2),
            suggested_target=round(suggested_target, 2),
            risk_reward_ratio=rr_ratio,
            rsi_14=indicators.get("rsi_14"),
            atr_14=indicators.get("atr_14"),
            ema_10=indicators.get("ema_10"),
            ema_30=indicators.get("ema_30"),
            macd_signal=indicators.get("macd_signal"),
            bb_pct_b=indicators.get("bb_pct_b"),
            trend=trend,
            trend_strength=trend_strength,
            warnings=warnings,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ─── Helper Functions ────────────────────────────────────────────────


def _safe_val(df_or_series, col_prefix: str = "") -> Optional[float]:
    """
    Safely extract the last value from a pandas Series or DataFrame column.

    Uses column-prefix matching (handles pandas-ta version differences in column names).
    Always returns a Python float or None — never a numpy scalar or pandas Series,
    which prevents 'truth value of a Series is ambiguous' errors downstream.
    """
    try:
        if df_or_series is None:
            return None
        if hasattr(df_or_series, "columns"):
            # DataFrame: find the first column whose name starts with the prefix
            cols = [c for c in df_or_series.columns if str(c).startswith(col_prefix)]
            if not cols:
                return None
            series = df_or_series[cols[0]]
        else:
            series = df_or_series

        if hasattr(series, "empty") and series.empty:
            return None

        # Extract as plain Python float — avoids numpy scalar ambiguity
        val = series.iloc[-1]
        f = float(val)
        # NaN check without pd.isna (NaN != NaN)
        return None if (f != f) else f
    except Exception:
        return None


def _build_dataframe(bars: list[CandleBar]) -> pd.DataFrame:
    """
    Convert the OHLCV bar list into a pandas DataFrame with datetime index.

    ShareHub sends timestamps as Unix seconds (not milliseconds).
    We convert to proper datetime for pandas-ta compatibility.
    """
    records = []
    for bar in bars:
        # ShareHub uses seconds; handle both seconds and millisecond timestamps
        ts = bar.time
        if ts > 1e12:
            ts = ts / 1000  # Convert ms → s
        records.append({
            "datetime": datetime.fromtimestamp(ts, tz=timezone.utc),
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
        })

    df = pd.DataFrame(records)
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)

    # Deduplicate timestamps (intraday data can have repeated bars)
    df = df[~df.index.duplicated(keep="last")]

    # Drop any rows where OHLC is zero or NaN (bad data from API)
    df = df[(df["close"] > 0) & (df["open"] > 0)]
    df.dropna(subset=["open", "high", "low", "close"], inplace=True)

    return df


def _compute_indicators(df: pd.DataFrame) -> dict[str, Any]:
    """
    Calculate all technical indicators using pandas-ta.

    Returns a flat dict of the LATEST values for each indicator.
    All values are Python floats or None — never numpy scalars or Series.
    """
    result: dict[str, Any] = {}

    # ── RSI (14-period) ──
    try:
        val = _safe_val(df.ta.rsi(length=14))
        result["rsi_14"] = round(val, 2) if val is not None else None
    except Exception:
        result["rsi_14"] = None

    # ── ATR (14-period) ──
    try:
        val = _safe_val(df.ta.atr(length=14))
        result["atr_14"] = round(val, 2) if val is not None else None
    except Exception:
        result["atr_14"] = None

    # ── EMA (10 and 30) ──
    try:
        val = _safe_val(df.ta.ema(length=10))
        result["ema_10"] = round(val, 2) if val is not None else None
    except Exception:
        result["ema_10"] = None
    try:
        val = _safe_val(df.ta.ema(length=30))
        result["ema_30"] = round(val, 2) if val is not None else None
    except Exception:
        result["ema_30"] = None

    # ── MACD (12, 26, 9) ──
    # Column names: MACD_12_26_9  MACDh_12_26_9  MACDs_12_26_9
    try:
        macd_df = df.ta.macd(fast=12, slow=26, signal=9)
        macd_line = _safe_val(macd_df, "MACD_")
        signal_line = _safe_val(macd_df, "MACDs_")
        if macd_line is not None and signal_line is not None:
            if macd_line > signal_line:
                result["macd_signal"] = "Bullish"
            elif macd_line < signal_line:
                result["macd_signal"] = "Bearish"
            else:
                result["macd_signal"] = "Neutral"
        else:
            result["macd_signal"] = None
    except Exception:
        result["macd_signal"] = None

    # ── ADX (14-period) — Trend Strength ──
    # Column names: ADX_14  DMP_14  DMN_14
    try:
        adx_df = df.ta.adx(length=14)
        val = _safe_val(adx_df, "ADX_")
        result["adx_14"] = round(val, 2) if val is not None else None
    except Exception:
        result["adx_14"] = None

    # ── Bollinger Bands %B ──
    # Column names: BBL_20_2.0  BBM_20_2.0  BBU_20_2.0  BBB_20_2.0  BBP_20_2.0
    try:
        bb_df = df.ta.bbands(length=20, std=2)
        bbu = _safe_val(bb_df, "BBU_")
        bbl = _safe_val(bb_df, "BBL_")
        price = float(df["close"].iloc[-1])
        if bbu is not None and bbl is not None:
            width = bbu - bbl
            if width > 0:
                result["bb_pct_b"] = round((price - bbl) / width, 3)
            else:
                result["bb_pct_b"] = None
        else:
            result["bb_pct_b"] = None
    except Exception:
        result["bb_pct_b"] = None

    # ── Stochastic RSI ──
    # Column names: STOCHRSIk_14_14_3_3  STOCHRSId_14_14_3_3
    try:
        stochrsi = df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3)
        k_val = _safe_val(stochrsi, "STOCHRSIk_")
        d_val = _safe_val(stochrsi, "STOCHRSId_")
        result["stochrsi_k"] = round(k_val, 2) if k_val is not None else None
        result["stochrsi_d"] = round(d_val, 2) if d_val is not None else None
    except Exception:
        result["stochrsi_k"] = None
        result["stochrsi_d"] = None

    return result


def _detect_patterns(df: pd.DataFrame) -> list[PatternInfo]:
    """
    Detect candlestick patterns using pure Python/numpy — no TA-Lib required.

    Covers the 15 most tradeable reversal and continuation patterns.
    Scans the last 3 bars; offset=0 is the most recent bar.
    """
    detected: list[PatternInfo] = []
    n = len(df)
    if n < 3:
        return []

    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)

    for offset in range(3):
        i = n - 1 - offset
        if i < 2:
            continue

        # Current bar
        o0, h0, l0, c0 = o[i], h[i], l[i], c[i]
        # Previous bar
        o1, h1, l1, c1 = o[i-1], h[i-1], l[i-1], c[i-1]
        # Two bars ago
        o2, h2, l2, c2 = o[i-2], h[i-2], l[i-2], c[i-2]

        body0  = abs(c0 - o0)
        range0 = h0 - l0
        body1  = abs(c1 - o1)
        range1 = h1 - l1 if h1 - l1 > 0 else 1e-9
        body2  = abs(c2 - o2)
        range2 = h2 - l2 if h2 - l2 > 0 else 1e-9

        if range0 <= 0:
            continue

        bull0 = c0 >= o0
        bear0 = c0 <  o0
        bull1 = c1 >= o1
        bear1 = c1 <  o1
        bull2 = c2 >= o2
        bear2 = c2 <  o2

        upper_wick0 = h0 - max(o0, c0)
        lower_wick0 = min(o0, c0) - l0
        upper_wick1 = h1 - max(o1, c1)
        lower_wick1 = min(o1, c1) - l1

        def add(name: str, direction: str, strength: int) -> None:
            detected.append(PatternInfo(
                name=name, direction=direction,
                bar_index=offset, strength=strength,
            ))

        # ── Doji (body ≤ 10% of range) ─────────────────────────────────
        if body0 <= 0.1 * range0:
            add("Doji", "Bullish", 100)

        # ── Marubozu (body ≥ 90%, virtually no wicks) ──────────────────
        elif body0 >= 0.9 * range0:
            add("Marubozu", "Bullish" if bull0 else "Bearish",
                200 if bull0 else -200)

        # ── Spinning Top (small body, both wicks present) ──────────────
        elif (body0 < 0.35 * range0 and
              upper_wick0 >= 0.15 * range0 and
              lower_wick0 >= 0.15 * range0):
            add("Spinning Top", "Bullish" if bull0 else "Bearish",
                100 if bull0 else -100)

        # ── Hammer / Hanging Man (long lower wick, tiny upper wick) ────
        if (body0 > 0 and lower_wick0 >= 2.0 * body0 and
                upper_wick0 <= 0.15 * range0):
            if bear1:
                add("Hammer", "Bullish", 100)      # After downtrend = bullish
            else:
                add("Hanging Man", "Bearish", -100) # After uptrend = bearish

        # ── Shooting Star / Inverted Hammer (long upper wick, tiny lower) ──
        if (body0 > 0 and upper_wick0 >= 2.0 * body0 and
                lower_wick0 <= 0.15 * range0):
            if bull1:
                add("Shooting Star", "Bearish", -100)   # After uptrend = bearish
            else:
                add("Inverted Hammer", "Bullish", 100)  # After downtrend = bullish

        # ── Bullish / Bearish Engulfing ─────────────────────────────────
        if body1 > 0:
            # Bullish: prev bearish, current bullish body fully engulfs prev
            if bear1 and bull0 and o0 <= c1 and c0 >= o1 and body0 > body1:
                add("Engulfing", "Bullish", 200)
            # Bearish: prev bullish, current bearish body fully engulfs prev
            elif bull1 and bear0 and o0 >= c1 and c0 <= o1 and body0 > body1:
                add("Engulfing", "Bearish", -200)

        # ── Harami (current body inside previous large body) ────────────
        if body1 > 0 and body0 < body1 * 0.6:
            hi_b1 = max(o1, c1); lo_b1 = min(o1, c1)
            hi_b0 = max(o0, c0); lo_b0 = min(o0, c0)
            if hi_b0 <= hi_b1 and lo_b0 >= lo_b1:
                if bear1 and bull0:
                    add("Harami", "Bullish", 100)
                elif bull1 and bear0:
                    add("Harami", "Bearish", -100)

        # ── Dark Cloud Cover (bearish 2-bar reversal) ───────────────────
        if (bull1 and bear0 and body1 >= 0.5 * range1 and
                o0 >= h1 * 0.99 and                     # opens near/above prev high
                c0 < (o1 + c1) / 2 and c0 > o1):        # closes in lower half of prev body
            add("Dark Cloud Cover", "Bearish", -100)

        # ── Piercing Line (bullish 2-bar reversal) ──────────────────────
        if (bear1 and bull0 and body1 >= 0.5 * range1 and
                o0 <= l1 * 1.01 and                      # opens near/below prev low
                c0 > (o1 + c1) / 2 and c0 < o1):        # closes in upper half of prev body
            add("Piercing", "Bullish", 100)

        # ── Morning Star (3-bar bullish reversal) ───────────────────────
        if (bear2 and body2 >= 0.5 * range2 and          # strong bearish first bar
                body1 <= 0.35 * range1 and                # small star middle bar
                bull0 and body0 >= 0.4 * range0 and       # strong bullish third bar
                c0 > (o2 + c2) / 2):                      # closes above first bar midpoint
            add("Morning Star", "Bullish", 200)

        # ── Evening Star (3-bar bearish reversal) ───────────────────────
        if (bull2 and body2 >= 0.5 * range2 and           # strong bullish first bar
                body1 <= 0.35 * range1 and                 # small star middle bar
                bear0 and body0 >= 0.4 * range0 and        # strong bearish third bar
                c0 < (o2 + c2) / 2):                       # closes below first bar midpoint
            add("Evening Star", "Bearish", -200)

        # ── Three White Soldiers ─────────────────────────────────────────
        if (bull0 and bull1 and bull2 and
                c0 > c1 > c2 and o0 > o1 > o2 and
                body0 >= 0.5 * range0 and
                body1 >= 0.5 * range1 and
                body2 >= 0.5 * range2):
            add("Three White Soldiers", "Bullish", 200)

        # ── Three Black Crows ────────────────────────────────────────────
        if (bear0 and bear1 and bear2 and
                c0 < c1 < c2 and o0 < o1 < o2 and
                body0 >= 0.5 * range0 and
                body1 >= 0.5 * range1 and
                body2 >= 0.5 * range2):
            add("Three Black Crows", "Bearish", -200)

    # Sort: latest bar first, then by strength (strongest first)
    detected.sort(key=lambda p: (p.bar_index, -abs(p.strength)))
    return detected


def _detect_operator_activity(df: pd.DataFrame) -> tuple[bool, float]:
    """
    Detect unusual volume that may indicate operator/institutional activity.

    In NEPSE, operators accumulate quietly then pump volume 3-5x to attract
    retail traders. We flag when latest volume exceeds 3x the 20-period SMA.

    Returns:
        (is_operator_activity, volume_ratio)
    """
    if "volume" not in df.columns or len(df) < 20:
        return False, 1.0

    vol_sma_20 = df["volume"].rolling(20).mean()
    latest_vol = df["volume"].iloc[-1]
    avg_vol = vol_sma_20.iloc[-1]

    if pd.isna(avg_vol) or avg_vol <= 0:
        return False, 1.0

    ratio = latest_vol / avg_vol

    # Flag if volume is 3x or more above 20-day average
    is_operator = bool(ratio >= 3.0)

    return is_operator, float(ratio)


def _determine_trend(df: pd.DataFrame, indicators: dict) -> tuple[str, Optional[float]]:
    """
    Determine the current trend using EMA alignment + ADX strength.

    EMA(10) > EMA(30) = UPTREND
    EMA(10) < EMA(30) = DOWNTREND
    ADX < 20 = SIDEWAYS (regardless of EMA)
    """
    ema10 = indicators.get("ema_10")
    ema30 = indicators.get("ema_30")
    adx = indicators.get("adx_14")

    if ema10 is None or ema30 is None:
        return "UNKNOWN", None

    # ADX below 20 = no meaningful trend (NEPSE-calibrated; NYSE uses 25)
    if adx is not None and adx < 20:
        return "SIDEWAYS", adx

    if ema10 > ema30:
        return "UPTREND", adx
    elif ema10 < ema30:
        return "DOWNTREND", adx
    else:
        return "SIDEWAYS", adx


def _calculate_stop_loss(
    current_price: float,
    atr: Optional[float],
    trend: str,
) -> float:
    """
    Dynamic ATR-based stop-loss.

    - Standard: Close - 1.5 × ATR (tighter for NEPSE — T+2 lockup)
    - Uptrend:  Close - 2.0 × ATR (wider stop, let it run)
    - Downtrend: Close - 1.0 × ATR (tight stop, preserve capital)

    NEPSE constraint: stop cannot be more than 8% below entry
    (because ±10% circuit breakers limit daily movement).
    """
    if atr is None or atr <= 0:
        # Fallback: 3% fixed stop
        return round(current_price * 0.97, 2)

    multiplier = {
        "UPTREND": 2.0,
        "DOWNTREND": 1.0,
        "SIDEWAYS": 1.5,
    }.get(trend, 1.5)

    raw_stop = current_price - (multiplier * atr)

    # NEPSE floor: max 8% below (circuit breaker constraint)
    floor_stop = current_price * 0.92
    stop = max(raw_stop, floor_stop)

    # Minimum: at least 1% below to avoid noise triggers
    ceiling = current_price * 0.99
    stop = min(stop, ceiling)

    return round(stop, 2)


def _calculate_target(current_price: float, stop_loss: float) -> float:
    """
    Calculate target price for minimum 1:2 Risk:Reward.

    Risk = |entry - stop|
    Target = entry + 2 × Risk
    """
    risk = abs(current_price - stop_loss)
    target = current_price + (2.0 * risk)

    # Cap at +10% (NEPSE daily circuit breaker — multi-day targets will exceed this)
    max_target = current_price * 1.15
    return round(min(target, max_target), 2)


def _generate_verdict(
    patterns: list[PatternInfo],
    indicators: dict,
    operator_activity: bool,
    trend: str,
    trend_strength: Optional[float],
    volume_ratio: float,
) -> tuple[str, int]:
    """
    Generate a trading verdict from the combined analysis.

    Scoring system (total points → verdict):
        ≥  7 → STRONG BUY
        4-6  → BUY
        1-3  → HOLD
       -3-0  → SELL (hold if you own, don't buy)
        ≤ -4 → STRONG SELL
    """
    score = 0
    reasons = []

    # ── RSI Score ──
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if rsi < 30:
            score += 3          # Oversold — high reversal probability
            reasons.append("RSI oversold")
        elif rsi < 40:
            score += 1
        elif rsi > 70:
            score -= 3          # Overbought — high reversal down
            reasons.append("RSI overbought")
        elif rsi > 60:
            score -= 1

    # ── Trend Score ──
    if trend == "UPTREND":
        score += 2
    elif trend == "DOWNTREND":
        score -= 2
    elif trend == "SIDEWAYS":
        score += 0  # Neutral

    # ── MACD Score ──
    macd = indicators.get("macd_signal")
    if macd == "Bullish":
        score += 1
    elif macd == "Bearish":
        score -= 1

    # ── Bollinger %B Score ──
    pct_b = indicators.get("bb_pct_b")
    if pct_b is not None:
        if pct_b < 0.0:
            score += 2      # Below lower band = oversold (value zone)
        elif pct_b < 0.2:
            score += 1
        elif pct_b > 1.0:
            score -= 2      # Above upper band = overbought
        elif pct_b > 0.8:
            score -= 1

    # ── Pattern Score ──
    # Only count patterns on the latest bar (most relevant)
    latest_patterns = [p for p in patterns if p.bar_index == 0]
    bullish_count = sum(1 for p in latest_patterns if p.direction == "Bullish")
    bearish_count = sum(1 for p in latest_patterns if p.direction == "Bearish")

    if bullish_count > 0:
        score += min(bullish_count, 3)  # Cap at +3
    if bearish_count > 0:
        score -= min(bearish_count, 3)

    # Strong patterns (200/-200) get extra weight
    for p in latest_patterns:
        if abs(p.strength) >= 200:
            if p.direction == "Bullish":
                score += 1
            else:
                score -= 1

    # ── Operator Activity Score ──
    # High volume + bullish patterns = operators pumping (ride it, but be cautious)
    # High volume + bearish patterns = distribution (avoid)
    if operator_activity:
        if bullish_count > bearish_count:
            score += 1
        elif bearish_count > bullish_count:
            score -= 2  # Distribution is more dangerous than missing a pump

    # ── StochRSI ──
    stoch_k = indicators.get("stochrsi_k")
    stoch_d = indicators.get("stochrsi_d")
    if stoch_k is not None and stoch_d is not None:
        if stoch_k > stoch_d and stoch_k < 30:
            score += 1      # Bullish crossover in oversold zone
        elif stoch_k < stoch_d and stoch_k > 70:
            score -= 1      # Bearish crossover in overbought zone

    # ── Map score to verdict ──
    if score >= 7:
        verdict = "STRONG BUY"
        confidence = min(95, 70 + score * 3)
    elif score >= 4:
        verdict = "BUY"
        confidence = min(85, 55 + score * 4)
    elif score >= 1:
        verdict = "HOLD"
        confidence = min(60, 40 + score * 5)
    elif score >= -3:
        verdict = "SELL"
        confidence = min(75, 40 + abs(score) * 5)
    else:
        verdict = "STRONG SELL"
        confidence = min(95, 70 + abs(score) * 3)

    return verdict, confidence


def _generate_warnings(
    df: pd.DataFrame,
    indicators: dict,
    operator_activity: bool,
    volume_ratio: float,
    resolution: str,
) -> list[str]:
    """
    Generate NEPSE-specific warnings and alerts.
    """
    warnings = []
    close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-2] if len(df) > 1 else close

    # Circuit breaker proximity
    daily_change_pct = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0
    if abs(daily_change_pct) > 8:
        remaining = 10 - abs(daily_change_pct)
        warnings.append(
            f"Near circuit breaker! Only {remaining:.1f}% "
            f"{'upside' if daily_change_pct > 0 else 'downside'} remaining"
        )

    # Operator warning
    if operator_activity:
        warnings.append(
            f"Volume anomaly: {volume_ratio:.1f}x average — possible operator activity"
        )

    # Extreme RSI
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if rsi > 80:
            warnings.append(f"RSI at {rsi:.0f} — extremely overbought, reversal likely")
        elif rsi < 20:
            warnings.append(f"RSI at {rsi:.0f} — extremely oversold, bounce possible")

    # Bollinger squeeze (low volatility → pending breakout)
    bb = indicators.get("bb_pct_b")
    atr = indicators.get("atr_14")
    if atr is not None and close > 0:
        atr_pct = (atr / close) * 100
        if atr_pct < 1.5:
            warnings.append("Low volatility (ATR squeeze) — expect breakout soon")

    # Intraday resolution warning
    if resolution in ("1", "3", "5", "15"):
        warnings.append("Intraday data — patterns less reliable than daily/weekly")

    # T+2 settlement reminder
    if resolution == "1D":
        warnings.append("NEPSE T+2 settlement: minimum 3 trading days hold")

    return warnings


# ─── Run ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
