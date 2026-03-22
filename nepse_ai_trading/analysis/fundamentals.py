"""
Fundamental Analysis Module for NEPSE AI Trading Bot.

🚀 DATA SOURCES - THE MILLIONAIRE'S EDGE
========================================

This module combines TWO powerful data sources:

1️⃣ NEPSE UNOFFICIAL API (nepalstock.com):
   - ✅ Market Capitalization
   - ✅ Listed Shares, Paid-up Capital
   - ✅ Promoter/Public Holding %
   - ✅ 52-Week High/Low
   - ✅ Last Traded Price (LTP)
   - ✅ Real-time OHLCV data
   - ⚠️ Floor Sheet (market hours only)
   - ⚠️ Market Depth (market hours only)

2️⃣ SHAREHUB NEPAL API (FREE! - sharehubnepal.com):
   - ✅ PE Ratio, PB Ratio (calculated from EPS/Book Value)
   - ✅ EPS (Earnings Per Share) - basic & annualized
   - ✅ Book Value (Net Worth per share)
   - ✅ ROE, ROA
   - ✅ Dividend History (bonus %, cash %)
   - ✅ Technical Ratings (RSI, MACD, ADX signals)
   - ✅ Price Change Summary (3D, 7D, 30D, 90D, 180D, 52W)
   - ✅ Banking Metrics: NPL, CD Ratio, Base Rate, Capital Adequacy
   - 🔒 Broker Analysis (requires auth token)

WHY THIS MATTERS:
=================
- NEPSE API alone CANNOT provide PE/EPS/ROE!
- ShareHub API is FREE and provides all fundamental data!
- No more unreliable web scraping - just API calls!
- Banking-specific metrics available for bank stocks!

USAGE:
======
    analyzer = FundamentalAnalyzer()
    
    # Get complete fundamentals (NEPSE + ShareHub combined)
    fundamentals = analyzer.get_fundamentals("NABIL")
    print(f"PE: {fundamentals.pe_ratio}, ROE: {fundamentals.roe}%")
    
    # Get dividend history
    dividends = analyzer.get_dividend_history("NABIL")
    
    # Get technical ratings (no need to calculate yourself!)
    ratings = analyzer.get_technical_ratings("NABIL")
    
    # Get complete analysis for AI
    full_analysis = analyzer.get_complete_analysis("NABIL")
"""

import asyncio
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from collections import defaultdict
from loguru import logger

from data.fetcher import NepseFetcher
from data.data_cleaner import parse_nepse_number


