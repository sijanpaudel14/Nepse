"""
NRB Macroeconomic Scoring Engine — Phase 5.4.

Scores Nepal Rastra Bank macroeconomic indicators and translates
them into actionable signals for NEPSE trading.

Since NRB data isn't available via API, this module provides:
  1. A scoring framework for manual data entry
  2. Pre-defined thresholds for each indicator
  3. Composite liquidity, banking health, and overall macro scores
  4. Integration with the CSS fundamental component

Data sources (manual entry):
  - Interbank rate: NRB daily (https://www.nrb.org.np)
  - CCD ratio: NRB quarterly report
  - Inflation rate: NRB monthly CPI
  - Remittance flow: NRB monthly
  - Base rate: NRB circulars
"""

from dataclasses import dataclass
from typing import Optional
from loguru import logger


# NEPSE-relevant thresholds (calibrated for Nepal)
INTERBANK_NEUTRAL = 5.0   # % — below = loose liquidity, above = tight
CCD_DANGER_ZONE = 78.0    # % — above = banks can't lend more
INFLATION_NEUTRAL = 6.0   # % YoY — NRB target is ~6%
BASE_RATE_NEUTRAL = 7.0   # % — NRB base rate midpoint


@dataclass
class MacroScore:
    """Composite macroeconomic score for NEPSE trading."""
    liquidity_score: float = 50.0       # 0-100 (higher = more liquidity)
    banking_health_score: float = 50.0  # 0-100 (higher = healthier banks)
    overall_macro_score: float = 50.0   # 0-100 (higher = bullish macro)

    interbank_rate: Optional[float] = None
    ccd_ratio: Optional[float] = None
    inflation_rate: Optional[float] = None
    remittance_growth: Optional[float] = None
    base_rate: Optional[float] = None

    @property
    def macro_signal(self) -> str:
        if self.overall_macro_score >= 70:
            return "BULLISH"
        if self.overall_macro_score >= 55:
            return "MILD_BULLISH"
        if self.overall_macro_score >= 45:
            return "NEUTRAL"
        if self.overall_macro_score >= 30:
            return "MILD_BEARISH"
        return "BEARISH"

    @property
    def css_adjustment(self) -> float:
        """
        CSS fundamental score adjustment (-0.2 to +0.2).
        Integrates with the CSS scoring system.
        """
        return (self.overall_macro_score - 50) / 250  # ±0.2 range


def score_interbank_rate(rate: Optional[float]) -> float:
    """
    Score interbank rate for liquidity assessment.
    Lower rate = more liquidity = bullish for NEPSE.
    """
    if rate is None:
        return 50.0

    if rate <= 2.0:
        return 90.0  # Very loose liquidity
    if rate <= 4.0:
        return 75.0
    if rate <= INTERBANK_NEUTRAL:
        return 60.0
    if rate <= 7.0:
        return 40.0
    if rate <= 9.0:
        return 25.0
    return 10.0  # Very tight — bearish


def score_ccd_ratio(ccd: Optional[float]) -> float:
    """
    Score CCD (Credit-to-Core-Deposit) ratio.
    Higher CCD = less room for lending = bearish for banking sector.
    """
    if ccd is None:
        return 50.0

    if ccd <= 60:
        return 90.0  # Banks have lots of room
    if ccd <= 70:
        return 70.0
    if ccd <= 75:
        return 55.0
    if ccd <= CCD_DANGER_ZONE:
        return 35.0
    if ccd <= 82:
        return 20.0
    return 10.0  # Near regulatory limit — very bearish for banks


def score_inflation(inflation: Optional[float]) -> float:
    """
    Score inflation rate.
    Moderate inflation (3-5%) = bullish. High inflation = bearish (NRB tightens).
    """
    if inflation is None:
        return 50.0

    if inflation <= 3.0:
        return 65.0  # Low inflation, room for easing
    if inflation <= 5.0:
        return 75.0  # Sweet spot
    if inflation <= INFLATION_NEUTRAL:
        return 55.0  # NRB target
    if inflation <= 8.0:
        return 35.0
    return 15.0  # High inflation → rate hikes coming


def score_remittance(growth: Optional[float]) -> float:
    """
    Score remittance growth.
    Higher remittance = more liquidity flowing into Nepal = bullish.
    """
    if growth is None:
        return 50.0

    if growth >= 15:
        return 85.0
    if growth >= 10:
        return 70.0
    if growth >= 5:
        return 60.0
    if growth >= 0:
        return 45.0
    return 25.0  # Declining remittance — bearish


def compute_macro_score(
    interbank_rate: Optional[float] = None,
    ccd_ratio: Optional[float] = None,
    inflation_rate: Optional[float] = None,
    remittance_growth: Optional[float] = None,
    base_rate: Optional[float] = None,
) -> MacroScore:
    """
    Compute composite macroeconomic score from NRB indicators.

    All parameters are optional — the score adapts to whatever data is available.
    Missing indicators are scored at 50 (neutral).
    """
    ib_score = score_interbank_rate(interbank_rate)
    ccd_score = score_ccd_ratio(ccd_ratio)
    inf_score = score_inflation(inflation_rate)
    rem_score = score_remittance(remittance_growth)

    # Base rate scoring: lower = bullish for market (cheaper borrowing)
    if base_rate is not None:
        if base_rate <= 5:
            br_score = 80.0
        elif base_rate <= BASE_RATE_NEUTRAL:
            br_score = 55.0
        elif base_rate <= 9:
            br_score = 35.0
        else:
            br_score = 15.0
    else:
        br_score = 50.0

    # Composite scores
    # Liquidity: interbank rate + remittance (direct liquidity indicators)
    liquidity = ib_score * 0.6 + rem_score * 0.4

    # Banking health: CCD + base rate (bank profitability indicators)
    banking = ccd_score * 0.6 + br_score * 0.4

    # Overall: weighted composite
    overall = (
        ib_score * 0.25
        + ccd_score * 0.20
        + inf_score * 0.20
        + rem_score * 0.15
        + br_score * 0.20
    )

    return MacroScore(
        liquidity_score=round(liquidity, 1),
        banking_health_score=round(banking, 1),
        overall_macro_score=round(overall, 1),
        interbank_rate=interbank_rate,
        ccd_ratio=ccd_ratio,
        inflation_rate=inflation_rate,
        remittance_growth=remittance_growth,
        base_rate=base_rate,
    )
