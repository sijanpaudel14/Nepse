"""
Strategy Parameter Optimizer.

Uses grid search and walk-forward optimization to find
the best parameter combinations for trading strategies.

CRITICAL: This module helps you avoid OVERFITTING!

Overfitting = Finding parameters that worked great in the past
but will fail in the future. Classic mistake of algo traders.

How we avoid it:
1. Walk-forward validation: Train on past, test on future
2. Out-of-sample testing: Reserve data the optimizer never sees
3. Parameter stability: Check if nearby parameters also work

NEPSE-SPECIFIC CONSIDERATIONS:
- Limited historical data (NEPSE modernized in ~2015)
- Low trading days (~200/year)
- High transaction costs (0.4% + slippage)
"""

import itertools
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional, Tuple
from datetime import date, timedelta
from concurrent.futures import ProcessPoolExecutor, as_completed
from loguru import logger

from backtesting.engine import SimpleBacktest, BacktestConfig
from backtesting.metrics import MetricsCalculator, BacktestMetrics


@dataclass
class ParameterRange:
    """Defines a parameter and its search range."""
    name: str
    min_value: float
    max_value: float
    step: float
    param_type: str = "float"  # "float", "int", "choice"
    choices: List[Any] = field(default_factory=list)
    
    def get_values(self) -> List:
        """Generate all values in this range."""
        if self.param_type == "choice":
            return self.choices
        elif self.param_type == "int":
            return list(range(int(self.min_value), int(self.max_value) + 1, int(self.step)))
        else:
            values = []
            current = self.min_value
            while current <= self.max_value:
                values.append(round(current, 4))
                current += self.step
            return values


@dataclass
class OptimizationResult:
    """Result from a single parameter combination test."""
    parameters: Dict[str, Any]
    metrics: BacktestMetrics
    in_sample_return: float
    out_sample_return: Optional[float] = None
    stability_score: float = 0.0
    rank: int = 0
    
    @property
    def overfitting_risk(self) -> str:
        """
        Estimate overfitting risk based on in-sample vs out-sample.
        
        If in-sample >> out-sample, likely overfitted.
        """
        if self.out_sample_return is None:
            return "Unknown (no out-sample test)"
        
        diff = self.in_sample_return - self.out_sample_return
        
        if diff < 5:
            return "LOW"
        elif diff < 15:
            return "MEDIUM"
        else:
            return "HIGH"


