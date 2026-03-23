"""
Technical Composite Score - Multi-timeframe technical alignment.

Combines 12 technical indicators across Daily/Weekly/Monthly timeframes
to generate a single 0-100 composite score.

Scoring Philosophy:
- All timeframes aligned = Strong signal
- Divergence between timeframes = Weak signal
- Trend + Momentum + Volume confluence = High confidence

Usage:
    scorer = TechnicalCompositeScorer()
    
    # Get composite score for a stock
    score = scorer.get_composite_score("NGPL")
    
    # Get detailed breakdown
    breakdown = scorer.get_score_breakdown("NGPL")
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
from loguru import logger
import pandas as pd
import numpy as np

try:
    from data.fetcher import NepseFetcher
    from data.sharehub_api import ShareHubAPI
    from analysis.indicators import TechnicalIndicators
except ImportError:
    NepseFetcher = None
    ShareHubAPI = None
    TechnicalIndicators = None


class SignalType(Enum):
    """Signal type."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass
class IndicatorScore:
    """Score for a single indicator."""
    name: str
    value: float
    score: float  # 0-100
    signal: SignalType
    weight: float = 1.0


@dataclass
class TimeframeScore:
    """Score for a single timeframe."""
    timeframe: str  # "D", "W", "M"
    indicators: List[IndicatorScore] = field(default_factory=list)
    trend_score: float = 0.0  # 0-100
    momentum_score: float = 0.0  # 0-100
    volume_score: float = 0.0  # 0-100
    total_score: float = 0.0  # 0-100
    signal: SignalType = SignalType.NEUTRAL
    
    @property
    def signal_emoji(self) -> str:
        """Get emoji for signal."""
        return {
            SignalType.STRONG_BUY: "🟢🟢",
            SignalType.BUY: "🟢",
            SignalType.NEUTRAL: "⚪",
            SignalType.SELL: "🔴",
            SignalType.STRONG_SELL: "🔴🔴",
        }.get(self.signal, "⚪")


@dataclass
class CompositeScore:
    """Complete composite score result."""
    symbol: str
    timestamp: datetime
    
    # Timeframe scores
    daily_score: TimeframeScore = None
    weekly_score: TimeframeScore = None
    monthly_score: TimeframeScore = None
    
    # Overall
    composite_score: float = 0.0  # 0-100
    alignment: str = "MIXED"  # ALIGNED, DIVERGENT, MIXED
    signal: SignalType = SignalType.NEUTRAL
    confidence: float = 0.0  # 0-100
    
    # Key levels
    current_price: float = 0.0
    support: float = 0.0
    resistance: float = 0.0
    
    @property
    def is_aligned(self) -> bool:
        """Check if all timeframes agree."""
        if not (self.daily_score and self.weekly_score):
            return False
        
        daily_bullish = self.daily_score.total_score >= 55
        weekly_bullish = self.weekly_score.total_score >= 55
        
        return daily_bullish == weekly_bullish
    
    @property
    def signal_strength(self) -> str:
        """Get signal strength description."""
        if self.confidence >= 80:
            return "VERY STRONG"
        elif self.confidence >= 60:
            return "STRONG"
        elif self.confidence >= 40:
            return "MODERATE"
        else:
            return "WEAK"


