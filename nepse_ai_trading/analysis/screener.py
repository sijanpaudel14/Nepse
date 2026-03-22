"""
Multi-Strategy Stock Screener.

Runs all strategies against all stocks and aggregates signals.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Optional, Type
import pandas as pd
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.config import settings
from core.database import SessionLocal, Stock, DailyPrice
from core.exceptions import InsufficientDataError
from analysis.strategies import BaseStrategy, StrategySignal
from analysis.strategies.golden_cross import GoldenCrossStrategy
from analysis.strategies.volume_breakout import VolumeBreakoutStrategy
from analysis.strategies.rsi_momentum import RSIMomentumStrategy
from analysis.strategies.support_bounce import SupportBounceStrategy


@dataclass
class ScreenerResult:
    """
    Result from the stock screener.
    """
    symbol: str
    signals: List[StrategySignal] = field(default_factory=list)
    combined_confidence: float = 0.0
    primary_signal: Optional[StrategySignal] = None
    
    def __post_init__(self):
        if self.signals:
            # Primary signal is the highest confidence
            self.primary_signal = max(self.signals, key=lambda s: s.confidence)
            
            # Combined confidence: weighted average
            self.combined_confidence = sum(s.confidence for s in self.signals) / len(self.signals)


class StockScreener:
    """
    Multi-strategy stock screener.
    
    Runs all registered strategies against stocks and aggregates results.
    """
    
    # Default strategies to run
    DEFAULT_STRATEGIES: List[Type[BaseStrategy]] = [
        GoldenCrossStrategy,
        VolumeBreakoutStrategy,
        RSIMomentumStrategy,
        SupportBounceStrategy,
    ]
    
    def __init__(
        self, 
        strategies: List[Type[BaseStrategy]] = None,
        max_workers: int = 4,
    ):
        """
        Initialize screener.
        
        Args:
            strategies: List of strategy classes to use
            max_workers: Max parallel workers for screening
        """
        strategy_classes = strategies or self.DEFAULT_STRATEGIES
        self.strategies = [cls() for cls in strategy_classes]
        self.max_workers = max_workers
        
        logger.info(f"Initialized screener with {len(self.strategies)} strategies")
    
    def get_stock_data(self, symbol: str, days: int = None) -> pd.DataFrame:
        """
        Get historical data for a stock from database.
        
        Args:
            symbol: Stock symbol
            days: Number of days of history
            
        Returns:
            DataFrame with OHLCV data
        """
        days = days or settings.lookback_days
        
        db = SessionLocal()
        try:
            stock = db.query(Stock).filter(Stock.symbol == symbol).first()
            if not stock:
                return pd.DataFrame()
            
            # Get recent prices
            prices = (
                db.query(DailyPrice)
                .filter(DailyPrice.stock_id == stock.id)
                .order_by(DailyPrice.date.desc())
                .limit(days)
                .all()
            )
            
            if not prices:
                return pd.DataFrame()
            
            # Convert to DataFrame
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
            
            df = pd.DataFrame(data)
            df = df.sort_values("date").reset_index(drop=True)
            return df
            
        finally:
            db.close()
    
    def screen_stock(self, symbol: str) -> Optional[ScreenerResult]:
        """
        Run all strategies against a single stock.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            ScreenerResult if any signals, None otherwise
        """
        # Get data
        df = self.get_stock_data(symbol)
        
        if df.empty or len(df) < 30:
            logger.debug(f"{symbol}: Insufficient data")
            return None
        
        # Run all strategies
        signals = []
        
        for strategy in self.strategies:
            try:
                signal = strategy.analyze(df, symbol)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.warning(f"{symbol} - {strategy.name} error: {e}")
                continue
        
        if not signals:
            return None
        
        return ScreenerResult(symbol=symbol, signals=signals)
    
    def screen_all(
        self, 
        symbols: List[str] = None,
        min_confidence: float = 5.0,
    ) -> List[ScreenerResult]:
        """
        Screen all stocks in database.
        
        Args:
            symbols: Optional list of symbols to screen (default: all)
            min_confidence: Minimum confidence to include
            
        Returns:
            List of ScreenerResults sorted by confidence
        """
        # Get symbols from database if not provided
        if symbols is None:
            db = SessionLocal()
            try:
                stocks = db.query(Stock).filter(Stock.is_active == True).all()
                symbols = [s.symbol for s in stocks]
            finally:
                db.close()
        
        logger.info(f"Screening {len(symbols)} stocks with {len(self.strategies)} strategies...")
        
        results = []
        
        # Use thread pool for parallel screening
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_symbol = {
                executor.submit(self.screen_stock, symbol): symbol 
                for symbol in symbols
            }
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    if result and result.combined_confidence >= min_confidence:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error screening {symbol}: {e}")
        
        # Sort by combined confidence
        results.sort(key=lambda r: r.combined_confidence, reverse=True)
        
        logger.info(f"Found {len(results)} stocks with signals")
        return results
    
    def get_top_signals(self, limit: int = 5) -> List[ScreenerResult]:
        """
        Get top N signals by confidence.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            Top signals
        """
        results = self.screen_all()
        return results[:limit]
    
    def format_results(self, results: List[ScreenerResult]) -> str:
        """
        Format screening results for display.
        
        Args:
            results: List of ScreenerResults
            
        Returns:
            Formatted string
        """
        if not results:
            return "No signals found."
        
        lines = ["📊 NEPSE TRADING SIGNALS", "=" * 40]
        
        for i, result in enumerate(results, 1):
            signal = result.primary_signal
            if not signal:
                continue
            
            lines.append(f"\n{i}. {result.symbol}")
            lines.append(f"   Signal: {signal.signal_type} ({signal.strategy_name})")
            lines.append(f"   Confidence: {signal.confidence:.1f}/10")
            lines.append(f"   Entry: Rs. {signal.entry_price:.2f}")
            if signal.target_price:
                lines.append(f"   Target: Rs. {signal.target_price:.2f}")
            if signal.stop_loss:
                lines.append(f"   Stop Loss: Rs. {signal.stop_loss:.2f}")
            lines.append(f"   Reason: {signal.reason}")
            
            # Show other signals for same stock
            other_signals = [s for s in result.signals if s != signal]
            if other_signals:
                other_names = [s.strategy_name for s in other_signals]
                lines.append(f"   Also triggered: {', '.join(other_names)}")
        
        return "\n".join(lines)
