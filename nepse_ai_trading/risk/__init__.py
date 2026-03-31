"""
Risk Management Module.

Provides position sizing, portfolio management, risk limits,
ATR-based dynamic stops, trailing stops, and portfolio risk enforcement.

RULES:
1. Never risk more than 2% per trade
2. Max 5 concurrent positions
3. Max 30% in single sector
4. Stop trading at 20% drawdown
5. Min 20% cash reserve
6. T+2 settlement: no exit within 3 trading days
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

from .atr_stops import (
    StopState,
    create_stop_state,
    update_stop_state,
    compute_initial_stop,
    compute_trailing_stop,
)

from .portfolio_risk_engine import (
    PortfolioRiskEngine,
    PreTradeResult,
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
    # ATR Stops
    "StopState",
    "create_stop_state",
    "update_stop_state",
    "compute_initial_stop",
    "compute_trailing_stop",
    # Portfolio Risk Engine
    "PortfolioRiskEngine",
    "PreTradeResult",
]
