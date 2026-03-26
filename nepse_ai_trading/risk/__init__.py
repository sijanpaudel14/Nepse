"""
Risk Management Module.

Provides position sizing, portfolio management, and risk limits
to protect capital and maximize long-term growth.

MILLIONAIRE RULES (embedded in this module):
1. Never risk more than 2% per trade
2. Max 5-7 positions at once
3. Max 30% in single sector
4. Stop trading at 20% drawdown
5. Review after 5 consecutive losses
"""

from .position_sizer import (
    PositionSizer,
    PositionSize,
    SizingMethod,
    quick_position_size,
    how_many_shares,
)

from .portfolio_manager import (
    PortfolioManager,
    Position,
    PositionStatus,
    PortfolioSnapshot,
)

from .risk_limits import (
    RiskManager,
    RiskLimits,
    RiskState,
    RiskAlert,
    check_risk,
)

__all__ = [
    # Position sizing
    "PositionSizer",
    "PositionSize",
    "SizingMethod",
    "quick_position_size",
    "how_many_shares",
    # Portfolio
    "PortfolioManager",
    "Position",
    "PositionStatus",
    "PortfolioSnapshot",
    # Risk limits
    "RiskManager",
    "RiskLimits",
    "RiskState",
    "RiskAlert",
    "check_risk",
]
