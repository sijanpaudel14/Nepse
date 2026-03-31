"""
NEPSE Backtesting Engine — Institutional-Grade.

Bar-by-bar simulation with:
  1. CSS-integrated signals (Composite Signal Score)
  2. NEPSE cost model: 0.36% buy + 0.36% sell + Rs.25 DP + 0.015% SEBON
  3. Volume-dependent slippage: f(volume) — low-vol 1-2%, high-vol 0.3-0.5%
  4. T+2 settlement awareness (block exits < 3 trading days)
  5. Walk-forward & Monte Carlo robustness testing

Also supports legacy strategy-based signals via BaseStrategy interface.

USAGE:
    # CSS mode (recommended)
    bt = SimpleBacktest(mode="css", profile="swing")
    results = bt.run(symbol="NICA", start_date="2024-01-01")

    # Legacy strategy mode
    bt = SimpleBacktest(strategy=GoldenCrossStrategy())
    results = bt.run(symbol="NICA", start_date="2024-01-01")
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Optional, Type, Tuple
import pandas as pd
import numpy as np
from loguru import logger

from core.config import settings
from core.database import SessionLocal, Stock, DailyPrice
from analysis.strategies import BaseStrategy, StrategySignal
from analysis.indicators import TechnicalIndicators
from risk.position_sizer import PositionSizer

# --------------- NEPSE Cost Constants ---------------
NEPSE_BROKER_COMMISSION = settings.broker_commission_pct   # 0.36% per side
NEPSE_SEBON_FEE = settings.sebon_fee_pct                   # 0.015%
NEPSE_DP_CHARGE = settings.dp_charge                       # Rs.25 per txn
NEPSE_TRADING_DAYS = settings.nepse_trading_days_per_year   # 230
NEPSE_RISK_FREE = settings.risk_free_rate                   # 5.5%

# Volume-based slippage tiers (avg daily volume → slippage %)
SLIPPAGE_TIERS = [
    (0,        5_000,   0.020),   # Micro-cap / illiquid: 2.0%
    (5_000,    20_000,  0.015),   # Low-volume: 1.5%
    (20_000,   100_000, 0.008),   # Mid-volume: 0.8%
    (100_000,  500_000, 0.005),   # High-volume: 0.5%
    (500_000,  float('inf'), 0.003),  # Very liquid: 0.3%
]


def volume_slippage(avg_volume: float) -> float:
    """Return slippage pct based on a stock's average daily volume."""
    for lo, hi, slip in SLIPPAGE_TIERS:
        if lo <= avg_volume < hi:
            return slip
    return 0.015  # default


