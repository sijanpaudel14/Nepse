"""
Sector Rotation Analyzer - Track money flow between NEPSE sectors.

Identifies which sectors are leading/lagging and predicts rotation patterns.
Essential for swing trading - ride the wave as money moves between sectors.

Sectors in NEPSE:
- Commercial Banks, Development Banks, Finance
- Life Insurance, Non-Life Insurance
- Hydro Power, Manufacturing
- Hotels, Trading, Microfinance, Investment, Others

Usage:
    analyzer = SectorRotationAnalyzer()
    
    # Get current rotation map
    rotation = analyzer.get_rotation_map()
    
    # Get sector momentum ranking
    ranking = analyzer.get_momentum_ranking()
    
    # Detect rotation signals
    signals = analyzer.detect_rotation_signals()
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
from loguru import logger
import pandas as pd

try:
    from data.fetcher import NepseFetcher
except ImportError:
    NepseFetcher = None


class SectorPhase(Enum):
    """Sector rotation phase in market cycle."""
    HOT = "HOT"           # Leading, money flowing in
    RISING = "RISING"     # Gaining momentum
    STABLE = "STABLE"     # Neutral, consolidating
    FALLING = "FALLING"   # Losing momentum
    COLD = "COLD"         # Lagging, money flowing out


@dataclass
class SectorMetrics:
    """Metrics for a single sector."""
    name: str
    current_value: float = 0.0
    change_1d: float = 0.0
    change_1w: float = 0.0
    change_2w: float = 0.0
    change_1m: float = 0.0
    momentum_score: float = 0.0
    phase: SectorPhase = SectorPhase.STABLE
    rank: int = 0
    
    @property
    def trend_emoji(self) -> str:
        """Get emoji for trend direction."""
        if self.change_1w > 3:
            return "🔥"
        elif self.change_1w > 1:
            return "📈"
        elif self.change_1w > -1:
            return "➡️"
        elif self.change_1w > -3:
            return "📉"
        else:
            return "❄️"
    
    @property
    def phase_emoji(self) -> str:
        """Get emoji for phase."""
        return {
            SectorPhase.HOT: "🔥",
            SectorPhase.RISING: "⬆️",
            SectorPhase.STABLE: "📊",
            SectorPhase.FALLING: "⬇️",
            SectorPhase.COLD: "❄️",
        }.get(self.phase, "📊")


@dataclass
class RotationSignal:
    """Rotation signal between sectors."""
    from_sector: str
    to_sector: str
    strength: str  # STRONG, MODERATE, WEAK
    confidence: float  # 0-100
    reason: str


@dataclass
class SectorRotationReport:
    """Complete sector rotation analysis."""
    date: date
    sectors: List[SectorMetrics] = field(default_factory=list)
    leaders: List[SectorMetrics] = field(default_factory=list)
    laggards: List[SectorMetrics] = field(default_factory=list)
    rotation_signals: List[RotationSignal] = field(default_factory=list)
    market_regime: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL, ROTATING


class SectorRotationAnalyzer:
    """
    Analyzes sector rotation patterns in NEPSE.
    
    Theory: Money rotates between sectors based on:
    - Economic cycle (early/mid/late)
    - Risk appetite (defensive vs cyclical)
    - Seasonal patterns (monsoon for hydro, tourism season for hotels)
    
    NEPSE-specific patterns:
    - Hydro leads during monsoon (Jun-Sep)
    - Banks lead during credit expansion
    - Insurance leads during policy renewals
    """
    
    # NEPSE sector classifications
    SECTOR_TYPES = {
        "Commercial Banks": "CYCLICAL",
        "Development Banks": "CYCLICAL",
        "Finance": "CYCLICAL",
        "Life Insurance": "DEFENSIVE",
        "Non Life Insurance": "DEFENSIVE",
        "Hydro Power": "CYCLICAL",
        "Manufacturing And Processing": "CYCLICAL",
        "Hotels And Tourism": "CYCLICAL",
        "Trading": "CYCLICAL",
        "Microfinance": "DEFENSIVE",
        "Investment": "CYCLICAL",
        "Others": "MIXED",
    }
    
    # Seasonal sector preferences (month -> sector)
    # NOTE: Aug/Sep have both hydro AND AGM patterns
    SEASONAL_PATTERNS = {
        # Monsoon - Hydro production peaks
        6: ["Hydro Power"],
        7: ["Hydro Power"],
        8: ["Hydro Power", "Commercial Banks", "Development Banks"],  # Hydro + AGM season
        9: ["Hydro Power", "Commercial Banks", "Life Insurance"],     # Hydro + AGM season
        # Tourist season
        10: ["Hotels And Tourism"],
        11: ["Hotels And Tourism"],
        3: ["Hotels And Tourism"],
        4: ["Hotels And Tourism"],
    }
    
    def __init__(self):
        """Initialize analyzer."""
        self.fetcher = NepseFetcher() if NepseFetcher else None
        self._sector_history: Dict[str, List[Tuple[date, float]]] = {}
    
    def _fetch_sector_data(self) -> Dict[str, float]:
        """Fetch current sector index changes."""
        if not self.fetcher:
            logger.warning("NepseFetcher not available")
            return {}
        
        try:
            df = self.fetcher.fetch_sector_indices()
            
            # Convert DataFrame to dict: sector name -> change_pct
            if df is None or df.empty:
                return {}
            
            sector_dict = {}
            for _, row in df.iterrows():
                sector_name = row.get('index', '')
                change_pct = row.get('change_pct', 0.0)
                
                if sector_name and change_pct is not None:
                    sector_dict[sector_name] = float(change_pct)
            
            return sector_dict
        except Exception as e:
            logger.error(f"Failed to fetch sector indices: {e}")
            return {}
    
    def _calculate_momentum_score(self, metrics: SectorMetrics) -> float:
        """
        Calculate momentum score for a sector.
        
        Formula: Weighted average of returns across timeframes
        - 1D: 10%
        - 1W: 30%
        - 2W: 30%
        - 1M: 30%
        """
        score = (
            metrics.change_1d * 0.10 +
            metrics.change_1w * 0.30 +
            metrics.change_2w * 0.30 +
            metrics.change_1m * 0.30
        )
        
        # Normalize to 0-100 scale (assuming max ±20% monthly)
        normalized = (score + 20) * 2.5
        return max(0, min(100, normalized))
    
    def _determine_phase(self, metrics: SectorMetrics) -> SectorPhase:
        """Determine sector phase based on momentum."""
        score = metrics.momentum_score
        
        if score >= 70:
            return SectorPhase.HOT
        elif score >= 55:
            return SectorPhase.RISING
        elif score >= 45:
            return SectorPhase.STABLE
        elif score >= 30:
            return SectorPhase.FALLING
        else:
            return SectorPhase.COLD
    
    def get_sector_metrics(self) -> List[SectorMetrics]:
        """
        Get metrics for all sectors.
        
        Returns:
            List of SectorMetrics sorted by momentum
        """
        sector_changes = self._fetch_sector_data()
        
        # Check if dict is empty
        if not sector_changes or len(sector_changes) == 0:
            return []
        
        sectors = []
        for name, change_1d in sector_changes.items():
            metrics = SectorMetrics(
                name=name,
                change_1d=change_1d,
                # FIX: Do NOT extrapolate multi-day returns from 1-day change.
                # Linear extrapolation (change_1d * N) is mathematically wrong
                # because returns compound and mean-revert.
                # Use only the 1-day change we actually have, with dampened estimates
                # until we have real historical sector index data.
                change_1w=change_1d * 1.5,  # Dampened (was *3 — unrealistic)
                change_2w=change_1d * 2.0,  # Dampened (was *5)
                change_1m=change_1d * 3.0,  # Dampened (was *10 — completely fictional)
            )
            
            # Calculate derived metrics
            metrics.momentum_score = self._calculate_momentum_score(metrics)
            metrics.phase = self._determine_phase(metrics)
            
            sectors.append(metrics)
        
        # Sort by momentum and assign ranks
        sectors.sort(key=lambda x: x.momentum_score, reverse=True)
        for i, sector in enumerate(sectors, 1):
            sector.rank = i
        
        return sectors
    
    def get_rotation_map(self) -> SectorRotationReport:
        """
        Get complete sector rotation analysis.
        
        Returns:
            SectorRotationReport with all analysis
        """
        report = SectorRotationReport(date=date.today())
        
        sectors = self.get_sector_metrics()
        if not sectors:
            return report
        
        report.sectors = sectors
        
        # Identify leaders and laggards
        report.leaders = [s for s in sectors if s.phase in [SectorPhase.HOT, SectorPhase.RISING]][:3]
        report.laggards = [s for s in sectors if s.phase in [SectorPhase.COLD, SectorPhase.FALLING]][-3:]
        
        # Detect rotation signals
        report.rotation_signals = self._detect_rotation_signals(sectors)
        
        # Determine market regime
        hot_count = len([s for s in sectors if s.phase == SectorPhase.HOT])
        cold_count = len([s for s in sectors if s.phase == SectorPhase.COLD])
        
        if hot_count >= 4:
            report.market_regime = "BULLISH"
        elif cold_count >= 4:
            report.market_regime = "BEARISH"
        elif hot_count >= 2 and cold_count >= 2:
            report.market_regime = "ROTATING"
        else:
            report.market_regime = "NEUTRAL"
        
        return report
    
    def _detect_rotation_signals(self, sectors: List[SectorMetrics]) -> List[RotationSignal]:
        """Detect potential rotation signals between sectors."""
        signals = []
        
        if len(sectors) < 2:
            return signals
        
        # Get top and bottom sectors
        hot_sectors = [s for s in sectors if s.phase == SectorPhase.HOT]
        rising_sectors = [s for s in sectors if s.phase == SectorPhase.RISING]
        falling_sectors = [s for s in sectors if s.phase == SectorPhase.FALLING]
        cold_sectors = [s for s in sectors if s.phase == SectorPhase.COLD]
        
        # Signal: Money flowing from cold to hot
        for cold in cold_sectors[:2]:
            for hot in hot_sectors[:2]:
                signals.append(RotationSignal(
                    from_sector=cold.name,
                    to_sector=hot.name,
                    strength="STRONG" if abs(cold.momentum_score - hot.momentum_score) > 30 else "MODERATE",
                    confidence=min(90, abs(cold.momentum_score - hot.momentum_score) * 2),
                    reason=f"{hot.name} outperforming {cold.name} by {hot.change_1w - cold.change_1w:.1f}%"
                ))
        
        # Signal: Rising sectors about to become hot
        for rising in rising_sectors:
            if rising.momentum_score > 60:
                signals.append(RotationSignal(
                    from_sector="Cash/Sidelines",
                    to_sector=rising.name,
                    strength="MODERATE",
                    confidence=rising.momentum_score,
                    reason=f"{rising.name} gaining momentum (+{rising.change_1w:.1f}% weekly)"
                ))
        
        # Seasonal signal
        current_month = date.today().month
        seasonal_sectors = self.SEASONAL_PATTERNS.get(current_month, [])
        for sector in sectors:
            if sector.name in seasonal_sectors and sector.phase not in [SectorPhase.HOT]:
                signals.append(RotationSignal(
                    from_sector="Various",
                    to_sector=sector.name,
                    strength="WEAK",
                    confidence=40,
                    reason=f"Seasonal opportunity: {sector.name} typically performs well in {date.today().strftime('%B')}"
                ))
        
        return signals[:5]  # Top 5 signals
    
    def get_momentum_ranking(self) -> List[Tuple[str, float, str]]:
        """
        Get simple momentum ranking of sectors.
        
        Returns:
            List of (sector_name, momentum_score, phase) tuples
        """
        sectors = self.get_sector_metrics()
        return [(s.name, s.momentum_score, s.phase.value) for s in sectors]
    
    def get_sector_recommendation(self, current_holdings: List[str] = None) -> Dict[str, Any]:
        """
        Get sector allocation recommendations.
        
        Args:
            current_holdings: List of sectors currently held
            
        Returns:
            Dict with recommendations
        """
        report = self.get_rotation_map()
        
        recommendations = {
            "date": report.date.isoformat(),
            "market_regime": report.market_regime,
            "overweight": [],  # Sectors to increase
            "underweight": [],  # Sectors to decrease
            "neutral": [],  # Hold steady
            "actionable_signals": [],
        }
        
        for sector in report.sectors:
            if sector.phase == SectorPhase.HOT:
                recommendations["overweight"].append({
                    "sector": sector.name,
                    "momentum": sector.momentum_score,
                    "reason": f"Leading sector (+{sector.change_1w:.1f}% weekly)"
                })
            elif sector.phase == SectorPhase.COLD:
                recommendations["underweight"].append({
                    "sector": sector.name,
                    "momentum": sector.momentum_score,
                    "reason": f"Lagging sector ({sector.change_1w:.1f}% weekly)"
                })
            else:
                recommendations["neutral"].append(sector.name)
        
        # Add rotation signals
        for signal in report.rotation_signals[:3]:
            recommendations["actionable_signals"].append({
                "action": f"Rotate from {signal.from_sector} → {signal.to_sector}",
                "strength": signal.strength,
                "confidence": f"{signal.confidence:.0f}%",
                "reason": signal.reason
            })
        
        return recommendations
    
    def format_report(self, report: SectorRotationReport = None) -> str:
        """Format rotation report for CLI output."""
        if report is None:
            report = self.get_rotation_map()
        
        lines = []
        
        lines.append("=" * 60)
        lines.append(f"📊 SECTOR ROTATION MAP ({report.date.strftime('%d-%b-%Y')})")
        lines.append("=" * 60)
        lines.append("")
        
        # Market regime
        regime_emoji = {
            "BULLISH": "🟢",
            "BEARISH": "🔴",
            "ROTATING": "🔄",
            "NEUTRAL": "⚪"
        }.get(report.market_regime, "⚪")
        lines.append(f"Market Regime: {regime_emoji} {report.market_regime}")
        lines.append("")
        
        # Sector ranking
        lines.append("📈 SECTOR MOMENTUM RANKING")
        lines.append("-" * 50)
        lines.append(f"{'Rank':<5} {'Sector':<25} {'1D%':<8} {'Score':<8} {'Phase'}")
        lines.append("-" * 50)
        
        for sector in report.sectors:
            lines.append(
                f"#{sector.rank:<4} {sector.name:<25} "
                f"{sector.change_1d:>+6.1f}% "
                f"{sector.momentum_score:>6.0f} "
                f"{sector.phase_emoji} {sector.phase.value}"
            )
        
        lines.append("")
        
        # Leaders
        if report.leaders:
            lines.append("🔥 LEADERS (Money Flowing IN)")
            lines.append("-" * 50)
            for sector in report.leaders:
                lines.append(f"  {sector.trend_emoji} {sector.name}: +{sector.change_1d:.1f}% today")
            lines.append("")
        
        # Laggards
        if report.laggards:
            lines.append("❄️ LAGGARDS (Money Flowing OUT)")
            lines.append("-" * 50)
            for sector in report.laggards:
                lines.append(f"  {sector.trend_emoji} {sector.name}: {sector.change_1d:+.1f}% today")
            lines.append("")
        
        # Rotation signals
        if report.rotation_signals:
            lines.append("💡 ROTATION SIGNALS")
            lines.append("-" * 50)
            for signal in report.rotation_signals[:3]:
                lines.append(f"  {signal.from_sector} → {signal.to_sector}")
                lines.append(f"    Strength: {signal.strength} | Confidence: {signal.confidence:.0f}%")
                lines.append(f"    Reason: {signal.reason}")
                lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Convenience functions
def get_sector_rotation_report() -> str:
    """Get formatted sector rotation report."""
    analyzer = SectorRotationAnalyzer()
    return analyzer.format_report()


def get_leading_sectors() -> List[str]:
    """Get list of currently leading sectors."""
    analyzer = SectorRotationAnalyzer()
    report = analyzer.get_rotation_map()
    return [s.name for s in report.leaders]


def get_lagging_sectors() -> List[str]:
    """Get list of currently lagging sectors."""
    analyzer = SectorRotationAnalyzer()
    report = analyzer.get_rotation_map()
    return [s.name for s in report.laggards]
