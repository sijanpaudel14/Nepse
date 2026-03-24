"""
Broker Intelligence Module - Advanced Operator Detection System for NEPSE.

This module provides three key broker analysis features:
1. Aggressive Holdings Score - Detect accelerating accumulation (pump early warning)
2. Stockwise Broker Table - Visual control detection (who owns what)  
3. Broker Favourites - Track repeat buying conviction (avoid one-day traps)

WHY THIS MATTERS FOR NEPSE:
- NEPSE has 5-10 "operator" brokers controlling ~60% of volume
- Pattern: Accumulate (1-2 weeks) → Pump (1-3 days) → Dump (1-2 days)
- These features detect ALL THREE phases for maximum profit protection

USAGE:
    python paper_trader.py --broker-intelligence
    python paper_trader.py --broker-intelligence --sector hydro
    
Author: NEPSE AI Trading Engine
Date: 2026-03-24
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import date, datetime
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

@dataclass
class AggressiveBroker:
    """Individual broker's aggressive activity metrics."""
    broker_id: str
    broker_name: str
    hold_pct: float = 0.0  # % of stock held
    net_amount: float = 0.0  # Net buy/sell amount (Rs.)
    net_quantity: int = 0  # Net buy/sell quantity
    buy_quantity: int = 0
    sell_quantity: int = 0
    
    # Calculated scores
    aggressive_score: int = 0  # 0-100
    is_favourite: bool = False  # Repeat buyer flag
    risk_level: str = "UNKNOWN"  # LOW, MEDIUM, HIGH, CRITICAL
    
    @property
    def is_accumulating(self) -> bool:
        """Check if broker is net buyer."""
        return self.net_amount > 0
    
    @property
    def is_distributing(self) -> bool:
        """Check if broker is net seller."""
        return self.net_amount < 0
    
    @property
    def formatted_net(self) -> str:
        """Format net amount in Cr/L."""
        amt = self.net_amount
        if abs(amt) >= 10_000_000:
            return f"{amt/10_000_000:+.1f}Cr"
        elif abs(amt) >= 100_000:
            return f"{amt/100_000:+.1f}L"
        else:
            return f"{amt:+,.0f}"


@dataclass  
class StockBrokerProfile:
    """Broker intelligence profile for a single stock."""
    symbol: str
    ltp: float = 0.0
    change_pct: float = 0.0
    sector: str = "Unknown"
    
    # Top brokers
    top_brokers: List[AggressiveBroker] = field(default_factory=list)
    total_involved_brokers: int = 0
    top3_concentration: float = 0.0  # % held by top 3
    
    # Aggregated scores
    aggressive_score: int = 0  # 0-100 (weighted from top brokers)
    conviction_score: int = 0  # 0-100 (based on 1D vs 1W comparison)
    manipulation_risk: str = "UNKNOWN"  # LOW, MEDIUM, HIGH
    
    # Signals
    has_favourite_broker: bool = False  # At least one ★ broker
    signal: str = "NEUTRAL"  # ACCUMULATING, DISTRIBUTING, NEUTRAL
    
    @property
    def risk_emoji(self) -> str:
        """Get emoji for risk level."""
        return {
            "LOW": "🟢",
            "MEDIUM": "🟡", 
            "HIGH": "🟠",
            "CRITICAL": "🔴",
            "UNKNOWN": "⚪"
        }.get(self.manipulation_risk, "⚪")


@dataclass
class BrokerIntelligenceReport:
    """Complete broker intelligence report."""
    date: date = field(default_factory=date.today)
    sector_filter: Optional[str] = None
    
    # Stock profiles
    stocks: List[StockBrokerProfile] = field(default_factory=list)
    
    # Summary stats
    total_stocks_analyzed: int = 0
    accumulating_count: int = 0
    distributing_count: int = 0
    high_risk_count: int = 0
    favourite_broker_count: int = 0
    
    # Top picks
    top_aggressive: List[StockBrokerProfile] = field(default_factory=list)
    top_conviction: List[StockBrokerProfile] = field(default_factory=list)


# ============================================================
# BROKER INTELLIGENCE ANALYZER
# ============================================================

