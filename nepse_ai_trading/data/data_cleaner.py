"""
Data cleaning utilities for NEPSE data.
Handles the messy, inconsistent data from NEPSE APIs.

IMPORTANT NEPSE REALITY:
Companies frequently issue Bonus Shares and Right Shares.
A 50% bonus share causes a 33% price drop the next day.
Without adjustment, this looks like a crash to the algorithm.
Always use ADJUSTED prices for backtesting!
"""

import re
from typing import Optional, Union, List
import pandas as pd
import numpy as np
from loguru import logger


def parse_nepse_number(value: Union[str, int, float, None]) -> Optional[float]:
    """
    Parse NEPSE numeric values which often come with commas or other formatting.
    
    Examples:
        "1,234.56" -> 1234.56
        "1234" -> 1234.0
        "-" -> None
        "" -> None
        12.34 -> 12.34
    
    Args:
        value: The value to parse
        
    Returns:
        Parsed float or None if unparseable
    """
    if value is None:
        return None
    
    if isinstance(value, (int, float)):
        if pd.isna(value):
            return None
        return float(value)
    
    if isinstance(value, str):
        # Remove whitespace
        cleaned = value.strip()
        
        # Handle empty or dash values
        if cleaned in ["", "-", "N/A", "n/a", "NA", "null", "None"]:
            return None
        
        # Remove commas (Nepali number formatting)
        cleaned = cleaned.replace(",", "")
        
        # Remove any currency symbols
        cleaned = re.sub(r"[Rs\.₨]", "", cleaned).strip()
        
        # Remove percentage signs
        cleaned = cleaned.replace("%", "").strip()
        
        try:
            return float(cleaned)
        except ValueError:
            logger.warning(f"Could not parse numeric value: {value}")
            return None
    
    return None


def clean_symbol(symbol: Union[str, None]) -> Optional[str]:
    """
    Clean stock symbol to standard format.
    
    Args:
        symbol: Raw symbol string
        
    Returns:
        Cleaned uppercase symbol or None
    """
    if symbol is None:
        return None
    
    if not isinstance(symbol, str):
        symbol = str(symbol)
    
    # Remove whitespace and convert to uppercase
    cleaned = symbol.strip().upper()
    
    # Remove any special characters except alphanumeric
    cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)
    
    return cleaned if cleaned else None


def clean_price_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean a DataFrame of NEPSE price data.
    
    Expected columns: symbol, date, open, high, low, close, volume
    Optional columns: turnover, trades
    
    Args:
        df: Raw DataFrame from NEPSE API
        
    Returns:
        Cleaned DataFrame with proper types
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for cleaning")
        return df
    
    df = df.copy()
    
    # Standardize column names
    column_mapping = {
        "Symbol": "symbol",
        "SYMBOL": "symbol",
        "CompanySymbol": "symbol",
        "company_symbol": "symbol",
        "Date": "date",
        "DATE": "date",
        "trade_date": "date",
        "TradeDate": "date",
        "Open": "open",
        "OPEN": "open",
        "OpenPrice": "open",
        "open_price": "open",
        "High": "high",
        "HIGH": "high",
        "HighPrice": "high",
        "high_price": "high",
        "max_price": "high",
        "MaxPrice": "high",
        "Low": "low",
        "LOW": "low",
        "LowPrice": "low",
        "low_price": "low",
        "min_price": "low",
        "MinPrice": "low",
        "Close": "close",
        "CLOSE": "close",
        "ClosePrice": "close",
        "close_price": "close",
        "ltp": "close",
        "LTP": "close",
        "LastTradedPrice": "close",
        "Volume": "volume",
        "VOLUME": "volume",
        "TotalVolume": "volume",
        "total_volume": "volume",
        "traded_quantity": "volume",
        "Quantity": "volume",
        "Turnover": "turnover",
        "TURNOVER": "turnover",
        "total_turnover": "turnover",
        "TotalTurnover": "turnover",
        "amount": "turnover",
        "Trades": "trades",
        "TRADES": "trades",
        "NumTrades": "trades",
        "num_trades": "trades",
        "total_trades": "trades",
    }
    
    df = df.rename(columns=column_mapping)
    
    # Ensure required columns exist
    required_columns = ["symbol", "date", "open", "high", "low", "close", "volume"]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        logger.error(f"Missing required columns: {missing}")
        raise ValueError(f"Missing required columns: {missing}")
    
    # Clean symbol
    df["symbol"] = df["symbol"].apply(clean_symbol)
    df = df.dropna(subset=["symbol"])
    
    # Parse date
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date"])
    
    # Parse numeric columns
    numeric_columns = ["open", "high", "low", "close", "volume"]
    optional_numeric = ["turnover", "trades"]
    
    for col in numeric_columns:
        df[col] = df[col].apply(parse_nepse_number)
    
    for col in optional_numeric:
        if col in df.columns:
            df[col] = df[col].apply(parse_nepse_number)
    
    # Drop rows with missing required numeric data
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    
    # Validate OHLC relationships
    # High >= max(Open, Close) and Low <= min(Open, Close)
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    
    # Ensure positive values
    for col in numeric_columns:
        df[col] = df[col].clip(lower=0)
    
    # Remove duplicates (same symbol + date)
    df = df.drop_duplicates(subset=["symbol", "date"], keep="last")
    
    # Sort by symbol and date
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    
    logger.info(f"Cleaned price data: {len(df)} records")
    return df


