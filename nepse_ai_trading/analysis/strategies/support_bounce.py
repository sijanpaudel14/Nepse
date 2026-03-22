"""
Support Bounce Strategy.

THEORY:
Price tends to bounce off major support levels.
When a stock touches support and shows rejection (long lower wick),
combined with oversold RSI, it's a high-probability bounce setup.

RULES:
1. Price touched or near a support level (within 2%)
2. Bullish candle pattern (close > open, long lower wick)
3. RSI oversold (< 35) and turning up
4. Volume above average (buyers stepping in)
5. Price > Rs. 200

WHY IT WORKS:
- Support levels are where buyers historically step in
- Long lower wick = rejection of lower prices
- Oversold RSI + support = high probability bounce
"""

from datetime import date
from typing import Optional, List
import pandas as pd
import numpy as np
from loguru import logger

from core.config import settings
from analysis.strategies import BaseStrategy, StrategySignal
from analysis.indicators import TechnicalIndicators, calculate_support_resistance


class SupportBounceStrategy(BaseStrategy):
    """
    Support Bounce Strategy - buy at support with confirmation.
    """
    
    @property
    def name(self) -> str:
        return "support_bounce"
    
    @property
    def description(self) -> str:
        return "Buy at support level with oversold reversal"
    
    def _setup_params(self):
        """Set default parameters."""
        defaults = {
            "support_threshold": 0.02,  # Within 2% of support
            "rsi_oversold": 35,
            "min_wick_ratio": 0.5,  # Lower wick > 50% of body
            "min_price": settings.min_price,
        }
        
        for key, value in defaults.items():
            if key not in self.params:
                self.params[key] = value
    
    def _is_bullish_reversal_candle(self, row: pd.Series) -> bool:
        """
        Check if candle shows bullish rejection.
        
        Bullish rejection candle:
        - Close > Open (green candle)
        - Long lower wick (rejection of lower prices)
        """
        open_price = row["open"]
        close = row["close"]
        high = row["high"]
        low = row["low"]
        
        # Must be green candle
        if close <= open_price:
            return False
        
        body = abs(close - open_price)
        lower_wick = min(open_price, close) - low
        
        # Body must be positive
        if body <= 0:
            return False
        
        # Lower wick should be at least 50% of body (rejection)
        return lower_wick >= body * self.params["min_wick_ratio"]
    
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[StrategySignal]:
        """
        Analyze for support bounce signals.
        """
        if not self.validate_data(df, min_rows=50):
            return None
        
        # Calculate indicators
        ti = TechnicalIndicators(df)
        ti.add_rsi()
        ti.add_volume_indicators()
        
        df = ti.df.copy()
        p = self.params
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        price = latest["close"]
        
        # Price filter
        if price < p["min_price"]:
            return None
        
        # ========================================
        # FIND SUPPORT LEVELS
        # ========================================
        
        support_levels, _ = calculate_support_resistance(df, window=10)
        
        if not support_levels:
            return None
        
        # Find nearest support below current price
        supports_below = [s for s in support_levels if s < price]
        if not supports_below:
            return None
        
        nearest_support = max(supports_below)  # Highest support below price
        
        # Check if price is near support (within threshold %)
        distance_pct = (price - nearest_support) / nearest_support
        near_support = distance_pct <= p["support_threshold"]
        
        if not near_support:
            return None  # Not close enough to support
        
        # ========================================
        # CHECK REVERSAL CONDITIONS
        # ========================================
        
        # RSI oversold and rising
        rsi = latest.get(f"rsi_{settings.rsi_period}", 50)
        prev_rsi = prev.get(f"rsi_{settings.rsi_period}", 50)
        
        rsi_oversold = rsi < p["rsi_oversold"] or prev_rsi < p["rsi_oversold"]
        rsi_rising = rsi > prev_rsi
        
        # Bullish reversal candle
        bullish_candle = self._is_bullish_reversal_candle(latest)
        
        # Volume confirmation
        volume_spike = latest.get("volume_spike", 1.0)
        volume_ok = volume_spike >= 1.0
        
        # ========================================
        # CALCULATE CONFIDENCE
        # ========================================
        
        conditions = [
            ("near_support", True, 2.5),  # Already passed
            ("rsi_oversold", rsi_oversold, 2.0),
            ("rsi_rising", rsi_rising, 1.5),
            ("bullish_candle", bullish_candle, 2.0),
            ("volume_ok", volume_ok, 1.0),
        ]
        
        confidence = self.calculate_confidence(conditions)
        
        # Support bounces are risky, need confirmation
        if confidence < 6.0:
            return None
        
        # Must have either bullish candle or RSI turning up
        if not (bullish_candle or (rsi_oversold and rsi_rising)):
            return None
        
        # ========================================
        # GENERATE SIGNAL
        # ========================================
        
        reasons = [
            f"Near support at {nearest_support:.2f}",
        ]
        if rsi_oversold:
            reasons.append(f"RSI oversold at {rsi:.1f}")
        if bullish_candle:
            reasons.append("Bullish rejection candle")
        if volume_ok:
            reasons.append("Volume confirmation")
        
        entry = price
        # Support bounce targets resistance
        target = round(entry * 1.08, 2)  # Conservative 8% target
        # Stop just below support
        stop = round(nearest_support * 0.98, 2)
        
        signal = StrategySignal(
            symbol=symbol,
            date=latest.get("date", date.today()),
            signal_type="BUY",
            confidence=confidence,
            entry_price=entry,
            target_price=target,
            stop_loss=stop,
            strategy_name=self.name,
            reason="; ".join(reasons),
            indicators={
                "rsi": rsi,
                "support_level": nearest_support,
                "distance_pct": distance_pct,
                "volume_spike": volume_spike,
            }
        )
        
        logger.info(f"⬆️ {symbol}: SUPPORT BOUNCE (confidence {confidence:.1f}/10)")
        return signal