@dataclass
class FundamentalData:
    """
    Complete fundamental data for a stock.
    
    Data Sources:
    - NEPSE API: Market cap, shares, 52W range, LTP
    - ShareHub API: PE, EPS, ROE, ROA, Book Value (FREE!)
    
    This is what separates intelligent investors from gamblers.
    """
    symbol: str
    name: str = ""
    sector: str = ""
    
    # Valuation Metrics
    market_cap: float = 0.0                # Market Capitalization
    pe_ratio: float = 0.0                  # Price to Earnings Ratio
    pb_ratio: float = 0.0                  # Price to Book Value
    eps: float = 0.0                       # Earnings Per Share (basic)
    eps_annualized: float = 0.0            # Annualized EPS (from ShareHub)
    book_value: float = 0.0                # Book Value Per Share (Net Worth)
    
    # Profitability
    roe: float = 0.0                       # Return on Equity (%)
    roa: float = 0.0                       # Return on Assets (%)
    net_profit_margin: float = 0.0         # Net Profit Margin (%)
    
    # Banking-Specific Metrics (from ShareHub)
    npl: Optional[float] = None            # Non-Performing Loan Ratio (%)
    cd_ratio: Optional[float] = None       # Credit to Deposit Ratio (%)
    base_rate: Optional[float] = None      # Base Interest Rate (%)
    capital_adequacy: Optional[float] = None  # Capital Adequacy Ratio (%)
    
    # Share Information
    listed_shares: int = 0
    paid_up_capital: float = 0.0
    face_value: float = 100.0              # Default Rs. 100
    free_float: float = 0.0                # Free floating shares %
    promoter_holding: float = 0.0          # Promoter holding %
    public_holding: float = 0.0            # Public holding %
    
    # Trading Info
    ltp: float = 0.0                       # Last Traded Price
    week_52_high: float = 0.0
    week_52_low: float = 0.0
    avg_volume_30d: float = 0.0
    
    # Dividend Info
    dps: float = 0.0                       # Dividend Per Share (from ShareHub)
    last_dividend: float = 0.0
    dividend_yield: float = 0.0
    last_bonus: str = ""
    last_right: str = ""
    
    # AGM/SGM
    last_agm_date: Optional[date] = None
    book_closure_date: Optional[date] = None
    
    def valuation_score(self) -> float:
        """
        Score stock valuation (0-100).
        Higher = more undervalued.
        
        Based on:
        - PE ratio (lower is better for value)
        - PB ratio (lower is better)
        - ROE (higher is better)
        """
        score = 50  # Neutral baseline
        
        # PE Ratio scoring
        if 0 < self.pe_ratio < 10:
            score += 20  # Cheap
        elif 10 <= self.pe_ratio < 15:
            score += 10  # Fair
        elif 15 <= self.pe_ratio < 25:
            score += 0   # Average
        elif self.pe_ratio >= 25:
            score -= 10  # Expensive
        
        # PB Ratio scoring
        if 0 < self.pb_ratio < 1:
            score += 20  # Trading below book value
        elif 1 <= self.pb_ratio < 2:
            score += 10  # Fair
        elif 2 <= self.pb_ratio < 3:
            score += 0   # Average
        elif self.pb_ratio >= 3:
            score -= 10  # Expensive
        
        # ROE scoring
        if self.roe >= 20:
            score += 15  # Excellent
        elif self.roe >= 15:
            score += 10  # Good
        elif self.roe >= 10:
            score += 5   # Average
        elif self.roe < 5:
            score -= 10  # Poor
        
        return max(0, min(100, score))
    
    def dividend_score(self) -> float:
        """Score dividend attractiveness (0-100)."""
        score = 50
        
        if self.dividend_yield >= 5:
            score += 25
        elif self.dividend_yield >= 3:
            score += 15
        elif self.dividend_yield >= 1:
            score += 5
        
        return max(0, min(100, score))
    
    def is_undervalued(self) -> bool:
        """Check if stock appears undervalued."""
        return (
            self.pe_ratio > 0 and self.pe_ratio < 15 and
            self.pb_ratio > 0 and self.pb_ratio < 2 and
            self.roe > 10
        )
    
    def get_recommendation(self) -> str:
        """Get simple recommendation based on fundamentals."""
        val_score = self.valuation_score()
        
        if val_score >= 75:
            return "STRONG VALUE"
        elif val_score >= 60:
            return "GOOD VALUE"
        elif val_score >= 40:
            return "FAIR VALUE"
        else:
            return "OVERVALUED"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "sector": self.sector,
            "market_cap": self.market_cap,
            "pe_ratio": self.pe_ratio,
            "pb_ratio": self.pb_ratio,
            "eps": self.eps,
            "book_value": self.book_value,
            "roe": self.roe,
            "dividend_yield": self.dividend_yield,
            "ltp": self.ltp,
            "52w_high": self.week_52_high,
            "52w_low": self.week_52_low,
            "valuation_score": self.valuation_score(),
            "recommendation": self.get_recommendation(),
        }
    
    def summary(self) -> str:
        """Human-readable summary with all available data."""
        banking_section = ""
        if self.npl is not None:
            banking_section = f"""
║ BANKING METRICS                                              ║
║   NPL Ratio:           {self.npl:>10.2f}%                       ║
║   CD Ratio:            {self.cd_ratio or 0:>10.2f}%                       ║
║   Base Rate:           {self.base_rate or 0:>10.2f}%                       ║
║   Capital Adequacy:    {self.capital_adequacy or 0:>10.2f}%                       ║
╠══════════════════════════════════════════════════════════════╣"""
        
        return f"""
╔══════════════════════════════════════════════════════════════╗
║          FUNDAMENTAL ANALYSIS: {self.symbol:10}                  ║
╠══════════════════════════════════════════════════════════════╣
║ Company: {self.name[:45]:45}  ║
║ Sector:  {self.sector[:45]:45}  ║
╠══════════════════════════════════════════════════════════════╣
║ VALUATION                                                    ║
║   Market Cap:    Rs. {self.market_cap/10000000:>10.2f} Cr                    ║
║   LTP:           Rs. {self.ltp:>10.2f}                        ║
║   PE Ratio:          {self.pe_ratio:>10.2f}                        ║
║   PB Ratio:          {self.pb_ratio:>10.2f}                        ║
║   EPS:           Rs. {self.eps:>10.2f}                        ║
║   EPS (Annualized):  {self.eps_annualized:>10.2f}                        ║
║   Book Value:    Rs. {self.book_value:>10.2f}                        ║
╠══════════════════════════════════════════════════════════════╣
║ PROFITABILITY                                                ║
║   ROE:               {self.roe:>10.2f}%                       ║
║   ROA:               {self.roa:>10.2f}%                       ║
╠══════════════════════════════════════════════════════════════╣{banking_section}
║ DIVIDENDS                                                    ║
║   DPS (Share Hub):   {self.dps:>10.2f}                        ║
║   Last Dividend:     {self.last_dividend:>10.2f}%                       ║
║   Dividend Yield:    {self.dividend_yield:>10.2f}%                       ║
║   Last Bonus:        {self.last_bonus[:20]:>20}              ║
╠══════════════════════════════════════════════════════════════╣
║ 52-WEEK RANGE                                                ║
║   High:          Rs. {self.week_52_high:>10.2f}                        ║
║   Low:           Rs. {self.week_52_low:>10.2f}                        ║
╠══════════════════════════════════════════════════════════════╣
║ VALUATION SCORE:     {self.valuation_score():>10.0f}/100                    ║
║ RECOMMENDATION:      {self.get_recommendation():>20}              ║
╚══════════════════════════════════════════════════════════════╝
"""


