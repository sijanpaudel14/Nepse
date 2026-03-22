"""
Corporate Actions & Dividend Analysis Module.

Tracks and analyzes:
- Cash Dividends
- Bonus Shares
- Right Shares
- Stock Splits
- AGM/SGM Dates
- Book Closure Dates

IMPORTANT FOR NEPSE:
- Dividends are announced at AGMs (usually after fiscal year end)
- NEPSE fiscal year: Shrawan to Ashad (mid-July to mid-July)
- Bonus shares cause price adjustment (must account in backtesting!)
- Right shares offer = need cash to exercise

MILLIONAIRE STRATEGY:
- Buy before dividend announcement (if expecting good dividend)
- Sell on cum-dividend date if price has run up
- Or hold for long-term compounding

Price Adjustment Formula:
- After X% bonus: Adjusted Price = Old Price × (100 / (100 + X))
- Example: Rs. 1000 stock + 50% bonus → Rs. 1000 × (100/150) = Rs. 666.67
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta
from enum import Enum
from loguru import logger

from data.data_cleaner import parse_nepse_number


class CorporateActionType(Enum):
    """Types of corporate actions."""
    CASH_DIVIDEND = "cash_dividend"
    BONUS_SHARE = "bonus_share"
    RIGHT_SHARE = "right_share"
    STOCK_SPLIT = "stock_split"
    AGM = "agm"
    SGM = "sgm"
    BOOK_CLOSURE = "book_closure"


@dataclass
class CorporateAction:
    """Represents a corporate action."""
    symbol: str
    action_type: CorporateActionType
    announcement_date: Optional[date] = None
    effective_date: Optional[date] = None
    book_closure_from: Optional[date] = None
    book_closure_to: Optional[date] = None
    
    # For dividends
    dividend_pct: float = 0.0              # Percentage of face value
    dividend_amount: float = 0.0            # Rs. per share
    
    # For bonus
    bonus_pct: float = 0.0                  # e.g., 50 = 50% bonus
    bonus_ratio: str = ""                   # e.g., "1:2" (1 bonus for 2 held)
    
    # For rights
    right_pct: float = 0.0
    right_ratio: str = ""
    right_price: float = 0.0                # Price to pay for rights
    
    # Fiscal year
    fiscal_year: str = ""                   # e.g., "2080/81"
    
    @property
    def adjustment_factor(self) -> float:
        """
        Price adjustment factor for bonus shares.
        
        Used to adjust historical prices for backtesting.
        """
        if self.action_type == CorporateActionType.BONUS_SHARE and self.bonus_pct > 0:
            return 100 / (100 + self.bonus_pct)
        return 1.0
    
    def __str__(self) -> str:
        if self.action_type == CorporateActionType.CASH_DIVIDEND:
            return f"{self.symbol}: {self.dividend_pct}% Cash Dividend"
        elif self.action_type == CorporateActionType.BONUS_SHARE:
            return f"{self.symbol}: {self.bonus_pct}% Bonus Share"
        elif self.action_type == CorporateActionType.RIGHT_SHARE:
            return f"{self.symbol}: {self.right_pct}% Right @ Rs.{self.right_price}"
        else:
            return f"{self.symbol}: {self.action_type.value}"


@dataclass
class DividendHistory:
    """
    Complete dividend history for a stock.
    """
    symbol: str
    name: str = ""
    sector: str = ""
    
    # Summary stats
    total_dividends: int = 0
    avg_dividend_pct: float = 0.0
    avg_dividend_yield: float = 0.0
    total_bonus_pct: float = 0.0
    
    # History
    actions: List[CorporateAction] = field(default_factory=list)
    
    # Consistency
    consecutive_dividend_years: int = 0
    is_dividend_king: bool = False          # 10+ years consecutive
    
    def get_dividend_trend(self) -> str:
        """Check if dividends are increasing, stable, or decreasing."""
        if len(self.actions) < 3:
            return "INSUFFICIENT DATA"
        
        dividends = [
            a.dividend_pct for a in self.actions 
            if a.action_type == CorporateActionType.CASH_DIVIDEND
        ][-5:]  # Last 5 dividends
        
        if len(dividends) < 2:
            return "N/A"
        
        # Check trend
        increasing = all(dividends[i] >= dividends[i-1] for i in range(1, len(dividends)))
        decreasing = all(dividends[i] <= dividends[i-1] for i in range(1, len(dividends)))
        
        if increasing:
            return "INCREASING"
        elif decreasing:
            return "DECREASING"
        else:
            return "STABLE"
    
    def summary(self) -> str:
        """Generate summary text."""
        lines = [
            f"Dividend History: {self.symbol}",
            f"Total Actions: {len(self.actions)}",
            f"Average Dividend: {self.avg_dividend_pct:.1f}%",
            f"Consecutive Years: {self.consecutive_dividend_years}",
            f"Trend: {self.get_dividend_trend()}",
        ]
        
        if self.is_dividend_king:
            lines.append("🏆 DIVIDEND KING (10+ years)")
        
        return "\n".join(lines)


@dataclass
class DividendCalendar:
    """
    Upcoming corporate actions calendar.
    """
    upcoming_agms: List[Dict] = field(default_factory=list)
    upcoming_dividends: List[Dict] = field(default_factory=list)
    upcoming_book_closures: List[Dict] = field(default_factory=list)
    recent_announcements: List[CorporateAction] = field(default_factory=list)


class CorporateActionsAnalyzer:
    """
    Analyzes corporate actions for trading decisions.
    
    Usage:
        analyzer = CorporateActionsAnalyzer()
        
        # Get dividend history
        history = analyzer.get_dividend_history("NABIL")
        print(history.summary())
        
        # Find high-yield stocks
        high_yield = analyzer.screen_by_dividend(min_yield=4.0)
        
        # Adjust prices for bonus shares
        adjusted_df = analyzer.adjust_prices_for_bonus(df, "NABIL")
    """
    
    def __init__(self):
        # Cache for corporate actions
        self._actions_cache: Dict[str, List[CorporateAction]] = {}
    
    def get_dividend_history(self, symbol: str) -> DividendHistory:
        """
        Get complete dividend history for a stock.
        
        Note: This would ideally scrape from ShareSansar or use a database.
        For now, returns structure based on available NEPSE data.
        """
        symbol = symbol.upper()
        
        history = DividendHistory(symbol=symbol)
        
        # This would be populated from database or scraped data
        # For now, placeholder structure
        
        return history
    
    def calculate_dividend_yield(
        self,
        dividend_pct: float,
        current_price: float,
        face_value: float = 100,
    ) -> float:
        """
        Calculate dividend yield.
        
        Formula: Yield = (Dividend Amount / Current Price) × 100
        
        Args:
            dividend_pct: Dividend as % of face value
            current_price: Current market price
            face_value: Face value of share (Rs. 100 for most NEPSE stocks)
            
        Returns:
            Dividend yield in percentage
        """
        if current_price <= 0:
            return 0
        
        dividend_amount = face_value * (dividend_pct / 100)
        yield_pct = (dividend_amount / current_price) * 100
        
        return round(yield_pct, 2)
    
    def calculate_bonus_adjusted_price(
        self,
        price: float,
        bonus_pct: float,
    ) -> float:
        """
        Calculate price after bonus share adjustment.
        
        Used for accurate backtesting.
        
        Args:
            price: Price before bonus
            bonus_pct: Bonus percentage
            
        Returns:
            Adjusted price after bonus
        """
        if bonus_pct <= 0:
            return price
        
        adjustment_factor = 100 / (100 + bonus_pct)
        return price * adjustment_factor
    
    def calculate_right_impact(
        self,
        current_price: float,
        right_pct: float,
        right_price: float,
    ) -> Dict[str, float]:
        """
        Calculate impact of right share issue.
        
        Args:
            current_price: Current market price
            right_pct: Right share percentage
            right_price: Price of right shares
            
        Returns:
            Dict with theoretical ex-right price and dilution
        """
        # Calculate theoretical ex-right price (TERP)
        # TERP = (Current Price × 100 + Right Price × Right%) / (100 + Right%)
        
        terp = (
            (current_price * 100) + (right_price * right_pct)
        ) / (100 + right_pct)
        
        dilution = (current_price - terp) / current_price * 100
        
        return {
            "current_price": current_price,
            "right_price": right_price,
            "right_pct": right_pct,
            "theoretical_ex_right_price": round(terp, 2),
            "dilution_pct": round(dilution, 2),
            "cash_needed_per_share": right_price * (right_pct / 100),
        }
    
    def adjust_prices_for_corporate_actions(
        self,
        df: pd.DataFrame,
        actions: List[CorporateAction],
    ) -> pd.DataFrame:
        """
        Adjust historical prices for all corporate actions.
        
        CRITICAL FOR BACKTESTING:
        Without adjustment, a 50% bonus looks like a 33% crash!
        
        Args:
            df: DataFrame with 'date', 'close', etc.
            actions: List of corporate actions
            
        Returns:
            DataFrame with adjusted prices
        """
        if df.empty or not actions:
            return df
        
        df = df.copy()
        df["adjusted_close"] = df["close"]
        df["adjustment_factor"] = 1.0
        
        # Sort actions by date
        sorted_actions = sorted(
            [a for a in actions if a.effective_date and a.adjustment_factor != 1.0],
            key=lambda x: x.effective_date,
            reverse=True  # Most recent first
        )
        
        for action in sorted_actions:
            # Apply adjustment to all prices BEFORE the effective date
            mask = df["date"] < action.effective_date
            
            df.loc[mask, "adjusted_close"] *= action.adjustment_factor
            df.loc[mask, "adjustment_factor"] *= action.adjustment_factor
            
            logger.debug(
                f"Adjusted prices for {action.symbol} {action.action_type.value} "
                f"on {action.effective_date} (factor: {action.adjustment_factor:.4f})"
            )
        
        return df
    
    def screen_dividend_stocks(
        self,
        stocks: List[Dict],
        min_yield: float = 3.0,
        min_consecutive_years: int = 3,
    ) -> List[Dict]:
        """
        Screen for quality dividend stocks.
        
        Args:
            stocks: List of stock data dicts
            min_yield: Minimum dividend yield %
            min_consecutive_years: Minimum consecutive dividend years
            
        Returns:
            Filtered list of dividend stocks
        """
        results = []
        
        for stock in stocks:
            dividend_yield = stock.get("dividend_yield", 0)
            consecutive_years = stock.get("consecutive_dividend_years", 0)
            
            if dividend_yield >= min_yield and consecutive_years >= min_consecutive_years:
                results.append(stock)
        
        # Sort by yield
        results.sort(key=lambda x: x.get("dividend_yield", 0), reverse=True)
        
        return results
    
    def estimate_dividend_date(
        self,
        sector: str,
        fiscal_year_end: str = "Ashad",  # Mid-July
    ) -> Dict[str, str]:
        """
        Estimate typical dividend announcement dates by sector.
        
        NEPSE sectors have typical AGM patterns:
        - Banks: Usually August-September
        - Insurance: August-October
        - Finance: August-September
        - Manufacturing: Varies
        """
        # Typical AGM months after fiscal year end (Ashad = mid-July)
        sector_patterns = {
            "Commercial Banks": "August-September",
            "Development Banks": "August-September",
            "Finance": "August-September",
            "Life Insurance": "September-October",
            "Non Life Insurance": "September-October",
            "Microfinance": "August-September",
            "Hydro Power": "September-November",
            "Manufacturing And Processing": "October-December",
            "Hotels And Tourism": "September-November",
            "Investment": "August-September",
            "Others": "September-December",
        }
        
        typical_period = sector_patterns.get(sector, "September-December")
        
        return {
            "sector": sector,
            "fiscal_year_end": fiscal_year_end,
            "typical_agm_period": typical_period,
            "book_closure_usually": "1-2 weeks before AGM",
            "dividend_payment": "Usually within 1 month of AGM",
        }
    
    def get_dividend_investment_strategy(
        self,
        symbol: str,
        fundamentals: Dict,
    ) -> Dict[str, Any]:
        """
        Generate dividend investment strategy.
        
        Args:
            symbol: Stock symbol
            fundamentals: Fundamental data dict
            
        Returns:
            Strategy recommendations
        """
        dividend_yield = fundamentals.get("dividend_yield", 0)
        pe_ratio = fundamentals.get("pe_ratio", 0)
        roe = fundamentals.get("roe", 0)
        
        strategy = {
            "symbol": symbol,
            "dividend_yield": dividend_yield,
        }
        
        # Evaluate dividend quality
        if dividend_yield >= 5 and pe_ratio < 20 and roe > 12:
            strategy["quality"] = "HIGH"
            strategy["action"] = "ACCUMULATE"
            strategy["reason"] = "High yield, reasonable valuation, good profitability"
        elif dividend_yield >= 3 and pe_ratio < 25:
            strategy["quality"] = "MODERATE"
            strategy["action"] = "HOLD"
            strategy["reason"] = "Decent yield, acceptable valuation"
        else:
            strategy["quality"] = "LOW"
            strategy["action"] = "AVOID"
            strategy["reason"] = "Low yield or overvalued"
        
        # Timing suggestions
        strategy["timing_tips"] = [
            "Buy 3-4 months before expected AGM for dividend play",
            "Watch for book closure announcements",
            "Consider selling before ex-dividend if price has run up significantly",
            "Reinvest dividends for compounding effect",
        ]
        
        return strategy


# Helper functions

def calculate_dividend_yield(dividend_pct: float, price: float, face_value: float = 100) -> float:
    """Quick dividend yield calculation."""
    if price <= 0:
        return 0
    return (face_value * dividend_pct / 100) / price * 100


def adjust_price_for_bonus(price: float, bonus_pct: float) -> float:
    """Quick bonus adjustment."""
    return price * (100 / (100 + bonus_pct))


def estimate_terp(current_price: float, right_pct: float, right_price: float) -> float:
    """Calculate Theoretical Ex-Right Price."""
    return (current_price * 100 + right_price * right_pct) / (100 + right_pct)
