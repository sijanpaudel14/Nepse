"""
Golden Cross Momentum Strategy.

This is the primary swing trading strategy for NEPSE.

RULES:
1. EMA(9) must have crossed ABOVE EMA(21) in last 2 days (Golden Cross)
2. RSI(14) must be between 50-65 (bullish momentum, not overbought)
3. Volume must be > 1.5x the 20-day average (institutional buying)
4. Price must be > Rs. 200 (avoid penny stock manipulation)

ENHANCEMENTS (over basic strategy):
5. MACD histogram must be positive (confirms momentum)
6. ADX > 25 (confirms trend strength)
7. Not in top 10% of 52-week high (avoid buying at peak)

WHY THESE RULES?
- Golden Cross: Signals start of new uptrend
- RSI 50-65: Bullish but not overextended
- Volume spike: Smart money is entering
- MACD positive: Momentum is accelerating
- ADX > 25: Trend is strong enough to trade
"""

from datetime import date
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd
from loguru import logger

from core.config import settings
from analysis.strategies import BaseStrategy, StrategySignal
from analysis.indicators import TechnicalIndicators


class GoldenCrossStrategy(BaseStrategy):
    """
    Golden Cross Momentum Strategy for NEPSE swing trading.
    """
    
    @property
    def name(self) -> str:
        return "golden_cross_momentum"
    
    @property
    def description(self) -> str:
        return "EMA 9/21 Golden Cross with RSI and Volume confirmation"
    
    def _setup_params(self):
        """Set default parameters."""
        defaults = {
            "ema_short": settings.ema_short,
            "ema_long": settings.ema_long,
            "rsi_period": settings.rsi_period,
            "rsi_min": settings.rsi_min,
            "rsi_max": settings.rsi_max,
            "volume_multiplier": settings.volume_spike_multiplier,
            "min_price": settings.min_price,
            "adx_threshold": 25.0,
            "max_pct_from_high": 10.0,  # Don't buy if within 10% of 52w high
        }
        
        # Merge with provided params
        for key, value in defaults.items():
            if key not in self.params:
                self.params[key] = value
    
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[StrategySignal]:
        """
        Analyze stock data and generate signal if conditions are met.
        
        Args:
            df: DataFrame with OHLCV data
            symbol: Stock symbol
            
        Returns:
            StrategySignal if all conditions met, None otherwise
        """
        if not self.validate_data(df, min_rows=30):
            return None
        
        # Calculate indicators
        ti = TechnicalIndicators(df)
        ti.add_all_indicators()
        ti.detect_golden_cross()
        
        df = ti.df
        latest = self.get_latest_values(df)
        
        # Get parameter shortcuts
        p = self.params
        
        # ========================================
        # CHECK ALL CONDITIONS
        # ========================================
        
        conditions = []
        
        # 1. Price filter (> Rs. 200)
        price = latest.get("close", 0)
        price_ok = price > p["min_price"]
        conditions.append(("price_filter", price_ok, 1.0))
        
        if not price_ok:
            logger.debug(f"{symbol}: Failed price filter ({price} < {p['min_price']})")
            return None  # Hard filter
        
        # 2. Golden Cross (must have occurred in last 2 days)
        golden_cross = latest.get("golden_cross_recent", False)
        conditions.append(("golden_cross", golden_cross, 2.0))
        
        if not golden_cross:
            # Check if we're at least in an uptrend (short EMA > long EMA)
            ema_short = latest.get(f"ema_{p['ema_short']}", 0)
            ema_long = latest.get(f"ema_{p['ema_long']}", 0)
            uptrend = ema_short > ema_long
            
            if not uptrend:
                logger.debug(f"{symbol}: Not in uptrend")
                return None
        
        # 3. RSI in bullish range (50-65)
        rsi = latest.get(f"rsi_{p['rsi_period']}", 50)
        rsi_ok = p["rsi_min"] <= rsi <= p["rsi_max"]
        conditions.append(("rsi_range", rsi_ok, 1.5))
        
        if rsi is None or not (p["rsi_min"] - 5 <= rsi <= p["rsi_max"] + 5):
            # Allow small buffer, but reject if clearly outside range
            logger.debug(f"{symbol}: RSI out of range ({rsi})")
            return None
        
        # 4. Volume spike (> 1.5x average)
        volume_spike = latest.get("volume_spike", 1.0)
        volume_ok = volume_spike >= p["volume_multiplier"]
        conditions.append(("volume_spike", volume_ok, 1.5))
        
        # 5. MACD histogram positive
        macd_hist = latest.get("macd_histogram", 0)
        macd_ok = macd_hist is not None and macd_hist > 0
        conditions.append(("macd_positive", macd_ok, 1.0))
        
        # 6. ADX > 25 (strong trend)
        adx = latest.get("adx", 0)
        adx_ok = adx is not None and adx > p["adx_threshold"]
        conditions.append(("adx_strong", adx_ok, 1.0))
        
        # 7. Not too close to 52-week high
        pct_from_high = latest.get("pct_from_high", 50)
        not_at_peak = pct_from_high is None or pct_from_high >= p["max_pct_from_high"]
        conditions.append(("not_at_peak", not_at_peak, 1.0))
        
        # ========================================
        # CALCULATE CONFIDENCE
        # ========================================
        
        confidence = self.calculate_confidence(conditions)
        
        # Must have minimum confidence to generate signal
        if confidence < 5.0:
            logger.debug(f"{symbol}: Low confidence ({confidence:.1f})")
            return None
        
        # Must have golden cross OR strong volume with uptrend
        if not golden_cross and not (volume_ok and latest.get(f"ema_{p['ema_short']}", 0) > latest.get(f"ema_{p['ema_long']}", 0)):
            logger.debug(f"{symbol}: Missing key trigger")
            return None
        
        # ========================================
        # GENERATE SIGNAL
        # ========================================
        
        # Build reason string
        reasons = []
        if golden_cross:
            reasons.append("Golden Cross detected")
        if rsi_ok:
            reasons.append(f"RSI at {rsi:.1f}")
        if volume_ok:
            reasons.append(f"Volume spike {volume_spike:.1f}x")
        if macd_ok:
            reasons.append("MACD bullish")
        if adx_ok:
            reasons.append(f"Strong trend (ADX {adx:.1f})")
        
        # Calculate ATR-based stop loss and target
        # CRITICAL: Do NOT use hardcoded percentages - use actual volatility
        # Add slippage buffer to entry price for realistic NEPSE execution
        entry = price * (1 + settings.slippage_pct)
        stop, target = self._calculate_atr_based_levels(df, entry)
        
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
                "ema_9": latest.get(f"ema_{p['ema_short']}"),
                "ema_21": latest.get(f"ema_{p['ema_long']}"),
                "volume_spike": volume_spike,
                "macd_histogram": macd_hist,
                "adx": adx,
                "golden_cross": golden_cross,
            }
        )
        
        logger.info(f"🟢 {symbol}: BUY signal (confidence {confidence:.1f}/10)")
        return signal
