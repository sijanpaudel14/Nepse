"""
Technical Indicators module using pandas-ta.
Calculates all indicators needed for trading strategies.

WHY THESE INDICATORS?
- EMA: Exponential Moving Average gives more weight to recent prices,
  making it more responsive to new trends than SMA.
- RSI: Relative Strength Index measures momentum; 50-65 is bullish
  but not overbought (which would be >70).
- MACD: Moving Average Convergence Divergence shows trend direction
  and momentum. Positive histogram = bullish momentum.
- ADX: Average Directional Index measures trend strength.
  ADX > 25 = strong trend worth trading.
- Volume: Confirms price moves. High volume = institutional participation.
"""

from typing import Optional, Tuple, List, Dict
import pandas as pd
import pandas_ta as ta
import numpy as np
from loguru import logger

from core.config import settings


class TechnicalIndicators:
    """
    Calculate technical indicators for a stock's price data.
    Uses pandas-ta for efficient vectorized calculations.
    """
    
    def __init__(self, df: pd.DataFrame):
        """
        Initialize with price data.
        
        Args:
            df: DataFrame with columns: date, open, high, low, close, volume
                Must be sorted by date ascending.
        """
        self.df = df.copy()
        self._validate_data()
        self._ensure_numeric()
    
    def _validate_data(self):
        """Validate input DataFrame has required columns."""
        required = ["date", "open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in self.df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        if len(self.df) < 2:
            raise ValueError("Need at least 2 rows of data")
    
    def _ensure_numeric(self):
        """
        Ensure OHLCV columns are numeric.
        DEFENSIVE: Handle NaN, None, and string values gracefully.
        
        CRITICAL: We DO NOT synthesize missing OHLC data by copying close prices.
        This would create false signals (breakouts, understated ATR).
        Instead, we flag incomplete rows and exclude them from calculations.
        """
        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            self.df[col] = pd.to_numeric(self.df[col], errors="coerce")
        
        # Track which rows have complete OHLC data
        ohlc_cols = ["open", "high", "low", "close"]
        self.df["ohlc_complete"] = ~self.df[ohlc_cols].isna().any(axis=1)
        
        # Count incomplete rows for logging
        incomplete_count = (~self.df["ohlc_complete"]).sum()
        if incomplete_count > 0:
            logger.warning(
                f"OHLC data incomplete: {incomplete_count} rows have missing O/H/L/C values. "
                f"These rows will be excluded from indicator calculations that require complete OHLC."
            )
        
        # For rows with missing OPEN only (common NEPSE API issue):
        # Fill with previous close ONLY if it's a single-column issue
        open_only_missing = self.df["open"].isna() & ~self.df[["high", "low", "close"]].isna().any(axis=1)
        if open_only_missing.any():
            self.df.loc[open_only_missing, "open"] = self.df.loc[open_only_missing, "close"].shift(1)
            # First row gets close if no previous day
            first_idx = self.df.index[0]
            if pd.isna(self.df.loc[first_idx, "open"]):
                self.df.loc[first_idx, "open"] = self.df.loc[first_idx, "close"]
            logger.debug(f"Filled {open_only_missing.sum()} missing OPEN values with previous close (acceptable fallback)")
        
        # For HIGH/LOW: DO NOT fill with close - this understates volatility
        # Instead, mark these rows as incomplete
        hl_missing = self.df["high"].isna() | self.df["low"].isna()
        if hl_missing.any():
            logger.warning(
                f"HIGH/LOW data missing for {hl_missing.sum()} rows. "
                f"ATR and volatility calculations may be affected. Data NOT synthesized."
            )
        
        # Volume: Fill with 0 (acceptable - indicates trading halt or no data)
        self.df["volume"] = self.df["volume"].fillna(0)
        
        # Only drop rows missing CLOSE (essential for all calculations)
        essential_cols = ["close"]
        rows_before = len(self.df)
        self.df = self.df.dropna(subset=essential_cols)
        rows_dropped = rows_before - len(self.df)
        if rows_dropped > 0:
            logger.warning(f"Dropped {rows_dropped} rows missing CLOSE price (essential data)")
    
    def has_sufficient_data(self, min_rows: int) -> bool:
        """
        Check if DataFrame has enough rows for a given indicator.
        DEFENSIVE: Use this before calculating indicators.
        """
        return len(self.df) >= min_rows
    
    def add_ema(
        self, 
        short_period: int = None, 
        long_period: int = None,
    ) -> pd.DataFrame:
        """
        Add Exponential Moving Averages.
        
        EMA gives more weight to recent prices, making it more responsive
        to new trends than Simple Moving Average (SMA).
        
        Args:
            short_period: Short EMA period (default: 9)
            long_period: Long EMA period (default: 21)
            
        Returns:
            DataFrame with EMA columns added
        """
        short_period = short_period or settings.ema_short
        long_period = long_period or settings.ema_long
        
        # FIX #10: Add data length validation before EMA calculation
        if len(self.df) < short_period:
            logger.warning(f"Insufficient data for EMA{short_period}: have {len(self.df)} rows, need {short_period}")
            self.df[f"ema_{short_period}"] = None
        else:
            self.df[f"ema_{short_period}"] = ta.ema(self.df["close"], length=short_period)
        
        if len(self.df) < long_period:
            logger.warning(f"Insufficient data for EMA{long_period}: have {len(self.df)} rows, need {long_period}")
            self.df[f"ema_{long_period}"] = None
        else:
            self.df[f"ema_{long_period}"] = ta.ema(self.df["close"], length=long_period)
        
        return self.df
    
    def add_sma(self, periods: List[int] = None) -> pd.DataFrame:
        """
        Add Simple Moving Averages.
        
        Args:
            periods: List of periods to calculate (default: [20, 50, 200])
        """
        periods = periods or [20, 50, 200]
        
        for period in periods:
            if len(self.df) >= period:
                self.df[f"sma_{period}"] = ta.sma(self.df["close"], length=period)
        
        return self.df
    
    def add_rsi(self, period: int = None) -> pd.DataFrame:
        """
        Add Relative Strength Index.
        
        RSI measures momentum on a scale of 0-100:
        - RSI < 30: Oversold (potential bounce)
        - RSI 50-65: Bullish momentum, safe zone
        - RSI > 70: Overbought (potential pullback)
        
        For NEPSE swing trading, we want RSI 50-65 (bullish but not extreme).
        
        Args:
            period: RSI period (default: 14)
        """
        period = period or settings.rsi_period
        
        rsi_result = ta.rsi(self.df["close"], length=period)
        if rsi_result is not None:
            self.df[f"rsi_{period}"] = rsi_result
        else:
            # Insufficient data - create NaN column to avoid KeyError later
            self.df[f"rsi_{period}"] = np.nan
            logger.debug(f"RSI calculation returned None (need {period + 1}+ rows, have {len(self.df)})")
        
        return self.df
    
    def add_macd(
        self, 
        fast: int = 12, 
        slow: int = 26, 
        signal: int = 9,
    ) -> pd.DataFrame:
        """
        Add MACD (Moving Average Convergence Divergence).
        
        MACD shows trend direction and momentum:
        - MACD line = Fast EMA - Slow EMA
        - Signal line = EMA of MACD line
        - Histogram = MACD - Signal (positive = bullish momentum)
        
        We want: MACD histogram > 0 (confirms upward momentum)
        """
        macd = ta.macd(self.df["close"], fast=fast, slow=slow, signal=signal)
        
        if macd is not None and not macd.empty:
            self.df["macd"] = macd.iloc[:, 0]  # MACD line
            self.df["macd_histogram"] = macd.iloc[:, 1]  # Histogram
            self.df["macd_signal"] = macd.iloc[:, 2]  # Signal line
        else:
            # Insufficient data - create NaN columns to avoid KeyError
            self.df["macd"] = np.nan
            self.df["macd_histogram"] = np.nan
            self.df["macd_signal"] = np.nan
            logger.debug(f"MACD calculation returned None (need {slow + signal}+ rows, have {len(self.df)})")
        
        return self.df
    
    def add_adx(self, period: int = 14) -> pd.DataFrame:
        """
        Add Average Directional Index.
        
        ADX measures trend strength (not direction):
        - ADX < 20: Weak/no trend (avoid trading)
        - ADX 20-25: Developing trend
        - ADX > 25: Strong trend (good for swing trading)
        - ADX > 50: Very strong trend
        
        We want ADX > 25 to confirm the trend is worth trading.
        """
        adx = ta.adx(self.df["high"], self.df["low"], self.df["close"], length=period)
        
        if adx is not None and not adx.empty:
            self.df["adx"] = adx.iloc[:, 0]  # ADX
            self.df["dmp"] = adx.iloc[:, 1]  # +DI (positive directional)
            self.df["dmn"] = adx.iloc[:, 2]  # -DI (negative directional)
        else:
            # Insufficient data - create NaN columns to avoid KeyError
            self.df["adx"] = np.nan
            self.df["dmp"] = np.nan
            self.df["dmn"] = np.nan
            logger.debug(f"ADX calculation returned None (need {period * 2}+ rows, have {len(self.df)})")
        
        return self.df
    
    def add_bollinger_bands(self, period: int = 20, std: float = 2.0) -> pd.DataFrame:
        """
        Add Bollinger Bands.
        
        Bollinger Bands show volatility:
        - Upper band: SMA + (std * standard deviation)
        - Lower band: SMA - (std * standard deviation)
        
        Price touching lower band in uptrend = potential buy.
        """
        bbands = ta.bbands(self.df["close"], length=period, std=std)
        
        if bbands is not None and not bbands.empty:
            self.df["bb_lower"] = bbands.iloc[:, 0]
            self.df["bb_middle"] = bbands.iloc[:, 1]
            self.df["bb_upper"] = bbands.iloc[:, 2]
            self.df["bb_width"] = bbands.iloc[:, 3]  # Band width (volatility measure)
        
        return self.df
    
    def add_atr(self, period: int = 14) -> pd.DataFrame:
        """
        Add Average True Range using the EXACT True Range formula.
        
        TRUE RANGE = max(
            High - Low,
            |High - Previous Close|,
            |Low - Previous Close|
        )
        
        ATR = Wilder's Smoothed Moving Average of True Range
        
        BULLETPROOF IMPLEMENTATION:
        - Validates all OHLC data before calculation
        - Calculates True Range manually (no library dependency for core math)
        - Uses Wilder's smoothing (alpha = 1/period)
        - NEVER estimates - returns NaN with clear flag if data insufficient
        - Downstream code MUST check 'atr_is_valid' before using ATR
        """
        # Initialize columns
        self.df["atr"] = np.nan
        self.df["atr_is_valid"] = False
        self.df["true_range"] = np.nan
        
        # VALIDATION: Minimum data requirements
        min_required = period + 1
        if len(self.df) < min_required:
            logger.warning(
                f"❌ ATR INVALID: Insufficient data ({len(self.df)}/{min_required} rows). "
                f"ATR cannot be calculated. Downstream functions must handle NaN."
            )
            return self.df
        
        # VALIDATION: Required columns
        required_cols = ["high", "low", "close"]
        missing_cols = [col for col in required_cols if col not in self.df.columns]
        if missing_cols:
            logger.warning(f"❌ ATR INVALID: Missing columns {missing_cols}")
            return self.df
        
        try:
            high = self.df["high"].values
            low = self.df["low"].values
            close = self.df["close"].values
            
            # VALIDATION: Check for NaN in essential data
            if np.isnan(high).all() or np.isnan(low).all() or np.isnan(close).all():
                logger.warning("❌ ATR INVALID: OHLC data contains all NaN values")
                return self.df
            
            # Calculate TRUE RANGE manually (exact formula)
            true_range = np.zeros(len(self.df))
            true_range[0] = high[0] - low[0]  # First row: just H-L
            
            for i in range(1, len(self.df)):
                # Skip if any value is NaN
                if np.isnan(high[i]) or np.isnan(low[i]) or np.isnan(close[i-1]):
                    true_range[i] = np.nan
                    continue
                
                # TRUE RANGE = max(H-L, |H-PC|, |L-PC|)
                tr1 = high[i] - low[i]
                tr2 = abs(high[i] - close[i-1])
                tr3 = abs(low[i] - close[i-1])
                true_range[i] = max(tr1, tr2, tr3)
            
            self.df["true_range"] = true_range
            
            # Calculate ATR using WILDER'S SMOOTHING
            # Wilder's smoothing: alpha = 1/period
            tr_series = pd.Series(true_range)
            atr_values = tr_series.ewm(alpha=1.0/period, min_periods=period, adjust=False).mean()
            
            self.df["atr"] = atr_values
            
            # Mark which rows have valid ATR
            self.df["atr_is_valid"] = ~self.df["atr"].isna()
            
            # Count valid vs invalid
            valid_count = self.df["atr_is_valid"].sum()
            invalid_count = len(self.df) - valid_count
            
            if valid_count == 0:
                logger.warning("❌ ATR INVALID: All calculated values are NaN")
            elif invalid_count > 0:
                logger.debug(f"ATR: {valid_count} valid values, {invalid_count} NaN (early period)")
            else:
                logger.debug(f"ATR: All {valid_count} values calculated successfully")
            
            # VALIDATION: Final check that latest ATR is valid
            latest_atr = self.df["atr"].iloc[-1]
            if pd.isna(latest_atr) or latest_atr <= 0:
                logger.warning(
                    f"⚠️ ATR WARNING: Latest ATR is invalid ({latest_atr}). "
                    f"Check OHLC data quality."
                )
            
        except Exception as e:
            logger.error(f"❌ ATR CALCULATION FAILED: {e}")
            # Leave as NaN - do not estimate
        
        return self.df
    
    def add_volume_indicators(self, period: int = None) -> pd.DataFrame:
        """
        Add volume-based indicators.
        
        Volume confirms price moves:
        - Price up + High volume = Strong move, likely to continue
        - Price up + Low volume = Weak move, may reverse
        
        We want volume > 1.5x the 20-day average (institutional buying).
        """
        period = period or settings.volume_avg_period
        
        # Volume Moving Average (shifted to avoid lookahead bias - compare today's volume to YESTERDAY's average)
        self.df["volume_avg"] = ta.sma(self.df["volume"], length=period).shift(1)
        
        # Volume spike (current volume / previous average)
        # SAFE DIVISION: Avoid division by zero/NaN by using np.where
        self.df["volume_spike"] = np.where(
            (self.df["volume_avg"].notna()) & (self.df["volume_avg"] > 0),
            self.df["volume"] / self.df["volume_avg"],
            0.0  # Default to 0 (no spike) if no average available
        )
        
        # On-Balance Volume (cumulative volume flow)
        obv_result = ta.obv(self.df["close"], self.df["volume"])
        if obv_result is not None:
            self.df["obv"] = obv_result
        else:
            self.df["obv"] = np.nan
        
        return self.df
    
    def add_52week_levels(self) -> pd.DataFrame:
        """
        Add 52-week high/low levels.
        
        Used to avoid buying at the top:
        - Don't buy if price is in top 10% of 52-week high
        - Consider buying near 52-week low with reversal signals
        """
        # Use last 252 trading days as proxy for 52 weeks
        # NEPSE has ~250 trading days per year (Sun-Thu, minus holidays)
        window = min(252, len(self.df))
        
        self.df["high_52week"] = self.df["high"].rolling(window=window).max()
        self.df["low_52week"] = self.df["low"].rolling(window=window).min()
        
        # Percentage from 52-week high - SAFE DIVISION
        self.df["pct_from_high"] = np.where(
            (self.df["high_52week"].notna()) & (self.df["high_52week"] > 0),
            (self.df["high_52week"] - self.df["close"]) / self.df["high_52week"] * 100,
            np.nan
        )
        
        return self.df
    
    def add_all_indicators(self) -> pd.DataFrame:
        """
        Add all indicators at once.
        
        Returns:
            DataFrame with all indicators added
        """
        self.add_ema()
        self.add_sma()
        self.add_rsi()
        self.add_macd()
        self.add_adx()
        self.add_bollinger_bands()
        self.add_atr()
        self.add_volume_indicators()
        self.add_52week_levels()
        
        return self.df
    
    def detect_golden_cross(self) -> pd.DataFrame:
        """
        Detect Golden Cross signals.
        
        Golden Cross: Short EMA crosses ABOVE long EMA.
        This signals a new uptrend is starting.
        
        Returns:
            DataFrame with 'golden_cross' boolean column
        """
        short = settings.ema_short
        long = settings.ema_long
        
        if f"ema_{short}" not in self.df.columns:
            self.add_ema()
        
        # Golden cross occurs when short EMA crosses above long EMA
        # We check if short > long today AND short <= long yesterday
        self.df["golden_cross"] = (
            (self.df[f"ema_{short}"] > self.df[f"ema_{long}"]) &
            (self.df[f"ema_{short}"].shift(1) <= self.df[f"ema_{long}"].shift(1))
        )
        
        # Also mark as golden cross if crossover happened in last 2 days
        self.df["golden_cross_recent"] = (
            self.df["golden_cross"] | self.df["golden_cross"].shift(1)
        ).fillna(False)
        
        return self.df
    
    def detect_death_cross(self) -> pd.DataFrame:
        """
        Detect Death Cross signals.
        
        Death Cross: Short EMA crosses BELOW long EMA.
        This signals a new downtrend is starting (SELL signal).
        """
        short = settings.ema_short
        long = settings.ema_long
        
        if f"ema_{short}" not in self.df.columns:
            self.add_ema()
        
        self.df["death_cross"] = (
            (self.df[f"ema_{short}"] < self.df[f"ema_{long}"]) &
            (self.df[f"ema_{short}"].shift(1) >= self.df[f"ema_{long}"].shift(1))
        )
        
        return self.df
    
    def detect_rsi_divergence(self) -> pd.DataFrame:
        """
        Detect RSI divergence (advanced reversal signal).
        
        Bullish Divergence: Price makes lower low, but RSI makes higher low.
        This suggests selling pressure is weakening and a reversal is coming.
        
        This is a more advanced signal than basic RSI thresholds.
        """
        period = settings.rsi_period
        
        if f"rsi_{period}" not in self.df.columns:
            self.add_rsi()
        
        # Find local lows in price and RSI (using 5-day windows)
        self.df["price_low_5d"] = self.df["low"].rolling(5).min()
        self.df["rsi_low_5d"] = self.df[f"rsi_{period}"].rolling(5).min()
        
        # Bullish divergence: price at 5-day low but RSI is higher than previous 5-day low
        self.df["bullish_divergence"] = (
            (self.df["low"] == self.df["price_low_5d"]) &
            (self.df[f"rsi_{period}"] > self.df["rsi_low_5d"].shift(5))
        )
        
        return self.df
    
    def get_latest_values(self) -> dict:
        """
        Get the most recent indicator values.
        
        Returns:
            Dict with latest indicator values
        """
        if self.df.empty:
            return {}
        
        latest = self.df.iloc[-1]
        
        return {
            "date": latest.get("date"),
            "close": latest.get("close"),
            "ema_9": latest.get(f"ema_{settings.ema_short}"),
            "ema_21": latest.get(f"ema_{settings.ema_long}"),
            "rsi": latest.get(f"rsi_{settings.rsi_period}"),
            "macd": latest.get("macd"),
            "macd_histogram": latest.get("macd_histogram"),
            "adx": latest.get("adx"),
            "volume_spike": latest.get("volume_spike"),
            "atr": latest.get("atr"),
            "pct_from_high": latest.get("pct_from_high"),
        }


def safe_ema(prices, period: int = 21) -> Optional[float]:
    """
    Return latest EMA value safely.

    Returns None when data is insufficient or invalid.
    """
    try:
        price_series = pd.Series(prices, dtype="float64").replace([np.inf, -np.inf], np.nan).dropna()
        if len(price_series) < max(2, period):
            return None
        ema_series = ta.ema(price_series, length=period)
        if ema_series is None or ema_series.empty:
            return None
        latest = ema_series.iloc[-1]
        return float(latest) if pd.notna(latest) else None
    except Exception as e:
        logger.debug(f"safe_ema failed: {e}")
        return None


def safe_rsi(prices, period: int = 14) -> Optional[float]:
    """
    Return latest RSI value safely.

    Returns None when data is insufficient or invalid.
    """
    try:
        price_series = pd.Series(prices, dtype="float64").replace([np.inf, -np.inf], np.nan).dropna()
        if len(price_series) < period + 1:
            return None
        rsi_series = ta.rsi(price_series, length=period)
        if rsi_series is None or rsi_series.empty:
            return None
        latest = rsi_series.iloc[-1]
        return float(latest) if pd.notna(latest) else None
    except Exception as e:
        logger.debug(f"safe_rsi failed: {e}")
        return None


def safe_vwap(ohlcv: pd.DataFrame) -> Optional[float]:
    """
    Return VWAP from OHLCV data safely.

    Uses Typical Price * Volume / Volume. Returns None on zero/invalid volume.
    """
    try:
        if ohlcv is None or ohlcv.empty:
            return None
        required = {"high", "low", "close", "volume"}
        if not required.issubset(set(ohlcv.columns)):
            return None

        high = pd.to_numeric(ohlcv["high"], errors="coerce")
        low = pd.to_numeric(ohlcv["low"], errors="coerce")
        close = pd.to_numeric(ohlcv["close"], errors="coerce")
        volume = pd.to_numeric(ohlcv["volume"], errors="coerce").fillna(0)

        valid_mask = high.notna() & low.notna() & close.notna() & (volume >= 0)
        if not valid_mask.any():
            return None

        typical_price = (high[valid_mask] + low[valid_mask] + close[valid_mask]) / 3
        weighted = typical_price * volume[valid_mask]
        total_volume = float(volume[valid_mask].sum())
        if total_volume <= 0:
            return None
        return float(weighted.sum() / total_volume)
    except Exception as e:
        logger.debug(f"safe_vwap failed: {e}")
        return None


def safe_support_resistance(prices: pd.DataFrame, days: int = 30) -> Optional[Dict[str, List[float]]]:
    """
    Return support/resistance safely for short NEPSE histories.

    Returns None if data is not sufficient to produce meaningful levels.
    """
    try:
        if prices is None or prices.empty:
            return None
        required = {"high", "low"}
        if not required.issubset(set(prices.columns)):
            return None
        if len(prices) < max(10, days):
            return None

        analysis_df = prices.tail(days).copy()
        analysis_df["high"] = pd.to_numeric(analysis_df["high"], errors="coerce")
        analysis_df["low"] = pd.to_numeric(analysis_df["low"], errors="coerce")
        analysis_df = analysis_df.dropna(subset=["high", "low"])
        if len(analysis_df) < 10:
            return None

        window = min(10, max(3, len(analysis_df) // 4))
        supports, resistances = calculate_support_resistance(analysis_df, window=window)
        if not supports and not resistances:
            return None
        return {"support": [float(x) for x in supports], "resistance": [float(x) for x in resistances]}
    except Exception as e:
        logger.debug(f"safe_support_resistance failed: {e}")
        return None


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience function to calculate all indicators.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        DataFrame with all indicators added
    """
    ti = TechnicalIndicators(df)
    return ti.add_all_indicators()


def calculate_support_resistance(
    df: pd.DataFrame, 
    window: int = 20,
) -> Tuple[List[float], List[float]]:
    """
    Calculate support and resistance levels.
    
    Support: Price levels where the stock has bounced up from.
    Resistance: Price levels where the stock has failed to break above.
    
    Args:
        df: DataFrame with OHLCV data
        window: Lookback window for pivot detection
        
    Returns:
        Tuple of (support_levels, resistance_levels)
    """
    if df is None or df.empty or "high" not in df.columns or "low" not in df.columns:
        return [], []
    if len(df) < (window * 2 + 1):
        return [], []

    # Find pivot highs (local maxima)
    highs = df["high"].values
    pivot_highs = []
    
    for i in range(window, len(highs) - window):
        if highs[i] == max(highs[i-window:i+window+1]):
            pivot_highs.append(highs[i])
    
    # Find pivot lows (local minima)
    lows = df["low"].values
    pivot_lows = []
    
    for i in range(window, len(lows) - window):
        if lows[i] == min(lows[i-window:i+window+1]):
            pivot_lows.append(lows[i])
    
    # Cluster nearby levels
    resistance_levels = _cluster_levels(pivot_highs)
    support_levels = _cluster_levels(pivot_lows)
    
    return support_levels, resistance_levels


def _cluster_levels(levels: List[float], threshold: float = 0.02) -> List[float]:
    """
    Cluster nearby price levels together.
    
    Args:
        levels: List of price levels
        threshold: Percentage threshold for clustering
        
    Returns:
        Clustered levels
    """
    if not levels:
        return []
    
    levels = sorted(set(levels))
    clustered = []
    current_cluster = [levels[0]]
    
    for level in levels[1:]:
        if level <= current_cluster[-1] * (1 + threshold):
            current_cluster.append(level)
        else:
            clustered.append(np.mean(current_cluster))
            current_cluster = [level]
    
    clustered.append(np.mean(current_cluster))
    return clustered
