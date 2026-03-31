"""
Composite Signal Score (CSS) Engine — Replaces arbitrary weight system.

Generates a statistically derived 0-1 score from 6 components:
  1. TREND      — EMA alignment, ADX, Supertrend direction
  2. MOMENTUM   — RSI zone, StochRSI crossover
  3. VOLUME     — RVOL, OBV trend, A/D line trend
  4. VOLATILITY — Bollinger %B, squeeze detection, ATR trend
  5. OPERATOR   — Broker concentration, buyer dominance, distribution risk
  6. FUNDAMENTAL — Sector-specific PE, ROE, dividend history

Signal thresholds:
  STRONG_BUY  >= 0.75    (market_regime != BEAR)
  BUY         >= 0.60    (market_regime != PANIC)
  WEAK_BUY    >= 0.50    (market_regime == BULL only)
  HOLD        0.35-0.50
  WEAK_SELL   < 0.35     (when holding)
  SELL        < 0.25     (when holding)
  STRONG_SELL < 0.15     (or market_regime == PANIC)

Signal freshness decay: confidence *= 0.8^(days_since_signal)
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Optional, Any
from loguru import logger
import math
import pandas as pd

from analysis.quant_indicators import QuantIndicators
from core.config import settings


# ============================================================
# CSS Weight Profiles (initial — refined by walk-forward later)
# ============================================================

CSS_WEIGHTS = {
    "short_term": {  # 5-day trades
        "trend": 0.20,
        "momentum": 0.25,
        "volume": 0.25,
        "volatility": 0.15,
        "operator": 0.15,
        "fundamental": 0.00,
    },
    "swing": {  # 10-20 day trades (default)
        "trend": 0.25,
        "momentum": 0.20,
        "volume": 0.20,
        "volatility": 0.10,
        "operator": 0.15,
        "fundamental": 0.10,
    },
    "investment": {  # 60+ day holds
        "trend": 0.15,
        "momentum": 0.10,
        "volume": 0.10,
        "volatility": 0.05,
        "operator": 0.10,
        "fundamental": 0.50,
    },
}


@dataclass
class CSSResult:
    """Result of Composite Signal Score computation."""
    symbol: str
    date: date
    css: float = 0.0  # 0-1 composite score

    # Component scores (all 0-1)
    trend_score: float = 0.0
    momentum_score: float = 0.0
    volume_score: float = 0.0
    volatility_score: float = 0.0
    operator_score: float = 0.0
    fundamental_score: float = 0.0

    # Signal
    signal: str = "HOLD"  # STRONG_BUY, BUY, WEAK_BUY, HOLD, WEAK_SELL, SELL, STRONG_SELL
    confidence: float = 0.0  # 0-100

    # Indicator snapshot (for audit trail)
    indicators: Dict[str, Any] = field(default_factory=dict)

    # Trade parameters
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_price: float = 0.0
    position_size_pct: float = 0.0

    @property
    def risk_reward(self) -> float:
        if self.entry_price <= 0 or self.stop_loss <= 0:
            return 0
        risk = self.entry_price - self.stop_loss
        reward = self.target_price - self.entry_price
        return round(reward / risk, 2) if risk > 0 else 0


def compute_trend_score(ind: Dict[str, float]) -> float:
    """TREND Score (0-1): EMA alignment + ADX strength + Supertrend."""
    score = 0.0
    ema10 = ind.get("ema10", 0)
    ema30 = ind.get("ema30", 0)
    adx = ind.get("adx", 0)
    st_dir = ind.get("supertrend_dir", 0)

    # EMA alignment (0-0.3)
    if ema30 > 0 and ema10 > ema30:
        alignment = min(1.0, (ema10 / ema30 - 1) * 20)
        score += 0.3 * alignment

    # ADX strength (0-0.4) — ADX > 20 = trend worth trading for NEPSE
    if adx > 15:
        score += 0.4 * min(1.0, (adx - 15) / 35)

    # Supertrend direction (0-0.3)
    if st_dir == 1:
        score += 0.3

    return min(1.0, score)


def compute_momentum_score(ind: Dict[str, float]) -> float:
    """MOMENTUM Score (0-1): RSI zone + StochRSI crossover."""
    score = 0.0
    rsi = ind.get("rsi", 50)
    k = ind.get("stochrsi_k", 50)
    d = ind.get("stochrsi_d", 50)

    # RSI zone (0-0.5)
    if 40 <= rsi <= 60:
        score += 0.5  # Optimal momentum zone
    elif 30 <= rsi < 40:
        score += 0.3  # Oversold bounce potential
    elif 60 < rsi <= 70:
        score += 0.3  # Strong but caution

    # StochRSI position (0-0.5)
    # K above D = bullish momentum
    if k > d:
        diff = min(k - d, 30)  # Cap contribution
        score += 0.5 * (diff / 30)

    return min(1.0, score)


def compute_volume_score(ind: Dict[str, float]) -> float:
    """VOLUME Score (0-1): RVOL activity + OBV trend + A/D trend."""
    score = 0.0
    rvol = ind.get("rvol", 1.0)
    obv_slope = ind.get("obv_slope", 0)
    ad_slope = ind.get("ad_slope", 0)

    # RVOL (0-0.3) — above average volume
    if rvol > 0.8:
        score += 0.3 * min(1.0, (rvol - 0.8) / 2.2)

    # OBV trend (0-0.4)
    if obv_slope > 0:
        score += 0.4 * min(1.0, obv_slope * 10)

    # A/D line trend (0-0.3)
    if ad_slope > 0:
        score += 0.3 * min(1.0, ad_slope * 10)

    return min(1.0, score)


def compute_volatility_score(ind: Dict[str, float]) -> float:
    """VOLATILITY Score (0-1): %B position + squeeze + ATR contraction."""
    score = 0.0
    pctb = ind.get("bb_pctb", 0.5)
    bbw_pctl = ind.get("bb_width_pctl", 0.5)
    squeeze = ind.get("squeeze", False)

    # %B position (0-0.4) — buy in lower half (value zone)
    if 0.0 <= pctb <= 0.3:
        score += 0.4  # Near lower band
    elif 0.3 < pctb <= 0.5:
        score += 0.25

    # Squeeze detection (0-0.3) — low volatility = pending breakout
    if squeeze:
        score += 0.3
    elif bbw_pctl < 0.2:
        score += 0.2  # Near-squeeze

    # ATR declining = consolidation (0-0.3)
    # (proxy: if bb_width_pctl is low, ATR is likely contracting)
    if bbw_pctl < 0.3:
        score += 0.3

    return min(1.0, score)


def compute_operator_score(
    broker_data: Optional[Dict[str, Any]] = None,
    player_favorites: Optional[Dict[str, Any]] = None,
    circuit_breaker_pct_used: float = 0.0,
) -> float:
    """
    OPERATOR Score (0-1): Broker concentration + buyer dominance + distribution risk.
    NEPSE-specific: detects institutional/operator activity.

    Phase 5.8: circuit_breaker_pct_used (0-100) penalizes stocks near circuit limit.
    """
    if not broker_data and not player_favorites:
        return 0.5  # Neutral if no data

    score = 0.0
    bd = broker_data or {}
    pf = player_favorites or {}

    # Broker concentration (0-0.3)
    top3_pct = bd.get("top3_pct", 0)
    if top3_pct > 50:
        score += 0.3 * min(1.0, (top3_pct - 40) / 30)

    # Buyer dominance (0-0.3)
    if pf.get("winner") == "Buyer" and pf.get("winner_weight", 0) > 55:
        score += 0.3 * min(1.0, (pf["winner_weight"] - 50) / 20)

    # Absence of distribution risk = positive (0-0.4)
    if not bd.get("distribution_divergence", False):
        score += 0.2
    dist_risk = bd.get("distribution_risk", "LOW")
    if dist_risk == "LOW":
        score += 0.2
    elif dist_risk == "MEDIUM":
        score += 0.1

    # Circuit breaker proximity penalty (Phase 5.8)
    # If stock has already used >80% of daily circuit range, penalize heavily
    if circuit_breaker_pct_used > 80:
        score *= 0.3  # Near circuit — very risky to enter
    elif circuit_breaker_pct_used > 60:
        score *= 0.6  # Limited remaining range

    return min(1.0, score)


def compute_fundamental_score(
    pe: float = 0,
    roe: float = 0,
    sector: str = "",
    has_dividend_history: bool = False,
) -> float:
    """FUNDAMENTAL Score (0-1): Sector-specific PE + ROE + dividend."""
    score = 0.0
    sector_pe_med = settings.sector_pe_medians.get(sector, 20)

    # Sector-specific PE (0-0.4)
    if 0 < pe < sector_pe_med * 0.8:
        score += 0.4  # Significantly undervalued
    elif 0 < pe < sector_pe_med:
        score += 0.25  # Below sector median
    elif 0 < pe < sector_pe_med * 1.2:
        score += 0.1  # Slightly above but acceptable

    # ROE (0-0.3)
    if roe > 15:
        score += 0.3
    elif roe > 10:
        score += 0.2
    elif roe > 5:
        score += 0.1

    # Dividend history (0-0.3)
    if has_dividend_history:
        score += 0.3

    return min(1.0, score)


def compute_css(
    symbol: str,
    indicators: Dict[str, float],
    profile: str = "swing",
    broker_data: Optional[Dict] = None,
    player_favorites: Optional[Dict] = None,
    pe: float = 0,
    roe: float = 0,
    sector: str = "",
    has_dividend_history: bool = False,
    market_regime: str = "NEUTRAL",
    signal_age_days: int = 0,
) -> CSSResult:
    """
    Compute the Composite Signal Score for a stock.

    Args:
        symbol: Stock symbol
        indicators: Dict from QuantIndicators.get_latest_indicators()
        profile: "short_term", "swing", or "investment"
        broker_data: Broker analysis dict (optional)
        player_favorites: Player favorites dict (optional)
        pe: PE ratio
        roe: Return on equity
        sector: Sector name (for PE benchmarking)
        has_dividend_history: Whether stock has 3-year dividend history
        market_regime: "BULL", "BEAR", "NEUTRAL", "PANIC"
        signal_age_days: Days since signal was generated (for freshness decay)

    Returns:
        CSSResult with score and signal.
    """
    weights = CSS_WEIGHTS.get(profile, CSS_WEIGHTS["swing"])

    trend = compute_trend_score(indicators)
    momentum = compute_momentum_score(indicators)
    volume = compute_volume_score(indicators)
    volatility = compute_volatility_score(indicators)
    operator = compute_operator_score(broker_data, player_favorites)
    fundamental = compute_fundamental_score(pe, roe, sector, has_dividend_history)

    # Weighted CSS
    css = (
        weights["trend"] * trend
        + weights["momentum"] * momentum
        + weights["volume"] * volume
        + weights["volatility"] * volatility
        + weights["operator"] * operator
        + weights["fundamental"] * fundamental
    )

    # Signal freshness decay: 0.8^days
    if signal_age_days > 0:
        decay = 0.8 ** signal_age_days
        css *= decay

    css = min(1.0, max(0.0, css))

    # Determine signal
    signal = _determine_signal(css, market_regime)

    # Calculate trade parameters from indicators
    close = indicators.get("close", 0)
    atr = indicators.get("atr", 0)
    entry = close
    stop = round(close - 2.0 * atr, 2) if atr > 0 else round(close * 0.95, 2)
    target = round(close + 3.0 * atr, 2) if atr > 0 else round(close * 1.10, 2)

    result = CSSResult(
        symbol=symbol,
        date=date.today(),
        css=round(css, 4),
        trend_score=round(trend, 4),
        momentum_score=round(momentum, 4),
        volume_score=round(volume, 4),
        volatility_score=round(volatility, 4),
        operator_score=round(operator, 4),
        fundamental_score=round(fundamental, 4),
        signal=signal,
        confidence=round(css * 100, 1),
        indicators=indicators,
        entry_price=entry,
        stop_loss=stop,
        target_price=target,
    )

    logger.debug(
        f"{symbol} CSS={css:.3f} [{signal}] "
        f"T={trend:.2f} M={momentum:.2f} V={volume:.2f} "
        f"Vol={volatility:.2f} Op={operator:.2f} F={fundamental:.2f}"
    )
    return result


def _determine_signal(css: float, market_regime: str) -> str:
    """Map CSS score to signal, adjusted for market regime."""
    if market_regime == "PANIC":
        return "STRONG_SELL" if css < 0.5 else "HOLD"

    if css >= 0.75 and market_regime != "BEAR":
        return "STRONG_BUY"
    elif css >= 0.60 and market_regime != "PANIC":
        return "BUY"
    elif css >= 0.50 and market_regime == "BULL":
        return "WEAK_BUY"
    elif css >= 0.35:
        return "HOLD"
    elif css >= 0.25:
        return "WEAK_SELL"
    elif css >= 0.15:
        return "SELL"
    else:
        return "STRONG_SELL"


def analyze_stock_css(
    symbol: str,
    df: pd.DataFrame,
    profile: str = "swing",
    broker_data: Optional[Dict] = None,
    player_favorites: Optional[Dict] = None,
    pe: float = 0,
    roe: float = 0,
    sector: str = "",
    has_dividend_history: bool = False,
    market_regime: str = "NEUTRAL",
) -> Optional[CSSResult]:
    """
    Convenience function: compute CSS for a stock from raw OHLCV data.

    Args:
        symbol: Stock symbol
        df: OHLCV DataFrame (min 30 rows recommended)
        profile: Weight profile
        ...other args passed to compute_css

    Returns:
        CSSResult or None if insufficient data.
    """
    if df is None or len(df) < 14:
        logger.warning(f"{symbol}: insufficient data for CSS ({len(df) if df is not None else 0} rows)")
        return None

    qi = QuantIndicators(df)
    indicators = qi.get_latest_indicators()
    if not indicators:
        return None

    return compute_css(
        symbol=symbol,
        indicators=indicators,
        profile=profile,
        broker_data=broker_data,
        player_favorites=player_favorites,
        pe=pe,
        roe=roe,
        sector=sector,
        has_dividend_history=has_dividend_history,
        market_regime=market_regime,
    )