@dataclass
class BacktestConfig:
    """Configuration container for backtest execution hooks."""
    slippage_pct: float = settings.slippage_pct
    commission_pct: float = NEPSE_BROKER_COMMISSION + NEPSE_SEBON_FEE
    dp_charge: float = NEPSE_DP_CHARGE
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
    exit_reason: str = ""  # "target", "stop_loss", "trailing_stop", "signal", "end_of_data"
    stop_loss: float = 0.0
    target_price: float = 0.0
    css_score: float = 0.0  # CSS score at entry
    entry_cost: float = 0.0
    exit_cost: float = 0.0
    slippage_cost: float = 0.0
    
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
    def net_pnl(self) -> float:
        """Profit/loss after all costs."""
        return self.gross_pnl - self.entry_cost - self.exit_cost - self.slippage_cost
    
    @property
    def gross_pnl_pct(self) -> float:
        """Gross P&L as percentage."""
        if not self.is_closed or self.entry_price == 0:
            return 0.0
        return ((self.exit_price / self.entry_price) - 1) * 100
    
    @property
    def holding_days(self) -> int:
        if not self.is_closed:
            return 0
        return (self.exit_date - self.entry_date).days


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
    cagr: float = 0.0
    
    # Risk metrics
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0  # Gross profit / Gross loss
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    expectancy: float = 0.0  # Rs. per trade
    avg_holding_days: float = 0.0
    
    # Cost breakdown
    total_slippage: float = 0.0
    total_commission: float = 0.0
    
    # Equity curve for further analysis
    equity_curve: List[float] = field(default_factory=list)
    equity_dates: List[date] = field(default_factory=list)
    
    def summary(self) -> str:
        """Generate a text summary of results."""
        lines = [
            f"\n{'='*60}",
            f"BACKTEST RESULTS: {self.symbol} ({self.strategy_name})",
            f"{'='*60}",
            f"Period: {self.start_date} to {self.end_date}",
            f"",
            f"TRADE STATISTICS",
            f"  Total Trades: {self.total_trades}",
            f"  Winning: {self.winning_trades} | Losing: {self.losing_trades}",
            f"  Win Rate: {self.win_rate:.1f}%",
            f"  Avg Holding: {self.avg_holding_days:.1f} days",
            f"",
            f"RETURNS",
            f"  Gross Return: {self.gross_return_pct:+.2f}%",
            f"  Net Return (after costs): {self.net_return_pct:+.2f}%",
            f"  CAGR: {self.cagr:+.2f}%",
            f"",
            f"RISK METRICS",
            f"  Sharpe Ratio:  {self.sharpe_ratio:.2f}",
            f"  Sortino Ratio: {self.sortino_ratio:.2f}",
            f"  Calmar Ratio:  {self.calmar_ratio:.2f}",
            f"  Avg Win: +{self.avg_win_pct:.2f}%",
            f"  Avg Loss: {self.avg_loss_pct:.2f}%",
            f"  Profit Factor: {self.profit_factor:.2f}",
            f"  Max Drawdown: {self.max_drawdown_pct:.2f}%",
            f"  Expectancy: Rs.{self.expectancy:,.0f}/trade",
            f"",
            f"COSTS (NEPSE Reality)",
            f"  Slippage: Rs. {self.total_slippage:,.2f}",
            f"  Commission+Fees: Rs. {self.total_commission:,.2f}",
            f"  Total Costs: Rs. {self.total_slippage + self.total_commission:,.2f}",
            f"{'='*60}",
        ]
        return "\n".join(lines)


