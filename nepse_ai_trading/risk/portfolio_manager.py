"""
Portfolio Manager.

Manages multiple positions with:
- Position tracking
- Exposure limits
- Sector concentration rules
- Correlation checks

MILLIONAIRE RULES:
1. Max 5-7 open positions at any time
2. Max 30% in a single sector
3. Never add to losing positions (averaging down is gambling)
4. Always have cash for opportunities (80% invested max)

NEPSE-SPECIFIC:
- T+2 settlement: Cash isn't immediately available after selling
- Circuit breaker risk: Can't exit if stock hits lower circuit
- Sector rotation: NEPSE rotates Banking → Hydro → Insurance → Finance
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from datetime import date, datetime, timedelta
from enum import Enum
from loguru import logger

from core.config import settings
from risk.position_sizer import PositionSizer, PositionSize


class PositionStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    PENDING_BUY = "pending_buy"     # T+2 settlement
    PENDING_SELL = "pending_sell"


@dataclass
class Position:
    """Represents a single stock position."""
    symbol: str
    shares: int
    entry_price: float
    entry_date: date
    sector: str = ""
    stop_loss: float = 0.0
    target_price: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    
    # Updated on each price update
    current_price: float = 0.0
    last_updated: Optional[datetime] = None
    
    # Exit info (filled when closed)
    exit_price: Optional[float] = None
    exit_date: Optional[date] = None
    exit_reason: str = ""
    
    @property
    def cost_basis(self) -> float:
        """Total cost of position."""
        return self.shares * self.entry_price
    
    @property
    def current_value(self) -> float:
        """Current market value."""
        price = self.current_price or self.entry_price
        return self.shares * price
    
    @property
    def unrealized_pnl(self) -> float:
        """Unrealized profit/loss."""
        return self.current_value - self.cost_basis
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L as percentage."""
        if self.cost_basis == 0:
            return 0
        return (self.unrealized_pnl / self.cost_basis) * 100
    
    @property
    def realized_pnl(self) -> float:
        """Realized P&L (only for closed positions)."""
        if self.status != PositionStatus.CLOSED or not self.exit_price:
            return 0
        return (self.exit_price - self.entry_price) * self.shares
    
    @property
    def holding_days(self) -> int:
        """Days position has been held."""
        end_date = self.exit_date or date.today()
        return (end_date - self.entry_date).days
    
    @property
    def is_profitable(self) -> bool:
        """Is position currently profitable?"""
        return self.unrealized_pnl > 0
    
    @property
    def hit_stop_loss(self) -> bool:
        """Has price hit stop loss? (with exit slippage buffer)
        
        SLIPPAGE FIX: When selling at stop-loss, you get a WORSE price than stop.
        So the effective stop is HIGHER than the set stop (you need to trigger earlier
        to account for the worse execution price you'll receive).
        """
        if self.stop_loss <= 0 or self.current_price <= 0:
            return False
        # Adjust stop UPWARD to account for selling slippage
        # (trigger earlier because actual exit will be worse)
        adjusted_stop = self.stop_loss * (1 + settings.slippage_pct)
        return self.current_price <= adjusted_stop
    
    @property
    def hit_target(self) -> bool:
        """Has price hit target? (with exit slippage buffer)
        
        Slippage means you get a LOWER price than expected on sell.
        So we require price to be ABOVE target + slippage to ensure
        the actual execution price meets the target.
        """
        if self.target_price <= 0 or self.current_price <= 0:
            return False
        # Require price above target + slippage buffer
        adjusted_target = self.target_price * (1 + settings.slippage_pct)
        return self.current_price >= adjusted_target
    
    def update_price(self, price: float):
        """Update current price."""
        self.current_price = price
        self.last_updated = datetime.now()
    
    def close(self, exit_price: float, reason: str = "Manual"):
        """Close the position."""
        self.exit_price = exit_price
        self.exit_date = date.today()
        self.exit_reason = reason
        self.status = PositionStatus.CLOSED
        self.current_price = exit_price


@dataclass
class PortfolioSnapshot:
    """Point-in-time snapshot of portfolio."""
    date: date
    total_value: float
    cash: float
    positions_value: float
    unrealized_pnl: float
    realized_pnl: float
    num_positions: int
    
    # Risk metrics
    largest_position_pct: float
    sector_concentration: Dict[str, float]
    cash_pct: float


