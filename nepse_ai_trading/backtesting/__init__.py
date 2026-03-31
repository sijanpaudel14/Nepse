"""
Backtesting Module.

Validates trading strategies on historical data before risking real capital.

Includes:
- SimpleBacktest: Institutional-grade bar-by-bar backtesting engine
- walk_forward_backtest: Walk-forward validation
- monte_carlo_test: Statistical edge verification
- compare_strategies: Multi-strategy comparison framework
- MetricsCalculator: Professional-grade performance metrics
- StrategyOptimizer: Parameter optimization with overfitting protection
"""

from .engine import (
    SimpleBacktest,
    BacktestConfig,
    BacktestResult,
    Trade,
    walk_forward_backtest,
    monte_carlo_test,
    compare_strategies,
    quick_backtest,
    volume_slippage,
)

from .metrics import (
    MetricsCalculator,
    BacktestMetrics,
    TradeResult,
    quick_metrics,
)

from .optimizer import (
    StrategyOptimizer,
    OptimizationResult,
    ParameterRange,
)

__all__ = [
    # Engine
    "SimpleBacktest",
    "BacktestConfig",
    "BacktestResult",
    "Trade",
    "walk_forward_backtest",
    "monte_carlo_test",
    "compare_strategies",
    "quick_backtest",
    "volume_slippage",
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
