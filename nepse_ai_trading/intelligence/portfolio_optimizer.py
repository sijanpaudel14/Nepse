"""
Portfolio Optimizer - Risk-adjusted portfolio construction.

Uses Modern Portfolio Theory concepts to:
- Calculate correlation matrix between stocks
- Optimize weights for maximum Sharpe ratio
- Suggest diversified allocation

Usage:
    optimizer = PortfolioOptimizer()
    
    # Optimize a list of stocks
    result = optimizer.optimize(["GVL", "PPCL", "NABIL"])
    
    # Get correlation matrix
    corr = optimizer.get_correlation_matrix(["GVL", "PPCL", "NABIL"])
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from loguru import logger
import pandas as pd
import numpy as np

try:
    from data.fetcher import NepseFetcher
except ImportError:
    NepseFetcher = None


@dataclass
class StockMetrics:
    """Risk/return metrics for a stock."""
    symbol: str
    sector: str = ""
    expected_return: float = 0.0  # Annual %
    volatility: float = 0.0  # Annual std dev
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    current_price: float = 0.0


@dataclass
class PortfolioWeights:
    """Optimized portfolio weights."""
    weights: Dict[str, float] = field(default_factory=dict)  # symbol -> weight
    expected_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    
    @property
    def total_weight(self) -> float:
        return sum(self.weights.values())


@dataclass
class OptimizationResult:
    """Complete optimization result."""
    symbols: List[str]
    timestamp: datetime
    
    # Individual metrics
    stock_metrics: Dict[str, StockMetrics] = field(default_factory=dict)
    
    # Correlation
    correlation_matrix: pd.DataFrame = None
    
    # Optimal weights
    optimal_weights: PortfolioWeights = None
    
    # Diversification
    sector_breakdown: Dict[str, float] = field(default_factory=dict)
    diversification_score: float = 0.0  # 0-100
    
    # Warnings
    warnings: List[str] = field(default_factory=list)


class PortfolioOptimizer:
    """
    Optimizes portfolio allocation using Modern Portfolio Theory.
    
    Objectives:
    1. Maximize Sharpe ratio (risk-adjusted return)
    2. Minimize correlation between holdings
    3. Diversify across sectors
    
    NEPSE-specific considerations:
    - Limited historical data
    - High correlation within sectors
    - Illiquidity issues for small caps
    """
    
    # Risk-free rate (Nepal Treasury Bill rate approximation)
    RISK_FREE_RATE = 0.06  # 6% annual
    
    # Trading days per year (NEPSE)
    TRADING_DAYS = 234
    
    # Constraints
    MIN_WEIGHT = 0.05  # 5% minimum per stock
    MAX_WEIGHT = 0.40  # 40% maximum per stock
    MAX_SECTOR_WEIGHT = 0.50  # 50% max per sector
    MAX_CORRELATION = 0.85  # Warn if correlation > 85%
    
    def __init__(self):
        """Initialize optimizer."""
        self.fetcher = NepseFetcher() if NepseFetcher else None
        self._sector_cache: Dict[str, str] = {}
    
    def _fetch_price_data(self, symbol: str, days: int = 180) -> pd.DataFrame:
        """Fetch price data."""
        if not self.fetcher:
            return pd.DataFrame()
        
        try:
            return self.fetcher.safe_fetch_data(symbol, days=days)
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return pd.DataFrame()
    
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
    
    def _calculate_returns(self, df: pd.DataFrame) -> pd.Series:
        """Calculate daily returns."""
        if df.empty or 'close' not in df.columns:
            return pd.Series()
        
        return df['close'].pct_change().dropna()
    
    def calculate_stock_metrics(self, symbol: str) -> StockMetrics:
        """
        Calculate risk/return metrics for a single stock.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            StockMetrics with all metrics
        """
        symbol = symbol.upper()
        metrics = StockMetrics(
            symbol=symbol,
            sector=self._get_stock_sector(symbol),
        )
        
        df = self._fetch_price_data(symbol)
        if df.empty or len(df) < 30:
            return metrics
        
        try:
            returns = self._calculate_returns(df)
            if returns.empty:
                return metrics
            
            # Current price
            metrics.current_price = df['close'].iloc[-1]
            
            # Annual expected return (extrapolated from historical)
            daily_return = returns.mean()
            metrics.expected_return = daily_return * self.TRADING_DAYS * 100  # %
            
            # Annual volatility
            daily_vol = returns.std()
            metrics.volatility = daily_vol * np.sqrt(self.TRADING_DAYS) * 100  # %
            
            # Sharpe ratio
            if metrics.volatility > 0:
                excess_return = metrics.expected_return - self.RISK_FREE_RATE * 100
                metrics.sharpe_ratio = excess_return / metrics.volatility
            
            # Max drawdown
            cumulative = (1 + returns).cumprod()
            rolling_max = cumulative.expanding().max()
            drawdowns = (cumulative - rolling_max) / rolling_max
            metrics.max_drawdown = drawdowns.min() * 100  # %
            
        except Exception as e:
            logger.error(f"Failed to calculate metrics for {symbol}: {e}")
        
        return metrics
    
    def get_correlation_matrix(self, symbols: List[str]) -> pd.DataFrame:
        """
        Calculate correlation matrix between stocks.
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            DataFrame with correlation matrix
        """
        symbols = [s.upper() for s in symbols]
        returns_data = {}
        
        for symbol in symbols:
            df = self._fetch_price_data(symbol)
            if not df.empty:
                returns = self._calculate_returns(df)
                if not returns.empty:
                    returns_data[symbol] = returns
        
        if len(returns_data) < 2:
            return pd.DataFrame()
        
        # Align dates and calculate correlation
        returns_df = pd.DataFrame(returns_data)
        returns_df = returns_df.dropna()
        
        if len(returns_df) < 10:
            return pd.DataFrame()
        
        return returns_df.corr()
    
    def _calculate_portfolio_metrics(
        self,
        weights: np.ndarray,
        returns: pd.DataFrame,
        cov_matrix: pd.DataFrame
    ) -> Tuple[float, float, float]:
        """
        Calculate portfolio return, volatility, and Sharpe ratio.
        
        Args:
            weights: Array of portfolio weights
            returns: DataFrame of individual stock returns
            cov_matrix: Covariance matrix
            
        Returns:
            Tuple of (expected_return, volatility, sharpe_ratio)
        """
        # Expected return
        mean_returns = returns.mean() * self.TRADING_DAYS
        portfolio_return = np.dot(weights, mean_returns)
        
        # Volatility
        portfolio_variance = np.dot(weights.T, np.dot(cov_matrix * self.TRADING_DAYS, weights))
        portfolio_vol = np.sqrt(portfolio_variance)
        
        # Sharpe ratio
        sharpe = (portfolio_return - self.RISK_FREE_RATE) / portfolio_vol if portfolio_vol > 0 else 0
        
        return portfolio_return * 100, portfolio_vol * 100, sharpe
    
    def _optimize_weights(
        self,
        returns_df: pd.DataFrame,
        sectors: Dict[str, str]
    ) -> PortfolioWeights:
        """
        Find optimal weights using simplified optimization.
        
        Since scipy.optimize may not be available, use a grid search approach.
        """
        n_stocks = len(returns_df.columns)
        symbols = list(returns_df.columns)
        
        if n_stocks == 0:
            return PortfolioWeights()
        
        if n_stocks == 1:
            return PortfolioWeights(
                weights={symbols[0]: 1.0},
                expected_return=returns_df.mean().iloc[0] * self.TRADING_DAYS * 100,
                volatility=returns_df.std().iloc[0] * np.sqrt(self.TRADING_DAYS) * 100,
            )
        
        cov_matrix = returns_df.cov()
        
        best_sharpe = -np.inf
        best_weights = None
        best_return = 0
        best_vol = 0
        
        # Grid search for optimal weights
        # For small portfolios, try many combinations
        if n_stocks == 2:
            for w1 in np.arange(self.MIN_WEIGHT, 1 - self.MIN_WEIGHT, 0.05):
                w2 = 1 - w1
                if w2 < self.MIN_WEIGHT or w2 > self.MAX_WEIGHT or w1 > self.MAX_WEIGHT:
                    continue
                
                weights = np.array([w1, w2])
                ret, vol, sharpe = self._calculate_portfolio_metrics(weights, returns_df, cov_matrix)
                
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_weights = weights
                    best_return = ret
                    best_vol = vol
        
        elif n_stocks == 3:
            for w1 in np.arange(self.MIN_WEIGHT, 0.8, 0.1):
                for w2 in np.arange(self.MIN_WEIGHT, 0.8 - w1, 0.1):
                    w3 = 1 - w1 - w2
                    if w3 < self.MIN_WEIGHT or max(w1, w2, w3) > self.MAX_WEIGHT:
                        continue
                    
                    weights = np.array([w1, w2, w3])
                    ret, vol, sharpe = self._calculate_portfolio_metrics(weights, returns_df, cov_matrix)
                    
                    if sharpe > best_sharpe:
                        best_sharpe = sharpe
                        best_weights = weights
                        best_return = ret
                        best_vol = vol
        
        else:
            # For larger portfolios, use equal weight as baseline
            equal_weight = 1.0 / n_stocks
            best_weights = np.array([equal_weight] * n_stocks)
            best_return, best_vol, best_sharpe = self._calculate_portfolio_metrics(
                best_weights, returns_df, cov_matrix
            )
            
            # Try inverse volatility weighting
            vols = returns_df.std()
            inv_vols = 1 / vols
            inv_vol_weights = inv_vols / inv_vols.sum()
            inv_vol_weights = inv_vol_weights.values
            
            ret, vol, sharpe = self._calculate_portfolio_metrics(inv_vol_weights, returns_df, cov_matrix)
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_weights = inv_vol_weights
                best_return = ret
                best_vol = vol
        
        result = PortfolioWeights(
            expected_return=best_return,
            volatility=best_vol,
            sharpe_ratio=best_sharpe,
        )
        
        if best_weights is not None:
            for i, symbol in enumerate(symbols):
                result.weights[symbol] = float(best_weights[i])
        
        return result
    
    def optimize(self, symbols: List[str]) -> OptimizationResult:
        """
        Optimize portfolio allocation.
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            OptimizationResult with optimal weights and analysis
        """
        symbols = [s.upper() for s in symbols]
        result = OptimizationResult(symbols=symbols, timestamp=datetime.now())
        
        if len(symbols) == 0:
            result.warnings.append("No symbols provided")
            return result
        
        # Calculate individual metrics
        returns_data = {}
        sectors = {}
        
        for symbol in symbols:
            metrics = self.calculate_stock_metrics(symbol)
            result.stock_metrics[symbol] = metrics
            sectors[symbol] = metrics.sector
            
            df = self._fetch_price_data(symbol)
            if not df.empty:
                returns = self._calculate_returns(df)
                if not returns.empty:
                    returns_data[symbol] = returns
        
        if len(returns_data) < len(symbols):
            missing = set(symbols) - set(returns_data.keys())
            result.warnings.append(f"Missing data for: {', '.join(missing)}")
        
        if len(returns_data) == 0:
            result.warnings.append("No valid data available for optimization")
            return result
        
        # Build returns DataFrame
        returns_df = pd.DataFrame(returns_data).dropna()
        
        if len(returns_df) < 10:
            result.warnings.append("Insufficient overlapping data for optimization")
            return result
        
        # Correlation matrix
        result.correlation_matrix = returns_df.corr()
        
        # Check for high correlations
        for i, s1 in enumerate(returns_df.columns):
            for j, s2 in enumerate(returns_df.columns):
                if i < j:
                    corr = result.correlation_matrix.loc[s1, s2]
                    if corr > self.MAX_CORRELATION:
                        result.warnings.append(
                            f"High correlation ({corr:.2f}) between {s1} and {s2}"
                        )
        
        # Optimize weights
        result.optimal_weights = self._optimize_weights(returns_df, sectors)
        
        # Sector breakdown
        for symbol, weight in result.optimal_weights.weights.items():
            sector = sectors.get(symbol, "Unknown")
            result.sector_breakdown[sector] = result.sector_breakdown.get(sector, 0) + weight
        
        # Check sector concentration
        for sector, weight in result.sector_breakdown.items():
            if weight > self.MAX_SECTOR_WEIGHT:
                result.warnings.append(
                    f"High sector concentration: {sector} = {weight*100:.0f}%"
                )
        
        # Diversification score
        n = len(result.optimal_weights.weights)
        if n > 0:
            # Higher = more diversified
            weights_array = np.array(list(result.optimal_weights.weights.values()))
            # HHI-based score (lower HHI = more diversified)
            hhi = np.sum(weights_array ** 2)
            result.diversification_score = (1 - hhi) * 100
        
        return result
    
    def format_report(self, result: OptimizationResult) -> str:
        """Format optimization result for CLI output."""
        lines = []
        
        lines.append("=" * 60)
        lines.append(f"📊 PORTFOLIO OPTIMIZATION")
        lines.append("=" * 60)
        lines.append("")
        
        # Individual stock metrics
        if result.stock_metrics:
            lines.append("📈 INDIVIDUAL STOCK METRICS")
            lines.append("-" * 50)
            lines.append(f"{'Symbol':<10} {'Return%':<10} {'Vol%':<10} {'Sharpe':<10} {'Sector'}")
            lines.append("-" * 50)
            
            for symbol, m in result.stock_metrics.items():
                lines.append(
                    f"{symbol:<10} {m.expected_return:>+7.1f}% "
                    f"{m.volatility:>7.1f}% "
                    f"{m.sharpe_ratio:>7.2f} "
                    f"{m.sector[:15]}"
                )
            lines.append("")
        
        # Correlation matrix
        if result.correlation_matrix is not None and not result.correlation_matrix.empty:
            lines.append("🔗 CORRELATION MATRIX")
            lines.append("-" * 50)
            
            symbols = list(result.correlation_matrix.columns)
            header = "      " + " ".join(f"{s[:6]:>7}" for s in symbols)
            lines.append(header)
            
            for s1 in symbols:
                row = f"{s1[:6]:<6}"
                for s2 in symbols:
                    corr = result.correlation_matrix.loc[s1, s2]
                    row += f" {corr:>6.2f}"
                lines.append(row)
            lines.append("")
        
        # Optimal weights
        if result.optimal_weights and result.optimal_weights.weights:
            lines.append("⚖️ OPTIMAL ALLOCATION")
            lines.append("-" * 50)
            
            sorted_weights = sorted(
                result.optimal_weights.weights.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            for symbol, weight in sorted_weights:
                bar = "█" * int(weight * 20)
                lines.append(f"  {symbol:<10} {weight*100:>5.1f}% {bar}")
            
            lines.append("")
            lines.append(f"Expected Return: {result.optimal_weights.expected_return:+.1f}%")
            lines.append(f"Volatility:      {result.optimal_weights.volatility:.1f}%")
            lines.append(f"Sharpe Ratio:    {result.optimal_weights.sharpe_ratio:.2f}")
            lines.append("")
        
        # Sector breakdown
        if result.sector_breakdown:
            lines.append("📊 SECTOR BREAKDOWN")
            lines.append("-" * 50)
            
            for sector, weight in sorted(result.sector_breakdown.items(), key=lambda x: x[1], reverse=True):
                bar = "█" * int(weight * 20)
                lines.append(f"  {sector[:20]:<20} {weight*100:>5.1f}% {bar}")
            lines.append("")
        
        # Diversification
        lines.append(f"🎯 Diversification Score: {result.diversification_score:.0f}/100")
        lines.append("")
        
        # Warnings
        if result.warnings:
            lines.append("⚠️ WARNINGS")
            lines.append("-" * 50)
            for warning in result.warnings:
                lines.append(f"  • {warning}")
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# Convenience functions
def optimize_portfolio(symbols: List[str]) -> str:
    """Get formatted portfolio optimization."""
    optimizer = PortfolioOptimizer()
    result = optimizer.optimize(symbols)
    return optimizer.format_report(result)


def get_correlation(symbols: List[str]) -> pd.DataFrame:
    """Get correlation matrix for stocks."""
    optimizer = PortfolioOptimizer()
    return optimizer.get_correlation_matrix(symbols)
