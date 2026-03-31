"""
Broker Profile Tracker — 30/60/90 day rolling net position profiles.

Phase 5.2: Builds historical profiles for top NEPSE brokers to detect
accumulation/distribution patterns over multiple timeframes.

Top brokers in NEPSE have distinctive behavior:
  - Institutional brokers (e.g. #36, #58) buy steadily during accumulation
  - Retail-heavy brokers spike during FOMO rallies
  - Syndicate brokers accumulate across 3-5 coordinated accounts

This module tracks net buy/sell flow per broker per stock over rolling
30, 60, and 90 day windows, and flags when a broker's pattern shifts.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional
from loguru import logger


@dataclass
class BrokerProfile:
    """Rolling broker profile for a single stock."""
    broker_id: str
    broker_name: str
    symbol: str

    # Net quantities (buy - sell) over rolling windows
    net_30d: float = 0.0
    net_60d: float = 0.0
    net_90d: float = 0.0

    # Net turnover (Rs.)
    turnover_30d: float = 0.0
    turnover_60d: float = 0.0
    turnover_90d: float = 0.0

    # Trend detection
    @property
    def is_accumulating(self) -> bool:
        """Broker is accumulating if net positive across all windows."""
        return self.net_30d > 0 and self.net_60d > 0

    @property
    def is_distributing(self) -> bool:
        """Broker is distributing if net negative across all windows."""
        return self.net_30d < 0 and self.net_60d < 0

    @property
    def trend_reversal(self) -> Optional[str]:
        """Detect trend reversal: was accumulating, now flipping."""
        if self.net_90d > 0 and self.net_30d < 0:
            return "DISTRIBUTION_START"
        if self.net_90d < 0 and self.net_30d > 0:
            return "ACCUMULATION_START"
        return None


@dataclass
class StockBrokerSummary:
    """Aggregate broker activity for a single stock."""
    symbol: str
    top_buyers: List[BrokerProfile] = field(default_factory=list)
    top_sellers: List[BrokerProfile] = field(default_factory=list)

    # Concentration metrics
    buyer_concentration_30d: float = 0.0  # HHI of top buyers (0-1)
    total_net_30d: float = 0.0
    total_net_60d: float = 0.0

    @property
    def is_concentrated_buying(self) -> bool:
        """Few brokers dominating buy side — classic operator signal."""
        return self.buyer_concentration_30d > 0.25 and self.total_net_30d > 0

    @property
    def signal_strength(self) -> str:
        """Signal strength based on broker activity."""
        if self.is_concentrated_buying:
            return "STRONG_ACCUMULATION"
        if self.total_net_30d > 0 and self.total_net_60d > 0:
            return "MILD_ACCUMULATION"
        if self.total_net_30d < 0 and self.total_net_60d < 0:
            return "DISTRIBUTION"
        return "NEUTRAL"


def build_broker_profiles(
    broker_data: List[Dict],
    symbol: str,
) -> StockBrokerSummary:
    """
    Build broker profiles from ShareHub broker analysis data.

    Args:
        broker_data: List of dicts with keys:
            broker_id, broker_name, buy_qty, sell_qty, buy_amount, sell_amount, date
        symbol: Stock symbol

    Returns:
        StockBrokerSummary with top buyers/sellers and concentration metrics
    """
    if not broker_data:
        return StockBrokerSummary(symbol=symbol)

    today = date.today()
    d30 = today - timedelta(days=30)
    d60 = today - timedelta(days=60)
    d90 = today - timedelta(days=90)

    # Aggregate per broker
    brokers: Dict[str, Dict] = {}
    for row in broker_data:
        bid = str(row.get("broker_id", ""))
        if not bid:
            continue
        if bid not in brokers:
            brokers[bid] = {
                "broker_name": row.get("broker_name", bid),
                "net_30d": 0, "net_60d": 0, "net_90d": 0,
                "turn_30d": 0, "turn_60d": 0, "turn_90d": 0,
            }

        rd = row.get("date")
        if isinstance(rd, str):
            from datetime import datetime
            rd = datetime.strptime(rd, "%Y-%m-%d").date()
        if rd is None:
            rd = today

        net_qty = (row.get("buy_qty", 0) or 0) - (row.get("sell_qty", 0) or 0)
        net_amt = (row.get("buy_amount", 0) or 0) - (row.get("sell_amount", 0) or 0)

        if rd >= d90:
            brokers[bid]["net_90d"] += net_qty
            brokers[bid]["turn_90d"] += abs(net_amt)
        if rd >= d60:
            brokers[bid]["net_60d"] += net_qty
            brokers[bid]["turn_60d"] += abs(net_amt)
        if rd >= d30:
            brokers[bid]["net_30d"] += net_qty
            brokers[bid]["turn_30d"] += abs(net_amt)

    # Build profiles
    profiles = []
    for bid, data in brokers.items():
        profiles.append(BrokerProfile(
            broker_id=bid,
            broker_name=data["broker_name"],
            symbol=symbol,
            net_30d=data["net_30d"],
            net_60d=data["net_60d"],
            net_90d=data["net_90d"],
            turnover_30d=data["turn_30d"],
            turnover_60d=data["turn_60d"],
            turnover_90d=data["turn_90d"],
        ))

    # Sort by 30d net (buyers first)
    profiles.sort(key=lambda p: p.net_30d, reverse=True)
    top_buyers = [p for p in profiles if p.net_30d > 0][:10]
    top_sellers = [p for p in profiles if p.net_30d < 0][:10]

    # Buyer concentration (HHI on turnover)
    total_buy_turn = sum(p.turnover_30d for p in top_buyers)
    if total_buy_turn > 0:
        shares = [(p.turnover_30d / total_buy_turn) for p in top_buyers]
        hhi = sum(s ** 2 for s in shares)
    else:
        hhi = 0

    total_net_30d = sum(p.net_30d for p in profiles)
    total_net_60d = sum(p.net_60d for p in profiles)

    return StockBrokerSummary(
        symbol=symbol,
        top_buyers=top_buyers,
        top_sellers=top_sellers,
        buyer_concentration_30d=hhi,
        total_net_30d=total_net_30d,
        total_net_60d=total_net_60d,
    )
