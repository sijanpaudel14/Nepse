"""
NEPSE Chart Analyzer — FastAPI Backend (v2.0 Premium)
=====================================================
Receives intercepted OHLCV chart data from the Chrome Extension,
runs comprehensive multi-timeframe technical analysis using pandas-ta,
and returns detailed actionable intelligence with expert-level data.

Endpoints:
    POST /analyze  — Full technical analysis with multi-timeframe
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
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class ChartMetadata(BaseModel):
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
    metadata: ChartMetadata
    data: list[CandleBar] = Field(..., min_length=5)


class PatternInfo(BaseModel):
    name: str
    direction: str
    bar_index: int
    strength: int


class FibonacciLevel(BaseModel):
    level: str
    price: float


class PivotPoints(BaseModel):
    pp: float
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float


class IndicatorSignal(BaseModel):
    name: str
    value: Optional[float] = None
    signal: str


class TimeframeAnalysis(BaseModel):
    timeframe: str
    verdict: str
    confidence: int
    rsi_14: Optional[float] = None
    macd_signal: Optional[str] = None
    trend: str
    trend_strength: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_10: Optional[float] = None
    ema_30: Optional[float] = None
    patterns: list[PatternInfo] = []


class AnalyzeResponse(BaseModel):
    symbol: str
    resolution: str
    verdict: str
    confidence: int
    pattern_detected: str
    patterns: list[PatternInfo]
    operator_activity: bool
    volume_ratio: float

    current_price: float
    suggested_sl: float
    suggested_target: float
    risk_reward_ratio: float
    price_change_pct: Optional[float] = None

    rsi_14: Optional[float] = None
    atr_14: Optional[float] = None
    stochrsi_k: Optional[float] = None
    stochrsi_d: Optional[float] = None
    williams_r: Optional[float] = None
    cci_20: Optional[float] = None
    roc_14: Optional[float] = None
    adx_14: Optional[float] = None

    ema_10: Optional[float] = None
    ema_20: Optional[float] = None
    ema_30: Optional[float] = None
    ema_50: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None

    macd_signal: Optional[str] = None
    macd_line: Optional[float] = None
    macd_histogram: Optional[float] = None
    signal_line_val: Optional[float] = None
    bb_pct_b: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_middle: Optional[float] = None
    trend: str
    trend_strength: Optional[float] = None

    obv_trend: Optional[str] = None
    volume_sma_20: Optional[float] = None

    support_levels: list[float] = []
    resistance_levels: list[float] = []
    fibonacci_levels: list[FibonacciLevel] = []
    pivot_points: Optional[PivotPoints] = None

    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    pct_from_52w_high: Optional[float] = None
    pct_from_52w_low: Optional[float] = None

    ma_crossover: Optional[str] = None

    # Enhanced analysis fields
    di_plus: Optional[float] = None
    di_minus: Optional[float] = None
    breakout_status: Optional[str] = None
    market_structure: Optional[str] = None
    momentum_status: Optional[str] = None
    volume_profile: Optional[str] = None
    bb_position: Optional[str] = None
    rsi_divergence: Optional[str] = None
    market_phase: Optional[str] = None
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    support_distance_pct: Optional[float] = None
    resistance_distance_pct: Optional[float] = None
    volatility_pct: Optional[float] = None
    avg_volume: Optional[float] = None

    multi_tf: list[TimeframeAnalysis] = []

    oscillator_signals: list[IndicatorSignal] = []
    ma_signals: list[IndicatorSignal] = []
    oscillator_summary: Optional[str] = None
    ma_summary: Optional[str] = None
    overall_summary: Optional[str] = None

    warnings: list[str] = []


# ─── FastAPI App ─────────────────────────────────────────────────────

app = FastAPI(
    title="NEPSE Chart Analyzer",
    version="2.0.0",
    description="Premium Backend for the NEPSE ShareHub Chrome Extension",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# Register the market screener /scan endpoint (lazy import to avoid circular dependency)
@app.on_event("startup")
def _register_screener():
    from screener import register_screener_routes
    register_screener_routes(app)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "nepse-chart-analyzer", "version": "2.0"}


_LIVE_CURL_HEADERS = [
    "-H", "accept: application/json",
    "-H", "origin: https://nepsealpha.com",
    "-H", "referer: https://nepsealpha.com/",
    "-H", "user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
]


def _is_market_hours() -> bool:
    """Return True if NEPSE market is currently open (05:15–09:15 UTC, Sun–Thu)."""
    utc = datetime.now(timezone.utc)
    if utc.weekday() in (4, 5):  # Friday=4, Saturday=5
        return False
    market_open  = utc.replace(hour=5,  minute=15, second=0, microsecond=0)
    market_close = utc.replace(hour=9,  minute=15, second=0, microsecond=0)
    return market_open <= utc <= market_close


def _fetch_today_bar_single(symbol: str) -> Optional[CandleBar]:
    """Fetch today's live OHLCV bar from live.nepsealpha.com/lv_data via curl.

    NepseAlpha's history endpoint only has data up to yesterday's close.
    The live endpoint returns today's running bar (updates every ~1s during market).
    Returns None if market not yet open, symbol not traded, or error.
    """
    import subprocess, json as _json
    try:
        _fs = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "0000"
        url = (
            f"https://live.nepsealpha.com/lv_data"
            f"?symbol={symbol}&resolution=1D&fs={_fs}&tck=pass"
        )
        r = subprocess.run(
            ["curl", "-s", "-k", url] + _LIVE_CURL_HEADERS,
            capture_output=True, text=True, timeout=8,
        )
        d = _json.loads(r.stdout)
        ts = d.get("t", [])
        c = d.get("c", [])
        if not ts or not c:
            return None
        close_p = float(c[0])
        open_p = float(d["o"][0]) if d.get("o") else close_p
        high_p = float(d["h"][0]) if d.get("h") else close_p
        low_p  = float(d["l"][0]) if d.get("l") else close_p
        vol    = float(str(d["v"][0]).replace(",", "")) if d.get("v") else 0.0
        # Normalise timestamp to 05:45 UTC (matches NepseAlpha daily bar convention)
        _utc = datetime.now(timezone.utc)
        today_ts = int(datetime(
            _utc.year, _utc.month, _utc.day, 5, 45, 0, tzinfo=timezone.utc
        ).timestamp())
        return CandleBar(
            time=today_ts, open=open_p, high=high_p,
            low=low_p, close=close_p, volume=vol,
        )
    except Exception:
        return None


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_chart(req: AnalyzeRequest):
    try:
        bars = list(req.data)

        # ── Inject today's live bar for daily charts ─────────────────────────
        # NepseAlpha 1D API only returns bars up to yesterday's close.
        # Fetch today's running OHLCV so the entire analysis (RSI, MACD,
        # EMA trend, breakout detection, etc.) reflects live price action.
        resolution_upper = req.metadata.resolution.upper().strip()
        if resolution_upper == "1D" and _is_market_hours():
            today_bar = _fetch_today_bar_single(req.metadata.symbol)
            if today_bar is not None:
                last_ts = bars[-1].time if bars else 0
                if today_bar.time > last_ts:
                    bars = bars + [today_bar]

        df = _build_dataframe(bars)
        if len(df) < 5:
            raise HTTPException(status_code=422, detail="Need at least 5 bars for analysis")

        indicators = _compute_indicators(df)
        patterns = _detect_patterns(df)
        operator_activity, volume_ratio = _detect_operator_activity(df)
        trend, trend_strength = _determine_trend(df, indicators)

        current_price = float(df["close"].iloc[-1])
        prev_close = float(df["close"].iloc[-2]) if len(df) > 1 else current_price
        price_change_pct = round(((current_price - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0

        atr_val = indicators.get("atr_14")
        # S/R computed first so SL and target can snap to real levels
        support_levels, resistance_levels = _compute_support_resistance(df)
        suggested_sl = _calculate_stop_loss(current_price, atr_val, trend, support_levels)
        suggested_target = _calculate_target(current_price, suggested_sl, resistance_levels)
        _risk = abs(current_price - suggested_sl)
        _reward = abs(suggested_target - current_price)
        rr_ratio = round(_reward / _risk, 2) if _risk > 0 else 0.0
        fibonacci_levels = _compute_fibonacci(df)
        pivot_points = _compute_pivot_points(df)
        obv_trend = _compute_obv_trend(df)
        high_52w, low_52w, pct_high, pct_low = _compute_52w_range(df, current_price)
        ma_crossover = _compute_ma_crossover(df)
        multi_tf = _multi_timeframe_analysis(df, req.metadata.resolution)

        # Enhanced analysis
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

        warnings = _generate_warnings(
            df, indicators, operator_activity, volume_ratio,
            req.metadata.resolution, ma_crossover,
        )

        primary_pattern = patterns[0].name if patterns else "None"
        vol_sma = df["volume"].rolling(20).mean().iloc[-1] if len(df) >= 20 else None
        vol_sma_20 = round(float(vol_sma), 0) if vol_sma is not None and not pd.isna(vol_sma) else None

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
            price_change_pct=price_change_pct,
            rsi_14=indicators.get("rsi_14"),
            atr_14=indicators.get("atr_14"),
            stochrsi_k=indicators.get("stochrsi_k"),
            stochrsi_d=indicators.get("stochrsi_d"),
            williams_r=indicators.get("williams_r"),
            cci_20=indicators.get("cci_20"),
            roc_14=indicators.get("roc_14"),
            adx_14=indicators.get("adx_14"),
            ema_10=indicators.get("ema_10"),
            ema_20=indicators.get("ema_20"),
            ema_30=indicators.get("ema_30"),
            ema_50=indicators.get("ema_50"),
            sma_20=indicators.get("sma_20"),
            sma_50=indicators.get("sma_50"),
            sma_200=indicators.get("sma_200"),
            macd_signal=indicators.get("macd_signal"),
            macd_line=indicators.get("macd_line"),
            macd_histogram=indicators.get("macd_histogram"),
            signal_line_val=indicators.get("signal_line_val"),
            bb_pct_b=indicators.get("bb_pct_b"),
            bb_upper=indicators.get("bb_upper"),
            bb_lower=indicators.get("bb_lower"),
            bb_middle=indicators.get("bb_middle"),
            trend=trend,
            trend_strength=trend_strength,
            obv_trend=obv_trend,
            volume_sma_20=vol_sma_20,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            fibonacci_levels=fibonacci_levels,
            pivot_points=pivot_points,
            high_52w=high_52w,
            low_52w=low_52w,
            pct_from_52w_high=pct_high,
            pct_from_52w_low=pct_low,
            ma_crossover=ma_crossover,
            di_plus=indicators.get("di_plus"),
            di_minus=indicators.get("di_minus"),
            breakout_status=breakout_status,
            market_structure=market_structure,
            momentum_status=momentum_status,
            volume_profile=volume_profile,
            bb_position=bb_position,
            rsi_divergence=rsi_divergence,
            market_phase=market_phase,
            nearest_support=nearest_s,
            nearest_resistance=nearest_r,
            support_distance_pct=s_dist_pct,
            resistance_distance_pct=r_dist_pct,
            volatility_pct=volatility_pct,
            avg_volume=vol_sma_20,
            multi_tf=multi_tf,
            oscillator_signals=oscillator_signals,
            ma_signals=ma_signals,
            oscillator_summary=osc_summary,
            ma_summary=ma_summary_str,
            overall_summary=overall,
            warnings=warnings,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ─── Helper: Safe Value Extraction ──────────────────────────────────

def _safe_val(df_or_series, col_prefix: str = "") -> Optional[float]:
    """Safely extract the last value as a Python float or None."""
    try:
        if df_or_series is None:
            return None
        if hasattr(df_or_series, "columns"):
            cols = [c for c in df_or_series.columns if str(c).startswith(col_prefix)]
            if not cols:
                return None
            series = df_or_series[cols[0]]
        else:
            series = df_or_series
        if hasattr(series, "empty") and series.empty:
            return None
        val = series.iloc[-1]
        f = float(val)
        return None if (f != f) else f
    except Exception:
        return None


# ─── Helper: DataFrame Builder ──────────────────────────────────────

def _build_dataframe(bars: list[CandleBar]) -> pd.DataFrame:
    records = []
    for bar in bars:
        ts = bar.time
        # Timestamps > 1e10 are in milliseconds (or microseconds); normalize to seconds
        if ts > 1e10:
            ts = ts / 1000
        # Safety: if still unreasonable (before 2000 or after 2100), try further division
        if ts > 4_102_444_800:  # 2100-01-01 UTC
            ts = ts / 1000
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
    df = df[~df.index.duplicated(keep="last")]
    df = df[(df["close"] > 0) & (df["open"] > 0)]
    df.dropna(subset=["open", "high", "low", "close"], inplace=True)
    return df


# ─── Helper: Indicator Computation ──────────────────────────────────

def _compute_indicators(df: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {}

    # RSI (14)
    try:
        val = _safe_val(df.ta.rsi(length=14))
        result["rsi_14"] = round(val, 2) if val is not None else None
    except Exception:
        result["rsi_14"] = None

    # ATR (14)
    try:
        val = _safe_val(df.ta.atr(length=14))
        result["atr_14"] = round(val, 2) if val is not None else None
    except Exception:
        result["atr_14"] = None

    # EMA (10, 20, 30, 50)
    for length in (10, 20, 30, 50):
        try:
            val = _safe_val(df.ta.ema(length=length))
            result[f"ema_{length}"] = round(val, 2) if val is not None else None
        except Exception:
            result[f"ema_{length}"] = None

    # SMA (20, 50, 200)
    for length in (20, 50, 200):
        try:
            val = _safe_val(df.ta.sma(length=length))
            result[f"sma_{length}"] = round(val, 2) if val is not None else None
        except Exception:
            result[f"sma_{length}"] = None

    # MACD (12, 26, 9)
    try:
        macd_df = df.ta.macd(fast=12, slow=26, signal=9)
        macd_line = _safe_val(macd_df, "MACD_")
        signal_line = _safe_val(macd_df, "MACDs_")
        histogram = _safe_val(macd_df, "MACDh_")
        result["macd_line"] = round(macd_line, 2) if macd_line is not None else None
        result["signal_line_val"] = round(signal_line, 2) if signal_line is not None else None
        result["macd_histogram"] = round(histogram, 2) if histogram is not None else None
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
        result["macd_line"] = None
        result["signal_line_val"] = None
        result["macd_histogram"] = None

    # ADX (14) with DI+/DI-
    try:
        adx_df = df.ta.adx(length=14)
        val = _safe_val(adx_df, "ADX_")
        result["adx_14"] = round(val, 2) if val is not None else None
        dmp = _safe_val(adx_df, "DMP_")
        dmn = _safe_val(adx_df, "DMN_")
        result["di_plus"] = round(dmp, 2) if dmp is not None else None
        result["di_minus"] = round(dmn, 2) if dmn is not None else None
    except Exception:
        result["adx_14"] = None
        result["di_plus"] = None
        result["di_minus"] = None

    # Bollinger Bands (20, 2)
    try:
        bb_df = df.ta.bbands(length=20, std=2)
        bbu = _safe_val(bb_df, "BBU_")
        bbl = _safe_val(bb_df, "BBL_")
        bbm = _safe_val(bb_df, "BBM_")
        price = float(df["close"].iloc[-1])
        result["bb_upper"] = round(bbu, 2) if bbu is not None else None
        result["bb_lower"] = round(bbl, 2) if bbl is not None else None
        result["bb_middle"] = round(bbm, 2) if bbm is not None else None
        if bbu is not None and bbl is not None:
            width = bbu - bbl
            result["bb_pct_b"] = round((price - bbl) / width, 3) if width > 0 else None
        else:
            result["bb_pct_b"] = None
    except Exception:
        result["bb_pct_b"] = None
        result["bb_upper"] = None
        result["bb_lower"] = None
        result["bb_middle"] = None

    # Stochastic RSI (14, 14, 3, 3)
    try:
        stochrsi = df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3)
        k_val = _safe_val(stochrsi, "STOCHRSIk_")
        d_val = _safe_val(stochrsi, "STOCHRSId_")
        result["stochrsi_k"] = round(k_val, 2) if k_val is not None else None
        result["stochrsi_d"] = round(d_val, 2) if d_val is not None else None
    except Exception:
        result["stochrsi_k"] = None
        result["stochrsi_d"] = None

    # Williams %R (14)
    try:
        val = _safe_val(df.ta.willr(length=14))
        result["williams_r"] = round(val, 2) if val is not None else None
    except Exception:
        result["williams_r"] = None

    # CCI (20)
    try:
        val = _safe_val(df.ta.cci(length=20))
        result["cci_20"] = round(val, 2) if val is not None else None
    except Exception:
        result["cci_20"] = None

    # ROC (14)
    try:
        val = _safe_val(df.ta.roc(length=14))
        result["roc_14"] = round(val, 2) if val is not None else None
    except Exception:
        result["roc_14"] = None

    return result


# ─── Helper: Candlestick Pattern Detection (Pure Python) ────────────

def _detect_patterns(df: pd.DataFrame) -> list[PatternInfo]:
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

        o0, h0, l0, c0 = o[i], h[i], l[i], c[i]
        o1, h1, l1, c1 = o[i-1], h[i-1], l[i-1], c[i-1]
        o2, h2, l2, c2 = o[i-2], h[i-2], l[i-2], c[i-2]

        body0 = abs(c0 - o0)
        range0 = h0 - l0
        body1 = abs(c1 - o1)
        range1 = h1 - l1 if h1 - l1 > 0 else 1e-9
        body2 = abs(c2 - o2)
        range2 = h2 - l2 if h2 - l2 > 0 else 1e-9

        if range0 <= 0:
            continue

        bull0 = c0 >= o0
        bear0 = c0 < o0
        bull1 = c1 >= o1
        bear1 = c1 < o1
        bull2 = c2 >= o2
        bear2 = c2 < o2

        upper_wick0 = h0 - max(o0, c0)
        lower_wick0 = min(o0, c0) - l0
        upper_wick1 = h1 - max(o1, c1)
        lower_wick1 = min(o1, c1) - l1

        def add(name, direction, strength):
            detected.append(PatternInfo(
                name=name, direction=direction,
                bar_index=offset, strength=strength,
            ))

        # Doji
        if body0 <= 0.1 * range0:
            add("Doji", "Bullish", 100)
        # Marubozu
        elif body0 >= 0.9 * range0:
            add("Marubozu", "Bullish" if bull0 else "Bearish",
                200 if bull0 else -200)
        # Spinning Top
        elif (body0 < 0.35 * range0 and
              upper_wick0 >= 0.15 * range0 and
              lower_wick0 >= 0.15 * range0):
            add("Spinning Top", "Bullish" if bull0 else "Bearish",
                100 if bull0 else -100)

        # Hammer / Hanging Man
        if (body0 > 0 and lower_wick0 >= 2.0 * body0 and
                upper_wick0 <= 0.15 * range0):
            if bear1:
                add("Hammer", "Bullish", 100)
            else:
                add("Hanging Man", "Bearish", -100)

        # Shooting Star / Inverted Hammer
        if (body0 > 0 and upper_wick0 >= 2.0 * body0 and
                lower_wick0 <= 0.15 * range0):
            if bull1:
                add("Shooting Star", "Bearish", -100)
            else:
                add("Inverted Hammer", "Bullish", 100)

        # Engulfing
        if body1 > 0:
            if bear1 and bull0 and o0 <= c1 and c0 >= o1 and body0 > body1:
                add("Engulfing", "Bullish", 200)
            elif bull1 and bear0 and o0 >= c1 and c0 <= o1 and body0 > body1:
                add("Engulfing", "Bearish", -200)

        # Harami
        if body1 > 0 and body0 < body1 * 0.6:
            hi_b1 = max(o1, c1); lo_b1 = min(o1, c1)
            hi_b0 = max(o0, c0); lo_b0 = min(o0, c0)
            if hi_b0 <= hi_b1 and lo_b0 >= lo_b1:
                if bear1 and bull0:
                    add("Harami", "Bullish", 100)
                elif bull1 and bear0:
                    add("Harami", "Bearish", -100)

        # Dark Cloud Cover
        if (bull1 and bear0 and body1 >= 0.5 * range1 and
                o0 >= h1 * 0.99 and
                c0 < (o1 + c1) / 2 and c0 > o1):
            add("Dark Cloud Cover", "Bearish", -100)

        # Piercing Line
        if (bear1 and bull0 and body1 >= 0.5 * range1 and
                o0 <= l1 * 1.01 and
                c0 > (o1 + c1) / 2 and c0 < o1):
            add("Piercing", "Bullish", 100)

        # Morning Star
        if (bear2 and body2 >= 0.5 * range2 and
                body1 <= 0.35 * range1 and
                bull0 and body0 >= 0.4 * range0 and
                c0 > (o2 + c2) / 2):
            add("Morning Star", "Bullish", 200)

        # Evening Star
        if (bull2 and body2 >= 0.5 * range2 and
                body1 <= 0.35 * range1 and
                bear0 and body0 >= 0.4 * range0 and
                c0 < (o2 + c2) / 2):
            add("Evening Star", "Bearish", -200)

        # Three White Soldiers
        if (bull0 and bull1 and bull2 and
                c0 > c1 > c2 and o0 > o1 > o2 and
                body0 >= 0.5 * range0 and
                body1 >= 0.5 * range1 and
                body2 >= 0.5 * range2):
            add("Three White Soldiers", "Bullish", 200)

        # Three Black Crows
        if (bear0 and bear1 and bear2 and
                c0 < c1 < c2 and o0 < o1 < o2 and
                body0 >= 0.5 * range0 and
                body1 >= 0.5 * range1 and
                body2 >= 0.5 * range2):
            add("Three Black Crows", "Bearish", -200)

        # ── Doji Variants ──
        # Dragonfly Doji — long lower wick, open≈high≈close → strong bullish reversal
        if (body0 <= 0.07 * range0 and range0 > 0 and
                lower_wick0 >= 0.6 * range0 and
                upper_wick0 <= 0.07 * range0):
            add("Dragonfly Doji", "Bullish", 150)

        # Gravestone Doji — long upper wick, open≈low≈close → strong bearish reversal
        if (body0 <= 0.07 * range0 and range0 > 0 and
                upper_wick0 >= 0.6 * range0 and
                lower_wick0 <= 0.07 * range0):
            add("Gravestone Doji", "Bearish", -150)

        # ── Belt Hold ──
        # Bullish Belt Hold — opens at/near low (no lower wick), closes near high after a downtrend
        if (bull0 and lower_wick0 <= 0.05 * range0 and
                body0 >= 0.7 * range0 and bear1):
            add("Bullish Belt Hold", "Bullish", 150)

        # Bearish Belt Hold — opens at/near high (no upper wick), closes near low after uptrend
        if (bear0 and upper_wick0 <= 0.05 * range0 and
                body0 >= 0.7 * range0 and bull1):
            add("Bearish Belt Hold", "Bearish", -150)

        # ── Tweezer Bottom / Top ──
        # Tweezer Bottom — two bars share the same low (within 0.1%); bullish reversal
        if (i >= 1 and bear1 and bull0 and
                abs(l0 - l1) <= 0.001 * l1):
            add("Tweezer Bottom", "Bullish", 150)

        # Tweezer Top — two bars share the same high; bearish reversal
        if (i >= 1 and bull1 and bear0 and
                abs(h0 - h1) <= 0.001 * h1):
            add("Tweezer Top", "Bearish", -150)

        # ── Three Inside Up / Down ──
        # Three Inside Up — bar2 bearish, bar1 bullish harami inside bar2, bar0 closes above bar2 open
        if (i >= 2 and bear2 and bull1 and bull0 and
                max(o1, c1) < max(o2, c2) and  # harami
                min(o1, c1) > min(o2, c2) and
                c0 > o2):
            add("Three Inside Up", "Bullish", 200)

        # Three Inside Down — bar2 bullish, bar1 bearish harami inside bar2, bar0 closes below bar2 open
        if (i >= 2 and bull2 and bear1 and bear0 and
                max(o1, c1) < max(o2, c2) and
                min(o1, c1) > min(o2, c2) and
                c0 < o2):
            add("Three Inside Down", "Bearish", -200)

        # ── Kicker Patterns (gap-based; very strong signals) ──
        # Bullish Kicker — bearish bar1, then bull0 opens ABOVE bar1 open (gap up); powerful reversal
        if (bear1 and bull0 and o0 > o1 and body0 >= 0.5 * range0):
            add("Bullish Kicker", "Bullish", 200)

        # Bearish Kicker — bullish bar1, then bear0 opens BELOW bar1 open (gap down); powerful reversal
        if (bull1 and bear0 and o0 < o1 and body0 >= 0.5 * range0):
            add("Bearish Kicker", "Bearish", -200)

        # ── Tasuki Gap (continuation) ──
        # Upside Tasuki Gap — bull2, gap-up bull1, bear0 tries to close the gap but can't
        if (i >= 2 and bull2 and bull1 and bear0 and
                o1 > h2 and  # gap up
                o0 > c1 and o0 < h1 and  # opens inside bar1
                c0 > o2):     # can't close the gap (closes above bar2 high)
            add("Upside Tasuki Gap", "Bullish", 150)

        # Downside Tasuki Gap — bear2, gap-down bear1, bull0 tries to close gap but can't
        if (i >= 2 and bear2 and bear1 and bull0 and
                o1 < l2 and  # gap down
                o0 < c1 and o0 > l1 and  # opens inside bar1
                c0 < o2):     # can't close the gap
            add("Downside Tasuki Gap", "Bearish", -150)

        # ── Rising / Falling Window (Gap Continuation) ──
        # Rising Window — bar0 low is above bar1 high (bullish gap support)
        if l0 > h1:
            add("Rising Window", "Bullish", 150)

        # Falling Window — bar0 high is below bar1 low (bearish gap resistance)
        if h0 < l1:
            add("Falling Window", "Bearish", -150)

        # ── Bullish / Bearish Counterattack ──
        # Bullish Counterattack — bear1 large body, bear0 gaps down but closes at bar1 close
        if (bear1 and body1 >= 0.5 * range1 and
                bear0 and o0 < l1 and  # opens below bar1 low
                abs(c0 - c1) <= 0.005 * c1):  # closes near same level
            add("Bullish Counterattack", "Bullish", 150)

        # Bearish Counterattack — bull1 large body, bull0 gaps up but closes at bar1 close
        if (bull1 and body1 >= 0.5 * range1 and
                bull0 and o0 > h1 and  # opens above bar1 high
                abs(c0 - c1) <= 0.005 * c1):
            add("Bearish Counterattack", "Bearish", -150)

        # ── Bullish Abandoned Baby ──
        # Extremely rare: bear2 → doji1 that GAPS down from bar2 (no overlap) → bull0 that GAPS up from doji
        if (i >= 2 and bear2 and body2 >= 0.5 * range2 and
                body1 <= 0.1 * range1 and range1 > 0 and
                h1 < l2 and  # doji gaps down
                bull0 and body0 >= 0.5 * range0 and
                l0 > h1):    # bar0 gaps up above doji
            add("Abandoned Baby", "Bullish", 250)

        # ── Bearish Abandoned Baby ──
        if (i >= 2 and bull2 and body2 >= 0.5 * range2 and
                body1 <= 0.1 * range1 and range1 > 0 and
                l1 > h2 and  # doji gaps up
                bear0 and body0 >= 0.5 * range0 and
                h0 < l1):    # bar0 gaps down below doji
            add("Abandoned Baby", "Bearish", -250)

    detected.sort(key=lambda p: (p.bar_index, -abs(p.strength)))
    return detected


# ─── Helper: Operator Activity Detection ────────────────────────────

def _detect_operator_activity(df: pd.DataFrame) -> tuple[bool, float]:
    if "volume" not in df.columns or len(df) < 20:
        return False, 1.0
    vol_sma_20 = df["volume"].rolling(20).mean()
    latest_vol = df["volume"].iloc[-1]
    avg_vol = vol_sma_20.iloc[-1]
    if pd.isna(avg_vol) or avg_vol <= 0:
        return False, 1.0
    ratio = latest_vol / avg_vol
    is_operator = bool(ratio >= 3.0)
    return is_operator, float(ratio)


# ─── Helper: Trend Determination ────────────────────────────────────

def _determine_trend(df: pd.DataFrame, indicators: dict) -> tuple[str, Optional[float]]:
    ema10 = indicators.get("ema_10")
    ema30 = indicators.get("ema_30")
    adx = indicators.get("adx_14")
    if ema10 is None or ema30 is None:
        # Fallback for long-TF resampled data with too few bars for EMA
        if len(df) >= 2:
            first = float(df['close'].iloc[0])
            last = float(df['close'].iloc[-1])
            return ("UPTREND" if last > first else "DOWNTREND"), None
        return "UNKNOWN", None
    if adx is not None and adx < 20:
        return "SIDEWAYS", adx
    if ema10 > ema30:
        return "UPTREND", adx
    elif ema10 < ema30:
        return "DOWNTREND", adx
    else:
        return "SIDEWAYS", adx


# ─── Helper: Stop Loss ─────────────────────────────────────────────

def _calculate_stop_loss(
    current_price: float, atr: Optional[float], trend: str,
    support_levels: Optional[list] = None,
) -> float:
    """
    ATR-based stop loss, snapped to support if a level is within 1 ATR.
    Minimum distance: 1% (intraday noise buffer).
    Maximum distance: 10% (capital preservation).
    """
    if atr is None or atr <= 0:
        atr = current_price * 0.02  # Fallback: 2% ATR estimate

    multiplier = {"UPTREND": 2.0, "DOWNTREND": 1.5, "SIDEWAYS": 1.5}.get(trend, 1.5)
    atr_stop = current_price - (multiplier * atr)

    # Snap to nearest support level if it is within 1 ATR of the ATR-based stop
    if support_levels:
        for sup in support_levels:
            if atr_stop - atr <= sup <= atr_stop + atr and sup < current_price:
                atr_stop = sup * 0.998  # Just below support
                break

    # Enforce band: never tighter than 1%, never wider than 10%
    min_stop = current_price * 0.90
    max_stop = current_price * 0.99
    stop = max(atr_stop, min_stop)  # Not too far
    stop = min(stop, max_stop)      # Not too close
    return round(stop, 2)


# ─── Helper: Target Price ──────────────────────────────────────────

def _calculate_target(
    current_price: float, stop_loss: float,
    resistance_levels: Optional[list] = None,
) -> float:
    """
    Primary target: first resistance level above price (if it offers >= 1.5:1 R:R).
    Fallback: 2:1 risk-reward, capped at 20% (NEPSE upper circuit is 10%/day).
    """
    risk = abs(current_price - stop_loss)
    if risk <= 0:
        return round(current_price * 1.05, 2)

    rr2_target = current_price + (2.0 * risk)

    # Prefer a resistance level that gives at least 1.5:1 R:R
    if resistance_levels:
        for res in resistance_levels:
            if res > current_price:
                r_reward = res - current_price
                if r_reward / risk >= 1.5:
                    # Use resistance as target (cap at +20%)
                    return round(min(res * 0.998, current_price * 1.20), 2)

    return round(min(rr2_target, current_price * 1.20), 2)


# ─── Helper: Support & Resistance ──────────────────────────────────

def _compute_support_resistance(df: pd.DataFrame, lookback: int = 50) -> tuple[list[float], list[float]]:
    n = len(df)
    if n < 5:
        return [], []
    highs = df["high"].values
    lows = df["low"].values
    close = float(df["close"].iloc[-1])
    start = max(0, n - lookback)

    swing_highs = []
    swing_lows = []
    for i in range(start + 2, n - 2):
        if (highs[i] > highs[i-1] and highs[i] > highs[i-2] and
                highs[i] > highs[i+1] and highs[i] > highs[i+2]):
            swing_highs.append(float(highs[i]))
        if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and
                lows[i] < lows[i+1] and lows[i] < lows[i+2]):
            swing_lows.append(float(lows[i]))

    supports = sorted(set(round(s, 2) for s in swing_lows if s < close), reverse=True)[:3]
    resistances = sorted(set(round(r, 2) for r in swing_highs if r > close))[:3]
    return supports, resistances


# ─── Helper: Fibonacci Retracement ─────────────────────────────────

def _compute_fibonacci(df: pd.DataFrame, lookback: int = 100) -> list[FibonacciLevel]:
    n = len(df)
    if n < 10:
        return []
    start = max(0, n - lookback)
    recent = df.iloc[start:]
    swing_high = float(recent["high"].max())
    swing_low = float(recent["low"].min())
    if swing_high <= swing_low:
        return []
    diff = swing_high - swing_low
    ratios = [
        ("0%", swing_low), ("23.6%", swing_low + 0.236 * diff),
        ("38.2%", swing_low + 0.382 * diff), ("50%", swing_low + 0.5 * diff),
        ("61.8%", swing_low + 0.618 * diff), ("78.6%", swing_low + 0.786 * diff),
        ("100%", swing_high),
    ]
    return [FibonacciLevel(level=l, price=round(p, 2)) for l, p in ratios]


# ─── Helper: Pivot Points (Classic) ────────────────────────────────

def _compute_pivot_points(df: pd.DataFrame) -> Optional[PivotPoints]:
    if len(df) < 2:
        return None
    prev = df.iloc[-2]
    h, l, c = float(prev["high"]), float(prev["low"]), float(prev["close"])
    pp = (h + l + c) / 3
    return PivotPoints(
        pp=round(pp, 2),
        r1=round(2 * pp - l, 2), r2=round(pp + (h - l), 2), r3=round(h + 2 * (pp - l), 2),
        s1=round(2 * pp - h, 2), s2=round(pp - (h - l), 2), s3=round(l - 2 * (h - pp), 2),
    )


# ─── Helper: OBV Trend ─────────────────────────────────────────────

def _compute_obv_trend(df: pd.DataFrame) -> Optional[str]:
    if len(df) < 20 or "volume" not in df.columns:
        return None
    try:
        obv = df.ta.obv()
        if obv is None or obv.empty:
            return None
        obv_sma = obv.rolling(20).mean()
        latest_obv = float(obv.iloc[-1])
        latest_sma = float(obv_sma.iloc[-1])
        if pd.isna(latest_sma):
            return None
        if latest_obv > latest_sma * 1.02:
            return "Rising"
        elif latest_obv < latest_sma * 0.98:
            return "Falling"
        return "Flat"
    except Exception:
        return None


# ─── Helper: 52-Week Range ─────────────────────────────────────────

def _compute_52w_range(df: pd.DataFrame, price: float) -> tuple:
    n = min(len(df), 252)
    if n < 20:
        return None, None, None, None
    recent = df.tail(n)
    high_52w = round(float(recent["high"].max()), 2)
    low_52w = round(float(recent["low"].min()), 2)
    pct_high = round(((price - high_52w) / high_52w) * 100, 2) if high_52w > 0 else None
    pct_low = round(((price - low_52w) / low_52w) * 100, 2) if low_52w > 0 else None
    return high_52w, low_52w, pct_high, pct_low


# ─── Helper: MA Crossover Detection ────────────────────────────────

def _compute_ma_crossover(df: pd.DataFrame) -> Optional[str]:
    if len(df) < 200:
        return None
    try:
        sma50 = df["close"].rolling(50).mean()
        sma200 = df["close"].rolling(200).mean()
        curr_50, curr_200 = float(sma50.iloc[-1]), float(sma200.iloc[-1])
        prev_50, prev_200 = float(sma50.iloc[-2]), float(sma200.iloc[-2])
        if pd.isna(curr_50) or pd.isna(curr_200) or pd.isna(prev_50) or pd.isna(prev_200):
            return None
        if prev_50 <= prev_200 and curr_50 > curr_200:
            return "Golden Cross"
        elif prev_50 >= prev_200 and curr_50 < curr_200:
            return "Death Cross"
        elif curr_50 > curr_200:
            return "Bullish (50 > 200)"
        else:
            return "Bearish (50 < 200)"
    except Exception:
        return None


# ─── Helper: OHLCV Resampling ──────────────────────────────────────

def _resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return df.resample(rule).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna()


# ─── Helper: Mini Analysis (for multi-TF) ──────────────────────────

def _mini_analysis(df: pd.DataFrame) -> dict:
    if len(df) < 2:
        return {
            "verdict": "N/A", "confidence": 0, "rsi_14": None,
            "macd_signal": None, "trend": "UNKNOWN", "trend_strength": None,
            "sma_20": None, "sma_50": None, "ema_10": None, "ema_30": None,
            "patterns": [],
        }

    # Short-bar path for long TFs (Semi-Yearly, Yearly) with < 14 bars
    if len(df) < 14:
        # Adaptive RSI with shorter period, validated to 0-100 range
        rsi = None
        rsi_len = min(len(df) - 1, 14)
        if rsi_len >= 2:
            try:
                rsi_val = _safe_val(df.ta.rsi(length=rsi_len))
                if rsi_val is not None and 0 <= rsi_val <= 100:
                    rsi = round(rsi_val, 2)
            except Exception:
                pass

        # Simple trend from price direction with 2% buffer
        first = float(df['close'].iloc[0])
        last = float(df['close'].iloc[-1])
        if last > first * 1.02:
            trend = "UPTREND"
        elif last < first * 0.98:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"

        # Verdict from trend + RSI
        if trend == "UPTREND":
            verdict, confidence = "BUY", 60
        elif trend == "DOWNTREND":
            verdict, confidence = "SELL", 60
        else:
            verdict, confidence = "HOLD", 50
        if rsi is not None:
            if rsi < 30:
                verdict, confidence = "BUY", max(confidence, 65)
            elif rsi > 70:
                verdict, confidence = "SELL", max(confidence, 65)

        return {
            "verdict": verdict, "confidence": confidence, "rsi_14": rsi,
            "macd_signal": None, "trend": trend, "trend_strength": None,
            "sma_20": None, "sma_50": None, "ema_10": None, "ema_30": None,
            "patterns": [],
        }

    indicators = _compute_indicators(df)
    patterns = _detect_patterns(df)
    operator_activity, volume_ratio = _detect_operator_activity(df)
    trend, trend_strength = _determine_trend(df, indicators)
    verdict, confidence = _generate_verdict(
        patterns=patterns, indicators=indicators,
        operator_activity=operator_activity, trend=trend,
        trend_strength=trend_strength, volume_ratio=volume_ratio,
    )
    return {
        "verdict": verdict, "confidence": confidence,
        "rsi_14": indicators.get("rsi_14"), "macd_signal": indicators.get("macd_signal"),
        "trend": trend, "trend_strength": trend_strength,
        "sma_20": indicators.get("sma_20"), "sma_50": indicators.get("sma_50"),
        "ema_10": indicators.get("ema_10"), "ema_30": indicators.get("ema_30"),
        "patterns": patterns,
    }


# ─── Helper: Multi-Timeframe Analysis ──────────────────────────────

def _multi_timeframe_analysis(df: pd.DataFrame, resolution: str) -> list[TimeframeAnalysis]:
    results = []
    res = resolution.upper().strip()

    # ── Intraday (1‑45 minute) → resample to Hourly + Daily ──
    if res in ("1", "2", "3", "5", "10", "15", "30", "45"):
        try:
            hourly = _resample_ohlcv(df, "h")
            if len(hourly) >= 14:
                a = _mini_analysis(hourly)
                results.append(TimeframeAnalysis(timeframe="Hourly", **a))
        except Exception:
            pass
        try:
            daily = _resample_ohlcv(df, "D")
            if len(daily) >= 14:
                a = _mini_analysis(daily)
                results.append(TimeframeAnalysis(timeframe="Daily", **a))
        except Exception:
            pass

    # ── Hourly variants (1H–4H) → Daily + Weekly + Monthly + Quarterly ──
    elif res in ("60", "1H", "120", "2H", "180", "3H", "240", "4H"):
        tf_specs = [
            ("D",   "Daily"),
            ("W",   "Weekly"),
            ("ME",  "Monthly"),
            ("QE",  "Quarterly"),
        ]
        for rule, label in tf_specs:
            try:
                resampled = _resample_ohlcv(df, rule)
                if len(resampled) >= 14:
                    a = _mini_analysis(resampled)
                    results.append(TimeframeAnalysis(timeframe=label, **a))
            except Exception:
                pass

    # ── Daily (1D, D) → Weekly + Bi-Weekly + Monthly + Quarterly + Semi-Yearly + Yearly ──
    elif res in ("1D", "D", "2D", "3D"):
        tf_specs = [
            ("W",   "Weekly",      14),
            ("14D", "Bi-Weekly",   14),
            ("ME",  "Monthly",     10),
            ("QE",  "Quarterly",    6),
            ("2QE", "Semi-Yearly",  3),
            ("YE",  "Yearly",       2),
        ]
        for rule, label, min_bars in tf_specs:
            try:
                resampled = _resample_ohlcv(df, rule)
                if len(resampled) >= min_bars:
                    a = _mini_analysis(resampled)
                    results.append(TimeframeAnalysis(timeframe=label, **a))
            except Exception:
                pass

    # ── Weekly (1W, W) → Monthly + Quarterly + Semi-Yearly + Yearly ──
    elif res in ("1W", "W"):
        tf_specs = [
            ("ME",  "Monthly",      6),
            ("QE",  "Quarterly",    4),
            ("2QE", "Semi-Yearly",  3),
            ("YE",  "Yearly",       2),
        ]
        for rule, label, min_bars in tf_specs:
            try:
                resampled = _resample_ohlcv(df, rule)
                if len(resampled) >= min_bars:
                    a = _mini_analysis(resampled)
                    results.append(TimeframeAnalysis(timeframe=label, **a))
            except Exception:
                pass

    # ── Monthly (1M, M) → resample to Quarterly + Yearly ──
    elif res in ("1M", "M"):
        try:
            quarterly = _resample_ohlcv(df, "QE")
            if len(quarterly) >= 4:
                a = _mini_analysis(quarterly)
                results.append(TimeframeAnalysis(timeframe="Quarterly", **a))
        except Exception:
            pass
        try:
            yearly = _resample_ohlcv(df, "YE")
            if len(yearly) >= 2:
                a = _mini_analysis(yearly)
                results.append(TimeframeAnalysis(timeframe="Yearly", **a))
        except Exception:
            pass

    # ── 3-Month (3M) or 6-Month (6M) bars → resample to Yearly ──
    elif res in ("3M", "6M"):
        try:
            yearly = _resample_ohlcv(df, "YE")
            if len(yearly) >= 2:
                a = _mini_analysis(yearly)
                results.append(TimeframeAnalysis(timeframe="Yearly", **a))
        except Exception:
            pass

    return results


# ─── Helper: Signal Summaries (TradingView-style) ──────────────────

def _compute_signal_summaries(
    indicators: dict, current_price: float,
) -> tuple[list[IndicatorSignal], list[IndicatorSignal]]:
    osc_signals: list[IndicatorSignal] = []
    ma_signals: list[IndicatorSignal] = []

    # Oscillators
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        sig = "Buy" if rsi < 30 else ("Sell" if rsi > 70 else "Neutral")
        osc_signals.append(IndicatorSignal(name="RSI(14)", value=rsi, signal=sig))

    stoch_k = indicators.get("stochrsi_k")
    if stoch_k is not None:
        sig = "Buy" if stoch_k < 20 else ("Sell" if stoch_k > 80 else "Neutral")
        osc_signals.append(IndicatorSignal(name="StochRSI", value=stoch_k, signal=sig))

    wr = indicators.get("williams_r")
    if wr is not None:
        sig = "Buy" if wr < -80 else ("Sell" if wr > -20 else "Neutral")
        osc_signals.append(IndicatorSignal(name="W%R(14)", value=wr, signal=sig))

    cci = indicators.get("cci_20")
    if cci is not None:
        sig = "Buy" if cci < -100 else ("Sell" if cci > 100 else "Neutral")
        osc_signals.append(IndicatorSignal(name="CCI(20)", value=cci, signal=sig))

    roc = indicators.get("roc_14")
    if roc is not None:
        sig = "Buy" if roc > 5 else ("Sell" if roc < -5 else "Neutral")
        osc_signals.append(IndicatorSignal(name="ROC(14)", value=roc, signal=sig))

    macd_sig = indicators.get("macd_signal")
    if macd_sig is not None:
        sig = "Buy" if macd_sig == "Bullish" else ("Sell" if macd_sig == "Bearish" else "Neutral")
        osc_signals.append(IndicatorSignal(name="MACD", value=indicators.get("macd_histogram"), signal=sig))

    # Moving Averages
    for name, key in [("EMA(10)", "ema_10"), ("EMA(20)", "ema_20"), ("EMA(30)", "ema_30"),
                       ("EMA(50)", "ema_50"), ("SMA(20)", "sma_20"), ("SMA(50)", "sma_50"),
                       ("SMA(200)", "sma_200")]:
        val = indicators.get(key)
        if val is not None:
            sig = "Buy" if current_price > val else "Sell"
            ma_signals.append(IndicatorSignal(name=name, value=round(val, 2), signal=sig))

    return osc_signals, ma_signals


def _summarize_signals(signals: list[IndicatorSignal]) -> Optional[str]:
    if not signals:
        return None
    buys = sum(1 for s in signals if s.signal == "Buy")
    sells = sum(1 for s in signals if s.signal == "Sell")
    if buys > sells + 2:
        return "Strong Buy"
    elif buys > sells:
        return "Buy"
    elif sells > buys + 2:
        return "Strong Sell"
    elif sells > buys:
        return "Sell"
    return "Neutral"


def _overall_summary(osc: Optional[str], ma: Optional[str]) -> Optional[str]:
    if not osc and not ma:
        return None
    score_map = {"Strong Buy": 2, "Buy": 1, "Neutral": 0, "Sell": -1, "Strong Sell": -2}
    total, count = 0, 0
    if osc:
        total += score_map.get(osc, 0)
        count += 1
    if ma:
        total += score_map.get(ma, 0)
        count += 1
    if count == 0:
        return None
    avg = total / count
    if avg >= 1.5:
        return "Strong Buy"
    elif avg >= 0.5:
        return "Buy"
    elif avg <= -1.5:
        return "Strong Sell"
    elif avg <= -0.5:
        return "Sell"
    return "Neutral"


# ─── Helper: Verdict Generator ─────────────────────────────────────

def _generate_verdict(
    patterns: list[PatternInfo],
    indicators: dict,
    operator_activity: bool,
    trend: str,
    trend_strength: Optional[float],
    volume_ratio: float,
    multi_tf: Optional[list] = None,
) -> tuple[str, int]:
    score = 0

    # RSI
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if rsi < 30:
            score += 3
        elif rsi < 40:
            score += 1
        elif rsi > 70:
            score -= 3
        elif rsi > 60:
            score -= 1

    # Trend
    if trend == "UPTREND":
        score += 2
    elif trend == "DOWNTREND":
        score -= 2

    # MACD
    macd = indicators.get("macd_signal")
    if macd == "Bullish":
        score += 1
    elif macd == "Bearish":
        score -= 1

    # BB %B
    pct_b = indicators.get("bb_pct_b")
    if pct_b is not None:
        if pct_b < 0.0:
            score += 2
        elif pct_b < 0.2:
            score += 1
        elif pct_b > 1.0:
            score -= 2
        elif pct_b > 0.8:
            score -= 1

    # Patterns
    latest_patterns = [p for p in patterns if p.bar_index == 0]
    bullish_count = sum(1 for p in latest_patterns if p.direction == "Bullish")
    bearish_count = sum(1 for p in latest_patterns if p.direction == "Bearish")
    if bullish_count > 0:
        score += min(bullish_count, 3)
    if bearish_count > 0:
        score -= min(bearish_count, 3)
    for p in latest_patterns:
        if abs(p.strength) >= 200:
            score += 1 if p.direction == "Bullish" else -1

    # Operator Activity
    if operator_activity:
        if bullish_count > bearish_count:
            score += 1
        elif bearish_count > bullish_count:
            score -= 2

    # StochRSI
    stoch_k = indicators.get("stochrsi_k")
    stoch_d = indicators.get("stochrsi_d")
    if stoch_k is not None and stoch_d is not None:
        if stoch_k > stoch_d and stoch_k < 30:
            score += 1
        elif stoch_k < stoch_d and stoch_k > 70:
            score -= 1

    # Williams %R
    wr = indicators.get("williams_r")
    if wr is not None:
        if wr < -80:
            score += 1
        elif wr > -20:
            score -= 1

    # CCI
    cci = indicators.get("cci_20")
    if cci is not None:
        if cci < -100:
            score += 1
        elif cci > 100:
            score -= 1

    # ADX trend strength — strong confirmed trend adds conviction
    adx = indicators.get("adx_14")
    di_plus = indicators.get("di_plus")
    di_minus = indicators.get("di_minus")
    if adx is not None and adx > 25:
        if trend == "UPTREND" and (di_plus or 0) > (di_minus or 0):
            score += 1
        elif trend == "DOWNTREND" and (di_minus or 0) > (di_plus or 0):
            score -= 1
    # Weak ADX → sideways, reduce conviction on trend signals
    if adx is not None and adx < 20 and trend in ("UPTREND", "DOWNTREND"):
        score = int(score * 0.7)  # Dampen by 30% — indeterminate market

    # Multi-TF Confluence — same direction across timeframes is a strong signal
    if multi_tf:
        bullish_tf = sum(1 for tf in multi_tf if tf.verdict in ("BUY", "STRONG BUY"))
        bearish_tf = sum(1 for tf in multi_tf if tf.verdict in ("SELL", "STRONG SELL"))
        total_tf = len(multi_tf)
        if total_tf > 0:
            if bullish_tf == total_tf:
                score += 3  # All higher TF agree → strong
            elif bullish_tf > bearish_tf * 2:
                score += 2  # Clear majority bullish
            elif bullish_tf > bearish_tf:
                score += 1
            elif bearish_tf == total_tf:
                score -= 3
            elif bearish_tf > bullish_tf * 2:
                score -= 2
            elif bearish_tf > bullish_tf:
                score -= 1

    # Map score to verdict — HOLD covers -1 to +3 (mixed signals)
    if score >= 8:
        verdict = "STRONG BUY"
        confidence = min(95, 72 + score * 2)
    elif score >= 4:
        verdict = "BUY"
        confidence = min(85, 55 + score * 4)
    elif score >= -1:
        verdict = "HOLD"
        confidence = min(65, 50 + abs(score) * 5)
    elif score >= -6:
        verdict = "SELL"
        confidence = min(80, 45 + abs(score) * 5)
    else:
        verdict = "STRONG SELL"
        confidence = min(95, 72 + abs(score) * 2)

    return verdict, confidence


# ─── Helper: Breakout Detection ─────────────────────────────────────

def _detect_breakout(
    df: pd.DataFrame, current_price: float,
    resistance_levels: list[float], support_levels: list[float],
    volume_ratio: float, indicators: dict,
) -> Optional[str]:
    """Detect breakout/breakdown based on S/R, volume, and BB position."""
    bb_upper = indicators.get("bb_upper")
    bb_lower = indicators.get("bb_lower")

    # Bullish breakout: price above resistance with volume
    if resistance_levels and current_price > resistance_levels[0] * 0.998:
        if volume_ratio >= 1.5:
            return "Bullish Breakout ▲"
        return "Testing Resistance"

    # Bearish breakdown: price below support with volume
    if support_levels and current_price < support_levels[0] * 1.002:
        if volume_ratio >= 1.5:
            return "Bearish Breakdown ▼"
        return "Testing Support"

    # BB breakout
    if bb_upper and current_price > bb_upper:
        return "BB Upper Breakout ▲"
    if bb_lower and current_price < bb_lower:
        return "BB Lower Breakdown ▼"

    # Near breakout zones
    if resistance_levels:
        dist_r = (resistance_levels[0] - current_price) / current_price * 100
        if dist_r < 1.5:
            return "Near Breakout Zone"

    if support_levels:
        dist_s = (current_price - support_levels[0]) / current_price * 100
        if dist_s < 1.5:
            return "Near Breakdown Zone"

    return "Range-Bound"


# ─── Helper: Market Structure ───────────────────────────────────────

def _detect_market_structure(df: pd.DataFrame) -> Optional[str]:
    """Detect Higher Highs/Lows or Lower Highs/Lows pattern."""
    n = len(df)
    if n < 20:
        return None

    highs = df["high"].values
    lows = df["low"].values

    # Find swing highs and lows using 5-bar lookback
    swing_highs = []
    swing_lows = []
    for i in range(5, n - 5):
        if all(highs[i] >= highs[i - j] for j in range(1, 6)) and \
           all(highs[i] >= highs[i + j] for j in range(1, 6)):
            swing_highs.append((i, float(highs[i])))
        if all(lows[i] <= lows[i - j] for j in range(1, 6)) and \
           all(lows[i] <= lows[i + j] for j in range(1, 6)):
            swing_lows.append((i, float(lows[i])))

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "Developing"

    # Check last two swings
    hh = swing_highs[-1][1] > swing_highs[-2][1]  # Higher High
    hl = swing_lows[-1][1] > swing_lows[-2][1]     # Higher Low
    lh = swing_highs[-1][1] < swing_highs[-2][1]   # Lower High
    ll = swing_lows[-1][1] < swing_lows[-2][1]     # Lower Low

    if hh and hl:
        return "HH/HL — Bullish Structure"
    elif lh and ll:
        return "LH/LL — Bearish Structure"
    elif hh and ll:
        return "Expanding Range"
    elif lh and hl:
        return "Contracting (Squeeze)"
    return "Transitioning"


# ─── Helper: Momentum Status ───────────────────────────────────────

def _detect_momentum_status(indicators: dict) -> Optional[str]:
    """Detect momentum acceleration/deceleration."""
    roc = indicators.get("roc_14")
    macd_hist = indicators.get("macd_histogram")
    rsi = indicators.get("rsi_14")

    if roc is None:
        return None

    if roc > 5:
        if macd_hist and macd_hist > 0:
            return "Strong Bullish Momentum ▲▲"
        return "Bullish Momentum ▲"
    elif roc > 0:
        if macd_hist and macd_hist > 0:
            return "Positive & Accelerating"
        return "Mildly Positive"
    elif roc > -5:
        if macd_hist and macd_hist < 0:
            return "Negative & Decelerating"
        return "Mildly Negative"
    else:
        if macd_hist and macd_hist < 0:
            return "Strong Bearish Momentum ▼▼"
        return "Bearish Momentum ▼"


# ─── Helper: Volume Profile ────────────────────────────────────────

def _detect_volume_profile(df: pd.DataFrame) -> Optional[str]:
    """Classify volume as Accumulation / Distribution / Neutral.

    Uses two signals:
    1. OBV divergence: price direction vs money-flow direction.
       OBV rising + price flat/down = smart money accumulating.
    2. Body-weighted up/down volume ratio over last 20 bars.
       Larger candle bodies carry proportionally more weight so
       genuine big moves are not diluted by small doji days.
    """
    if len(df) < 20 or "volume" not in df.columns:
        return None

    recent = df.tail(20).reset_index(drop=True)
    n = len(recent)

    # Signal 1: OBV slope vs price slope
    obv = 0.0
    obv_mid = 0.0
    for i in range(1, n):
        c_cur = recent.iloc[i]["close"]
        c_prev = recent.iloc[i - 1]["close"]
        vol = recent.iloc[i]["volume"]
        if c_cur > c_prev:
            obv += vol
        elif c_cur < c_prev:
            obv -= vol
        if i == 10:
            obv_mid = obv

    obv_rising = obv > obv_mid
    prices = recent["close"].values
    price_rising = float(prices[-5:].mean()) > float(prices[:10].mean())

    # OBV-price divergence: strongest signals
    if obv_rising and not price_rising:
        return "Accumulation (Smart Money Buying)"
    if not obv_rising and price_rising:
        return "Distribution (Smart Money Selling)"

    # Signal 2: body-weighted up/down volume
    up_vol_w = 0.0
    dn_vol_w = 0.0
    for i in range(n):
        row = recent.iloc[i]
        body_pct = abs(row["close"] - row["open"]) / max(abs(row["open"]), 1e-6)
        weight = 1.0 + body_pct * 8   # bigger candle bodies carry more weight
        if row["close"] >= row["open"]:
            up_vol_w += row["volume"] * weight
        else:
            dn_vol_w += row["volume"] * weight

    total_w = up_vol_w + dn_vol_w
    if total_w <= 0:
        return "Neutral Volume"

    ratio = up_vol_w / total_w
    if ratio > 0.68:
        return "Accumulation (Buying Pressure)"
    elif ratio < 0.32:
        return "Distribution (Selling Pressure)"
    elif ratio > 0.57:
        return "Mild Accumulation"
    elif ratio < 0.43:
        return "Mild Distribution"
    return "Neutral Volume"


# ─── Helper: BB Position ───────────────────────────────────────────

def _detect_bb_position(current_price: float, indicators: dict) -> Optional[str]:
    """Classify price position relative to Bollinger Bands."""
    bb_upper = indicators.get("bb_upper")
    bb_lower = indicators.get("bb_lower")
    bb_middle = indicators.get("bb_middle")
    pct_b = indicators.get("bb_pct_b")

    if bb_upper is None or bb_lower is None:
        return None

    if current_price > bb_upper:
        return "Above Upper Band — Overbought"
    elif current_price < bb_lower:
        return "Below Lower Band — Oversold"
    elif pct_b is not None:
        if pct_b > 0.8:
            return "Near Upper Band — Resistance Zone"
        elif pct_b < 0.2:
            return "Near Lower Band — Support Zone"
        elif 0.4 <= pct_b <= 0.6:
            return "Mid-Band — Neutral Zone"
        elif pct_b > 0.5:
            return "Upper Half — Bullish Bias"
        else:
            return "Lower Half — Bearish Bias"
    return None


# ─── Helper: RSI Divergence Detection ──────────────────────────────

def _detect_rsi_divergence(df: pd.DataFrame) -> Optional[str]:
    """Detect bullish/bearish RSI divergence using a two-window comparison.

    Approach (matches how traders actually spot divergence on a chart):
      - Split the recent history into two consecutive windows (each ~60 bars).
      - Bearish: the MOST SIGNIFICANT HIGH in the recent window is higher in
        price but lower in RSI than the most significant high in the prior
        window → buyers are losing momentum while price still rises.
      - Bullish: the MOST SIGNIFICANT LOW in the recent window is lower in
        price but higher in RSI than the most significant low in the prior
        window → sellers are losing momentum while price still falls.
    This avoids the micro-pivot noise problem where a 3-bar pivot rule finds
    dozens of tiny zigzags inside a trend that individually show nothing.
    """
    n = len(df)
    if n < 50:
        return None

    try:
        rsi_series = df.ta.rsi(length=14)
        if rsi_series is None or len(rsi_series) < 20:
            return None

        closes = df["close"].values
        rsi_vals = rsi_series.values

        # Two equal windows covering the last ~120 bars
        win = min(60, n // 2 - 1)
        recent_start = n - win
        prior_start  = n - win * 2
        prior_end    = recent_start

        # Exclude the very last bar (possibly incomplete / just opened)
        recent_slice = closes[recent_start : n - 1]
        prior_slice  = closes[prior_start : prior_end]

        if len(recent_slice) < 10 or len(prior_slice) < 10:
            return None

        # ── Bearish divergence ────────────────────────────────────────────
        r_high_rel = int(np.argmax(recent_slice))        # index within slice
        p_high_rel = int(np.argmax(prior_slice))
        r_high_idx = recent_start + r_high_rel           # absolute index
        p_high_idx = prior_start + p_high_rel

        if not (pd.isna(rsi_vals[r_high_idx]) or pd.isna(rsi_vals[p_high_idx])):
            price_r = float(closes[r_high_idx])
            price_p = float(closes[p_high_idx])
            rsi_r   = float(rsi_vals[r_high_idx])
            rsi_p   = float(rsi_vals[p_high_idx])
            # Price made a higher high but RSI dropped ≥ 3 points
            if price_r > price_p * 1.005 and rsi_r < rsi_p - 3.0:
                return "Bearish Divergence — Reversal Signal"

        # ── Bullish divergence ────────────────────────────────────────────
        r_low_rel = int(np.argmin(recent_slice))
        p_low_rel = int(np.argmin(prior_slice))
        r_low_idx = recent_start + r_low_rel
        p_low_idx = prior_start + p_low_rel

        if not (pd.isna(rsi_vals[r_low_idx]) or pd.isna(rsi_vals[p_low_idx])):
            price_r = float(closes[r_low_idx])
            price_p = float(closes[p_low_idx])
            rsi_r   = float(rsi_vals[r_low_idx])
            rsi_p   = float(rsi_vals[p_low_idx])
            # Price made a lower low but RSI rose ≥ 3 points
            if price_r < price_p * 0.995 and rsi_r > rsi_p + 3.0:
                return "Bullish Divergence — Reversal Signal"

    except Exception:
        return None

    return None


# ─── Helper: Market Phase (Wyckoff) ────────────────────────────────

def _detect_market_phase(
    trend: str, volume_profile: Optional[str],
    indicators: dict, market_structure: Optional[str],
) -> Optional[str]:
    """Wyckoff-style market phase detection."""
    adx = indicators.get("adx_14")
    rsi = indicators.get("rsi_14")

    if trend == "UPTREND":
        if volume_profile and "Accumulation" in volume_profile:
            return "Markup Phase — Active Uptrend with Buying"
        if adx and adx > 25:
            return "Markup Phase — Strong Uptrend"
        return "Early Markup — Uptrend Developing"

    if trend == "DOWNTREND":
        if volume_profile and "Distribution" in volume_profile:
            return "Markdown Phase — Active Downtrend with Selling"
        if adx and adx > 25:
            return "Markdown Phase — Strong Downtrend"
        return "Early Markdown — Downtrend Developing"

    # Sideways
    if market_structure and "Contracting" in market_structure:
        if volume_profile and "Accumulation" in volume_profile:
            return "Accumulation Phase — Smart Money Buying"
        if volume_profile and "Distribution" in volume_profile:
            return "Distribution Phase — Smart Money Selling"
        return "Consolidation — Preparing for Breakout"

    if rsi and 40 <= rsi <= 60:
        return "Accumulation/Distribution — Watch for Direction"

    return "Transitional Phase"


# ─── Helper: Nearest S/R with Distance ─────────────────────────────

def _compute_nearest_sr(
    current_price: float,
    support_levels: list[float],
    resistance_levels: list[float],
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Find nearest support/resistance with distance percentages."""
    nearest_s = support_levels[0] if support_levels else None
    nearest_r = resistance_levels[0] if resistance_levels else None

    s_dist_pct = round((current_price - nearest_s) / current_price * 100, 2) if nearest_s else None
    r_dist_pct = round((nearest_r - current_price) / current_price * 100, 2) if nearest_r else None

    return nearest_s, nearest_r, s_dist_pct, r_dist_pct