@dataclass
class BrokerAnalysis:
    """
    Broker-wise transaction analysis.
    
    This reveals institutional buying/selling patterns.
    Big brokers = institutional money = smart money.
    """
    symbol: str
    date: date
    
    # Top buyers
    top_buyers: List[Dict] = field(default_factory=list)
    # Top sellers
    top_sellers: List[Dict] = field(default_factory=list)
    
    # Aggregate stats
    total_buy_volume: int = 0
    total_sell_volume: int = 0
    unique_buyers: int = 0
    unique_sellers: int = 0
    
    # Net position
    buy_sell_ratio: float = 1.0            # > 1 = more buying
    net_volume: int = 0                    # Positive = net buying
    
    # Large transaction detection
    large_transactions: int = 0            # Transactions > Rs. 1 Cr
    avg_transaction_size: float = 0.0
    
    def is_accumulation(self) -> bool:
        """Check if there's net accumulation by institutions."""
        return (
            self.buy_sell_ratio > 1.2 and
            self.large_transactions > 5 and
            self.net_volume > 0
        )
    
    def is_distribution(self) -> bool:
        """Check if institutions are selling."""
        return (
            self.buy_sell_ratio < 0.8 and
            self.large_transactions > 5 and
            self.net_volume < 0
        )
    
    def signal(self) -> str:
        """Get broker analysis signal."""
        if self.is_accumulation():
            return "ACCUMULATION"
        elif self.is_distribution():
            return "DISTRIBUTION"
        else:
            return "NEUTRAL"


@dataclass
class MarketDepthAnalysis:
    """
    Order book analysis.
    
    Shows pending buy/sell orders at different prices.
    Used to gauge immediate supply/demand.
    """
    symbol: str
    timestamp: datetime
    
    # Bid side (buyers)
    total_bid_quantity: int = 0
    best_bid_price: float = 0.0
    best_bid_quantity: int = 0
    bid_levels: List[Dict] = field(default_factory=list)
    
    # Ask side (sellers)
    total_ask_quantity: int = 0
    best_ask_price: float = 0.0
    best_ask_quantity: int = 0
    ask_levels: List[Dict] = field(default_factory=list)
    
    # Derived metrics
    spread: float = 0.0                    # Best ask - Best bid
    spread_pct: float = 0.0                # Spread as % of mid price
    imbalance: float = 0.0                 # (Bid - Ask) / (Bid + Ask)
    
    def is_bullish(self) -> bool:
        """Check if order book is bullish."""
        return self.imbalance > 0.3  # More buyers than sellers
    
    def is_bearish(self) -> bool:
        """Check if order book is bearish."""
        return self.imbalance < -0.3  # More sellers than buyers
    
    def get_support_price(self) -> float:
        """Get nearest support from bid levels."""
        if self.bid_levels:
            # Find level with highest quantity
            max_bid = max(self.bid_levels, key=lambda x: x.get("quantity", 0))
            return max_bid.get("price", 0)
        return 0
    
    def get_resistance_price(self) -> float:
        """Get nearest resistance from ask levels."""
        if self.ask_levels:
            # Find level with highest quantity
            max_ask = max(self.ask_levels, key=lambda x: x.get("quantity", 0))
            return max_ask.get("price", 0)
        return 0


