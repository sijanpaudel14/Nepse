"""
Dividend Forecaster - Predict future dividends based on EPS and historical patterns.

Analyzes:
- Historical payout ratios
- EPS trends
- Sector dividend patterns
- AGM timing estimates

Usage:
    forecaster = DividendForecaster()
    
    # Get dividend forecast for a stock
    forecast = forecaster.forecast_dividend("NABIL")
    
    # Get high-yield opportunities
    opportunities = forecaster.find_high_yield_stocks()
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Any
from loguru import logger

try:
    from data.sharehub_api import ShareHubAPI, DividendRecord
    from data.fetcher import NepseFetcher
except ImportError:
    ShareHubAPI = None
    DividendRecord = None
    NepseFetcher = None


@dataclass
class DividendMetrics:
    """Historical dividend metrics for a stock."""
    symbol: str
    sector: str = ""
    
    # Historical
    avg_cash_pct: float = 0.0  # Average cash dividend %
    avg_bonus_pct: float = 0.0  # Average bonus %
    avg_total_pct: float = 0.0  # Average total dividend
    payout_ratio: float = 0.0  # Dividend / EPS
    consistency: int = 0  # Consecutive years of dividend
    
    # Current fundamentals
    current_eps: float = 0.0
    current_price: float = 0.0
    current_yield: float = 0.0
    
    # History
    history: List[Dict] = field(default_factory=list)


@dataclass
class DividendForecast:
    """Dividend forecast for upcoming year."""
    symbol: str
    timestamp: datetime
    
    # Forecast
    predicted_cash_pct: float = 0.0
    predicted_bonus_pct: float = 0.0
    predicted_total_pct: float = 0.0
    
    # Confidence
    confidence: str = "LOW"  # LOW, MEDIUM, HIGH
    confidence_score: float = 0.0
    
    # Yield calculation
    forecast_yield: float = 0.0
    forecast_dividend_rs: float = 0.0
    
    # Timing
    expected_agm_period: str = ""
    expected_book_closure: str = ""
    
    # Metrics
    metrics: DividendMetrics = None
    
    # Factors
    factors: List[str] = field(default_factory=list)


class DividendForecaster:
    """
    Forecasts future dividends based on historical data and EPS.
    
    Methodology:
    1. Analyze 3-5 year dividend history
    2. Calculate average payout ratio
    3. Apply payout ratio to current EPS
    4. Adjust for sector patterns
    
    NEPSE dividend patterns:
    - Banks: 15-30% cash + 10-20% bonus
    - Insurance: 10-25% cash + 5-15% bonus
    - Hydro: 0-15% cash (depends on production)
    - Microfinance: 10-20% cash + 5-10% bonus
    """
    
    # Sector-specific payout patterns (historical averages)
    SECTOR_PATTERNS = {
        "Commercial Banks": {"cash": 20, "bonus": 12, "consistency": 0.9},
        "Development Banks": {"cash": 15, "bonus": 10, "consistency": 0.8},
        "Finance": {"cash": 12, "bonus": 8, "consistency": 0.7},
        "Life Insurance": {"cash": 15, "bonus": 10, "consistency": 0.8},
        "Non Life Insurance": {"cash": 18, "bonus": 8, "consistency": 0.7},
        "Hydro Power": {"cash": 8, "bonus": 5, "consistency": 0.5},
        "Microfinance": {"cash": 15, "bonus": 8, "consistency": 0.7},
        "Hotels And Tourism": {"cash": 5, "bonus": 3, "consistency": 0.4},
        "Manufacturing And Processing": {"cash": 10, "bonus": 5, "consistency": 0.5},
    }
    
    # AGM timing by sector (months after fiscal year end)
    AGM_TIMING = {
        "Commercial Banks": "August-September",
        "Development Banks": "August-September",
        "Finance": "August-September",
        "Life Insurance": "September-October",
        "Non Life Insurance": "September-October",
        "Microfinance": "August-September",
        "Hydro Power": "September-November",
        "Hotels And Tourism": "September-November",
    }
    
    def __init__(self):
        """Initialize forecaster."""
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
    
    def get_dividend_metrics(self, symbol: str) -> DividendMetrics:
        """
        Get historical dividend metrics for a stock.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            DividendMetrics with historical analysis
        """
        symbol = symbol.upper()
        metrics = DividendMetrics(
            symbol=symbol,
            sector=self._get_stock_sector(symbol),
        )
        
        if not self.sharehub:
            return metrics
        
        try:
            # Get dividend history
            dividends = self.sharehub.get_dividend_history(symbol, limit=10)
            
            if dividends:
                cash_pcts = []
                bonus_pcts = []
                total_pcts = []
                
                for div in dividends:
                    cash_pcts.append(div.cash_pct)
                    bonus_pcts.append(div.bonus_pct)
                    total_pcts.append(div.total_pct)
                    
                    metrics.history.append({
                        "fiscal_year": div.fiscal_year,
                        "cash_pct": div.cash_pct,
                        "bonus_pct": div.bonus_pct,
                        "total_pct": div.total_pct,
                    })
                
                metrics.avg_cash_pct = sum(cash_pcts) / len(cash_pcts) if cash_pcts else 0
                metrics.avg_bonus_pct = sum(bonus_pcts) / len(bonus_pcts) if bonus_pcts else 0
                metrics.avg_total_pct = sum(total_pcts) / len(total_pcts) if total_pcts else 0
                
                # Consistency: how many years had dividends
                metrics.consistency = sum(1 for t in total_pcts if t > 0)
            
            # Get fundamentals for EPS
            fundamentals = self.sharehub.get_fundamentals(symbol)
            if fundamentals:
                metrics.current_eps = fundamentals.eps_annualized or fundamentals.eps
            
            # Get current price
            if self.fetcher:
                df = self.fetcher.safe_fetch_data(symbol, days=5)
                if not df.empty:
                    metrics.current_price = df['close'].iloc[-1]
            
            # Calculate current yield
            if metrics.current_price > 0 and metrics.avg_total_pct > 0:
                # Dividend is % of face value (Rs.100), yield is % of market price
                dividend_rs = metrics.avg_total_pct  # Rs. per share (% of Rs.100)
                metrics.current_yield = (dividend_rs / metrics.current_price) * 100
            
            # Calculate payout ratio
            if metrics.current_eps > 0 and metrics.avg_cash_pct > 0:
                metrics.payout_ratio = (metrics.avg_cash_pct / metrics.current_eps) * 100
            
        except Exception as e:
            logger.error(f"Failed to get dividend metrics for {symbol}: {e}")
        
        return metrics
    
    def forecast_dividend(self, symbol: str) -> DividendForecast:
        """
        Forecast next dividend for a stock.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            DividendForecast with prediction
        """
        symbol = symbol.upper()
        forecast = DividendForecast(symbol=symbol, timestamp=datetime.now())
        
        # Get historical metrics
        metrics = self.get_dividend_metrics(symbol)
        forecast.metrics = metrics
        
        if not metrics.history:
            forecast.factors.append("No dividend history available")
            forecast.confidence = "LOW"
            forecast.confidence_score = 20
            
            # Use sector average as fallback
            sector_pattern = self.SECTOR_PATTERNS.get(metrics.sector, {})
            if sector_pattern:
                forecast.predicted_cash_pct = sector_pattern.get("cash", 0)
                forecast.predicted_bonus_pct = sector_pattern.get("bonus", 0)
                forecast.factors.append(f"Using {metrics.sector} sector average")
            
            return forecast
        
        try:
            # Base prediction on historical average
            forecast.predicted_cash_pct = metrics.avg_cash_pct
            forecast.predicted_bonus_pct = metrics.avg_bonus_pct
            forecast.factors.append(f"Based on {len(metrics.history)}-year average")
            
            # Adjust for EPS trend
            if metrics.current_eps > 0:
                # If EPS is higher than historical, might see higher dividend
                sector_pattern = self.SECTOR_PATTERNS.get(metrics.sector, {})
                typical_payout = sector_pattern.get("cash", 15) + sector_pattern.get("bonus", 10)
                
                if metrics.current_eps > typical_payout:
                    # EPS can support higher dividend
                    eps_factor = min(1.2, metrics.current_eps / typical_payout)
                    forecast.predicted_cash_pct *= eps_factor
                    forecast.factors.append(f"EPS ({metrics.current_eps:.1f}) supports higher dividend")
            
            # Adjust for consistency
            if metrics.consistency >= 5:
                forecast.confidence_score += 30
                forecast.factors.append("Strong dividend consistency (5+ years)")
            elif metrics.consistency >= 3:
                forecast.confidence_score += 20
                forecast.factors.append("Good dividend consistency (3+ years)")
            else:
                forecast.confidence_score += 10
                forecast.factors.append("Limited dividend history")
            
            # Adjust for sector
            sector_pattern = self.SECTOR_PATTERNS.get(metrics.sector, {})
            if sector_pattern:
                sector_consistency = sector_pattern.get("consistency", 0.5)
                forecast.confidence_score += sector_consistency * 30
            
            # Total prediction
            forecast.predicted_total_pct = forecast.predicted_cash_pct + forecast.predicted_bonus_pct
            
            # Calculate yield forecast
            if metrics.current_price > 0:
                forecast.forecast_dividend_rs = forecast.predicted_cash_pct  # Rs. per share
                forecast.forecast_yield = (forecast.forecast_dividend_rs / metrics.current_price) * 100
            
            # Confidence level
            if forecast.confidence_score >= 70:
                forecast.confidence = "HIGH"
            elif forecast.confidence_score >= 45:
                forecast.confidence = "MEDIUM"
            else:
                forecast.confidence = "LOW"
            
            # AGM timing
            forecast.expected_agm_period = self.AGM_TIMING.get(
                metrics.sector,
                "September-November"
            )
            forecast.expected_book_closure = f"1-2 weeks before AGM ({forecast.expected_agm_period})"
            
        except Exception as e:
            logger.error(f"Failed to forecast dividend for {symbol}: {e}")
        
        return forecast
    
    def find_high_yield_stocks(self, min_yield: float = 4.0, limit: int = 20) -> List[DividendForecast]:
        """
        Find stocks with high dividend yield potential.
        
        Args:
            min_yield: Minimum yield threshold (%)
            limit: Maximum results
            
        Returns:
            List of DividendForecast sorted by yield
        """
        results = []
        
        if not self.fetcher:
            return results
        
        try:
            # Get all companies
            companies = self.fetcher.fetch_company_list()
            
            # Check dividend-paying sectors
            dividend_sectors = list(self.SECTOR_PATTERNS.keys())
            
            for company in companies[:100]:  # Limit to avoid rate limiting
                if company.sector not in dividend_sectors:
                    continue
                
                forecast = self.forecast_dividend(company.symbol)
                
                if forecast.forecast_yield >= min_yield:
                    results.append(forecast)
            
            # Sort by yield
            results.sort(key=lambda x: x.forecast_yield, reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to find high yield stocks: {e}")
        
        return results[:limit]
    
    def format_report(self, forecast: DividendForecast) -> str:
        """Format dividend forecast for CLI output."""
        lines = []
        
        lines.append("=" * 60)
        lines.append(f"💰 DIVIDEND FORECAST: {forecast.symbol}")
        lines.append("=" * 60)
        lines.append("")
        
        if forecast.metrics:
            m = forecast.metrics
            
            # Current fundamentals
            lines.append("📊 CURRENT FUNDAMENTALS")
            lines.append("-" * 50)
            lines.append(f"Sector:        {m.sector}")
            lines.append(f"Current Price: Rs.{m.current_price:,.2f}")
            lines.append(f"Current EPS:   Rs.{m.current_eps:.2f}")
            lines.append(f"Current Yield: {m.current_yield:.1f}%")
            lines.append("")
            
            # Historical dividends
            if m.history:
                lines.append("📜 DIVIDEND HISTORY")
                lines.append("-" * 50)
                lines.append(f"{'Year':<12} {'Cash%':<10} {'Bonus%':<10} {'Total%'}")
                lines.append("-" * 50)
                
                for h in m.history[:5]:
                    lines.append(
                        f"{h['fiscal_year']:<12} "
                        f"{h['cash_pct']:>7.1f}% "
                        f"{h['bonus_pct']:>8.1f}% "
                        f"{h['total_pct']:>7.1f}%"
                    )
                
                lines.append("")
                lines.append(f"Average Total: {m.avg_total_pct:.1f}%")
                lines.append(f"Consistency:   {m.consistency} years")
                lines.append("")
        
        # Forecast
        lines.append("🔮 FORECAST (Next Year)")
        lines.append("-" * 50)
        lines.append(f"Predicted Cash Dividend:  {forecast.predicted_cash_pct:.1f}%")
        lines.append(f"Predicted Bonus:          {forecast.predicted_bonus_pct:.1f}%")
        lines.append(f"Predicted Total:          {forecast.predicted_total_pct:.1f}%")
        lines.append("")
        
        if forecast.metrics and forecast.metrics.current_price > 0:
            lines.append(f"Forecast Dividend:        Rs.{forecast.forecast_dividend_rs:.1f} per share")
            lines.append(f"Forecast Yield:           {forecast.forecast_yield:.2f}%")
        
        lines.append("")
        lines.append(f"Confidence:               {forecast.confidence} ({forecast.confidence_score:.0f}%)")
        lines.append("")
        
        # Timing
        lines.append("📅 EXPECTED TIMING")
        lines.append("-" * 50)
        lines.append(f"AGM Period:      {forecast.expected_agm_period}")
        lines.append(f"Book Closure:    {forecast.expected_book_closure}")
        lines.append("")
        
        # Factors
        if forecast.factors:
            lines.append("📋 FORECAST FACTORS")
            lines.append("-" * 50)
            for factor in forecast.factors:
                lines.append(f"  • {factor}")
            lines.append("")
        
        # Trading guidance
        lines.append("💡 DIVIDEND STRATEGY")
        lines.append("-" * 50)
        
        if forecast.forecast_yield >= 5:
            lines.append("  🟢 HIGH YIELD OPPORTUNITY")
            lines.append(f"     Yield ({forecast.forecast_yield:.1f}%) exceeds typical FD rates (6-7%)")
        elif forecast.forecast_yield >= 3:
            lines.append("  🟡 MODERATE YIELD")
            lines.append("     Consider for dividend + growth strategy")
        else:
            lines.append("  ⚪ LOW YIELD")
            lines.append("     Better suited for capital appreciation")
        
        if forecast.confidence == "HIGH":
            lines.append("  ✅ High confidence in forecast")
        elif forecast.confidence == "MEDIUM":
            lines.append("  ⚠️ Medium confidence - verify with company announcements")
        else:
            lines.append("  ❌ Low confidence - dividend uncertain")
        
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Convenience functions
def get_dividend_forecast(symbol: str) -> str:
    """Get formatted dividend forecast."""
    forecaster = DividendForecaster()
    forecast = forecaster.forecast_dividend(symbol)
    return forecaster.format_report(forecast)


def get_high_yield_stocks(min_yield: float = 4.0) -> List[str]:
    """Get high yield stock symbols."""
    forecaster = DividendForecaster()
    stocks = forecaster.find_high_yield_stocks(min_yield=min_yield)
    return [s.symbol for s in stocks]