class PortfolioManager:
    """
    Manages trading portfolio with risk controls.
    
    Usage:
        pm = PortfolioManager(initial_capital=500_000)
        
        # Add position
        pm.add_position(Position(
            symbol="NABIL",
            shares=100,
            entry_price=1200,
            entry_date=date.today(),
            sector="Commercial Banks",
            stop_loss=1140,
            target_price=1320,
        ))
        
        # Check if can add more
        if pm.can_add_position("NICA", "Commercial Banks"):
            pm.add_position(...)
        
        # Daily update
        pm.update_prices({"NABIL": 1250, "NICA": 850})
        
        # Check portfolio health
        pm.print_summary()
    """
    
    def __init__(
        self,
        initial_capital: float,
        max_positions: int = 5,
        max_sector_exposure: float = 0.30,     # 30% max per sector
        max_single_position: float = 0.20,     # 20% max single position
        min_cash_pct: float = 0.20,            # Keep 20% cash
        max_correlation: float = 0.80,         # Max correlation between holdings
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        
        # Risk limits
        self.max_positions = max_positions
        self.max_sector_exposure = max_sector_exposure
        self.max_single_position = max_single_position
        self.min_cash_pct = min_cash_pct
        self.max_correlation = max_correlation
        
        # Positions
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        self.closed_positions: List[Position] = []
        
        # History
        self.snapshots: List[PortfolioSnapshot] = []
        self.trades_today: int = 0
        
        # Position sizer
        self.sizer = PositionSizer(
            portfolio_value=initial_capital,
            max_risk_per_trade=settings.max_risk_per_trade_pct / 100,
        )
        
        logger.info(
            f"PortfolioManager initialized: {initial_capital:,.0f} capital, "
            f"{max_positions} max positions, {max_sector_exposure:.0%} sector limit"
        )
    
    @property
    def total_value(self) -> float:
        """Total portfolio value (cash + positions)."""
        positions_value = sum(p.current_value for p in self.positions.values())
        return self.cash + positions_value
    
    @property
    def positions_value(self) -> float:
        """Total value of all positions."""
        return sum(p.current_value for p in self.positions.values())
    
    @property
    def unrealized_pnl(self) -> float:
        """Total unrealized P&L."""
        return sum(p.unrealized_pnl for p in self.positions.values())
    
    @property
    def realized_pnl(self) -> float:
        """Total realized P&L from closed trades."""
        return sum(p.realized_pnl for p in self.closed_positions)
    
    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)."""
        return self.unrealized_pnl + self.realized_pnl
    
    @property
    def return_pct(self) -> float:
        """Portfolio return percentage."""
        return (self.total_value - self.initial_capital) / self.initial_capital * 100
    
    @property
    def invested_pct(self) -> float:
        """Percentage of portfolio invested."""
        return (self.positions_value / self.total_value) * 100 if self.total_value > 0 else 0
    
    @property
    def cash_pct(self) -> float:
        """Cash as percentage of portfolio."""
        return (self.cash / self.total_value) * 100 if self.total_value > 0 else 100
    
    def get_sector_exposure(self) -> Dict[str, float]:
        """Get exposure by sector as percentage."""
        sector_values = {}
        
        for p in self.positions.values():
            sector = p.sector or "Unknown"
            sector_values[sector] = sector_values.get(sector, 0) + p.current_value
        
        total = self.total_value
        return {s: v / total for s, v in sector_values.items()} if total > 0 else {}
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position by symbol."""
        return self.positions.get(symbol.upper())
    
    def has_position(self, symbol: str) -> bool:
        """Check if position exists."""
        return symbol.upper() in self.positions
    
    def can_add_position(
        self, 
        symbol: str, 
        sector: str,
        position_value: float = 0,
    ) -> Tuple[bool, str]:
        """
        Check if a new position can be added.
        
        Returns:
            Tuple of (can_add, reason)
        """
        symbol = symbol.upper()
        
        # Already have position
        if symbol in self.positions:
            return False, f"Already have position in {symbol}"
        
        # Max positions reached
        if len(self.positions) >= self.max_positions:
            return False, f"Max positions ({self.max_positions}) reached"
        
        # Sector exposure check
        sector_exposure = self.get_sector_exposure()
        current_sector_exp = sector_exposure.get(sector, 0)
        
        if position_value > 0:
            new_sector_exp = (
                (current_sector_exp * self.total_value + position_value) / 
                (self.total_value + position_value)
            )
        else:
            new_sector_exp = current_sector_exp
        
        if new_sector_exp > self.max_sector_exposure:
            return False, f"Sector {sector} would exceed {self.max_sector_exposure:.0%} limit"
        
        # Cash check
        if position_value > 0:
            remaining_cash = self.cash - position_value
            remaining_cash_pct = remaining_cash / self.total_value
            
            if remaining_cash_pct < self.min_cash_pct:
                return False, f"Would leave less than {self.min_cash_pct:.0%} cash"
        
        return True, "OK"
    
    def add_position(self, position: Position) -> bool:
        """
        Add a new position to portfolio.
        
        Returns:
            True if added successfully
        """
        symbol = position.symbol.upper()
        
        # Validate
        can_add, reason = self.can_add_position(
            symbol, 
            position.sector, 
            position.cost_basis
        )
        
        if not can_add:
            logger.warning(f"Cannot add position: {reason}")
            return False
        
        # Deduct cash
        if self.cash < position.cost_basis:
            logger.warning(f"Insufficient cash for {symbol}")
            return False
        
        self.cash -= position.cost_basis
        
        # Initialize current price
        if position.current_price == 0:
            position.current_price = position.entry_price
        
        # Add position
        self.positions[symbol] = position
        self.trades_today += 1
        
        logger.info(
            f"Added position: {position.shares} {symbol} @ {position.entry_price:.2f} "
            f"(SL: {position.stop_loss:.2f}, TP: {position.target_price:.2f})"
        )
        
        return True
    
    def close_position(
        self, 
        symbol: str, 
        exit_price: float, 
        reason: str = "Manual"
    ) -> Optional[Position]:
        """
        Close a position.
        
        Returns:
            Closed position or None
        """
        symbol = symbol.upper()
        
        if symbol not in self.positions:
            logger.warning(f"No position found for {symbol}")
            return None
        
        position = self.positions.pop(symbol)
        position.close(exit_price, reason)
        
        # Add cash from sale (minus transaction costs)
        sale_value = position.shares * exit_price
        transaction_cost = sale_value * settings.total_transaction_cost_pct
        net_sale_value = sale_value - transaction_cost
        
        self.cash += net_sale_value
        
        # Move to closed positions
        self.closed_positions.append(position)
        self.trades_today += 1
        
        logger.info(
            f"Closed position: {symbol} @ {exit_price:.2f} "
            f"P&L: {position.realized_pnl:+,.2f} ({position.unrealized_pnl_pct:+.2f}%)"
        )
        
        return position
    
    def update_prices(self, prices: Dict[str, float]):
        """
        Update current prices for all positions.
        
        Args:
            prices: Dict of symbol -> current price
        """
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_price(prices[symbol])
        
        # Update position sizer with new portfolio value
        self.sizer.update_portfolio_value(self.total_value)
    
    def check_stop_losses(self) -> List[str]:
        """
        Check which positions have hit stop loss.
        
        Returns:
            List of symbols that hit stop loss
        """
        triggered = []
        
        for symbol, position in self.positions.items():
            if position.hit_stop_loss:
                triggered.append(symbol)
                logger.warning(
                    f"⚠️ STOP LOSS HIT: {symbol} "
                    f"(Price: {position.current_price:.2f}, SL: {position.stop_loss:.2f})"
                )
        
        return triggered
    
    def check_targets(self) -> List[str]:
        """
        Check which positions have hit target.
        
        Returns:
            List of symbols that hit target
        """
        triggered = []
        
        for symbol, position in self.positions.items():
            if position.hit_target:
                triggered.append(symbol)
                logger.info(
                    f"🎯 TARGET HIT: {symbol} "
                    f"(Price: {position.current_price:.2f}, Target: {position.target_price:.2f})"
                )
        
        return triggered
    
    def get_positions_to_exit(self) -> List[Tuple[str, str]]:
        """
        Get positions that should be exited.
        
        Returns:
            List of (symbol, reason) tuples
        """
        to_exit = []
        
        for symbol in self.check_stop_losses():
            to_exit.append((symbol, "Stop Loss Hit"))
        
        for symbol in self.check_targets():
            to_exit.append((symbol, "Target Hit"))
        
        return to_exit
    
    def take_snapshot(self):
        """Take a snapshot of current portfolio state."""
        sector_exposure = self.get_sector_exposure()
        
        largest_position_pct = 0
        if self.positions:
            largest = max(self.positions.values(), key=lambda p: p.current_value)
            largest_position_pct = largest.current_value / self.total_value * 100
        
        snapshot = PortfolioSnapshot(
            date=date.today(),
            total_value=self.total_value,
            cash=self.cash,
            positions_value=self.positions_value,
            unrealized_pnl=self.unrealized_pnl,
            realized_pnl=self.realized_pnl,
            num_positions=len(self.positions),
            largest_position_pct=largest_position_pct,
            sector_concentration=sector_exposure,
            cash_pct=self.cash_pct,
        )
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def get_equity_curve(self) -> pd.Series:
        """Get equity curve from snapshots."""
        if not self.snapshots:
            return pd.Series()
        
        data = {s.date: s.total_value for s in self.snapshots}
        return pd.Series(data).sort_index()
    
    def get_open_positions_df(self) -> pd.DataFrame:
        """Get open positions as DataFrame."""
        if not self.positions:
            return pd.DataFrame()
        
        records = []
        for symbol, p in self.positions.items():
            records.append({
                "symbol": symbol,
                "shares": p.shares,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "cost_basis": p.cost_basis,
                "current_value": p.current_value,
                "unrealized_pnl": p.unrealized_pnl,
                "pnl_pct": p.unrealized_pnl_pct,
                "stop_loss": p.stop_loss,
                "target": p.target_price,
                "sector": p.sector,
                "holding_days": p.holding_days,
            })
        
        return pd.DataFrame(records)
    
    def get_closed_positions_df(self) -> pd.DataFrame:
        """Get closed positions as DataFrame."""
        if not self.closed_positions:
            return pd.DataFrame()
        
        records = []
        for p in self.closed_positions:
            records.append({
                "symbol": p.symbol,
                "shares": p.shares,
                "entry_price": p.entry_price,
                "exit_price": p.exit_price,
                "entry_date": p.entry_date,
                "exit_date": p.exit_date,
                "realized_pnl": p.realized_pnl,
                "pnl_pct": (p.exit_price - p.entry_price) / p.entry_price * 100 if p.exit_price else 0,
                "holding_days": p.holding_days,
                "exit_reason": p.exit_reason,
            })
        
        return pd.DataFrame(records)
    
    def print_summary(self) -> str:
        """Print portfolio summary."""
        summary = f"""
╔══════════════════════════════════════════════════════════════╗
║                    PORTFOLIO SUMMARY                         ║
╠══════════════════════════════════════════════════════════════╣
║ Total Value:      Rs. {self.total_value:>15,.2f}              ║
║ Cash:             Rs. {self.cash:>15,.2f} ({self.cash_pct:.1f}%)        ║
║ Positions Value:  Rs. {self.positions_value:>15,.2f} ({self.invested_pct:.1f}%)    ║
╠══════════════════════════════════════════════════════════════╣
║ Unrealized P&L:   Rs. {self.unrealized_pnl:>+15,.2f}              ║
║ Realized P&L:     Rs. {self.realized_pnl:>+15,.2f}              ║
║ Total Return:         {self.return_pct:>+10.2f}%                  ║
╠══════════════════════════════════════════════════════════════╣
║ Open Positions:   {len(self.positions):>3} / {self.max_positions}                           ║
║ Closed Trades:    {len(self.closed_positions):>3}                                  ║
╚══════════════════════════════════════════════════════════════╝
"""
        
        # Add position details
        if self.positions:
            summary += "\n📊 OPEN POSITIONS:\n"
            summary += "-" * 70 + "\n"
            
            for symbol, p in self.positions.items():
                pnl_emoji = "🟢" if p.is_profitable else "🔴"
                summary += (
                    f"{pnl_emoji} {symbol:8} | {p.shares:5} @ Rs.{p.entry_price:8.2f} "
                    f"→ Rs.{p.current_price:8.2f} | P&L: {p.unrealized_pnl:+10,.2f} "
                    f"({p.unrealized_pnl_pct:+6.2f}%)\n"
                )
        
        # Sector exposure
        sector_exposure = self.get_sector_exposure()
        if sector_exposure:
            summary += "\n📈 SECTOR EXPOSURE:\n"
            for sector, exp in sorted(sector_exposure.items(), key=lambda x: -x[1]):
                bar = "█" * int(exp * 20)
                summary += f"   {sector:25} {bar} {exp:.1%}\n"
        
        print(summary)
        return summary
    
    def reset_daily(self):
        """Reset daily counters (call at start of trading day)."""
        self.trades_today = 0


# Type hint for Tuple
from typing import Tuple
