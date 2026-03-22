"""
Financial Report Scraper Module.

Scrapes financial reports and key metrics from:
- ShareSansar (primary source)
- Merolagani (fallback)
- NEPSE company pages

Data extracted:
- Quarterly Reports (Q1, Q2, Q3, Annual)
- Balance Sheet (Assets, Liabilities, Equity)
- Income Statement (Revenue, Expenses, Profit)
- Cash Flow Statement
- Key Financial Ratios

NEPSE SPECIFICS:
- Fiscal Year: Shrawan to Ashad (mid-July to mid-July)
- Quarterly reports follow Nepali calendar:
  - Q1: Shrawan-Ashoj (mid-Jul to mid-Oct)
  - Q2: Kartik-Poush (mid-Oct to mid-Jan) = Half-yearly
  - Q3: Magh-Chaitra (mid-Jan to mid-Apr)
  - Q4: Baisakh-Ashad (mid-Apr to mid-Jul) = Annual
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import date, datetime
from enum import Enum

from loguru import logger

try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Financial scraping will be limited.")

from data.data_cleaner import parse_nepse_number


class ReportType(Enum):
    """Types of financial reports."""
    Q1 = "Q1"
    Q2_HALF_YEARLY = "Q2"
    Q3 = "Q3"
    Q4_ANNUAL = "Annual"


class ReportPeriod(Enum):
    """Report periods."""
    QUARTERLY = "quarterly"
    HALF_YEARLY = "half_yearly"
    ANNUAL = "annual"


@dataclass
class BalanceSheet:
    """Balance sheet data."""
    symbol: str
    fiscal_year: str
    quarter: str
    
    # Assets
    total_assets: float = 0.0
    current_assets: float = 0.0
    fixed_assets: float = 0.0
    
    # For banks
    loans_and_advances: float = 0.0
    investments: float = 0.0
    cash_and_bank: float = 0.0
    
    # Liabilities
    total_liabilities: float = 0.0
    current_liabilities: float = 0.0
    deposits: float = 0.0              # For banks
    borrowings: float = 0.0
    
    # Equity
    shareholders_equity: float = 0.0
    paid_up_capital: float = 0.0
    reserves: float = 0.0
    retained_earnings: float = 0.0
    
    @property
    def book_value(self) -> float:
        """Calculate book value per share."""
        if self.paid_up_capital > 0:
            shares = self.paid_up_capital / 100  # Face value Rs. 100
            return self.shareholders_equity / shares
        return 0
    
    @property
    def debt_to_equity(self) -> float:
        """Calculate debt to equity ratio."""
        if self.shareholders_equity > 0:
            return self.total_liabilities / self.shareholders_equity
        return 0


@dataclass
class IncomeStatement:
    """Income statement data."""
    symbol: str
    fiscal_year: str
    quarter: str
    
    # Revenue
    total_revenue: float = 0.0
    interest_income: float = 0.0       # For banks
    fee_income: float = 0.0
    premium_income: float = 0.0        # For insurance
    
    # Expenses
    total_expenses: float = 0.0
    interest_expense: float = 0.0      # For banks
    operating_expense: float = 0.0
    provisions: float = 0.0            # Loan loss provisions
    
    # Profit
    operating_profit: float = 0.0
    profit_before_tax: float = 0.0
    tax: float = 0.0
    net_profit: float = 0.0
    
    # Per share metrics
    eps: float = 0.0
    diluted_eps: float = 0.0
    
    @property
    def net_profit_margin(self) -> float:
        """Calculate net profit margin."""
        if self.total_revenue > 0:
            return (self.net_profit / self.total_revenue) * 100
        return 0
    
    @property
    def operating_margin(self) -> float:
        """Calculate operating margin."""
        if self.total_revenue > 0:
            return (self.operating_profit / self.total_revenue) * 100
        return 0


@dataclass
class FinancialRatios:
    """Key financial ratios."""
    symbol: str
    fiscal_year: str
    quarter: str
    
    # Profitability
    roe: float = 0.0                   # Return on Equity
    roa: float = 0.0                   # Return on Assets
    npm: float = 0.0                   # Net Profit Margin
    
    # Valuation
    pe_ratio: float = 0.0
    pb_ratio: float = 0.0
    
    # Efficiency (for banks)
    nim: float = 0.0                   # Net Interest Margin
    cost_income_ratio: float = 0.0
    
    # Asset Quality (for banks)
    npl_ratio: float = 0.0             # Non-Performing Loan Ratio
    provision_coverage: float = 0.0
    
    # Capital (for banks)
    car: float = 0.0                   # Capital Adequacy Ratio
    tier1_ratio: float = 0.0
    
    # Insurance specific
    combined_ratio: float = 0.0
    solvency_ratio: float = 0.0


@dataclass
class FinancialReport:
    """Complete financial report."""
    symbol: str
    company_name: str
    sector: str
    fiscal_year: str
    report_type: ReportType
    published_date: Optional[date] = None
    
    balance_sheet: Optional[BalanceSheet] = None
    income_statement: Optional[IncomeStatement] = None
    ratios: Optional[FinancialRatios] = None
    
    # Raw data
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def summary(self) -> str:
        """Generate summary text."""
        lines = [
            f"📊 Financial Report: {self.symbol}",
            f"Period: {self.fiscal_year} - {self.report_type.value}",
            "",
        ]
        
        if self.income_statement:
            lines.extend([
                "Income Statement:",
                f"  Net Profit: Rs. {self.income_statement.net_profit:,.0f}",
                f"  EPS: Rs. {self.income_statement.eps:.2f}",
                f"  NPM: {self.income_statement.net_profit_margin:.1f}%",
                "",
            ])
        
        if self.balance_sheet:
            lines.extend([
                "Balance Sheet:",
                f"  Book Value: Rs. {self.balance_sheet.book_value:.2f}",
                f"  Total Assets: Rs. {self.balance_sheet.total_assets:,.0f}",
                f"  D/E Ratio: {self.balance_sheet.debt_to_equity:.2f}",
                "",
            ])
        
        if self.ratios:
            lines.extend([
                "Key Ratios:",
                f"  ROE: {self.ratios.roe:.1f}%",
                f"  ROA: {self.ratios.roa:.2f}%",
                f"  PE Ratio: {self.ratios.pe_ratio:.1f}",
            ])
        
        return "\n".join(lines)


class FinancialReportScraper:
    """
    Scrapes financial reports from various sources.
    
    Usage:
        scraper = FinancialReportScraper()
        
        # Get latest financial report
        report = await scraper.get_latest_report("NABIL")
        print(report.summary())
        
        # Get historical reports
        reports = await scraper.get_financial_history("NABIL", years=3)
    """
    
    def __init__(self):
        self.sharesansar_base = "https://www.sharesansar.com"
        self.merolagani_base = "https://merolagani.com"
        self.headless = True
        
    async def get_latest_report(self, symbol: str) -> Optional[FinancialReport]:
        """
        Get latest financial report for a stock.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            FinancialReport or None if not found
        """
        symbol = symbol.upper()
        
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available")
            return None
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                page = await browser.new_page()
                
                # Try ShareSansar first
                report = await self._scrape_sharesansar(page, symbol)
                
                if not report:
                    # Fallback to Merolagani
                    report = await self._scrape_merolagani(page, symbol)
                
                await browser.close()
                return report
                
        except Exception as e:
            logger.error(f"Error scraping financial report for {symbol}: {e}")
            return None
    
    async def _scrape_sharesansar(
        self,
        page: Page,
        symbol: str,
    ) -> Optional[FinancialReport]:
        """Scrape from ShareSansar."""
        try:
            url = f"{self.sharesansar_base}/company/{symbol}"
            await page.goto(url, timeout=15000)
            await page.wait_for_timeout(2000)
            
            # Look for financial tables
            financials_tab = await page.query_selector('a[href*="financials"]')
            if financials_tab:
                await financials_tab.click()
                await page.wait_for_timeout(2000)
            
            # Extract financial data
            report = FinancialReport(
                symbol=symbol,
                company_name="",
                sector="",
                fiscal_year="",
                report_type=ReportType.Q4_ANNUAL,
            )
            
            # Try to extract company name
            name_elem = await page.query_selector('h1.company-name, h2.company-name')
            if name_elem:
                report.company_name = await name_elem.inner_text()
            
            # Extract key metrics from page
            metrics = await self._extract_metrics_from_page(page)
            
            if metrics:
                # Build income statement
                report.income_statement = IncomeStatement(
                    symbol=symbol,
                    fiscal_year=metrics.get("fiscal_year", ""),
                    quarter="Annual",
                    net_profit=parse_nepse_number(metrics.get("net_profit", "0")),
                    eps=parse_nepse_number(metrics.get("eps", "0")),
                )
                
                # Build balance sheet
                report.balance_sheet = BalanceSheet(
                    symbol=symbol,
                    fiscal_year=metrics.get("fiscal_year", ""),
                    quarter="Annual",
                    shareholders_equity=parse_nepse_number(metrics.get("shareholders_equity", "0")),
                    paid_up_capital=parse_nepse_number(metrics.get("paid_up_capital", "0")),
                )
                
                # Build ratios
                report.ratios = FinancialRatios(
                    symbol=symbol,
                    fiscal_year=metrics.get("fiscal_year", ""),
                    quarter="Annual",
                    pe_ratio=parse_nepse_number(metrics.get("pe_ratio", "0")),
                    pb_ratio=parse_nepse_number(metrics.get("pb_ratio", "0")),
                    roe=parse_nepse_number(metrics.get("roe", "0")),
                )
            
            return report
            
        except Exception as e:
            logger.warning(f"ShareSansar scraping failed for {symbol}: {e}")
            return None
    
    async def _scrape_merolagani(
        self,
        page: Page,
        symbol: str,
    ) -> Optional[FinancialReport]:
        """Scrape from Merolagani."""
        try:
            url = f"{self.merolagani_base}/CompanyDetail.aspx/{symbol}"
            await page.goto(url, timeout=15000)
            await page.wait_for_timeout(2000)
            
            # Extract financial data
            report = FinancialReport(
                symbol=symbol,
                company_name="",
                sector="",
                fiscal_year="",
                report_type=ReportType.Q4_ANNUAL,
            )
            
            # Try to extract data
            metrics = await self._extract_metrics_from_page(page)
            
            if metrics:
                report.income_statement = IncomeStatement(
                    symbol=symbol,
                    fiscal_year=metrics.get("fiscal_year", ""),
                    quarter="Annual",
                    eps=parse_nepse_number(metrics.get("eps", "0")),
                )
                
                report.ratios = FinancialRatios(
                    symbol=symbol,
                    fiscal_year=metrics.get("fiscal_year", ""),
                    quarter="Annual",
                    pe_ratio=parse_nepse_number(metrics.get("pe_ratio", "0")),
                )
            
            return report
            
        except Exception as e:
            logger.warning(f"Merolagani scraping failed for {symbol}: {e}")
            return None
    
    async def _extract_metrics_from_page(self, page: Page) -> Dict[str, str]:
        """Extract financial metrics from page."""
        metrics = {}
        
        try:
            # Look for common metric patterns
            # These selectors work for both ShareSansar and Merolagani
            
            # EPS
            eps_elem = await page.query_selector('[class*="eps"], td:has-text("EPS") + td')
            if eps_elem:
                metrics["eps"] = await eps_elem.inner_text()
            
            # PE Ratio
            pe_elem = await page.query_selector('[class*="pe"], td:has-text("P/E") + td')
            if pe_elem:
                metrics["pe_ratio"] = await pe_elem.inner_text()
            
            # PB Ratio / PBV
            pb_elem = await page.query_selector('[class*="pb"], td:has-text("P/B") + td, td:has-text("PBV") + td')
            if pb_elem:
                metrics["pb_ratio"] = await pb_elem.inner_text()
            
            # Book Value
            bv_elem = await page.query_selector('td:has-text("Book Value") + td')
            if bv_elem:
                metrics["book_value"] = await bv_elem.inner_text()
            
            # ROE
            roe_elem = await page.query_selector('td:has-text("ROE") + td')
            if roe_elem:
                metrics["roe"] = await roe_elem.inner_text()
            
        except Exception as e:
            logger.debug(f"Error extracting metrics: {e}")
        
        return metrics
    
    async def get_financial_history(
        self,
        symbol: str,
        years: int = 3,
    ) -> List[FinancialReport]:
        """
        Get financial history for multiple years.
        
        Args:
            symbol: Stock symbol
            years: Number of years of history
            
        Returns:
            List of FinancialReport objects
        """
        # This would require more sophisticated scraping
        # For now, return single report
        report = await self.get_latest_report(symbol)
        return [report] if report else []
    
    def calculate_growth_rates(
        self,
        reports: List[FinancialReport],
    ) -> Dict[str, float]:
        """
        Calculate year-over-year growth rates.
        
        Args:
            reports: List of financial reports (sorted by date)
            
        Returns:
            Dict with growth rates for various metrics
        """
        if len(reports) < 2:
            return {}
        
        growth = {}
        
        # Sort by fiscal year
        sorted_reports = sorted(
            reports,
            key=lambda r: r.fiscal_year,
            reverse=True  # Most recent first
        )
        
        current = sorted_reports[0]
        previous = sorted_reports[1]
        
        if current.income_statement and previous.income_statement:
            # EPS growth
            if previous.income_statement.eps > 0:
                eps_growth = (
                    (current.income_statement.eps - previous.income_statement.eps) /
                    previous.income_statement.eps * 100
                )
                growth["eps_growth"] = round(eps_growth, 2)
            
            # Profit growth
            if previous.income_statement.net_profit > 0:
                profit_growth = (
                    (current.income_statement.net_profit - previous.income_statement.net_profit) /
                    previous.income_statement.net_profit * 100
                )
                growth["profit_growth"] = round(profit_growth, 2)
        
        if current.balance_sheet and previous.balance_sheet:
            # Book value growth
            if previous.balance_sheet.book_value > 0:
                bv_growth = (
                    (current.balance_sheet.book_value - previous.balance_sheet.book_value) /
                    previous.balance_sheet.book_value * 100
                )
                growth["book_value_growth"] = round(bv_growth, 2)
        
        return growth
    
    def evaluate_financial_health(
        self,
        report: FinancialReport,
    ) -> Dict[str, Any]:
        """
        Evaluate financial health based on report.
        
        Returns:
            Dict with health scores and recommendations
        """
        evaluation = {
            "symbol": report.symbol,
            "overall_score": 0,
            "strengths": [],
            "weaknesses": [],
            "recommendation": "",
        }
        
        score = 50  # Start neutral
        
        if report.ratios:
            # Check ROE
            if report.ratios.roe >= 15:
                score += 15
                evaluation["strengths"].append(f"Strong ROE: {report.ratios.roe:.1f}%")
            elif report.ratios.roe < 8:
                score -= 10
                evaluation["weaknesses"].append(f"Weak ROE: {report.ratios.roe:.1f}%")
            
            # Check PE
            if 0 < report.ratios.pe_ratio < 15:
                score += 10
                evaluation["strengths"].append(f"Attractive PE: {report.ratios.pe_ratio:.1f}")
            elif report.ratios.pe_ratio > 30:
                score -= 10
                evaluation["weaknesses"].append(f"High PE: {report.ratios.pe_ratio:.1f}")
            
            # Check PB
            if 0 < report.ratios.pb_ratio < 2:
                score += 5
                evaluation["strengths"].append(f"Low PB: {report.ratios.pb_ratio:.2f}")
            elif report.ratios.pb_ratio > 3:
                score -= 5
                evaluation["weaknesses"].append(f"High PB: {report.ratios.pb_ratio:.2f}")
        
        if report.income_statement:
            # Check profitability
            if report.income_statement.eps > 30:
                score += 10
                evaluation["strengths"].append(f"Strong EPS: Rs. {report.income_statement.eps:.2f}")
            elif report.income_statement.eps < 10:
                score -= 5
                evaluation["weaknesses"].append(f"Low EPS: Rs. {report.income_statement.eps:.2f}")
        
        if report.balance_sheet:
            # Check debt
            if report.balance_sheet.debt_to_equity < 2:
                score += 5
                evaluation["strengths"].append("Manageable debt levels")
            elif report.balance_sheet.debt_to_equity > 5:
                score -= 10
                evaluation["weaknesses"].append("High debt levels")
        
        # Final score
        evaluation["overall_score"] = max(0, min(100, score))
        
        # Generate recommendation
        if evaluation["overall_score"] >= 70:
            evaluation["recommendation"] = "FUNDAMENTALLY STRONG - Consider for long-term investment"
        elif evaluation["overall_score"] >= 50:
            evaluation["recommendation"] = "MODERATE - Watch for better entry points"
        else:
            evaluation["recommendation"] = "WEAK FUNDAMENTALS - Avoid or trade only"
        
        return evaluation


# Async helper function
async def get_financial_report(symbol: str) -> Optional[FinancialReport]:
    """Convenience function to get financial report."""
    scraper = FinancialReportScraper()
    return await scraper.get_latest_report(symbol)
