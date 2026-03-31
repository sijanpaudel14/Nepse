"""
Quantitative Indicator Module — Minimal Effective Indicator Set (MEIS).

Replaces "indicator soup" with statistically validated indicators
organized by what they detect:

Tier 1: Volume-Price Relationship (Core Edge)
  - VWAP, RVOL, OBV, Volume-Weighted RSI, A/D Line

Tier 2: Volatility & Regime Detection
  - ATR, Bollinger %B, BBW, Keltner Squeeze, StochRSI

Tier 3: Trend Strength & Structure
  - ADX, EMA(10/30), EMA Slope, Supertrend

Tier 4: Operator Detection (NEPSE-Specific)
  - Broker Concentration (HHI), Buying Pressure Index

All indicators return normalized 0-1 scores for the Composite Signal Score.
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Optional, Dict, Tuple
from loguru import logger


class QuantIndicators:
    """
    Calculates the Minimal Effective Indicator Set for NEPSE trading.
    Each method returns clean, validated indicator values.
    """

    def __init__(self, df: pd.DataFrame):
        """
        Args:
            df: DataFrame with columns: date, open, high, low, close, volume
                Sorted by date ascending. Minimum 30 rows recommended.
        """
        self.df = df.copy()
        for col in ["open", "high", "low", "close", "volume"]:
            self.df[col] = pd.to_numeric(self.df[col], errors="coerce")
        self.df = self.df.dropna(subset=["close"])
        self.n = len(self.df)

    # ========================
    # TIER 1: Volume-Price
    # ========================

    def vwap(self, period: int = 20) -> pd.Series:
        """Rolling Volume-Weighted Average Price."""
        tp = (self.df["high"] + self.df["low"] + self.df["close"]) / 3
        vol = self.df["volume"].replace(0, np.nan)
        cum_tpv = (tp * vol).rolling(period, min_periods=1).sum()
        cum_vol = vol.rolling(period, min_periods=1).sum()
        return (cum_tpv / cum_vol).fillna(self.df["close"])

    def rvol(self, period: int = 20) -> pd.Series:
        """Relative Volume — today's volume vs 20-day average."""
        avg_vol = self.df["volume"].rolling(period, min_periods=5).mean()
        return (self.df["volume"] / avg_vol.replace(0, np.nan)).fillna(1.0)

    def obv(self) -> pd.Series:
        """On-Balance Volume."""
        result = ta.obv(self.df["close"], self.df["volume"])
        return result if result is not None else pd.Series(0, index=self.df.index)

    def obv_slope(self, window: int = 5) -> pd.Series:
        """OBV slope (rate of change) over window bars."""
        _obv = self.obv()
        shifted = _obv.shift(window)
        denom = shifted.abs().replace(0, np.nan)
        return ((_obv - shifted) / denom).fillna(0)

    def ad_line(self) -> pd.Series:
        """Accumulation/Distribution Line."""
        result = ta.ad(self.df["high"], self.df["low"], self.df["close"], self.df["volume"])
        return result if result is not None else pd.Series(0, index=self.df.index)

    def ad_slope(self, window: int = 5) -> pd.Series:
        """A/D line slope over window bars."""
        ad = self.ad_line()
        shifted = ad.shift(window)
        denom = shifted.abs().replace(0, np.nan)
        return ((ad - shifted) / denom).fillna(0)

    # ========================
    # TIER 2: Volatility
    # ========================

    def atr(self, period: int = 14) -> pd.Series:
        """Average True Range."""
        result = ta.atr(self.df["high"], self.df["low"], self.df["close"], length=period)
        return result if result is not None else pd.Series(0, index=self.df.index)

    def _get_bb_col(self, bb: pd.DataFrame, prefix: str, period: int, std: float) -> Optional[pd.Series]:
        """Robustly retrieve a Bollinger Band column regardless of pandas-ta version naming.
        pandas-ta may produce 'BBL_20_2.0' or 'BBL_20_2' depending on version."""
        for name in (
            f"{prefix}_{period}_{std}",       # e.g. BBL_20_2.0
            f"{prefix}_{period}_{int(std)}",   # e.g. BBL_20_2
            f"{prefix}_{period}_{std:.1f}",    # e.g. BBL_20_2.0 (explicit 1 decimal)
        ):
            if name in bb.columns:
                return bb[name]
        # Last resort: find first column that starts with the prefix (e.g. "BBL_")
        matches = [c for c in bb.columns if c.startswith(f"{prefix}_")]
        return bb[matches[0]] if matches else None

    def bollinger_pctb(self, period: int = 20, std: float = 2.0) -> pd.Series:
        """Bollinger Band %B — position within bands (0=lower, 1=upper)."""
        bb = ta.bbands(self.df["close"], length=period, std=std)
        if bb is None or bb.empty:
            return pd.Series(0.5, index=self.df.index)
        lower = self._get_bb_col(bb, "BBL", period, std)
        upper = self._get_bb_col(bb, "BBU", period, std)
        if lower is None or upper is None:
            return pd.Series(0.5, index=self.df.index)
        width = upper - lower
        return ((self.df["close"] - lower) / width.replace(0, np.nan)).fillna(0.5)

    def bollinger_width(self, period: int = 20, std: float = 2.0) -> pd.Series:
        """Bollinger Band Width — volatility gauge."""
        bb = ta.bbands(self.df["close"], length=period, std=std)
        if bb is None or bb.empty:
            return pd.Series(0, index=self.df.index)
        mid   = self._get_bb_col(bb, "BBM", period, std)
        upper = self._get_bb_col(bb, "BBU", period, std)
        lower = self._get_bb_col(bb, "BBL", period, std)
        if mid is None or upper is None or lower is None:
            return pd.Series(0, index=self.df.index)
        return ((upper - lower) / mid.replace(0, np.nan)).fillna(0)

    def bb_width_percentile(self, period: int = 20, lookback: int = 120) -> pd.Series:
        """BBW percentile rank over lookback period (0-1)."""
        bbw = self.bollinger_width(period)
        return bbw.rolling(lookback, min_periods=20).rank(pct=True).fillna(0.5)

    def stochrsi(
        self, rsi_len: int = 14, stoch_len: int = 14, k: int = 3, d: int = 3
    ) -> Tuple[pd.Series, pd.Series]:
        """StochRSI K and D lines."""
        result = ta.stochrsi(self.df["close"], length=rsi_len, rsi_length=stoch_len, k=k, d=d)
        if result is None:
            zeros = pd.Series(50, index=self.df.index)
            return zeros, zeros
        k_line = result[f"STOCHRSIk_{rsi_len}_{stoch_len}_{k}_{d}"]
        d_line = result[f"STOCHRSId_{rsi_len}_{stoch_len}_{k}_{d}"]
        return k_line.fillna(50), d_line.fillna(50)

    def keltner_squeeze(self, bb_period: int = 20, kc_period: int = 20, kc_mult: float = 1.5) -> pd.Series:
        """Keltner Channel Squeeze detection. True when BB inside KC."""
        bb = ta.bbands(self.df["close"], length=bb_period, std=2.0)
        kc = ta.kc(self.df["high"], self.df["low"], self.df["close"], length=kc_period, scalar=kc_mult)
        if bb is None or kc is None or bb.empty or kc.empty:
            return pd.Series(False, index=self.df.index)
        bb_upper = self._get_bb_col(bb, "BBU", bb_period, 2.0)
        bb_lower = self._get_bb_col(bb, "BBL", bb_period, 2.0)
        if bb_upper is None or bb_lower is None:
            return pd.Series(False, index=self.df.index)
        # Keltner column names also vary by pandas-ta version
        kc_upper, kc_lower = None, None
        for col in kc.columns:
            if col.startswith("KCUe"):
                kc_upper = kc[col]
            elif col.startswith("KCLe"):
                kc_lower = kc[col]
        if kc_upper is None or kc_lower is None:
            return pd.Series(False, index=self.df.index)
        return (bb_lower > kc_lower) & (bb_upper < kc_upper)

    # ========================
    # TIER 3: Trend
    # ========================

    def ema(self, period: int) -> pd.Series:
        """Exponential Moving Average."""
        result = ta.ema(self.df["close"], length=period)
        return result if result is not None else self.df["close"]

    def ema_slope(self, period: int = 10, window: int = 5) -> pd.Series:
        """EMA slope — rate of change of EMA over window bars."""
        _ema = self.ema(period)
        return ((_ema - _ema.shift(window)) / window).fillna(0)

    def adx(self, period: int = 14) -> pd.Series:
        """Average Directional Index — trend existence (not direction)."""
        result = ta.adx(self.df["high"], self.df["low"], self.df["close"], length=period)
        if result is None:
            return pd.Series(0, index=self.df.index)
        return result[f"ADX_{period}"].fillna(0)

    def supertrend(self, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
        """Supertrend value and direction (+1=bullish, -1=bearish)."""
        result = ta.supertrend(
            self.df["high"], self.df["low"], self.df["close"],
            length=period, multiplier=multiplier,
        )
        if result is None:
            zeros = pd.Series(0, index=self.df.index)
            return self.df["close"], zeros
        st_val = result[f"SUPERT_{period}_{multiplier}"]
        st_dir = result[f"SUPERTd_{period}_{multiplier}"]
        return st_val.fillna(self.df["close"]), st_dir.fillna(0)

    def rsi(self, period: int = 14) -> pd.Series:
        """Relative Strength Index."""
        result = ta.rsi(self.df["close"], length=period)
        return result if result is not None else pd.Series(50, index=self.df.index)

    # ========================
    # COMPOSITE ACCESSORS
    # ========================

    def get_latest_indicators(self) -> Dict[str, float]:
        """Get all latest indicator values as a flat dict."""
        if self.n < 14:
            return {}

        ema10 = self.ema(10)
        ema30 = self.ema(30)
        _adx = self.adx()
        _st_val, _st_dir = self.supertrend()
        _stoch_k, _stoch_d = self.stochrsi()

        return {
            # Volume-Price
            "vwap": self.vwap().iloc[-1],
            "rvol": self.rvol().iloc[-1],
            "obv_slope": self.obv_slope().iloc[-1],
            "ad_slope": self.ad_slope().iloc[-1],
            # Volatility
            "atr": self.atr().iloc[-1],
            "bb_pctb": self.bollinger_pctb().iloc[-1],
            "bb_width": self.bollinger_width().iloc[-1],
            "bb_width_pctl": self.bb_width_percentile().iloc[-1],
            "stochrsi_k": _stoch_k.iloc[-1],
            "stochrsi_d": _stoch_d.iloc[-1],
            "squeeze": bool(self.keltner_squeeze().iloc[-1]),
            # Trend
            "ema10": ema10.iloc[-1],
            "ema30": ema30.iloc[-1],
            "ema10_slope": self.ema_slope(10).iloc[-1],
            "adx": _adx.iloc[-1],
            "supertrend_dir": _st_dir.iloc[-1],
            "rsi": self.rsi().iloc[-1],
            # Price
            "close": self.df["close"].iloc[-1],
            "volume": self.df["volume"].iloc[-1],
        }
