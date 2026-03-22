"""
Pydantic schemas for data validation.
Ensures clean, type-safe data throughout the pipeline.
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
import re


class StockData(BaseModel):
    """Schema for stock master data."""
    symbol: str = Field(..., min_length=1, max_length=20)
    name: Optional[str] = None
    sector: Optional[str] = None
    listed_shares: Optional[float] = None
    market_cap: Optional[float] = None
    is_active: bool = True
    
    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase and trimmed."""
        return v.strip().upper()
    
    @field_validator("sector")
    @classmethod
    def clean_sector(cls, v: Optional[str]) -> Optional[str]:
        """Clean sector name."""
        if v:
            return v.strip().title()
        return v


class PriceData(BaseModel):
    """
    Schema for daily OHLCV price data.
    Handles the messy NEPSE API data formats.
    """
    symbol: str
    date: date
    open: float = Field(..., ge=0)
    high: float = Field(..., ge=0)
    low: float = Field(..., ge=0)
    close: float = Field(..., ge=0)
    volume: float = Field(..., ge=0)
    turnover: Optional[float] = Field(default=None, ge=0)
    trades: Optional[int] = Field(default=None, ge=0)
    
    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.strip().upper()
    
    @field_validator("open", "high", "low", "close", "volume", "turnover", mode="before")
    @classmethod
    def parse_numeric(cls, v):
        """
        NEPSE API often returns numbers as strings with commas.
        Example: "1,234.56" -> 1234.56
        """
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            # Remove commas and whitespace
            cleaned = v.replace(",", "").replace(" ", "").strip()
            if cleaned == "" or cleaned == "-":
                return 0.0
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0
    
    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        """Parse various date formats from NEPSE."""
        if isinstance(v, date):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            # Try common formats
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(v.strip(), fmt).date()
                except ValueError:
                    continue
        raise ValueError(f"Cannot parse date: {v}")
    
    def model_post_init(self, __context):
        """Validate OHLC relationships after parsing."""
        # High should be >= Open, Close, Low
        # Low should be <= Open, Close, High
        if self.high < max(self.open, self.close):
            # Sometimes API has bad data, set high to max of O/C
            self.high = max(self.open, self.close, self.high)
        if self.low > min(self.open, self.close):
            # Set low to min of O/C
            self.low = min(self.open, self.close, self.low)


class MarketDataSchema(BaseModel):
    """Schema for overall market data."""
    date: date
    nepse_index: Optional[float] = None
    nepse_change: Optional[float] = None
    nepse_change_pct: Optional[float] = None
    advances: Optional[int] = None
    declines: Optional[int] = None
    unchanged: Optional[int] = None
    total_turnover: Optional[float] = None
    total_volume: Optional[float] = None
    total_trades: Optional[int] = None
    
    @field_validator("nepse_index", "nepse_change", "nepse_change_pct", 
                     "total_turnover", "total_volume", mode="before")
    @classmethod
    def parse_numeric(cls, v):
        """Parse numeric fields that may come as strings."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            cleaned = v.replace(",", "").replace(" ", "").strip()
            if cleaned == "" or cleaned == "-":
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None


class SignalSchema(BaseModel):
    """Schema for trading signals."""
    symbol: str
    date: date
    signal_type: str = Field(..., pattern="^(BUY|SELL|HOLD)$")
    strategy_name: str
    confidence_score: float = Field(..., ge=1, le=10)
    entry_price: float = Field(..., gt=0)
    target_price: Optional[float] = Field(default=None, gt=0)
    stop_loss: Optional[float] = Field(default=None, gt=0)
    
    # Technical indicators at signal time
    rsi: Optional[float] = Field(default=None, ge=0, le=100)
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    volume_spike: Optional[float] = None
    
    # AI analysis
    ai_verdict: Optional[str] = None
    ai_analysis: Optional[str] = None
    news_summary: Optional[str] = None


class IndicatorValues(BaseModel):
    """Schema for calculated technical indicators."""
    symbol: str
    date: date
    
    # Moving Averages
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    
    # Momentum
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    
    # Volatility
    atr_14: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    
    # Volume
    volume_avg_20: Optional[float] = None
    volume_spike: Optional[float] = None  # Today's volume / avg volume
    obv: Optional[float] = None
    
    # Trend
    adx: Optional[float] = None
    
    # Price levels
    high_52week: Optional[float] = None
    low_52week: Optional[float] = None
    pct_from_52week_high: Optional[float] = None