class BrokerIntelligenceAnalyzer:
    """
    Advanced broker analysis for NEPSE operator detection.
    
    Combines three analysis methods:
    1. Aggressive Score - Today vs 5-day average accumulation
    2. Broker Table - Visual ownership matrix
    3. Favourites - Repeat buying conviction detection
    """
    
    # Scoring thresholds (calibrated for NEPSE)
    MIN_CONCENTRATION = 50.0  # Minimum top3 % to be interesting
    AGGRESSIVE_NET_THRESHOLD = 10_000_000  # Rs.1Cr minimum
    FAVOURITE_1W_1D_RATIO = 1.5  # 1W holding > 1.5x 1D = favourite
    
    def __init__(self):
        """Initialize analyzer with API connections."""
        self.sharehub: Optional[ShareHubAPI] = None
        self.fetcher: Optional[NepseFetcher] = None
        self._sector_map: Dict[str, str] = {}
        
        try:
            self.sharehub = ShareHubAPI()
            self.fetcher = NepseFetcher()
            self._load_sector_map()
        except Exception as e:
            logger.error(f"Failed to initialize BrokerIntelligenceAnalyzer: {e}")
    
    def _load_sector_map(self):
        """Load stock-to-sector mapping."""
        if not self.fetcher:
            return
        
        try:
            companies = self.fetcher.fetch_company_list()
            for c in companies:
                # Handle both dict and Pydantic object formats
                if hasattr(c, 'symbol'):
                    symbol = c.symbol
                    sector = getattr(c, 'sector', 'Unknown')
                else:
                    symbol = c.get("symbol", "")
                    sector = c.get("sectorName", c.get("sector", "Unknown"))
                
                if symbol:
                    self._sector_map[symbol.upper()] = sector
            
            logger.debug(f"Loaded {len(self._sector_map)} stocks into sector map")
        except Exception as e:
            logger.debug(f"Could not load sector map: {e}")
    
    def _get_sector(self, symbol: str) -> str:
        """Get sector for a stock."""
        return self._sector_map.get(symbol.upper(), "Unknown")
    
    def _calculate_aggressive_score(
        self,
        broker_1d: Optional[BrokerData],
        broker_1w: Optional[BrokerData],
        top3_pct: float
    ) -> Tuple[int, bool]:
        """
        Calculate aggressive accumulation score (0-100).
        
        SCORING:
        - Concentration bonus: +30 pts if top3 > 60%
        - Net amount bonus: +25 pts if net buy > 1Cr
        - Acceleration bonus: +20 pts if 1D activity > avg daily from 1W
        - Conviction bonus: +25 pts if consistent buying 1D AND 1W
        
        Returns:
            (score, is_favourite)
        """
        score = 0
        is_favourite = False
        
        # Get amounts
        net_1d = broker_1d.net_amount if broker_1d else 0
        net_1w = broker_1w.net_amount if broker_1w else 0
        buy_qty_1d = broker_1d.buy_quantity if broker_1d else 0
        buy_qty_1w = broker_1w.buy_quantity if broker_1w else 0
        
        # 1. Concentration bonus (+30 pts if top3 > 60%)
        if top3_pct >= 80:
            score += 30
        elif top3_pct >= 70:
            score += 25
        elif top3_pct >= 60:
            score += 20
        elif top3_pct >= 50:
            score += 15
        
        # 2. Net amount bonus (+25 pts if net buy > 1Cr)
        if net_1d > 50_000_000:  # > 5Cr
            score += 25
        elif net_1d > 20_000_000:  # > 2Cr
            score += 20
        elif net_1d > 10_000_000:  # > 1Cr
            score += 15
        elif net_1d > 5_000_000:  # > 50L
            score += 10
        elif net_1d > 0:
            score += 5
        
        # 3. Acceleration bonus (+20 pts if 1D > avg daily from 1W)
        # Assumes 5 trading days in 1W
        avg_daily_1w = buy_qty_1w / 5 if buy_qty_1w > 0 else 0
        if avg_daily_1w > 0 and buy_qty_1d > avg_daily_1w * 1.5:
            score += 20  # Today > 1.5x average = accelerating
        elif avg_daily_1w > 0 and buy_qty_1d > avg_daily_1w:
            score += 10  # Today > average
        
        # 4. Conviction bonus (+25 pts if consistent buying)
        if net_1d > 0 and net_1w > 0:
            score += 15  # Both periods positive
            
            # Favourite detection: 1W holding much larger than 1D
            # Indicates sustained multi-day buying, not one-day pump
            if net_1w > net_1d * self.FAVOURITE_1W_1D_RATIO:
                score += 10
                is_favourite = True
        
        return min(100, score), is_favourite
    
    def _calculate_risk_level(
        self,
        broker_data: BrokerData,
        ltp: float
    ) -> str:
        """
        Calculate broker's risk level based on profit position.
        
        If broker has big unrealized profit, they may dump soon!
        """
        if not broker_data or broker_data.buy_quantity <= 0:
            return "UNKNOWN"
        
        # Estimate broker's average cost
        avg_cost = broker_data.buy_amount / broker_data.buy_quantity
        
        if avg_cost <= 0 or ltp <= 0:
            return "UNKNOWN"
        
        # Calculate broker's unrealized profit %
        profit_pct = ((ltp - avg_cost) / avg_cost) * 100
        
        if profit_pct > 20:
            return "CRITICAL"  # > 20% profit, likely to dump
        elif profit_pct > 15:
            return "HIGH"
        elif profit_pct > 10:
            return "MEDIUM"
        else:
            return "LOW"
    
    def analyze_stock(self, symbol: str) -> StockBrokerProfile:
        """
        Analyze broker intelligence for a single stock.
        
        Returns:
            StockBrokerProfile with all metrics
        """
        symbol = symbol.upper()
        profile = StockBrokerProfile(
            symbol=symbol,
            sector=self._get_sector(symbol)
        )
        
        if not self.sharehub:
            return profile
        
        try:
            # Get broker data for different timeframes
            brokers_1d = self.sharehub.get_broker_analysis(symbol, "1D")
            brokers_1w = self.sharehub.get_broker_analysis(symbol, "1W")
            
            if not brokers_1d and not brokers_1w:
                return profile
            
            # Use 1D data as primary, with 1W for comparison
            primary_brokers = brokers_1d if brokers_1d else brokers_1w
            
            # Create broker lookup for 1W data
            broker_1w_map = {b.broker_code: b for b in brokers_1w} if brokers_1w else {}
            
            # Sort by net_amount (top accumulators first)
            sorted_brokers = sorted(
                primary_brokers,
                key=lambda x: x.net_amount,
                reverse=True
            )
            
            # Get LTP from broker data
            total_buy_amt = sum(b.buy_amount for b in primary_brokers)
            total_buy_qty = sum(b.buy_quantity for b in primary_brokers)
            if total_buy_qty > 0:
                profile.ltp = total_buy_amt / total_buy_qty
            
            # Calculate top 3 concentration
            total_activity = sum(b.buy_quantity + b.sell_quantity for b in primary_brokers)
            if total_activity > 0:
                top3_activity = sum(
                    b.buy_quantity + b.sell_quantity 
                    for b in sorted_brokers[:3]
                )
                profile.top3_concentration = (top3_activity / total_activity) * 100
            
            profile.total_involved_brokers = len(primary_brokers)
            
            # Analyze top 5 brokers
            total_aggressive_score = 0
            has_favourite = False
            
            for i, broker in enumerate(sorted_brokers[:5]):
                broker_1w = broker_1w_map.get(broker.broker_code)
                
                # Calculate aggressive score
                agg_score, is_fav = self._calculate_aggressive_score(
                    broker, broker_1w, profile.top3_concentration
                )
                
                # Calculate risk level
                risk = self._calculate_risk_level(broker, profile.ltp)
                
                # Create AggressiveBroker object
                ab = AggressiveBroker(
                    broker_id=broker.broker_code,
                    broker_name=broker.broker_name,
                    hold_pct=0,  # Will be calculated from concentration
                    net_amount=broker.net_amount,
                    net_quantity=broker.net_quantity,
                    buy_quantity=broker.buy_quantity,
                    sell_quantity=broker.sell_quantity,
                    aggressive_score=agg_score,
                    is_favourite=is_fav,
                    risk_level=risk
                )
                
                profile.top_brokers.append(ab)
                total_aggressive_score += agg_score
                if is_fav:
                    has_favourite = True
            
            # Calculate stock-level scores
            if profile.top_brokers:
                profile.aggressive_score = total_aggressive_score // len(profile.top_brokers)
            
            profile.has_favourite_broker = has_favourite
            
            # Determine signal
            net_activity = sum(b.net_amount for b in profile.top_brokers)
            if net_activity > self.AGGRESSIVE_NET_THRESHOLD:
                profile.signal = "ACCUMULATING"
            elif net_activity < -self.AGGRESSIVE_NET_THRESHOLD:
                profile.signal = "DISTRIBUTING"
            else:
                profile.signal = "NEUTRAL"
            
            # Determine manipulation risk
            high_risk_count = sum(
                1 for b in profile.top_brokers 
                if b.risk_level in ("HIGH", "CRITICAL")
            )
            if high_risk_count >= 2:
                profile.manipulation_risk = "HIGH"
            elif high_risk_count == 1 or profile.top3_concentration > 80:
                profile.manipulation_risk = "MEDIUM"
            else:
                profile.manipulation_risk = "LOW"
            
        except Exception as e:
            logger.error(f"Failed to analyze broker intelligence for {symbol}: {e}")
        
        return profile
    
    def get_aggressive_holdings(
        self,
        sector: Optional[str] = None,
        min_concentration: float = None,
        limit: int = 20
    ) -> List[StockBrokerProfile]:
        """
        Get stocks with aggressive broker accumulation.
        
        Args:
            sector: Filter by sector (e.g., "hydro", "banks")
            min_concentration: Minimum top3 concentration %
            limit: Maximum results
            
        Returns:
            List of StockBrokerProfile sorted by aggressive score
        """
        min_conc = min_concentration or self.MIN_CONCENTRATION
        
        if not self.sharehub:
            return []
        
        try:
            # Get aggressive holdings from API
            holdings = self.sharehub.get_broker_aggressive_holdings(duration="1D")
            
            profiles = []
            for item in holdings:
                symbol = item.get("symbol", "")
                if not symbol:
                    continue
                
                # Filter by sector if specified
                stock_sector = self._get_sector(symbol)
                if sector:
                    if sector.lower() not in stock_sector.lower():
                        continue
                
                # Filter by concentration
                top3_pct = float(item.get("topThreeBrokersHoldingPercentage", 0) or 0)
                if top3_pct < min_conc:
                    continue
                
                # Analyze the stock
                profile = self.analyze_stock(symbol)
                profile.ltp = float(item.get("ltp", 0) or 0)
                profile.change_pct = float(item.get("changePercentage", 0) or 0)
                profile.top3_concentration = top3_pct
                
                profiles.append(profile)
            
            # Sort by aggressive score
            profiles.sort(key=lambda x: x.aggressive_score, reverse=True)
            
            return profiles[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get aggressive holdings: {e}")
            return []
    
    def get_sector_stocks(self, sector: str) -> List[str]:
        """
        Get all stock symbols in a specific sector.
        
        Args:
            sector: Sector name (e.g., "hydro", "banks", "insurance")
            
        Returns:
            List of stock symbols in that sector
        """
        sector_lower = sector.lower()
        
        # Map common sector aliases to actual sector names (case-insensitive matching)
        sector_aliases = {
            # Hydro Power
            "hydro": "hydro power",
            "hydropower": "hydro power",
            "power": "hydro power",
            # Commercial Banks
            "bank": "commercial banks",
            "banks": "commercial banks",
            "commercial": "commercial banks",
            # Development Banks
            "dev bank": "development banks",
            "devbank": "development banks",
            "development": "development banks",
            # Life Insurance
            "insurance": "life insurance",
            "life": "life insurance",
            "life insurance": "life insurance",
            # Non-Life Insurance
            "non-life": "non life insurance",
            "nonlife": "non life insurance",
            "non life": "non life insurance",
            # Finance
            "finance": "finance",
            # Microfinance
            "microfinance": "microfinance",
            "micro": "microfinance",
            # Manufacturing
            "manufacturing": "manufacturing and processing",
            "mfg": "manufacturing and processing",
            # Hotels
            "hotel": "hotels and tourism",
            "hotels": "hotels and tourism",
            "tourism": "hotels and tourism",
            # Trading
            "trading": "tradings",
            "tradings": "tradings",
            # Others
            "others": "others",
            "other": "others",
            # Investment
            "investment": "investment",
            # Mutual Fund
            "mutual": "mutual fund",
            "mutual fund": "mutual fund",
            "fund": "mutual fund",
        }
        
        # Try to find matching sector
        target_sector = sector_aliases.get(sector_lower, sector_lower)
        
        matching_stocks = []
        for symbol, stock_sector in self._sector_map.items():
            if target_sector in stock_sector.lower():
                matching_stocks.append(symbol)
        
        logger.debug(f"Found {len(matching_stocks)} stocks in sector '{sector}' (mapped to '{target_sector}')")
        
        return sorted(matching_stocks)
    
    def scan_sector(
        self,
        sector: str,
        limit: int = 30
    ) -> List[StockBrokerProfile]:
        """
        Scan ALL stocks in a specific sector for broker intelligence.
        
        This is more comprehensive than get_aggressive_holdings() as it
        analyzes every stock in the sector, not just those with high concentration.
        
        Args:
            sector: Sector name (e.g., "hydro", "banks")
            limit: Maximum stocks to return
            
        Returns:
            List of StockBrokerProfile sorted by aggressive score
        """
        stocks_in_sector = self.get_sector_stocks(sector)
        
        if not stocks_in_sector:
            logger.warning(f"No stocks found in sector: {sector}")
            return []
        
        logger.info(f"Scanning {len(stocks_in_sector)} stocks in {sector} sector...")
        
        profiles = []
        for symbol in stocks_in_sector[:50]:  # Cap at 50 to avoid timeout
            try:
                profile = self.analyze_stock(symbol)
                if profile.top_brokers:  # Only include if we got broker data
                    profiles.append(profile)
            except Exception as e:
                logger.debug(f"Could not analyze {symbol}: {e}")
                continue
        
        # Sort by aggressive score
        profiles.sort(key=lambda x: x.aggressive_score, reverse=True)
        
        return profiles[:limit]
    
    def generate_report(
        self,
        sector: Optional[str] = None,
        limit: int = 15
    ) -> BrokerIntelligenceReport:
        """
        Generate comprehensive broker intelligence report.
        
        Args:
            sector: Filter by sector (e.g., "hydro", "banks"). If None, scans all sectors.
            limit: Maximum stocks to analyze
            
        Returns:
            BrokerIntelligenceReport with all analysis
        """
        report = BrokerIntelligenceReport(
            date=date.today(),
            sector_filter=sector
        )
        
        # If sector specified, do a deep sector scan
        # Otherwise, get aggressive holdings across all sectors
        if sector:
            stocks = self.scan_sector(sector=sector, limit=limit)
        else:
            stocks = self.get_aggressive_holdings(sector=None, limit=limit)
        
        for profile in stocks:
            report.stocks.append(profile)
            report.total_stocks_analyzed += 1
            
            if profile.signal == "ACCUMULATING":
                report.accumulating_count += 1
            elif profile.signal == "DISTRIBUTING":
                report.distributing_count += 1
            
            if profile.manipulation_risk in ("HIGH", "CRITICAL"):
                report.high_risk_count += 1
            
            if profile.has_favourite_broker:
                report.favourite_broker_count += 1
        
        # Get top picks
        report.top_aggressive = sorted(
            stocks,
            key=lambda x: x.aggressive_score,
            reverse=True
        )[:5]
        
        report.top_conviction = [
            s for s in stocks if s.has_favourite_broker
        ][:5]
        
        return report
    
    def format_report(self, report: BrokerIntelligenceReport) -> str:
        """Format broker intelligence report for CLI output."""
        lines = []
        
        # Header
        lines.append("=" * 70)
        if report.sector_filter:
            lines.append(f"🕵️ BROKER INTELLIGENCE: {report.sector_filter.upper()} SECTOR")
            lines.append(f"   Date: {report.date.strftime('%d-%b-%Y')}")
        else:
            lines.append(f"🕵️ BROKER INTELLIGENCE REPORT ({report.date.strftime('%d-%b-%Y')})")
            lines.append("   Scope: ALL SECTORS (High Concentration Stocks)")
        lines.append("=" * 70)
        lines.append("")
        
        # Summary
        lines.append("📊 SUMMARY")
        lines.append("-" * 70)
        if report.sector_filter:
            lines.append(f"   Sector: {report.sector_filter.upper()}")
        lines.append(f"   Total Analyzed: {report.total_stocks_analyzed}")
        lines.append(f"   🟢 Accumulating: {report.accumulating_count}")
        lines.append(f"   🔴 Distributing: {report.distributing_count}")
        lines.append(f"   ⚠️ High Risk: {report.high_risk_count}")
        lines.append(f"   ⭐ With Favourite Broker: {report.favourite_broker_count}")
        lines.append("")
        
        # Top Aggressive Holdings
        if report.top_aggressive:
            section_title = f"🚀 TOP {report.sector_filter.upper()} PICKS" if report.sector_filter else "🚀 TOP AGGRESSIVE ACCUMULATION"
            lines.append(f"{section_title} (Pump Early Warning)")
            lines.append("-" * 70)
            lines.append(f"{'#':<3} {'Symbol':<10} {'Score':<8} {'Top3%':<8} {'Signal':<12} {'Risk'}")
            lines.append("-" * 70)
            
            for i, stock in enumerate(report.top_aggressive, 1):
                star = "⭐" if stock.has_favourite_broker else "  "
                lines.append(
                    f"{i:<3} {stock.symbol:<10} {stock.aggressive_score:<8} "
                    f"{stock.top3_concentration:.1f}%{'':<4} "
                    f"{stock.signal:<12} {stock.risk_emoji} {stock.manipulation_risk}"
                    f" {star}"
                )
            lines.append("")
        
        # Favourite Broker Stocks
        if report.top_conviction:
            lines.append("⭐ FAVOURITE BROKER PICKS (Sustained Conviction)")
            lines.append("-" * 70)
            for stock in report.top_conviction:
                fav_brokers = [b for b in stock.top_brokers if b.is_favourite]
                broker_str = ", ".join([f"Br{b.broker_id}" for b in fav_brokers[:2]])
                lines.append(f"   {stock.symbol}: {broker_str} ⭐ (Score: {stock.aggressive_score})")
            lines.append("")
        
        # Stockwise Broker Table
        lines.append("📋 STOCKWISE BROKER TABLE (Who Controls What)")
        lines.append("-" * 70)
        lines.append(f"{'Stock':<8} {'Broker':<25} {'Net Amt':<12} {'Risk':<8} {'Flag'}")
        lines.append("-" * 70)
        
        for stock in report.stocks[:10]:
            first_row = True
            for broker in stock.top_brokers[:3]:
                symbol_col = stock.symbol if first_row else ""
                star = "⭐" if broker.is_favourite else ""
                acc = "🟢" if broker.is_accumulating else "🔴"
                
                lines.append(
                    f"{symbol_col:<8} "
                    f"Br{broker.broker_id} ({broker.broker_name[:15]}...) "
                    f"{broker.formatted_net:<12} "
                    f"{broker.risk_level:<8} "
                    f"{acc}{star}"
                )
                first_row = False
            lines.append("")
        
        # Trading Guidance
        lines.append("=" * 70)
        lines.append("💡 INTERPRETATION GUIDE")
        lines.append("=" * 70)
        lines.append("   Score 80-100: Strong accumulation → Consider entry (3% position)")
        lines.append("   Score 60-79:  Moderate accumulation → Watchlist (1% if any)")
        lines.append("   Score 40-59:  Weak signal → Monitor only")
        lines.append("   Score < 40:   No clear pattern → Avoid")
        lines.append("")
        lines.append("   ⭐ = Favourite Broker (repeat buyer, high conviction)")
        lines.append("   🟢 = Accumulating | 🔴 = Distributing")
        lines.append("   Risk: LOW = Safe | HIGH/CRITICAL = May dump soon")
        lines.append("=" * 70)
        
        return "\n".join(lines)


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def get_broker_intelligence_report(sector: Optional[str] = None) -> str:
    """
    Get formatted broker intelligence report.
    
    Args:
        sector: Optional sector filter (e.g., "hydro", "banks")
        
    Returns:
        Formatted report string
    """
    analyzer = BrokerIntelligenceAnalyzer()
    report = analyzer.generate_report(sector=sector)
    return analyzer.format_report(report)


def analyze_stock_brokers(symbol: str) -> str:
    """
    Analyze broker activity for a single stock.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Formatted analysis string
    """
    analyzer = BrokerIntelligenceAnalyzer()
    profile = analyzer.analyze_stock(symbol)
    
    lines = []
    lines.append(f"\n🕵️ BROKER INTELLIGENCE: {profile.symbol}")
    lines.append("=" * 50)
    lines.append(f"   LTP: Rs.{profile.ltp:.2f}")
    lines.append(f"   Sector: {profile.sector}")
    lines.append(f"   Top 3 Concentration: {profile.top3_concentration:.1f}%")
    lines.append(f"   Aggressive Score: {profile.aggressive_score}/100")
    lines.append(f"   Signal: {profile.signal}")
    lines.append(f"   Risk: {profile.risk_emoji} {profile.manipulation_risk}")
    lines.append("")
    
    lines.append("📋 TOP BROKERS:")
    for i, broker in enumerate(profile.top_brokers, 1):
        star = "⭐" if broker.is_favourite else ""
        lines.append(
            f"   #{i} Br{broker.broker_id}: {broker.formatted_net} | "
            f"Risk: {broker.risk_level} {star}"
        )
    
    return "\n".join(lines)


# ============================================================
# CLI ENTRY POINT (for testing)
# ============================================================

if __name__ == "__main__":
    import sys
    
    sector = None
    if len(sys.argv) > 1:
        sector = sys.argv[1]
    
    print(get_broker_intelligence_report(sector=sector))
