"""
Simple Backtesting Engine for NEPSE.

This is a MINIMAL backtester to validate strategies before live trading.
Following the advice to avoid scope creep - this is NOT a full-featured
backtesting framework, just enough to test the core strategies.

CRITICAL NEPSE REALITIES MODELED:
1. Slippage: 1.5% default (manual execution in illiquid market)
2. Transaction costs: 0.4% broker + 0.015% SEBON + Rs.25 DP
3. Adjusted prices: Must use bonus/right-adjusted prices
4. No stop-loss orders: NEPSE TMS doesn't support them

USAGE:
    from backtesting.engine import SimpleBacktest
    
    bt = SimpleBacktest(strategy=GoldenCrossStrategy())
    results = bt.run(symbol="NICA", start_date="2024-01-01")
    print(results.summary())
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Optional, Type
import pandas as pd
import numpy as np
from loguru import logger

from core.config import settings
from core.database import SessionLocal, Stock, DailyPrice
from analysis.strategies import BaseStrategy, StrategySignal
from analysis.indicators import TechnicalIndicators
from risk.position_sizer import PositionSizer


@dataclass
class BacktestConfig:
    """Configuration container for backtest execution hooks."""
    slippage_pct: float = settings.slippage_pct
    commission_pct: float = settings.broker_commission_pct + settings.sebon_fee_pct
    dp_charge: float = settings.dp_charge
    initial_capital: float = 100000
    risk_per_trade: float = settings.risk_per_trade


@dataclass
class Trade:
    """Represents a single backtest trade."""
    symbol: str
    entry_date: date
    entry_price: float
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    quantity: int = 1
    signal_type: str = "BUY"
    exit_reason: str = ""  # "target", "stop_loss", "signal", "end_of_data"
    
    @property
    def is_closed(self) -> bool:
        return self.exit_date is not None
    
    @property
    def gross_pnl(self) -> float:
        """Profit/loss before costs."""
        if not self.is_closed:
            return 0.0
        return (self.exit_price - self.entry_price) * self.quantity
    
    @property
    def gross_pnl_pct(self) -> float:
        """Gross P&L as percentage."""
        if not self.is_closed or self.entry_price == 0:
            return 0.0
        return ((self.exit_price / self.entry_price) - 1) * 100


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    symbol: str
    strategy_name: str
    start_date: date
    end_date: date
    
    # Trade statistics
    trades: List[Trade] = field(default_factory=list)
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Returns
    gross_return_pct: float = 0.0
    net_return_pct: float = 0.0  # After costs
    
    # Risk metrics
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0  # Gross profit / Gross loss
    max_drawdown_pct: float = 0.0
    
    # Cost breakdown
    total_slippage: float = 0.0
    total_commission: float = 0.0
    
    def summary(self) -> str:
        """Generate a text summary of results."""
        lines = [
            f"\n{'='*50}",
            f"BACKTEST RESULTS: {self.symbol} ({self.strategy_name})",
            f"{'='*50}",
            f"Period: {self.start_date} to {self.end_date}",
            f"",
            f"📊 TRADE STATISTICS",
            f"  Total Trades: {self.total_trades}",
            f"  Winning: {self.winning_trades} | Losing: {self.losing_trades}",
            f"  Win Rate: {self.win_rate:.1f}%",
            f"",
            f"💰 RETURNS",
            f"  Gross Return: {self.gross_return_pct:+.2f}%",
            f"  Net Return (after costs): {self.net_return_pct:+.2f}%",
            f"",
            f"📉 RISK METRICS",
            f"  Avg Win: +{self.avg_win_pct:.2f}%",
            f"  Avg Loss: {self.avg_loss_pct:.2f}%",
            f"  Profit Factor: {self.profit_factor:.2f}",
            f"  Max Drawdown: {self.max_drawdown_pct:.2f}%",
            f"",
            f"💸 COSTS (NEPSE Reality)",
            f"  Slippage: Rs. {self.total_slippage:.2f}",
            f"  Commission: Rs. {self.total_commission:.2f}",
            f"{'='*50}",
        ]
        return "\n".join(lines)


class SimpleBacktest:
    """
    Simple backtesting engine for NEPSE strategies.
    
    Models real-world NEPSE execution:
    - Manual execution (no API trading)
    - Slippage in illiquid stocks
    - Full transaction costs
    """
    
    def __init__(
        self,
        strategy: BaseStrategy,
        slippage_pct: float = None,
        commission_pct: float = None,
    ):
        """
        Initialize backtest.
        
        Args:
            strategy: Trading strategy to test
            slippage_pct: Override default slippage
            commission_pct: Override default commission
        """
        self.strategy = strategy
        self.slippage_pct = slippage_pct or settings.slippage_pct
        self.commission_pct = commission_pct or (
            settings.broker_commission_pct + settings.sebon_fee_pct
        )
        self.sizer = None  # Initialized in run() with actual capital
    
    def _get_historical_data(
        self, 
        symbol: str, 
        start_date: date,
        end_date: date = None,
    ) -> pd.DataFrame:
        """Load historical data from database."""
        end_date = end_date or date.today()
        
        db = SessionLocal()
        try:
            stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
            if not stock:
                logger.error(f"Stock not found: {symbol}")
                return pd.DataFrame()
            
            prices = (
                db.query(DailyPrice)
                .filter(
                    DailyPrice.stock_id == stock.id,
                    DailyPrice.date >= start_date,
                    DailyPrice.date <= end_date,
                )
                .order_by(DailyPrice.date)
                .all()
            )
            
            if not prices:
                return pd.DataFrame()
            
            data = [
                {
                    "date": p.date,
                    "open": p.open,
                    "high": p.high,
                    "low": p.low,
                    "close": p.close,
                    "volume": p.volume,
                }
                for p in prices
            ]
            
            return pd.DataFrame(data)
            
        finally:
            db.close()
    
    def _apply_slippage(self, price: float, is_buy: bool) -> float:
        """
        Apply slippage to a trade price.
        
        NEPSE REALITY: No API trading means manual execution.
        In volatile/illiquid conditions, you won't get the exact price.
        
        Args:
            price: Ideal execution price
            is_buy: True if buying (slippage works against you)
            
        Returns:
            Price after slippage
        """
        if is_buy:
            # Buying: you pay more than expected
            return price * (1 + self.slippage_pct)
        else:
            # Selling: you get less than expected
            return price * (1 - self.slippage_pct)
    
    def _calculate_costs(self, price: float, quantity: int) -> float:
        """
        Calculate transaction costs for NEPSE trade.
        
        Costs include:
        - Broker commission: 0.4%
        - SEBON fee: 0.015%
        - DP charge: Rs. 25 per transaction
        """
        turnover = price * quantity
        commission = turnover * self.commission_pct
        dp_charge = settings.dp_charge
        
        return commission + dp_charge
    
    def run(
        self,
        symbol: str,
        start_date: str,
        end_date: str = None,
        initial_capital: float = 100000,
    ) -> BacktestResult:
        """
        Run backtest on a single stock.
        
        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD, default: today)
            initial_capital: Starting capital in Rs.
            
        Returns:
            BacktestResult with all metrics
        """
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.today()
        
        logger.info(f"Running backtest: {symbol} from {start} to {end}")
        
        # Load data
        df = self._get_historical_data(symbol, start, end)
        
        if df.empty or len(df) < 30:
            logger.error(f"Insufficient data for {symbol}")
            return BacktestResult(
                symbol=symbol,
                strategy_name=self.strategy.name,
                start_date=start,
                end_date=end,
            )
        
        # Calculate indicators
        ti = TechnicalIndicators(df)
        ti.add_all_indicators()
        ti.detect_golden_cross()
        df = ti.df
        
        # Simulate trading
        trades = []
        current_trade: Optional[Trade] = None
        capital = initial_capital
        equity_curve = [capital]
        total_slippage = 0.0
        total_commission = 0.0
        
        # Initialize PositionSizer with capital (H6 fix: proper risk management)
        self.sizer = PositionSizer(
            portfolio_value=initial_capital,
            max_risk_per_trade=settings.risk_per_trade / 100,  # Convert % to decimal
        )
        
        # Walk through each day
        for i in range(30, len(df)):  # Need 30 days for indicators
            row = df.iloc[i]
            current_date = row["date"]
            price = row["close"]
            
            # If we have an open position, check for exit
            if current_trade and not current_trade.is_closed:
                # Check stop loss (5% below entry)
                stop_price = current_trade.entry_price * (1 - settings.stop_loss)
                
                # Check target (10% above entry)
                target_price = current_trade.entry_price * (1 + settings.target_profit)
                
                exit_triggered = False
                exit_reason = ""
                
                if row["low"] <= stop_price:
                    # H5 FIX: Stop loss hit - but manual execution means you may NOT catch it
                    # In NEPSE manual execution: 40% chance you catch the stop during the day
                    # Otherwise you miss it and exit at close
                    if np.random.random() < 0.4:  # 40% chance you catch it
                        exit_price = self._apply_slippage(stop_price, is_buy=False)
                    else:
                        # Miss the stop, exit at close with extra slippage
                        exit_price = self._apply_slippage(row["close"], is_buy=False)
                    exit_triggered = True
                    exit_reason = "stop_loss"
                    
                elif row["high"] >= target_price:
                    # H5 FIX: Target hit - but market pulls back before you can sell
                    # Assume 70% chance market holds and you get the target
                    if np.random.random() < 0.7:  # 70% chance market holds
                        exit_price = self._apply_slippage(target_price, is_buy=False)
                    else:
                        # Market rejects target, you exit at close
                        exit_price = self._apply_slippage(row["close"], is_buy=False)
                    exit_triggered = True
                    exit_reason = "target"
                
                if exit_triggered:
                    current_trade.exit_date = current_date
                    current_trade.exit_price = exit_price
                    current_trade.exit_reason = exit_reason
                    
                    # Calculate costs
                    cost = self._calculate_costs(exit_price, current_trade.quantity)
                    total_commission += cost
                    total_slippage += abs(price - exit_price) * current_trade.quantity
                    
                    # Update capital
                    pnl = current_trade.gross_pnl - cost
                    capital += pnl
                    
                    trades.append(current_trade)
                    current_trade = None
            
            # If no position, look for entry signal
            if current_trade is None:
                # Get recent data for strategy
                lookback_df = df.iloc[i-29:i+1].copy()
                
                signal = self.strategy.analyze(lookback_df, symbol)
                
                if signal and signal.signal_type == "BUY":
                    # Enter trade
                    entry_price = self._apply_slippage(price, is_buy=True)
                    
                    # H6 FIX: Use PositionSizer instead of 100% capital allocation
                    # Calculate stop loss (use signal's stop or default 5%)
                    stop_loss = signal.stop_loss if signal.stop_loss else entry_price * (1 - settings.stop_loss)
                    target_price = signal.target_price if signal.target_price else entry_price * (1 + settings.target_profit)
                    
                    # Update sizer with current capital
                    self.sizer.portfolio_value = capital
                    self.sizer.max_risk_amount = capital * self.sizer.max_risk_per_trade
                    
                    try:
                        position = self.sizer.calculate(
                            symbol=symbol,
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            target_price=target_price,
                        )
                        quantity = position.shares
                    except ValueError:
                        # Invalid stop loss (above entry), use conservative sizing
                        quantity = int(capital * 0.1 / entry_price)  # Max 10% of capital
                    
                    if quantity > 0:
                        # Entry cost
                        cost = self._calculate_costs(entry_price, quantity)
                        total_commission += cost
                        total_slippage += abs(entry_price - price) * quantity
                        
                        current_trade = Trade(
                            symbol=symbol,
                            entry_date=current_date,
                            entry_price=entry_price,
                            quantity=quantity,
                        )
                        
                        # Deduct capital
                        capital -= (entry_price * quantity + cost)
            
            # Track equity
            if current_trade and not current_trade.is_closed:
                mark_to_market = current_trade.entry_price + (price - current_trade.entry_price) * current_trade.quantity
                equity_curve.append(capital + mark_to_market)
            else:
                equity_curve.append(capital)
        
        # Close any open trade at end of period
        if current_trade and not current_trade.is_closed:
            final_price = df.iloc[-1]["close"]
            exit_price = self._apply_slippage(final_price, is_buy=False)
            
            current_trade.exit_date = df.iloc[-1]["date"]
            current_trade.exit_price = exit_price
            current_trade.exit_reason = "end_of_data"
            
            cost = self._calculate_costs(exit_price, current_trade.quantity)
            total_commission += cost
            
            trades.append(current_trade)
        
        # Calculate metrics
        result = self._calculate_metrics(
            trades=trades,
            equity_curve=equity_curve,
            initial_capital=initial_capital,
            symbol=symbol,
            start_date=start,
            end_date=end,
            total_slippage=total_slippage,
            total_commission=total_commission,
        )
        
        return result
    
    def _calculate_metrics(
        self,
        trades: List[Trade],
        equity_curve: List[float],
        initial_capital: float,
        symbol: str,
        start_date: date,
        end_date: date,
        total_slippage: float,
        total_commission: float,
    ) -> BacktestResult:
        """Calculate all backtest metrics."""
        
        result = BacktestResult(
            symbol=symbol,
            strategy_name=self.strategy.name,
            start_date=start_date,
            end_date=end_date,
            trades=trades,
            total_slippage=total_slippage,
            total_commission=total_commission,
        )
        
        if not trades:
            return result
        
        # Basic counts
        closed_trades = [t for t in trades if t.is_closed]
        result.total_trades = len(closed_trades)
        
        wins = [t for t in closed_trades if t.gross_pnl > 0]
        losses = [t for t in closed_trades if t.gross_pnl <= 0]
        
        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0
        
        # Returns
        final_equity = equity_curve[-1] if equity_curve else initial_capital
        gross_pnl = sum(t.gross_pnl for t in closed_trades)
        
        result.gross_return_pct = (gross_pnl / initial_capital) * 100
        result.net_return_pct = ((final_equity / initial_capital) - 1) * 100
        
        # Win/loss averages
        if wins:
            result.avg_win_pct = np.mean([t.gross_pnl_pct for t in wins])
        if losses:
            result.avg_loss_pct = np.mean([t.gross_pnl_pct for t in losses])
        
        # Profit factor
        total_win = sum(t.gross_pnl for t in wins) if wins else 0
        total_loss = abs(sum(t.gross_pnl for t in losses)) if losses else 1
        result.profit_factor = total_win / total_loss if total_loss > 0 else 0
        
        # Max drawdown
        if equity_curve:
            equity = np.array(equity_curve)
            peak = np.maximum.accumulate(equity)
            drawdown = (peak - equity) / peak * 100
            result.max_drawdown_pct = np.max(drawdown)
        
        return result


def quick_backtest(
    symbol: str,
    strategy_name: str = "golden_cross",
    start_date: str = "2024-01-01",
) -> BacktestResult:
    """
    Quick backtest with default settings.
    
    Args:
        symbol: Stock symbol
        strategy_name: Strategy to test
        start_date: Start date
        
    Returns:
        BacktestResult
    """
    from analysis.strategies.golden_cross import GoldenCrossStrategy
    from analysis.strategies.volume_breakout import VolumeBreakoutStrategy
    from analysis.strategies.rsi_momentum import RSIMomentumStrategy
    
    strategies = {
        "golden_cross": GoldenCrossStrategy,
        "volume_breakout": VolumeBreakoutStrategy,
        "rsi_momentum": RSIMomentumStrategy,
    }
    
    strategy_class = strategies.get(strategy_name, GoldenCrossStrategy)
    strategy = strategy_class()
    
    bt = SimpleBacktest(strategy=strategy)
    return bt.run(symbol=symbol, start_date=start_date)