def fill_missing_dates(
    df: pd.DataFrame, 
    symbol: str,
    start_date: pd.Timestamp = None,
    end_date: pd.Timestamp = None,
) -> pd.DataFrame:
    """
    Fill missing dates in price data with forward-filled values.
    NEPSE is closed on Fridays and Saturdays, so we only fill weekday gaps.
    
    Args:
        df: DataFrame with date and OHLCV columns (single symbol)
        symbol: Stock symbol
        start_date: Start of date range
        end_date: End of date range
        
    Returns:
        DataFrame with missing dates filled
    """
    if df.empty:
        return df
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    
    if start_date is None:
        start_date = df.index.min()
    if end_date is None:
        end_date = df.index.max()
    
    # Create date range (NEPSE trading days: Sun-Thu)
    # In Nepal, Friday (4) and Saturday (5) are holidays
    all_dates = pd.date_range(start=start_date, end=end_date, freq="D")
    trading_days = all_dates[~all_dates.dayofweek.isin([4, 5])]
    
    # Reindex to include all trading days
    df = df.reindex(trading_days)
    
    # Forward fill missing values
    df = df.ffill()
    
    # Reset index
    df = df.reset_index()
    df = df.rename(columns={"index": "date"})
    df["symbol"] = symbol
    
    return df


def calculate_returns(prices: pd.Series) -> pd.Series:
    """
    Calculate daily returns from price series.
    
    Args:
        prices: Series of closing prices
        
    Returns:
        Series of daily returns (percentage)
    """
    return prices.pct_change() * 100


