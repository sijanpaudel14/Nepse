"""
Floorsheet Concentration Tracker — Phase 5.7.

Computes daily HHI (Herfindahl-Hirschman Index) per stock from broker
trade data to detect operator concentration.

HHI Guide for NEPSE:
  < 1500  = Competitive (many brokers, normal trading)
  1500-2500 = Moderately concentrated (few dominant brokers)
  > 2500  = Highly concentrated (operator activity likely)

Also tracks top-3 broker share — if >40% in a single session,
operator activity is very likely.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from loguru import logger


@dataclass
class ConcentrationResult:
    """Floorsheet concentration metrics for a single stock on a single day."""
    symbol: str
    hhi: float = 0.0                   # 0–10000 scale
    top3_share_pct: float = 0.0        # % of volume from top 3 brokers
    total_brokers: int = 0
    total_volume: int = 0

    # Dominant brokers
    top_brokers: List[Dict] = None  # [{broker_id, name, share_pct, volume}]

    @property
    def concentration_level(self) -> str:
        if self.hhi > 2500:
            return "HIGH"
        if self.hhi > 1500:
            return "MODERATE"
        return "LOW"

    @property
    def is_operator_likely(self) -> bool:
        """Operator activity likely if HHI > 2500 OR top 3 > 40%."""
        return self.hhi > 2500 or self.top3_share_pct > 40

    def __post_init__(self):
        if self.top_brokers is None:
            self.top_brokers = []


def compute_hhi(broker_volumes: Dict[str, int]) -> float:
    """
    Compute Herfindahl-Hirschman Index from broker volume map.

    Args:
        broker_volumes: {broker_id: total_volume_traded}

    Returns:
        HHI on 0-10000 scale. Higher = more concentrated.
    """
    total = sum(broker_volumes.values())
    if total <= 0:
        return 0.0

    return sum((v / total * 100) ** 2 for v in broker_volumes.values())


def analyze_floorsheet_concentration(
    trades: List[Dict],
    symbol: str,
) -> ConcentrationResult:
    """
    Analyze floorsheet trade data for a stock and compute concentration metrics.

    Args:
        trades: List of dicts with keys:
            buyer_broker_id, seller_broker_id, quantity
            (from NEPSE floorsheet or ShareHub data)
        symbol: Stock symbol

    Returns:
        ConcentrationResult with HHI and top broker shares
    """
    if not trades:
        return ConcentrationResult(symbol=symbol)

    # Aggregate volume per broker (buy side + sell side counted)
    broker_vol: Dict[str, int] = {}
    total_vol = 0

    for t in trades:
        qty = t.get("quantity", 0) or 0
        if qty <= 0:
            continue
        total_vol += qty

        buyer = str(t.get("buyer_broker_id", ""))
        seller = str(t.get("seller_broker_id", ""))

        if buyer:
            broker_vol[buyer] = broker_vol.get(buyer, 0) + qty
        if seller:
            broker_vol[seller] = broker_vol.get(seller, 0) + qty

    if not broker_vol:
        return ConcentrationResult(symbol=symbol)

    hhi = compute_hhi(broker_vol)

    # Top brokers by volume
    sorted_brokers = sorted(broker_vol.items(), key=lambda x: x[1], reverse=True)
    top3_vol = sum(v for _, v in sorted_brokers[:3])
    total_broker_vol = sum(broker_vol.values())
    top3_pct = (top3_vol / total_broker_vol * 100) if total_broker_vol > 0 else 0

    top_brokers = [
        {
            "broker_id": bid,
            "share_pct": round(vol / total_broker_vol * 100, 1) if total_broker_vol > 0 else 0,
            "volume": vol,
        }
        for bid, vol in sorted_brokers[:5]
    ]

    return ConcentrationResult(
        symbol=symbol,
        hhi=round(hhi, 1),
        top3_share_pct=round(top3_pct, 1),
        total_brokers=len(broker_vol),
        total_volume=total_vol,
        top_brokers=top_brokers,
    )