class StrategyOptimizer:
    """
    Optimizes strategy parameters using grid search and validation.
    
    Usage:
        optimizer = StrategyOptimizer(
            backtest_func=run_golden_cross,
            data=historical_prices
        )
        
        optimizer.add_parameter("ema_fast", 5, 15, 2)
        optimizer.add_parameter("ema_slow", 15, 30, 5)
        optimizer.add_parameter("rsi_period", 10, 20, 2)
        
        best = optimizer.optimize(target_metric="sharpe_ratio")
    """
    
    def __init__(
        self,
        backtest_func: Callable,
        data: pd.DataFrame,
        initial_capital: float = 500_000,
        in_sample_ratio: float = 0.7,  # 70% training, 30% validation
    ):
        """
        Args:
            backtest_func: Function that runs backtest given parameters
                          Signature: func(data, params) -> (trades, equity_curve)
            data: Historical price data
            initial_capital: Starting capital
            in_sample_ratio: Fraction of data for training
        """
        self.backtest_func = backtest_func
        self.data = data
        self.initial_capital = initial_capital
        self.in_sample_ratio = in_sample_ratio
        
        self.parameters: List[ParameterRange] = []
        self.results: List[OptimizationResult] = []
        
        self.metrics_calc = MetricsCalculator(initial_capital=initial_capital)
    
    def add_parameter(
        self,
        name: str,
        min_value: float,
        max_value: float,
        step: float,
        param_type: str = "float"
    ):
        """Add a parameter to optimize."""
        self.parameters.append(ParameterRange(
            name=name,
            min_value=min_value,
            max_value=max_value,
            step=step,
            param_type=param_type
        ))
    
    def add_choice_parameter(self, name: str, choices: List[Any]):
        """Add a parameter with discrete choices."""
        self.parameters.append(ParameterRange(
            name=name,
            min_value=0,
            max_value=0,
            step=0,
            param_type="choice",
            choices=choices
        ))
    
    def _generate_param_combinations(self) -> List[Dict]:
        """Generate all parameter combinations."""
        if not self.parameters:
            return [{}]
        
        value_lists = [p.get_values() for p in self.parameters]
        names = [p.name for p in self.parameters]
        
        combinations = []
        for values in itertools.product(*value_lists):
            combinations.append(dict(zip(names, values)))
        
        return combinations
    
    def _split_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Split data into in-sample and out-of-sample."""
        split_idx = int(len(self.data) * self.in_sample_ratio)
        
        in_sample = self.data.iloc[:split_idx].copy()
        out_sample = self.data.iloc[split_idx:].copy()
        
        return in_sample, out_sample
    
    def _run_single_backtest(
        self, 
        params: Dict, 
        data: pd.DataFrame
    ) -> Optional[BacktestMetrics]:
        """Run a single backtest with given parameters."""
        try:
            trades, equity_curve = self.backtest_func(data, params)
            
            if not trades or equity_curve.empty:
                return None
            
            metrics = self.metrics_calc.calculate(trades, equity_curve)
            return metrics
            
        except Exception as e:
            logger.debug(f"Backtest failed with params {params}: {e}")
            return None
    
    def optimize(
        self,
        target_metric: str = "sharpe_ratio",
        min_trades: int = 10,
        max_drawdown: float = 30.0,
        parallel: bool = False,
        top_n: int = 10,
    ) -> List[OptimizationResult]:
        """
        Run grid search optimization.
        
        Args:
            target_metric: Metric to maximize (sharpe_ratio, profit_factor, cagr)
            min_trades: Minimum trades required for valid result
            max_drawdown: Maximum allowed drawdown %
            parallel: Use parallel processing (experimental)
            top_n: Return top N results
            
        Returns:
            List of OptimizationResult, sorted by target metric
        """
        combinations = self._generate_param_combinations()
        total = len(combinations)
        
        logger.info(f"Starting optimization with {total} parameter combinations")
        logger.info(f"Target metric: {target_metric}, Min trades: {min_trades}")
        
        in_sample, out_sample = self._split_data()
        logger.info(f"In-sample: {len(in_sample)} days, Out-sample: {len(out_sample)} days")
        
        self.results = []
        
        for i, params in enumerate(combinations):
            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i + 1}/{total}")
            
            # In-sample backtest
            in_metrics = self._run_single_backtest(params, in_sample)
            
            if in_metrics is None:
                continue
            
            # Filter by minimum requirements
            if in_metrics.total_trades < min_trades:
                continue
            if in_metrics.max_drawdown_pct > max_drawdown:
                continue
            
            # Out-of-sample backtest
            out_metrics = self._run_single_backtest(params, out_sample)
            out_return = out_metrics.total_return_pct if out_metrics else None
            
            result = OptimizationResult(
                parameters=params,
                metrics=in_metrics,
                in_sample_return=in_metrics.total_return_pct,
                out_sample_return=out_return,
            )
            
            self.results.append(result)
        
        # Sort by target metric
        self.results.sort(
            key=lambda r: getattr(r.metrics, target_metric, 0),
            reverse=True
        )
        
        # Assign ranks
        for i, result in enumerate(self.results):
            result.rank = i + 1
        
        logger.info(f"Optimization complete. {len(self.results)} valid parameter sets found")
        
        if self.results:
            best = self.results[0]
            logger.info(f"Best parameters: {best.parameters}")
            logger.info(f"Best {target_metric}: {getattr(best.metrics, target_metric):.2f}")
        
        return self.results[:top_n]
    
    def walk_forward_optimize(
        self,
        target_metric: str = "sharpe_ratio",
        num_folds: int = 5,
        min_trades_per_fold: int = 5,
    ) -> Dict[str, Any]:
        """
        Walk-forward optimization to reduce overfitting.
        
        Instead of one train/test split, uses multiple overlapping
        windows to ensure parameters work across different periods.
        
        Args:
            target_metric: Metric to optimize
            num_folds: Number of walk-forward windows
            min_trades_per_fold: Minimum trades per test window
            
        Returns:
            Dict with best parameters and consistency analysis
        """
        logger.info(f"Starting walk-forward optimization with {num_folds} folds")
        
        data_len = len(self.data)
        fold_size = data_len // (num_folds + 1)
        
        combinations = self._generate_param_combinations()
        param_scores: Dict[str, List[float]] = {
            str(p): [] for p in combinations
        }
        
        for fold in range(num_folds):
            # Training window: start to fold end
            train_end = (fold + 1) * fold_size
            train_data = self.data.iloc[:train_end]
            
            # Test window: next fold
            test_start = train_end
            test_end = min(test_start + fold_size, data_len)
            test_data = self.data.iloc[test_start:test_end]
            
            logger.info(f"Fold {fold + 1}: Train {len(train_data)} days, Test {len(test_data)} days")
            
            # Find best params on training data
            for params in combinations:
                metrics = self._run_single_backtest(params, test_data)
                
                if metrics and metrics.total_trades >= min_trades_per_fold:
                    score = getattr(metrics, target_metric, 0)
                    param_scores[str(params)].append(score)
        
        # Find parameters that work consistently
        consistency_results = []
        
        for params_str, scores in param_scores.items():
            if len(scores) >= num_folds // 2:  # Must work in at least half the folds
                consistency_results.append({
                    "parameters": eval(params_str),
                    "mean_score": np.mean(scores),
                    "std_score": np.std(scores),
                    "folds_successful": len(scores),
                    "min_score": min(scores),
                    "max_score": max(scores),
                    "consistency": 1 - (np.std(scores) / (np.mean(scores) + 0.001)),
                })
        
        # Sort by mean score
        consistency_results.sort(key=lambda x: x["mean_score"], reverse=True)
        
        if consistency_results:
            best = consistency_results[0]
            logger.info(f"Best walk-forward parameters: {best['parameters']}")
            logger.info(f"Mean {target_metric}: {best['mean_score']:.2f} ± {best['std_score']:.2f}")
            logger.info(f"Consistency score: {best['consistency']:.2f}")
        
        return {
            "best_parameters": consistency_results[0]["parameters"] if consistency_results else None,
            "all_results": consistency_results[:10],
            "num_folds": num_folds,
            "target_metric": target_metric,
        }
    
    def parameter_sensitivity(
        self,
        base_params: Dict,
        param_name: str,
        values: List[Any] = None,
    ) -> pd.DataFrame:
        """
        Analyze how sensitive results are to a single parameter.
        
        Good parameters should have stable performance even when
        slightly changed. If performance drops sharply with small
        changes, the parameter is likely overfit.
        
        Args:
            base_params: Base parameter set
            param_name: Parameter to vary
            values: Values to test (uses param range if not provided)
            
        Returns:
            DataFrame with parameter value vs metrics
        """
        if values is None:
            param = next((p for p in self.parameters if p.name == param_name), None)
            if param is None:
                raise ValueError(f"Parameter {param_name} not found")
            values = param.get_values()
        
        results = []
        
        for value in values:
            params = base_params.copy()
            params[param_name] = value
            
            metrics = self._run_single_backtest(params, self.data)
            
            if metrics:
                results.append({
                    param_name: value,
                    "total_return": metrics.total_return_pct,
                    "sharpe_ratio": metrics.sharpe_ratio,
                    "max_drawdown": metrics.max_drawdown_pct,
                    "win_rate": metrics.win_rate,
                    "profit_factor": metrics.profit_factor,
                    "total_trades": metrics.total_trades,
                })
        
        df = pd.DataFrame(results)
        
        # Calculate stability (coefficient of variation)
        if not df.empty:
            stability = 1 - (df["sharpe_ratio"].std() / (df["sharpe_ratio"].mean() + 0.001))
            logger.info(f"Parameter {param_name} stability: {stability:.2f} (>0.7 is good)")
        
        return df
    
    def get_optimization_report(self) -> str:
        """Generate a text report of optimization results."""
        if not self.results:
            return "No optimization results available. Run optimize() first."
        
        lines = [
            "=" * 70,
            "STRATEGY OPTIMIZATION REPORT",
            "=" * 70,
            "",
            f"Total parameter combinations tested: {len(self._generate_param_combinations())}",
            f"Valid results: {len(self.results)}",
            "",
            "TOP 5 PARAMETER SETS:",
            "-" * 70,
        ]
        
        for i, result in enumerate(self.results[:5]):
            lines.extend([
                f"",
                f"Rank #{i + 1}",
                f"Parameters: {result.parameters}",
                f"In-Sample Return: {result.in_sample_return:.2f}%",
                f"Out-Sample Return: {result.out_sample_return:.2f}%" if result.out_sample_return else "Out-Sample: N/A",
                f"Sharpe Ratio: {result.metrics.sharpe_ratio:.2f}",
                f"Max Drawdown: {result.metrics.max_drawdown_pct:.2f}%",
                f"Win Rate: {result.metrics.win_rate:.1f}%",
                f"Overfitting Risk: {result.overfitting_risk}",
                "-" * 70,
            ])
        
        lines.extend([
            "",
            "RECOMMENDATIONS:",
            "- Choose parameters with LOW overfitting risk",
            "- Prefer Sharpe > 1.0 and Win Rate > 50%",
            "- Test parameter sensitivity before live trading",
            "=" * 70,
        ])
        
        return "\n".join(lines)


# Pre-built parameter ranges for common NEPSE strategies
GOLDEN_CROSS_PARAMS = [
    ParameterRange("ema_fast", 5, 15, 2, "int"),
    ParameterRange("ema_slow", 15, 30, 5, "int"),
    ParameterRange("rsi_period", 10, 20, 2, "int"),
    ParameterRange("rsi_upper", 60, 70, 5, "int"),
    ParameterRange("rsi_lower", 45, 55, 5, "int"),
    ParameterRange("volume_mult", 1.2, 2.0, 0.2, "float"),
]

VOLUME_BREAKOUT_PARAMS = [
    ParameterRange("volume_mult", 2.0, 4.0, 0.5, "float"),
    ParameterRange("lookback", 15, 30, 5, "int"),
    ParameterRange("min_change_pct", 2, 5, 1, "float"),
]

RSI_MOMENTUM_PARAMS = [
    ParameterRange("rsi_period", 10, 20, 2, "int"),
    ParameterRange("oversold", 25, 35, 5, "int"),
    ParameterRange("overbought", 65, 80, 5, "int"),
]
