"""
🎯 PRICE TARGET ANALYZER
========================
Intelligent price target prediction for NEPSE stocks.

This module analyzes historical prices, volume profiles, broker data,
and technical patterns to predict realistic price targets.

METHODOLOGY:
1. Technical Resistance Analysis - Historical highs, pivot points
2. Volume Profile Analysis - Price levels with heavy trading (attraction zones)
3. Fibonacci Extensions - Mathematical price projections
4. ATR-Based Targets - Volatility-adjusted realistic targets
5. Broker Cost Basis - Institutional entry points as support/targets
6. Statistical Upper Bounds - 90th/95th percentile analysis

NEPSE-SPECIFIC FACTORS:
- Low liquidity = exaggerated moves (both up and down)
- Promoter lock-in = reduced float = easier manipulation
- Broker concentration = coordinated pump potential
- Circuit breaker limits (+/-10%) = natural resistance

Author: NEPSE AI Trading System
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any
import pandas as pd
import numpy as np
from loguru import logger

try:
    import pandas_ta as ta
except ImportError:
    ta = None
    logger.warning("pandas-ta not installed. Some features may be limited.")


@dataclass
class PriceTarget:
    """Individual price target with metadata."""
    level: float                    # Target price level
    name: str                       # Target name (e.g., "Fibonacci 1.618")
    method: str                     # Calculation method
    probability: float = 0.0        # Probability of reaching (0-100%)
    days_estimate: int = 0          # Estimated days to reach
    upside_percent: float = 0.0     # Percentage gain from current price
    confidence: str = "LOW"         # LOW, MEDIUM, HIGH
    reasoning: str = ""             # Explanation


@dataclass
class PriceTargetAnalysis:
    """Complete price target analysis result."""
    symbol: str
    current_price: float
    analysis_date: date
    
    # Core targets (sorted by confidence)
    conservative_target: Optional[PriceTarget] = None   # High probability, low reward
    moderate_target: Optional[PriceTarget] = None       # Balanced
    aggressive_target: Optional[PriceTarget] = None     # Low probability, high reward
    maximum_theoretical: Optional[PriceTarget] = None   # Statistical upper bound
    
    # All calculated targets for transparency
    all_targets: List[PriceTarget] = field(default_factory=list)
    
    # Support levels (downside protection reference)
    support_levels: List[float] = field(default_factory=list)
    nearest_support: float = 0.0
    
    # Risk assessment
    risk_reward_ratio: float = 0.0      # Upside / Downside
    downside_risk_percent: float = 0.0  # Distance to nearest support
    
    # Volume profile insights
    volume_poc: float = 0.0             # Point of Control (highest volume price)
    high_volume_nodes: List[float] = field(default_factory=list)
    
    # Confidence factors
    trend_direction: str = "NEUTRAL"    # BULLISH, BEARISH, NEUTRAL
    momentum_score: float = 0.0         # 0-100
    broker_accumulation: bool = False   # True if brokers accumulating
    
    # Smart Money Risk Assessment (NEW)
    dump_risk: str = "UNKNOWN"          # LOW, MEDIUM, HIGH
    manipulation_score: float = 0.0     # 0-100 (higher = more manipulated)
    buy_recommendation: str = "NEUTRAL" # BUY, AVOID, PAPER-TRADE
    
    # Warnings
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "symbol": self.symbol,
            "current_price": self.current_price,
            "analysis_date": str(self.analysis_date),
            "conservative_target": self._target_to_dict(self.conservative_target),
            "moderate_target": self._target_to_dict(self.moderate_target),
            "aggressive_target": self._target_to_dict(self.aggressive_target),
            "maximum_theoretical": self._target_to_dict(self.maximum_theoretical),
            "support_levels": self.support_levels[:3],  # Top 3
            "nearest_support": self.nearest_support,
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "downside_risk_percent": round(self.downside_risk_percent, 2),
            "volume_poc": self.volume_poc,
            "trend_direction": self.trend_direction,
            "momentum_score": round(self.momentum_score, 1),
            "warnings": self.warnings,
        }
    
    def _target_to_dict(self, target: Optional[PriceTarget]) -> Optional[Dict]:
        if not target:
            return None
        return {
            "level": round(target.level, 2),
            "name": target.name,
            "probability": round(target.probability, 1),
            "days_estimate": target.days_estimate,
            "upside_percent": round(target.upside_percent, 2),
            "confidence": target.confidence,
            "reasoning": target.reasoning,
        }


class PriceTargetAnalyzer:
    """
    🎯 Intelligent Price Target Prediction System
    
    Combines multiple methodologies to predict realistic price targets:
    1. Technical Analysis (Resistance, Fibonacci, Pivots)
    2. Volume Profile (POC, HVN, LVN)
    3. Statistical Analysis (Percentiles, Standard Deviations)
    4. Market Microstructure (Broker data, Float analysis)
    
    NEPSE-SPECIFIC ADAPTATIONS:
    - Circuit breaker awareness (+/-10% daily limit)
    - Low liquidity premium/discount
    - Manipulation detection signals
    """
    
    # NEPSE circuit breaker limits
    CIRCUIT_UP = 0.10   # +10% daily limit
    CIRCUIT_DOWN = 0.10 # -10% daily limit
    
    # Fibonacci levels for extensions
    FIB_LEVELS = [1.0, 1.272, 1.414, 1.618, 2.0, 2.618]
    
    # Percentile thresholds
    PERCENTILE_CONSERVATIVE = 75
    PERCENTILE_MODERATE = 85
    PERCENTILE_AGGRESSIVE = 95
    
    def __init__(self, fetcher=None, sharehub=None):
        """
        Initialize analyzer with optional data sources.
        
        Args:
            fetcher: NepseFetcher instance for price data
            sharehub: ShareHubAPI instance for broker data
        """
        self.fetcher = fetcher
        self.sharehub = sharehub
    
    def analyze(
        self,
        symbol: str,
        price_history: pd.DataFrame = None,
        broker_data: Dict = None,
        current_price: float = None,
        lookback_days: int = 365,
    ) -> PriceTargetAnalysis:
        """
        Generate comprehensive price target analysis.
        
        Args:
            symbol: Stock symbol
            price_history: Optional pre-fetched OHLCV DataFrame
            broker_data: Optional pre-fetched broker accumulation data
            current_price: Optional current price override
            lookback_days: Days of history to analyze
            
        Returns:
            PriceTargetAnalysis with all targets and metadata
        """
        symbol = symbol.upper()
        logger.info(f"🎯 Starting price target analysis for {symbol}")
        
        # Fetch data if not provided
        df = price_history
        if df is None and self.fetcher:
            df = self.fetcher.safe_fetch_data(symbol, days=lookback_days, min_rows=30)
        
        if df is None or df.empty or len(df) < 30:
            logger.warning(f"{symbol}: Insufficient data for target analysis")
            return self._create_empty_analysis(symbol, current_price or 0)
        
        # Ensure data is clean
        df = self._prepare_dataframe(df)
        
        # Current price (use latest close if not provided)
        ltp = current_price or float(df.iloc[-1]["close"])
        
        # Initialize analysis
        analysis = PriceTargetAnalysis(
            symbol=symbol,
            current_price=ltp,
            analysis_date=date.today(),
        )
        
        # Calculate all targets using different methods
        all_targets = []
        
        # 1. Technical Resistance Levels
        resistance_targets = self._calculate_resistance_targets(df, ltp)
        all_targets.extend(resistance_targets)
        
        # 2. Fibonacci Extension Targets
        fib_targets = self._calculate_fibonacci_targets(df, ltp)
        all_targets.extend(fib_targets)
        
        # 3. ATR-Based Targets (Volatility-adjusted)
        atr_targets = self._calculate_atr_targets(df, ltp)
        all_targets.extend(atr_targets)
        
        # 4. Volume Profile Analysis
        volume_targets, poc, hvn = self._calculate_volume_profile_targets(df, ltp)
        all_targets.extend(volume_targets)
        analysis.volume_poc = poc
        analysis.high_volume_nodes = hvn
        
        # 5. Statistical Targets (Percentile analysis)
        stat_targets = self._calculate_statistical_targets(df, ltp)
        all_targets.extend(stat_targets)
        
        # 6. All-Time/52-Week High Targets
        historical_targets = self._calculate_historical_targets(df, ltp)
        all_targets.extend(historical_targets)
        
        # 7. Circuit Breaker Targets (NEPSE-specific)
        circuit_targets = self._calculate_circuit_targets(ltp)
        all_targets.extend(circuit_targets)
        
        # Store all targets
        analysis.all_targets = sorted(all_targets, key=lambda x: x.level)
        
        # Calculate support levels
        analysis.support_levels = self._calculate_support_levels(df, ltp)
        analysis.nearest_support = analysis.support_levels[0] if analysis.support_levels else ltp * 0.95
        
        # Calculate risk metrics
        analysis.downside_risk_percent = ((ltp - analysis.nearest_support) / ltp) * 100
        
        # Classify targets into conservative/moderate/aggressive
        self._classify_targets(analysis, all_targets, ltp)
        
        # Assess trend and momentum
        analysis.trend_direction = self._assess_trend(df)
        analysis.momentum_score = self._calculate_momentum_score(df)
        
        # Check broker accumulation if data available
        if broker_data or self.sharehub:
            analysis.broker_accumulation = self._check_broker_accumulation(symbol, broker_data)
        
        # ========== SMART MONEY RISK ASSESSMENT (NEW) ==========
        # This integrates dump risk and manipulation detection to provide
        # a COMPLETE picture, not just technical targets
        analysis = self._assess_smart_money_risk(symbol, analysis, ltp)
        
        # Calculate risk-reward ratio
        if analysis.moderate_target and analysis.downside_risk_percent > 0:
            upside = analysis.moderate_target.upside_percent
            analysis.risk_reward_ratio = upside / analysis.downside_risk_percent
        
        # Add warnings (including smart money warnings)
        analysis.warnings = self._generate_warnings(analysis, df, ltp)
        
        # Adjust probabilities based on trend AND dump risk
        self._adjust_probabilities(analysis)
        
        logger.info(f"🎯 {symbol}: Found {len(all_targets)} potential targets, "
                   f"Conservative: Rs.{analysis.conservative_target.level if analysis.conservative_target else 'N/A'}, "
                   f"Dump Risk: {analysis.dump_risk}")
        
        return analysis
    
    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare and clean the dataframe."""
        df = df.copy()
        
        # Ensure numeric columns
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Sort by date
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.sort_values("date")
        
        # Drop rows with missing close prices
        df = df.dropna(subset=["close"])
        
        return df.reset_index(drop=True)
    
    def _calculate_resistance_targets(self, df: pd.DataFrame, ltp: float) -> List[PriceTarget]:
        """Calculate targets from technical resistance levels."""
        targets = []
        
        # Find pivot highs (local maxima) - potential resistance levels
        highs = df["high"].values
        window = min(10, len(df) // 10) or 3
        
        pivot_highs = []
        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[max(0, i-window):i+window+1]):
                pivot_highs.append(float(highs[i]))
        
        # Filter to levels above current price
        resistance_levels = [r for r in pivot_highs if r > ltp * 1.02]
        
        # Cluster nearby levels (within 2%)
        resistance_levels = self._cluster_price_levels(resistance_levels)
        
        # Sort by proximity to current price
        resistance_levels = sorted(resistance_levels, key=lambda x: x - ltp)
        
        for i, level in enumerate(resistance_levels[:5]):  # Top 5 resistances
            upside = ((level / ltp) - 1) * 100
            
            # Probability decreases with distance
            base_prob = 80 - (i * 12)  # 80%, 68%, 56%, 44%, 32%
            prob = max(15, base_prob - (upside * 0.8))  # Reduce more for higher targets
            
            # Days estimate based on ATR
            atr = self._get_atr(df)
            if atr > 0:
                days = int((level - ltp) / (atr * 0.5))  # Assumes 50% of ATR per day avg move
                days = max(3, min(days, 90))  # Bound between 3-90 days
            else:
                days = 7 + (i * 5)
            
            target = PriceTarget(
                level=round(level, 2),
                name=f"Resistance R{i+1}",
                method="Technical Resistance",
                probability=prob,
                days_estimate=days,
                upside_percent=upside,
                confidence="HIGH" if upside < 10 else ("MEDIUM" if upside < 20 else "LOW"),
                reasoning=f"Historical pivot high tested {self._count_tests(df, level)} times"
            )
            targets.append(target)
        
        return targets
    
    def _calculate_fibonacci_targets(self, df: pd.DataFrame, ltp: float) -> List[PriceTarget]:
        """Calculate Fibonacci extension targets from recent swing."""
        targets = []
        
        # Find recent swing low to current (for uptrend extensions)
        # Look for lowest point in last 90 days
        recent_df = df.tail(90)
        if len(recent_df) < 10:
            return targets
        
        swing_low = float(recent_df["low"].min())
        swing_high = float(recent_df["high"].max())
        
        # Only calculate if we're in an uptrend (LTP > swing midpoint)
        midpoint = (swing_low + swing_high) / 2
        if ltp < midpoint:
            return targets  # Not in uptrend, Fib extensions less relevant
        
        # Calculate range for extensions
        range_size = swing_high - swing_low
        
        for fib_level in self.FIB_LEVELS:
            if fib_level <= 1.0:
                continue  # Skip retracements, only extensions
            
            target_price = swing_low + (range_size * fib_level)
            
            # Only include targets above current price
            if target_price <= ltp * 1.02:
                continue
            
            upside = ((target_price / ltp) - 1) * 100
            
            # Probability based on Fibonacci level
            prob_map = {1.272: 65, 1.414: 55, 1.618: 45, 2.0: 30, 2.618: 15}
            base_prob = prob_map.get(fib_level, 40)
            
            # Reduce probability for very high targets
            prob = max(10, base_prob - max(0, (upside - 20) * 0.5))
            
            target = PriceTarget(
                level=round(target_price, 2),
                name=f"Fibonacci {fib_level}",
                method="Fibonacci Extension",
                probability=prob,
                days_estimate=self._estimate_days_to_target(df, ltp, target_price),
                upside_percent=upside,
                confidence="MEDIUM" if upside < 20 else "LOW",
                reasoning=f"Extension from swing low {swing_low:.0f} to high {swing_high:.0f}"
            )
            targets.append(target)
        
        return targets
    
    def _calculate_atr_targets(self, df: pd.DataFrame, ltp: float) -> List[PriceTarget]:
        """Calculate ATR-based volatility targets."""
        targets = []
        
        atr = self._get_atr(df)
        if atr <= 0:
            return targets
        
        # ATR multipliers for different targets
        # 2x ATR = Conservative (1-2 days)
        # 3x ATR = Moderate (3-5 days)
        # 5x ATR = Aggressive (5-10 days)
        # 8x ATR = Extended (10-20 days)
        
        atr_multipliers = [
            (2.0, "ATR 2x (Short-term)", 75, 2, "HIGH"),
            (3.0, "ATR 3x (Swing)", 60, 5, "MEDIUM"),
            (5.0, "ATR 5x (Extended)", 40, 10, "MEDIUM"),
            (8.0, "ATR 8x (Long-term)", 25, 20, "LOW"),
        ]
        
        for mult, name, base_prob, base_days, confidence in atr_multipliers:
            target_price = ltp + (atr * mult)
            upside = ((target_price / ltp) - 1) * 100
            
            # Adjust probability based on current trend
            trend_factor = 1.0
            if len(df) >= 20:
                ema20 = df["close"].ewm(span=20).mean().iloc[-1]
                if ltp > ema20:
                    trend_factor = 1.1  # Uptrend boost
                else:
                    trend_factor = 0.85  # Downtrend penalty
            
            prob = min(85, base_prob * trend_factor)
            
            target = PriceTarget(
                level=round(target_price, 2),
                name=name,
                method="ATR Volatility",
                probability=prob,
                days_estimate=base_days,
                upside_percent=upside,
                confidence=confidence,
                reasoning=f"Based on {atr:.1f} ATR ({(atr/ltp)*100:.1f}% daily volatility)"
            )
            targets.append(target)
        
        return targets
    
    def _calculate_volume_profile_targets(
        self, df: pd.DataFrame, ltp: float
    ) -> Tuple[List[PriceTarget], float, List[float]]:
        """
        Calculate targets from Volume Profile Analysis.
        
        Volume Profile shows where most trading occurred (POC = Point of Control).
        High Volume Nodes (HVN) act as support/resistance.
        Low Volume Nodes (LVN) are areas price moves through quickly.
        """
        targets = []
        poc = 0.0
        hvn = []
        
        if "volume" not in df.columns or df["volume"].sum() == 0:
            return targets, poc, hvn
        
        # Create price bins (0.5% intervals)
        price_min = df["low"].min()
        price_max = df["high"].max()
        bin_size = ltp * 0.005  # 0.5% bins
        
        bins = np.arange(price_min, price_max + bin_size, bin_size)
        if len(bins) < 3:
            return targets, poc, hvn
        
        # Calculate volume at each price level
        volume_profile = {}
        for idx, row in df.iterrows():
            # Distribute volume across the day's range (simplified)
            low, high, vol = row["low"], row["high"], row["volume"]
            if vol > 0 and high > low:
                bins_in_range = [b for b in bins if low <= b <= high]
                vol_per_bin = vol / max(1, len(bins_in_range))
                for b in bins_in_range:
                    volume_profile[b] = volume_profile.get(b, 0) + vol_per_bin
        
        if not volume_profile:
            return targets, poc, hvn
        
        # Find Point of Control (highest volume level)
        poc_level = max(volume_profile, key=volume_profile.get)
        poc = float(poc_level)
        
        # Find High Volume Nodes (top 20% by volume)
        sorted_levels = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)
        top_20_pct = max(1, len(sorted_levels) // 5)
        hvn = [float(level) for level, _ in sorted_levels[:top_20_pct]]
        
        # Create targets from HVN above current price
        hvn_above = [h for h in hvn if h > ltp * 1.02]
        
        for i, level in enumerate(sorted(hvn_above)[:3]):
            upside = ((level / ltp) - 1) * 100
            
            # HVN targets have high probability because price is "attracted" to them
            prob = 70 - (i * 10)  # 70%, 60%, 50%
            
            target = PriceTarget(
                level=round(level, 2),
                name=f"Volume Node {i+1}",
                method="Volume Profile",
                probability=prob,
                days_estimate=5 + (i * 3),
                upside_percent=upside,
                confidence="HIGH" if upside < 8 else "MEDIUM",
                reasoning="High volume accumulation zone - price likely to revisit"
            )
            targets.append(target)
        
        return targets, poc, hvn
    
    def _calculate_statistical_targets(self, df: pd.DataFrame, ltp: float) -> List[PriceTarget]:
        """Calculate targets from statistical analysis."""
        targets = []
        
        highs = df["high"].values
        
        # Percentile-based targets
        percentiles = [
            (self.PERCENTILE_CONSERVATIVE, "75th Percentile", 70, "HIGH"),
            (self.PERCENTILE_MODERATE, "85th Percentile", 50, "MEDIUM"),
            (self.PERCENTILE_AGGRESSIVE, "95th Percentile", 25, "LOW"),
            (99, "99th Percentile", 10, "LOW"),
        ]
        
        for pct, name, prob, confidence in percentiles:
            target_price = float(np.percentile(highs, pct))
            
            if target_price <= ltp * 1.01:
                continue
            
            upside = ((target_price / ltp) - 1) * 100
            
            target = PriceTarget(
                level=round(target_price, 2),
                name=name,
                method="Statistical Percentile",
                probability=prob,
                days_estimate=self._estimate_days_to_target(df, ltp, target_price),
                upside_percent=upside,
                confidence=confidence,
                reasoning=f"Price reached this level {100-pct}% of the time historically"
            )
            targets.append(target)
        
        # Standard deviation bands
        close_mean = df["close"].mean()
        close_std = df["close"].std()
        
        for mult, name, prob, confidence in [(1, "1 StdDev", 68, "HIGH"), (2, "2 StdDev", 30, "LOW")]:
            target_price = close_mean + (close_std * mult)
            if target_price > ltp * 1.02:
                upside = ((target_price / ltp) - 1) * 100
                target = PriceTarget(
                    level=round(target_price, 2),
                    name=f"+{name} Band",
                    method="Statistical StdDev",
                    probability=prob,
                    days_estimate=10 * mult,
                    upside_percent=upside,
                    confidence=confidence,
                    reasoning=f"Statistical upper band at {mult} standard deviations"
                )
                targets.append(target)
        
        return targets
    
    def _calculate_historical_targets(self, df: pd.DataFrame, ltp: float) -> List[PriceTarget]:
        """Calculate targets from historical highs."""
        targets = []
        
        # 52-week high
        if len(df) >= 252:
            high_52w = float(df.tail(252)["high"].max())
        else:
            high_52w = float(df["high"].max())
        
        # All-time high (from available data)
        all_time_high = float(df["high"].max())
        
        # 52-week high target
        if high_52w > ltp * 1.02:
            upside = ((high_52w / ltp) - 1) * 100
            
            # Probability based on how close we are to it
            distance_pct = upside
            prob = max(20, 80 - (distance_pct * 2))
            
            target = PriceTarget(
                level=round(high_52w, 2),
                name="52-Week High",
                method="Historical Peak",
                probability=prob,
                days_estimate=self._estimate_days_to_target(df, ltp, high_52w),
                upside_percent=upside,
                confidence="HIGH" if upside < 10 else "MEDIUM",
                reasoning="Proven price level - psychological and technical significance"
            )
            targets.append(target)
        
        # All-time high (if different from 52w)
        if abs(all_time_high - high_52w) > (ltp * 0.02) and all_time_high > ltp * 1.02:
            upside = ((all_time_high / ltp) - 1) * 100
            prob = max(10, 60 - (upside * 1.5))
            
            target = PriceTarget(
                level=round(all_time_high, 2),
                name="All-Time High",
                method="Historical Peak",
                probability=prob,
                days_estimate=self._estimate_days_to_target(df, ltp, all_time_high) + 10,
                upside_percent=upside,
                confidence="LOW",
                reasoning="Ultimate price ceiling - requires strong catalyst"
            )
            targets.append(target)
        
        return targets
    
    def _calculate_circuit_targets(self, ltp: float) -> List[PriceTarget]:
        """
        Calculate NEPSE circuit breaker targets.
        NEPSE stocks can move +/-10% in a single day.
        """
        targets = []
        
        # Upper circuit (1 day)
        uc1 = ltp * (1 + self.CIRCUIT_UP)
        # Upper circuit (2 consecutive days)
        uc2 = uc1 * (1 + self.CIRCUIT_UP)
        # Upper circuit (3 consecutive days - rare but happens)
        uc3 = uc2 * (1 + self.CIRCUIT_UP)
        
        circuit_targets = [
            (uc1, "1-Day Upper Circuit", 35, 1, "MEDIUM", "Requires very strong buying; 10% gain in single day"),
            (uc2, "2-Day Circuit Run", 15, 2, "LOW", "Two consecutive 10% upper circuits - rare event"),
            (uc3, "3-Day Circuit Run", 5, 3, "LOW", "Three consecutive circuits - exceptional event"),
        ]
        
        for level, name, prob, days, confidence, reasoning in circuit_targets:
            upside = ((level / ltp) - 1) * 100
            
            target = PriceTarget(
                level=round(level, 2),
                name=name,
                method="Circuit Breaker",
                probability=prob,
                days_estimate=days,
                upside_percent=upside,
                confidence=confidence,
                reasoning=reasoning
            )
            targets.append(target)
        
        return targets
    
    def _calculate_support_levels(self, df: pd.DataFrame, ltp: float) -> List[float]:
        """Calculate support levels below current price."""
        supports = []
        
        # Pivot lows
        lows = df["low"].values
        window = min(10, len(df) // 10) or 3
        
        for i in range(window, len(lows) - window):
            if lows[i] == min(lows[max(0, i-window):i+window+1]):
                if lows[i] < ltp * 0.98:  # Below current price
                    supports.append(float(lows[i]))
        
        # Cluster and sort
        supports = self._cluster_price_levels(supports)
        supports = sorted(supports, reverse=True)  # Nearest first
        
        # Always include some safety levels
        if not supports or supports[0] > ltp * 0.95:
            supports.insert(0, round(ltp * 0.95, 2))  # -5%
        
        return supports[:5]
    
    def _classify_targets(
        self, 
        analysis: PriceTargetAnalysis, 
        all_targets: List[PriceTarget], 
        ltp: float
    ):
        """
        Classify targets into conservative, moderate, aggressive, maximum.
        
        RULE: Each category MUST have a DISTINCT target (no duplicates).
        
        Categories:
        - Conservative: 5-10% upside, highest probability
        - Moderate: 10-20% upside, medium probability
        - Aggressive: 20-50% upside, lower probability
        - Maximum: Highest price level (50%+ upside typically)
        """
        if not all_targets:
            return
        
        # Filter to valid targets (above current price by at least 1%)
        valid_targets = [t for t in all_targets if t.level > ltp * 1.01]
        
        if not valid_targets:
            return
        
        # Sort by level (lowest first) for easier bucketing
        sorted_by_level = sorted(valid_targets, key=lambda x: x.level)
        
        # Track used targets to ensure no duplicates
        used_levels = set()
        
        # Helper to find best target in upside range
        def find_best_target(targets: List[PriceTarget], min_upside: float, max_upside: float) -> Optional[PriceTarget]:
            candidates = [
                t for t in targets 
                if min_upside <= t.upside_percent < max_upside 
                and round(t.level, 2) not in used_levels
            ]
            if not candidates:
                return None
            # Prefer highest probability within range
            return max(candidates, key=lambda x: (x.probability, -x.level))
        
        # 1. CONSERVATIVE: 5-12% upside (nearest achievable target)
        conservative = find_best_target(sorted_by_level, 5, 12)
        if conservative:
            analysis.conservative_target = conservative
            used_levels.add(round(conservative.level, 2))
        
        # 2. MODERATE: 12-25% upside (medium-term swing target)
        moderate = find_best_target(sorted_by_level, 12, 25)
        if moderate:
            analysis.moderate_target = moderate
            used_levels.add(round(moderate.level, 2))
        
        # If no moderate found in 12-25%, look for next best above conservative
        if not moderate and conservative:
            fallback_candidates = [
                t for t in sorted_by_level 
                if t.upside_percent > conservative.upside_percent + 3  # At least 3% higher
                and round(t.level, 2) not in used_levels
            ]
            if fallback_candidates:
                moderate = max(fallback_candidates[:3], key=lambda x: x.probability)
                analysis.moderate_target = moderate
                used_levels.add(round(moderate.level, 2))
        
        # 3. AGGRESSIVE: 25-80% upside (major breakout target)
        aggressive = find_best_target(sorted_by_level, 25, 80)
        if aggressive:
            analysis.aggressive_target = aggressive
            used_levels.add(round(aggressive.level, 2))
        
        # 4. MAXIMUM THEORETICAL: Highest level, 50%+ upside or just the max
        max_candidates = [
            t for t in sorted_by_level 
            if round(t.level, 2) not in used_levels
        ]
        if max_candidates:
            analysis.maximum_theoretical = max(max_candidates, key=lambda x: x.level)
        elif sorted_by_level:
            # If all levels used, just use the absolute maximum
            analysis.maximum_theoretical = max(sorted_by_level, key=lambda x: x.level)
        
        # VALIDATION: Ensure no two categories have identical levels
        targets = [
            analysis.conservative_target,
            analysis.moderate_target,
            analysis.aggressive_target,
            analysis.maximum_theoretical
        ]
        levels_seen = {}
        for i, t in enumerate(targets):
            if t:
                level_key = round(t.level, 2)
                if level_key in levels_seen:
                    # Duplicate detected - clear the later one
                    if i == 1:
                        analysis.moderate_target = None
                    elif i == 2:
                        analysis.aggressive_target = None
                    elif i == 3 and analysis.aggressive_target:
                        # Keep max only if it's different from aggressive
                        if round(analysis.aggressive_target.level, 2) == level_key:
                            analysis.maximum_theoretical = None
                else:
                    levels_seen[level_key] = i
    
    def _get_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Get Average True Range."""
        if len(df) < period + 1:
            return df["close"].mean() * 0.02  # Fallback: 2% of price
        
        try:
            if ta:
                atr = ta.atr(df["high"], df["low"], df["close"], length=period)
                if atr is not None and not atr.isna().all():
                    return float(atr.iloc[-1])
        except:
            pass
        
        # Manual ATR calculation
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
        
        if tr:
            return float(np.mean(tr[-period:]))
        return df["close"].mean() * 0.02
    
    def _assess_trend(self, df: pd.DataFrame) -> str:
        """Assess current trend direction."""
        if len(df) < 21:
            return "NEUTRAL"
        
        close = df["close"].values
        ema9 = pd.Series(close).ewm(span=9).mean().values[-1]
        ema21 = pd.Series(close).ewm(span=21).mean().values[-1]
        
        ltp = close[-1]
        
        if ltp > ema9 > ema21:
            return "BULLISH"
        elif ltp < ema9 < ema21:
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    def _calculate_momentum_score(self, df: pd.DataFrame) -> float:
        """Calculate momentum score (0-100)."""
        score = 50.0  # Neutral base
        
        if len(df) < 14:
            return score
        
        close = df["close"]
        
        # RSI component (0-30 points)
        try:
            if ta:
                rsi = ta.rsi(close, length=14)
                if rsi is not None and not rsi.isna().all():
                    rsi_val = float(rsi.iloc[-1])
                    if rsi_val > 70:
                        score -= 10  # Overbought
                    elif rsi_val > 50:
                        score += (rsi_val - 50) * 0.5  # +0 to +10
                    elif rsi_val < 30:
                        score -= 15  # Oversold (bearish)
                    else:
                        score += (rsi_val - 50) * 0.3
        except:
            pass
        
        # Price vs EMA20 component (0-20 points)
        ema20 = close.ewm(span=20).mean().iloc[-1]
        ltp = close.iloc[-1]
        pct_above_ema = ((ltp / ema20) - 1) * 100
        
        if pct_above_ema > 0:
            score += min(20, pct_above_ema * 2)
        else:
            score += max(-20, pct_above_ema * 2)
        
        # Volume trend (0-10 points)
        if "volume" in df.columns and len(df) >= 20:
            recent_vol = df["volume"].tail(5).mean()
            avg_vol = df["volume"].tail(20).mean()
            if avg_vol > 0:
                vol_ratio = recent_vol / avg_vol
                if vol_ratio > 1.5:
                    score += 10
                elif vol_ratio > 1.0:
                    score += 5
        
        return max(0, min(100, score))
    
    def _check_broker_accumulation(self, symbol: str, broker_data: Dict = None) -> bool:
        """Check if brokers are accumulating."""
        if broker_data:
            net_buy = broker_data.get("net_buy_amount", 0)
            return net_buy > 0
        
        if self.sharehub:
            try:
                data = self.sharehub.get_broker_analysis(symbol, duration="1W")
                if data:
                    total_buy = sum(b.buy_amount for b in data if b.buy_amount > 0)
                    total_sell = sum(b.sell_amount for b in data if b.sell_amount > 0)
                    return total_buy > total_sell
            except:
                pass
        
        return False
    
    def _assess_smart_money_risk(
        self, 
        symbol: str, 
        analysis: PriceTargetAnalysis, 
        ltp: float
    ) -> PriceTargetAnalysis:
        """
        Assess smart money dump risk and manipulation.
        
        This is CRITICAL because technical targets are meaningless if
        smart money is distributing or the stock is manipulated.
        """
        try:
            if not self.sharehub:
                analysis.dump_risk = "UNKNOWN"
                analysis.buy_recommendation = "CHECK_FULL_ANALYSIS"
                return analysis
            
            # 1. Get 1-Month broker data for dump risk
            broker_data_1m = self.sharehub.get_broker_analysis(symbol, duration="1M")
            broker_data_1w = self.sharehub.get_broker_analysis(symbol, duration="1W")
            
            if not broker_data_1m:
                analysis.dump_risk = "UNKNOWN"
                analysis.buy_recommendation = "CHECK_FULL_ANALYSIS"
                return analysis
            
            # 2. Calculate broker metrics
            total_buy_1m = sum(b.buy_amount for b in broker_data_1m if b.buy_amount > 0)
            total_buy_qty_1m = sum(b.buy_quantity for b in broker_data_1m if b.buy_quantity > 0)
            total_sell_1m = sum(b.sell_amount for b in broker_data_1m if b.sell_amount > 0)
            
            net_1m = sum(b.net_quantity for b in broker_data_1m)
            net_1w = sum(b.net_quantity for b in broker_data_1w) if broker_data_1w else 0
            
            # 3. Calculate broker avg cost
            broker_avg = total_buy_1m / total_buy_qty_1m if total_buy_qty_1m > 0 else ltp
            broker_profit_pct = ((ltp - broker_avg) / broker_avg * 100) if broker_avg > 0 else 0
            
            # 4. Determine dump risk
            dump_risk_score = 0
            dump_reasons = []
            
            # Rule 1: Broker profit > 8% = elevated dump risk
            if broker_profit_pct > 8:
                dump_risk_score += 30
                dump_reasons.append(f"Brokers at +{broker_profit_pct:.1f}% profit")
            
            # Rule 2: 1M accumulation but 1W distribution = distribution phase starting
            if net_1m > 0 and net_1w < 0:
                dump_risk_score += 25
                dump_reasons.append("1W distribution started")
            
            # Rule 3: Overall distribution (1M net < 0)
            if net_1m < 0:
                dump_risk_score += 35
                dump_reasons.append("Smart money selling (1M net negative)")
            
            # Rule 4: High concentration (top brokers control > 40%)
            if broker_data_1m:
                sorted_brokers = sorted(broker_data_1m, key=lambda x: x.net_quantity, reverse=True)
                top3_qty = sum(b.net_quantity for b in sorted_brokers[:3] if b.net_quantity > 0)
                total_qty = sum(b.buy_quantity for b in broker_data_1m if b.buy_quantity > 0)
                if total_qty > 0 and top3_qty / total_qty > 0.40:
                    dump_risk_score += 20
                    dump_reasons.append("High broker concentration")
            
            # 5. Classify dump risk
            if dump_risk_score >= 50:
                analysis.dump_risk = "HIGH"
            elif dump_risk_score >= 25:
                analysis.dump_risk = "MEDIUM"
            else:
                analysis.dump_risk = "LOW"
            
            # 6. Determine buy recommendation
            if analysis.dump_risk == "HIGH":
                analysis.buy_recommendation = "AVOID"
                analysis.warnings.append(f"🚨 HIGH DUMP RISK: {', '.join(dump_reasons)}")
            elif analysis.dump_risk == "MEDIUM":
                analysis.buy_recommendation = "PAPER-TRADE"
                analysis.warnings.append(f"⚠️ MEDIUM DUMP RISK: {', '.join(dump_reasons)}")
            else:
                analysis.buy_recommendation = "BUY" if analysis.trend_direction == "BULLISH" else "NEUTRAL"
            
            # 7. Store manipulation score (basic calculation)
            analysis.manipulation_score = min(100, dump_risk_score * 1.5)
            
        except Exception as e:
            logger.warning(f"Could not assess smart money risk for {symbol}: {e}")
            analysis.dump_risk = "UNKNOWN"
            analysis.buy_recommendation = "CHECK_FULL_ANALYSIS"
        
        return analysis
    
    def _estimate_days_to_target(self, df: pd.DataFrame, ltp: float, target: float) -> int:
        """Estimate trading days to reach target."""
        atr = self._get_atr(df)
        if atr <= 0:
            return 10
        
        distance = target - ltp
        # Assume average daily progress = 50% of ATR (conservative)
        avg_daily_progress = atr * 0.5
        
        if avg_daily_progress <= 0:
            return 10
        
        days = int(distance / avg_daily_progress)
        return max(2, min(60, days))  # Bound between 2-60 days
    
    def _count_tests(self, df: pd.DataFrame, level: float, tolerance: float = 0.02) -> int:
        """Count how many times price tested a level."""
        upper = level * (1 + tolerance)
        lower = level * (1 - tolerance)
        
        count = 0
        for _, row in df.iterrows():
            if lower <= row["high"] <= upper:
                count += 1
        
        return count
    
    def _cluster_price_levels(self, levels: List[float], tolerance: float = 0.02) -> List[float]:
        """Cluster nearby price levels together."""
        if not levels:
            return []
        
        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]
        
        for i in range(1, len(levels)):
            if levels[i] <= current_cluster[-1] * (1 + tolerance):
                current_cluster.append(levels[i])
            else:
                clusters.append(np.mean(current_cluster))
                current_cluster = [levels[i]]
        
        clusters.append(np.mean(current_cluster))
        return [round(c, 2) for c in clusters]
    
    def _generate_warnings(
        self, 
        analysis: PriceTargetAnalysis, 
        df: pd.DataFrame, 
        ltp: float
    ) -> List[str]:
        """Generate warnings based on analysis."""
        warnings = []
        
        # Overbought warning
        if analysis.momentum_score > 80:
            warnings.append("⚠️ Stock appears overbought - targets may take longer to reach")
        
        # Near all-time high warning
        if analysis.maximum_theoretical:
            ath = analysis.maximum_theoretical.level
            if ltp > ath * 0.95:
                warnings.append("⚠️ Trading near all-time high - limited upside potential")
        
        # High volatility warning
        atr = self._get_atr(df)
        atr_pct = (atr / ltp) * 100 if ltp > 0 else 0
        if atr_pct > 4:
            warnings.append(f"⚠️ High volatility ({atr_pct:.1f}% daily) - expect large swings")
        
        # Downtrend warning
        if analysis.trend_direction == "BEARISH":
            warnings.append("⚠️ Stock in downtrend - wait for trend reversal before buying")
        
        # Low liquidity warning (if volume data available)
        if "volume" in df.columns:
            avg_volume = df["volume"].tail(20).mean()
            if avg_volume < 1000:
                warnings.append("⚠️ Low liquidity - may be difficult to exit at target prices")
        
        return warnings
    
    def _adjust_probabilities(self, analysis: PriceTargetAnalysis):
        """Adjust target probabilities based on overall market context AND dump risk."""
        trend_multiplier = {
            "BULLISH": 1.15,
            "NEUTRAL": 1.0,
            "BEARISH": 0.75,
        }.get(analysis.trend_direction, 1.0)
        
        accumulation_boost = 1.10 if analysis.broker_accumulation else 1.0
        
        # NEW: Dump risk penalty - CRITICAL for accurate probability
        dump_risk_penalty = {
            "HIGH": 0.40,    # 60% probability reduction
            "MEDIUM": 0.70,  # 30% probability reduction
            "LOW": 1.0,      # No penalty
            "UNKNOWN": 0.85, # Slight caution
        }.get(analysis.dump_risk, 0.85)
        
        for target in analysis.all_targets:
            adjusted = target.probability * trend_multiplier * accumulation_boost * dump_risk_penalty
            target.probability = max(5, min(90, adjusted))
        
        # Also adjust main targets
        for target in [analysis.conservative_target, analysis.moderate_target, 
                       analysis.aggressive_target, analysis.maximum_theoretical]:
            if target:
                adjusted = target.probability * trend_multiplier * accumulation_boost * dump_risk_penalty
                target.probability = max(5, min(90, adjusted))
    
    def _create_empty_analysis(self, symbol: str, current_price: float) -> PriceTargetAnalysis:
        """Create empty analysis when data is insufficient."""
        return PriceTargetAnalysis(
            symbol=symbol,
            current_price=current_price,
            analysis_date=date.today(),
            warnings=["⚠️ Insufficient data for target analysis"],
        )
    
    def format_report(self, analysis: PriceTargetAnalysis) -> str:
        """Format analysis as readable report."""
        lines = []
        
        lines.append("=" * 70)
        lines.append(f"🎯 PRICE TARGET ANALYSIS: {analysis.symbol}")
        lines.append(f"   Current Price: Rs. {analysis.current_price:,.2f}")
        lines.append(f"   Analysis Date: {analysis.analysis_date}")
        lines.append(f"   Trend: {analysis.trend_direction} | Momentum: {analysis.momentum_score:.0f}/100")
        
        # ========== SMART MONEY VERDICT (NEW) ==========
        dump_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "UNKNOWN": "⚪"}.get(analysis.dump_risk, "⚪")
        rec_emoji = {"BUY": "✅", "AVOID": "🚫", "PAPER-TRADE": "⚠️", "NEUTRAL": "➖"}.get(analysis.buy_recommendation, "➖")
        lines.append(f"   Dump Risk: {dump_emoji} {analysis.dump_risk} | Recommendation: {rec_emoji} {analysis.buy_recommendation}")
        
        if analysis.broker_accumulation:
            lines.append("   📊 Broker Accumulation: DETECTED (Bullish)")
        lines.append("=" * 70)
        
        # ========== CRITICAL WARNING IF HIGH DUMP RISK ==========
        if analysis.dump_risk == "HIGH":
            lines.append("\n" + "🚨" * 20)
            lines.append("🚨 WARNING: HIGH DUMP RISK DETECTED!")
            lines.append("   Price targets below are THEORETICAL only.")
            lines.append("   Smart money may be distributing. DO NOT BUY.")
            lines.append("   Run '--action=analyze --stock " + analysis.symbol + "' for full analysis.")
            lines.append("🚨" * 20)
        elif analysis.dump_risk == "MEDIUM":
            lines.append("\n⚠️ CAUTION: Medium dump risk. Paper-trade first.")
        
        lines.append("\n📈 PRICE TARGETS (By Risk Profile)")
        lines.append("-" * 70)
        
        if analysis.conservative_target:
            t = analysis.conservative_target
            lines.append(f"\n🟢 CONSERVATIVE TARGET (High Probability)")
            lines.append(f"   Price:       Rs. {t.level:,.2f} (+{t.upside_percent:.1f}%)")
            lines.append(f"   Probability: {t.probability:.0f}%")
            lines.append(f"   Timeframe:   ~{t.days_estimate} trading days")
            lines.append(f"   Method:      {t.method}")
            lines.append(f"   Reasoning:   {t.reasoning}")
        
        if analysis.moderate_target:
            t = analysis.moderate_target
            lines.append(f"\n🟡 MODERATE TARGET (Balanced)")
            lines.append(f"   Price:       Rs. {t.level:,.2f} (+{t.upside_percent:.1f}%)")
            lines.append(f"   Probability: {t.probability:.0f}%")
            lines.append(f"   Timeframe:   ~{t.days_estimate} trading days")
            lines.append(f"   Method:      {t.method}")
            lines.append(f"   Reasoning:   {t.reasoning}")
        
        if analysis.aggressive_target:
            t = analysis.aggressive_target
            lines.append(f"\n🔴 AGGRESSIVE TARGET (High Risk/Reward)")
            lines.append(f"   Price:       Rs. {t.level:,.2f} (+{t.upside_percent:.1f}%)")
            lines.append(f"   Probability: {t.probability:.0f}%")
            lines.append(f"   Timeframe:   ~{t.days_estimate} trading days")
            lines.append(f"   Method:      {t.method}")
            lines.append(f"   Reasoning:   {t.reasoning}")
        
        if analysis.maximum_theoretical:
            t = analysis.maximum_theoretical
            lines.append(f"\n🚀 MAXIMUM THEORETICAL (Statistical Upper Bound)")
            lines.append(f"   Price:       Rs. {t.level:,.2f} (+{t.upside_percent:.1f}%)")
            lines.append(f"   Probability: {t.probability:.0f}%")
            lines.append(f"   Method:      {t.method}")
        
        lines.append("\n" + "-" * 70)
        lines.append("📊 RISK ASSESSMENT")
        lines.append("-" * 70)
        
        lines.append(f"\n   Nearest Support: Rs. {analysis.nearest_support:,.2f}")
        lines.append(f"   Downside Risk:   -{analysis.downside_risk_percent:.1f}%")
        if analysis.risk_reward_ratio > 0:
            lines.append(f"   Risk/Reward:     1:{analysis.risk_reward_ratio:.1f}")
        
        if analysis.volume_poc > 0:
            lines.append(f"\n   Volume POC:      Rs. {analysis.volume_poc:,.2f}")
            lines.append("   (Point of Control - highest volume price level)")
        
        if analysis.warnings:
            lines.append("\n⚠️ WARNINGS:")
            for w in analysis.warnings:
                lines.append(f"   {w}")
        
        if len(analysis.all_targets) > 4:
            lines.append(f"\n💡 {len(analysis.all_targets)} total target levels calculated.")
            lines.append("   Use --detailed flag for complete breakdown.")
        
        lines.append("\n" + "=" * 70)
        
        return "\n".join(lines)


# Convenience function for direct use
def analyze_price_targets(
    symbol: str,
    fetcher=None,
    sharehub=None,
    lookback_days: int = 365,
) -> PriceTargetAnalysis:
    """
    Convenience function to analyze price targets for a stock.
    
    Args:
        symbol: Stock symbol
        fetcher: NepseFetcher instance (optional, will create if not provided)
        sharehub: ShareHubAPI instance (optional)
        lookback_days: Days of history to analyze
        
    Returns:
        PriceTargetAnalysis with all targets
    """
    analyzer = PriceTargetAnalyzer(fetcher=fetcher, sharehub=sharehub)
    return analyzer.analyze(symbol, lookback_days=lookback_days)
