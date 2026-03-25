"""
RSI Momentum Strategy.

THEORY:
RSI divergence is a leading indicator of reversals.
When price makes a lower low but RSI makes a higher low,
it signals selling pressure is weakening.

RULES:
1. Price made a lower low (recent low < previous low)
2. RSI made a higher low (bullish divergence)
3. RSI is crossing above 30 (recovering from oversold)
4. Price > Rs. 200

WHY IT WORKS:
- Divergence shows momentum is shifting before price does
- Catching reversals early = bigger profit potential
- More risk, so we need strong confirmation
"""

from datetime import date
from typing import Optional
import pandas as pd
import numpy as np
from loguru import logger

from core.config import settings
from analysis.strategies import BaseStrategy, StrategySignal
from analysis.indicators import TechnicalIndicators


class RSIMomentumStrategy(BaseStrategy):
    """
    RSI Divergence Reversal Strategy.
    """
    
    @property
    def name(self) -> str:
        return "rsi_divergence"
    
    @property
    def description(self) -> str:
        return "RSI bullish divergence reversal"
    
    def _setup_params(self):
        """Set default parameters."""
        defaults = {
            "rsi_period": settings.rsi_period,
            "rsi_oversold": 30,
            "rsi_cross_above": 30,
            "lookback": 10,  # Days to look for divergence
            "min_price": settings.min_price,
        }
        
        for key, value in defaults.items():
            if key not in self.params:
                self.params[key] = value
    
    def _find_local_lows(self, series: pd.Series, window: int = 5) -> pd.Series:
        """Find local minima in a series (backward-looking only to avoid lookahead bias)."""
        # Use only historical data: check if value equals minimum of past 'window' bars
        shifted = series.shift(1)
        return shifted == shifted.rolling(window=window, min_periods=1).min()
    
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[StrategySignal]:
        """
        Analyze for RSI divergence signals.
        """
        if not self.validate_data(df, min_rows=30):
            return None
        
        # Calculate indicators
        ti = TechnicalIndicators(df)
        ti.add_rsi()
        ti.add_ema()
        
        df = ti.df.copy()
        p = self.params
        rsi_col = f"rsi_{p['rsi_period']}"
        
        latest = df.iloc[-1]
        price = latest["close"]
        
        # Price filter
        if price < p["min_price"]:
            return None
        
        # Get RSI
        rsi = latest.get(rsi_col, 50)
        prev_rsi = df[rsi_col].iloc[-2] if len(df) > 1 else rsi
        
        # ========================================
        # DETECT BULLISH DIVERGENCE
        # ========================================
        
        # Look at last N days
        lookback = min(p["lookback"], len(df) - 5)
        recent = df.tail(lookback)
        
        # Find price lows
        price_lows = recent.loc[self._find_local_lows(recent["low"])]
        
        if len(price_lows) < 2:
            # Need at least 2 lows to compare
            return None
        
        # Check for bullish divergence:
        # Price: lower low, RSI: higher low
        last_low = price_lows.iloc[-1]
        prev_low = price_lows.iloc[-2]
        
        price_lower_low = last_low["low"] < prev_low["low"]
        rsi_higher_low = last_low[rsi_col] > prev_low[rsi_col]
        
        bullish_divergence = price_lower_low and rsi_higher_low
        
        if not bullish_divergence:
            return None  # Core condition
        
        # RSI crossing above oversold (recovering)
        rsi_recovering = (
            prev_rsi < p["rsi_cross_above"] and 
            rsi >= p["rsi_cross_above"]
        )
        
        # Or RSI is already above 30 and rising
        rsi_rising = rsi > prev_rsi and rsi > p["rsi_oversold"]
        
        if not (rsi_recovering or rsi_rising):
            return None
        
        # ========================================
        # CALCULATE CONFIDENCE
        # ========================================
        
        conditions = [
            ("bullish_divergence", True, 3.0),
            ("rsi_recovering", rsi_recovering, 2.0),
            ("rsi_rising", rsi_rising, 1.0),
        ]
        
        # Bonus: RSI was very oversold (< 25)
        if prev_rsi < 25:
            conditions.append(("deep_oversold", True, 1.0))
        
        confidence = self.calculate_confidence(conditions)
        
        # Divergence strategy is higher risk, need higher confidence
        if confidence < 6.5:
            return None
        
        # ========================================
        # GENERATE SIGNAL
        # ========================================
        
        reasons = [
            "Bullish RSI divergence",
            f"RSI recovering at {rsi:.1f}",
        ]
        
        # Add slippage buffer to entry price for realistic NEPSE execution
        entry = price * (1 + settings.slippage_pct)
        # ATR-based stop loss and target (reversal plays use tighter stops)
        stop, target = self._calculate_atr_based_levels(df, entry, stop_multiplier=2.0, rr_ratio=1.3)
        
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
                "prev_rsi": prev_rsi,
                "divergence_type": "bullish",
            }
        )
        
        logger.info(f"📈 {symbol}: RSI DIVERGENCE (confidence {confidence:.1f}/10)")
        return signal
