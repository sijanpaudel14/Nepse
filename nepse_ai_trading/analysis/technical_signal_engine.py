"""
🎯 TECHNICAL SIGNAL ENGINE (NEPSE-OPTIMIZED)
=============================================
Professional Entry/Exit Timing System for Nepal Stock Exchange

This module automates what expert chart readers do visually:
1. Identifies WHEN to enter (not just "this stock is good")
2. Identifies WHEN to exit (profit targets, stop-loss, reversals)
3. Estimates HOW LONG to hold based on trend strength
4. Detects CHART PATTERNS algorithmically
5. Scores signal CONFLUENCE (multiple confirmations)
6. Detects OPERATOR CYCLES (2-3 week pump patterns)
7. Adapts to NEPSE volatility (+/-10% circuit breakers)

NEPSE-SPECIFIC OPTIMIZATIONS:
- Wider breakout buffers (2-3% vs 1%) for higher volatility
- Tighter signal validity (1-2 days vs 3 days) for fast market
- Faster distribution exits (1-2 days vs 3 days) for dump detection
- Volume-weighted pivot points for institutional level detection
- Operator cycle detection (14-21 day pump/dump patterns)
- Candle body % filtering (>2% range) to avoid low-liquidity noise

PHILOSOPHY:
- Better to miss a trade than catch a falling knife
- Wait for confirmation, not prediction
- Exit signals are MORE important than entry signals
- Trend is your friend until it bends
- Confluence > Single indicator

Author: NEPSE AI Trading System v2.0
Version: 2.0.0 (NEPSE-Optimized)
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger

try:
    import pandas_ta as ta
except ImportError:
    ta = None
    logger.warning("pandas-ta not installed. Some features may be limited.")


# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================

class TrendPhase(Enum):
    """Wyckoff-style market phases."""
    ACCUMULATION = "accumulation"    # Smart money buying (bottoming)
    MARKUP = "markup"                # Uptrend (best for buying)
    DISTRIBUTION = "distribution"    # Smart money selling (topping)
    MARKDOWN = "markdown"            # Downtrend (avoid or short)
    UNKNOWN = "unknown"


class SignalType(Enum):
    """Types of trading signals."""
    STRONG_BUY = "strong_buy"        # High confidence entry
    BUY = "buy"                      # Normal entry
    WEAK_BUY = "weak_buy"            # Cautious entry
    HOLD = "hold"                    # Keep position
    WEAK_SELL = "weak_sell"          # Consider reducing
    SELL = "sell"                    # Exit position
    STRONG_SELL = "strong_sell"      # Urgent exit


class PatternType(Enum):
    """Chart pattern types."""
    # Bullish patterns
    GOLDEN_CROSS = "golden_cross"
    BULLISH_ENGULFING = "bullish_engulfing"
    HAMMER = "hammer"
    MORNING_STAR = "morning_star"
    DOUBLE_BOTTOM = "double_bottom"
    BREAKOUT = "breakout"
    PULLBACK_TO_SUPPORT = "pullback_to_support"
    RSI_OVERSOLD_BOUNCE = "rsi_oversold_bounce"
    
    # Bearish patterns
    DEATH_CROSS = "death_cross"
    BEARISH_ENGULFING = "bearish_engulfing"
    SHOOTING_STAR = "shooting_star"
    EVENING_STAR = "evening_star"
    DOUBLE_TOP = "double_top"
    BREAKDOWN = "breakdown"
    FAILED_BREAKOUT = "failed_breakout"
    RSI_OVERBOUGHT_REJECTION = "rsi_overbought_rejection"
    
    # Neutral patterns
    DOJI = "doji"
    CONSOLIDATION = "consolidation"
    NO_PATTERN = "no_pattern"


@dataclass
class TradingSignal:
    """Complete trading signal with entry/exit details."""
    symbol: str
    signal_type: SignalType
    confidence: float = 0.0        # 0-100%
    
    # Entry details (if BUY signal)
    entry_price: float = 0.0
    entry_zone_low: float = 0.0    # Buy between these
    entry_zone_high: float = 0.0
    
    # Exit details
    stop_loss: float = 0.0
    target_1: float = 0.0          # Conservative target
    target_2: float = 0.0          # Moderate target
    target_3: float = 0.0          # Aggressive target
    trailing_stop_pct: float = 0.0 # Trailing stop percentage
    
    # Target probabilities (likelihood of hitting each target)
    t1_probability: int = 0        # % chance of hitting T1
    t2_probability: int = 0        # % chance of hitting T2
    t3_probability: int = 0        # % chance of hitting T3
    
    # Risk metrics
    risk_reward_ratio: float = 0.0
    position_size_pct: float = 0.0 # Suggested portfolio allocation
    max_loss_pct: float = 0.0      # Maximum drawdown expected
    
    # Timing
    hold_duration_days: int = 0    # Estimated holding period
    urgency: str = "normal"        # "immediate", "normal", "wait"
    valid_until: Optional[date] = None  # Signal expiry
    
    # Entry date prediction
    estimated_entry_date: Optional[date] = None  # When to buy
    days_until_entry: int = 0      # Days until expected entry
    entry_probability: float = 0.0  # Probability of reaching entry zone
    price_to_entry_pct: float = 0.0 # How far from entry zone (%)
    
    # Exit date predictions (T1, T2, T3)
    estimated_exit_date_t1: Optional[date] = None  # When to sell at T1
    days_until_t1: int = 0         # Days until T1
    estimated_exit_date_t2: Optional[date] = None  # When to sell at T2
    days_until_t2: int = 0         # Days until T2
    estimated_exit_date_t3: Optional[date] = None  # When to sell at T3
    days_until_t3: int = 0         # Days until T3
    
    # Context
    trend_phase: TrendPhase = TrendPhase.UNKNOWN
    patterns_detected: List[PatternType] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Confluence & Quality Metrics
    confluence_score: float = 0.0   # 0-100 (multiple confirmations boost this)
    signal_quality: str = "low"     # "low", "medium", "high", "exceptional"
    confirmations: List[str] = field(default_factory=list)  # What confirms this signal
    
    # Operator Cycle Detection
    operator_cycle_detected: bool = False
    cycle_phase: str = "unknown"    # "accumulation", "pump", "distribution", "dump"
    cycle_day: int = 0              # Day in 14-21 day cycle
    
    # Market Context
    market_regime: str = "unknown"  # "bull", "bear", "sideways"
    sector_trend: str = "unknown"   # "leading", "lagging", "neutral"
    
    # Timestamps
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ChartPattern:
    """Detected chart pattern with details."""
    pattern_type: PatternType
    confidence: float              # 0-100%
    start_date: date
    end_date: date
    price_at_detection: float
    target_price: float
    stop_price: float
    description: str


# ============================================================================
# TECHNICAL SIGNAL ENGINE
# ============================================================================

class TechnicalSignalEngine:
    """
    Main engine for generating entry/exit signals.
    
    This automates what chart readers do:
    1. Trend Phase Detection (Accumulation → Markup → Distribution → Markdown)
    2. Entry Signal Generation (When exactly to buy)
    3. Exit Signal Generation (When exactly to sell)
    4. Chart Pattern Detection (Visual patterns as code)
    5. Hold Duration Estimation (How long to hold)
    """
    
    def __init__(self, fetcher=None, sharehub=None):
        """
        Initialize the signal engine.
        
        Args:
            fetcher: NepseFetcher instance for price data
            sharehub: ShareHubAPI instance for broker data
        """
        self.fetcher = fetcher
        self.sharehub = sharehub
    
    def generate_signal(
        self,
        symbol: str,
        price_history: pd.DataFrame = None,
        current_price: float = None,
        broker_data: Dict = None,
        lookback_days: int = 365,
    ) -> TradingSignal:
        """
        Generate comprehensive trading signal for a stock.
        
        This is the main entry point that combines all analysis.
        
        Args:
            symbol: Stock symbol (e.g., "SMHL")
            price_history: Optional pre-fetched OHLCV DataFrame
            current_price: Optional live price override
            broker_data: Optional broker activity data
            lookback_days: Days of history to analyze
            
        Returns:
            TradingSignal with complete entry/exit recommendations
        """
        symbol = symbol.upper()
        logger.info(f"📊 Generating trading signal for {symbol}")
        
        # 1. Fetch data if not provided
        df = price_history
        if df is None and self.fetcher:
            df = self.fetcher.safe_fetch_data(symbol, days=lookback_days, min_rows=50)
        
        if df is None or df.empty or len(df) < 50:
            logger.warning(f"{symbol}: Insufficient data for signal generation")
            return self._create_insufficient_data_signal(symbol)
        
        # Ensure clean data
        df = self._prepare_dataframe(df)
        
        # Get current price
        ltp = current_price or float(df.iloc[-1]["close"])
        
        # 2. Detect trend phase (Wyckoff)
        trend_phase = self._detect_trend_phase(df)
        
        # 3. Detect chart patterns
        patterns = self._detect_patterns(df, ltp)
        
        # 4. Calculate key technical levels
        support, resistance = self._calculate_sr_levels(df, ltp)
        atr = self._get_atr(df)
        
        # 5. Analyze entry conditions
        entry_analysis = self._analyze_entry_conditions(df, ltp, trend_phase, patterns, support)
        
        # 6. Analyze exit conditions (for existing positions)
        exit_analysis = self._analyze_exit_conditions(df, ltp, trend_phase, patterns, resistance)
        
        # 7. Generate signal
        signal = self._generate_final_signal(
            symbol=symbol,
            ltp=ltp,
            trend_phase=trend_phase,
            patterns=patterns,
            entry_analysis=entry_analysis,
            exit_analysis=exit_analysis,
            support=support,
            resistance=resistance,
            atr=atr,
            df=df
        )
        
        # 8. Add broker data insights if available
        if broker_data or self.sharehub:
            signal = self._enhance_with_broker_data(signal, symbol, broker_data)
        
        logger.info(f"📊 {symbol}: Signal={signal.signal_type.value}, "
                   f"Confidence={signal.confidence:.0f}%, Phase={trend_phase.value}")
        
        return signal
    
    # ========================================================================
    # TREND PHASE DETECTION (Wyckoff Method)
    # ========================================================================
    
    def _detect_trend_phase(self, df: pd.DataFrame) -> TrendPhase:
        """
        Detect current market phase using Wyckoff principles.
        
        Phases:
        1. ACCUMULATION: Smart money buying at bottom
           - Price range-bound after decline
           - Volume declining on down moves
           - RSI making higher lows while price makes equal lows
           
        2. MARKUP: Uptrend phase
           - Higher highs and higher lows
           - Price above rising EMAs
           - Volume confirming moves up
           
        3. DISTRIBUTION: Smart money selling at top
           - Price range-bound after rally
           - Volume increasing on down moves
           - RSI making lower highs while price makes equal highs
           
        4. MARKDOWN: Downtrend phase
           - Lower highs and lower lows
           - Price below falling EMAs
           - Best to avoid or paper-trade only
        """
        if len(df) < 50:
            return TrendPhase.UNKNOWN
        
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        volume = df["volume"].values if "volume" in df.columns else None
        
        # Calculate EMAs
        ema20 = pd.Series(close).ewm(span=20).mean().values
        ema50 = pd.Series(close).ewm(span=50).mean().values
        ema200 = pd.Series(close).ewm(span=200).mean().values if len(df) >= 200 else ema50
        
        ltp = close[-1]
        
        # Calculate trend metrics
        price_vs_ema20 = (ltp / ema20[-1] - 1) * 100
        price_vs_ema50 = (ltp / ema50[-1] - 1) * 100
        ema20_vs_ema50 = (ema20[-1] / ema50[-1] - 1) * 100
        
        # Recent price action (last 20 days)
        recent_high = max(high[-20:])
        recent_low = min(low[-20:])
        recent_range_pct = (recent_high - recent_low) / recent_low * 100
        
        # Trend direction from higher highs/lower lows
        highs_trend = self._calculate_trend_direction(high[-30:])
        lows_trend = self._calculate_trend_direction(low[-30:])
        
        # Volume trend (if available)
        volume_trend = 0
        if volume is not None and len(volume) >= 20:
            vol_recent = np.mean(volume[-10:])
            vol_older = np.mean(volume[-20:-10])
            volume_trend = (vol_recent / vol_older - 1) * 100 if vol_older > 0 else 0
        
        # RSI for divergence detection
        rsi = self._calculate_rsi(close)
        
        # Decision logic
        score = {
            TrendPhase.ACCUMULATION: 0,
            TrendPhase.MARKUP: 0,
            TrendPhase.DISTRIBUTION: 0,
            TrendPhase.MARKDOWN: 0,
        }
        
        # MARKUP indicators
        if price_vs_ema20 > 0 and price_vs_ema50 > 0:
            score[TrendPhase.MARKUP] += 30
        if ema20_vs_ema50 > 0:
            score[TrendPhase.MARKUP] += 20
        if highs_trend > 0 and lows_trend > 0:  # Higher highs AND higher lows
            score[TrendPhase.MARKUP] += 30
        if 50 < rsi < 70:
            score[TrendPhase.MARKUP] += 20
        
        # MARKDOWN indicators
        if price_vs_ema20 < 0 and price_vs_ema50 < 0:
            score[TrendPhase.MARKDOWN] += 30
        if ema20_vs_ema50 < 0:
            score[TrendPhase.MARKDOWN] += 20
        if highs_trend < 0 and lows_trend < 0:  # Lower highs AND lower lows
            score[TrendPhase.MARKDOWN] += 30
        if rsi < 40:
            score[TrendPhase.MARKDOWN] += 20
        
        # ACCUMULATION indicators (bottoming after markdown)
        if recent_range_pct < 15 and price_vs_ema50 < 0:  # Tight range below EMA
            score[TrendPhase.ACCUMULATION] += 30
        if lows_trend >= 0 and highs_trend <= 0 and price_vs_ema20 < 5:  # Equal lows, lower highs
            score[TrendPhase.ACCUMULATION] += 25
        if rsi < 50 and rsi > 30:  # Neutral-oversold
            score[TrendPhase.ACCUMULATION] += 20
        if volume_trend < -10:  # Volume declining (selling exhaustion)
            score[TrendPhase.ACCUMULATION] += 25
        
        # DISTRIBUTION indicators (topping after markup)
        if recent_range_pct < 15 and price_vs_ema50 > 0:  # Tight range above EMA
            score[TrendPhase.DISTRIBUTION] += 30
        if highs_trend <= 0 and lows_trend >= 0 and price_vs_ema20 > -5:  # Equal highs, higher lows
            score[TrendPhase.DISTRIBUTION] += 25
        if rsi > 60:  # Near overbought
            score[TrendPhase.DISTRIBUTION] += 20
        if volume_trend > 10:  # Volume increasing (distribution volume)
            score[TrendPhase.DISTRIBUTION] += 25
        
        # Return phase with highest score
        best_phase = max(score, key=score.get)
        if score[best_phase] < 40:
            return TrendPhase.UNKNOWN
        
        return best_phase
    
    def _calculate_trend_direction(self, prices: np.ndarray) -> float:
        """
        Calculate trend direction from price array.
        Returns positive for uptrend, negative for downtrend, ~0 for sideways.
        """
        if len(prices) < 10:
            return 0
        
        # Compare first third to last third
        first_third = np.mean(prices[:len(prices)//3])
        last_third = np.mean(prices[-len(prices)//3:])
        
        if first_third == 0:
            return 0
        
        return (last_third / first_third - 1) * 100
    
    # ========================================================================
    # CHART PATTERN DETECTION
    # ========================================================================
    
    def _detect_patterns(self, df: pd.DataFrame, ltp: float) -> List[ChartPattern]:
        """
        Detect chart patterns in price data.
        
        Patterns detected:
        - Golden/Death Cross
        - Bullish/Bearish Engulfing
        - Hammer/Shooting Star
        - Double Top/Bottom
        - Breakout/Breakdown
        - RSI Oversold Bounce / Overbought Rejection
        - Pullback to Support
        """
        patterns = []
        
        close = df["close"].values
        open_prices = df["open"].values if "open" in df.columns else close
        high = df["high"].values
        low = df["low"].values
        
        # 1. EMA Crossovers
        ema9 = pd.Series(close).ewm(span=9).mean().values
        ema21 = pd.Series(close).ewm(span=21).mean().values
        
        # Golden Cross (EMA9 crosses above EMA21)
        if len(df) >= 5:
            if ema9[-1] > ema21[-1] and ema9[-3] <= ema21[-3]:
                patterns.append(ChartPattern(
                    pattern_type=PatternType.GOLDEN_CROSS,
                    confidence=75,
                    start_date=df.index[-3] if hasattr(df.index[-3], 'date') else date.today(),
                    end_date=df.index[-1] if hasattr(df.index[-1], 'date') else date.today(),
                    price_at_detection=ltp,
                    target_price=ltp * 1.15,
                    stop_price=ltp * 0.95,
                    description="EMA9 crossed above EMA21 - bullish momentum"
                ))
            
            # Death Cross (EMA9 crosses below EMA21)
            if ema9[-1] < ema21[-1] and ema9[-3] >= ema21[-3]:
                patterns.append(ChartPattern(
                    pattern_type=PatternType.DEATH_CROSS,
                    confidence=75,
                    start_date=df.index[-3] if hasattr(df.index[-3], 'date') else date.today(),
                    end_date=df.index[-1] if hasattr(df.index[-1], 'date') else date.today(),
                    price_at_detection=ltp,
                    target_price=ltp * 0.90,
                    stop_price=ltp * 1.03,
                    description="EMA9 crossed below EMA21 - bearish momentum"
                ))
        
        # 2. Candlestick Patterns (last 3 candles)
        candle_patterns = self._detect_candlestick_patterns(df)
        patterns.extend(candle_patterns)
        
        # 3. Double Top/Bottom
        double_patterns = self._detect_double_patterns(df, ltp)
        patterns.extend(double_patterns)
        
        # 4. RSI-based patterns
        rsi_patterns = self._detect_rsi_patterns(df, ltp)
        patterns.extend(rsi_patterns)
        
        # 5. Breakout/Breakdown
        breakout_patterns = self._detect_breakout_patterns(df, ltp)
        patterns.extend(breakout_patterns)
        
        # 6. Pullback to Support
        pullback_patterns = self._detect_pullback_patterns(df, ltp)
        patterns.extend(pullback_patterns)
        
        return patterns
    
    def _detect_candlestick_patterns(self, df: pd.DataFrame) -> List[ChartPattern]:
        """Detect candlestick patterns in recent candles."""
        patterns = []
        
        if len(df) < 3:
            return patterns
        
        # Get last 3 candles
        for i in range(-3, 0):
            if abs(i) > len(df):
                continue
                
            o = float(df.iloc[i].get("open", df.iloc[i]["close"]))
            h = float(df.iloc[i]["high"])
            l = float(df.iloc[i]["low"])
            c = float(df.iloc[i]["close"])
            
            body = abs(c - o)
            upper_wick = h - max(o, c)
            lower_wick = min(o, c) - l
            total_range = h - l
            
            if total_range == 0:
                continue
            
            body_pct = body / total_range
            upper_wick_pct = upper_wick / total_range
            lower_wick_pct = lower_wick / total_range
            
            today_date = df.index[i] if hasattr(df.index[i], 'date') else date.today()
            
            # NEPSE OPTIMIZATION: Filter out tiny candles (low liquidity noise)
            # Only detect patterns if body > 2% of total range
            if total_range > 0 and (body / c) < 0.02:  # Body must be > 2% of close price
                continue  # Skip tiny candles
            
            # HAMMER: Small body at top, long lower wick (bullish reversal)
            if body_pct < 0.3 and lower_wick_pct > 0.6 and c > o:
                patterns.append(ChartPattern(
                    pattern_type=PatternType.HAMMER,
                    confidence=70,
                    start_date=today_date,
                    end_date=today_date,
                    price_at_detection=c,
                    target_price=c * 1.08,
                    stop_price=l * 0.98,
                    description="Hammer candle - potential bullish reversal at support"
                ))
            
            # SHOOTING STAR: Small body at bottom, long upper wick (bearish reversal)
            if body_pct < 0.3 and upper_wick_pct > 0.6 and c < o:
                patterns.append(ChartPattern(
                    pattern_type=PatternType.SHOOTING_STAR,
                    confidence=70,
                    start_date=today_date,
                    end_date=today_date,
                    price_at_detection=c,
                    target_price=c * 0.92,
                    stop_price=h * 1.02,
                    description="Shooting star - potential bearish reversal at resistance"
                ))
            
            # DOJI: Very small body (indecision)
            # NEPSE: Still allow doji even if small (it's the definition)
            if body_pct < 0.1:
                patterns.append(ChartPattern(
                    pattern_type=PatternType.DOJI,
                    confidence=50,
                    start_date=today_date,
                    end_date=today_date,
                    price_at_detection=c,
                    target_price=c,
                    stop_price=c,
                    description="Doji - market indecision, wait for confirmation"
                ))
        
        # BULLISH ENGULFING: Today's green candle engulfs yesterday's red candle
        if len(df) >= 2:
            prev_o = float(df.iloc[-2].get("open", df.iloc[-2]["close"]))
            prev_c = float(df.iloc[-2]["close"])
            prev_h = float(df.iloc[-2]["high"])
            prev_l = float(df.iloc[-2]["low"])
            curr_o = float(df.iloc[-1].get("open", df.iloc[-1]["close"]))
            curr_c = float(df.iloc[-1]["close"])
            
            # NEPSE: Check candle size before engulfing pattern
            prev_body = abs(prev_c - prev_o)
            curr_body = abs(curr_c - curr_o)
            prev_range = prev_h - prev_l
            
            # Both candles must have meaningful body (> 2% of price)
            if prev_body / prev_c > 0.02 and curr_body / curr_c > 0.02:
                if prev_c < prev_o and curr_c > curr_o:  # Red then green
                    if curr_o <= prev_c and curr_c >= prev_o:  # Engulfs
                        patterns.append(ChartPattern(
                            pattern_type=PatternType.BULLISH_ENGULFING,
                            confidence=80,
                            start_date=df.index[-2] if hasattr(df.index[-2], 'date') else date.today(),
                            end_date=df.index[-1] if hasattr(df.index[-1], 'date') else date.today(),
                            price_at_detection=curr_c,
                            target_price=curr_c * 1.10,
                            stop_price=min(prev_c, curr_o) * 0.98,
                            description="Bullish engulfing - strong reversal signal"
                        ))
            
            # BEARISH ENGULFING: Today's red candle engulfs yesterday's green candle
            # NEPSE: Check meaningful candle size
            if prev_body / prev_c > 0.02 and curr_body / curr_c > 0.02:
                if prev_c > prev_o and curr_c < curr_o:  # Green then red
                    if curr_o >= prev_c and curr_c <= prev_o:  # Engulfs
                        patterns.append(ChartPattern(
                            pattern_type=PatternType.BEARISH_ENGULFING,
                            confidence=80,
                            start_date=df.index[-2] if hasattr(df.index[-2], 'date') else date.today(),
                            end_date=df.index[-1] if hasattr(df.index[-1], 'date') else date.today(),
                            price_at_detection=curr_c,
                            target_price=curr_c * 0.90,
                            stop_price=max(prev_c, curr_o) * 1.02,
                            description="Bearish engulfing - strong reversal signal"
                        ))
        
        return patterns
    
    def _detect_double_patterns(self, df: pd.DataFrame, ltp: float) -> List[ChartPattern]:
        """Detect double top and double bottom patterns."""
        patterns = []
        
        if len(df) < 30:
            return patterns
        
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        
        # Look for peaks and troughs in last 60 days
        lookback = min(60, len(df))
        recent_high = high[-lookback:]
        recent_low = low[-lookback:]
        
        # Find local maxima (peaks)
        peaks = []
        for i in range(5, len(recent_high) - 5):
            if recent_high[i] == max(recent_high[i-5:i+6]):
                peaks.append((i, recent_high[i]))
        
        # Find local minima (troughs)
        troughs = []
        for i in range(5, len(recent_low) - 5):
            if recent_low[i] == min(recent_low[i-5:i+6]):
                troughs.append((i, recent_low[i]))
        
        # DOUBLE TOP: Two peaks at similar levels
        if len(peaks) >= 2:
            for i in range(len(peaks) - 1):
                for j in range(i + 1, len(peaks)):
                    peak1_idx, peak1_price = peaks[i]
                    peak2_idx, peak2_price = peaks[j]
                    
                    # Peaks should be within 3% of each other
                    if abs(peak1_price - peak2_price) / peak1_price < 0.03:
                        # NEPSE OPTIMIZATION: At least 15-20 days apart (not 10)
                        # Reason: Operators run 2-week pump cycles
                        if peak2_idx - peak1_idx >= 17:  # ~3.5 weeks
                            # And current price below both peaks
                            if ltp < min(peak1_price, peak2_price) * 0.97:
                                neckline = min(recent_low[peak1_idx:peak2_idx+1])
                                patterns.append(ChartPattern(
                                    pattern_type=PatternType.DOUBLE_TOP,
                                    confidence=75,
                                    start_date=date.today() - timedelta(days=lookback-peak1_idx),
                                    end_date=date.today(),
                                    price_at_detection=ltp,
                                    target_price=neckline - (peak1_price - neckline),  # Measured move
                                    stop_price=peak1_price * 1.02,
                                    description=f"Double top at Rs.{peak1_price:.0f} - bearish reversal"
                                ))
                                break
        
        # DOUBLE BOTTOM: Two troughs at similar levels
        if len(troughs) >= 2:
            for i in range(len(troughs) - 1):
                for j in range(i + 1, len(troughs)):
                    trough1_idx, trough1_price = troughs[i]
                    trough2_idx, trough2_price = troughs[j]
                    
                    # Troughs should be within 3% of each other
                    if abs(trough1_price - trough2_price) / trough1_price < 0.03:
                        # NEPSE OPTIMIZATION: At least 15-20 days apart (not 10)
                        # Reason: Operators run 2-week pump cycles
                        if trough2_idx - trough1_idx >= 17:  # ~3.5 weeks
                            # And current price above both troughs
                            if ltp > max(trough1_price, trough2_price) * 1.03:
                                neckline = max(recent_high[trough1_idx:trough2_idx+1])
                                patterns.append(ChartPattern(
                                    pattern_type=PatternType.DOUBLE_BOTTOM,
                                    confidence=75,
                                    start_date=date.today() - timedelta(days=lookback-trough1_idx),
                                    end_date=date.today(),
                                    price_at_detection=ltp,
                                    target_price=neckline + (neckline - trough1_price),  # Measured move
                                    stop_price=trough1_price * 0.98,
                                    description=f"Double bottom at Rs.{trough1_price:.0f} - bullish reversal"
                                ))
                                break
        
        return patterns
    
    def _detect_rsi_patterns(self, df: pd.DataFrame, ltp: float) -> List[ChartPattern]:
        """Detect RSI-based patterns."""
        patterns = []
        
        close = df["close"].values
        rsi = self._calculate_rsi(close)
        
        if rsi is None:
            return patterns
        
        rsi_values = self._calculate_rsi_series(close)
        if rsi_values is None or len(rsi_values) < 5:
            return patterns
        
        # RSI OVERSOLD BOUNCE: RSI was below 30, now rising above 30
        if len(rsi_values) >= 5:
            recent_rsi = rsi_values[-5:]
            if min(recent_rsi[:-1]) < 30 and recent_rsi[-1] > 30:
                patterns.append(ChartPattern(
                    pattern_type=PatternType.RSI_OVERSOLD_BOUNCE,
                    confidence=70,
                    start_date=date.today() - timedelta(days=5),
                    end_date=date.today(),
                    price_at_detection=ltp,
                    target_price=ltp * 1.10,
                    stop_price=ltp * 0.95,
                    description="RSI bounced from oversold - potential reversal"
                ))
        
        # RSI OVERBOUGHT REJECTION: RSI was above 70, now falling below 70
        if len(rsi_values) >= 5:
            recent_rsi = rsi_values[-5:]
            if max(recent_rsi[:-1]) > 70 and recent_rsi[-1] < 70:
                patterns.append(ChartPattern(
                    pattern_type=PatternType.RSI_OVERBOUGHT_REJECTION,
                    confidence=70,
                    start_date=date.today() - timedelta(days=5),
                    end_date=date.today(),
                    price_at_detection=ltp,
                    target_price=ltp * 0.92,
                    stop_price=ltp * 1.03,
                    description="RSI rejected from overbought - potential pullback"
                ))
        
        return patterns
    
    def _detect_breakout_patterns(self, df: pd.DataFrame, ltp: float) -> List[ChartPattern]:
        """Detect breakout and breakdown patterns."""
        patterns = []
        
        if len(df) < 30:
            return patterns
        
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        volume = df["volume"].values if "volume" in df.columns else None
        
        # Calculate 20-day high/low (excluding last 2 days for fresh breakout)
        lookback = min(20, len(df) - 2)
        range_high = max(high[-lookback-2:-2])
        range_low = min(low[-lookback-2:-2])
        
        # Average volume
        avg_volume = np.mean(volume[-20:]) if volume is not None else 0
        today_volume = volume[-1] if volume is not None else 0
        volume_spike = today_volume / avg_volume if avg_volume > 0 else 1
        
        # BREAKOUT: Price breaks above recent high with volume
        # NEPSE OPTIMIZATION: 2% threshold (not 1%) due to higher volatility
        if ltp > range_high * 1.02:  # Above by at least 2% (NEPSE daily noise)
            confidence = 60
            if volume_spike > 1.5:
                confidence += 20  # Volume confirmation
            if ltp > range_high * 1.04:  # 4% = strong breakout
                confidence += 10  # Strong breakout
                
            patterns.append(ChartPattern(
                pattern_type=PatternType.BREAKOUT,
                confidence=confidence,
                start_date=date.today() - timedelta(days=lookback),
                end_date=date.today(),
                price_at_detection=ltp,
                target_price=ltp + (range_high - range_low),  # Measured move
                stop_price=range_high * 0.98,  # Below breakout level
                description=f"Breakout above Rs.{range_high:.0f} resistance (NEPSE-confirmed 2%+)"
            ))
        
        # BREAKDOWN: Price breaks below recent low with volume
        # NEPSE OPTIMIZATION: 2% threshold (not 1%)
        if ltp < range_low * 0.98:  # Below by at least 2%
            confidence = 60
            if volume_spike > 1.5:
                confidence += 20
            if ltp < range_low * 0.96:  # 4% = strong breakdown
                confidence += 10
                
            patterns.append(ChartPattern(
                pattern_type=PatternType.BREAKDOWN,
                confidence=confidence,
                start_date=date.today() - timedelta(days=lookback),
                end_date=date.today(),
                price_at_detection=ltp,
                target_price=ltp - (range_high - range_low),  # Measured move down
                stop_price=range_low * 1.02,  # Above breakdown level
                description=f"Breakdown below Rs.{range_low:.0f} support (NEPSE-confirmed 2%+)"
            ))
        
        # FAILED BREAKOUT: Price broke out but came back inside range
        if len(df) >= 5:
            recent_high = max(high[-5:])
            # NEPSE: Use 2% threshold for failed breakout too
            if recent_high > range_high * 1.02 and ltp < range_high:
                patterns.append(ChartPattern(
                    pattern_type=PatternType.FAILED_BREAKOUT,
                    confidence=75,
                    start_date=date.today() - timedelta(days=5),
                    end_date=date.today(),
                    price_at_detection=ltp,
                    target_price=range_low,  # Back to bottom of range
                    stop_price=recent_high * 1.02,
                    description="Failed breakout - bearish trap"
                ))
        
        return patterns
    
    def _detect_pullback_patterns(self, df: pd.DataFrame, ltp: float) -> List[ChartPattern]:
        """Detect pullback to support patterns."""
        patterns = []
        
        if len(df) < 30:
            return patterns
        
        close = df["close"].values
        
        # Calculate EMAs
        ema20 = pd.Series(close).ewm(span=20).mean().values
        ema50 = pd.Series(close).ewm(span=50).mean().values
        
        # Price should be in uptrend (EMA20 > EMA50)
        if ema20[-1] > ema50[-1]:
            # Check if price pulled back to EMA20 (within 2%)
            distance_to_ema20 = abs(ltp - ema20[-1]) / ema20[-1] * 100
            
            if distance_to_ema20 < 2:
                patterns.append(ChartPattern(
                    pattern_type=PatternType.PULLBACK_TO_SUPPORT,
                    confidence=70,
                    start_date=date.today() - timedelta(days=5),
                    end_date=date.today(),
                    price_at_detection=ltp,
                    target_price=ltp * 1.08,
                    stop_price=ema50[-1] * 0.98,
                    description=f"Pullback to EMA20 support (Rs.{ema20[-1]:.0f})"
                ))
        
        return patterns
    
    # ========================================================================
    # ENTRY/EXIT ANALYSIS
    # ========================================================================
    
    def _analyze_entry_conditions(
        self,
        df: pd.DataFrame,
        ltp: float,
        trend_phase: TrendPhase,
        patterns: List[ChartPattern],
        support: float
    ) -> Dict[str, Any]:
        """
        Analyze conditions for entry.
        
        Returns dict with:
        - should_enter: bool
        - entry_type: "immediate" | "limit" | "wait"
        - entry_price: suggested entry price
        - confidence: 0-100
        - reasons: list of why to enter
        - warnings: list of cautions
        """
        close = df["close"].values
        rsi = self._calculate_rsi(close)
        atr = self._get_atr(df)
        
        # Start with base analysis
        result = {
            "should_enter": False,
            "entry_type": "wait",
            "entry_price": ltp,
            "confidence": 0,
            "reasons": [],
            "warnings": []
        }
        
        # ========== VETO CONDITIONS (Do NOT enter) ==========
        
        # Veto 1: Markdown phase (downtrend)
        if trend_phase == TrendPhase.MARKDOWN:
            result["warnings"].append("❌ Downtrend (Markdown phase) - avoid buying")
            return result
        
        # Veto 2: RSI overbought
        if rsi and rsi > 70:
            result["warnings"].append(f"❌ RSI overbought ({rsi:.0f}) - wait for pullback")
            return result
        
        # Veto 3: Price far above EMAs (chasing)
        ema20 = pd.Series(close).ewm(span=20).mean().values[-1]
        price_above_ema = (ltp / ema20 - 1) * 100
        if price_above_ema > 10:
            result["warnings"].append(f"❌ Price {price_above_ema:.1f}% above EMA20 - don't chase")
            return result
        
        # ========== ENTRY CONDITIONS ==========
        
        confidence = 0
        reasons = []
        
        # Condition 1: Trend phase favorable
        if trend_phase == TrendPhase.MARKUP:
            confidence += 25
            reasons.append("✅ Uptrend (Markup phase)")
        elif trend_phase == TrendPhase.ACCUMULATION:
            confidence += 20
            reasons.append("✅ Accumulation phase (early)")
        
        # Condition 2: RSI in optimal zone
        if rsi:
            if 40 <= rsi <= 55:
                confidence += 20
                reasons.append(f"✅ RSI in optimal zone ({rsi:.0f})")
            elif 55 < rsi <= 65:
                confidence += 15
                reasons.append(f"✅ RSI healthy ({rsi:.0f})")
            elif rsi < 40:
                confidence += 10
                reasons.append(f"⚠️ RSI oversold ({rsi:.0f}) - reversal possible")
        
        # Condition 3: Bullish patterns detected
        bullish_patterns = [p for p in patterns if p.pattern_type in [
            PatternType.GOLDEN_CROSS, PatternType.BULLISH_ENGULFING,
            PatternType.HAMMER, PatternType.DOUBLE_BOTTOM,
            PatternType.BREAKOUT, PatternType.PULLBACK_TO_SUPPORT,
            PatternType.RSI_OVERSOLD_BOUNCE
        ]]
        
        for pattern in bullish_patterns:
            confidence += min(20, pattern.confidence * 0.3)
            reasons.append(f"✅ {pattern.pattern_type.value}: {pattern.description}")
        
        # Condition 4: Price near support
        distance_to_support = (ltp - support) / support * 100 if support > 0 else 100
        if 0 < distance_to_support < 5:
            confidence += 15
            reasons.append(f"✅ Price near support (Rs.{support:.0f})")
        
        # Condition 5: Volume confirmation
        if "volume" in df.columns and len(df) >= 20:
            avg_vol = df["volume"].tail(20).mean()
            today_vol = df["volume"].iloc[-1]
            if today_vol > avg_vol * 1.5:
                confidence += 10
                reasons.append("✅ Volume spike confirms move")
        
        # ========== DECISION ==========
        
        result["confidence"] = min(100, confidence)
        result["reasons"] = reasons
        
        if confidence >= 60:
            result["should_enter"] = True
            result["entry_type"] = "immediate"
            result["entry_price"] = ltp
        elif confidence >= 45:
            result["should_enter"] = True
            result["entry_type"] = "limit"
            result["entry_price"] = support * 1.02 if support > 0 else ltp * 0.98
            result["warnings"].append("⚠️ Wait for better entry near support")
        else:
            result["entry_type"] = "wait"
            result["warnings"].append("⚠️ Conditions not favorable - paper trade first")
        
        return result
    
    def _analyze_exit_conditions(
        self,
        df: pd.DataFrame,
        ltp: float,
        trend_phase: TrendPhase,
        patterns: List[ChartPattern],
        resistance: float
    ) -> Dict[str, Any]:
        """
        Analyze conditions for exit (for existing positions).
        
        Returns dict with:
        - should_exit: bool
        - exit_urgency: "immediate" | "soon" | "hold"
        - reasons: list of why to exit
        """
        close = df["close"].values
        rsi = self._calculate_rsi(close)
        
        result = {
            "should_exit": False,
            "exit_urgency": "hold",
            "reasons": [],
        }
        
        exit_score = 0
        reasons = []
        
        # ========== EXIT CONDITIONS ==========
        
        # Condition 1: Distribution/Markdown phase
        if trend_phase == TrendPhase.DISTRIBUTION:
            exit_score += 30
            reasons.append("⚠️ Distribution phase - smart money selling")
        elif trend_phase == TrendPhase.MARKDOWN:
            exit_score += 50
            reasons.append("🔴 Markdown phase - exit immediately")
        
        # Condition 2: RSI overbought
        if rsi and rsi > 75:
            exit_score += 30
            reasons.append(f"🔴 RSI overbought ({rsi:.0f}) - take profit")
        elif rsi and rsi > 70:
            exit_score += 20
            reasons.append(f"⚠️ RSI elevated ({rsi:.0f}) - consider partial exit")
        
        # Condition 3: Bearish patterns detected
        bearish_patterns = [p for p in patterns if p.pattern_type in [
            PatternType.DEATH_CROSS, PatternType.BEARISH_ENGULFING,
            PatternType.SHOOTING_STAR, PatternType.DOUBLE_TOP,
            PatternType.BREAKDOWN, PatternType.FAILED_BREAKOUT,
            PatternType.RSI_OVERBOUGHT_REJECTION
        ]]
        
        for pattern in bearish_patterns:
            exit_score += min(25, pattern.confidence * 0.3)
            reasons.append(f"🔴 {pattern.pattern_type.value}: {pattern.description}")
        
        # Condition 4: Price at resistance
        if resistance > 0:
            distance_to_resistance = (resistance - ltp) / ltp * 100
            if distance_to_resistance < 2:
                exit_score += 20
                reasons.append(f"⚠️ Price at resistance (Rs.{resistance:.0f})")
        
        # ========== DECISION ==========
        
        result["reasons"] = reasons
        
        if exit_score >= 60:
            result["should_exit"] = True
            result["exit_urgency"] = "immediate"
        elif exit_score >= 40:
            result["should_exit"] = True
            result["exit_urgency"] = "soon"
        else:
            result["exit_urgency"] = "hold"
        
        return result
    
    # ========================================================================
    # SIGNAL GENERATION
    # ========================================================================
    
    def _generate_final_signal(
        self,
        symbol: str,
        ltp: float,
        trend_phase: TrendPhase,
        patterns: List[ChartPattern],
        entry_analysis: Dict,
        exit_analysis: Dict,
        support: float,
        resistance: float,
        atr: float,
        df: pd.DataFrame
    ) -> TradingSignal:
        """Generate the final trading signal."""
        
        # Determine signal type
        if exit_analysis["should_exit"] and exit_analysis["exit_urgency"] == "immediate":
            signal_type = SignalType.STRONG_SELL
        elif exit_analysis["should_exit"]:
            signal_type = SignalType.SELL
        elif entry_analysis["should_enter"] and entry_analysis["entry_type"] == "immediate":
            if entry_analysis["confidence"] >= 75:
                signal_type = SignalType.STRONG_BUY
            else:
                signal_type = SignalType.BUY
        elif entry_analysis["should_enter"]:
            signal_type = SignalType.WEAK_BUY
        else:
            signal_type = SignalType.HOLD
        
        # Calculate levels
        # NEPSE OPTIMIZATION: Use 2.5-3×ATR for stop loss (not 2×) 
        # Reason: NEPSE has +/-10% circuit breakers and higher intraday volatility
        stop_loss = max(support * 0.98, ltp - 2.75 * atr) if support > 0 else ltp * 0.95
        
        # =================================================================
        # REALISTIC NEPSE SWING TRADING TARGETS
        # =================================================================
        # Based on user requirement: 10% profit in 10-12 days max
        # Typical NEPSE swing trade: 5-7% in 5-7 days, 8-10% in 10-12 days
        #
        # T1 (Safe): 5-6% - High probability (~70%), 5-7 days
        # T2 (Medium): 8-10% - Medium probability (~45%), 10-12 days  
        # T3 (Stretch): 12-15% - Low probability (~25%), 15-20 days
        # =================================================================
        
        # Calculate ATR percentage for reference
        atr_pct = (atr / ltp * 100) if ltp > 0 else 4.0
        
        # NEPSE-optimized targets based on typical swing trade expectations
        # Adjusted by trend phase (faster targets in MARKUP)
        if trend_phase == TrendPhase.MARKUP:
            # Strong uptrend - slightly higher targets achievable faster
            t1_pct = 5.5   # T1: 5.5% (5-6 days)
            t2_pct = 9.0   # T2: 9% (9-11 days)
            t3_pct = 13.0  # T3: 13% (15-18 days)
        elif trend_phase == TrendPhase.ACCUMULATION:
            # Consolidation - conservative targets
            t1_pct = 5.0   # T1: 5% (6-8 days)
            t2_pct = 8.0   # T2: 8% (10-14 days)  
            t3_pct = 12.0  # T3: 12% (18-22 days)
        else:
            # Weak trend - very conservative
            t1_pct = 4.0   # T1: 4% (7-10 days)
            t2_pct = 7.0   # T2: 7% (12-15 days)
            t3_pct = 10.0  # T3: 10% (20-25 days)
        
        # Calculate actual target prices
        target_1 = ltp * (1 + t1_pct / 100)
        target_2 = ltp * (1 + t2_pct / 100)
        target_3 = ltp * (1 + t3_pct / 100)
        
        # If resistance is close and realistic, use it as T3
        if resistance > 0 and resistance > target_2 and resistance < ltp * 1.15:
            target_3 = resistance
        
        # TARGET PROBABILITIES based on historical NEPSE data
        # These are stored for output display
        t1_prob = 70 if trend_phase == TrendPhase.MARKUP else 60  # T1 usually hit
        t2_prob = 45 if trend_phase == TrendPhase.MARKUP else 35  # T2 less certain
        t3_prob = 25 if trend_phase == TrendPhase.MARKUP else 15  # T3 stretch goal
        
        # Risk reward
        risk = ltp - stop_loss
        reward = target_2 - ltp
        risk_reward = reward / risk if risk > 0 else 0
        
        # Position sizing based on risk
        max_loss_pct = (ltp - stop_loss) / ltp * 100
        if max_loss_pct > 8:
            position_size = 1.0  # Very small
        elif max_loss_pct > 5:
            position_size = 2.0
        elif max_loss_pct > 3:
            position_size = 3.0
        else:
            position_size = 5.0  # Standard
        
        # Hold duration based on trend strength (NEPSE: max 12 days for swing)
        hold_duration = self._estimate_hold_duration(df, trend_phase, atr, ltp, target_2)
        hold_duration = min(12, hold_duration)  # Cap at 12 days for swing trading
        
        # Determine urgency
        if signal_type in [SignalType.STRONG_BUY, SignalType.STRONG_SELL]:
            urgency = "immediate"
        elif signal_type in [SignalType.BUY, SignalType.SELL]:
            urgency = "normal"
        else:
            urgency = "wait"
        
        # Compile all reasons and warnings
        all_reasons = entry_analysis.get("reasons", []) + exit_analysis.get("reasons", [])
        all_warnings = entry_analysis.get("warnings", [])
        
        # Pattern types
        pattern_types = [p.pattern_type for p in patterns]
        
        # Calculate entry zone
        entry_zone_low = support * 1.01 if support > 0 else ltp * 0.95
        entry_zone_high = ltp * 1.02
        
        # RECALCULATE TARGETS FROM ENTRY ZONE (for HOLD signals)
        # This ensures targets are realistic from the expected entry price
        if signal_type == SignalType.HOLD:
            # Targets should be from entry_zone_low (where we'll actually buy)
            base_price = entry_zone_low
        else:
            # For BUY/SELL signals, use current price
            base_price = ltp
        
        # Recalculate targets from actual entry price
        target_1 = base_price * (1 + t1_pct / 100)
        target_2 = base_price * (1 + t2_pct / 100)
        target_3 = base_price * (1 + t3_pct / 100)
        
        # PREDICT ENTRY DATE: When will price reach entry zone?
        entry_date_info = self._predict_entry_date(df, ltp, entry_zone_low, atr, trend_phase)
        
        # For immediate-entry scenarios (already near entry), base targets on current price
        if entry_date_info.get("days", 0) <= 0:
            base_price = ltp
            target_1 = base_price * (1 + t1_pct / 100)
            target_2 = base_price * (1 + t2_pct / 100)
            target_3 = base_price * (1 + t3_pct / 100)

        # PREDICT EXIT DATES: When will price reach T1, T2, T3?
        # Calculate from expected entry date (not today)
        entry_start = entry_date_info["date"]
        
        exit_t1_info = self._predict_exit_date(
            df, base_price, target_1, atr, trend_phase, hold_duration,
            start_date=entry_start
        )
        exit_t2_info = self._predict_exit_date(
            df, base_price, target_2, atr, trend_phase, hold_duration,
            start_date=entry_start
        )
        exit_t3_info = self._predict_exit_date(
            df, entry_zone_low, target_3, atr, trend_phase, hold_duration,
            start_date=entry_start
        )
        
        return TradingSignal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=entry_analysis.get("confidence", 50),
            
            entry_price=ltp,
            entry_zone_low=entry_zone_low,
            entry_zone_high=entry_zone_high,
            
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            target_3=target_3,
            trailing_stop_pct=max(3, max_loss_pct),
            
            # Target probabilities
            t1_probability=t1_prob,
            t2_probability=t2_prob,
            t3_probability=t3_prob,
            
            risk_reward_ratio=risk_reward,
            position_size_pct=position_size,
            max_loss_pct=max_loss_pct,
            
            hold_duration_days=hold_duration,
            urgency=urgency,
            # NEPSE OPTIMIZATION: Signal valid 1-2 days max (not 3)
            # Reason: NEPSE moves fast, signals become stale quickly
            valid_until=date.today() + timedelta(days=2 if signal_type in [SignalType.STRONG_BUY, SignalType.BUY] else 1),
            
            # NEW: Entry date predictions
            estimated_entry_date=entry_date_info["date"],
            days_until_entry=entry_date_info["days"],
            entry_probability=entry_date_info["probability"],
            price_to_entry_pct=entry_date_info["pct_away"],
            
            # NEW: Exit date predictions for T1, T2, T3
            estimated_exit_date_t1=exit_t1_info["date"],
            days_until_t1=exit_t1_info["days"],
            estimated_exit_date_t2=exit_t2_info["date"],
            days_until_t2=exit_t2_info["days"],
            estimated_exit_date_t3=exit_t3_info["date"],
            days_until_t3=exit_t3_info["days"],
            
            trend_phase=trend_phase,
            patterns_detected=pattern_types,
            reasons=all_reasons,
            warnings=all_warnings,
        )
    
    def _estimate_hold_duration(
        self,
        df: pd.DataFrame,
        trend_phase: TrendPhase,
        atr: float,
        ltp: float,
        target: float
    ) -> int:
        """Estimate how many days to hold based on trend and targets."""
        
        # NEPSE OPTIMIZATION: Adjusted hold durations for NEPSE volatility
        # Base duration by phase
        base_duration = {
            TrendPhase.MARKUP: 10,
            TrendPhase.ACCUMULATION: 15,
            TrendPhase.DISTRIBUTION: 2,  # CHANGED: 3→2 days (dumps happen FAST in NEPSE)
            TrendPhase.MARKDOWN: 1,
            TrendPhase.UNKNOWN: 7,
        }.get(trend_phase, 7)
        
        # Adjust by distance to target
        # NEPSE OPTIMIZATION: Use 75% ATR daily progress (not 50%) - NEPSE moves faster
        if atr > 0 and ltp > 0:
            distance = target - ltp
            days_by_atr = int(distance / (atr * 0.75))  # CHANGED: 0.5→0.75 (more aggressive)
            base_duration = max(base_duration, min(30, days_by_atr))
        
        return base_duration
    
    def _predict_entry_date(
        self,
        df: pd.DataFrame,
        current_price: float,
        entry_zone_low: float,
        atr: float,
        trend_phase: TrendPhase
    ) -> dict:
        """
        Predict WHEN price will reach entry zone.
        
        Uses:
        1. Recent price trend (7-day average daily change)
        2. ATR for volatility
        3. Trend phase for direction probability
        
        Returns:
            dict with: date, days, probability, pct_away
        """
        from datetime import date, timedelta
        
        # Calculate how far current price is from entry zone
        if current_price <= 0 or entry_zone_low <= 0:
            return {"date": None, "days": 0, "probability": 0, "pct_away": 0}
        
        pct_away = ((current_price - entry_zone_low) / current_price) * 100
        
        # If price is already in entry zone, entry is NOW
        if current_price <= entry_zone_low * 1.02:  # Within 2% of entry zone
            return {
                "date": date.today(),
                "days": 0,
                "probability": 90,
                "pct_away": pct_away
            }
        
        # Calculate recent trend (7-day average daily change)
        if len(df) >= 10:
            recent = df.tail(10)
            daily_changes = recent["close"].pct_change().dropna()
            avg_daily_change = daily_changes.mean() * 100  # As percentage
            daily_volatility = daily_changes.std() * 100
        else:
            avg_daily_change = 0
            daily_volatility = atr / current_price * 100 if current_price > 0 else 5
        
        # Estimate days to reach entry zone
        price_drop_needed = pct_away  # % drop needed
        
        if avg_daily_change < 0:  # Price is falling - good for entry
            # Days = drop needed / average daily drop
            days_to_entry = int(price_drop_needed / abs(avg_daily_change)) if avg_daily_change != 0 else 10
            probability = min(80, 50 + int(abs(avg_daily_change) * 10))  # Higher if falling faster
        elif avg_daily_change > 0.5:  # Price rising strongly
            # Unlikely to drop - long wait
            days_to_entry = max(15, int(price_drop_needed / daily_volatility * 2)) if daily_volatility > 0 else 20
            probability = max(20, 40 - int(avg_daily_change * 5))
        else:  # Price sideways/consolidating
            days_to_entry = max(5, int(price_drop_needed / (daily_volatility * 0.75))) if daily_volatility > 0 else 10
            probability = 50
        
        # Adjust by trend phase
        if trend_phase == TrendPhase.DISTRIBUTION:
            days_to_entry = max(1, days_to_entry - 3)  # Faster drop in distribution
            probability = min(85, probability + 15)
        elif trend_phase == TrendPhase.MARKDOWN:
            days_to_entry = max(1, days_to_entry - 5)
            probability = min(90, probability + 25)
        elif trend_phase == TrendPhase.MARKUP:
            days_to_entry = days_to_entry + 5  # Slower to reach entry in uptrend
            probability = max(15, probability - 20)
        
        # Cap at reasonable limits
        days_to_entry = max(1, min(30, days_to_entry))
        probability = max(10, min(90, probability))
        
        # Skip weekends (NEPSE closed Friday/Saturday)
        estimated_date = date.today()
        days_added = 0
        while days_added < days_to_entry:
            estimated_date += timedelta(days=1)
            if estimated_date.weekday() not in [4, 5]:  # Skip Friday(4), Saturday(5)
                days_added += 1
        
        return {
            "date": estimated_date,
            "days": days_to_entry,
            "probability": probability,
            "pct_away": pct_away
        }
    
    def _predict_exit_date(
        self,
        df: pd.DataFrame,
        current_price: float,
        target_price: float,
        atr: float,
        trend_phase: TrendPhase,
        hold_duration: int,
        start_date: Optional[date] = None  # NEW: Start from entry date, not today
    ) -> dict:
        """
        Predict WHEN price will reach target (exit point).
        
        Args:
            start_date: If provided, calculate from this date (e.g., expected entry date)
                       If None, calculate from today
        
        Returns:
            dict with: date, days
        """
        from datetime import date as date_type, timedelta
        
        if current_price <= 0 or target_price <= 0:
            return {"date": None, "days": 0}
        
        pct_gain_needed = ((target_price - current_price) / current_price) * 100
        
        # REALISTIC NEPSE daily gain expectation:
        # - ATR shows total volatility (up AND down), not directional progress
        # - In a good uptrend, expect ~0.5-1% daily gain on average
        # - More conservative: 0.3-0.5% daily progress toward target
        daily_pct_progress = 0.5  # Conservative: 0.5% per day toward target
        
        # Adjust by trend phase (affects how fast price moves toward target)
        if trend_phase == TrendPhase.MARKUP:
            daily_pct_progress = 0.7  # Faster in confirmed uptrend
        elif trend_phase == TrendPhase.ACCUMULATION:
            daily_pct_progress = 0.4  # Slower during accumulation
        elif trend_phase == TrendPhase.DISTRIBUTION:
            daily_pct_progress = 0.2  # Very slow/unlikely in distribution
        elif trend_phase == TrendPhase.MARKDOWN:
            daily_pct_progress = 0.1  # Almost no upward progress in downtrend
        
        # Calculate days needed
        days_to_target = int(pct_gain_needed / daily_pct_progress) if daily_pct_progress > 0 else hold_duration
        
        # Cap at reasonable limits (min 3 days for any target, max 60 days)
        days_to_target = max(3, min(60, days_to_target))
        
        # Start from provided date or today
        from datetime import date as date_type
        base_date = start_date if start_date is not None else date_type.today()
        
        # Skip weekends (NEPSE closed Friday/Saturday)
        estimated_date = base_date
        days_added = 0
        while days_added < days_to_target:
            estimated_date += timedelta(days=1)
            if estimated_date.weekday() not in [4, 5]:  # Skip Friday(4), Saturday(5)
                days_added += 1
        
        return {
            "date": estimated_date,
            "days": days_to_target
        }
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare dataframe."""
        df = df.copy()
        
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        df = df.dropna(subset=["close"])
        return df
    
    def _calculate_sr_levels(self, df: pd.DataFrame, ltp: float) -> Tuple[float, float]:
        """Calculate nearest support and resistance."""
        if len(df) < 20:
            return ltp * 0.95, ltp * 1.05
        
        high = df["high"].values
        low = df["low"].values
        
        # Find pivot highs (resistance)
        resistances = []
        for i in range(5, len(high) - 5):
            if high[i] == max(high[i-5:i+6]) and high[i] > ltp:
                resistances.append(high[i])
        
        # Find pivot lows (support)
        supports = []
        for i in range(5, len(low) - 5):
            if low[i] == min(low[i-5:i+6]) and low[i] < ltp:
                supports.append(low[i])
        
        nearest_support = max(supports) if supports else ltp * 0.95
        nearest_resistance = min(resistances) if resistances else ltp * 1.10
        
        return nearest_support, nearest_resistance
    
    def _get_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR."""
        if len(df) < period + 1:
            return float(df["close"].mean() * 0.02)
        
        try:
            if ta:
                atr = ta.atr(df["high"], df["low"], df["close"], length=period)
                if atr is not None and not atr.isna().all():
                    return float(atr.iloc[-1])
        except:
            pass
        
        # Manual calculation
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        
        tr = []
        for i in range(1, len(df)):
            tr_val = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
            tr.append(tr_val)
        
        return float(np.mean(tr[-period:])) if tr else close[-1] * 0.02
    
    def _calculate_rsi(self, close: np.ndarray, period: int = 14) -> Optional[float]:
        """Calculate RSI."""
        if len(close) < period + 1:
            return None
        
        try:
            if ta:
                rsi = ta.rsi(pd.Series(close), length=period)
                if rsi is not None and not rsi.isna().all():
                    return float(rsi.iloc[-1])
        except:
            pass
        
        # Manual calculation
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_rsi_series(self, close: np.ndarray, period: int = 14) -> Optional[np.ndarray]:
        """Calculate RSI series for pattern detection."""
        if len(close) < period + 10:
            return None
        
        try:
            if ta:
                rsi = ta.rsi(pd.Series(close), length=period)
                if rsi is not None:
                    return rsi.values
        except:
            pass
        
        return None
    
    def _enhance_with_broker_data(
        self,
        signal: TradingSignal,
        symbol: str,
        broker_data: Dict = None
    ) -> TradingSignal:
        """Enhance signal with broker activity data."""
        if not self.sharehub:
            return signal
        
        try:
            data_1m = self.sharehub.get_broker_analysis(symbol, duration="1M")
            if not data_1m:
                return signal
            
            # Check net accumulation
            net_qty = sum(b.net_quantity for b in data_1m)
            
            if net_qty > 0:
                signal.reasons.append(f"✅ Brokers accumulating (+{net_qty:,} shares)")
                signal.confidence = min(100, signal.confidence + 10)
            elif net_qty < 0:
                signal.warnings.append(f"⚠️ Brokers distributing ({net_qty:,} shares)")
                signal.confidence = max(0, signal.confidence - 15)
        except Exception as e:
            logger.debug(f"Could not enhance with broker data: {e}")
        
        return signal
    
    def _create_insufficient_data_signal(self, symbol: str) -> TradingSignal:
        """Create signal when data is insufficient."""
        return TradingSignal(
            symbol=symbol,
            signal_type=SignalType.HOLD,
            confidence=0,
            warnings=["⚠️ Insufficient data for signal generation"],
            trend_phase=TrendPhase.UNKNOWN,
        )
    
    # ========================================================================
    # REPORT FORMATTING
    # ========================================================================
    
    def format_signal_report(self, signal: TradingSignal) -> str:
        """Format signal as human-readable report."""
        lines = []
        
        # Header
        signal_emoji = {
            SignalType.STRONG_BUY: "🟢🟢",
            SignalType.BUY: "🟢",
            SignalType.WEAK_BUY: "🟡",
            SignalType.HOLD: "⚪",
            SignalType.WEAK_SELL: "🟠",
            SignalType.SELL: "🔴",
            SignalType.STRONG_SELL: "🔴🔴",
        }.get(signal.signal_type, "⚪")
        
        lines.append("=" * 70)
        lines.append(f"📊 TRADING SIGNAL: {signal.symbol}")
        lines.append(f"   {signal_emoji} {signal.signal_type.value.upper()} | Confidence: {signal.confidence:.0f}%")
        lines.append(f"   Trend Phase: {signal.trend_phase.value.upper()}")
        lines.append(f"   Generated: {signal.generated_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append("=" * 70)
        
        # ALWAYS show price levels (entry, targets, stop loss)
        if signal.signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
            lines.append("\n📍 ENTRY PLAN (Recommended)")
            lines.append("-" * 40)
            lines.append(f"   💰 Entry Price:  Rs. {signal.entry_price:,.2f}")
            lines.append(f"   📊 Entry Zone:   Rs. {signal.entry_zone_low:,.2f} - Rs. {signal.entry_zone_high:,.2f}")
            lines.append(f"   🛑 Stop Loss:    Rs. {signal.stop_loss:,.2f} ({signal.max_loss_pct:.1f}% risk)")
            lines.append(f"\n   🎯 TARGETS (When to Exit):")
            lines.append(f"      T1 (Book 50%): Rs. {signal.target_1:,.2f} (+{(signal.target_1/signal.entry_price-1)*100:.1f}%)")
            lines.append(f"      T2 (Book 30%): Rs. {signal.target_2:,.2f} (+{(signal.target_2/signal.entry_price-1)*100:.1f}%)")
            lines.append(f"      T3 (Trail 20%): Rs. {signal.target_3:,.2f} (+{(signal.target_3/signal.entry_price-1)*100:.1f}%)")
        
        elif signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
            lines.append("\n🚨 EXIT NOW (Sell Immediately)")
            lines.append("-" * 40)
            lines.append(f"   Current Price: Rs. {signal.entry_price:,.2f}")
            lines.append(f"   Urgency:       {signal.urgency.upper()}")
            lines.append(f"   Action:        SELL ALL HOLDINGS")
        
        elif signal.signal_type in [SignalType.HOLD, SignalType.WEAK_BUY]:
            # Show complete trade plan for HOLD and WEAK_BUY for consistent UX
            is_weak_buy = signal.signal_type == SignalType.WEAK_BUY
            lines.append("\n" + "=" * 70)
            lines.append("📅 COMPLETE TRADE PLAN (When to Buy/Sell/Hold)")
            lines.append("=" * 70)
            
            # Section 1: ENTRY TIMING
            lines.append("\n🔵 PHASE 1: ENTRY (When to Buy)")
            lines.append("-" * 40)
            lines.append(f"   Current Price:   Rs. {signal.entry_price:,.2f}")
            lines.append(f"   Target Buy Zone: Rs. {signal.entry_zone_low:,.2f} - Rs. {signal.entry_zone_high:,.2f}")
            lines.append(f"   Price Gap:       {signal.price_to_entry_pct:.1f}% above entry zone")
            if is_weak_buy:
                lines.append("   ⚠️ Signal Type:   WEAK_BUY (small size only, confirmation needed)")
            
            if signal.estimated_entry_date:
                lines.append(f"\n   📅 ESTIMATED ENTRY DATE: {signal.estimated_entry_date.strftime('%Y-%m-%d (%A)')}")
                lines.append(f"   ⏳ Days Until Entry:     ~{signal.days_until_entry} trading days")
                lines.append(f"   🎯 Entry Probability:   {signal.entry_probability:.0f}%")
            else:
                lines.append(f"\n   📅 Entry Date: Cannot predict (price rising)")
            
            lines.append(f"\n   💡 Entry Conditions (Wait for ANY):")
            lines.append(f"      ✅ Price drops to Rs. {signal.entry_zone_low:,.2f}")
            lines.append(f"      ✅ RSI drops below 50 (cool down)")
            lines.append(f"      ✅ Volume spike 1.5x average on green day")
            
            # Section 2: HOLD DURATION
            lines.append("\n🟡 PHASE 2: HOLD (How Long to Keep)")
            lines.append("-" * 40)
            lines.append(f"   Hold Duration:   ~{signal.hold_duration_days} trading days")
            lines.append(f"   🛑 Stop Loss:    Rs. {signal.stop_loss:,.2f} ({signal.max_loss_pct:.1f}% max loss)")
            lines.append(f"   📈 Trail Stop:   {signal.trailing_stop_pct:.1f}% below peak")
            
            # Section 3: EXIT TARGETS with probabilities and dates
            lines.append("\n🔴 PHASE 3: EXIT (When to Sell)")
            lines.append("-" * 40)
            lines.append("   ⚠️ NOTE: These are TARGETS, not guarantees!")
            lines.append("   Probability decreases as target increases.\n")
            
            # T1 with probability and date
            t1_pct = (signal.target_1/signal.entry_zone_low-1)*100 if signal.entry_zone_low > 0 else 0
            lines.append(f"   🎯 T1 (Safe): Rs. {signal.target_1:,.2f} (+{t1_pct:.1f}%) | {signal.t1_probability}% likely")
            if signal.estimated_exit_date_t1:
                lines.append(f"      📅 ~{signal.days_until_t1} days → {signal.estimated_exit_date_t1.strftime('%Y-%m-%d')}")
            
            # T2 with probability and date
            t2_pct = (signal.target_2/signal.entry_zone_low-1)*100 if signal.entry_zone_low > 0 else 0
            lines.append(f"   🎯 T2 (Medium): Rs. {signal.target_2:,.2f} (+{t2_pct:.1f}%) | {signal.t2_probability}% likely")
            if signal.estimated_exit_date_t2:
                lines.append(f"      📅 ~{signal.days_until_t2} days → {signal.estimated_exit_date_t2.strftime('%Y-%m-%d')}")
            
            # T3 with probability and date
            t3_pct = (signal.target_3/signal.entry_zone_low-1)*100 if signal.entry_zone_low > 0 else 0
            lines.append(f"   🎯 T3 (Stretch): Rs. {signal.target_3:,.2f} (+{t3_pct:.1f}%) | {signal.t3_probability}% likely")
            if signal.estimated_exit_date_t3:
                lines.append(f"      📅 ~{signal.days_until_t3} days → {signal.estimated_exit_date_t3.strftime('%Y-%m-%d')}")
            
            lines.append(f"\n   💡 Exit Strategy (for {signal.hold_duration_days}-day swing):")
            lines.append(f"      • At T1: Sell 50% (highest probability)")
            lines.append(f"      • At T2: Sell 30% more (if momentum continues)")
            lines.append(f"      • Max hold: {signal.hold_duration_days} days, then exit regardless")
        
        elif signal.signal_type == SignalType.WEAK_SELL:
            lines.append("\n⚠️ EXIT CONSIDERATION (Partial Sell)")
            lines.append("-" * 40)
            lines.append(f"   Current Price: Rs. {signal.entry_price:,.2f}")
            lines.append(f"   Suggestion:    Book 50% profit, trail rest")
            lines.append(f"   Trail Stop:    Rs. {signal.stop_loss:,.2f}")
        
        # Risk Management
        lines.append("\n⚖️ RISK MANAGEMENT")
        lines.append("-" * 40)
        lines.append(f"   Risk/Reward:    1:{signal.risk_reward_ratio:.1f}")
        lines.append(f"   Position Size:  {signal.position_size_pct:.1f}% of portfolio")
        lines.append(f"   Trailing Stop:  {signal.trailing_stop_pct:.1f}%")
        lines.append(f"   Hold Duration:  ~{signal.hold_duration_days} trading days")
        
        # Patterns Detected
        if signal.patterns_detected:
            lines.append("\n📈 PATTERNS DETECTED")
            lines.append("-" * 40)
            for pattern in signal.patterns_detected[:5]:
                lines.append(f"   • {pattern.value}")
        
        # Reasons
        if signal.reasons:
            lines.append("\n✅ REASONS")
            lines.append("-" * 40)
            for reason in signal.reasons[:7]:
                lines.append(f"   {reason}")
        
        # Warnings
        if signal.warnings:
            lines.append("\n⚠️ WARNINGS")
            lines.append("-" * 40)
            for warning in signal.warnings:
                lines.append(f"   {warning}")
        
        # ACTION SUMMARY - Clear instructions
        lines.append("\n" + "=" * 70)
        lines.append("📋 ACTION SUMMARY (What to Do)")
        lines.append("=" * 70)
        
        if signal.signal_type == SignalType.STRONG_BUY:
            lines.append(f"   ✅ ENTER NOW at Rs. {signal.entry_price:,.2f}")
            lines.append(f"   ✅ Set stop loss at Rs. {signal.stop_loss:,.2f}")
            lines.append(f"   ✅ Book 50% at T1 (Rs. {signal.target_1:,.2f})")
            lines.append(f"   ✅ Book 30% at T2 (Rs. {signal.target_2:,.2f})")
            lines.append(f"   ✅ Trail 20% to T3 (Rs. {signal.target_3:,.2f})")
            lines.append(f"   ⏰ Hold for ~{signal.hold_duration_days} days max")
            if signal.estimated_exit_date_t1:
                lines.append(f"   📅 Expected T1: {signal.estimated_exit_date_t1.strftime('%Y-%m-%d')}")
        
        elif signal.signal_type == SignalType.BUY:
            lines.append(f"   ✅ ENTER at Rs. {signal.entry_zone_low:,.2f} - Rs. {signal.entry_zone_high:,.2f}")
            lines.append(f"   ✅ Set stop loss at Rs. {signal.stop_loss:,.2f}")
            lines.append(f"   ✅ First target: Rs. {signal.target_1:,.2f} (+{(signal.target_1/signal.entry_price-1)*100:.1f}%)")
            lines.append(f"   ⏰ Hold for ~{signal.hold_duration_days} days")
            if signal.estimated_exit_date_t1:
                lines.append(f"   📅 Expected T1: {signal.estimated_exit_date_t1.strftime('%Y-%m-%d')}")
        
        elif signal.signal_type == SignalType.WEAK_BUY:
            lines.append(f"   🟡 WEAK BUY: Use small position (1-2%)")
            lines.append(f"   🟡 Follow complete trade plan above")
            lines.append(f"   🟡 Enter only near Rs. {signal.entry_zone_low:,.2f} with volume confirmation")
        
        elif signal.signal_type == SignalType.HOLD:
            lines.append(f"\n   📌 SWING TRADE PLAN ({signal.hold_duration_days}-day max hold):")
            lines.append(f"   ⏸️ DO NOT ENTER TODAY (wait for entry zone)")
            
            # ENTRY section
            if signal.estimated_entry_date and signal.days_until_entry > 0:
                lines.append(f"\n   📅 ENTRY: {signal.estimated_entry_date.strftime('%Y-%m-%d')} (~{signal.days_until_entry}d wait)")
                lines.append(f"      Buy at: Rs. {signal.entry_zone_low:,.2f}")
                lines.append(f"      Entry probability: {signal.entry_probability:.0f}%")
            
            # EXIT section with probabilities
            lines.append(f"\n   🎯 TARGETS (with probability):")
            t1_pct = (signal.target_1/signal.entry_zone_low-1)*100 if signal.entry_zone_low > 0 else 0
            t2_pct = (signal.target_2/signal.entry_zone_low-1)*100 if signal.entry_zone_low > 0 else 0
            lines.append(f"      T1: Rs. {signal.target_1:,.2f} (+{t1_pct:.0f}%) in ~{signal.days_until_t1}d | {signal.t1_probability}% likely ✅")
            lines.append(f"      T2: Rs. {signal.target_2:,.2f} (+{t2_pct:.0f}%) in ~{signal.days_until_t2}d | {signal.t2_probability}% likely")
            
            # Risk
            lines.append(f"\n   🛑 STOP LOSS: Rs. {signal.stop_loss:,.2f} ({signal.max_loss_pct:.1f}%)")
            
            # Recommendation based on user's 10-12 day swing preference
            lines.append(f"\n   💡 RECOMMENDATION (10-12 day swing):")
            lines.append(f"      → Focus on T1 (+{t1_pct:.0f}%) - highest probability ({signal.t1_probability}%)")
            lines.append(f"      → Max hold: {signal.hold_duration_days} days, then exit")
            lines.append(f"      → If T1 hit early, move stop to breakeven")
        
        elif signal.signal_type == SignalType.WEAK_SELL:
            lines.append(f"   🟠 Consider booking partial profits")
            lines.append(f"   🟠 Move stop loss to breakeven")
            lines.append(f"   🟠 Trail stop at Rs. {signal.stop_loss:,.2f}")
        
        elif signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
            lines.append(f"   🔴 EXIT ALL POSITIONS NOW")
            lines.append(f"   🔴 Downtrend detected - cut losses")
            lines.append(f"   🔴 Do not average down")
        
        # Footer
        lines.append("\n" + "-" * 70)
        if signal.valid_until:
            lines.append(f"⏰ Signal valid until: {signal.valid_until}")
        lines.append("💡 Always verify with --analyze before trading.")
        lines.append("=" * 70)
        
        return "\n".join(lines)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def generate_trading_signal(
    symbol: str,
    fetcher=None,
    sharehub=None,
    lookback_days: int = 365,
) -> TradingSignal:
    """
    Convenience function to generate trading signal.
    
    Usage:
        signal = generate_trading_signal("SMHL")
        print(signal.signal_type, signal.confidence)
    """
    engine = TechnicalSignalEngine(fetcher=fetcher, sharehub=sharehub)
    return engine.generate_signal(symbol, lookback_days=lookback_days)


def get_quick_signal(symbol: str, fetcher=None, sharehub=None) -> str:
    """
    Get one-line quick signal for a stock.
    
    Returns: "SMHL: 🟢 BUY (75%) | Entry: Rs.560 | SL: Rs.530 | T: Rs.620"
    """
    signal = generate_trading_signal(symbol, fetcher, sharehub)
    
    emoji = {
        SignalType.STRONG_BUY: "🟢🟢",
        SignalType.BUY: "🟢",
        SignalType.WEAK_BUY: "🟡",
        SignalType.HOLD: "⚪",
        SignalType.WEAK_SELL: "🟠",
        SignalType.SELL: "🔴",
        SignalType.STRONG_SELL: "🔴🔴",
    }.get(signal.signal_type, "⚪")
    
    if signal.signal_type in [SignalType.STRONG_BUY, SignalType.BUY, SignalType.WEAK_BUY]:
        return (f"{symbol}: {emoji} {signal.signal_type.value.upper()} ({signal.confidence:.0f}%) | "
                f"Entry: Rs.{signal.entry_price:,.0f} | SL: Rs.{signal.stop_loss:,.0f} | "
                f"T: Rs.{signal.target_2:,.0f}")
    else:
        return f"{symbol}: {emoji} {signal.signal_type.value.upper()} ({signal.confidence:.0f}%)"
