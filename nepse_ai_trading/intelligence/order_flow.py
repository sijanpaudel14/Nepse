"""
Order Flow Analyzer - Intraday buy/sell aggression analysis.

Analyzes floorsheet data to detect:
- Delta (buy volume vs sell volume)
- Absorption (high volume, flat price)
- Liquidity grabs (fake breakdowns)
- Large trader activity

Limited by NEPSE data availability - uses end-of-day patterns as proxy.

Usage:
    analyzer = OrderFlowAnalyzer()
    
    # Analyze order flow for a stock
    flow = analyzer.analyze_order_flow("NGPL")
    
    # Detect absorption patterns
    absorption = analyzer.detect_absorption("NGPL")
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from loguru import logger
import pandas as pd
import numpy as np

try:
    from data.fetcher import NepseFetcher
    from data.sharehub_api import ShareHubAPI
except ImportError:
    NepseFetcher = None
    ShareHubAPI = None


@dataclass
class OrderFlowMetrics:
    """Order flow metrics for a stock."""
    symbol: str
    date: date
    
    # Volume metrics
    total_volume: int = 0
    buy_volume: int = 0  # Estimated
    sell_volume: int = 0  # Estimated
    delta: int = 0  # buy - sell
    delta_pct: float = 0.0
    
    # Price metrics
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    vwap: float = 0.0
    
    # Patterns
    is_absorption: bool = False
    is_liquidity_grab: bool = False
    is_accumulation_day: bool = False
    is_distribution_day: bool = False
    
    # Large trades
    large_trade_count: int = 0
    large_trade_volume: int = 0
    large_trade_pct: float = 0.0
    
    @property
    def delta_signal(self) -> str:
        """Get delta signal."""
        if self.delta_pct > 20:
            return "🟢 STRONG BUYING"
        elif self.delta_pct > 5:
            return "🟢 BUYING"
        elif self.delta_pct > -5:
            return "⚪ NEUTRAL"
        elif self.delta_pct > -20:
            return "🔴 SELLING"
        else:
            return "🔴 STRONG SELLING"


@dataclass
class OrderFlowReport:
    """Complete order flow analysis."""
    symbol: str
    timestamp: datetime
    
    # Current day
    today: OrderFlowMetrics = None
    
    # Historical context
    avg_volume_20d: int = 0
    volume_vs_avg: float = 0.0  # ratio
    
    # Pattern detection
    absorption_detected: bool = False
    absorption_type: str = ""  # "BUYING" or "SELLING"
    
    liquidity_grab_detected: bool = False
    liquidity_grab_type: str = ""  # "BULL_TRAP" or "BEAR_TRAP"
    
    # Trend context
    cumulative_delta_5d: int = 0
    trend_signal: str = "NEUTRAL"
    
    # Trading signals
    overall_signal: str = "NEUTRAL"
    confidence: float = 0.0


class OrderFlowAnalyzer:
    """
    Analyzes order flow patterns from floorsheet data.
    
    Key concepts:
    - Delta: Buy volume - Sell volume (positive = buyers aggressive)
    - Absorption: High volume but price doesn't move (hidden accumulation/distribution)
    - Liquidity Grab: Price spikes through support/resistance then reverses
    
    NEPSE limitations:
    - No tick-by-tick data
    - Use daily OHLCV as proxy
    - Estimate buy/sell from price movement
    """
    
    # Thresholds
    HIGH_VOLUME_RATIO = 1.5  # Volume > 1.5x average
    ABSORPTION_PRICE_CHANGE = 1.0  # Less than 1% move with high volume
    LIQUIDITY_GRAB_REVERSION = 0.5  # Price reverses 50% of spike
    
    def __init__(self):
        """Initialize analyzer."""
        self.fetcher = NepseFetcher() if NepseFetcher else None
        self.sharehub = ShareHubAPI() if ShareHubAPI else None
    
    def _fetch_price_data(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """Fetch price data."""
        if not self.fetcher:
            return pd.DataFrame()
        
        try:
            return self.fetcher.safe_fetch_data(symbol, days=days)
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _estimate_buy_sell_volume(self, row: pd.Series) -> Tuple[int, int]:
        """
        Estimate buy vs sell volume from OHLC data.
        
        Method: Use close position within range
        - Close near high = more buying
        - Close near low = more selling
        """
        try:
            open_p = row.get('open', 0)
            high = row.get('high', 0)
            low = row.get('low', 0)
            close = row.get('close', 0)
            volume = int(row.get('volume', 0))
            
            if high == low or volume == 0:
                return volume // 2, volume // 2
            
            # Close position in range (0 = at low, 1 = at high)
            range_position = (close - low) / (high - low)
            
            # Also consider open-to-close direction
            if close > open_p:
                # Bullish candle - add bias
                range_position = min(1.0, range_position + 0.1)
            elif close < open_p:
                # Bearish candle - reduce
                range_position = max(0.0, range_position - 0.1)
            
            buy_volume = int(volume * range_position)
            sell_volume = volume - buy_volume
            
            return buy_volume, sell_volume
            
        except Exception:
            volume = int(row.get('volume', 0) or 0)
            return volume // 2, volume // 2
    
    def _calculate_vwap(self, df: pd.DataFrame) -> float:
        """Calculate VWAP for the day."""
        if df.empty:
            return 0.0
        
        try:
            # Use typical price * volume
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            total_value = (typical_price * df['volume']).sum()
            total_volume = df['volume'].sum()
            
            if total_volume > 0:
                return total_value / total_volume
            return df['close'].iloc[-1]
            
        except Exception:
            return df['close'].iloc[-1] if not df.empty else 0.0
    
    def analyze_order_flow(self, symbol: str) -> OrderFlowReport:
        """
        Analyze order flow for a stock.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            OrderFlowReport with complete analysis
        """
        symbol = symbol.upper()
        report = OrderFlowReport(symbol=symbol, timestamp=datetime.now())
        
        df = self._fetch_price_data(symbol, days=30)
        if df.empty or len(df) < 5:
            return report
        
        try:
            # Latest day metrics
            latest = df.iloc[-1]
            buy_vol, sell_vol = self._estimate_buy_sell_volume(latest)
            
            today = OrderFlowMetrics(
                symbol=symbol,
                date=latest.get('date', date.today()),
                total_volume=int(latest.get('volume', 0)),
                buy_volume=buy_vol,
                sell_volume=sell_vol,
                delta=buy_vol - sell_vol,
                open_price=float(latest.get('open', 0)),
                high_price=float(latest.get('high', 0)),
                low_price=float(latest.get('low', 0)),
                close_price=float(latest.get('close', 0)),
            )
            
            # Delta percentage
            if today.total_volume > 0:
                today.delta_pct = (today.delta / today.total_volume) * 100
            
            # VWAP
            today.vwap = self._calculate_vwap(df.tail(1))
            
            # Average volume
            report.avg_volume_20d = int(df['volume'].tail(20).mean())
            if report.avg_volume_20d > 0:
                report.volume_vs_avg = today.total_volume / report.avg_volume_20d
            
            # Detect patterns
            price_change_pct = abs(
                (today.close_price - today.open_price) / today.open_price * 100
            ) if today.open_price > 0 else 0
            
            # Absorption: High volume, low price change
            if report.volume_vs_avg > self.HIGH_VOLUME_RATIO and price_change_pct < self.ABSORPTION_PRICE_CHANGE:
                today.is_absorption = True
                report.absorption_detected = True
                report.absorption_type = "BUYING" if today.delta > 0 else "SELLING"
            
            # Accumulation/Distribution day
            if today.delta_pct > 15:
                today.is_accumulation_day = True
            elif today.delta_pct < -15:
                today.is_distribution_day = True
            
            # Liquidity grab detection
            today_range = today.high_price - today.low_price
            if today_range > 0:
                # Check if price spiked and reversed
                upper_wick = today.high_price - max(today.open_price, today.close_price)
                lower_wick = min(today.open_price, today.close_price) - today.low_price
                
                if upper_wick > today_range * 0.4 and today.close_price < today.open_price:
                    today.is_liquidity_grab = True
                    report.liquidity_grab_detected = True
                    report.liquidity_grab_type = "BULL_TRAP"
                elif lower_wick > today_range * 0.4 and today.close_price > today.open_price:
                    today.is_liquidity_grab = True
                    report.liquidity_grab_detected = True
                    report.liquidity_grab_type = "BEAR_TRAP"
            
            report.today = today
            
            # Cumulative delta (5 days)
            for i in range(-5, 0):
                if i + len(df) >= 0:
                    row = df.iloc[i]
                    bv, sv = self._estimate_buy_sell_volume(row)
                    report.cumulative_delta_5d += (bv - sv)
            
            # Trend signal based on cumulative delta
            if report.cumulative_delta_5d > report.avg_volume_20d * 0.3:
                report.trend_signal = "BULLISH"
            elif report.cumulative_delta_5d < -report.avg_volume_20d * 0.3:
                report.trend_signal = "BEARISH"
            else:
                report.trend_signal = "NEUTRAL"
            
            # Overall signal
            if today.is_accumulation_day and report.volume_vs_avg > 1.2:
                report.overall_signal = "STRONG_BUY"
                report.confidence = 75
            elif today.delta_pct > 10:
                report.overall_signal = "BUY"
                report.confidence = 60
            elif today.is_distribution_day and report.volume_vs_avg > 1.2:
                report.overall_signal = "STRONG_SELL"
                report.confidence = 75
            elif today.delta_pct < -10:
                report.overall_signal = "SELL"
                report.confidence = 60
            elif today.is_absorption:
                report.overall_signal = f"ABSORPTION_{report.absorption_type}"
                report.confidence = 70
            else:
                report.overall_signal = "NEUTRAL"
                report.confidence = 40
            
        except Exception as e:
            logger.error(f"Failed to analyze order flow for {symbol}: {e}")
        
        return report
    
    def detect_absorption(self, symbol: str) -> Dict[str, Any]:
        """
        Specifically detect absorption patterns.
        
        Absorption occurs when:
        - Volume is high (>1.5x average)
        - Price change is minimal (<1%)
        - Indicates hidden accumulation or distribution
        
        Returns:
            Dict with absorption analysis
        """
        report = self.analyze_order_flow(symbol)
        
        result = {
            "symbol": symbol,
            "absorption_detected": report.absorption_detected,
            "type": report.absorption_type,
            "volume_vs_avg": f"{report.volume_vs_avg:.1f}x",
            "interpretation": "",
        }
        
        if report.absorption_detected:
            if report.absorption_type == "BUYING":
                result["interpretation"] = (
                    "🟢 BUYING ABSORPTION: Institutions absorbing selling pressure. "
                    "High volume but price stable = hidden accumulation."
                )
            else:
                result["interpretation"] = (
                    "🔴 SELLING ABSORPTION: Large sellers distributing into buyers. "
                    "High volume but price stable = hidden distribution."
                )
        else:
            result["interpretation"] = "No absorption pattern detected today."
        
        return result
    
    def format_report(self, report: OrderFlowReport) -> str:
        """Format order flow report for CLI output."""
        lines = []
        
        lines.append("=" * 60)
        lines.append(f"📊 ORDER FLOW ANALYSIS: {report.symbol}")
        lines.append("=" * 60)
        lines.append("")
        
        if report.today:
            t = report.today
            
            # Volume analysis
            lines.append("📈 VOLUME ANALYSIS")
            lines.append("-" * 50)
            lines.append(f"Total Volume: {t.total_volume:,}")
            lines.append(f"vs 20D Avg:   {report.volume_vs_avg:.1f}x")
            lines.append("")
            
            # Delta analysis
            lines.append("⚖️ BUY/SELL DELTA")
            lines.append("-" * 50)
            lines.append(f"Buy Volume:  {t.buy_volume:,} ({t.buy_volume / t.total_volume * 100:.0f}%)" if t.total_volume > 0 else "Buy Volume: N/A")
            lines.append(f"Sell Volume: {t.sell_volume:,} ({t.sell_volume / t.total_volume * 100:.0f}%)" if t.total_volume > 0 else "Sell Volume: N/A")
            lines.append(f"Delta:       {t.delta:+,} ({t.delta_pct:+.1f}%)")
            lines.append(f"Signal:      {t.delta_signal}")
            lines.append("")
            
            # Price context
            lines.append("💰 PRICE CONTEXT")
            lines.append("-" * 50)
            lines.append(f"Open:  Rs.{t.open_price:,.2f}")
            lines.append(f"High:  Rs.{t.high_price:,.2f}")
            lines.append(f"Low:   Rs.{t.low_price:,.2f}")
            lines.append(f"Close: Rs.{t.close_price:,.2f}")
            lines.append(f"VWAP:  Rs.{t.vwap:,.2f}")
            lines.append("")
            
            # Pattern detection
            lines.append("🔍 PATTERN DETECTION")
            lines.append("-" * 50)
            
            if t.is_absorption:
                lines.append(f"  ⚠️ ABSORPTION DETECTED: {report.absorption_type}")
                lines.append(f"     → High volume ({report.volume_vs_avg:.1f}x) but price stable")
                if report.absorption_type == "BUYING":
                    lines.append("     → Institutions absorbing sells = BULLISH")
                else:
                    lines.append("     → Distribution into buyers = BEARISH")
            
            if t.is_liquidity_grab:
                lines.append(f"  ⚠️ LIQUIDITY GRAB: {report.liquidity_grab_type}")
                if report.liquidity_grab_type == "BEAR_TRAP":
                    lines.append("     → Price swept lows then recovered = BULLISH")
                else:
                    lines.append("     → Price swept highs then failed = BEARISH")
            
            if t.is_accumulation_day:
                lines.append("  🟢 ACCUMULATION DAY: Strong buying pressure")
            elif t.is_distribution_day:
                lines.append("  🔴 DISTRIBUTION DAY: Strong selling pressure")
            
            if not any([t.is_absorption, t.is_liquidity_grab, t.is_accumulation_day, t.is_distribution_day]):
                lines.append("  No significant patterns detected")
            
            lines.append("")
        
        # Cumulative context
        lines.append("📊 5-DAY CUMULATIVE DELTA")
        lines.append("-" * 50)
        lines.append(f"Cumulative Delta: {report.cumulative_delta_5d:+,}")
        lines.append(f"Trend Signal: {report.trend_signal}")
        lines.append("")
        
        # Overall signal
        lines.append("🎯 OVERALL SIGNAL")
        lines.append("-" * 50)
        signal_emoji = "🟢" if "BUY" in report.overall_signal else "🔴" if "SELL" in report.overall_signal else "⚪"
        lines.append(f"Signal: {signal_emoji} {report.overall_signal}")
        lines.append(f"Confidence: {report.confidence:.0f}%")
        lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Convenience functions
def get_order_flow(symbol: str) -> str:
    """Get formatted order flow analysis."""
    analyzer = OrderFlowAnalyzer()
    report = analyzer.analyze_order_flow(symbol)
    return analyzer.format_report(report)


def get_order_flow_report(symbol: str) -> str:
    """Get formatted order flow report (alias for CLI)."""
    return get_order_flow(symbol)


def check_absorption(symbol: str) -> Dict:
    """Check for absorption patterns."""
    analyzer = OrderFlowAnalyzer()
    return analyzer.detect_absorption(symbol)