def adjust_for_corporate_actions(
    df: pd.DataFrame,
    bonus_shares: List[dict] = None,
    right_shares: List[dict] = None,
) -> pd.DataFrame:
    """
    Adjust historical prices for corporate actions (bonus shares, right shares).
    
    NEPSE REALITY:
    - A 50% bonus share means existing shareholders get 50 extra shares per 100 held
    - The stock price adjusts DOWN by 33% the next day (same market cap, more shares)
    - Without adjustment, this looks like a crash to the algorithm!
    
    Adjustment factor for bonus:
    - If bonus is X%, adjustment = 100 / (100 + X)
    - 50% bonus → factor = 100/150 = 0.667 (prices before action multiplied by 0.667)
    
    Args:
        df: DataFrame with date, open, high, low, close, volume
        bonus_shares: List of {"date": "YYYY-MM-DD", "percent": 50.0}
        right_shares: List of {"date": "YYYY-MM-DD", "percent": 25.0, "premium": 100}
        
    Returns:
        DataFrame with adjusted prices (adds adj_close column)
    """
    if df.empty:
        return df
    
    df = df.copy()
    df = df.sort_values("date").reset_index(drop=True)
    
    # Start with raw close as adjusted close
    df["adj_close"] = df["close"].astype(float)
    df["adj_factor"] = 1.0
    
    # Process bonus shares (reverse chronological for cumulative adjustment)
    if bonus_shares:
        for action in sorted(bonus_shares, key=lambda x: x["date"], reverse=True):
            action_date = pd.to_datetime(action["date"]).date()
            percent = float(action["percent"])
            
            # Adjustment factor: prices before action date get multiplied
            factor = 100.0 / (100.0 + percent)
            
            # Apply to all dates BEFORE the action
            mask = df["date"] < action_date
            df.loc[mask, "adj_factor"] *= factor
            
            logger.debug(f"Applied bonus adjustment: {percent}% on {action_date}, factor={factor:.4f}")
    
    # Process right shares (similar logic but includes premium)
    if right_shares:
        for action in sorted(right_shares, key=lambda x: x["date"], reverse=True):
            action_date = pd.to_datetime(action["date"]).date()
            percent = float(action["percent"])
            premium = float(action.get("premium", 100))  # Right share price
            
            # Get closing price just before the right share
            pre_action = df[df["date"] < action_date]
            if pre_action.empty:
                continue
            
            close_before = pre_action.iloc[-1]["close"]
            
            # Right share adjustment is more complex:
            # New shares = percent% of existing shares
            # Each new share costs Rs. premium
            # Theoretical ex-right price = (Old shares * Old price + New shares * Premium) / Total shares
            old_shares = 100
            new_shares = percent
            total_shares = old_shares + new_shares
            ex_right_price = (old_shares * close_before + new_shares * premium) / total_shares
            factor = ex_right_price / close_before
            
            mask = df["date"] < action_date
            df.loc[mask, "adj_factor"] *= factor
            
            logger.debug(f"Applied right share adjustment: {percent}% on {action_date}, factor={factor:.4f}")
    
    # Apply cumulative adjustment factor
    df["adj_close"] = df["close"] * df["adj_factor"]
    df["adj_open"] = df["open"] * df["adj_factor"]
    df["adj_high"] = df["high"] * df["adj_factor"]
    df["adj_low"] = df["low"] * df["adj_factor"]
    
    # Adjust volume inversely (more shares outstanding after bonus)
    df["adj_volume"] = df["volume"] / df["adj_factor"]
    
    return df


def detect_corporate_actions(df: pd.DataFrame, threshold: float = 0.15) -> List[dict]:
    """
    Detect potential corporate actions by looking for sudden price gaps.
    
    A gap down of >15% with no market-wide crash is likely a bonus/right share.
    
    Args:
        df: DataFrame with date and close prices
        threshold: Minimum gap to flag (0.15 = 15%)
        
    Returns:
        List of suspected corporate action dates
    """
    if df.empty or len(df) < 2:
        return []
    
    df = df.copy().sort_values("date")
    
    # Calculate daily returns
    df["return"] = df["close"].pct_change()
    
    # Find large gaps
    suspected = []
    for i, row in df.iterrows():
        if pd.notna(row["return"]) and row["return"] < -threshold:
            suspected.append({
                "date": row["date"],
                "gap": row["return"],
                "note": "Suspected bonus/right share (large gap down)"
            })
    
    if suspected:
        logger.warning(f"Detected {len(suspected)} potential corporate actions. Review manually!")
    
    return suspected


def detect_outliers(
    df: pd.DataFrame, 
    column: str, 
    method: str = "iqr",
    threshold: float = 3.0,
) -> pd.Series:
    """
    Detect outliers in a DataFrame column.
    
    Args:
        df: DataFrame
        column: Column to check
        method: "iqr" or "zscore"
        threshold: For zscore method
        
    Returns:
        Boolean Series (True = outlier)
    """
    values = df[column].dropna()
    
    if method == "iqr":
        Q1 = values.quantile(0.25)
        Q3 = values.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        return (df[column] < lower_bound) | (df[column] > upper_bound)
    
    elif method == "zscore":
        mean = values.mean()
        std = values.std()
        if std == 0:
            return pd.Series(False, index=df.index)
        z_scores = (df[column] - mean) / std
        return z_scores.abs() > threshold
    
    else:
        raise ValueError(f"Unknown method: {method}")
