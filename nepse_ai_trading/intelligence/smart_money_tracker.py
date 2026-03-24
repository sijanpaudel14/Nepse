"""
Smart Money Tracker - Detect institutional buying patterns.

Tracks "smart money" by analyzing:
- Broker concentration patterns (institutions use specific brokers)
- Large accumulation over time (1W/1M holding increases)
- Player favorites (buyer/seller dominance)

Usage:
    tracker = SmartMoneyTracker()
    
    # Get market-wide smart money flow
    flow = tracker.get_market_flow()
    
    # Analyze specific stock
    analysis = tracker.analyze_stock("NGPL")
    
    # Get institutional accumulation list
    stocks = tracker.get_accumulation_stocks()
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Any
from loguru import logger

try:
    from data.sharehub_api import ShareHubAPI, BrokerData
    from data.fetcher import NepseFetcher
except ImportError:
    ShareHubAPI = None
    BrokerData = None
    NepseFetcher = None


@dataclass
class SmartMoneyStock:
    """Stock with smart money activity."""
    symbol: str
    sector: str = ""
    ltp: float = 0.0
    
    # Flow metrics
    net_flow_1d: float = 0.0  # Rs.
    net_flow_1w: float = 0.0
    net_flow_1m: float = 0.0
    net_qty_1m: int = 0
    
    # Concentration
    top3_broker_pct: float = 0.0  # % held by top 3 brokers
    institutional_score: float = 0.0  # 0-100
    
    # Signals
    is_accumulating: bool = False
    is_distributing: bool = False
    smart_money_signal: str = "NEUTRAL"  # STRONG_BUY, BUY, NEUTRAL, SELL, STRONG_SELL
    
    @property
    def flow_emoji(self) -> str:
        """Get emoji for flow direction."""
        if self.net_flow_1w > 5_000_000:
            return "🟢"
        elif self.net_flow_1w > 0:
            return "🔵"
        elif self.net_flow_1w > -5_000_000:
            return "⚪"
        else:
            return "🔴"
    
    @property
    def formatted_flow_1w(self) -> str:
        """Format weekly flow."""
        sign = "+" if self.net_flow_1w >= 0 else ""
        if abs(self.net_flow_1w) >= 10_000_000:
            return f"{sign}Rs.{self.net_flow_1w / 10_000_000:.1f}Cr"
        elif abs(self.net_flow_1w) >= 100_000:
            return f"{sign}Rs.{self.net_flow_1w / 100_000:.1f}L"
        else:
            return f"{sign}Rs.{self.net_flow_1w:,.0f}"
    
    @property
    def formatted_flow_1m(self) -> str:
        """Format monthly flow."""
        sign = "+" if self.net_flow_1m >= 0 else ""
        if abs(self.net_flow_1m) >= 10_000_000:
            return f"{sign}Rs.{self.net_flow_1m / 10_000_000:.1f}Cr"
        elif abs(self.net_flow_1m) >= 100_000:
            return f"{sign}Rs.{self.net_flow_1m / 100_000:.1f}L"
        else:
            return f"{sign}Rs.{self.net_flow_1m:,.0f}"


@dataclass
class SectorFlow:
    """Smart money flow for a sector."""
    sector: str
    net_flow_1w: float = 0.0
    net_flow_1m: float = 0.0
    stock_count: int = 0
    accumulating_count: int = 0
    distributing_count: int = 0
    top_stocks: List[SmartMoneyStock] = field(default_factory=list)
    
    @property
    def flow_direction(self) -> str:
        """Get flow direction."""
        if self.net_flow_1w > 10_000_000:
            return "STRONG_INFLOW"
        elif self.net_flow_1w > 0:
            return "INFLOW"
        elif self.net_flow_1w > -10_000_000:
            return "OUTFLOW"
        else:
            return "STRONG_OUTFLOW"


@dataclass
class SmartMoneyReport:
    """Complete smart money analysis report."""
    date: date
    total_inflow: float = 0.0
    total_outflow: float = 0.0
    net_flow: float = 0.0
    
    top_accumulation: List[SmartMoneyStock] = field(default_factory=list)
    top_distribution: List[SmartMoneyStock] = field(default_factory=list)
    sector_flows: List[SectorFlow] = field(default_factory=list)
    
    institutional_favorites: List[SmartMoneyStock] = field(default_factory=list)


class SmartMoneyTracker:
    """
    Tracks institutional/smart money flow in NEPSE.
    
    Detection methods:
    1. Broker concentration - Institutions use specific brokers
    2. Accumulation patterns - Consistent buying over weeks
    3. Volume analysis - Large quiet accumulation
    4. Player favorites - Who's dominating (buyers vs sellers)
    
    NEPSE-specific:
    - Top 10 brokers handle most institutional flow
    - >60% concentration = likely institutional
    - Consistent net buying over 1M = accumulation
    """
    
    # Institutional broker indicators
    INSTITUTIONAL_BROKER_THRESHOLD = 60.0  # Top 3 holding >60%
    SIGNIFICANT_FLOW = 5_000_000  # Rs. 50 Lakh
    
    def __init__(self):
        """Initialize tracker."""
        self.sharehub = ShareHubAPI() if ShareHubAPI else None
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
    
    def _calculate_institutional_score(
        self,
        top3_pct: float,
        net_flow_1w: float,
        net_flow_1m: float
    ) -> float:
        """
        Calculate institutional activity score (0-100).
        
        Factors:
        - Broker concentration (40%)
        - Weekly flow magnitude (30%)
        - Monthly flow consistency (30%)
        """
        # Concentration score (higher = more institutional)
        conc_score = min(100, top3_pct * 1.5)
        
        # Weekly flow score
        flow_1w_score = min(100, abs(net_flow_1w) / 500_000)  # 5Cr = 100
        
        # Monthly flow score
        flow_1m_score = min(100, abs(net_flow_1m) / 2_000_000)  # 20Cr = 100
        
        # Weighted average
        score = (
            conc_score * 0.40 +
            flow_1w_score * 0.30 +
            flow_1m_score * 0.30
        )
        
        return min(100, score)
    
    def analyze_stock(self, symbol: str) -> SmartMoneyStock:
        """
        Analyze smart money activity for a stock.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            SmartMoneyStock with analysis
        """
        symbol = symbol.upper()
        
        result = SmartMoneyStock(
            symbol=symbol,
            sector=self._get_stock_sector(symbol),
        )
        
        if not self.sharehub:
            return result
        
        try:
            # Get broker analysis for different periods
            brokers_1d = self.sharehub.get_broker_analysis(symbol, "1D")
            brokers_1w = self.sharehub.get_broker_analysis(symbol, "1W")
            brokers_1m = self.sharehub.get_broker_analysis(symbol, "1M")
            
            # Calculate net flows
            # NOTE: Summing ALL brokers gives 0 (closed system).
            # Instead, track TOP buyers (accumulation) vs TOP sellers (distribution)
            if brokers_1d:
                # Sum only top 10 buyers/sellers to get meaningful flow
                sorted_1d = sorted(brokers_1d, key=lambda x: x.net_amount, reverse=True)
                top_buyers = sum(b.net_amount for b in sorted_1d[:10] if b.net_amount > 0)
                top_sellers = sum(b.net_amount for b in sorted_1d[-10:] if b.net_amount < 0)
                result.net_flow_1d = top_buyers + top_sellers  # top_sellers is negative
            
            if brokers_1w:
                sorted_1w = sorted(brokers_1w, key=lambda x: x.net_amount, reverse=True)
                top_buyers = sum(b.net_amount for b in sorted_1w[:10] if b.net_amount > 0)
                top_sellers = sum(b.net_amount for b in sorted_1w[-10:] if b.net_amount < 0)
                result.net_flow_1w = top_buyers + top_sellers
            
            if brokers_1m:
                sorted_1m = sorted(brokers_1m, key=lambda x: x.net_amount, reverse=True)
                top_buyers = sum(b.net_amount for b in sorted_1m[:10] if b.net_amount > 0)
                top_sellers = sum(b.net_amount for b in sorted_1m[-10:] if b.net_amount < 0)
                result.net_flow_1m = top_buyers + top_sellers
                result.net_qty_1m = sum(b.net_quantity for b in sorted_1m[:10] if b.net_quantity > 0)
                
                # Calculate top 3 broker concentration
                total_qty = sum(b.buy_quantity + b.sell_quantity for b in brokers_1m)
                if total_qty > 0:
                    sorted_brokers = sorted(brokers_1m, key=lambda x: x.buy_quantity + x.sell_quantity, reverse=True)
                    top3_qty = sum(b.buy_quantity + b.sell_quantity for b in sorted_brokers[:3])
                    result.top3_broker_pct = (top3_qty / total_qty) * 100
            
            # Calculate institutional score
            result.institutional_score = self._calculate_institutional_score(
                result.top3_broker_pct,
                result.net_flow_1w,
                result.net_flow_1m
            )
            
            # Determine signals
            if result.net_flow_1m > self.SIGNIFICANT_FLOW and result.net_flow_1w > 0:
                result.is_accumulating = True
                result.smart_money_signal = "STRONG_BUY" if result.net_flow_1m > 20_000_000 else "BUY"
            elif result.net_flow_1m < -self.SIGNIFICANT_FLOW and result.net_flow_1w < 0:
                result.is_distributing = True
                result.smart_money_signal = "STRONG_SELL" if result.net_flow_1m < -20_000_000 else "SELL"
            else:
                result.smart_money_signal = "NEUTRAL"
            
        except Exception as e:
            logger.error(f"Failed to analyze smart money for {symbol}: {e}")
        
        return result
    
    def get_accumulation_stocks(self, min_flow: float = None, limit: int = 20) -> List[SmartMoneyStock]:
        """
        Get stocks with smart money accumulation.
        
        Args:
            min_flow: Minimum monthly flow threshold
            limit: Maximum results
            
        Returns:
            List of SmartMoneyStock sorted by flow
        """
        min_flow = min_flow or self.SIGNIFICANT_FLOW
        
        if not self.sharehub:
            return []
        
        try:
            # Get aggressive holdings (stocks with concentrated buying)
            holdings = self.sharehub.get_broker_aggressive_holdings(duration="1M")
            
            accumulation = []
            for item in holdings[:50]:  # Check top 50
                symbol = item.get("symbol", "")
                if not symbol:
                    continue
                
                analysis = self.analyze_stock(symbol)
                if analysis.is_accumulating and analysis.net_flow_1m >= min_flow:
                    analysis.ltp = float(item.get("ltp", 0) or 0)
                    analysis.top3_broker_pct = float(item.get("topThreeBrokersHoldingPercentage", 0) or 0)
                    accumulation.append(analysis)
            
            # Sort by flow
            accumulation.sort(key=lambda x: x.net_flow_1m, reverse=True)
            
            return accumulation[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get accumulation stocks: {e}")
            return []
    
    def get_distribution_stocks(self, min_flow: float = None, limit: int = 20) -> List[SmartMoneyStock]:
        """
        Get stocks with smart money distribution (selling).
        
        Args:
            min_flow: Minimum monthly outflow threshold
            limit: Maximum results
            
        Returns:
            List of SmartMoneyStock sorted by outflow
        """
        min_flow = min_flow or self.SIGNIFICANT_FLOW
        
        if not self.sharehub:
            return []
        
        try:
            # Get seller-dominated stocks
            sellers = self.sharehub.get_seller_dominated_stocks(min_weight=55.0)
            
            distribution = []
            for item in sellers[:30]:
                symbol = item.get("symbol", "")
                if not symbol:
                    continue
                
                analysis = self.analyze_stock(symbol)
                if analysis.is_distributing and abs(analysis.net_flow_1m) >= min_flow:
                    distribution.append(analysis)
            
            # Sort by outflow (most negative first)
            distribution.sort(key=lambda x: x.net_flow_1m)
            
            return distribution[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get distribution stocks: {e}")
            return []
    
    def get_sector_flows(self) -> List[SectorFlow]:
        """
        Get smart money flow by sector.
        
        Returns:
            List of SectorFlow sorted by net flow
        """
        sector_data: Dict[str, SectorFlow] = {}
        
        try:
            # Get accumulation stocks
            accum_stocks = self.get_accumulation_stocks(limit=50)
            for stock in accum_stocks:
                sector = stock.sector or "Unknown"
                if sector not in sector_data:
                    sector_data[sector] = SectorFlow(sector=sector)
                
                sector_data[sector].net_flow_1w += stock.net_flow_1w
                sector_data[sector].net_flow_1m += stock.net_flow_1m
                sector_data[sector].stock_count += 1
                sector_data[sector].accumulating_count += 1
                sector_data[sector].top_stocks.append(stock)
            
            # Get distribution stocks
            dist_stocks = self.get_distribution_stocks(limit=30)
            for stock in dist_stocks:
                sector = stock.sector or "Unknown"
                if sector not in sector_data:
                    sector_data[sector] = SectorFlow(sector=sector)
                
                sector_data[sector].net_flow_1w += stock.net_flow_1w
                sector_data[sector].net_flow_1m += stock.net_flow_1m
                sector_data[sector].stock_count += 1
                sector_data[sector].distributing_count += 1
            
        except Exception as e:
            logger.error(f"Failed to get sector flows: {e}")
        
        # Sort by net flow
        flows = list(sector_data.values())
        flows.sort(key=lambda x: x.net_flow_1m, reverse=True)
        
        return flows
    
    def get_market_flow(self) -> SmartMoneyReport:
        """
        Get comprehensive market-wide smart money analysis.
        
        Returns:
            SmartMoneyReport with all analysis
        """
        report = SmartMoneyReport(date=date.today())
        
        try:
            # Get accumulation stocks
            report.top_accumulation = self.get_accumulation_stocks(limit=10)
            for stock in report.top_accumulation:
                report.total_inflow += stock.net_flow_1m
            
            # Get distribution stocks
            report.top_distribution = self.get_distribution_stocks(limit=10)
            for stock in report.top_distribution:
                report.total_outflow += abs(stock.net_flow_1m)
            
            # Calculate net flow
            report.net_flow = report.total_inflow - report.total_outflow
            
            # Get sector flows
            report.sector_flows = self.get_sector_flows()
            
            # Get institutional favorites (high concentration + accumulating)
            if self.sharehub:
                try:
                    holdings = self.sharehub.get_top_accumulated_stocks(
                        duration="1M",
                        min_holding_pct=50.0,
                        limit=10
                    )
                    
                    for item in holdings:
                        symbol = item.get("symbol", "")
                        if symbol:
                            stock = self.analyze_stock(symbol)
                            stock.ltp = float(item.get("ltp", 0) or 0)
                            stock.top3_broker_pct = float(item.get("topThreeBrokersHoldingPercentage", 0) or 0)
                            report.institutional_favorites.append(stock)
                            
                except Exception as e:
                    logger.debug(f"Could not get institutional favorites: {e}")
            
        except Exception as e:
            logger.error(f"Failed to generate smart money report: {e}")
        
        return report
    
    def format_report(self, report: SmartMoneyReport = None) -> str:
        """Format smart money report for CLI output."""
        if report is None:
            report = self.get_market_flow()
        
        lines = []
        
        lines.append("=" * 60)
        lines.append(f"💰 SMART MONEY FLOW ({report.date.strftime('%d-%b-%Y')})")
        lines.append("=" * 60)
        lines.append("")
        
        # Summary
        inflow_cr = report.total_inflow / 10_000_000
        outflow_cr = report.total_outflow / 10_000_000
        net_cr = report.net_flow / 10_000_000
        
        net_emoji = "🟢" if net_cr > 0 else "🔴"
        lines.append(f"📊 MARKET FLOW SUMMARY")
        lines.append(f"   🟢 Inflow:  Rs.{inflow_cr:.1f}Cr")
        lines.append(f"   🔴 Outflow: Rs.{outflow_cr:.1f}Cr")
        lines.append(f"   {net_emoji} Net:     Rs.{net_cr:+.1f}Cr")
        lines.append("")
        
        # Top accumulation
        if report.top_accumulation:
            lines.append("🟢 TOP ACCUMULATION (Smart Money Buying)")
            lines.append("-" * 50)
            lines.append(f"{'#':<3} {'Symbol':<10} {'1M Flow':<15} {'1W Flow':<15} {'Signal'}")
            lines.append("-" * 50)
            for i, stock in enumerate(report.top_accumulation[:5], 1):
                lines.append(
                    f"{i:<3} {stock.symbol:<10} "
                    f"{stock.formatted_flow_1m:<15} "
                    f"{stock.formatted_flow_1w:<15} "
                    f"{stock.smart_money_signal}"
                )
            lines.append("")
        
        # Top distribution
        if report.top_distribution:
            lines.append("🔴 TOP DISTRIBUTION (Smart Money Selling)")
            lines.append("-" * 50)
            for i, stock in enumerate(report.top_distribution[:5], 1):
                lines.append(
                    f"{i:<3} {stock.symbol:<10} "
                    f"{stock.formatted_flow_1m:<15} "
                    f"{stock.formatted_flow_1w:<15} "
                    f"{stock.smart_money_signal}"
                )
            lines.append("")
        
        # Sector flows
        if report.sector_flows:
            lines.append("📈 SECTOR SMART MONEY FLOW")
            lines.append("-" * 50)
            for flow in report.sector_flows[:5]:
                net_cr = flow.net_flow_1m / 10_000_000
                emoji = "🟢" if net_cr > 0 else "🔴"
                lines.append(
                    f"  {emoji} {flow.sector}: Rs.{net_cr:+.1f}Cr "
                    f"({flow.accumulating_count}↑ {flow.distributing_count}↓)"
                )
            lines.append("")
        
        # Institutional favorites
        if report.institutional_favorites:
            lines.append("⭐ INSTITUTIONAL FAVORITES (High Concentration)")
            lines.append("-" * 50)
            for stock in report.institutional_favorites[:5]:
                lines.append(
                    f"  {stock.symbol}: {stock.top3_broker_pct:.0f}% top3 | "
                    f"Flow: {stock.formatted_flow_1m}"
                )
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Convenience functions
def get_smart_money_report(sector: str = None) -> str:
    """Get formatted smart money report (convenience function)."""
    tracker = SmartMoneyTracker()
    report = tracker.get_market_flow()  # Sector filtering not yet supported in backend
    return tracker.format_report(report)


def get_accumulating_stocks() -> List[str]:
    """Get list of stocks being accumulated."""
    tracker = SmartMoneyTracker()
    stocks = tracker.get_accumulation_stocks(limit=10)
    return [s.symbol for s in stocks]


def get_distributing_stocks() -> List[str]:
    """Get list of stocks being distributed."""
    tracker = SmartMoneyTracker()
    stocks = tracker.get_distribution_stocks(limit=10)
    return [s.symbol for s in stocks]
