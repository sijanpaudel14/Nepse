"""
Backtesting Module.

Validates trading strategies on historical data before risking real capital.

Includes:
- SimpleBacktest: Fast vectorized backtesting engine
- MetricsCalculator: Professional-grade performance metrics
- StrategyOptimizer: Parameter optimization with overfitting protection
"""

from backtesting.engine import (
    SimpleBacktest,
    BacktestConfig,
    BacktestResult,
)

from backtesting.metrics import (
    MetricsCalculator,
    BacktestMetrics,
    TradeResult,
    quick_metrics,
)

from backtesting.optimizer import (
    StrategyOptimizer,
    OptimizationResult,
    ParameterRange,
)

__all__ = [
    # Engine
    "SimpleBacktest",
    "BacktestConfig",
    "BacktestResult",
    # Metrics
    "MetricsCalculator",
    "BacktestMetrics",
    "TradeResult",
    "quick_metrics",
    # Optimizer
    "StrategyOptimizer",
    "OptimizationResult",
    "ParameterRange",
]
