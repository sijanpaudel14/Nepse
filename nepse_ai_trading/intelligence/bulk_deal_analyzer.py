"""
Bulk Deal Analyzer - Track large block trades for insider activity detection.

Monitors trades >1Cr value or 10K+ shares to identify:
- Promoter exits (large sells before bad news)
- Institutional accumulation (repeated large buys)
- Block trade patterns (negotiated deals)

Usage:
    analyzer = BulkDealAnalyzer()
    
    # Get all bulk deals today
    deals = analyzer.get_bulk_deals_summary()
    
    # Get bulk deals for a sector
    hydro_deals = analyzer.get_bulk_deals_by_sector("Hydro Power")
    
    # Analyze a specific stock
    analysis = analyzer.analyze_stock_bulk_deals("NGPL", days=7)
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Any
from loguru import logger
import pandas as pd

try:
    from data.sharehub_api import ShareHubAPI
    from data.fetcher import NepseFetcher
except ImportError:
    ShareHubAPI = None
    NepseFetcher = None


@dataclass
class BulkDeal:
    """Single bulk transaction record."""
    symbol: str
    quantity: int
    amount: float
    rate: float
    buyer_broker: str
    seller_broker: str
    trade_time: Optional[datetime] = None
    deal_type: str = "UNKNOWN"  # BUY_HEAVY, SELL_HEAVY, BALANCED
    
    @property
    def is_large(self) -> bool:
        """Check if deal is significant (>1Cr or >10K shares)."""
        return self.amount >= 10_000_000 or self.quantity >= 10_000
    
    @property
    def formatted_amount(self) -> str:
        """Format amount in Cr/Lakh."""
        if self.amount >= 10_000_000:
            return f"Rs.{self.amount / 10_000_000:.2f}Cr"
        elif self.amount >= 100_000:
            return f"Rs.{self.amount / 100_000:.2f}L"
        else:
            return f"Rs.{self.amount:,.0f}"


@dataclass
class BulkDealSummary:
    """Summary of bulk deals for a stock."""
    symbol: str
    sector: str = ""
    total_deals: int = 0
    total_buy_qty: int = 0
    total_sell_qty: int = 0
    total_buy_amount: float = 0.0
    total_sell_amount: float = 0.0
    net_quantity: int = 0
    net_amount: float = 0.0
    dominant_side: str = "NEUTRAL"  # ACCUMULATION, DISTRIBUTION, NEUTRAL
    top_buyer: str = ""
    top_seller: str = ""
    deals: List[BulkDeal] = field(default_factory=list)
    
    @property
    def signal(self) -> str:
        """Trading signal based on bulk deal pattern."""
        if self.net_quantity > 0 and self.net_amount > 5_000_000:
            return "🟢 ACCUMULATION"
        elif self.net_quantity < 0 and abs(self.net_amount) > 5_000_000:
            return "🔴 DISTRIBUTION"
        else:
            return "⚪ NEUTRAL"
    
    @property
    def formatted_net(self) -> str:
        """Format net amount."""
        sign = "+" if self.net_amount >= 0 else ""
        if abs(self.net_amount) >= 10_000_000:
            return f"{sign}Rs.{self.net_amount / 10_000_000:.2f}Cr"
        elif abs(self.net_amount) >= 100_000:
            return f"{sign}Rs.{self.net_amount / 100_000:.2f}L"
        else:
            return f"{sign}Rs.{self.net_amount:,.0f}"


@dataclass
class BulkDealReport:
    """Complete bulk deal analysis report."""
    date: date
    total_stocks: int = 0
    total_deals: int = 0
    total_value: float = 0.0
    accumulation_stocks: List[BulkDealSummary] = field(default_factory=list)
    distribution_stocks: List[BulkDealSummary] = field(default_factory=list)
    neutral_stocks: List[BulkDealSummary] = field(default_factory=list)
    sector_breakdown: Dict[str, Dict] = field(default_factory=dict)


class BulkDealAnalyzer:
    """
    Analyzes bulk transactions to detect institutional activity.
    
    Key signals:
    - Repeated large buys by same broker = Institutional accumulation
    - Large sells by promoter-linked brokers = Exit signal
    - Block trades at discount = Negotiated placement
    """
    
    # Minimum thresholds for "bulk" deals
    MIN_QUANTITY = 3000  # Shares
    MIN_VALUE = 1_000_000  # Rs. 10 Lakh
    
    # Significant thresholds
    SIGNIFICANT_QUANTITY = 10_000
    SIGNIFICANT_VALUE = 10_000_000  # Rs. 1 Crore
    
    def __init__(self):
        """Initialize with API clients."""
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
    
    def get_bulk_deals(self, symbol: str, min_quantity: int = None) -> List[BulkDeal]:
        """
        Get bulk deals for a specific stock.
        
        Args:
            symbol: Stock symbol
            min_quantity: Minimum quantity threshold
            
        Returns:
            List of BulkDeal objects
        """
        min_qty = min_quantity or self.MIN_QUANTITY
        
        if not self.sharehub:
            logger.warning("ShareHub API not available")
            return []
        
        try:
            raw_deals = self.sharehub.get_bulk_transactions(symbol, min_quantity=min_qty)
            
            deals = []
            for item in raw_deals:
                deal = BulkDeal(
                    symbol=symbol.upper(),
                    quantity=int(item.get("quantity", 0) or 0),
                    amount=float(item.get("amount", 0) or 0),
                    rate=float(item.get("rate", 0) or 0),
                    buyer_broker=str(item.get("buyerBrokerCode", "") or item.get("buyerBroker", "")),
                    seller_broker=str(item.get("sellerBrokerCode", "") or item.get("sellerBroker", "")),
                )
                
                # Determine deal type based on broker activity
                if deal.buyer_broker == deal.seller_broker:
                    deal.deal_type = "WASH"  # Same broker buy/sell
                else:
                    deal.deal_type = "BLOCK"
                
                deals.append(deal)
            
            return deals
            
        except Exception as e:
            logger.error(f"Failed to fetch bulk deals for {symbol}: {e}")
            return []
    
    def analyze_stock_bulk_deals(
        self,
        symbol: str,
        days: int = 7,
        min_quantity: int = None
    ) -> BulkDealSummary:
        """
        Analyze bulk deal patterns for a specific stock.
        
        Args:
            symbol: Stock symbol
            days: Number of days to analyze
            min_quantity: Minimum quantity threshold
            
        Returns:
            BulkDealSummary with analysis
        """
        symbol = symbol.upper()
        deals = self.get_bulk_deals(symbol, min_quantity)
        
        summary = BulkDealSummary(
            symbol=symbol,
            sector=self._get_stock_sector(symbol),
            deals=deals,
            total_deals=len(deals),
        )
        
        if not deals:
            return summary
        
        # Aggregate by broker
        buyer_totals: Dict[str, int] = {}
        seller_totals: Dict[str, int] = {}
        
        for deal in deals:
            # Track quantities
            summary.total_buy_qty += deal.quantity
            summary.total_sell_qty += deal.quantity  # Same quantity for buy/sell
            summary.total_buy_amount += deal.amount
            summary.total_sell_amount += deal.amount
            
            # Track by broker
            buyer_totals[deal.buyer_broker] = buyer_totals.get(deal.buyer_broker, 0) + deal.quantity
            seller_totals[deal.seller_broker] = seller_totals.get(deal.seller_broker, 0) + deal.quantity
        
        # Find dominant brokers
        if buyer_totals:
            summary.top_buyer = max(buyer_totals, key=buyer_totals.get)
        if seller_totals:
            summary.top_seller = max(seller_totals, key=seller_totals.get)
        
        # Calculate net (based on broker analysis, not just deals)
        # For bulk deals, we look at pattern - repeated buyer = accumulation
        buy_concentration = max(buyer_totals.values()) / sum(buyer_totals.values()) if buyer_totals else 0
        sell_concentration = max(seller_totals.values()) / sum(seller_totals.values()) if seller_totals else 0
        
        if buy_concentration > 0.5:
            summary.dominant_side = "ACCUMULATION"
            summary.net_quantity = summary.total_buy_qty
            summary.net_amount = summary.total_buy_amount
        elif sell_concentration > 0.5:
            summary.dominant_side = "DISTRIBUTION"
            summary.net_quantity = -summary.total_sell_qty
            summary.net_amount = -summary.total_sell_amount
        else:
            summary.dominant_side = "NEUTRAL"
            summary.net_quantity = 0
            summary.net_amount = 0
        
        return summary
    
    def get_bulk_deals_by_sector(self, sector: str) -> List[BulkDealSummary]:
        """
        Get bulk deals for all stocks in a sector.
        
        Args:
            sector: Sector name (e.g., "Hydro Power", "Commercial Banks")
            
        Returns:
            List of BulkDealSummary for each stock with bulk activity
        """
        results = []
        
        try:
            if not self.fetcher:
                return results
            
            companies = self.fetcher.fetch_company_list()
            sector_stocks = [c.symbol for c in companies if sector.lower() in c.sector.lower()]
            
            for symbol in sector_stocks[:20]:  # Limit to avoid rate limiting
                summary = self.analyze_stock_bulk_deals(symbol)
                if summary.total_deals > 0:
                    results.append(summary)
            
            # Sort by net amount (absolute value)
            results.sort(key=lambda x: abs(x.net_amount), reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to analyze sector {sector}: {e}")
        
        return results
    
    def get_market_bulk_deals(self) -> BulkDealReport:
        """
        Get comprehensive bulk deal report for entire market.
        
        Returns:
            BulkDealReport with market-wide analysis
        """
        report = BulkDealReport(date=date.today())
        
        try:
            if not self.sharehub:
                return report
            
            # Get player favorites (stocks with significant activity)
            favorites = self.sharehub.get_player_favorites()
            
            all_summaries = []
            for fav in favorites[:30]:  # Top 30 active stocks
                symbol = fav.get("symbol", "")
                if not symbol:
                    continue
                
                summary = self.analyze_stock_bulk_deals(symbol)
                if summary.total_deals > 0:
                    all_summaries.append(summary)
                    report.total_deals += summary.total_deals
                    report.total_value += summary.total_buy_amount
            
            report.total_stocks = len(all_summaries)
            
            # Categorize
            for summary in all_summaries:
                if summary.dominant_side == "ACCUMULATION":
                    report.accumulation_stocks.append(summary)
                elif summary.dominant_side == "DISTRIBUTION":
                    report.distribution_stocks.append(summary)
                else:
                    report.neutral_stocks.append(summary)
                
                # Sector breakdown
                sector = summary.sector or "Unknown"
                if sector not in report.sector_breakdown:
                    report.sector_breakdown[sector] = {
                        "count": 0,
                        "total_value": 0,
                        "accumulation": 0,
                        "distribution": 0,
                    }
                report.sector_breakdown[sector]["count"] += 1
                report.sector_breakdown[sector]["total_value"] += summary.total_buy_amount
                if summary.dominant_side == "ACCUMULATION":
                    report.sector_breakdown[sector]["accumulation"] += 1
                elif summary.dominant_side == "DISTRIBUTION":
                    report.sector_breakdown[sector]["distribution"] += 1
            
            # Sort by value
            report.accumulation_stocks.sort(key=lambda x: x.net_amount, reverse=True)
            report.distribution_stocks.sort(key=lambda x: abs(x.net_amount), reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to generate market bulk deal report: {e}")
        
        return report
    
    def detect_promoter_activity(self, symbol: str) -> Dict[str, Any]:
        """
        Detect potential promoter/insider activity patterns.
        
        Looks for:
        - Large sells concentrated in few brokers (exit)
        - Large buys before announcements (accumulation)
        - Block trades at significant premium/discount
        
        Returns:
            Dict with activity analysis
        """
        summary = self.analyze_stock_bulk_deals(symbol, days=30)
        
        result = {
            "symbol": symbol,
            "has_activity": summary.total_deals > 0,
            "activity_type": "NONE",
            "risk_level": "LOW",
            "signals": [],
            "summary": summary,
        }
        
        if not summary.deals:
            return result
        
        # Check for concentrated selling
        if summary.dominant_side == "DISTRIBUTION":
            result["activity_type"] = "PROMOTER_EXIT_RISK"
            result["risk_level"] = "HIGH"
            result["signals"].append(f"🔴 Large distribution detected: {summary.formatted_net}")
            result["signals"].append(f"🔴 Top seller: Broker {summary.top_seller}")
        
        # Check for concentrated buying
        elif summary.dominant_side == "ACCUMULATION":
            result["activity_type"] = "INSTITUTIONAL_ACCUMULATION"
            result["risk_level"] = "LOW"
            result["signals"].append(f"🟢 Institutional accumulation: {summary.formatted_net}")
            result["signals"].append(f"🟢 Top buyer: Broker {summary.top_buyer}")
        
        # Check for wash trades (same broker)
        wash_deals = [d for d in summary.deals if d.deal_type == "WASH"]
        if len(wash_deals) > len(summary.deals) * 0.3:
            result["risk_level"] = "HIGH"
            result["signals"].append(f"⚠️ {len(wash_deals)} wash trades detected (same broker buy/sell)")
        
        return result
    
    def format_report(self, report: BulkDealReport) -> str:
        """Format bulk deal report for CLI output."""
        lines = []
        
        lines.append("=" * 60)
        lines.append(f"🔥 BULK DEAL TRACKER ({report.date.strftime('%d-%b-%Y')})")
        lines.append("=" * 60)
        lines.append("")
        
        # Summary
        total_value_cr = report.total_value / 10_000_000
        lines.append(f"📊 Total Stocks: {report.total_stocks} | Deals: {report.total_deals} | Value: Rs.{total_value_cr:.1f}Cr")
        lines.append(f"🟢 Accumulation: {len(report.accumulation_stocks)} | 🔴 Distribution: {len(report.distribution_stocks)}")
        lines.append("")
        
        # Accumulation stocks
        if report.accumulation_stocks:
            lines.append("🟢 ACCUMULATION (Institutional Buying)")
            lines.append("-" * 50)
            for i, stock in enumerate(report.accumulation_stocks[:5], 1):
                lines.append(f"#{i} {stock.symbol}: {stock.formatted_net} (Buyer: Br.{stock.top_buyer})")
            lines.append("")
        
        # Distribution stocks
        if report.distribution_stocks:
            lines.append("🔴 DISTRIBUTION (Potential Exits)")
            lines.append("-" * 50)
            for i, stock in enumerate(report.distribution_stocks[:5], 1):
                lines.append(f"#{i} {stock.symbol}: {stock.formatted_net} (Seller: Br.{stock.top_seller})")
            lines.append("")
        
        # Sector breakdown
        if report.sector_breakdown:
            lines.append("📈 SECTOR BREAKDOWN")
            lines.append("-" * 50)
            sorted_sectors = sorted(
                report.sector_breakdown.items(),
                key=lambda x: x[1]["total_value"],
                reverse=True
            )
            for sector, data in sorted_sectors[:5]:
                val_cr = data["total_value"] / 10_000_000
                lines.append(f"{sector}: Rs.{val_cr:.1f}Cr ({data['accumulation']}🟢 {data['distribution']}🔴)")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Convenience function
def get_bulk_deal_report() -> str:
    """Get formatted bulk deal report."""
    analyzer = BulkDealAnalyzer()
    report = analyzer.get_market_bulk_deals()
    return analyzer.format_report(report)


def analyze_bulk_deals(symbol: str = None, sector: str = None) -> str:
    """Get bulk deal analysis for a stock or market-wide."""
    analyzer = BulkDealAnalyzer()
    
    if symbol:
        # Single stock analysis
        activity = analyzer.detect_promoter_activity(symbol)
        summary = activity['summary']
        
        lines = [
            f"🔍 BULK DEAL ANALYSIS: {symbol}",
            "-" * 40,
            f"Activity Type: {activity['activity_type']}",
            f"Risk Level: {activity['risk_level']}",
        ]
        
        # FIX #1: Use summary object, not non-existent keys
        if summary.total_deals > 0:
            lines.append(f"Total Deals: {summary.total_deals}")
            lines.append(f"Net Quantity: {summary.net_quantity:,} shares")
            if summary.net_quantity != 0:
                avg_price = summary.net_amount / summary.net_quantity
                lines.append(f"Avg Price: Rs.{avg_price:.2f}")
        
        # FIX #2: Move signals handling BEFORE return (was dead code)
        if activity['signals']:
            lines.append("")
            lines.append("Signals:")
            for sig in activity['signals']:
                lines.append(f"  {sig}")
        
        return "\n".join(lines)
    else:
        # Market-wide bulk deals
        report = analyzer.get_market_bulk_deals()
        return analyzer.format_report(report)
