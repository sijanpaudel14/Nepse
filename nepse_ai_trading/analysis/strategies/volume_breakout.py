"""
Volume Breakout Strategy.

THEORY:
When volume explodes (3x+ average) and price breaks above recent highs,
it signals institutional accumulation. This often precedes major moves.

RULES:
1. Volume > 3x the 50-day average (institutional buying)
2. Price breaks above 20-day high
3. RSI not overbought (< 75)
4. Price > Rs. 200 (avoid penny stocks)

WHY IT WORKS:
- Institutions can't hide when they buy large positions
- Volume spike = smart money entering
- Breakout = demand exceeds supply at old resistance
"""

from datetime import date
from typing import Optional, Dict, Any
import pandas as pd
from loguru import logger

from core.config import settings
from analysis.strategies import BaseStrategy, StrategySignal
from analysis.indicators import TechnicalIndicators


class VolumeBreakoutStrategy(BaseStrategy):
    """
    Volume Breakout Strategy - catches institutional accumulation.
    """
    
    @property
    def name(self) -> str:
        return "volume_breakout"
    
    @property
    def description(self) -> str:
        return "High volume breakout above 20-day high"
    
    def _setup_params(self):
        """Set default parameters."""
        defaults = {
            "volume_multiplier": 3.0,  # 3x average volume
            "volume_avg_period": 50,   # 50-day volume average
            "breakout_period": 20,     # 20-day high breakout
            "rsi_max": 75,             # Not overbought
            "min_price": settings.min_price,
        }
        
        for key, value in defaults.items():
            if key not in self.params:
                self.params[key] = value
    
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[StrategySignal]:
        """
        Analyze for volume breakout signals.
        """
        if not self.validate_data(df, min_rows=50):
            return None
        
        # Calculate indicators
        ti = TechnicalIndicators(df)
        ti.add_rsi()
        
        df = ti.df.copy()
        
        # Calculate 50-day volume average
        df["volume_avg_50"] = df["volume"].rolling(50).mean()
        df["volume_spike"] = df["volume"] / df["volume_avg_50"]
        
        # Calculate 20-day high
        df["high_20d"] = df["high"].rolling(20).max().shift(1)  # Previous 20-day high
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        p = self.params
        
        # ========================================
        # CHECK CONDITIONS
        # ========================================
        
        # Price filter
        price = latest["close"]
        if price < p["min_price"]:
            return None
        
        # Volume spike (> 3x average)
        volume_spike = latest["volume_spike"]
        volume_ok = volume_spike >= p["volume_multiplier"]
        
        if not volume_ok:
            return None  # Core condition
        
        # Price breakout (today's close > previous 20-day high)
        breakout_level = latest["high_20d"]
        breakout = price > breakout_level if pd.notna(breakout_level) else False
        
        if not breakout:
            return None  # Core condition
        
        # RSI not overbought
        rsi = latest.get(f"rsi_{settings.rsi_period}", 50)
        rsi_ok = rsi < p["rsi_max"]
        
        # ========================================
        # CALCULATE CONFIDENCE
        # ========================================
        
        conditions = [
            ("volume_spike", True, 3.0),  # Already passed
            ("breakout", True, 3.0),      # Already passed
            ("rsi_ok", rsi_ok, 1.5),
        ]
        
        # Bonus for very high volume
        if volume_spike >= 5.0:
            conditions.append(("extreme_volume", True, 1.5))
        
        confidence = self.calculate_confidence(conditions)
        
        if confidence < 6.0:
            return None
        
        # ========================================
        # GENERATE SIGNAL
        # ========================================
        
        reasons = [
            f"Volume breakout {volume_spike:.1f}x",
            f"Broke above {breakout_level:.2f}",
        ]
        if rsi_ok:
            reasons.append(f"RSI healthy at {rsi:.1f}")
        
        entry = price
        target = round(entry * (1 + settings.target_profit), 2)
        stop = round(entry * (1 - settings.stop_loss), 2)
        
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
                "volume_spike": volume_spike,
                "breakout_level": breakout_level,
            }
        )
        
        logger.info(f"🔊 {symbol}: VOLUME BREAKOUT (confidence {confidence:.1f}/10)")
        return signal
