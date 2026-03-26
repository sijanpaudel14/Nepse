"""
IPO Exit Signal Analyzer - When to Sell Newly Listed Stocks.

This module helps traders who don't read charts understand when to sell IPO stocks
by analyzing volume patterns and broker flow data.

KEY SIGNALS DETECTED:
1. Volume Decay - Initial excitement fading (3+ days declining volume)
2. Distribution Day - Smart money exiting (high volume + price down)
3. Broker Flow Flip - Institutions selling to retail
4. Listing Gain Exhaustion - Price breaks below Day 2 low
5. Volume Spike After Quiet - Potential manipulation or news

WHY THIS MATTERS FOR NEPSE IPOs:
- Most IPOs see 50-200% listing gains
- Smart money (operators) exit within 5-10 trading days
- Retail often holds too long and gives back gains
- This analyzer detects when smart money is exiting

USAGE:
    from intelligence.ipo_exit_analyzer import IPOExitAnalyzer
    
    analyzer = IPOExitAnalyzer()
    result = analyzer.analyze("SOHL")
    print(result.verdict)  # "SELL 50%" or "HOLD"

Author: NEPSE AI Trading Engine
Date: 2026-03-26
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import date, datetime, timedelta
from enum import Enum
import numpy as np
import pandas as pd
from loguru import logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from data.sharehub_api import ShareHubAPI, BrokerData
    from data.fetcher import NepseFetcher
except ImportError:
    ShareHubAPI = None
    NepseFetcher = None
    BrokerData = None


# ============================================================
# DATA STRUCTURES
# ============================================================

class ExitSignal(Enum):
    """Exit signal strength levels."""
    STRONG_HOLD = "strong_hold"      # 🟢 No exit pressure
    HOLD = "hold"                     # 🟢 Normal conditions
    WATCH = "watch"                   # 🟡 Early warning signs
    CONSIDER_PARTIAL = "partial"      # 🟠 Sell 50% recommended
    SELL = "sell"                     # 🔴 Exit recommended
    URGENT_SELL = "urgent_sell"       # 🔴🔴 Exit immediately


@dataclass
class VolumeAnalysis:
    """Volume pattern analysis for IPO stocks."""
    days_analyzed: int = 0
    
    # Volume metrics
    avg_volume: float = 0
    volume_trend: str = "unknown"  # "increasing", "stable", "declining", "spike"
    consecutive_decline_days: int = 0
    volume_spike_detected: bool = False
    spike_day: Optional[int] = None
    
    # Day-by-day volumes (for visual)
    daily_volumes: List[Tuple[str, int]] = field(default_factory=list)
    
    # Interpretation
    signal: str = ""
    explanation: str = ""


@dataclass  
class BrokerFlowAnalysis:
    """Broker buying/selling flow analysis."""
    analysis_period: str = ""
    
    # Net flow
    net_quantity: int = 0
    net_amount: float = 0
    
    # Buyer breakdown
    institutional_buy_pct: float = 0  # Large brokers
    retail_buy_pct: float = 0         # Small brokers
    
    # Seller breakdown  
    institutional_sell_pct: float = 0
    retail_sell_pct: float = 0
    
    # Top players
    top_buyers: List[Dict] = field(default_factory=list)
    top_sellers: List[Dict] = field(default_factory=list)
    
    # Key insight
    flow_type: str = "neutral"  # "accumulation", "distribution", "neutral", "retail_buying"
    signal: str = ""
    explanation: str = ""


@dataclass
class PricePatternAnalysis:
    """Price pattern analysis for IPO stocks."""
    listing_price: float = 0
    current_price: float = 0
    day_2_low: float = 0
    
    # Gains
    listing_gain_pct: float = 0
    current_gain_pct: float = 0
    gain_exhaustion_pct: float = 0  # How much of listing gain is left
    
    # Key levels
    broke_day2_low: bool = False
    price_trend: str = "unknown"  # "uptrend", "consolidating", "downtrend"
    
    signal: str = ""
    explanation: str = ""


@dataclass
class IPOExitResult:
    """Complete IPO exit analysis result."""
    symbol: str
    analyzed_at: datetime = field(default_factory=datetime.now)
    days_since_listing: int = 0
    
    # Current state
    current_price: float = 0
    listing_price: float = 0
    gain_from_listing_pct: float = 0
    
    # Component analyses
    volume_analysis: VolumeAnalysis = field(default_factory=VolumeAnalysis)
    broker_flow: BrokerFlowAnalysis = field(default_factory=BrokerFlowAnalysis)
    price_pattern: PricePatternAnalysis = field(default_factory=PricePatternAnalysis)
    
    # Final verdict
    exit_signal: ExitSignal = ExitSignal.HOLD
    confidence: int = 0  # 0-100
    
    # Recommendations
    verdict: str = ""
    action: str = ""
    stop_loss: float = 0
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def format_report(self) -> str:
        """Format a human-readable exit analysis report."""
        lines = []
        
        # Header
        emoji_map = {
            ExitSignal.STRONG_HOLD: "🟢🟢",
            ExitSignal.HOLD: "🟢",
            ExitSignal.WATCH: "🟡",
            ExitSignal.CONSIDER_PARTIAL: "🟠",
            ExitSignal.SELL: "🔴",
            ExitSignal.URGENT_SELL: "🔴🔴",
        }
        emoji = emoji_map.get(self.exit_signal, "⚪")
        
        lines.append("=" * 60)
        lines.append(f"📊 IPO EXIT ANALYSIS: {self.symbol}")
        lines.append(f"   Listed {self.days_since_listing} trading days ago")
        lines.append("=" * 60)
        
        # Current status
        lines.append(f"\n💰 CURRENT STATUS")
        lines.append("-" * 40)
        lines.append(f"   Current Price:  Rs. {self.current_price:,.2f}")
        lines.append(f"   Listing Price:  Rs. {self.listing_price:,.2f}")
        gain_sign = "+" if self.gain_from_listing_pct >= 0 else ""
        lines.append(f"   Gain/Loss:      {gain_sign}{self.gain_from_listing_pct:.1f}%")
        
        # Volume Analysis
        lines.append(f"\n📈 VOLUME TREND (Last {self.volume_analysis.days_analyzed} Days)")
        lines.append("-" * 40)
        
        # Visual volume bars
        if self.volume_analysis.daily_volumes:
            max_vol = max(v for _, v in self.volume_analysis.daily_volumes) or 1
            for day_label, vol in self.volume_analysis.daily_volumes[-5:]:  # Last 5 days
                bar_len = int((vol / max_vol) * 20)
                bar = "█" * bar_len
                spike = " ← SPIKE!" if vol > max_vol * 0.9 and self.volume_analysis.volume_spike_detected else ""
                lines.append(f"   {day_label}: {vol:>10,} {bar}{spike}")
        
        lines.append(f"\n   Trend: {self.volume_analysis.volume_trend.upper()}")
        lines.append(f"   {self.volume_analysis.signal}")
        if self.volume_analysis.explanation:
            lines.append(f"   → {self.volume_analysis.explanation}")
        
        # Broker Flow (if available)
        if self.broker_flow.analysis_period:
            lines.append(f"\n🔍 WHO'S TRADING? ({self.broker_flow.analysis_period})")
            lines.append("-" * 40)
            
            net_sign = "+" if self.broker_flow.net_quantity >= 0 else ""
            lines.append(f"   Net Flow: {net_sign}{self.broker_flow.net_quantity:,} shares")
            
            if self.broker_flow.top_buyers:
                lines.append(f"\n   Top Buyers:")
                for b in self.broker_flow.top_buyers[:3]:
                    lines.append(f"      • {b['name']}: +{b['quantity']:,} shares")
            
            if self.broker_flow.top_sellers:
                lines.append(f"\n   Top Sellers:")
                for s in self.broker_flow.top_sellers[:3]:
                    lines.append(f"      • {s['name']}: -{s['quantity']:,} shares")
            
            lines.append(f"\n   Flow Type: {self.broker_flow.flow_type.upper()}")
            lines.append(f"   {self.broker_flow.signal}")
            if self.broker_flow.explanation:
                lines.append(f"   → {self.broker_flow.explanation}")
        else:
            lines.append(f"\n🔍 BROKER FLOW: Data not available")
            lines.append("   (Requires ShareHub authentication)")
        
        # Price Pattern
        lines.append(f"\n📉 PRICE PATTERN")
        lines.append("-" * 40)
        lines.append(f"   Day 2 Low:    Rs. {self.price_pattern.day_2_low:,.2f}")
        
        if self.price_pattern.broke_day2_low:
            lines.append(f"   ⚠️ BROKEN below Day 2 low!")
        else:
            buffer = (self.current_price - self.price_pattern.day_2_low) / self.price_pattern.day_2_low * 100
            lines.append(f"   Buffer:       {buffer:.1f}% above Day 2 low")
        
        lines.append(f"   Trend:        {self.price_pattern.price_trend.upper()}")
        if self.price_pattern.signal:
            lines.append(f"   {self.price_pattern.signal}")
        
        # Final Verdict
        lines.append(f"\n{'='*60}")
        lines.append(f"{emoji} VERDICT: {self.verdict}")
        lines.append("=" * 60)
        
        if self.action:
            lines.append(f"\n💡 ACTION: {self.action}")
        
        if self.stop_loss > 0:
            lines.append(f"🛑 STOP LOSS: Rs. {self.stop_loss:,.2f}")
        
        if self.reasons:
            lines.append(f"\n📋 REASONS:")
            for r in self.reasons:
                lines.append(f"   • {r}")
        
        if self.warnings:
            lines.append(f"\n⚠️ WARNINGS:")
            for w in self.warnings:
                lines.append(f"   • {w}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# ============================================================
# IPO EXIT ANALYZER
# ============================================================

class IPOExitAnalyzer:
    """
    Analyzes newly listed IPO stocks to determine when to sell.
    
    Uses volume patterns, broker flow, and price action to detect
    distribution (smart money exiting) and recommend exit timing.
    """
    
    # Broker codes considered "institutional" (large volume operators)
    INSTITUTIONAL_BROKERS = {
        "33", "58", "37", "47", "14", "26", "11", "29", "17", "38"
    }
    
    def __init__(self, fetcher: NepseFetcher = None, sharehub: ShareHubAPI = None):
        """
        Initialize the IPO Exit Analyzer.
        
        Args:
            fetcher: NepseFetcher for price data
            sharehub: ShareHubAPI for broker flow data (optional but recommended)
        """
        self.fetcher = fetcher or (NepseFetcher() if NepseFetcher else None)
        self.sharehub = sharehub or (ShareHubAPI() if ShareHubAPI else None)
    
    def _fetch_realtime_ltp(self, symbol: str) -> Optional[float]:
        """Fetch real-time Last Traded Price (LTP) for today."""
        # Method 1: Try NepseFetcher's live market data (most reliable)
        try:
            if self.fetcher:
                live_df = self.fetcher.fetch_live_market()
                if live_df is not None and not live_df.empty:
                    symbol_upper = symbol.upper()
                    match = live_df[live_df['symbol'].str.upper() == symbol_upper]
                    if not match.empty:
                        # 'close' in live market is actually the LTP
                        ltp = match.iloc[0].get('close') or match.iloc[0].get('ltp')
                        if ltp and float(ltp) > 0:
                            return float(ltp)
        except Exception as e:
            logger.debug(f"Live market failed: {e}")
        
        # Method 2: Try ShareHub real-time quote
        try:
            if self.sharehub:
                quote = self.sharehub.get_stock_quote(symbol)
                if quote and hasattr(quote, 'ltp') and quote.ltp > 0:
                    return float(quote.ltp)
        except Exception as e:
            logger.debug(f"ShareHub quote failed: {e}")
        
        return None
    
    def analyze(
        self,
        symbol: str,
        price_data: pd.DataFrame = None,
        broker_data: List = None,
    ) -> IPOExitResult:
        """
        Analyze an IPO stock for exit signals.
        
        Args:
            symbol: Stock symbol (e.g., "SOHL")
            price_data: Optional pre-fetched OHLCV DataFrame
            broker_data: Optional pre-fetched broker flow data
            
        Returns:
            IPOExitResult with complete analysis and recommendations
        """
        symbol = symbol.upper()
        logger.info(f"📊 Analyzing IPO exit signals for {symbol}")
        
        result = IPOExitResult(symbol=symbol)
        
        # 1. Fetch price data if not provided
        df = price_data
        if df is None and self.fetcher:
            df = self.fetcher.safe_fetch_data(symbol, days=60, min_rows=5)
        
        if df is None or df.empty or len(df) < 3:
            result.verdict = "INSUFFICIENT DATA"
            result.warnings.append("Need at least 3 days of trading data")
            return result
        
        # 2. Basic metrics - use real-time LTP if available
        result.days_since_listing = len(df)
        result.listing_price = float(df.iloc[0]["close"])  # Day 1 close
        
        # Try to get real-time LTP instead of yesterday's close
        realtime_ltp = self._fetch_realtime_ltp(symbol)
        if realtime_ltp and realtime_ltp > 0:
            result.current_price = realtime_ltp
            logger.info(f"📊 Using real-time LTP: Rs. {realtime_ltp}")
        else:
            result.current_price = float(df.iloc[-1]["close"])
        
        result.gain_from_listing_pct = (result.current_price / result.listing_price - 1) * 100
        
        # 3. Analyze volume patterns
        result.volume_analysis = self._analyze_volume(df)
        
        # 4. Analyze price patterns
        result.price_pattern = self._analyze_price_pattern(df)
        
        # 5. Analyze broker flow (if available)
        if broker_data or self.sharehub:
            result.broker_flow = self._analyze_broker_flow(symbol, broker_data)
        
        # 6. Generate final verdict
        self._generate_verdict(result)
        
        logger.info(f"📊 {symbol}: Exit Signal = {result.exit_signal.value}, Verdict = {result.verdict}")
        
        return result
    
    def _analyze_volume(self, df: pd.DataFrame) -> VolumeAnalysis:
        """Analyze volume patterns for exit signals."""
        analysis = VolumeAnalysis()
        
        if "volume" not in df.columns:
            analysis.signal = "⚠️ No volume data available"
            return analysis
        
        volumes = df["volume"].values
        dates = df["date"].values if "date" in df.columns else range(len(volumes))
        
        analysis.days_analyzed = len(volumes)
        analysis.avg_volume = float(np.mean(volumes))
        
        # Store daily volumes for visualization
        for i, (d, v) in enumerate(zip(dates, volumes)):
            day_label = f"Day {i+1}" if isinstance(d, int) else str(d)[:10]
            analysis.daily_volumes.append((day_label, int(v)))
        
        # Check for volume trend (last 5 days)
        if len(volumes) >= 5:
            recent_vols = volumes[-5:]
            
            # Count declining days
            decline_count = 0
            for i in range(1, len(recent_vols)):
                if recent_vols[i] < recent_vols[i-1]:
                    decline_count += 1
            
            analysis.consecutive_decline_days = decline_count
            
            # Determine trend
            vol_change = (recent_vols[-1] - recent_vols[0]) / max(recent_vols[0], 1) * 100
            
            if decline_count >= 3:
                analysis.volume_trend = "declining"
                analysis.signal = "⚠️ Volume declining for 3+ days"
                analysis.explanation = "Initial excitement fading - watch for reversal"
            elif vol_change > 50:
                analysis.volume_trend = "spike"
                analysis.volume_spike_detected = True
                analysis.spike_day = len(volumes)
                analysis.signal = "🚨 VOLUME SPIKE DETECTED"
                analysis.explanation = "Sudden volume increase - potential distribution or news"
            elif vol_change > 20:
                analysis.volume_trend = "increasing"
                analysis.signal = "📈 Volume increasing"
                analysis.explanation = "Interest building - could be accumulation or distribution"
            else:
                analysis.volume_trend = "stable"
                analysis.signal = "✅ Volume stable"
                analysis.explanation = "Normal trading activity"
        
        # Check for spike after quiet period
        if len(volumes) >= 5:
            quiet_period_vol = np.mean(volumes[-5:-1])  # Excluding today
            today_vol = volumes[-1]
            
            if today_vol > quiet_period_vol * 2:
                analysis.volume_spike_detected = True
                analysis.signal = "🚨 VOLUME SPIKE after quiet period"
                analysis.explanation = "2x normal volume - smart money may be moving"
        
        return analysis
    
    def _analyze_price_pattern(self, df: pd.DataFrame) -> PricePatternAnalysis:
        """Analyze price patterns for exit signals."""
        analysis = PricePatternAnalysis()
        
        closes = df["close"].values
        lows = df["low"].values if "low" in df.columns else closes
        highs = df["high"].values if "high" in df.columns else closes
        
        analysis.listing_price = float(closes[0])
        analysis.current_price = float(closes[-1])
        
        # Day 2 low (key support level for IPOs)
        if len(lows) >= 2:
            analysis.day_2_low = float(lows[1])
        else:
            analysis.day_2_low = float(lows[0]) * 0.95  # Estimate
        
        # Calculate gains
        analysis.listing_gain_pct = (closes[-1] / closes[0] - 1) * 100
        analysis.current_gain_pct = analysis.listing_gain_pct
        
        # Check if broke Day 2 low
        analysis.broke_day2_low = float(closes[-1]) < analysis.day_2_low
        
        # Determine price trend (last 5 days)
        if len(closes) >= 5:
            recent_closes = closes[-5:]
            price_change = (recent_closes[-1] - recent_closes[0]) / recent_closes[0] * 100
            
            if price_change > 5:
                analysis.price_trend = "uptrend"
            elif price_change < -5:
                analysis.price_trend = "downtrend"
            else:
                analysis.price_trend = "consolidating"
        else:
            # For very new IPOs, compare to listing
            if analysis.listing_gain_pct > 10:
                analysis.price_trend = "uptrend"
            elif analysis.listing_gain_pct < -5:
                analysis.price_trend = "downtrend"
            else:
                analysis.price_trend = "consolidating"
        
        # Generate signals
        if analysis.broke_day2_low:
            analysis.signal = "🔴 BROKE Day 2 Low - EXIT SIGNAL"
            analysis.explanation = "Key support broken - further downside likely"
        elif analysis.price_trend == "downtrend":
            analysis.signal = "⚠️ Downtrend developing"
            analysis.explanation = "Price weakening - consider partial exit"
        elif analysis.price_trend == "consolidating":
            analysis.signal = "🟡 Consolidating"
            analysis.explanation = "Price stable - watch for direction"
        else:
            analysis.signal = "✅ Uptrend intact"
            analysis.explanation = "Price strength continues"
        
        return analysis
    
    def _analyze_broker_flow(
        self, 
        symbol: str, 
        broker_data: List = None
    ) -> BrokerFlowAnalysis:
        """Analyze broker buying/selling flow."""
        analysis = BrokerFlowAnalysis()
        
        # Fetch broker data if not provided
        if broker_data is None and self.sharehub:
            try:
                response = self.sharehub.get_broker_analysis(symbol, duration="1W")
                # Handle both list and object response types
                if response:
                    if hasattr(response, 'brokers') and response.brokers:
                        broker_data = response.brokers
                        analysis.analysis_period = getattr(response, 'date_range', 'Recent')
                    elif isinstance(response, list):
                        broker_data = response
                        analysis.analysis_period = "1 Week"
            except Exception as e:
                logger.debug(f"Could not fetch broker data: {e}")
                return analysis
        
        if not broker_data:
            return analysis
        
        analysis.analysis_period = analysis.analysis_period or "Recent"
        
        # Calculate totals
        total_buy = sum(getattr(b, 'buy_quantity', 0) for b in broker_data)
        total_sell = sum(getattr(b, 'sell_quantity', 0) for b in broker_data)
        analysis.net_quantity = total_buy - total_sell
        analysis.net_amount = sum(getattr(b, 'net_amount', 0) for b in broker_data)
        
        # Separate institutional vs retail
        inst_buy = 0
        inst_sell = 0
        retail_buy = 0
        retail_sell = 0
        
        for b in broker_data:
            broker_code = getattr(b, 'broker_code', '')
            buy_qty = getattr(b, 'buy_quantity', 0)
            sell_qty = getattr(b, 'sell_quantity', 0)
            
            if broker_code in self.INSTITUTIONAL_BROKERS:
                inst_buy += buy_qty
                inst_sell += sell_qty
            else:
                retail_buy += buy_qty
                retail_sell += sell_qty
        
        total_buy = max(total_buy, 1)  # Avoid division by zero
        total_sell = max(total_sell, 1)
        
        analysis.institutional_buy_pct = (inst_buy / total_buy) * 100
        analysis.retail_buy_pct = (retail_buy / total_buy) * 100
        analysis.institutional_sell_pct = (inst_sell / total_sell) * 100
        analysis.retail_sell_pct = (retail_sell / total_sell) * 100
        
        # Top buyers and sellers
        sorted_buyers = sorted(broker_data, key=lambda x: getattr(x, 'buy_quantity', 0), reverse=True)
        sorted_sellers = sorted(broker_data, key=lambda x: getattr(x, 'sell_quantity', 0), reverse=True)
        
        analysis.top_buyers = [
            {"name": getattr(b, 'broker_name', 'Unknown'), "quantity": getattr(b, 'buy_quantity', 0)}
            for b in sorted_buyers[:5] if getattr(b, 'buy_quantity', 0) > 0
        ]
        
        analysis.top_sellers = [
            {"name": getattr(b, 'broker_name', 'Unknown'), "quantity": getattr(b, 'sell_quantity', 0)}
            for b in sorted_sellers[:5] if getattr(b, 'sell_quantity', 0) > 0
        ]
        
        # Determine flow type
        if analysis.institutional_sell_pct > 60 and analysis.retail_buy_pct > 50:
            analysis.flow_type = "distribution"
            analysis.signal = "🔴 DISTRIBUTION: Institutions selling to retail"
            analysis.explanation = "Smart money exiting - consider selling"
        elif analysis.institutional_buy_pct > 60:
            analysis.flow_type = "accumulation"
            analysis.signal = "🟢 ACCUMULATION: Institutions buying"
            analysis.explanation = "Smart money entering - hold for now"
        elif analysis.net_quantity < 0:
            analysis.flow_type = "net_selling"
            analysis.signal = "⚠️ Net selling pressure"
            analysis.explanation = "More selling than buying - watch closely"
        elif analysis.net_quantity > 0:
            analysis.flow_type = "net_buying"
            analysis.signal = "✅ Net buying pressure"
            analysis.explanation = "More buying than selling - bullish"
        else:
            analysis.flow_type = "neutral"
            analysis.signal = "🟡 Neutral flow"
            analysis.explanation = "Balanced buying and selling"
        
        return analysis
    
    def _generate_verdict(self, result: IPOExitResult) -> None:
        """Generate final exit verdict based on all analyses."""
        
        # Scoring system
        exit_score = 0
        reasons = []
        warnings = []
        
        # 1. Volume signals
        if result.volume_analysis.volume_spike_detected:
            exit_score += 25
            reasons.append("Volume spike detected - potential distribution")
        
        if result.volume_analysis.consecutive_decline_days >= 3:
            exit_score += 15
            reasons.append("Volume declining for 3+ days - interest fading")
        
        # 2. Broker flow signals
        if result.broker_flow.flow_type == "distribution":
            exit_score += 40
            reasons.append("Institutions selling to retail - classic distribution")
        elif result.broker_flow.flow_type == "net_selling":
            exit_score += 20
            reasons.append("Net selling pressure detected")
        elif result.broker_flow.flow_type == "accumulation":
            exit_score -= 20
            reasons.append("Institutions still accumulating")
        
        # 3. Price signals
        if result.price_pattern.broke_day2_low:
            exit_score += 35
            reasons.append("Broke Day 2 low - key support broken")
        
        if result.price_pattern.price_trend == "downtrend":
            exit_score += 20
            reasons.append("Price in downtrend")
        elif result.price_pattern.price_trend == "uptrend":
            exit_score -= 15
            reasons.append("Price still in uptrend")
        
        # 4. Time-based signals
        if result.days_since_listing >= 10:
            exit_score += 10
            warnings.append(f"Stock listed {result.days_since_listing} days - typical operator exit window")
        
        # 5. Profit-based signals  
        if result.gain_from_listing_pct > 50:
            exit_score += 10
            warnings.append(f"Sitting on +{result.gain_from_listing_pct:.0f}% gain - consider booking profits")
        elif result.gain_from_listing_pct < -10:
            exit_score += 15
            warnings.append(f"Already down {result.gain_from_listing_pct:.0f}% from listing")
        
        # Generate verdict based on score
        result.reasons = reasons
        result.warnings = warnings
        
        if exit_score >= 70:
            result.exit_signal = ExitSignal.URGENT_SELL
            result.verdict = "SELL IMMEDIATELY"
            result.action = "Exit entire position at market. Distribution confirmed."
            result.confidence = min(95, exit_score)
        elif exit_score >= 50:
            result.exit_signal = ExitSignal.SELL
            result.verdict = "SELL"
            result.action = "Exit position. Multiple exit signals triggered."
            result.confidence = min(85, exit_score)
        elif exit_score >= 30:
            result.exit_signal = ExitSignal.CONSIDER_PARTIAL
            result.verdict = "CONSIDER SELLING 50%"
            result.action = "Book partial profits. Lock in gains while keeping upside exposure."
            result.confidence = exit_score + 20
        elif exit_score >= 15:
            result.exit_signal = ExitSignal.WATCH
            result.verdict = "WATCH CLOSELY"
            result.action = "Hold but monitor daily. Set stop loss at Day 2 low."
            result.confidence = 50
        else:
            result.exit_signal = ExitSignal.HOLD
            result.verdict = "HOLD"
            result.action = "Continue holding. No exit signals detected."
            result.confidence = 70
        
        # Set stop loss at Day 2 low
        result.stop_loss = result.price_pattern.day_2_low
    
    def quick_check(self, symbol: str) -> str:
        """
        Quick one-line exit signal check.
        
        Returns:
            Simple verdict string like "🟢 HOLD" or "🔴 SELL 50%"
        """
        result = self.analyze(symbol)
        
        emoji_map = {
            ExitSignal.STRONG_HOLD: "🟢🟢",
            ExitSignal.HOLD: "🟢",
            ExitSignal.WATCH: "🟡",
            ExitSignal.CONSIDER_PARTIAL: "🟠",
            ExitSignal.SELL: "🔴",
            ExitSignal.URGENT_SELL: "🔴🔴",
        }
        
        emoji = emoji_map.get(result.exit_signal, "⚪")
        return f"{emoji} {result.verdict}"


# ============================================================
# CLI INTERFACE
# ============================================================

def main():
    """Command line interface for IPO exit analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IPO Exit Signal Analyzer")
    parser.add_argument("symbol", help="Stock symbol to analyze (e.g., SOHL)")
    parser.add_argument("--quick", action="store_true", help="Quick one-line verdict")
    
    args = parser.parse_args()
    
    analyzer = IPOExitAnalyzer()
    
    if args.quick:
        print(analyzer.quick_check(args.symbol))
    else:
        result = analyzer.analyze(args.symbol)
        print(result.format_report())


if __name__ == "__main__":
    main()