class FundamentalAnalyzer:
    """
    Comprehensive fundamental analysis for NEPSE stocks.
    
    Usage:
        analyzer = FundamentalAnalyzer()
        
        # Get complete fundamental data (uses ShareHub for PE/EPS/ROE!)
        fundamentals = analyzer.get_fundamentals("NABIL")
        print(fundamentals.summary())
        
        # Analyze broker activity
        broker_data = analyzer.analyze_brokers("NABIL")
        print(f"Signal: {broker_data.signal()}")
        
        # Market depth
        depth = analyzer.get_market_depth("NABIL")
        print(f"Support: {depth.get_support_price()}")
    """
    
    def __init__(self):
        self.fetcher = NepseFetcher()
        self._company_cache: Dict[str, Any] = {}
        
        # Initialize ShareHub API for fundamental data
        try:
            from data.sharehub_api import ShareHubAPI
            self.sharehub = ShareHubAPI()
            self._sharehub_available = True
            logger.info("ShareHub API initialized for fundamental data")
        except ImportError:
            self.sharehub = None
            self._sharehub_available = False
            logger.warning("ShareHub API not available")
    
    def get_fundamentals(self, symbol: str) -> FundamentalData:
        """
        Get complete fundamental data for a stock.
        
        Uses TWO sources:
        1. NEPSE API: Market cap, shares, 52W high/low, LTP
        2. ShareHub API: PE, EPS, ROE, ROA, Book Value, NPL, etc.
        
        This combination gives COMPLETE fundamental analysis!
        
        Args:
            symbol: Stock symbol (e.g., "NABIL")
            
        Returns:
            FundamentalData with ALL metrics
        """
        symbol = symbol.upper()
        logger.info(f"Fetching fundamentals for {symbol}...")
        
        fundamentals = FundamentalData(symbol=symbol)
        
        # STEP 1: Get basic data from NEPSE API
        try:
            details = self.fetcher.fetch_company_details(symbol)
            
            if details:
                # Parse based on ACTUAL API response structure
                # The API returns these top-level keys:
                # - securityDailyTradeDto: daily trading data
                # - security: company/security master data
                # - stockListedShares, paidUpCapital, marketCapitalization
                # - publicPercentage, promoterPercentage
                
                security = details.get("security", {})
                daily_trade = details.get("securityDailyTradeDto", {})
                company_info = security.get("companyId", {})
                sector_info = company_info.get("sectorMaster", {})
                
                # Company Info
                fundamentals.name = security.get("securityName", 
                                    company_info.get("companyName", ""))
                fundamentals.sector = sector_info.get("sectorDescription", "")
                
                # Share Info - these come from top level
                fundamentals.listed_shares = int(parse_nepse_number(
                    details.get("stockListedShares", 0)) or 0)
                fundamentals.paid_up_capital = parse_nepse_number(
                    details.get("paidUpCapital", 0)) or 0
                fundamentals.market_cap = parse_nepse_number(
                    details.get("marketCapitalization", 0)) or 0
                fundamentals.face_value = parse_nepse_number(
                    security.get("faceValue", 100)) or 100
                
                # Ownership Structure
                fundamentals.public_holding = parse_nepse_number(
                    details.get("publicPercentage", 0)) or 0
                fundamentals.promoter_holding = parse_nepse_number(
                    details.get("promoterPercentage", 0)) or 0
                
                # Daily Trading Data
                fundamentals.ltp = parse_nepse_number(
                    daily_trade.get("lastTradedPrice", 
                    daily_trade.get("closePrice", 0))) or 0
                fundamentals.week_52_high = parse_nepse_number(
                    daily_trade.get("fiftyTwoWeekHigh", 0)) or 0
                fundamentals.week_52_low = parse_nepse_number(
                    daily_trade.get("fiftyTwoWeekLow", 0)) or 0
                
                logger.info(
                    f"NEPSE API data for {symbol}: "
                    f"Market Cap={fundamentals.market_cap/1e7:.2f}Cr, "
                    f"LTP={fundamentals.ltp}, "
                    f"52W={fundamentals.week_52_high}/{fundamentals.week_52_low}"
                )
            
        except Exception as e:
            logger.error(f"Failed to fetch NEPSE data for {symbol}: {e}")
        
        # STEP 2: Get PE/EPS/ROE/Book Value from ShareHub API (FREE!)
        if self._sharehub_available:
            try:
                sharehub_data = self.sharehub.get_fundamentals(symbol)
                
                if sharehub_data:
                    # Core financial ratios (ShareHub has REAL data!)
                    fundamentals.eps = sharehub_data.eps or 0.0
                    fundamentals.eps_annualized = sharehub_data.eps_annualized or 0.0
                    fundamentals.book_value = sharehub_data.book_value or 0.0  # Book value per share
                    fundamentals.roe = sharehub_data.roe or 0.0
                    fundamentals.roa = sharehub_data.roa or 0.0
                    fundamentals.dps = sharehub_data.dps or 0.0
                    
                    # Banking-specific metrics
                    if sharehub_data.npl > 0:  # Only set if it's a bank
                        fundamentals.npl = sharehub_data.npl
                        fundamentals.cd_ratio = sharehub_data.cd_ratio
                        fundamentals.base_rate = sharehub_data.base_rate
                        fundamentals.capital_adequacy = sharehub_data.capital_adequacy
                    
                    # Calculate PE ratio from LTP and EPS
                    if fundamentals.eps > 0 and fundamentals.ltp > 0:
                        fundamentals.pe_ratio = fundamentals.ltp / fundamentals.eps
                    
                    # Calculate PB ratio from LTP and Book Value
                    if fundamentals.book_value > 0 and fundamentals.ltp > 0:
                        fundamentals.pb_ratio = fundamentals.ltp / fundamentals.book_value
                    
                    logger.info(
                        f"ShareHub data for {symbol}: "
                        f"EPS={fundamentals.eps:.2f}, PE={fundamentals.pe_ratio:.2f}, "
                        f"ROE={fundamentals.roe:.2f}%, BV={fundamentals.book_value:.2f}"
                    )
                else:
                    logger.warning(f"No ShareHub fundamental data for {symbol}")
                    
            except Exception as e:
                logger.error(f"Failed to fetch ShareHub data for {symbol}: {e}")
        else:
            logger.warning("ShareHub API not available - PE/EPS/ROE will be missing")
        
        return fundamentals
    
    async def scrape_sharesansar_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """
        Scrape complete fundamental data from ShareSansar.
        
        ShareSansar has the complete data including:
        - PE Ratio, EPS, Book Value, ROE, ROA
        - Dividend History
        - Financial Reports
        
        This requires Playwright for scraping.
        """
        # Import here to avoid circular import
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright not installed. Cannot scrape ShareSansar.")
            return {}
        
        url = f"https://www.sharesansar.com/company/{symbol.lower()}"
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=15000)
                await page.wait_for_timeout(2000)
                
                data = {}
                
                # Try to extract key metrics
                # EPS
                eps_elem = await page.query_selector('td:has-text("EPS") + td')
                if eps_elem:
                    data["eps"] = parse_nepse_number(await eps_elem.inner_text())
                
                # PE Ratio
                pe_elem = await page.query_selector('td:has-text("P/E Ratio") + td')
                if pe_elem:
                    data["pe_ratio"] = parse_nepse_number(await pe_elem.inner_text())
                
                # Book Value
                bv_elem = await page.query_selector('td:has-text("Book Value") + td')
                if bv_elem:
                    data["book_value"] = parse_nepse_number(await bv_elem.inner_text())
                
                # ROE
                roe_elem = await page.query_selector('td:has-text("ROE") + td')
                if roe_elem:
                    data["roe"] = parse_nepse_number(await roe_elem.inner_text())
                
                await browser.close()
                return data
                
        except Exception as e:
            logger.error(f"Failed to scrape ShareSansar for {symbol}: {e}")
            return {}
    
    def get_dividend_history(self, symbol: str) -> List[Dict]:
        """
        Get complete dividend history from ShareHub API.
        
        Returns list of dividend records with:
        - fiscal_year: e.g., "2080/81"
        - bonus_percent: Bonus share %
        - cash_percent: Cash dividend %
        - right_share: Right share details
        - book_close_date: Book closure date
        
        This is CRITICAL for:
        1. Understanding company's dividend policy
        2. Detecting bonus/right shares for adjusted price calculation
        3. Identifying income-generating stocks
        """
        symbol = symbol.upper()
        
        if not self._sharehub_available:
            logger.warning("ShareHub API not available for dividend history")
            return []
        
        try:
            dividends = self.sharehub.get_dividend_history(symbol)
            
            if dividends:
                logger.info(f"Found {len(dividends)} dividend records for {symbol}")
                return [
                    {
                        "fiscal_year": d.fiscal_year,
                        "bonus_percent": d.bonus_pct,  # Correct attribute name
                        "cash_percent": d.cash_pct,    # Correct attribute name
                        "total_percent": d.total_pct,  # Correct attribute name
                        "book_close_date": str(d.book_closure_date) if d.book_closure_date else None,
                        "status": d.status,
                    }
                    for d in dividends
                ]
            else:
                logger.info(f"No dividend records for {symbol}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get dividend history for {symbol}: {e}")
            return []
    
    def get_technical_ratings(self, symbol: str) -> Dict:
        """
        Get technical indicator ratings from ShareHub API.
        
        Returns signals for:
        - RSI: overbought/oversold/neutral
        - MACD: bullish/bearish/neutral
        - ADX: trending/ranging
        - SMA: above/below various SMAs
        
        This provides a quick technical snapshot without
        needing to download full price history!
        """
        symbol = symbol.upper()
        
        if not self._sharehub_available:
            logger.warning("ShareHub API not available for technical ratings")
            return {}
        
        try:
            analysis = self.sharehub.get_technical_ratings(symbol)
            
            if analysis:
                # TechnicalAnalysis has oscillators and moving_averages lists
                result = {
                    "symbol": symbol,
                    "oscillator_summary": analysis.oscillator_summary,
                    "ma_summary": analysis.ma_summary,
                    "overall_rating": analysis.overall_rating,
                    "oscillators": [],
                    "moving_averages": [],
                }
                
                # Parse oscillators (RSI, MACD, etc.)
                for osc in analysis.oscillators:
                    result["oscillators"].append({
                        "name": osc.name,
                        "value": osc.value,
                        "action": osc.action,
                    })
                
                # Parse moving averages
                for ma in analysis.moving_averages:
                    result["moving_averages"].append({
                        "name": ma.name,
                        "value": ma.value,
                        "action": ma.action,
                    })
                
                return result
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get technical ratings for {symbol}: {e}")
            return {}
    
    def get_price_change_summary(self, symbol: str) -> Dict:
        """
        Get price change summary from ShareHub API.
        
        Returns returns over multiple timeframes:
        - 3 days, 7 days, 30 days
        - 90 days, 180 days
        - 52-week (1 year)
        
        This is useful for:
        1. Momentum screening (stocks with consistent positive returns)
        2. Mean reversion plays (oversold stocks bouncing)
        3. Quick performance assessment
        """
        symbol = symbol.upper()
        
        if not self._sharehub_available:
            logger.warning("ShareHub API not available for price summary")
            return {}
        
        try:
            summary = self.sharehub.get_price_change_summary(symbol)
            
            if summary:
                # PriceChangeSummary is a dataclass, not a dict
                return {
                    "symbol": symbol,
                    "change_3d": summary.change_3d,
                    "change_3d_pct": summary.change_3d_pct,
                    "change_7d": summary.change_7d,
                    "change_7d_pct": summary.change_7d_pct,
                    "change_30d": summary.change_30d,
                    "change_30d_pct": summary.change_30d_pct,
                    "change_90d": summary.change_90d,
                    "change_90d_pct": summary.change_90d_pct,
                    "change_180d": summary.change_180d,
                    "change_180d_pct": summary.change_180d_pct,
                    "change_52w": summary.change_52w,
                    "change_52w_pct": summary.change_52w_pct,
                }
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get price summary for {symbol}: {e}")
            return {}
    
    def get_complete_analysis(self, symbol: str) -> Dict:
        """
        Get COMPLETE stock analysis combining all sources.
        
        This is the MASTER method that pulls:
        1. NEPSE API: Real-time price, market cap, 52W range
        2. ShareHub Fundamentals: PE, EPS, ROE, Book Value
        3. ShareHub Dividends: Dividend history
        4. ShareHub Technicals: RSI, MACD, ADX signals
        5. ShareHub Price Summary: Multi-timeframe returns
        
        Returns a comprehensive dictionary for AI analysis.
        """
        symbol = symbol.upper()
        logger.info(f"Running complete analysis for {symbol}...")
        
        result = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
        }
        
        # 1. Get fundamentals (NEPSE + ShareHub combined)
        fundamentals = self.get_fundamentals(symbol)
        result["fundamentals"] = {
            "name": fundamentals.name,
            "sector": fundamentals.sector,
            "market_cap_cr": fundamentals.market_cap / 1e7,
            "ltp": fundamentals.ltp,
            "pe_ratio": fundamentals.pe_ratio,
            "pb_ratio": fundamentals.pb_ratio,
            "eps": fundamentals.eps,
            "book_value": fundamentals.book_value,
            "roe": fundamentals.roe,
            "roa": fundamentals.roa,
            "week_52_high": fundamentals.week_52_high,
            "week_52_low": fundamentals.week_52_low,
            "promoter_holding": fundamentals.promoter_holding,
            "public_holding": fundamentals.public_holding,
            "valuation_score": fundamentals.valuation_score(),
            "recommendation": fundamentals.get_recommendation(),
        }
        
        # Add banking metrics if available
        if fundamentals.npl is not None:
            result["fundamentals"]["banking"] = {
                "npl": fundamentals.npl,
                "cd_ratio": fundamentals.cd_ratio,
                "base_rate": fundamentals.base_rate,
                "capital_adequacy": fundamentals.capital_adequacy,
            }
        
        # 2. Get dividend history
        result["dividends"] = self.get_dividend_history(symbol)
        
        # 3. Get technical ratings
        result["technical_ratings"] = self.get_technical_ratings(symbol)
        
        # 4. Get price change summary
        result["price_changes"] = self.get_price_change_summary(symbol)
        
        logger.info(f"Complete analysis for {symbol} ready")
        return result
    
    def analyze_brokers(
        self, 
        symbol: str, 
        business_date: date = None
    ) -> BrokerAnalysis:
        """
        Analyze broker-wise buying/selling activity from floor sheet.
        
        This is GOLD for detecting institutional activity!
        
        Floor Sheet API Response Structure (when available):
        Each transaction has:
        - contractId: Unique transaction ID
        - contractQuantity: Number of shares
        - contractRate: Price per share
        - contractAmount: Total value
        - buyerMemberId: Buyer broker code
        - sellerMemberId: Seller broker code
        - buyerBrokerName: Buyer broker name (if available)
        - sellerBrokerName: Seller broker name (if available)
        
        NOTE: Floor sheet data is only available during market hours
        and for recent trading days. NEPSE servers can be unstable.
        
        Args:
            symbol: Stock symbol
            business_date: Date to analyze (default: today)
            
        Returns:
            BrokerAnalysis with buyer/seller breakdown
        """
        symbol = symbol.upper()
        business_date = business_date or date.today()
        
        logger.info(f"Analyzing broker activity for {symbol}...")
        
        analysis = BrokerAnalysis(symbol=symbol, date=business_date)
        
        try:
            # Get floor sheet for the symbol
            floorsheet = self.fetcher.fetch_floorsheet(symbol)
            
            if floorsheet.empty:
                logger.warning(
                    f"No floorsheet data for {symbol}. "
                    "This is normal outside market hours."
                )
                return analysis
            
            # Group by buyer broker
            buyer_volume = defaultdict(int)
            buyer_value = defaultdict(float)
            
            # Group by seller broker  
            seller_volume = defaultdict(int)
            seller_value = defaultdict(float)
            
            # Transaction analysis
            large_tx_count = 0
            total_value = 0
            
            for _, row in floorsheet.iterrows():
                # Parse with fallbacks for different API versions
                qty = parse_nepse_number(
                    row.get("contractQuantity", row.get("quantity", 0))
                ) or 0
                rate = parse_nepse_number(
                    row.get("contractRate", row.get("rate", 0))
                ) or 0
                amount = parse_nepse_number(
                    row.get("contractAmount", row.get("amount", qty * rate))
                ) or 0
                
                # Get broker identifiers
                buyer = str(
                    row.get("buyerBrokerName", "") or 
                    row.get("buyerMemberId", "Unknown")
                )
                seller = str(
                    row.get("sellerBrokerName", "") or 
                    row.get("sellerMemberId", "Unknown")
                )
                
                buyer_volume[buyer] += qty
                buyer_value[buyer] += amount
                
                seller_volume[seller] += qty
                seller_value[seller] += amount
                
                total_value += amount
                
                # Count large transactions (> Rs. 1 Crore)
                if amount > 10_000_000:
                    large_tx_count += 1
            
            # Top buyers
            sorted_buyers = sorted(
                buyer_volume.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
            
            analysis.top_buyers = [
                {
                    "broker": broker,
                    "volume": vol,
                    "value": buyer_value[broker],
                }
                for broker, vol in sorted_buyers
            ]
            
            # Top sellers
            sorted_sellers = sorted(
                seller_volume.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
            
            analysis.top_sellers = [
                {
                    "broker": broker,
                    "volume": vol,
                    "value": seller_value[broker],
                }
                for broker, vol in sorted_sellers
            ]
            
            # Aggregate stats
            analysis.total_buy_volume = sum(buyer_volume.values())
            analysis.total_sell_volume = sum(seller_volume.values())
            analysis.unique_buyers = len(buyer_volume)
            analysis.unique_sellers = len(seller_volume)
            analysis.large_transactions = large_tx_count
            
            # Calculate ratios
            if analysis.total_sell_volume > 0:
                analysis.buy_sell_ratio = (
                    analysis.total_buy_volume / analysis.total_sell_volume
                )
            
            analysis.net_volume = (
                analysis.total_buy_volume - analysis.total_sell_volume
            )
            
            if len(floorsheet) > 0:
                analysis.avg_transaction_size = total_value / len(floorsheet)
            
            logger.info(
                f"Broker analysis complete: {analysis.signal()} "
                f"(B/S ratio: {analysis.buy_sell_ratio:.2f})"
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze brokers for {symbol}: {e}")
        
        return analysis
    
    def get_market_depth(self, symbol: str) -> MarketDepthAnalysis:
        """
        Get order book / market depth analysis.
        
        Shows pending buy/sell orders at each price level.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            MarketDepthAnalysis with bid/ask analysis
        """
        symbol = symbol.upper()
        
        analysis = MarketDepthAnalysis(
            symbol=symbol,
            timestamp=datetime.now(),
        )
        
        try:
            depth = self.fetcher.fetch_market_depth(symbol)
            
            if not depth:
                logger.debug(f"No market depth for {symbol}")
                return analysis
            
            # Parse buy orders (bids)
            buy_data = depth.get("buyMarketDepthList", [])
            if buy_data:
                analysis.bid_levels = [
                    {
                        "price": item.get("orderPrice", 0),
                        "quantity": item.get("quantity", 0),
                        "orders": item.get("orderCount", 0),
                    }
                    for item in buy_data
                ]
                
                analysis.total_bid_quantity = sum(
                    item.get("quantity", 0) for item in buy_data
                )
                
                if analysis.bid_levels:
                    best = max(analysis.bid_levels, key=lambda x: x["price"])
                    analysis.best_bid_price = best["price"]
                    analysis.best_bid_quantity = best["quantity"]
            
            # Parse sell orders (asks)
            sell_data = depth.get("sellMarketDepthList", [])
            if sell_data:
                analysis.ask_levels = [
                    {
                        "price": item.get("orderPrice", 0),
                        "quantity": item.get("quantity", 0),
                        "orders": item.get("orderCount", 0),
                    }
                    for item in sell_data
                ]
                
                analysis.total_ask_quantity = sum(
                    item.get("quantity", 0) for item in sell_data
                )
                
                if analysis.ask_levels:
                    best = min(analysis.ask_levels, key=lambda x: x["price"])
                    analysis.best_ask_price = best["price"]
                    analysis.best_ask_quantity = best["quantity"]
            
            # Calculate spread
            if analysis.best_ask_price > 0 and analysis.best_bid_price > 0:
                analysis.spread = analysis.best_ask_price - analysis.best_bid_price
                mid_price = (analysis.best_ask_price + analysis.best_bid_price) / 2
                analysis.spread_pct = (analysis.spread / mid_price) * 100
            
            # Calculate order imbalance
            total_qty = analysis.total_bid_quantity + analysis.total_ask_quantity
            if total_qty > 0:
                analysis.imbalance = (
                    (analysis.total_bid_quantity - analysis.total_ask_quantity) / 
                    total_qty
                )
            
        except Exception as e:
            logger.debug(f"Failed to get market depth for {symbol}: {e}")
        
        return analysis
    
    def get_price_history_analysis(
        self, 
        symbol: str, 
        days: int = 365
    ) -> Dict[str, Any]:
        """
        Comprehensive price history analysis.
        
        Returns:
            Dict with price statistics, volatility, support/resistance
        """
        symbol = symbol.upper()
        
        try:
            df = self.fetcher.fetch_price_history(symbol, days)
            
            if df.empty:
                return {}
            
            # Current price
            current = df["close"].iloc[-1]
            
            # Price statistics
            high_52w = df["high"].max()
            low_52w = df["low"].min()
            avg_price = df["close"].mean()
            
            # Calculate returns
            df["returns"] = df["close"].pct_change()
            
            # Volatility
            daily_volatility = df["returns"].std() * 100
            annual_volatility = daily_volatility * np.sqrt(252)
            
            # Drawdown from peak
            rolling_max = df["close"].cummax()
            current_drawdown = (current - rolling_max.iloc[-1]) / rolling_max.iloc[-1] * 100
            max_drawdown = ((df["close"] - rolling_max) / rolling_max).min() * 100
            
            # Price levels
            # Support = recent lows
            recent_lows = df["low"].tail(20).nsmallest(3).mean()
            
            # Resistance = recent highs
            recent_highs = df["high"].tail(20).nlargest(3).mean()
            
            # Volume analysis
            avg_volume = df["volume"].mean()
            recent_volume = df["volume"].tail(5).mean()
            volume_trend = "INCREASING" if recent_volume > avg_volume * 1.2 else "NORMAL"
            
            return {
                "symbol": symbol,
                "current_price": current,
                "52w_high": high_52w,
                "52w_low": low_52w,
                "avg_price": avg_price,
                "distance_from_high_pct": (current - high_52w) / high_52w * 100,
                "distance_from_low_pct": (current - low_52w) / low_52w * 100,
                "daily_volatility_pct": daily_volatility,
                "annual_volatility_pct": annual_volatility,
                "current_drawdown_pct": current_drawdown,
                "max_drawdown_pct": max_drawdown,
                "support_level": recent_lows,
                "resistance_level": recent_highs,
                "avg_volume": avg_volume,
                "recent_volume": recent_volume,
                "volume_trend": volume_trend,
            }
            
        except Exception as e:
            logger.error(f"Failed price history analysis for {symbol}: {e}")
            return {}
    
    def screen_by_fundamentals(
        self,
        max_pe: float = 20,
        min_roe: float = 10,
        min_dividend_yield: float = 0,
        sectors: List[str] = None,
    ) -> List[FundamentalData]:
        """
        Screen stocks by fundamental criteria.
        
        Args:
            max_pe: Maximum PE ratio
            min_roe: Minimum ROE %
            min_dividend_yield: Minimum dividend yield %
            sectors: Filter by sectors
            
        Returns:
            List of stocks meeting criteria
        """
        logger.info("Screening stocks by fundamentals...")
        
        stocks = self.fetcher.fetch_company_list()
        results = []
        
        for stock in stocks:
            try:
                # Filter by sector
                if sectors and stock.sector not in sectors:
                    continue
                
                fundamentals = self.get_fundamentals(stock.symbol)
                
                # Apply filters
                if fundamentals.pe_ratio <= 0 or fundamentals.pe_ratio > max_pe:
                    continue
                    
                if fundamentals.roe < min_roe:
                    continue
                
                if fundamentals.dividend_yield < min_dividend_yield:
                    continue
                
                results.append(fundamentals)
                
            except Exception as e:
                logger.debug(f"Error screening {stock.symbol}: {e}")
                continue
        
        # Sort by valuation score
        results.sort(key=lambda x: x.valuation_score(), reverse=True)
        
        logger.info(f"Found {len(results)} stocks meeting fundamental criteria")
        return results
    
    def get_complete_analysis(self, symbol: str) -> Dict[str, Any]:
        """
        Get complete analysis combining all data sources.
        
        This is the ONE function to call for full analysis.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Complete analysis dict
        """
        symbol = symbol.upper()
        logger.info(f"Running complete analysis for {symbol}...")
        
        # Get all data
        fundamentals = self.get_fundamentals(symbol)
        broker_analysis = self.analyze_brokers(symbol)
        market_depth = self.get_market_depth(symbol)
        price_analysis = self.get_price_history_analysis(symbol)
        
        # Combine into final analysis
        analysis = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            
            # Fundamentals
            "fundamentals": fundamentals.to_dict(),
            "valuation_score": fundamentals.valuation_score(),
            "fundamental_recommendation": fundamentals.get_recommendation(),
            
            # Broker Activity
            "broker_signal": broker_analysis.signal(),
            "buy_sell_ratio": broker_analysis.buy_sell_ratio,
            "top_buyers": broker_analysis.top_buyers[:5],
            "top_sellers": broker_analysis.top_sellers[:5],
            "large_transactions": broker_analysis.large_transactions,
            
            # Market Depth
            "order_book_signal": "BULLISH" if market_depth.is_bullish() else (
                "BEARISH" if market_depth.is_bearish() else "NEUTRAL"
            ),
            "spread_pct": market_depth.spread_pct,
            "bid_ask_imbalance": market_depth.imbalance,
            "support_from_depth": market_depth.get_support_price(),
            "resistance_from_depth": market_depth.get_resistance_price(),
            
            # Price Analysis
            **price_analysis,
            
            # Overall Score (combine all signals)
            "overall_score": self._calculate_overall_score(
                fundamentals, broker_analysis, market_depth, price_analysis
            ),
        }
        
        # Get buy/sell recommendation
        analysis["recommendation"] = self._get_recommendation(analysis)
        
        return analysis
    
    def _calculate_overall_score(
        self,
        fundamentals: FundamentalData,
        broker: BrokerAnalysis,
        depth: MarketDepthAnalysis,
        price: Dict,
    ) -> float:
        """Calculate combined score from all analyses."""
        score = 0
        
        # Fundamental score (40%)
        score += fundamentals.valuation_score() * 0.4
        
        # Broker activity score (30%)
        if broker.is_accumulation():
            score += 30
        elif broker.is_distribution():
            score -= 10
        else:
            score += 15
        
        # Market depth score (15%)
        if depth.is_bullish():
            score += 15
        elif depth.is_bearish():
            score += 5
        else:
            score += 10
        
        # Price momentum score (15%)
        if price:
            # Price above average = bullish
            if price.get("current_price", 0) > price.get("avg_price", 0):
                score += 10
            else:
                score += 5
            
            # Volume increasing = bullish
            if price.get("volume_trend") == "INCREASING":
                score += 5
        
        return min(100, max(0, score))
    
    def _get_recommendation(self, analysis: Dict) -> str:
        """Get overall recommendation."""
        score = analysis.get("overall_score", 50)
        
        if score >= 75:
            return "STRONG BUY"
        elif score >= 60:
            return "BUY"
        elif score >= 45:
            return "HOLD"
        elif score >= 30:
            return "REDUCE"
        else:
            return "SELL"


# Convenience functions for quick analysis

def quick_fundamentals(symbol: str) -> FundamentalData:
    """Quick fundamental analysis."""
    analyzer = FundamentalAnalyzer()
    return analyzer.get_fundamentals(symbol)


def check_broker_activity(symbol: str) -> str:
    """Quick check of broker activity signal."""
    analyzer = FundamentalAnalyzer()
    broker = analyzer.analyze_brokers(symbol)
    return broker.signal()


def full_stock_analysis(symbol: str) -> Dict:
    """Complete stock analysis."""
    analyzer = FundamentalAnalyzer()
    return analyzer.get_complete_analysis(symbol)
