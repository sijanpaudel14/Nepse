"""
Backtesting Performance Metrics Calculator.

Calculates professional-grade trading metrics:
- Total Return, CAGR
- Sharpe Ratio, Sortino Ratio
- Maximum Drawdown, Recovery Time
- Win Rate, Profit Factor, Expectancy

These metrics help evaluate if a strategy is worth trading with real money.

IMPORTANT FOR NEPSE:
- Risk-free rate: Use Nepal Rastra Bank's repo rate (~6.5% as of 2024)
- Trading days: ~200 days/year (NEPSE is closed Fri-Sat, plus holidays)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import date, timedelta


# Nepal's ~6.5% risk-free rate (NRB repo rate)
NEPAL_RISK_FREE_RATE = 0.065

# NEPSE trading days per year (~200, accounting for weekends + holidays)
NEPSE_TRADING_DAYS_PER_YEAR = 200


@dataclass
class TradeResult:
    """Represents a single completed trade."""
    symbol: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    shares: int
    side: str = "LONG"  # NEPSE doesn't allow shorting
    
    @property
    def holding_days(self) -> int:
        return (self.exit_date - self.entry_date).days
    
    @property
    def gross_pnl(self) -> float:
        """P&L before costs."""
        return (self.exit_price - self.entry_price) * self.shares
    
    @property
    def gross_return_pct(self) -> float:
        """Percentage return before costs."""
        return (self.exit_price - self.entry_price) / self.entry_price * 100
    
    @property
    def capital_used(self) -> float:
        return self.entry_price * self.shares


@dataclass
class BacktestMetrics:
    """
    Comprehensive backtesting performance metrics.
    
    Use these to evaluate strategy quality before risking real capital.
    """
    
    # Basic Returns
    total_return_pct: float = 0.0       # Total percentage return
    cagr: float = 0.0                   # Compound Annual Growth Rate
    
    # Risk-Adjusted Returns
    sharpe_ratio: float = 0.0           # Risk-adjusted return (>1 is good, >2 excellent)
    sortino_ratio: float = 0.0          # Like Sharpe, but only penalizes downside
    calmar_ratio: float = 0.0           # CAGR / Max Drawdown
    
    # Drawdown Analysis
    max_drawdown_pct: float = 0.0       # Largest peak-to-trough drop
    max_drawdown_duration: int = 0      # Days to recover from max drawdown
    avg_drawdown_pct: float = 0.0       # Average drawdown
    
    # Trade Statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0               # % of trades that are profitable
    
    # P&L Analysis
    gross_profit: float = 0.0           # Total profit from winners
    gross_loss: float = 0.0             # Total loss from losers (positive number)
    net_profit: float = 0.0             # Gross profit - Gross loss - Costs
    
    # Trade Metrics
    profit_factor: float = 0.0          # Gross Profit / Gross Loss (>1.5 good)
    expectancy: float = 0.0             # Average $ expected per trade
    avg_win: float = 0.0                # Average winning trade
    avg_loss: float = 0.0               # Average losing trade
    avg_win_loss_ratio: float = 0.0     # Avg Win / Avg Loss (>2 good)
    
    # Timing
    avg_holding_days: float = 0.0       # Average days per trade
    avg_trades_per_month: float = 0.0   # Trading frequency
    
    # Costs
    total_commission: float = 0.0
    total_slippage: float = 0.0
    
    # Period
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    trading_days: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_return_pct": round(self.total_return_pct, 2),
            "cagr": round(self.cagr, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "max_drawdown_duration_days": self.max_drawdown_duration,
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 2),
            "profit_factor": round(self.profit_factor, 2),
            "expectancy": round(self.expectancy, 2),
            "avg_win_loss_ratio": round(self.avg_win_loss_ratio, 2),
            "net_profit": round(self.net_profit, 2),
            "avg_holding_days": round(self.avg_holding_days, 1),
        }
    
    def is_profitable(self) -> bool:
        """Quick check if strategy is profitable."""
        return self.net_profit > 0 and self.total_return_pct > 0
    
    def meets_minimum_standards(self) -> bool:
        """
        Check if strategy meets minimum trading standards.
        
        Requirements:
        - Win rate > 40%
        - Profit factor > 1.2
        - Sharpe ratio > 0.5
        - Max drawdown < 30%
        """
        return (
            self.win_rate > 40 and
            self.profit_factor > 1.2 and
            self.sharpe_ratio > 0.5 and
            self.max_drawdown_pct < 30
        )
    
    def grade(self) -> str:
        """
        Grade the strategy A-F based on metrics.
        
        This gives you a quick sense of strategy quality.
        """
        score = 0
        
        # Win rate scoring
        if self.win_rate >= 60:
            score += 3
        elif self.win_rate >= 50:
            score += 2
        elif self.win_rate >= 40:
            score += 1
        
        # Sharpe scoring
        if self.sharpe_ratio >= 2.0:
            score += 3
        elif self.sharpe_ratio >= 1.0:
            score += 2
        elif self.sharpe_ratio >= 0.5:
            score += 1
        
        # Profit factor scoring
        if self.profit_factor >= 2.0:
            score += 3
        elif self.profit_factor >= 1.5:
            score += 2
        elif self.profit_factor >= 1.2:
            score += 1
        
        # Drawdown scoring (lower is better)
        if self.max_drawdown_pct <= 10:
            score += 3
        elif self.max_drawdown_pct <= 20:
            score += 2
        elif self.max_drawdown_pct <= 30:
            score += 1
        
        # Map score to grade
        if score >= 10:
            return "A"
        elif score >= 8:
            return "B"
        elif score >= 6:
            return "C"
        elif score >= 4:
            return "D"
        else:
            return "F"
    
    def summary(self) -> str:
        """Human-readable summary of metrics."""
        grade = self.grade()
        
        return f"""
