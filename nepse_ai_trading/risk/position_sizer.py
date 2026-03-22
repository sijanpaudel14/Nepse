"""
Position Sizing Module.

Calculates how many shares to buy for each trade based on:
1. Account size
2. Risk tolerance
3. Stop loss distance
4. Volatility

CRITICAL RULE: Never risk more than 2% of capital on a single trade.
This is the single most important rule for long-term survival.

Why 2%? 
- 10 losing trades in a row = 20% drawdown (recoverable)
- 10 losing trades at 5% risk each = 50% drawdown (devastating)
- Professional traders often use 0.5-1% per trade

NEPSE CONSIDERATIONS:
- No fractional shares (must buy whole lots)
- Minimum trade size varies by broker
- Transaction costs: 0.4% broker + 0.015% SEBON + slippage
- Circuit breakers: 10% daily limit
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum
from loguru import logger

from core.config import settings


class SizingMethod(Enum):
    """Position sizing methods available."""
    FIXED_AMOUNT = "fixed_amount"       # Fixed Rs. amount per trade
    FIXED_PERCENT = "fixed_percent"     # Fixed % of portfolio per trade
    RISK_PERCENT = "risk_percent"       # Risk X% of portfolio (needs stop loss)
    KELLY = "kelly"                     # Kelly Criterion (aggressive)
    VOLATILITY = "volatility"           # Volatility-adjusted sizing
    EQUAL_WEIGHT = "equal_weight"       # Equal weight across positions


@dataclass
class PositionSize:
    """Result of position sizing calculation."""
    symbol: str
    shares: int                         # Number of shares to buy
    entry_price: float                  # Expected entry price
    position_value: float               # Total position value (shares * price)
    risk_amount: float                  # Maximum Rs. at risk
    risk_percent: float                 # % of portfolio at risk
    stop_loss: float                    # Stop loss price
    sizing_method: str                  # Method used
    
    # For millionaire tracking
    expected_profit: Optional[float] = None      # If target hit
    expected_loss: Optional[float] = None        # If stop hit
    risk_reward_ratio: Optional[float] = None    # Reward / Risk
    
    def is_valid(self) -> bool:
        """Check if position size is valid."""
        return (
            self.shares > 0 and
            self.position_value > 0 and
            self.risk_percent <= settings.max_risk_per_trade_pct
        )
    
    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"📊 Position: {self.symbol}\n"
            f"   Shares: {self.shares:,}\n"
            f"   Entry: Rs. {self.entry_price:,.2f}\n"
            f"   Value: Rs. {self.position_value:,.2f}\n"
            f"   Stop Loss: Rs. {self.stop_loss:,.2f}\n"
            f"   Risk: Rs. {self.risk_amount:,.2f} ({self.risk_percent:.2f}%)\n"
            f"   R:R Ratio: {self.risk_reward_ratio:.2f}" if self.risk_reward_ratio else ""
        )


class PositionSizer:
    """
    Calculates optimal position sizes based on risk management rules.
    
    The Golden Rule: NEVER risk more than 2% on a single trade.
    
    Usage:
        sizer = PositionSizer(portfolio_value=500_000)
        
        position = sizer.calculate(
            symbol="NABIL",
            entry_price=1200,
            stop_loss=1140,  # 5% below entry
            target_price=1320,  # 10% above entry
        )
        
        print(f"Buy {position.shares} shares of NABIL")
    """
    
    def __init__(
        self,
        portfolio_value: float,
        max_risk_per_trade: float = 0.02,  # 2% default
        max_position_size: float = 0.20,    # Max 20% in single position
        method: SizingMethod = SizingMethod.RISK_PERCENT,
    ):
        """
        Args:
            portfolio_value: Total portfolio value in Rs.
            max_risk_per_trade: Maximum risk per trade (default 2%)
            max_position_size: Maximum position size as % of portfolio
            method: Sizing method to use
        """
        self.portfolio_value = portfolio_value
        self.max_risk_per_trade = max_risk_per_trade
        self.max_position_size = max_position_size
        self.method = method
        
        # Calculate derived values
        self.max_risk_amount = portfolio_value * max_risk_per_trade
        self.max_position_value = portfolio_value * max_position_size
        
        logger.debug(
            f"PositionSizer initialized: Portfolio={portfolio_value:,.0f}, "
            f"MaxRisk={self.max_risk_amount:,.0f}, MaxPosition={self.max_position_value:,.0f}"
        )
    
    def calculate(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        target_price: Optional[float] = None,
        atr: Optional[float] = None,
        win_rate: Optional[float] = None,
    ) -> PositionSize:
        """
        Calculate position size for a trade.
        
        Args:
            symbol: Stock symbol
            entry_price: Expected entry price
            stop_loss: Stop loss price
            target_price: Take profit target (optional)
            atr: Average True Range for volatility sizing (optional)
            win_rate: Historical win rate for Kelly sizing (optional)
            
        Returns:
            PositionSize with calculated values
        """
        if entry_price <= 0 or stop_loss <= 0:
            raise ValueError("Prices must be positive")
        
        if stop_loss >= entry_price:
            raise ValueError("Stop loss must be below entry price for long positions")
        
        # Calculate risk per share
        risk_per_share = entry_price - stop_loss
        risk_percent_per_share = risk_per_share / entry_price * 100
        
        # Choose sizing method
        if self.method == SizingMethod.RISK_PERCENT:
            shares, risk_amount = self._size_by_risk(entry_price, risk_per_share)
        elif self.method == SizingMethod.VOLATILITY and atr:
            shares, risk_amount = self._size_by_volatility(entry_price, atr)
        elif self.method == SizingMethod.KELLY and win_rate:
            shares, risk_amount = self._size_by_kelly(entry_price, risk_per_share, win_rate)
        elif self.method == SizingMethod.FIXED_PERCENT:
            shares, risk_amount = self._size_fixed_percent(entry_price)
        else:
            # Default to risk-based
            shares, risk_amount = self._size_by_risk(entry_price, risk_per_share)
        
        # Ensure whole shares (NEPSE requirement)
        shares = int(shares)
        
        # Apply maximum position size limit
        max_shares_by_position = int(self.max_position_value / entry_price)
        shares = min(shares, max_shares_by_position)
        
        # Ensure at least 1 share if any position is valid
        if shares == 0 and self.portfolio_value > entry_price:
            shares = 1
        
        # Recalculate actual values
        position_value = shares * entry_price
        actual_risk_amount = shares * risk_per_share
        actual_risk_percent = actual_risk_amount / self.portfolio_value * 100
        
        # Calculate expected P&L
        expected_profit = None
        expected_loss = None
        risk_reward = None
        
        if target_price:
            expected_profit = shares * (target_price - entry_price)
            expected_loss = actual_risk_amount
            risk_reward = expected_profit / expected_loss if expected_loss > 0 else 0
        
        return PositionSize(
            symbol=symbol,
            shares=shares,
            entry_price=entry_price,
            position_value=position_value,
            risk_amount=actual_risk_amount,
            risk_percent=actual_risk_percent,
            stop_loss=stop_loss,
            sizing_method=self.method.value,
            expected_profit=expected_profit,
            expected_loss=expected_loss,
            risk_reward_ratio=risk_reward,
        )
    
    def _size_by_risk(
        self, 
        entry_price: float, 
        risk_per_share: float
    ) -> Tuple[int, float]:
        """
        Position sizing based on fixed % risk.
        
        Formula: Shares = (Portfolio * Risk%) / (Entry - StopLoss)
        
        This is the SAFEST method - recommended for NEPSE trading.
        """
        if risk_per_share <= 0:
            return 0, 0
        
        shares = self.max_risk_amount / risk_per_share
        risk_amount = shares * risk_per_share
        
        return int(shares), risk_amount
    
    def _size_by_volatility(
        self, 
        entry_price: float, 
        atr: float,
        atr_multiplier: float = 2.0,
    ) -> Tuple[int, float]:
        """
        Volatility-adjusted position sizing using ATR.
        
        Smaller positions in volatile stocks, larger in stable ones.
        
        Formula: Shares = (Portfolio * Risk%) / (ATR * Multiplier)
        """
        if atr <= 0:
            return 0, 0
        
        risk_per_share = atr * atr_multiplier
        shares = self.max_risk_amount / risk_per_share
        risk_amount = shares * risk_per_share
        
        return int(shares), risk_amount
    
    def _size_by_kelly(
        self,
        entry_price: float,
        risk_per_share: float,
        win_rate: float,
        profit_factor: float = 2.0,  # Avg win / Avg loss
    ) -> Tuple[int, float]:
        """
        Kelly Criterion position sizing.
        
        Mathematically optimal but VERY aggressive. We use Half-Kelly.
        
        Formula: Kelly% = W - (1-W)/R
        Where W = win rate, R = profit factor
        
        WARNING: Full Kelly can cause huge drawdowns!
        We use Half-Kelly (Kelly / 2) for safety.
        """
        if risk_per_share <= 0 or win_rate <= 0:
            return 0, 0
        
        # Kelly percentage (using simplified formula)
        w = win_rate / 100  # Convert to decimal
        r = profit_factor
        
        kelly_pct = w - ((1 - w) / r)
        
        # Sanity checks
        kelly_pct = max(0, min(kelly_pct, 0.25))  # Cap at 25%
        
        # Use Half-Kelly for safety
        half_kelly_pct = kelly_pct / 2
        
        # Apply to portfolio
        position_value = self.portfolio_value * half_kelly_pct
        shares = position_value / entry_price
        risk_amount = shares * risk_per_share
        
        logger.debug(f"Kelly: {kelly_pct:.1%} → Half-Kelly: {half_kelly_pct:.1%}")
        
        return int(shares), risk_amount
    
    def _size_fixed_percent(
        self,
        entry_price: float,
        percent: float = 0.10,  # 10% of portfolio per position
    ) -> Tuple[int, float]:
        """
        Fixed percentage of portfolio per position.
        
        Simple but doesn't account for risk/stop loss.
        """
        position_value = self.portfolio_value * percent
        shares = position_value / entry_price
        
        # Risk is entire position (since no stop loss used)
        risk_amount = position_value * 0.1  # Assume 10% potential loss
        
        return int(shares), risk_amount
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        method: str = "percent",
        value: float = 5.0,  # 5% for percent method
        atr: Optional[float] = None,
    ) -> float:
        """
        Calculate stop loss price.
        
        Methods:
        - percent: Fixed percentage below entry (default 5%)
        - atr: ATR-based stop (value = ATR multiplier)
        - support: Place at nearest support level (not implemented here)
        """
        if method == "percent":
            return entry_price * (1 - value / 100)
        elif method == "atr" and atr:
            return entry_price - (atr * value)
        else:
            # Default 5% stop
            return entry_price * 0.95
    
    def update_portfolio_value(self, new_value: float):
        """Update portfolio value (call after P&L changes)."""
        self.portfolio_value = new_value
        self.max_risk_amount = new_value * self.max_risk_per_trade
        self.max_position_value = new_value * self.max_position_size


def calculate_position_for_signal(
    signal,  # TradingSignal from signal_aggregator
    portfolio_value: float,
    risk_percent: float = 2.0,
) -> PositionSize:
    """
    Convenience function to size a position from a trading signal.
    
    Args:
        signal: TradingSignal with entry, stop_loss, target
        portfolio_value: Current portfolio value
        risk_percent: Risk percentage per trade
        
    Returns:
        PositionSize
    """
    sizer = PositionSizer(
        portfolio_value=portfolio_value,
        max_risk_per_trade=risk_percent / 100,
    )
    
    return sizer.calculate(
        symbol=signal.symbol,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        target_price=signal.target_price,
    )


# Quick calculation functions for the CLI

def quick_position_size(
    portfolio: float,
    entry: float,
    stop: float,
    risk_pct: float = 2.0,
) -> int:
    """Quick position size calculation."""
    risk_amount = portfolio * (risk_pct / 100)
    risk_per_share = entry - stop
    
    if risk_per_share <= 0:
        return 0
    
    shares = risk_amount / risk_per_share
    return int(shares)


def how_many_shares(
    portfolio: float,
    entry: float,
    stop_pct: float = 5.0,
    risk_pct: float = 2.0,
) -> dict:
    """
    Answer: "How many shares should I buy?"
    
    Example:
        >>> how_many_shares(500000, 1200, 5, 2)
        {'shares': 166, 'position_value': 199200, 'risk': 9960}
    """
    stop = entry * (1 - stop_pct / 100)
    shares = quick_position_size(portfolio, entry, stop, risk_pct)
    
    return {
        "shares": shares,
        "position_value": shares * entry,
        "risk": shares * (entry - stop),
        "stop_loss": stop,
    }