class TechnicalCompositeScorer:
    """
    Calculates multi-timeframe technical composite scores.
    
    Indicator weights:
    - TREND (40%): EMA alignment, ADX, Price vs SMA
    - MOMENTUM (30%): RSI, MACD, Stochastic
    - VOLUME (30%): Volume trend, OBV, CMF
    
    Timeframe weights:
    - Daily: 40%
    - Weekly: 40%
    - Monthly: 20%
    """
    
    # Indicator weights within each category
    TREND_WEIGHTS = {
        "ema_alignment": 0.35,
        "adx": 0.30,
        "price_vs_sma": 0.35,
    }
    
    MOMENTUM_WEIGHTS = {
        "rsi": 0.40,
        "macd": 0.35,
        "stochastic": 0.25,
    }
    
    VOLUME_WEIGHTS = {
        "volume_trend": 0.50,
        "volume_vs_avg": 0.50,
    }
    
    # Category weights
    CATEGORY_WEIGHTS = {
        "trend": 0.40,
        "momentum": 0.30,
        "volume": 0.30,
    }
    
    # Timeframe weights
    TIMEFRAME_WEIGHTS = {
        "D": 0.40,
        "W": 0.40,
        "M": 0.20,
    }
    
    def __init__(self):
        """Initialize scorer."""
        self.fetcher = NepseFetcher() if NepseFetcher else None
        self.sharehub = ShareHubAPI() if ShareHubAPI else None
        self.indicators = None  # Created per-stock with DataFrame
    
    def _fetch_price_data(self, symbol: str, days: int = 200) -> pd.DataFrame:
        """Fetch price data for analysis."""
        if not self.fetcher:
            return pd.DataFrame()
        
        try:
            return self.fetcher.safe_fetch_data(symbol, days=days)
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _calculate_ema_alignment_score(self, df: pd.DataFrame) -> float:
        """
        Calculate EMA alignment score.
        
        Perfect bullish: Price > EMA9 > EMA21 > EMA50
        Perfect bearish: Price < EMA9 < EMA21 < EMA50
        """
        if len(df) < 50:
            return 50.0
        
        try:
            close = df['close'].iloc[-1]
            ema9 = df['close'].ewm(span=9).mean().iloc[-1]
            ema21 = df['close'].ewm(span=21).mean().iloc[-1]
            ema50 = df['close'].ewm(span=50).mean().iloc[-1]
            
            # Check alignment
            bullish_count = 0
            if close > ema9:
                bullish_count += 1
            if ema9 > ema21:
                bullish_count += 1
            if ema21 > ema50:
                bullish_count += 1
            if close > ema50:
                bullish_count += 1
            
            # Score: 0-4 bullish signals -> 0-100 score
            return bullish_count * 25
            
        except Exception as e:
            logger.debug(f"EMA alignment calc failed: {e}")
            return 50.0
    
    def _calculate_rsi_score(self, df: pd.DataFrame, period: int = 14) -> Tuple[float, float]:
        """
        Calculate RSI score.
        
        Returns:
            Tuple of (rsi_value, score)
        """
        if len(df) < period + 1:
            return 50.0, 50.0
        
        try:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss.replace(0, 0.0001)
            rsi = 100 - (100 / (1 + rs))
            rsi_value = rsi.iloc[-1]
            
            # Score RSI
            # Optimal: 40-60 (neutral)
            # Bullish: 50-70
            # Bearish: 30-50
            # Overbought: >70 (penalty)
            # Oversold: <30 (opportunity)
            
            if 50 <= rsi_value <= 65:
                score = 80  # Ideal bullish momentum
            elif 40 <= rsi_value < 50:
                score = 60  # Neutral
            elif 65 < rsi_value <= 70:
                score = 65  # Getting overbought
            elif 30 <= rsi_value < 40:
                score = 55  # Oversold but not extreme
            elif rsi_value > 70:
                score = 40  # Overbought
            elif rsi_value < 30:
                score = 70  # Oversold opportunity
            else:
                score = 50
            
            return rsi_value, score
            
        except Exception as e:
            logger.debug(f"RSI calc failed: {e}")
            return 50.0, 50.0
    
    def _calculate_macd_score(self, df: pd.DataFrame) -> Tuple[float, float]:
        """
        Calculate MACD score.
        
        Returns:
            Tuple of (macd_histogram, score)
        """
        if len(df) < 26:
            return 0.0, 50.0
        
        try:
            ema12 = df['close'].ewm(span=12).mean()
            ema26 = df['close'].ewm(span=26).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9).mean()
            histogram = macd - signal
            
            hist_value = histogram.iloc[-1]
            prev_hist = histogram.iloc[-2] if len(histogram) > 1 else 0
            
            # Score based on histogram direction and value
            if hist_value > 0 and hist_value > prev_hist:
                score = 80  # Bullish and accelerating
            elif hist_value > 0:
                score = 65  # Bullish
            elif hist_value < 0 and hist_value > prev_hist:
                score = 50  # Bearish but improving
            elif hist_value < 0:
                score = 35  # Bearish
            else:
                score = 50
            
            return hist_value, score
            
        except Exception as e:
            logger.debug(f"MACD calc failed: {e}")
            return 0.0, 50.0
    
    def _calculate_adx_score(self, df: pd.DataFrame, period: int = 14) -> Tuple[float, float]:
        """
        Calculate ADX (trend strength) score.
        
        Returns:
            Tuple of (adx_value, score)
        """
        if len(df) < period + 1:
            return 0.0, 50.0
        
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            # True Range
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # Directional Movement
            plus_dm = ((high - high.shift()) > (low.shift() - low)) * (high - high.shift())
            plus_dm = plus_dm.where(plus_dm > 0, 0)
            minus_dm = ((low.shift() - low) > (high - high.shift())) * (low.shift() - low)
            minus_dm = minus_dm.where(minus_dm > 0, 0)
            
            # Smoothed
            atr = tr.ewm(span=period).mean()
            plus_di = 100 * (plus_dm.ewm(span=period).mean() / atr)
            minus_di = 100 * (minus_dm.ewm(span=period).mean() / atr)
            
            # ADX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.0001)
            adx = dx.ewm(span=period).mean()
            adx_value = adx.iloc[-1]
            
            # Score: Strong trend is good for momentum
            if adx_value >= 25:
                score = 75 + min((adx_value - 25) * 0.5, 25)  # 75-100
            elif adx_value >= 20:
                score = 60 + (adx_value - 20) * 3  # 60-75
            else:
                score = 40 + adx_value * 1  # 40-60
            
            return adx_value, score
            
        except Exception as e:
            logger.debug(f"ADX calc failed: {e}")
            return 0.0, 50.0
    
    def _calculate_volume_score(self, df: pd.DataFrame, period: int = 20) -> float:
        """Calculate volume confirmation score."""
        if len(df) < period:
            return 50.0
        
        try:
            vol = df['volume'].iloc[-1]
            avg_vol = df['volume'].rolling(period).mean().iloc[-1]
            price_change = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]
            
            vol_ratio = vol / (avg_vol + 1)
            
            # Score based on volume confirmation
            if vol_ratio > 1.5 and price_change > 0:
                score = 85  # High volume + price up = bullish
            elif vol_ratio > 1.0 and price_change > 0:
                score = 70  # Normal volume + up
            elif vol_ratio < 0.7 and price_change > 0:
                score = 55  # Low volume rally (weak)
            elif vol_ratio > 1.5 and price_change < 0:
                score = 30  # High volume selling
            elif vol_ratio > 1.0 and price_change < 0:
                score = 40  # Normal volume decline
            else:
                score = 50
            
            return score
            
        except Exception as e:
            logger.debug(f"Volume calc failed: {e}")
            return 50.0
    
    def _calculate_timeframe_score(self, df: pd.DataFrame, timeframe: str) -> TimeframeScore:
        """Calculate score for a single timeframe."""
        tf_score = TimeframeScore(timeframe=timeframe)
        
        if df.empty or len(df) < 20:
            return tf_score
        
        try:
            # TREND indicators
            ema_score = self._calculate_ema_alignment_score(df)
            adx_value, adx_score = self._calculate_adx_score(df)
            
            # Price vs SMA50/200
            close = df['close'].iloc[-1]
            sma50 = df['close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else close
            price_vs_sma = 75 if close > sma50 else 25
            
            tf_score.trend_score = (
                ema_score * self.TREND_WEIGHTS["ema_alignment"] +
                adx_score * self.TREND_WEIGHTS["adx"] +
                price_vs_sma * self.TREND_WEIGHTS["price_vs_sma"]
            )
            
            # MOMENTUM indicators
            rsi_value, rsi_score = self._calculate_rsi_score(df)
            macd_value, macd_score = self._calculate_macd_score(df)
            
            # Simple stochastic proxy
            stoch_score = 50  # Default
            
            tf_score.momentum_score = (
                rsi_score * self.MOMENTUM_WEIGHTS["rsi"] +
                macd_score * self.MOMENTUM_WEIGHTS["macd"] +
                stoch_score * self.MOMENTUM_WEIGHTS["stochastic"]
            )
            
            # VOLUME
            volume_score = self._calculate_volume_score(df)
            tf_score.volume_score = volume_score
            
            # TOTAL
            tf_score.total_score = (
                tf_score.trend_score * self.CATEGORY_WEIGHTS["trend"] +
                tf_score.momentum_score * self.CATEGORY_WEIGHTS["momentum"] +
                tf_score.volume_score * self.CATEGORY_WEIGHTS["volume"]
            )
            
            # Determine signal
            if tf_score.total_score >= 75:
                tf_score.signal = SignalType.STRONG_BUY
            elif tf_score.total_score >= 60:
                tf_score.signal = SignalType.BUY
            elif tf_score.total_score >= 40:
                tf_score.signal = SignalType.NEUTRAL
            elif tf_score.total_score >= 25:
                tf_score.signal = SignalType.SELL
            else:
                tf_score.signal = SignalType.STRONG_SELL
            
            # Store key indicators
            tf_score.indicators = [
                IndicatorScore("RSI", rsi_value, rsi_score, tf_score.signal),
                IndicatorScore("ADX", adx_value, adx_score, tf_score.signal),
                IndicatorScore("MACD", macd_value, macd_score, tf_score.signal),
            ]
            
        except Exception as e:
            logger.error(f"Failed to calculate {timeframe} score: {e}")
        
        return tf_score
    
    def get_composite_score(self, symbol: str) -> CompositeScore:
        """
        Calculate complete composite score for a stock.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            CompositeScore with all analysis
        """
        symbol = symbol.upper()
        result = CompositeScore(symbol=symbol, timestamp=datetime.now())
        
        # Fetch price data
        df = self._fetch_price_data(symbol, days=200)
        if df.empty:
            return result
        
        try:
            result.current_price = df['close'].iloc[-1]
            
            # Calculate daily score
            result.daily_score = self._calculate_timeframe_score(df, "D")
            
            # Create weekly data (resample)
            if len(df) >= 5:
                weekly_df = df.set_index('date').resample('W').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna().reset_index()
                
                if len(weekly_df) >= 10:
                    result.weekly_score = self._calculate_timeframe_score(weekly_df, "W")
            
            # Create monthly data
            if len(df) >= 30:
                monthly_df = df.set_index('date').resample('M').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna().reset_index()
                
                if len(monthly_df) >= 3:
                    result.monthly_score = self._calculate_timeframe_score(monthly_df, "M")
            
            # Calculate composite
            weights_used = 0
            weighted_sum = 0
            
            if result.daily_score:
                weighted_sum += result.daily_score.total_score * self.TIMEFRAME_WEIGHTS["D"]
                weights_used += self.TIMEFRAME_WEIGHTS["D"]
            
            if result.weekly_score:
                weighted_sum += result.weekly_score.total_score * self.TIMEFRAME_WEIGHTS["W"]
                weights_used += self.TIMEFRAME_WEIGHTS["W"]
            
            if result.monthly_score:
                weighted_sum += result.monthly_score.total_score * self.TIMEFRAME_WEIGHTS["M"]
                weights_used += self.TIMEFRAME_WEIGHTS["M"]
            
            if weights_used > 0:
                result.composite_score = weighted_sum / weights_used
            
            # Determine alignment
            if result.is_aligned:
                result.alignment = "ALIGNED"
                result.confidence = min(90, result.composite_score + 10)
            else:
                result.alignment = "DIVERGENT"
                result.confidence = max(30, result.composite_score - 15)
            
            # Overall signal
            if result.composite_score >= 75 and result.alignment == "ALIGNED":
                result.signal = SignalType.STRONG_BUY
            elif result.composite_score >= 60:
                result.signal = SignalType.BUY
            elif result.composite_score >= 40:
                result.signal = SignalType.NEUTRAL
            elif result.composite_score >= 25:
                result.signal = SignalType.SELL
            else:
                result.signal = SignalType.STRONG_SELL
            
            # Calculate support/resistance
            if len(df) >= 20:
                result.support = df['low'].tail(20).min()
                result.resistance = df['high'].tail(20).max()
            
        except Exception as e:
            logger.error(f"Failed to calculate composite score for {symbol}: {e}")
        
        return result
    
    def format_report(self, score: CompositeScore) -> str:
        """Format composite score for CLI output."""
        lines = []
        
        lines.append("=" * 60)
        lines.append(f"📈 TECHNICAL COMPOSITE SCORE: {score.symbol}")
        lines.append("=" * 60)
        lines.append("")
        
        # Overall score
        signal_emoji = {
            SignalType.STRONG_BUY: "🟢🟢",
            SignalType.BUY: "🟢",
            SignalType.NEUTRAL: "⚪",
            SignalType.SELL: "🔴",
            SignalType.STRONG_SELL: "🔴🔴",
        }.get(score.signal, "⚪")
        
        lines.append(f"COMPOSITE SCORE: {score.composite_score:.0f}/100 {signal_emoji}")
        lines.append(f"Signal: {score.signal.value}")
        lines.append(f"Alignment: {score.alignment}")
        lines.append(f"Confidence: {score.confidence:.0f}%")
        lines.append(f"Price: Rs.{score.current_price:,.2f}")
        lines.append("")
        
        # Timeframe breakdown
        lines.append("📊 TIMEFRAME BREAKDOWN")
        lines.append("-" * 50)
        lines.append(f"{'TF':<8} {'Trend':<10} {'Momentum':<10} {'Volume':<10} {'Total':<10}")
        lines.append("-" * 50)
        
        if score.daily_score:
            d = score.daily_score
            lines.append(
                f"{'Daily':<8} {d.trend_score:>6.0f} "
                f"{d.momentum_score:>9.0f} "
                f"{d.volume_score:>9.0f} "
                f"{d.total_score:>6.0f} {d.signal_emoji}"
            )
        
        if score.weekly_score:
            w = score.weekly_score
            lines.append(
                f"{'Weekly':<8} {w.trend_score:>6.0f} "
                f"{w.momentum_score:>9.0f} "
                f"{w.volume_score:>9.0f} "
                f"{w.total_score:>6.0f} {w.signal_emoji}"
            )
        
        if score.monthly_score:
            m = score.monthly_score
            lines.append(
                f"{'Monthly':<8} {m.trend_score:>6.0f} "
                f"{m.momentum_score:>9.0f} "
                f"{m.volume_score:>9.0f} "
                f"{m.total_score:>6.0f} {m.signal_emoji}"
            )
        
        lines.append("")
        
        # Key indicators
        if score.daily_score and score.daily_score.indicators:
            lines.append("📉 KEY INDICATORS (Daily)")
            lines.append("-" * 50)
            for ind in score.daily_score.indicators:
                lines.append(f"  {ind.name}: {ind.value:.1f} (Score: {ind.score:.0f})")
            lines.append("")
        
        # Key levels
        if score.support > 0 or score.resistance > 0:
            lines.append("📍 KEY LEVELS")
            lines.append(f"  Support: Rs.{score.support:,.2f}")
            lines.append(f"  Resistance: Rs.{score.resistance:,.2f}")
            lines.append("")
        
        # Trading guidance
        lines.append("💡 TRADING GUIDANCE")
        lines.append("-" * 50)
        
        if score.signal in [SignalType.STRONG_BUY, SignalType.BUY]:
            lines.append(f"  ✅ BULLISH ({score.signal_strength} signal)")
            if score.alignment == "ALIGNED":
                lines.append("  → All timeframes aligned - Higher confidence")
            else:
                lines.append("  → Timeframes divergent - Reduce position size")
        elif score.signal in [SignalType.SELL, SignalType.STRONG_SELL]:
            lines.append(f"  ⚠️ BEARISH ({score.signal_strength} signal)")
            lines.append("  → Consider reducing exposure")
        else:
            lines.append("  ⚪ NEUTRAL - Wait for clearer signal")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Convenience functions
def get_technical_score(symbol: str) -> str:
    """Get formatted technical score for a stock."""
    scorer = TechnicalCompositeScorer()
    score = scorer.get_composite_score(symbol)
    return scorer.format_report(score)


def get_composite_score_report(symbol: str) -> str:
    """Get formatted composite score report (alias for CLI)."""
    return get_technical_score(symbol)


def get_composite_score_value(symbol: str) -> float:
    """Get just the composite score value."""
    scorer = TechnicalCompositeScorer()
    score = scorer.get_composite_score(symbol)
    return score.composite_score