╔══════════════════════════════════════════════════════════════╗
║              BACKTEST PERFORMANCE REPORT                     ║
║                    Grade: {grade}                                 ║
╠══════════════════════════════════════════════════════════════╣
║ RETURNS                                                      ║
║   Total Return: {self.total_return_pct:>8.2f}%                              ║
║   CAGR:         {self.cagr:>8.2f}%                              ║
║   Net Profit:   Rs.{self.net_profit:>10,.0f}                       ║
╠══════════════════════════════════════════════════════════════╣
║ RISK-ADJUSTED                                                ║
║   Sharpe Ratio:  {self.sharpe_ratio:>7.2f}  (>1 good, >2 excellent)   ║
║   Sortino Ratio: {self.sortino_ratio:>7.2f}                             ║
║   Max Drawdown:  {self.max_drawdown_pct:>7.2f}%                           ║
╠══════════════════════════════════════════════════════════════╣
║ TRADE STATISTICS                                             ║
║   Total Trades:  {self.total_trades:>7}                              ║
║   Win Rate:      {self.win_rate:>7.1f}%                             ║
║   Profit Factor: {self.profit_factor:>7.2f}  (>1.5 good)               ║
║   Avg Win/Loss:  {self.avg_win_loss_ratio:>7.2f}  (>2 good)                ║
║   Expectancy:    Rs.{self.expectancy:>7,.0f}/trade                   ║
╠══════════════════════════════════════════════════════════════╣
║ TRADING ACTIVITY                                             ║
║   Avg Holding:   {self.avg_holding_days:>7.1f} days                        ║
║   Trades/Month:  {self.avg_trades_per_month:>7.1f}                              ║
╚══════════════════════════════════════════════════════════════╝
"""


class MetricsCalculator:
    """
    Calculates all backtest metrics from trade results and equity curve.
    """
    
    def __init__(
        self,
        initial_capital: float = 500_000,
        risk_free_rate: float = NEPAL_RISK_FREE_RATE,
        trading_days_per_year: int = NEPSE_TRADING_DAYS_PER_YEAR,
    ):
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate
        self.trading_days_per_year = trading_days_per_year
    
    def calculate(
        self,
        trades: List[TradeResult],
        equity_curve: pd.Series,
        total_commission: float = 0,
        total_slippage: float = 0,
    ) -> BacktestMetrics:
        """
        Calculate all metrics from trades and equity curve.
        
        Args:
            trades: List of completed trades
            equity_curve: Daily portfolio values (indexed by date)
            total_commission: Total broker commission paid
            total_slippage: Total estimated slippage cost
            
        Returns:
            BacktestMetrics with all calculated values
        """
        metrics = BacktestMetrics()
        
        if not trades or equity_curve.empty:
            return metrics
        
        # --- Basic Returns ---
        final_equity = equity_curve.iloc[-1]
        metrics.total_return_pct = (
            (final_equity - self.initial_capital) / self.initial_capital * 100
        )
        
        # --- Period Calculation ---
        metrics.start_date = equity_curve.index.min()
        metrics.end_date = equity_curve.index.max()
        metrics.trading_days = len(equity_curve)
        
        # CAGR
        years = metrics.trading_days / self.trading_days_per_year
        if years > 0 and final_equity > 0:
            metrics.cagr = (
                (final_equity / self.initial_capital) ** (1 / years) - 1
            ) * 100
        
        # --- Daily Returns ---
        daily_returns = equity_curve.pct_change().dropna()
        
        if len(daily_returns) > 0:
            # Sharpe Ratio (annualized)
            daily_rf = self.risk_free_rate / self.trading_days_per_year
            excess_returns = daily_returns - daily_rf
            
            if excess_returns.std() > 0:
                metrics.sharpe_ratio = (
                    excess_returns.mean() / excess_returns.std() * 
                    np.sqrt(self.trading_days_per_year)
                )
            
            # Sortino Ratio (only penalizes downside volatility)
            downside_returns = daily_returns[daily_returns < 0]
            if len(downside_returns) > 0 and downside_returns.std() > 0:
                metrics.sortino_ratio = (
                    (daily_returns.mean() - daily_rf) / downside_returns.std() *
                    np.sqrt(self.trading_days_per_year)
                )
        
        # --- Drawdown Analysis ---
        rolling_max = equity_curve.cummax()
        drawdown = (equity_curve - rolling_max) / rolling_max * 100
        
        metrics.max_drawdown_pct = abs(drawdown.min())
        metrics.avg_drawdown_pct = abs(drawdown[drawdown < 0].mean()) if len(drawdown[drawdown < 0]) > 0 else 0
        
        # Max drawdown duration (days to recover)
        metrics.max_drawdown_duration = self._calculate_max_dd_duration(drawdown)
        
        # Calmar Ratio (CAGR / Max Drawdown)
        if metrics.max_drawdown_pct > 0:
            metrics.calmar_ratio = metrics.cagr / metrics.max_drawdown_pct
        
        # --- Trade Statistics ---
        metrics.total_trades = len(trades)
        
        pnls = [t.gross_pnl for t in trades]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p <= 0]
        
        metrics.winning_trades = len(winners)
        metrics.losing_trades = len(losers)
        metrics.win_rate = (len(winners) / len(trades)) * 100 if trades else 0
        
        # P&L
        metrics.gross_profit = sum(winners)
        metrics.gross_loss = abs(sum(losers))
        metrics.net_profit = sum(pnls) - total_commission - total_slippage
        
        metrics.total_commission = total_commission
        metrics.total_slippage = total_slippage
        
        # Averages
        metrics.avg_win = np.mean(winners) if winners else 0
        metrics.avg_loss = abs(np.mean(losers)) if losers else 0
        
        if metrics.avg_loss > 0:
            metrics.avg_win_loss_ratio = metrics.avg_win / metrics.avg_loss
        
        # Profit Factor
        if metrics.gross_loss > 0:
            metrics.profit_factor = metrics.gross_profit / metrics.gross_loss
        elif metrics.gross_profit > 0:
            metrics.profit_factor = float('inf')
        
        # Expectancy (expected $ per trade)
        win_rate_decimal = metrics.win_rate / 100
        metrics.expectancy = (
            (win_rate_decimal * metrics.avg_win) - 
            ((1 - win_rate_decimal) * metrics.avg_loss)
        )
        
        # Holding period
        holding_days = [t.holding_days for t in trades]
        metrics.avg_holding_days = np.mean(holding_days) if holding_days else 0
        
        # Trades per month
        if years > 0:
            metrics.avg_trades_per_month = len(trades) / (years * 12)
        
        return metrics
    
    def _calculate_max_dd_duration(self, drawdown: pd.Series) -> int:
        """Calculate maximum drawdown duration in days."""
        in_drawdown = False
        max_duration = 0
        current_duration = 0
        
        for dd in drawdown:
            if dd < 0:
                if not in_drawdown:
                    in_drawdown = True
                    current_duration = 1
                else:
                    current_duration += 1
            else:
                if in_drawdown:
                    max_duration = max(max_duration, current_duration)
                    in_drawdown = False
                    current_duration = 0
        
        # Handle case where we end in drawdown
        if in_drawdown:
            max_duration = max(max_duration, current_duration)
        
        return max_duration
    
    def calculate_monthly_returns(self, equity_curve: pd.Series) -> pd.DataFrame:
        """
        Calculate monthly return breakdown.
        
        Useful for seeing seasonality and consistency.
        """
        if equity_curve.empty:
            return pd.DataFrame()
        
        # Ensure datetime index
        if not isinstance(equity_curve.index, pd.DatetimeIndex):
            equity_curve.index = pd.to_datetime(equity_curve.index)
        
        # Resample to monthly
        monthly = equity_curve.resample('M').last()
        monthly_returns = monthly.pct_change() * 100
        
        # Create year-month matrix
        df = monthly_returns.to_frame(name='return')
        df['year'] = df.index.year
        df['month'] = df.index.month
        
        pivot = df.pivot_table(values='return', index='year', columns='month')
        pivot.columns = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][:len(pivot.columns)]
        
        return pivot
    
    def calculate_rolling_metrics(
        self, 
        equity_curve: pd.Series, 
        window: int = 60
    ) -> pd.DataFrame:
        """
        Calculate rolling metrics over time.
        
        Args:
            equity_curve: Portfolio values
            window: Rolling window in days (default 60 = ~3 months)
            
        Returns:
            DataFrame with rolling Sharpe, return, volatility
        """
        if len(equity_curve) < window:
            return pd.DataFrame()
        
        daily_returns = equity_curve.pct_change().dropna()
        
        rolling_return = daily_returns.rolling(window).mean() * self.trading_days_per_year * 100
        rolling_vol = daily_returns.rolling(window).std() * np.sqrt(self.trading_days_per_year) * 100
        
        daily_rf = self.risk_free_rate / self.trading_days_per_year
        excess = daily_returns - daily_rf
        rolling_sharpe = (
            excess.rolling(window).mean() / 
            excess.rolling(window).std() * 
            np.sqrt(self.trading_days_per_year)
        )
        
        return pd.DataFrame({
            'rolling_return_annualized': rolling_return,
            'rolling_volatility': rolling_vol,
            'rolling_sharpe': rolling_sharpe,
        })


def quick_metrics(
    trades: List[TradeResult],
    initial_capital: float = 500_000
) -> Dict:
    """
    Quick metric calculation without full equity curve.
    
    Use this for fast strategy comparison when you don't have
    daily equity values.
    """
    if not trades:
        return {"error": "No trades provided"}
    
    pnls = [t.gross_pnl for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]
    
    win_rate = len(winners) / len(trades) * 100 if trades else 0
    avg_win = np.mean(winners) if winners else 0
    avg_loss = abs(np.mean(losers)) if losers else 0
    
    profit_factor = sum(winners) / abs(sum(losers)) if losers else float('inf')
    
    total_return = sum(pnls) / initial_capital * 100
    
    # Expectancy
    expectancy = (win_rate/100 * avg_win) - ((1 - win_rate/100) * avg_loss)
    
    return {
        "total_trades": len(trades),
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "total_return_pct": round(total_return, 2),
        "expectancy_per_trade": round(expectancy, 0),
        "avg_win": round(avg_win, 0),
        "avg_loss": round(avg_loss, 0),
        "avg_holding_days": round(np.mean([t.holding_days for t in trades]), 1),
    }
