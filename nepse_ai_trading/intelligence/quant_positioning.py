"""
Quant Positioning - Market-wide positioning indicators.

Tracks:
- % of stocks above/below key moving averages
- Extreme positioning signals (crowded trades)
- Mean reversion opportunities

Usage:
    analyzer = QuantPositioning()
    
    # Get market positioning
    positioning = analyzer.get_market_positioning()
    
    # Detect extreme positioning
    extremes = analyzer.detect_extremes()
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple
from enum import Enum
from loguru import logger
import pandas as pd
import numpy as np

try:
    from data.fetcher import NepseFetcher
except ImportError:
    NepseFetcher = None


class PositioningRegime(Enum):
    """Market positioning regime."""
    EXTREMELY_OVERBOUGHT = "EXTREMELY_OVERBOUGHT"  # >85% above SMA
    OVERBOUGHT = "OVERBOUGHT"  # 70-85%
    BULLISH = "BULLISH"  # 55-70%
    NEUTRAL = "NEUTRAL"  # 45-55%
    BEARISH = "BEARISH"  # 30-45%
    OVERSOLD = "OVERSOLD"  # 15-30%
    EXTREMELY_OVERSOLD = "EXTREMELY_OVERSOLD"  # <15%


@dataclass
class PositioningMetrics:
    """Positioning metrics for the market."""
    timestamp: datetime
    total_stocks: int = 0
    
    # Stocks above various SMAs
    above_sma_20: int = 0
    above_sma_50: int = 0
    above_sma_200: int = 0
    
    # Percentages
    pct_above_sma_20: float = 0.0
    pct_above_sma_50: float = 0.0
    pct_above_sma_200: float = 0.0
    
    # Stocks at extremes
    at_52w_high: int = 0
    at_52w_low: int = 0
    pct_at_52w_high: float = 0.0
    pct_at_52w_low: float = 0.0
    
    # Regimes
    regime_20: PositioningRegime = PositioningRegime.NEUTRAL
    regime_50: PositioningRegime = PositioningRegime.NEUTRAL
    regime_200: PositioningRegime = PositioningRegime.NEUTRAL
    
    @property
    def overall_regime(self) -> PositioningRegime:
        """Get overall positioning regime based on 50 SMA."""
        return self.regime_50


@dataclass
class SectorPositioning:
    """Positioning metrics for a sector."""
    sector: str
    total_stocks: int = 0
    above_sma_50: int = 0
    pct_above_sma_50: float = 0.0
    regime: PositioningRegime = PositioningRegime.NEUTRAL
    
    @property
    def regime_emoji(self) -> str:
        """Get emoji for regime."""
        return {
            PositioningRegime.EXTREMELY_OVERBOUGHT: "🔴",
            PositioningRegime.OVERBOUGHT: "🟠",
            PositioningRegime.BULLISH: "🟢",
            PositioningRegime.NEUTRAL: "⚪",
            PositioningRegime.BEARISH: "🔵",
            PositioningRegime.OVERSOLD: "🟡",
            PositioningRegime.EXTREMELY_OVERSOLD: "🟢",  # Opportunity
        }.get(self.regime, "⚪")


@dataclass
class PositioningReport:
    """Complete positioning report."""
    timestamp: datetime
    metrics: PositioningMetrics = None
    sector_positioning: List[SectorPositioning] = field(default_factory=list)
    
    # Signals
    extreme_overbought_sectors: List[str] = field(default_factory=list)
    extreme_oversold_sectors: List[str] = field(default_factory=list)
    
    # Trading guidance
    signal: str = "NEUTRAL"
    guidance: str = ""


class QuantPositioning:
    """
    Analyzes market-wide positioning using quantitative metrics.
    
    Key indicators:
    - % stocks above 50-day SMA (breadth indicator)
    - % stocks above 200-day SMA (trend indicator)
    - % stocks at 52-week high/low (extremes)
    
    Trading rules:
    - >80% above 50 SMA = Overbought (reduce longs)
    - <20% above 50 SMA = Oversold (accumulation zone)
    - Divergence = Index up but breadth down (warning)
    """
    
    # Regime thresholds
    EXTREMELY_OVERBOUGHT = 85
    OVERBOUGHT = 70
    BULLISH = 55
    NEUTRAL_LOW = 45
    BEARISH = 30
    OVERSOLD = 15
    
    def __init__(self):
        """Initialize analyzer."""
        self.fetcher = NepseFetcher() if NepseFetcher else None
        self._sector_cache: Dict[str, str] = {}
    
    def _get_stock_sector(self, symbol: str) -> str:
        """Get sector for a stock (cached)."""
        if symbol in self._sector_cache:
            return self._sector_cache[symbol]
        
        try:
            if self.fetcher:
                companies = self.fetcher.fetch_company_list()
                for c in companies:
                    self._sector_cache[c.symbol] = c.sector
                return self._sector_cache.get(symbol, "Unknown")
        except Exception as e:
            logger.debug(f"Could not get sector for {symbol}: {e}")
        
        return "Unknown"
    
    def _determine_regime(self, pct: float) -> PositioningRegime:
        """Determine regime from percentage."""
        if pct >= self.EXTREMELY_OVERBOUGHT:
            return PositioningRegime.EXTREMELY_OVERBOUGHT
        elif pct >= self.OVERBOUGHT:
            return PositioningRegime.OVERBOUGHT
        elif pct >= self.BULLISH:
            return PositioningRegime.BULLISH
        elif pct >= self.NEUTRAL_LOW:
            return PositioningRegime.NEUTRAL
        elif pct >= self.BEARISH:
            return PositioningRegime.BEARISH
        elif pct >= self.OVERSOLD:
            return PositioningRegime.OVERSOLD
        else:
            return PositioningRegime.EXTREMELY_OVERSOLD
    
    def _calculate_stock_positioning(self, symbol: str) -> Dict[str, bool]:
        """
        Calculate positioning metrics for a single stock.
        
        Returns:
            Dict with above_sma_20, above_sma_50, above_sma_200, at_52w_high, at_52w_low
        """
        result = {
            "above_sma_20": False,
            "above_sma_50": False,
            "above_sma_200": False,
            "at_52w_high": False,
            "at_52w_low": False,
        }
        
        if not self.fetcher:
            return result
        
        try:
            df = self.fetcher.safe_fetch_data(symbol, days=260)  # ~1 year
            
            if df.empty or len(df) < 20:
                return result
            
            close = df['close'].iloc[-1]
            
            # SMA calculations
            if len(df) >= 20:
                sma_20 = df['close'].tail(20).mean()
                result["above_sma_20"] = close > sma_20
            
            if len(df) >= 50:
                sma_50 = df['close'].tail(50).mean()
                result["above_sma_50"] = close > sma_50
            
            if len(df) >= 200:
                sma_200 = df['close'].tail(200).mean()
                result["above_sma_200"] = close > sma_200
            
            # 52-week extremes
            high_52w = df['high'].max()
            low_52w = df['low'].min()
            
            # Within 3% of extreme
            if high_52w > 0:
                result["at_52w_high"] = close >= high_52w * 0.97
            if low_52w > 0:
                result["at_52w_low"] = close <= low_52w * 1.03
            
        except Exception as e:
            logger.debug(f"Failed to calculate positioning for {symbol}: {e}")
        
        return result
    
    def get_market_positioning(self, sample_size: int = 100) -> PositioningMetrics:
        """
        Get market-wide positioning metrics.
        
        Args:
            sample_size: Number of stocks to sample
            
        Returns:
            PositioningMetrics with all metrics
        """
        metrics = PositioningMetrics(timestamp=datetime.now())
        
        if not self.fetcher:
            return metrics
        
        try:
            # Get company list
            companies = self.fetcher.fetch_company_list()
            
            # Sample stocks (prioritize liquid ones)
            symbols = [c.symbol for c in companies[:sample_size]]
            metrics.total_stocks = len(symbols)
            
            # Calculate positioning for each stock
            for symbol in symbols:
                pos = self._calculate_stock_positioning(symbol)
                
                if pos["above_sma_20"]:
                    metrics.above_sma_20 += 1
                if pos["above_sma_50"]:
                    metrics.above_sma_50 += 1
                if pos["above_sma_200"]:
                    metrics.above_sma_200 += 1
                if pos["at_52w_high"]:
                    metrics.at_52w_high += 1
                if pos["at_52w_low"]:
                    metrics.at_52w_low += 1
            
            # Calculate percentages
            if metrics.total_stocks > 0:
                metrics.pct_above_sma_20 = (metrics.above_sma_20 / metrics.total_stocks) * 100
                metrics.pct_above_sma_50 = (metrics.above_sma_50 / metrics.total_stocks) * 100
                metrics.pct_above_sma_200 = (metrics.above_sma_200 / metrics.total_stocks) * 100
                metrics.pct_at_52w_high = (metrics.at_52w_high / metrics.total_stocks) * 100
                metrics.pct_at_52w_low = (metrics.at_52w_low / metrics.total_stocks) * 100
            
            # Determine regimes
            metrics.regime_20 = self._determine_regime(metrics.pct_above_sma_20)
            metrics.regime_50 = self._determine_regime(metrics.pct_above_sma_50)
            metrics.regime_200 = self._determine_regime(metrics.pct_above_sma_200)
            
        except Exception as e:
            logger.error(f"Failed to get market positioning: {e}")
        
        return metrics
    
    def get_sector_positioning(self, sample_per_sector: int = 10) -> List[SectorPositioning]:
        """
        Get positioning by sector.
        
        Args:
            sample_per_sector: Stocks to sample per sector
            
        Returns:
            List of SectorPositioning sorted by positioning
        """
        sector_data: Dict[str, SectorPositioning] = {}
        
        if not self.fetcher:
            return []
        
        try:
            companies = self.fetcher.fetch_company_list()
            
            # Group by sector
            sector_stocks: Dict[str, List[str]] = {}
            for c in companies:
                sector = c.sector or "Unknown"
                if sector not in sector_stocks:
                    sector_stocks[sector] = []
                sector_stocks[sector].append(c.symbol)
            
            # Calculate positioning for each sector
            for sector, symbols in sector_stocks.items():
                sp = SectorPositioning(sector=sector)
                sp.total_stocks = min(len(symbols), sample_per_sector)
                
                for symbol in symbols[:sample_per_sector]:
                    pos = self._calculate_stock_positioning(symbol)
                    if pos["above_sma_50"]:
                        sp.above_sma_50 += 1
                
                if sp.total_stocks > 0:
                    sp.pct_above_sma_50 = (sp.above_sma_50 / sp.total_stocks) * 100
                
                sp.regime = self._determine_regime(sp.pct_above_sma_50)
                sector_data[sector] = sp
            
        except Exception as e:
            logger.error(f"Failed to get sector positioning: {e}")
        
        # Sort by positioning percentage
        result = list(sector_data.values())
        result.sort(key=lambda x: x.pct_above_sma_50, reverse=True)
        
        return result
    
    def get_positioning_report(self) -> PositioningReport:
        """
        Get complete positioning report.
        
        Returns:
            PositioningReport with all analysis
        """
        report = PositioningReport(timestamp=datetime.now())
        
        # Market metrics
        report.metrics = self.get_market_positioning()
        
        # Sector positioning
        report.sector_positioning = self.get_sector_positioning()
        
        # Find extremes
        for sp in report.sector_positioning:
            if sp.regime in [PositioningRegime.EXTREMELY_OVERBOUGHT, PositioningRegime.OVERBOUGHT]:
                report.extreme_overbought_sectors.append(sp.sector)
            elif sp.regime in [PositioningRegime.EXTREMELY_OVERSOLD, PositioningRegime.OVERSOLD]:
                report.extreme_oversold_sectors.append(sp.sector)
        
        # Generate trading guidance
        regime = report.metrics.overall_regime if report.metrics else PositioningRegime.NEUTRAL
        
        if regime == PositioningRegime.EXTREMELY_OVERBOUGHT:
            report.signal = "STRONG_SELL"
            report.guidance = (
                "🔴 EXTREMELY OVERBOUGHT: Market is crowded on the long side. "
                "Consider reducing exposure, tightening stops, and taking profits. "
                "Mean reversion risk is high."
            )
        elif regime == PositioningRegime.OVERBOUGHT:
            report.signal = "CAUTION"
            report.guidance = (
                "🟠 OVERBOUGHT: Market positioning is extended. "
                "Be selective with new longs. Consider hedging or reducing position sizes."
            )
        elif regime == PositioningRegime.EXTREMELY_OVERSOLD:
            report.signal = "STRONG_BUY"
            report.guidance = (
                "🟢 EXTREMELY OVERSOLD: Market is washed out. "
                "This is a high-probability accumulation zone. "
                "Look for quality stocks with strong fundamentals."
            )
        elif regime == PositioningRegime.OVERSOLD:
            report.signal = "BUY"
            report.guidance = (
                "🟡 OVERSOLD: Market positioning is depressed. "
                "Look for oversold bounces and accumulation opportunities."
            )
        else:
            report.signal = "NEUTRAL"
            report.guidance = (
                "⚪ NEUTRAL: Market positioning is balanced. "
                "Focus on individual stock selection and sector rotation."
            )
        
        return report
    
    def format_report(self, report: PositioningReport = None) -> str:
        """Format positioning report for CLI output."""
        if report is None:
            report = self.get_positioning_report()
        
        lines = []
        
        lines.append("=" * 60)
        lines.append(f"📊 QUANT POSITIONING ({report.timestamp.strftime('%d-%b %H:%M')})")
        lines.append("=" * 60)
        lines.append("")
        
        if report.metrics:
            m = report.metrics
            
            # Main metrics
            lines.append("📈 MARKET POSITIONING")
            lines.append("-" * 50)
            
            # Visual bars
            bar_20 = "█" * int(m.pct_above_sma_20 / 10) + "░" * (10 - int(m.pct_above_sma_20 / 10))
            bar_50 = "█" * int(m.pct_above_sma_50 / 10) + "░" * (10 - int(m.pct_above_sma_50 / 10))
            bar_200 = "█" * int(m.pct_above_sma_200 / 10) + "░" * (10 - int(m.pct_above_sma_200 / 10))
            
            lines.append(f"Above 20-SMA:  {m.pct_above_sma_20:>5.1f}% {bar_20} ({m.regime_20.value})")
            lines.append(f"Above 50-SMA:  {m.pct_above_sma_50:>5.1f}% {bar_50} ({m.regime_50.value})")
            lines.append(f"Above 200-SMA: {m.pct_above_sma_200:>5.1f}% {bar_200} ({m.regime_200.value})")
            lines.append("")
            
            # Extremes
            lines.append(f"At 52W High: {m.at_52w_high} stocks ({m.pct_at_52w_high:.1f}%)")
            lines.append(f"At 52W Low:  {m.at_52w_low} stocks ({m.pct_at_52w_low:.1f}%)")
            lines.append("")
            
            # Overall regime
            regime_emoji = {
                PositioningRegime.EXTREMELY_OVERBOUGHT: "🔴",
                PositioningRegime.OVERBOUGHT: "🟠",
                PositioningRegime.BULLISH: "🟢",
                PositioningRegime.NEUTRAL: "⚪",
                PositioningRegime.BEARISH: "🔵",
                PositioningRegime.OVERSOLD: "🟡",
                PositioningRegime.EXTREMELY_OVERSOLD: "🟢",
            }.get(m.overall_regime, "⚪")
            
            lines.append(f"Overall Regime: {regime_emoji} {m.overall_regime.value}")
            lines.append("")
        
        # Sector positioning
        if report.sector_positioning:
            lines.append("📊 SECTOR POSITIONING")
            lines.append("-" * 50)
            lines.append(f"{'Sector':<25} {'% Above 50-SMA':<15} {'Regime'}")
            lines.append("-" * 50)
            
            for sp in report.sector_positioning[:10]:
                bar = "█" * int(sp.pct_above_sma_50 / 10)
                lines.append(
                    f"{sp.sector[:24]:<25} {sp.pct_above_sma_50:>5.1f}% {bar:<10} "
                    f"{sp.regime_emoji} {sp.regime.value[:12]}"
                )
            lines.append("")
        
        # Extremes
        if report.extreme_overbought_sectors:
            lines.append("🔴 OVERBOUGHT SECTORS (Caution)")
            for sector in report.extreme_overbought_sectors[:3]:
                lines.append(f"  • {sector}")
            lines.append("")
        
        if report.extreme_oversold_sectors:
            lines.append("🟢 OVERSOLD SECTORS (Opportunity)")
            for sector in report.extreme_oversold_sectors[:3]:
                lines.append(f"  • {sector}")
            lines.append("")
        
        # Trading guidance
        lines.append("💡 TRADING GUIDANCE")
        lines.append("-" * 50)
        lines.append(f"Signal: {report.signal}")
        lines.append("")
        
        # Wrap guidance text
        guidance_words = report.guidance.split()
        current_line = ""
        for word in guidance_words:
            if len(current_line) + len(word) + 1 <= 55:
                current_line += (" " if current_line else "") + word
            else:
                lines.append(f"  {current_line}")
                current_line = word
        if current_line:
            lines.append(f"  {current_line}")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Convenience functions
def get_positioning_report() -> str:
    """Get formatted positioning report."""
    analyzer = QuantPositioning()
    return analyzer.format_report()


def get_market_regime() -> str:
    """Get current market positioning regime."""
    analyzer = QuantPositioning()
    metrics = analyzer.get_market_positioning()
    return metrics.overall_regime.value


def get_overbought_sectors() -> List[str]:
    """Get overbought sectors."""
    analyzer = QuantPositioning()
    report = analyzer.get_positioning_report()
    return report.extreme_overbought_sectors


def get_oversold_sectors() -> List[str]:
    """Get oversold sectors."""
    analyzer = QuantPositioning()
    report = analyzer.get_positioning_report()
    return report.extreme_oversold_sectors
