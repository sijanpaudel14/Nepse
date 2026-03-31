"""
NEPSE Operator Cycle Detector.

Detects the 14-21 day pump/dump cycle that operators run in NEPSE:

  Day 1-5:   ACCUMULATION — Quiet buying on low volume
  Day 5-10:  MARKUP       — Allow price rise, attract retail
  Day 10-15: DISTRIBUTION — Sell into retail demand at highs
  Day 15-21: MARKDOWN     — Price collapses as supply overwhelms

Detection uses volume/price divergences and broker concentration.

Usage:
    from intelligence.operator_cycle import detect_operator_cycle
    phase, details = detect_operator_cycle(df, broker_data)
    # phase: "ACCUMULATION" | "MARKUP" | "DISTRIBUTION" | "MARKDOWN" | "CLEAN"
"""

from typing import Tuple, Optional, Dict, Any
import pandas as pd
import numpy as np
from loguru import logger

from analysis.quant_indicators import QuantIndicators


def detect_operator_cycle(
    df: pd.DataFrame,
    broker_data: Optional[Dict[str, Any]] = None,
    window: int = 21,
) -> Tuple[str, str]:
    """
    Detect current phase of an operator pump/dump cycle.

    Args:
        df: OHLCV DataFrame, sorted by date ascending, min 21 rows.
        broker_data: Optional broker analysis data with keys:
            - top3_pct: float (broker concentration %)
            - net_flow_1w: float (weekly net flow)
            - net_flow_1m: float (monthly net flow)
        window: Lookback window in days for cycle detection.

    Returns:
        (phase, explanation) where phase is one of:
        "ACCUMULATION", "MARKUP", "DISTRIBUTION", "MARKDOWN", "CLEAN"
    """
    if df is None or len(df) < window:
        return "CLEAN", "Insufficient data for cycle detection."

    qi = QuantIndicators(df)

    # Split recent data into sub-windows
    recent = df.tail(window).copy()
    first_half = recent.head(window // 2)
    second_half = recent.tail(window // 2)

    close = recent["close"]
    volume = recent["volume"]

    # Price movement over the window
    price_change_pct = (close.iloc[-1] / close.iloc[0] - 1) * 100
    first_half_change = (first_half["close"].iloc[-1] / first_half["close"].iloc[0] - 1) * 100
    second_half_change = (second_half["close"].iloc[-1] / second_half["close"].iloc[0] - 1) * 100

    # Volume analysis
    rvol = qi.rvol(period=20)
    avg_rvol_first = rvol.iloc[-(window):-(window // 2)].mean() if len(rvol) >= window else 1.0
    avg_rvol_second = rvol.iloc[-(window // 2):].mean() if len(rvol) >= window else 1.0

    # OBV analysis
    obv = qi.obv()
    obv_change = obv.iloc[-1] - obv.iloc[-window] if len(obv) >= window else 0
    obv_trend_pos = obv_change > 0

    # Broker concentration hint
    broker_concentrated = False
    if broker_data:
        top3 = broker_data.get("top3_pct", 0)
        broker_concentrated = top3 > 50

    # ========================================
    # Phase Detection Logic
    # ========================================

    # ACCUMULATION: Price flat/slightly down, volume low, OBV rising
    # (operators buying quietly below the radar)
    if (
        abs(price_change_pct) < 5
        and avg_rvol_first < 1.2
        and obv_trend_pos
        and broker_concentrated
    ):
        return (
            "ACCUMULATION",
            f"Price flat ({price_change_pct:+.1f}%) with low volume (RVOL={avg_rvol_first:.1f}) "
            f"but OBV rising — possible operator accumulation. "
            f"Broker concentration: {broker_data.get('top3_pct', 0):.0f}%."
        )

    # MARKUP: Price rising sharply, volume increasing, OBV rising
    # (operators let price rise to attract retail)
    if (
        price_change_pct > 8
        and first_half_change > 3
        and avg_rvol_second > 1.3
        and obv_trend_pos
    ):
        return (
            "MARKUP",
            f"Strong price rise ({price_change_pct:+.1f}%) with increasing volume "
            f"(RVOL={avg_rvol_second:.1f}). Operator markup phase — "
            f"ride the trend but tighten stop-loss."
        )

    # DISTRIBUTION: Price at high, volume high, but OBV diverging (flattening/declining)
    # (operators selling into retail demand)
    if (
        price_change_pct > 5
        and avg_rvol_second > 1.5
        and not obv_trend_pos
    ):
        return (
            "DISTRIBUTION",
            f"Price up ({price_change_pct:+.1f}%) with high volume (RVOL={avg_rvol_second:.1f}) "
            f"BUT OBV declining — DANGER: operators likely distributing. "
            f"Consider exiting or tightening stops significantly."
        )

    # MARKDOWN: Price falling, volume may be declining, OBV falling
    # (operators done selling, retail left holding bags)
    if (
        price_change_pct < -8
        and second_half_change < -3
        and not obv_trend_pos
    ):
        return (
            "MARKDOWN",
            f"Price dropping ({price_change_pct:+.1f}%) with OBV declining — "
            f"markdown phase. AVOID buying. Wait for accumulation phase restart."
        )

    # Additional check: Distribution divergence
    # Price making new high but OBV not confirming
    if len(df) >= 30:
        price_10d_high = close.tail(10).max()
        price_20d_high = close.tail(20).max()
        obv_10d = obv.tail(10)
        obv_20d = obv.tail(20)

        if (
            price_10d_high >= price_20d_high * 0.98  # Near 20d high
            and obv_10d.iloc[-1] < obv_20d.max() * 0.95  # OBV not confirming
        ):
            return (
                "DISTRIBUTION",
                f"Price near 20-day high but OBV diverging downward — "
                f"hidden distribution detected. Be cautious."
            )

    return "CLEAN", "No operator cycle pattern detected."


def get_cycle_risk_adjustment(phase: str) -> float:
    """
    Get position size adjustment factor based on operator cycle phase.

    Returns:
        Multiplier to apply to position size (0.0 = don't trade, 1.0 = full size)
    """
    adjustments = {
        "ACCUMULATION": 1.0,   # Good entry point
        "MARKUP": 0.75,        # Can ride but smaller size
        "DISTRIBUTION": 0.0,   # Don't buy — operators are selling
        "MARKDOWN": 0.0,       # Don't buy — falling knife
        "CLEAN": 1.0,          # Normal trading
    }
    return adjustments.get(phase, 0.5)