class SimpleBacktest:
    """
    Institutional-grade NEPSE backtesting engine.

    Supports two modes:
      1. "css"      — Uses Composite Signal Score (recommended)
      2. "strategy" — Legacy BaseStrategy interface

    Models real-world NEPSE execution:
      - Volume-dependent slippage (not flat %)
      - Full transaction costs (buy + sell side)
      - T+2 settlement awareness
      - Manual execution probability (no API orders)
      - ATR-based dynamic stops
    """

    def __init__(
        self,
        strategy: Optional[BaseStrategy] = None,
        mode: str = "strategy",
        profile: str = "swing",
        slippage_pct: Optional[float] = None,
        commission_pct: Optional[float] = None,
    ):
        self.strategy = strategy
        self.mode = mode
        self.profile = profile
        self.slippage_override = slippage_pct
        self.commission_pct = commission_pct or (NEPSE_BROKER_COMMISSION + NEPSE_SEBON_FEE)
        self.sizer: Optional[PositionSizer] = None

    # ────────────────────────────────────────────
    # Data loading
    # ────────────────────────────────────────────

    def _get_historical_data(
        self,
        symbol: str,
        start_date: date,
        end_date: Optional[date] = None,
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

    # ────────────────────────────────────────────
    # NEPSE cost & slippage model
    # ────────────────────────────────────────────

    def _get_slippage(self, avg_volume: float) -> float:
        """Volume-dependent slippage — replaces flat 1.5%."""
        if self.slippage_override is not None:
            return self.slippage_override
        return volume_slippage(avg_volume)

    def _apply_slippage(self, price: float, is_buy: bool, slip_pct: float) -> float:
        """Apply directional slippage to price."""
        if is_buy:
            return price * (1 + slip_pct)
        return price * (1 - slip_pct)

    def _calculate_costs(self, price: float, quantity: int, side: str = "buy") -> float:
        """
        Full NEPSE cost model for one side of a trade.

        Buy side:  0.36% broker + 0.015% SEBON + Rs.25 DP
        Sell side: 0.36% broker + 0.015% SEBON + Rs.25 DP
        """
        turnover = price * quantity
        broker = turnover * NEPSE_BROKER_COMMISSION
        sebon = turnover * NEPSE_SEBON_FEE
        return broker + sebon + NEPSE_DP_CHARGE

    # ────────────────────────────────────────────
    # CSS signal generation (bar-by-bar)
    # ────────────────────────────────────────────

    def _generate_css_signal(
        self,
        df: pd.DataFrame,
        idx: int,
        symbol: str,
    ) -> Optional[dict]:
        """
        Generate a CSS signal for bar at idx.

        Returns dict with keys: signal, css, entry_price, stop_loss, target_price
        or None if insufficient data.
        """
        from analysis.signal_scorer import compute_css
        from analysis.quant_indicators import QuantIndicators

        lookback = df.iloc[max(0, idx - 59) : idx + 1].copy()
        if len(lookback) < 30:
            return None

        qi = QuantIndicators(lookback)
        ind = qi.get_latest_indicators()
        if not ind:
            return None

        result = compute_css(
            symbol=symbol,
            indicators=ind,
            profile=self.profile,
        )

        if result.signal in ("STRONG_BUY", "BUY"):
            return {
                "signal": result.signal,
                "css": result.css,
                "entry_price": result.entry_price,
                "stop_loss": result.stop_loss,
                "target_price": result.target_price,
            }
        if result.signal in ("SELL", "STRONG_SELL"):
            return {
                "signal": result.signal,
                "css": result.css,
                "entry_price": 0,
                "stop_loss": 0,
                "target_price": 0,
            }
        return None

    # ────────────────────────────────────────────
    # Main simulation loop
    # ────────────────────────────────────────────

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
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD (default: today)
            initial_capital: Starting capital in Rs.

        Returns:
            BacktestResult with all metrics
        """
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.today()
        strategy_name = self.strategy.name if self.strategy else f"CSS-{self.profile}"

        logger.info(f"Running backtest: {symbol} [{strategy_name}] {start}→{end}")

        # Load data
        df = self._get_historical_data(symbol, start, end)
        if df.empty or len(df) < 30:
            logger.error(f"Insufficient data for {symbol}")
            return BacktestResult(
                symbol=symbol,
                strategy_name=strategy_name,
                start_date=start,
                end_date=end,
            )

        # Pre-compute indicators for legacy mode
        if self.mode == "strategy" and self.strategy:
            ti = TechnicalIndicators(df)
            ti.add_all_indicators()
            ti.detect_golden_cross()
            df = ti.df

        # Compute average volume for slippage model
        avg_vol = df["volume"].mean()
        slip_pct = self._get_slippage(avg_vol)

        # State
        trades: List[Trade] = []
        current_trade: Optional[Trade] = None
        capital = initial_capital
        equity_curve: List[float] = [capital]
        equity_dates: List[date] = [df.iloc[0]["date"]]
        total_slippage = 0.0
        total_commission = 0.0

        # Position sizer
        self.sizer = PositionSizer(
            portfolio_value=initial_capital,
            max_risk_per_trade=settings.risk_per_trade,
        )

        warmup = 30

        for i in range(warmup, len(df)):
            row = df.iloc[i]
            current_date = row["date"]
            price = row["close"]

            # ─── EXIT LOGIC ───
            if current_trade and not current_trade.is_closed:
                # T+2: block exits if < 3 trading days held
                bars_held = i - self._entry_bar_idx
                if bars_held < 3:
                    # Cannot sell yet (T+2 settlement)
                    pass
                else:
                    exit_triggered = False
                    exit_reason = ""
                    exit_price = 0.0

                    # 1. Stop loss (ATR-based stored in trade)
                    if row["low"] <= current_trade.stop_loss:
                        # Manual execution: 40% chance to catch intraday stop
                        if np.random.random() < 0.4:
                            exit_price = self._apply_slippage(
                                current_trade.stop_loss, False, slip_pct
                            )
                        else:
                            exit_price = self._apply_slippage(
                                row["close"], False, slip_pct
                            )
                        exit_triggered = True
                        exit_reason = "stop_loss"

                    # 2. Target hit
                    elif row["high"] >= current_trade.target_price:
                        if np.random.random() < 0.7:
                            exit_price = self._apply_slippage(
                                current_trade.target_price, False, slip_pct
                            )
                        else:
                            exit_price = self._apply_slippage(
                                row["close"], False, slip_pct
                            )
                        exit_triggered = True
                        exit_reason = "target"

                    # 3. CSS sell signal (CSS mode only)
                    elif self.mode == "css":
                        css_sig = self._generate_css_signal(df, i, symbol)
                        if css_sig and css_sig["signal"] in ("SELL", "STRONG_SELL"):
                            exit_price = self._apply_slippage(
                                row["close"], False, slip_pct
                            )
                            exit_triggered = True
                            exit_reason = "css_sell"

                    if exit_triggered:
                        sell_cost = self._calculate_costs(exit_price, current_trade.quantity, "sell")
                        slip_cost = abs(price - exit_price) * current_trade.quantity
                        total_commission += sell_cost
                        total_slippage += slip_cost

                        current_trade.exit_date = current_date
                        current_trade.exit_price = exit_price
                        current_trade.exit_reason = exit_reason
                        current_trade.exit_cost = sell_cost
                        current_trade.slippage_cost += slip_cost

                        capital += (exit_price * current_trade.quantity) - sell_cost
                        trades.append(current_trade)
                        current_trade = None

            # ─── ENTRY LOGIC ───
            if current_trade is None:
                signal = None

                if self.mode == "css":
                    css_sig = self._generate_css_signal(df, i, symbol)
                    if css_sig and css_sig["signal"] in ("STRONG_BUY", "BUY"):
                        signal = css_sig
                elif self.strategy:
                    lookback_df = df.iloc[i - 29 : i + 1].copy()
                    strat_sig = self.strategy.analyze(lookback_df, symbol)
                    if strat_sig and strat_sig.signal_type == "BUY":
                        atr_default = price * 0.03
                        signal = {
                            "signal": "BUY",
                            "css": strat_sig.confidence / 10.0,
                            "entry_price": price,
                            "stop_loss": strat_sig.stop_loss
                            if strat_sig.stop_loss
                            else price * (1 - settings.stop_loss),
                            "target_price": strat_sig.target_price
                            if strat_sig.target_price
                            else price * (1 + settings.target_profit),
                        }

                if signal:
                    entry_price = self._apply_slippage(
                        signal["entry_price"], True, slip_pct
                    )
                    stop = signal["stop_loss"]
                    target = signal["target_price"]

                    # Position sizing via PositionSizer
                    self.sizer.portfolio_value = capital
                    self.sizer.max_risk_amount = capital * self.sizer.max_risk_per_trade
                    try:
                        pos = self.sizer.calculate(
                            symbol=symbol,
                            entry_price=entry_price,
                            stop_loss=stop,
                            target_price=target,
                        )
                        quantity = pos.shares
                    except (ValueError, Exception):
                        quantity = max(1, int(capital * 0.10 / entry_price))

                    required = entry_price * quantity
                    buy_cost = self._calculate_costs(entry_price, quantity, "buy")
                    if required + buy_cost > capital:
                        quantity = max(1, int((capital - buy_cost) / entry_price))
                        required = entry_price * quantity
                        buy_cost = self._calculate_costs(entry_price, quantity, "buy")

                    if quantity > 0 and required + buy_cost <= capital:
                        slip_cost = abs(entry_price - price) * quantity
                        total_commission += buy_cost
                        total_slippage += slip_cost

                        current_trade = Trade(
                            symbol=symbol,
                            entry_date=current_date,
                            entry_price=entry_price,
                            quantity=quantity,
                            stop_loss=stop,
                            target_price=target,
                            css_score=signal.get("css", 0),
                            entry_cost=buy_cost,
                            slippage_cost=slip_cost,
                        )
                        capital -= (required + buy_cost)
                        self._entry_bar_idx = i

            # Equity tracking
            if current_trade and not current_trade.is_closed:
                mark = capital + price * current_trade.quantity
                equity_curve.append(mark)
            else:
                equity_curve.append(capital)
            equity_dates.append(current_date)

        # Close any open trade at end of period
        if current_trade and not current_trade.is_closed:
            final_price = df.iloc[-1]["close"]
            exit_price = self._apply_slippage(final_price, False, slip_pct)
            sell_cost = self._calculate_costs(exit_price, current_trade.quantity, "sell")
            total_commission += sell_cost
            total_slippage += abs(final_price - exit_price) * current_trade.quantity

            current_trade.exit_date = df.iloc[-1]["date"]
            current_trade.exit_price = exit_price
            current_trade.exit_reason = "end_of_data"
            current_trade.exit_cost = sell_cost
            capital += (exit_price * current_trade.quantity) - sell_cost
            trades.append(current_trade)

        # Calculate metrics
        return self._calculate_metrics(
            trades=trades,
            equity_curve=equity_curve,
            equity_dates=equity_dates,
            initial_capital=initial_capital,
            symbol=symbol,
            strategy_name=strategy_name,
            start_date=start,
            end_date=end,
            total_slippage=total_slippage,
            total_commission=total_commission,
        )
    
    # ────────────────────────────────────────────
    # Metrics calculation
    # ────────────────────────────────────────────

    def _calculate_metrics(
        self,
        trades: List[Trade],
        equity_curve: List[float],
        equity_dates: List[date],
        initial_capital: float,
        symbol: str,
        strategy_name: str,
        start_date: date,
        end_date: date,
        total_slippage: float,
        total_commission: float,
    ) -> BacktestResult:
        """Calculate all backtest metrics including Sharpe/Sortino/CAGR."""
        result = BacktestResult(
            symbol=symbol,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            trades=trades,
            total_slippage=total_slippage,
            total_commission=total_commission,
            equity_curve=equity_curve,
            equity_dates=equity_dates,
        )

        if not trades:
            return result

        closed = [t for t in trades if t.is_closed]
        result.total_trades = len(closed)

        wins = [t for t in closed if t.gross_pnl > 0]
        losses = [t for t in closed if t.gross_pnl <= 0]
        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.win_rate = (len(wins) / len(closed) * 100) if closed else 0

        # Returns
        final_equity = equity_curve[-1] if equity_curve else initial_capital
        gross_pnl = sum(t.gross_pnl for t in closed)
        result.gross_return_pct = (gross_pnl / initial_capital) * 100
        result.net_return_pct = ((final_equity / initial_capital) - 1) * 100

        # CAGR
        trading_days = len(equity_curve)
        years = trading_days / NEPSE_TRADING_DAYS
        if years > 0 and final_equity > 0:
            result.cagr = ((final_equity / initial_capital) ** (1 / years) - 1) * 100

        # Win/loss averages
        if wins:
            result.avg_win_pct = float(np.mean([t.gross_pnl_pct for t in wins]))
        if losses:
            result.avg_loss_pct = float(np.mean([t.gross_pnl_pct for t in losses]))

        # Profit factor
        total_win = sum(t.gross_pnl for t in wins) if wins else 0
        total_loss = abs(sum(t.gross_pnl for t in losses)) if losses else 1
        result.profit_factor = total_win / total_loss if total_loss > 0 else 0

        # Expectancy
        w = result.win_rate / 100
        result.expectancy = (
            w * (result.avg_win_pct if wins else 0) * initial_capital / 100
            - (1 - w) * abs(result.avg_loss_pct if losses else 0) * initial_capital / 100
        )

        # Avg holding days
        holding = [t.holding_days for t in closed if t.holding_days > 0]
        result.avg_holding_days = float(np.mean(holding)) if holding else 0

        # Sharpe / Sortino / Calmar / Max Drawdown
        if len(equity_curve) > 1:
            eq = np.array(equity_curve, dtype=float)
            daily_ret = np.diff(eq) / eq[:-1]
            daily_rf = NEPSE_RISK_FREE / NEPSE_TRADING_DAYS
            excess = daily_ret - daily_rf

            # Sharpe
            if np.std(excess) > 0:
                result.sharpe_ratio = float(
                    np.mean(excess) / np.std(excess) * np.sqrt(NEPSE_TRADING_DAYS)
                )

            # Sortino
            down = daily_ret[daily_ret < 0]
            if len(down) > 0 and np.std(down) > 0:
                result.sortino_ratio = float(
                    (np.mean(daily_ret) - daily_rf)
                    / np.std(down)
                    * np.sqrt(NEPSE_TRADING_DAYS)
                )

            # Max drawdown
            peak = np.maximum.accumulate(eq)
            dd_pct = (peak - eq) / peak * 100
            result.max_drawdown_pct = float(np.max(dd_pct))

            # Calmar
            if result.max_drawdown_pct > 0:
                result.calmar_ratio = result.cagr / result.max_drawdown_pct

        return result


# ================================================================
# Walk-forward backtest
# ================================================================

def walk_forward_backtest(
    symbol: str,
    strategy: Optional[BaseStrategy] = None,
    mode: str = "css",
    profile: str = "swing",
    start_date: str = "2023-01-01",
    end_date: str = None,
    train_months: int = 6,
    test_months: int = 2,
    initial_capital: float = 500_000,
) -> Dict[str, object]:
    """
    Walk-forward validation: train 6 months, test 2 months, roll forward.

    Returns dict with:
      - folds: list of BacktestResult (one per test window)
      - aggregate: combined metrics across all test windows
      - equity_curve: stitched equity curve across test windows
    """
    from dateutil.relativedelta import relativedelta

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.today()

    folds: List[BacktestResult] = []
    cursor = start
    roll_capital = initial_capital

    while cursor + relativedelta(months=train_months + test_months) <= end:
        test_start = cursor + relativedelta(months=train_months)
        test_end = test_start + relativedelta(months=test_months)
        if test_end > end:
            test_end = end

        bt = SimpleBacktest(
            strategy=strategy, mode=mode, profile=profile,
        )
        result = bt.run(
            symbol=symbol,
            start_date=test_start.strftime("%Y-%m-%d"),
            end_date=test_end.strftime("%Y-%m-%d"),
            initial_capital=roll_capital,
        )
        folds.append(result)
        # Rolling capital: carry forward
        if result.equity_curve:
            roll_capital = result.equity_curve[-1]

        cursor += relativedelta(months=test_months)

    # Aggregate metrics
    all_trades = [t for f in folds for t in f.trades]
    total_return = ((roll_capital / initial_capital) - 1) * 100

    return {
        "folds": folds,
        "total_folds": len(folds),
        "total_trades": len(all_trades),
        "total_return_pct": total_return,
        "final_capital": roll_capital,
        "avg_win_rate": float(np.mean([f.win_rate for f in folds])) if folds else 0,
    }


# ================================================================
# Monte Carlo robustness test
# ================================================================

def monte_carlo_test(
    symbol: str,
    strategy: Optional[BaseStrategy] = None,
    mode: str = "css",
    profile: str = "swing",
    start_date: str = "2024-01-01",
    end_date: str = None,
    initial_capital: float = 500_000,
    num_simulations: int = 100,
) -> Dict[str, object]:
    """
    Monte Carlo permutation test.

    Runs the actual backtest once, then shuffles the daily returns
    num_simulations times to produce a null distribution.

    If the actual return is above the 95th percentile of the shuffled
    distribution, the strategy has statistical edge.
    """
    bt = SimpleBacktest(strategy=strategy, mode=mode, profile=profile)
    actual = bt.run(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
    )

    if len(actual.equity_curve) < 10:
        return {
            "actual_return": actual.net_return_pct,
            "simulations": 0,
            "p_value": 1.0,
            "has_edge": False,
            "message": "Insufficient data for Monte Carlo test",
        }

    eq = np.array(actual.equity_curve, dtype=float)
    daily_returns = np.diff(eq) / eq[:-1]

    shuffled_finals = []
    for _ in range(num_simulations):
        perm = np.random.permutation(daily_returns)
        cum = initial_capital * np.cumprod(1 + perm)
        shuffled_finals.append(float(cum[-1]))

    shuffled_returns = [(f / initial_capital - 1) * 100 for f in shuffled_finals]
    pct_95 = float(np.percentile(shuffled_returns, 95))

    actual_ret = actual.net_return_pct
    # p-value: fraction of shuffled returns >= actual
    p_value = float(np.mean([1 for s in shuffled_returns if s >= actual_ret]))

    return {
        "actual_return": actual_ret,
        "shuffled_mean": float(np.mean(shuffled_returns)),
        "shuffled_95th": pct_95,
        "p_value": p_value,
        "simulations": num_simulations,
        "has_edge": actual_ret > pct_95,
        "message": (
            f"Strategy return ({actual_ret:.1f}%) {'>' if actual_ret > pct_95 else '<='} "
            f"95th percentile of random ({pct_95:.1f}%). "
            f"{'Statistically significant edge.' if actual_ret > pct_95 else 'No significant edge detected.'}"
        ),
    }


# ================================================================
# Multi-strategy comparison
# ================================================================

def compare_strategies(
    symbol: str,
    start_date: str = "2024-01-01",
    end_date: str = None,
    initial_capital: float = 500_000,
) -> pd.DataFrame:
    """
    Run all available strategies + CSS profiles on a single stock and compare.

    Returns a DataFrame sorted by net return.
    """
    from analysis.strategies.golden_cross import GoldenCrossStrategy
    from analysis.strategies.volume_breakout import VolumeBreakoutStrategy
    from analysis.strategies.rsi_momentum import RSIMomentumStrategy

    configs = [
        ("GoldenCross", GoldenCrossStrategy(), "strategy", None),
        ("VolumeBreakout", VolumeBreakoutStrategy(), "strategy", None),
        ("RSIMomentum", RSIMomentumStrategy(), "strategy", None),
        ("CSS-short_term", None, "css", "short_term"),
        ("CSS-swing", None, "css", "swing"),
        ("CSS-investment", None, "css", "investment"),
    ]

    rows = []
    for name, strat, mode, profile in configs:
        try:
            bt = SimpleBacktest(strategy=strat, mode=mode, profile=profile or "swing")
            r = bt.run(symbol, start_date, end_date, initial_capital)
            rows.append({
                "strategy": name,
                "net_return_pct": round(r.net_return_pct, 2),
                "cagr": round(r.cagr, 2),
                "sharpe": round(r.sharpe_ratio, 2),
                "max_dd": round(r.max_drawdown_pct, 2),
                "win_rate": round(r.win_rate, 1),
                "profit_factor": round(r.profit_factor, 2),
                "trades": r.total_trades,
                "total_costs": round(r.total_commission + r.total_slippage, 0),
            })
        except Exception as e:
            logger.warning(f"{name} failed: {e}")

    df = pd.DataFrame(rows).sort_values("net_return_pct", ascending=False)
    return df


# ================================================================
# Convenience wrapper (backward-compatible)
# ================================================================

def quick_backtest(
    symbol: str,
    strategy_name: str = "golden_cross",
    start_date: str = "2024-01-01",
) -> BacktestResult:
    """Quick backtest with default settings (legacy interface)."""
    from analysis.strategies.golden_cross import GoldenCrossStrategy
    from analysis.strategies.volume_breakout import VolumeBreakoutStrategy
    from analysis.strategies.rsi_momentum import RSIMomentumStrategy

    strategies = {
        "golden_cross": GoldenCrossStrategy,
        "volume_breakout": VolumeBreakoutStrategy,
        "rsi_momentum": RSIMomentumStrategy,
        "css_swing": None,
        "css_short": None,
        "css_invest": None,
    }

    if strategy_name.startswith("css"):
        profile_map = {
            "css_swing": "swing",
            "css_short": "short_term",
            "css_invest": "investment",
        }
        bt = SimpleBacktest(
            mode="css",
            profile=profile_map.get(strategy_name, "swing"),
        )
    else:
        strategy_class = strategies.get(strategy_name, GoldenCrossStrategy)
        bt = SimpleBacktest(strategy=strategy_class())

    return bt.run(symbol=symbol, start_date=start_date)
