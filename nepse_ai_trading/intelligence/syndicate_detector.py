"""
Syndicate Detection — Phase 5.3.

Detects coordinated accumulation across multiple brokers, which
is the hallmark of operator syndicate pump-and-dump schemes in NEPSE.

Algorithm:
  1. For a target stock, get top N brokers by buy volume (7-day window)
  2. For each of those brokers, check if they are also net buyers in
     OTHER stocks simultaneously
  3. If 3+ large brokers are simultaneously accumulating the same set
     of stocks → syndicate behavior detected

This is a STRONG signal: coordinated buying precedes pumps by 3-7 days.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set
from loguru import logger


@dataclass
class SyndicateSignal:
    """Result of syndicate detection for a stock."""
    symbol: str
    syndicate_detected: bool = False
    syndicate_brokers: List[str] = field(default_factory=list)
    common_stocks: List[str] = field(default_factory=list)  # Other stocks same syndicate is buying
    confidence: float = 0.0  # 0-1

    @property
    def risk_level(self) -> str:
        if self.confidence >= 0.7:
            return "HIGH"
        if self.confidence >= 0.4:
            return "MODERATE"
        return "LOW"


def detect_syndicate(
    target_symbol: str,
    broker_net_positions: Dict[str, Dict[str, float]],
    min_brokers: int = 3,
    min_overlap_stocks: int = 2,
) -> SyndicateSignal:
    """
    Detect coordinated broker accumulation (syndicate behavior).

    Args:
        target_symbol: The stock being analyzed
        broker_net_positions: {broker_id: {symbol: net_qty, ...}, ...}
            Net positions per broker across all stocks in the 7-day window.
            Positive = net buyer, negative = net seller.
        min_brokers: Minimum coordinated brokers to flag syndicate (default 3)
        min_overlap_stocks: Minimum overlapping stocks for coordination (default 2)

    Returns:
        SyndicateSignal with detection result
    """
    if not broker_net_positions:
        return SyndicateSignal(symbol=target_symbol)

    # Step 1: Find brokers that are net buyers of the target stock
    target_buyers: List[str] = []
    for broker_id, positions in broker_net_positions.items():
        net = positions.get(target_symbol, 0)
        if net > 0:
            target_buyers.append(broker_id)

    if len(target_buyers) < min_brokers:
        return SyndicateSignal(symbol=target_symbol)

    # Step 2: For each target buyer, find what OTHER stocks they're also buying
    broker_buy_sets: Dict[str, Set[str]] = {}
    for bid in target_buyers:
        positions = broker_net_positions[bid]
        other_buys = {
            sym for sym, net in positions.items()
            if net > 0 and sym != target_symbol
        }
        if other_buys:
            broker_buy_sets[bid] = other_buys

    if len(broker_buy_sets) < min_brokers:
        return SyndicateSignal(symbol=target_symbol)

    # Step 3: Find common stocks across multiple target-buyer brokers
    # Count how many brokers are buying each stock
    stock_buyer_count: Dict[str, int] = {}
    for bid, stocks in broker_buy_sets.items():
        for sym in stocks:
            stock_buyer_count[sym] = stock_buyer_count.get(sym, 0) + 1

    # Stocks being bought by >= min_brokers of the target buyers
    common_stocks = [
        sym for sym, count in stock_buyer_count.items()
        if count >= min_brokers
    ]

    # Step 4: Identify the syndicate brokers (those buying target + common stocks)
    if len(common_stocks) < min_overlap_stocks:
        return SyndicateSignal(symbol=target_symbol)

    common_set = set(common_stocks)
    syndicate_members = []
    for bid, stocks in broker_buy_sets.items():
        overlap = stocks & common_set
        if len(overlap) >= min_overlap_stocks:
            syndicate_members.append(bid)

    if len(syndicate_members) < min_brokers:
        return SyndicateSignal(symbol=target_symbol)

    # Confidence: more members and more overlap = higher confidence
    member_factor = min(len(syndicate_members) / 5.0, 1.0)
    overlap_factor = min(len(common_stocks) / 4.0, 1.0)
    confidence = (member_factor * 0.6) + (overlap_factor * 0.4)

    return SyndicateSignal(
        symbol=target_symbol,
        syndicate_detected=True,
        syndicate_brokers=syndicate_members,
        common_stocks=common_stocks[:10],
        confidence=round(confidence, 2),
    )