# ─── Helper: Warning Generator ─────────────────────────────────────

def _generate_warnings(
    df: pd.DataFrame, indicators: dict,
    operator_activity: bool, volume_ratio: float,
    resolution: str, ma_crossover: Optional[str] = None,
) -> list[str]:
    warnings = []
    close = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-2] if len(df) > 1 else close

    # Warn when there are too few bars for reliable indicators (happens with
    # high intraday timeframes like 2H/4H where 1000 base 1-min bars yield
    # only a handful of resampled candles).
    if len(df) < 30:
        warnings.append(
            f"⚠️ Only {len(df)} bars available — some indicators may be unreliable. "
            "Switch to a lower timeframe for more data."
        )

    daily_change_pct = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0
    if abs(daily_change_pct) > 8:
        remaining = 10 - abs(daily_change_pct)
        warnings.append(
            f"⚡ Near circuit breaker! Only {remaining:.1f}% "
            f"{'upside' if daily_change_pct > 0 else 'downside'} remaining"
        )

    if operator_activity:
        warnings.append(
            f"🚨 Volume anomaly: {volume_ratio:.1f}x average — possible operator activity"
        )

    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if rsi > 80:
            warnings.append(f"🔴 RSI at {rsi:.0f} — extremely overbought, reversal likely")
        elif rsi < 20:
            warnings.append(f"🟢 RSI at {rsi:.0f} — extremely oversold, bounce possible")

    atr = indicators.get("atr_14")
    if atr is not None and close > 0:
        atr_pct = (atr / close) * 100
        if atr_pct < 1.5:
            warnings.append("📉 Low volatility (ATR squeeze) — expect breakout soon")

    if ma_crossover:
        if "Golden Cross" == ma_crossover:
            warnings.append("✨ Golden Cross: SMA50 crossed above SMA200 — bullish long-term")
        elif "Death Cross" == ma_crossover:
            warnings.append("💀 Death Cross: SMA50 crossed below SMA200 — bearish long-term")

    if resolution in ("1", "3", "5", "15", "30"):
        warnings.append("⏱️ Intraday data — patterns less reliable than daily/weekly")

    if resolution == "60":
        warnings.append("🕐 Hourly data — good for entry timing, confirm with daily chart")

    if resolution in ("1D", "D"):
        warnings.append("📅 NEPSE T+2 settlement: minimum 3 trading days hold")

    if resolution in ("1W", "W"):
        warnings.append("📆 Weekly chart — signals play out over 2–6 weeks")

    if resolution in ("1M", "M"):
        warnings.append("📊 Monthly chart — investor-grade signals, 3–12 month horizon")

    if resolution in ("3M", "6M"):
        warnings.append("📈 Macro chart — strategic positioning, 1–5 year horizon")

    return warnings


# ─── Run ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
