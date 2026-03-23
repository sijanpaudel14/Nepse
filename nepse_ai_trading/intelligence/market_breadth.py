"""
Market Breadth Analyzer - NEPSE Market Heatmap and Breadth Indicators.

Tracks market-wide health through:
- Advance/Decline ratio
- Sector breadth breakdown
- Overbought/Oversold regime detection
- Breadth divergence signals

Usage:
    analyzer = MarketBreadthAnalyzer()
    
    # Get market breadth snapshot
    breadth = analyzer.get_market_breadth()
    
    # Get sector heatmap
    heatmap = analyzer.get_sector_heatmap()
    
    # Detect regime
    regime = analyzer.detect_regime()
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple
from enum import Enum
from loguru import logger
import pandas as pd

try:
    from data.fetcher import NepseFetcher
except ImportError:
    NepseFetcher = None


class MarketRegime(Enum):
    """Market breadth regime."""
    OVERBOUGHT = "OVERBOUGHT"     # >80% green
    BULLISH = "BULLISH"           # 60-80% green
    NEUTRAL = "NEUTRAL"           # 40-60% green
    BEARISH = "BEARISH"           # 20-40% green
    OVERSOLD = "OVERSOLD"         # <20% green


@dataclass
class SectorBreadth:
    """Breadth metrics for a sector."""
    sector: str
    total_stocks: int = 0
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    breadth_pct: float = 0.0  # % advancing
    avg_change: float = 0.0
    top_gainer: str = ""
    top_gainer_pct: float = 0.0
    top_loser: str = ""
    top_loser_pct: float = 0.0
    
    @property
    def heat_level(self) -> str:
        """Get heat level emoji."""
        if self.breadth_pct >= 80:
            return "🔥"  # Very hot
        elif self.breadth_pct >= 60:
            return "🟢"  # Hot
        elif self.breadth_pct >= 40:
            return "🟡"  # Neutral
        elif self.breadth_pct >= 20:
            return "🟠"  # Cold
        else:
            return "❄️"  # Very cold
    
    @property
    def heat_bar(self) -> str:
        """Visual heat bar."""
        filled = int(self.breadth_pct / 10)
        return "█" * filled + "░" * (10 - filled)


@dataclass
class MarketBreadthSnapshot:
    """Complete market breadth snapshot."""
    timestamp: datetime
    total_stocks: int = 0
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    
    # Derived metrics
    advance_decline_ratio: float = 0.0
    breadth_pct: float = 0.0  # % advancing
    regime: MarketRegime = MarketRegime.NEUTRAL
    
    # Index data
    nepse_index: float = 0.0
    nepse_change: float = 0.0
    nepse_change_pct: float = 0.0
    
    # Sector breakdown
    sector_breadths: List[SectorBreadth] = field(default_factory=list)
    
    # Top movers
    top_gainers: List[Tuple[str, float]] = field(default_factory=list)
    top_losers: List[Tuple[str, float]] = field(default_factory=list)
    
    @property
    def breadth_signal(self) -> str:
        """Get breadth signal."""
        if self.regime == MarketRegime.OVERBOUGHT:
            return "⚠️ OVERBOUGHT - Caution on new longs"
        elif self.regime == MarketRegime.BULLISH:
            return "🟢 BULLISH - Healthy breadth"
        elif self.regime == MarketRegime.NEUTRAL:
            return "⚪ NEUTRAL - Mixed signals"
        elif self.regime == MarketRegime.BEARISH:
            return "🔴 BEARISH - Weak breadth"
        else:
            return "🟢 OVERSOLD - Look for reversals"


class MarketBreadthAnalyzer:
    """
    Analyzes market breadth and generates heatmaps.
    
    Breadth indicators:
    - Advance/Decline Ratio: Advancing stocks / Declining stocks
    - Breadth Thrust: Sudden surge in advancing stocks
    - McClellan Oscillator: Momentum of A/D line
    
    Trading rules:
    - >80% green = Overbought (reduce exposure)
    - <20% green = Oversold (accumulation zone)
    - Divergence = Index up but breadth down (warning)
    """
    
    def __init__(self):
        """Initialize analyzer."""
        self.fetcher = NepseFetcher() if NepseFetcher else None
    
    def _fetch_live_data(self) -> pd.DataFrame:
        """Fetch live market data."""
        if not self.fetcher:
            return pd.DataFrame()
        
        try:
            return self.fetcher.fetch_live_market()
        except Exception as e:
            logger.error(f"Failed to fetch live market: {e}")
            return pd.DataFrame()
    
    def _determine_regime(self, breadth_pct: float) -> MarketRegime:
        """Determine market regime from breadth."""
        if breadth_pct >= 80:
            return MarketRegime.OVERBOUGHT
        elif breadth_pct >= 60:
            return MarketRegime.BULLISH
        elif breadth_pct >= 40:
            return MarketRegime.NEUTRAL
        elif breadth_pct >= 20:
            return MarketRegime.BEARISH
        else:
            return MarketRegime.OVERSOLD
    
    def get_market_breadth(self) -> MarketBreadthSnapshot:
        """
        Get current market breadth snapshot.
        
        Returns:
            MarketBreadthSnapshot with all metrics
        """
        snapshot = MarketBreadthSnapshot(timestamp=datetime.now())
        
        df = self._fetch_live_data()
        if df.empty:
            return snapshot
        
        try:
            # Ensure we have required columns
            if 'close' not in df.columns:
                return snapshot
            
            # Calculate change if not present
            if 'change_pct' not in df.columns and 'open' in df.columns:
                df['change_pct'] = ((df['close'] - df['open']) / df['open'] * 100).fillna(0)
            elif 'change_pct' not in df.columns:
                df['change_pct'] = 0
            
            # Count advancing/declining
            snapshot.total_stocks = len(df)
            snapshot.advancing = len(df[df['change_pct'] > 0])
            snapshot.declining = len(df[df['change_pct'] < 0])
            snapshot.unchanged = len(df[df['change_pct'] == 0])
            
            # Calculate ratios
            if snapshot.declining > 0:
                snapshot.advance_decline_ratio = snapshot.advancing / snapshot.declining
            else:
                snapshot.advance_decline_ratio = snapshot.advancing if snapshot.advancing > 0 else 1.0
            
            if snapshot.total_stocks > 0:
                snapshot.breadth_pct = (snapshot.advancing / snapshot.total_stocks) * 100
            
            # Determine regime
            snapshot.regime = self._determine_regime(snapshot.breadth_pct)
            
            # Top gainers/losers
            df_sorted = df.sort_values('change_pct', ascending=False)
            snapshot.top_gainers = [
                (row.get('symbol', ''), row.get('change_pct', 0))
                for _, row in df_sorted.head(5).iterrows()
            ]
            snapshot.top_losers = [
                (row.get('symbol', ''), row.get('change_pct', 0))
                for _, row in df_sorted.tail(5).iterrows()
            ]
            
            # Sector breadths
            if 'sector' in df.columns:
                snapshot.sector_breadths = self._calculate_sector_breadths(df)
            
        except Exception as e:
            logger.error(f"Failed to calculate market breadth: {e}")
        
        return snapshot
    
    def _calculate_sector_breadths(self, df: pd.DataFrame) -> List[SectorBreadth]:
        """Calculate breadth for each sector."""
        sector_breadths = []
        
        try:
            for sector in df['sector'].unique():
                if not sector or pd.isna(sector):
                    continue
                
                sector_df = df[df['sector'] == sector]
                
                breadth = SectorBreadth(
                    sector=sector,
                    total_stocks=len(sector_df),
                    advancing=len(sector_df[sector_df['change_pct'] > 0]),
                    declining=len(sector_df[sector_df['change_pct'] < 0]),
                    unchanged=len(sector_df[sector_df['change_pct'] == 0]),
                )
                
                if breadth.total_stocks > 0:
                    breadth.breadth_pct = (breadth.advancing / breadth.total_stocks) * 100
                    breadth.avg_change = sector_df['change_pct'].mean()
                
                # Top gainer/loser in sector
                if len(sector_df) > 0:
                    top = sector_df.loc[sector_df['change_pct'].idxmax()]
                    bottom = sector_df.loc[sector_df['change_pct'].idxmin()]
                    
                    breadth.top_gainer = top.get('symbol', '')
                    breadth.top_gainer_pct = top.get('change_pct', 0)
                    breadth.top_loser = bottom.get('symbol', '')
                    breadth.top_loser_pct = bottom.get('change_pct', 0)
                
                sector_breadths.append(breadth)
            
            # Sort by breadth percentage
            sector_breadths.sort(key=lambda x: x.breadth_pct, reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to calculate sector breadths: {e}")
        
        return sector_breadths
    
    def get_sector_heatmap(self) -> Dict[str, Dict]:
        """
        Get sector heatmap data.
        
        Returns:
            Dict mapping sector -> heat metrics
        """
        snapshot = self.get_market_breadth()
        
        heatmap = {}
        for sector in snapshot.sector_breadths:
            heatmap[sector.sector] = {
                "breadth_pct": sector.breadth_pct,
                "heat_level": sector.heat_level,
                "advancing": sector.advancing,
                "declining": sector.declining,
                "avg_change": sector.avg_change,
                "top_gainer": f"{sector.top_gainer} (+{sector.top_gainer_pct:.1f}%)",
                "top_loser": f"{sector.top_loser} ({sector.top_loser_pct:.1f}%)",
            }
        
        return heatmap
    
    def detect_breadth_divergence(self, index_change: float = None) -> Optional[str]:
        """
        Detect breadth divergence from index.
        
        Divergence occurs when:
        - Index up but breadth weak (<50%)
        - Index down but breadth strong (>50%)
        
        Args:
            index_change: NEPSE index % change
            
        Returns:
            Divergence signal or None
        """
        snapshot = self.get_market_breadth()
        
        if index_change is None:
            # Would need to fetch index change
            return None
        
        breadth = snapshot.breadth_pct
        
        if index_change > 0.5 and breadth < 45:
            return "⚠️ BEARISH DIVERGENCE: Index up but breadth weak - Correction risk"
        elif index_change < -0.5 and breadth > 55:
            return "🟢 BULLISH DIVERGENCE: Index down but breadth strong - Buying opportunity"
        
        return None
    
    def format_report(self, snapshot: MarketBreadthSnapshot = None) -> str:
        """Format breadth report for CLI output."""
        if snapshot is None:
            snapshot = self.get_market_breadth()
        
        lines = []
        
        lines.append("=" * 60)
        lines.append(f"🌡️ NEPSE MARKET HEATMAP ({snapshot.timestamp.strftime('%d-%b %H:%M')})")
        lines.append("=" * 60)
        lines.append("")
        
        # Overall breadth
        lines.append("📊 MARKET BREADTH")
        lines.append("-" * 50)
        
        # Visual bar
        adv_pct = snapshot.breadth_pct
        dec_pct = (snapshot.declining / snapshot.total_stocks * 100) if snapshot.total_stocks > 0 else 0
        adv_bars = int(adv_pct / 10)
        dec_bars = int(dec_pct / 10)
        
        lines.append(f"Advancing: {snapshot.advancing} ({adv_pct:.0f}%) {'🟢' * min(adv_bars, 10)}")
        lines.append(f"Declining: {snapshot.declining} ({dec_pct:.0f}%) {'🔴' * min(dec_bars, 10)}")
        lines.append(f"Unchanged: {snapshot.unchanged}")
        lines.append("")
        lines.append(f"A/D Ratio: {snapshot.advance_decline_ratio:.2f}")
        lines.append(f"Regime: {snapshot.regime.value}")
        lines.append(f"Signal: {snapshot.breadth_signal}")
        lines.append("")
        
        # Sector heatmap
        if snapshot.sector_breadths:
            lines.append("📈 SECTOR HEATMAP")
            lines.append("-" * 50)
            lines.append(f"{'Sector':<25} {'Breadth':<10} {'Heat'}")
            lines.append("-" * 50)
            
            for sector in snapshot.sector_breadths[:10]:
                lines.append(
                    f"{sector.sector:<25} "
                    f"{sector.breadth_pct:>5.0f}% "
                    f"{sector.heat_bar} {sector.heat_level}"
                )
            lines.append("")
        
        # Extremes
        if snapshot.sector_breadths:
            hottest = [s for s in snapshot.sector_breadths if s.breadth_pct >= 70]
            coldest = [s for s in snapshot.sector_breadths if s.breadth_pct <= 30]
            
            if hottest:
                lines.append("🔥 HOTTEST SECTORS (>70% green)")
                for s in hottest[:3]:
                    lines.append(f"  {s.sector}: {s.breadth_pct:.0f}% | Top: {s.top_gainer} +{s.top_gainer_pct:.1f}%")
                lines.append("")
            
            if coldest:
                lines.append("❄️ COLDEST SECTORS (<30% green)")
                for s in coldest[:3]:
                    lines.append(f"  {s.sector}: {s.breadth_pct:.0f}% | Bottom: {s.top_loser} {s.top_loser_pct:.1f}%")
                lines.append("")
        
        # Top movers
        if snapshot.top_gainers:
            lines.append("🚀 TOP GAINERS")
            for symbol, pct in snapshot.top_gainers[:3]:
                lines.append(f"  {symbol}: +{pct:.1f}%")
            lines.append("")
        
        if snapshot.top_losers:
            lines.append("📉 TOP LOSERS")
            for symbol, pct in snapshot.top_losers[:3]:
                lines.append(f"  {symbol}: {pct:.1f}%")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Convenience functions
def get_market_heatmap() -> str:
    """Get formatted market heatmap."""
    analyzer = MarketBreadthAnalyzer()
    return analyzer.format_report()


def get_market_regime() -> str:
    """Get current market regime."""
    analyzer = MarketBreadthAnalyzer()
    snapshot = analyzer.get_market_breadth()
    return snapshot.regime.value


def get_hottest_sectors() -> List[str]:
    """Get hottest sectors (>70% green)."""
    analyzer = MarketBreadthAnalyzer()
    snapshot = analyzer.get_market_breadth()
    return [s.sector for s in snapshot.sector_breadths if s.breadth_pct >= 70]


def get_coldest_sectors() -> List[str]:
    """Get coldest sectors (<30% green)."""
    analyzer = MarketBreadthAnalyzer()
    snapshot = analyzer.get_market_breadth()
    return [s.sector for s in snapshot.sector_breadths if s.breadth_pct <= 30]
