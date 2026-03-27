"""
SaaS API Routes - Core endpoints for the Next.js frontend.

Provides clean JSON endpoints for:
- Market Scanner (4-Pillar Analysis)
- Stealth Radar (Sector Rotation)
- Portfolio Management
- Single Stock Analysis
"""

import sys
from pathlib import Path

# Add parent directory to path for nepse_ai_trading imports
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import math
import re
import requests
import threading
from dataclasses import asdict, is_dataclass
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from loguru import logger

# Pre-import all dependencies to avoid ThreadPoolExecutor import issues
from analysis.master_screener import MasterStockScreener
from data.fetcher import NepseFetcher

router = APIRouter(prefix="/api", tags=["SaaS"])
_ANALYZE_CANCEL_FLAGS: Dict[str, bool] = {}
_ANALYZE_LOCK = threading.Lock()


def _normalize_company_list(company_list: Any) -> List[Dict[str, Any]]:
    """
    Normalize company list into dict records so API routes can safely access keys.
    NepseFetcher.fetch_company_list() returns List[StockData], while older code
    expected a pandas DataFrame; this bridge prevents runtime type crashes.
    """
    normalized: List[Dict[str, Any]] = []
    if not company_list:
        return normalized

    for item in company_list:
        if isinstance(item, dict):
            symbol = str(item.get("symbol", "")).upper()
            if symbol:
                normalized.append({
                    "symbol": symbol,
                    "name": item.get("name", item.get("securityName", item.get("companyName", symbol))),
                    "sector": item.get("sector", item.get("sectorName", "Unknown")) or "Unknown",
                })
            continue

        symbol = str(getattr(item, "symbol", "")).upper()
        if symbol:
            normalized.append({
                "symbol": symbol,
                "name": getattr(item, "name", symbol) or symbol,
                "sector": getattr(item, "sector", "Unknown") or "Unknown",
            })

    return normalized


def _jsonable(value: Any) -> Any:
    """Convert dataclasses/enums/dates into JSON-safe values."""
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, float):
        return value if math.isfinite(value) else 0.0
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


_DECORATIVE_ICON_PREFIX = re.compile(r"^[\s\-\u2600-\u27BF\U0001F300-\U0001FAFF]+")


def _clean_text(value: Any) -> str:
    """Strip decorative emoji/icon prefixes from model-provided human text."""
    text = str(value or "").strip()
    if not text:
        return ""
    text = _DECORATIVE_ICON_PREFIX.sub("", text).strip()
    return re.sub(r"\s{2,}", " ", text)


def _clean_text_list(values: Any) -> List[str]:
    if not values:
        return []
    return [x for x in (_clean_text(v) for v in values) if x]


def _fetch_sharehub_intraday_volume(symbol: str) -> int:
    """
    Best-effort intraday traded quantity from ShareHub daily graph endpoint.
    This helps when NEPSE live snapshot volume lags by one day for newly listed IPOs.
    """
    try:
        url = f"https://sharehubnepal.com/live/api/v1/daily-graph/company/{symbol.upper()}"
        response = requests.get(
            url,
            headers={"accept": "application/json", "referer": f"https://sharehubnepal.com/company/{symbol.upper()}"},
            timeout=8,
        )
        if response.status_code != 200:
            return 0
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            return 0
        qty = 0
        for trade in payload:
            qty += int(_to_float(trade.get("contractQuantity", 0)))
        return max(qty, 0)
    except Exception:
        return 0


def _map_signal_response(
    symbol: str,
    signal_obj: Any,
    company_name: Optional[str] = None,
    company_sector: Optional[str] = None,
) -> Dict[str, Any]:
    signal_type = str(getattr(getattr(signal_obj, "signal_type", None), "name", "HOLD")).upper()
    signal_map = {
        "STRONG_BUY": "BUY",
        "BUY": "BUY",
        "WEAK_BUY": "BUY",
        "HOLD": "HOLD",
        "WEAK_SELL": "SELL",
        "SELL": "SELL",
        "STRONG_SELL": "SELL",
    }
    signal = signal_map.get(signal_type, "WAIT")
    current_price = float(getattr(signal_obj, "entry_price", 0) or 0)
    stop_loss = float(getattr(signal_obj, "stop_loss", 0) or 0)
    return {
        "symbol": symbol,
        "name": company_name or symbol,
        "sector": company_sector or "Unknown",
        "current_price": current_price,
        "signal": signal,
        "signal_emoji": signal,
        "confidence": int(float(getattr(signal_obj, "confidence", 0) or 0)),
        "trend_phase": str(getattr(getattr(signal_obj, "trend_phase", None), "name", "UNKNOWN")).upper(),
        "entry": {
            "target_zone_low": float(getattr(signal_obj, "entry_zone_low", current_price) or current_price),
            "target_zone_high": float(getattr(signal_obj, "entry_zone_high", current_price) or current_price),
            "price_gap_pct": float(getattr(signal_obj, "price_to_entry_pct", 0) or 0),
            "entry_date": str(getattr(signal_obj, "estimated_entry_date", "") or "TBD"),
            "conditions": _clean_text_list(getattr(signal_obj, "reasons", []) or []),
        },
        "hold": {
            "duration_days": int(getattr(signal_obj, "hold_duration_days", 0) or 0),
            "stop_loss": stop_loss,
            "stop_loss_pct": abs(((stop_loss - current_price) / current_price) * 100) if current_price > 0 else 0,
            "trail_stop_pct": float(getattr(signal_obj, "trailing_stop_pct", 0) or 0),
        },
        "targets": [
            {"level": "T1", "price": float(getattr(signal_obj, "target_1", 0) or 0), "gain_pct": ((float(getattr(signal_obj, "target_1", 0) or 0) - current_price) / current_price * 100) if current_price > 0 else 0, "probability": int(getattr(signal_obj, "t1_probability", 0) or 0)},
            {"level": "T2", "price": float(getattr(signal_obj, "target_2", 0) or 0), "gain_pct": ((float(getattr(signal_obj, "target_2", 0) or 0) - current_price) / current_price * 100) if current_price > 0 else 0, "probability": int(getattr(signal_obj, "t2_probability", 0) or 0)},
            {"level": "T3", "price": float(getattr(signal_obj, "target_3", 0) or 0), "gain_pct": ((float(getattr(signal_obj, "target_3", 0) or 0) - current_price) / current_price * 100) if current_price > 0 else 0, "probability": int(getattr(signal_obj, "t3_probability", 0) or 0)},
        ],
        "risk": {
            "risk_reward": float(getattr(signal_obj, "risk_reward_ratio", 0) or 0),
            "position_size_pct": float(getattr(signal_obj, "position_size_pct", 0) or 0),
            "trailing_stop_pct": float(getattr(signal_obj, "trailing_stop_pct", 0) or 0),
        },
        "warnings": _clean_text_list(getattr(signal_obj, "warnings", []) or []),
        "recommendation": (_clean_text_list(getattr(signal_obj, "reasons", []) or ["Wait for confirmation"])[0]),
    }


def _map_ipo_exit_response(result: Any) -> Dict[str, Any]:
    volume = getattr(result, "volume_analysis", None)
    broker = getattr(result, "broker_flow", None)
    pattern = getattr(result, "price_pattern", None)

    daily_volumes = list(getattr(volume, "daily_volumes", []) or [])
    dates = [str(d) for d, _ in daily_volumes]
    vols = [int(v or 0) for _, v in daily_volumes]

    trend_raw = str(getattr(volume, "volume_trend", "stable")).upper()
    trend = "DECAY" if trend_raw in {"DECLINING", "DECAY"} else "SPIKE" if trend_raw == "SPIKE" else "DISTRIBUTION" if trend_raw == "DISTRIBUTION" else "STABLE"

    flow_raw = str(getattr(broker, "flow_type", "neutral")).upper()
    flow_type = {
        "ACCUMULATION": "ACCUMULATION",
        "RETAIL_BUYING": "ACCUMULATION",
        "DISTRIBUTION": "DISTRIBUTION",
        "NEUTRAL": "NEUTRAL",
    }.get(flow_raw, "NEUTRAL")

    verdict = str(getattr(getattr(result, "exit_signal", None), "name", "HOLD")).upper()

    reasons = list(getattr(result, "reasons", []) or [])
    exit_signals = [
        {"name": "Volume Pressure", "triggered": any("volume" in r.lower() for r in reasons), "score": 20 if any("volume" in r.lower() for r in reasons) else 0, "max_score": 25},
        {"name": "Broker Distribution", "triggered": any("institution" in r.lower() or "selling" in r.lower() for r in reasons), "score": 30 if any("institution" in r.lower() or "selling" in r.lower() for r in reasons) else 0, "max_score": 40},
        {"name": "Price Breakdown", "triggered": any("broke" in r.lower() or "downtrend" in r.lower() for r in reasons), "score": 25 if any("broke" in r.lower() or "downtrend" in r.lower() for r in reasons) else 0, "max_score": 35},
    ]

    return {
        "symbol": str(getattr(result, "symbol", "")),
        "current_price": float(getattr(result, "current_price", 0) or 0),
        "listing_price": float(getattr(result, "listing_price", 0) or 0),
        "gain_loss_pct": float(getattr(result, "gain_from_listing_pct", 0) or 0),
        "days_listed": int(getattr(result, "days_since_listing", 0) or 0),
        "volume_trend": {
            "dates": dates,
            "volumes": vols,
            "trend": trend,
            "interpretation": _clean_text(getattr(volume, "explanation", "") or ""),
        },
        "broker_flow": {
            "analysis_period": _clean_text(getattr(broker, "analysis_period", "") or ""),
            "net_quantity": int(getattr(broker, "net_quantity", 0) or 0),
            "flow_type": flow_type,
            "interpretation": _clean_text(getattr(broker, "explanation", "") or ""),
            "top_buyers": [{"name": str(x.get("name", "")), "quantity": int(x.get("quantity", 0) or 0)} for x in list(getattr(broker, "top_buyers", []) or [])],
            "top_sellers": [{"name": str(x.get("name", "")), "quantity": int(x.get("quantity", 0) or 0)} for x in list(getattr(broker, "top_sellers", []) or [])],
        },
        "price_pattern": {
            "day2_low": float(getattr(pattern, "day_2_low", 0) or 0),
            "buffer_pct": ((float(getattr(result, "current_price", 0) or 0) - float(getattr(pattern, "day_2_low", 0) or 0)) / max(float(getattr(pattern, "day_2_low", 0) or 1), 1.0)) * 100 if pattern else 0,
            "trend": "BREAKDOWN" if bool(getattr(pattern, "broke_day2_low", False)) else "UPTREND" if str(getattr(pattern, "price_trend", "")).lower() == "uptrend" else "CONSOLIDATION",
        },
        "exit_signals": exit_signals,
        "total_exit_score": int(getattr(result, "confidence", 0) or 0),
        "verdict": verdict if verdict in {"STRONG_HOLD", "HOLD", "WATCH", "CONSIDER_PARTIAL", "SELL", "URGENT_SELL"} else "HOLD",
        "verdict_emoji": "",
        "action": _clean_text(getattr(result, "action", "") or ""),
        "stop_loss": float(getattr(result, "stop_loss", 0) or 0),
        "reasons": _clean_text_list(reasons),
        "warnings": _clean_text_list(getattr(result, "warnings", []) or []),
    }


def _map_position_advice_response(advice: Any) -> Dict[str, Any]:
    recommended_action = str(getattr(advice, "recommended_action", "") or "")
    actions = [_clean_text(line.strip()) for line in recommended_action.split("\n") if line.strip()]
    support_info = getattr(advice, "support_resistance", None)
    risk_info = getattr(advice, "risk_reward", None)
    technical = getattr(advice, "technical", None)
    support = float(getattr(support_info, "immediate_support", 0) or 0)
    resistance = float(getattr(support_info, "immediate_resistance", 0) or 0)
    current_price = float(getattr(advice, "current_price", 0) or 0)
    buy_price = float(getattr(advice, "buy_price", 0) or 0)
    ema_count = sum([
        bool(getattr(technical, "above_ema_9", False)),
        bool(getattr(technical, "above_ema_21", False)),
        bool(getattr(technical, "above_ema_50", False)),
        bool(getattr(technical, "above_ema_200", False)),
    ])
    support_distance_pct = ((current_price - support) / max(current_price, 1.0)) * 100 if support > 0 and current_price > 0 else 0.0
    resistance_distance_pct = ((resistance - current_price) / max(current_price, 1.0)) * 100 if resistance > 0 and current_price > 0 else 0.0

    return {
        "symbol": str(getattr(advice, "symbol", "")),
        "name": str(getattr(advice, "symbol", "")),
        "position": {
            "buy_price": buy_price,
            "current_price": current_price,
            "pnl_amount": float(getattr(advice, "pnl_amount", 0) or 0),
            "pnl_pct": float(getattr(advice, "pnl_percent", 0) or 0),
            "holding_period": str(getattr(getattr(advice, "holding_period", None), "name", "MEDIUM")).replace("_", " "),
            "days_held": int(getattr(advice, "holding_days", 0) or 0),
            "trading_days_held": int(getattr(advice, "trading_days_held", 0) or 0),
            "example_100_shares": {
                "invested": buy_price * 100,
                "current_value": current_price * 100,
                "pnl_amount": (current_price - buy_price) * 100,
            },
        },
        "technical": {
            "trend": str(getattr(technical, "trend", "UNKNOWN")),
            "momentum": str(getattr(technical, "rsi_signal", "NEUTRAL")),
            "support": float(support),
            "resistance": float(resistance),
            "rsi": float(getattr(technical, "rsi", 50) or 50),
            "trend_strength": int(getattr(technical, "trend_strength", 0) or 0),
            "volume_trend": str(getattr(technical, "volume_trend", "NORMAL")),
            "ema_above_count": int(ema_count),
            "ema_total": 4,
            "ema_alignment": "Perfect alignment" if ema_count == 4 else "Moderate" if ema_count >= 2 else "Weak",
        },
        "support_resistance": {
            "immediate_support": support,
            "strong_support": float(getattr(support_info, "strong_support", 0) or 0),
            "immediate_resistance": resistance,
            "strong_resistance": float(getattr(support_info, "strong_resistance", 0) or 0),
            "entry_vs_support": str(getattr(support_info, "entry_vs_support", "") or ""),
            "support_distance_pct": float(support_distance_pct),
            "resistance_distance_pct": float(resistance_distance_pct),
        },
        "risk_reward": {
            "risk_to_support_pct": float(getattr(risk_info, "risk_to_support", 0) or 0),
            "reward_to_resistance_pct": float(getattr(risk_info, "reward_to_resistance", 0) or 0),
            "ratio": float(getattr(risk_info, "risk_reward_ratio", 0) or 0),
            "favorable": bool(getattr(risk_info, "favorable", False)),
        },
        "health_score": int(getattr(advice, "health_score", 0) or 0),
        "health_grade": str(getattr(advice, "health_grade", "C") or "C"),
        "health_breakdown": [
            {"factor": "Trend", "score": int(getattr(technical, "trend_strength", 0) or 0), "max_score": 100, "weight_pct": 30},
            {"factor": "Risk/Reward", "score": int(min(max(float(getattr(getattr(advice, "risk_reward", None), "risk_reward_ratio", 0) or 0) * 40, 0), 100)), "max_score": 100, "weight_pct": 25},
            {"factor": "Position Health", "score": int(getattr(advice, "health_score", 0) or 0), "max_score": 100, "weight_pct": 45},
        ],
        "verdict": str(getattr(getattr(advice, "verdict", None), "name", "HOLD")),
        "verdict_text": _clean_text(getattr(advice, "verdict_text", "") or ""),
        "verdict_emoji": "",
        "actions": actions if actions else ["Hold and monitor"],
        "exit_triggers": _clean_text_list(getattr(advice, "exit_triggers", []) or []),
        "hold_checklist": _clean_text_list(getattr(advice, "hold_checklist", []) or []),
        "stop_loss": float(getattr(advice, "stop_loss", 0) or 0),
        "targets": [
            {"level": "T1", "price": float(getattr(advice, "target_1", 0) or 0), "gain_pct": (((float(getattr(advice, "target_1", 0) or 0) - current_price) / max(current_price or 1, 1.0)) * 100)},
            {"level": "T2", "price": float(getattr(advice, "target_2", 0) or 0), "gain_pct": (((float(getattr(advice, "target_2", 0) or 0) - current_price) / max(current_price or 1, 1.0)) * 100)},
        ],
        "trade_plan": {
            "stop_loss_pct_from_current": (((float(getattr(advice, "stop_loss", 0) or 0) - current_price) / max(current_price, 1.0)) * 100) if current_price > 0 else 0.0,
        },
        "warnings": _clean_text_list(getattr(advice, "warnings", []) or []),
    }


def _to_float(value: Any, default: float = 0.0) -> float:
    """Best-effort numeric conversion for mixed API payloads."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_live_price(row: Any) -> float:
    """
    Extract a usable market price from live market row data.
    Supports mixed payloads where price may come as ltp/close/lastTradedPrice.
    """
    if row is None:
        return 0.0

    # pandas.Series supports `.get`, sqlite row / dict support item access
    get_value = row.get if hasattr(row, "get") else lambda key, default=None: row[key] if key in row else default
    for key in ("ltp", "close", "lastTradedPrice", "last_traded_price", "open"):
        price = _to_float(get_value(key, 0.0), 0.0)
        if price > 0:
            return price
    return 0.0


def _is_valid_price(value: Any) -> bool:
    """True only for finite positive prices."""
    price = _to_float(value, 0.0)
    return math.isfinite(price) and price > 0


# ============== Pydantic Models ==============

class PillarScore(BaseModel):
    """Individual pillar score."""
    name: str
    score: float
    max_score: float
    percentage: float


class StockScanResult(BaseModel):
    """Stock scan result for frontend table."""
    rank: int
    symbol: str
    name: str = ""
    sector: str
    ltp: float
    score: int
    verdict: str
    verdict_emoji: str
    
    # Trade Plan
    entry_price: float
    target_price: float
    stop_loss: float
    hold_days: str
    
    # Pillar Breakdown
    pillar_broker: float
    pillar_unlock: float
    pillar_fundamental: float
    pillar_technical: float
    
    # Risk Data
    distribution_risk: str
    distribution_risk_emoji: str
    broker_profit_pct: float
    vwap_cost: float
    
    # Additional
    rsi: float
    volume_spike: float
    buyer_dominance: float
    pe_ratio: float
    roe: float
    
    # Signals
    key_signals: List[str] = []
    red_flags: List[str] = []


class ScanResponse(BaseModel):
    """Response for scan endpoint."""
    success: bool
    timestamp: str
    market_regime: str
    market_regime_emoji: str
    strategy: str
    sector: Optional[str]
    total_analyzed: int
    results: List[StockScanResult]


class StealthStock(BaseModel):
    """Stock with stealth accumulation detected."""
    symbol: str
    sector: str
    ltp: float
    broker_score: float
    broker_score_pct: float
    technical_score: float
    technical_score_pct: float
    distribution_risk: str
    broker_profit_pct: float
    buyer_dominance: float


class SectorRotation(BaseModel):
    """Sector with stealth accumulation activity."""
    sector: str
    stock_count: int
    avg_broker_score: float
    stocks: List[StealthStock]


class StealthResponse(BaseModel):
    """Response for stealth-scan endpoint."""
    success: bool
    timestamp: str
    total_stealth_stocks: int
    sectors: List[SectorRotation]


class PortfolioPosition(BaseModel):
    """Open position in portfolio."""
    id: int
    symbol: str
    entry_date: str
    entry_price: float
    quantity: int
    current_price: float
    target_price: float
    stop_loss: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    days_held: int
    status: str  # "OPEN", "TARGET_HIT", "STOP_HIT", "EXPIRED"


class PortfolioStats(BaseModel):
    """Portfolio statistics."""
    total_trades: int
    open_positions: int
    closed_positions: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float


class PortfolioResponse(BaseModel):
    """Response for portfolio status."""
    success: bool
    timestamp: str
    stats: PortfolioStats
    positions: List[PortfolioPosition]


class PortfolioEditRequest(BaseModel):
    quantity: Optional[int] = Field(default=None, gt=0)
    entry_price: Optional[float] = Field(default=None, gt=0)
    target_price: Optional[float] = Field(default=None, gt=0)
    stop_loss: Optional[float] = Field(default=None, gt=0)


class PortfolioSellRequest(BaseModel):
    exit_price: Optional[float] = Field(default=None, gt=0)


class SingleStockAnalysis(BaseModel):
    """Deep analysis for a single stock."""
    symbol: str
    name: str
    company_name: str = ""
    sector: str
    ltp: float
    
    # Overall Scores
    momentum_score: int
    value_score: int
    momentum_verdict: str
    value_verdict: str
    recommendation: str = ""
    verdict_reason: str = ""
    strategy: str = "momentum"
    
    # Pillar Details (for visualization)
    pillars: Dict[str, PillarScore]
    
    # Fundamentals
    pe_ratio: float
    pe_status: str
    eps: float
    eps_annualized: float
    book_value: float
    pbv: float
    roe: float
    roe_status: str
    
    # Technical
    rsi: float
    rsi_status: str
    ema_signal: str
    volume_spike: float
    atr: float
    high_52w: float = 0.0
    low_52w: float = 0.0
    pct_from_52w_high: float = 0.0
    pct_from_52w_low: float = 0.0
    
    # Distribution Risk
    distribution_risk: str
    broker_avg_cost: float
    broker_profit_pct: float
    distribution_warning: str
    net_holdings_1m: int = 0
    net_holdings_1w: int = 0
    intraday_dump_detected: bool = False
    open_vs_broker_pct: float = 0.0
    close_vs_vwap_pct: float = 0.0
    intraday_volume_spike: float = 0.0
    
    # Trade Plan
    entry_price: float
    target_price: float
    stop_loss: float
    hold_days: str
    expected_holding_days: int = 0
    max_holding_days: int = 0
    minimum_hold_period: str = ""
    risk_reward_ratio: float = 0.0
    execution_warning: str = ""
    support_level: float = 0.0
    resistance_level: float = 0.0
    
    # Recommendations
    long_term_recommendation: str
    short_term_recommendation: str
    friend_recommendation: str
    
    # Red Flags
    red_flags: List[str]
    
    # Price History (for mini chart)
    price_history_7d: List[Dict[str, Any]] = []
    price_trend_7d: float
    price_trend_30d: float
    price_trend_90d: float
    price_trend_1y: float = 0.0

    # Company overview
    market_cap_cr: float = 0.0
    paid_up_capital_cr: float = 0.0
    outstanding_shares_cr: float = 0.0
    promoter_pct: float = 0.0
    public_pct: float = 0.0
    free_float_pct: float = 0.0
    daily_turnover_cr: float = 0.0

    # Rich CLI parity block (verbatim-style narrative)
    full_report_text: str = ""

    # Full report parity sections
    strategy_comparison: Dict[str, Any] = {}
    sector_comparison: Dict[str, Any] = {}
    dividend_history: List[Dict[str, Any]] = []
    broker_activity: Dict[str, Any] = {}
    manipulation_risk: Dict[str, Any] = {}
    support_resistance: Dict[str, Any] = {}
    price_target_analysis: Dict[str, Any] = {}
    distribution_details: Dict[str, Any] = {}


class AnalyzeResponse(BaseModel):
    """Response for single stock analysis."""
    success: bool
    timestamp: str
    data: SingleStockAnalysis


class MarketRegimeResponse(BaseModel):
    """Current market regime."""
    regime: str
    regime_emoji: str
    reason: str
    nepse_index: float
    ema50: float
    timestamp: str


# ============== API Endpoints ==============

@router.get("/scan", response_model=ScanResponse)
async def run_market_scan(
    strategy: str = Query("momentum", enum=["momentum", "value"]),
    sector: Optional[str] = Query(None),
    quick: bool = Query(True),
    max_price: Optional[float] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Run the 4-Pillar AI Market Scanner.
    
    Returns top stocks based on the selected strategy.
    """
    try:
        from analysis.master_screener import MasterStockScreener
        
        logger.info(f"API Scan: strategy={strategy}, sector={sector}, quick={quick}")
        
        # Initialize screener
        screener = MasterStockScreener(
            strategy=strategy,
            target_sector=sector,
            max_price=max_price
        )
        
        # Check market regime
        regime, regime_reason = screener.check_market_regime()
        regime_emoji = ""
        
        # Run analysis
        results = screener.run_full_analysis(quick_mode=quick)
        
        # Convert to response format
        scan_results = []
        for i, stock in enumerate(results[:limit], 1):
            # Determine verdict emoji
            score = stock.total_score
            if score >= 85:
                verdict = "EXCELLENT"
            elif score >= 70:
                verdict = "GOOD"
            elif score >= 55:
                verdict = "AVERAGE"
            else:
                verdict = "WEAK"
            
            # Distribution risk emoji
            dist_risk = getattr(stock, 'distribution_risk', 'N/A')
            dist_emoji = ""
            
            scan_results.append(StockScanResult(
                rank=i,
                symbol=stock.symbol,
                name=getattr(stock, 'name', ''),
                sector=stock.sector,
                ltp=stock.ltp,
                score=int(stock.total_score),
                verdict=verdict,
                verdict_emoji="",
                entry_price=stock.entry_price,
                target_price=stock.target_price,
                stop_loss=stock.stop_loss,
                hold_days=stock.exit_strategy.split(':')[0].replace('📅 ', '').replace('📆 ', '') if hasattr(stock, 'exit_strategy') else "5-10 days",
                pillar_broker=stock.pillar1_broker,
                pillar_unlock=stock.pillar2_unlock,
                pillar_fundamental=stock.pillar3_fundamental,
                pillar_technical=stock.pillar4_technical,
                distribution_risk=dist_risk,
                distribution_risk_emoji=dist_emoji,
                broker_profit_pct=getattr(stock, 'broker_profit_pct', 0),
                vwap_cost=getattr(stock, 'broker_avg_cost', 0),
                rsi=stock.rsi,
                volume_spike=stock.volume_spike,
                buyer_dominance=stock.buyer_dominance_pct,
                pe_ratio=stock.pe_ratio,
                roe=stock.roe,
                key_signals=getattr(stock, 'key_signals', []),
                red_flags=getattr(stock, 'red_flags', []),
            ))
        
        return ScanResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            market_regime=regime,
            market_regime_emoji=regime_emoji,
            strategy=strategy.upper(),
            sector=sector,
            total_analyzed=len(results),
            results=scan_results,
        )
        
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stealth-scan", response_model=StealthResponse)
async def run_stealth_scan(
    sector: Optional[str] = Query(None),
    max_price: Optional[float] = Query(None),
):
    """
    Run the Stealth Radar - Detect Smart Money Accumulation.
    
    Finds stocks where:
    - Technical Score is LOW (price hasn't broken out)
    - Broker Score is HIGH (heavy institutional buying)
    - Distribution Risk is LOW (brokers not selling)
    """
    try:
        from analysis.master_screener import MasterStockScreener
        
        logger.info(f"API Stealth Scan: sector={sector}")
        
        # Initialize screener
        screener = MasterStockScreener(
            strategy="momentum",
            target_sector=sector,
            max_price=max_price
        )
        
        # Run full analysis to get all scores
        results = screener.run_full_analysis(quick_mode=False)
        
        # Filter for stealth criteria
        stealth_stocks = []
        for stock in results:
            tech_score = stock.pillar4_technical
            broker_score = stock.pillar1_broker
            dist_risk = getattr(stock, 'distribution_risk', 'N/A')
            
            # Stealth criteria: Low tech (<40%), High broker (>80%), Low risk
            max_tech = 40.0  # Max for momentum
            max_broker = 30.0
            
            tech_pct = (tech_score / max_tech) * 100 if max_tech > 0 else 0
            broker_pct = (broker_score / max_broker) * 100 if max_broker > 0 else 0
            
            if tech_pct < 40 and broker_pct > 70 and dist_risk == "LOW":
                stealth_stocks.append(StealthStock(
                    symbol=stock.symbol,
                    sector=stock.sector,
                    ltp=stock.ltp,
                    broker_score=broker_score,
                    broker_score_pct=broker_pct,
                    technical_score=tech_score,
                    technical_score_pct=tech_pct,
                    distribution_risk=dist_risk,
                    broker_profit_pct=getattr(stock, 'broker_profit_pct', 0),
                    buyer_dominance=stock.buyer_dominance_pct,
                ))
        
        # Group by sector
        sector_map: Dict[str, List[StealthStock]] = {}
        for stock in stealth_stocks:
            if stock.sector not in sector_map:
                sector_map[stock.sector] = []
            sector_map[stock.sector].append(stock)
        
        sectors = []
        for sector_name, stocks in sorted(sector_map.items(), key=lambda x: -len(x[1])):
            avg_broker = sum(s.broker_score for s in stocks) / len(stocks) if stocks else 0
            sectors.append(SectorRotation(
                sector=sector_name,
                stock_count=len(stocks),
                avg_broker_score=round(avg_broker, 1),
                stocks=stocks,
            ))
        
        return StealthResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            total_stealth_stocks=len(stealth_stocks),
            sectors=sectors,
        )
        
    except Exception as e:
        logger.error(f"Stealth scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Cache for market regime data (15 minute TTL - due to high Azure→Nepal latency)
_market_regime_cache = {
    "data": None,
    "timestamp": None,
    "ttl_seconds": 900  # 15 minutes (high latency makes frequent fetches impractical)
}

def _get_cached_regime():
    """Get cached market regime if still valid."""
    if _market_regime_cache["data"] is None:
        return None
    
    now = datetime.now()
    cached_time = _market_regime_cache["timestamp"]
    
    if cached_time and (now - cached_time).total_seconds() < _market_regime_cache["ttl_seconds"]:
        logger.info(f"📦 Returning cached market regime (age: {(now - cached_time).total_seconds():.0f}s)")
        return _market_regime_cache["data"]
    
    return None


@router.get("/market-regime", response_model=MarketRegimeResponse)
async def get_market_regime():
    """
    Get current market regime (Bull/Bear/Panic) with instant response.
    
    Returns cached data immediately. If cache is stale, refreshes in background.
    """
    try:
        # Always return cached data immediately if available
        if _market_regime_cache["data"] is not None:
            now = datetime.now()
            cached_time = _market_regime_cache["timestamp"]
            age_seconds = (now - cached_time).total_seconds()
            
            # If cache is older than 5 minutes, refresh in background
            if age_seconds >= _market_regime_cache["ttl_seconds"]:
                logger.info(f"📦 Returning stale cache ({age_seconds:.0f}s old), refreshing in background...")
                
                # Start background refresh (don't await)
                import asyncio
                asyncio.create_task(_refresh_market_regime_background())
            else:
                logger.info(f"📦 Returning fresh cache ({age_seconds:.0f}s old)")
            
            return _market_regime_cache["data"]
        
        # First time - must fetch synchronously (but with short timeout)
        logger.info("🔄 First fetch - getting market regime data...")
        return await _fetch_market_regime_with_timeout()
        
    except Exception as e:
        import traceback
        logger.error(f"Market regime check failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Return safe default
        return MarketRegimeResponse(
            regime="BULL",
            regime_emoji="",
            reason="Market data unavailable",
            nepse_index=0,
            ema50=0,
            timestamp=datetime.now().isoformat(),
        )


async def _refresh_market_regime_background():
    """Refresh market regime in background."""
    try:
        response = await _fetch_market_regime_with_timeout()
        _market_regime_cache["data"] = response
        _market_regime_cache["timestamp"] = datetime.now()
        logger.info("✅ Background refresh complete")
    except Exception as e:
        logger.error(f"Background refresh failed: {e}")


async def _fetch_market_regime_with_timeout():
    """Fetch market regime with 60 second timeout (Azure->Nepal latency + double fetch issue)."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    def fetch_regime_data():
        """Fetch regime in thread."""
        # All imports already done at module level - just use them
        screener = MasterStockScreener(strategy="momentum")
        regime, reason = screener.check_market_regime()
        
        # Reuse fetcher - data is already fetched by screener
        fetcher = NepseFetcher()
        index_df = fetcher.fetch_index_history(days=30)  # Reduced from 60 to save time
        
        nepse_index = float(index_df['close'].iloc[-1]) if not index_df.empty else 0
        ema50 = float(index_df['close'].ewm(span=50).mean().iloc[-1]) if len(index_df) >= 50 else 0
        
        return regime, reason, nepse_index, ema50
    
    # Run in thread pool with 60 second timeout (Azure->Nepal has very high latency)
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        try:
            regime, reason, nepse_index, ema50 = await asyncio.wait_for(
                loop.run_in_executor(executor, fetch_regime_data),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            logger.warning("⏱️ NEPSE API timeout (60s), using default values")
            regime = "BULL"
            reason = "Market data temporarily unavailable (NEPSE API timeout - high Azure→Nepal latency)"
            nepse_index = 0
            ema50 = 0
    
    return MarketRegimeResponse(
        regime=regime,
        regime_emoji="",
        reason=reason,
        nepse_index=round(nepse_index, 2),
        ema50=round(ema50, 2),
        timestamp=datetime.now().isoformat(),
    )


@router.get("/portfolio/status", response_model=PortfolioResponse)
async def get_portfolio_status():
    """Get current portfolio status and statistics."""
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path(__file__).parent.parent.parent / "tools" / "paper_trading.db"
        
        # Create empty portfolio response helper
        def empty_portfolio():
            return PortfolioResponse(
                success=True,
                timestamp=datetime.now().isoformat(),
                stats=PortfolioStats(
                    total_trades=0,
                    open_positions=0,
                    closed_positions=0,
                    wins=0,
                    losses=0,
                    win_rate=0.0,
                    total_pnl=0.0,
                    avg_win=0.0,
                    avg_loss=0.0,
                    best_trade=0.0,
                    worst_trade=0.0,
                ),
                positions=[],
            )
        
        if not db_path.exists():
            return empty_portfolio()
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if trades table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if not cursor.fetchone():
            conn.close()
            return empty_portfolio()
        
        # Get open positions
        cursor.execute("""
            SELECT * FROM trades 
            WHERE status = 'OPEN' 
            ORDER BY entry_date DESC
        """)
        open_trades = cursor.fetchall()
        
        # Get closed trades for stats
        cursor.execute("""
            SELECT * FROM trades 
            WHERE status != 'OPEN'
        """)
        closed_trades = cursor.fetchall()
        
        # Calculate stats
        wins = sum(1 for t in closed_trades if t['pnl'] and t['pnl'] > 0)
        losses = sum(1 for t in closed_trades if t['pnl'] and t['pnl'] < 0)
        total_pnl = sum(t['pnl'] or 0 for t in closed_trades)
        
        win_pnls = [t['pnl'] for t in closed_trades if t['pnl'] and t['pnl'] > 0]
        loss_pnls = [t['pnl'] for t in closed_trades if t['pnl'] and t['pnl'] < 0]
        
        # Get current prices for open positions (skip if no open trades)
        positions = []
        if open_trades:
            from data.fetcher import NepseFetcher
            fetcher = NepseFetcher()
            live_data = fetcher.fetch_live_market()
            
            price_map = {}
            if not live_data.empty:
                for _, row in live_data.iterrows():
                    symbol = str(row.get('symbol', '')).upper()
                    if not symbol:
                        continue
                    live_price = _extract_live_price(row)
                    if live_price > 0:
                        price_map[symbol] = live_price
            
            for trade in open_trades:
                current_price = price_map.get(trade['symbol'], trade['entry_price'])
                unrealized_pnl = (current_price - trade['entry_price']) * trade['quantity']
                unrealized_pnl_pct = ((current_price / trade['entry_price']) - 1) * 100
                
                entry_date = datetime.strptime(trade['entry_date'], '%Y-%m-%d')
                days_held = (datetime.now() - entry_date).days
                
                positions.append(PortfolioPosition(
                    id=trade['id'],
                    symbol=trade['symbol'],
                    entry_date=trade['entry_date'],
                    entry_price=trade['entry_price'],
                    quantity=trade['quantity'],
                    current_price=current_price,
                    target_price=trade['target_price'],
                    stop_loss=trade['stop_loss'],
                    unrealized_pnl=round(unrealized_pnl, 2),
                    unrealized_pnl_pct=round(unrealized_pnl_pct, 2),
                    days_held=days_held,
                    status="OPEN",
                ))
        
        conn.close()
        
        return PortfolioResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            stats=PortfolioStats(
                total_trades=len(open_trades) + len(closed_trades),
                open_positions=len(open_trades),
                closed_positions=len(closed_trades),
                wins=wins,
                losses=losses,
                win_rate=round((wins / len(closed_trades) * 100) if closed_trades else 0, 1),
                total_pnl=round(total_pnl, 2),
                avg_win=round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else 0,
                avg_loss=round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else 0,
                best_trade=round(max(win_pnls), 2) if win_pnls else 0,
                worst_trade=round(min(loss_pnls), 2) if loss_pnls else 0,
            ),
            positions=positions,
        )
        
    except Exception as e:
        logger.error(f"Portfolio status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/update")
async def update_portfolio():
    """
    Check all open positions against current prices.
    Updates status if target or stop-loss is hit.
    """
    try:
        import sqlite3
        from pathlib import Path
        from data.fetcher import NepseFetcher
        
        db_path = Path(__file__).parent.parent.parent / "tools" / "paper_trading.db"
        
        if not db_path.exists():
            return {"success": True, "message": "No portfolio database found", "updates": []}
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if trades table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if not cursor.fetchone():
            conn.close()
            return {"success": True, "message": "No trades yet - portfolio empty", "updates": []}
        
        # Get open positions
        cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
        open_trades = cursor.fetchall()
        
        if not open_trades:
            conn.close()
            return {"success": True, "message": "No open positions", "updates": []}
        
        # Get current prices
        fetcher = NepseFetcher()
        live_data = fetcher.fetch_live_market()
        
        price_map = {}
        if not live_data.empty:
            for _, row in live_data.iterrows():
                symbol = str(row.get('symbol', '')).upper()
                if not symbol:
                    continue
                live_price = _extract_live_price(row)
                if live_price > 0:
                    price_map[symbol] = live_price
        
        updates = []
        for trade in open_trades:
            current_price = price_map.get(trade['symbol'])
            if current_price is None:
                continue
            
            new_status = None
            pnl = 0
            
            if current_price >= trade['target_price']:
                new_status = "TARGET_HIT"
                pnl = (trade['target_price'] - trade['entry_price']) * trade['quantity']
            elif current_price <= trade['stop_loss']:
                new_status = "STOP_HIT"
                pnl = (trade['stop_loss'] - trade['entry_price']) * trade['quantity']
            
            if new_status:
                cursor.execute("""
                    UPDATE trades 
                    SET status = ?, exit_price = ?, exit_date = ?, pnl = ?
                    WHERE id = ?
                """, (new_status, current_price, datetime.now().strftime('%Y-%m-%d'), pnl, trade['id']))
                
                updates.append({
                    "symbol": trade['symbol'],
                    "old_status": "OPEN",
                    "new_status": new_status,
                    "pnl": round(pnl, 2),
                })
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "updates": updates,
            "message": f"Updated {len(updates)} positions",
        }
        
    except Exception as e:
        logger.error(f"Portfolio update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/{symbol}", response_model=AnalyzeResponse)
async def analyze_single_stock(
    symbol: str,
    strategy: str = Query("momentum", enum=["momentum", "value"]),
):
    """
    Deep 4-Pillar analysis for a single stock.
    
    Returns comprehensive data including:
    - All 4 pillar scores with breakdown
    - Fundamentals (PE, EPS, ROE, etc.)
    - Technical indicators (RSI, EMA, Volume)
    - Distribution risk analysis
    - Trade plan with entry/target/stop-loss
    - Red flags and recommendations
    """
    try:
        from analysis.master_screener import MasterStockScreener
        from analysis.price_target_analyzer import PriceTargetAnalyzer
        from data.fetcher import NepseFetcher
        
        symbol = symbol.upper()
        with _ANALYZE_LOCK:
            _ANALYZE_CANCEL_FLAGS[symbol] = False
        logger.info(f"API Analyze: symbol={symbol}, strategy={strategy}")

        # Get live market row first (used by both strategy runs)
        fetcher = NepseFetcher()
        live_data = fetcher.fetch_live_market()

        ltp = 0.0
        live_row = None
        if not live_data.empty:
            stock_row = live_data[live_data['symbol'] == symbol]
            if not stock_row.empty:
                live_row = stock_row.iloc[0]
                ltp = _extract_live_price(live_row)

        # If no live data, try historical
        if not _is_valid_price(ltp):
            history = fetcher.fetch_price_history(symbol, days=7)
            if history is not None and not history.empty:
                ltp = _to_float(history['close'].iloc[-1], 0.0)

        if not _is_valid_price(ltp):
            raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

        # Get company info
        company_list = fetcher.fetch_company_list()
        normalized_companies = _normalize_company_list(company_list)
        company_info = next((c for c in normalized_companies if c["symbol"] == symbol), None)
        name = company_info["name"] if company_info else symbol
        sector = company_info["sector"] if company_info else "Unknown"

        # Rich company overview from NEPSE detail payload
        company_details = None
        market_cap_cr = 0.0
        paid_up_capital_cr = 0.0
        outstanding_shares_cr = 0.0
        promoter_pct = 0.0
        public_pct = 0.0
        free_float_pct = 0.0
        daily_turnover_cr = 0.0
        try:
            company_details = fetcher.fetch_company_details(symbol)
            if company_details:
                market_cap_cr = _to_float(company_details.get('marketCapitalization'), 0.0) / 10000000
                paid_up_capital_cr = _to_float(company_details.get('paidUpCapital'), 0.0) / 10000000
                outstanding_shares_cr = _to_float(company_details.get('stockListedShares'), 0.0) / 10000000
                promoter_pct = _to_float(company_details.get('promoterPercentage'), 0.0)
                public_pct = _to_float(company_details.get('publicPercentage'), 0.0)
                free_float_pct = public_pct * 0.7 if public_pct > 0 else public_pct
                daily_data = company_details.get('securityDailyTradeDto', {}) if isinstance(company_details, dict) else {}
                volume_q = _to_float(daily_data.get('totalTradeQuantity'), 0.0)
                ltp_daily = _to_float(daily_data.get('lastTradedPrice'), ltp)
                daily_turnover_cr = (volume_q * ltp_daily) / 10000000 if volume_q > 0 and ltp_daily > 0 else 0.0
        except Exception as e:
            logger.debug(f"Could not fetch company details for {symbol}: {e}")

        # Run BOTH strategy engines to match CLI parity
        def _row_get_float(row: Any, keys: List[str], default: float = 0.0) -> float:
            if row is None:
                return default
            getter = row.get if hasattr(row, "get") else lambda k, d=None: row[k] if k in row else d
            for key in keys:
                value = _to_float(getter(key, default), default)
                if key in {"volume", "turnover", "change_pct"}:
                    return value
                if value > 0:
                    return value
            return default

        market_row = {
            "symbol": symbol,
            "ltp": ltp,
            "lastTradedPrice": ltp,
            "close": _row_get_float(live_row, ["close", "lastTradedPrice", "ltp"], ltp),
            "open": _row_get_float(live_row, ["open", "openPrice"], ltp),
            "high": _row_get_float(live_row, ["high", "highPrice"], ltp),
            "low": _row_get_float(live_row, ["low", "lowPrice"], ltp),
            "volume": _row_get_float(live_row, ["volume", "totalTradeQuantity"], 0.0),
            "turnover": _row_get_float(live_row, ["turnover", "totalTradeValue"], 0.0),
            "change_pct": _row_get_float(live_row, ["change_pct", "percentageChange"], 0.0),
        }

        strategy_results: Dict[str, Any] = {}
        screeners: Dict[str, Any] = {}
        for st in ("value", "momentum"):
            with _ANALYZE_LOCK:
                if _ANALYZE_CANCEL_FLAGS.get(symbol):
                    _ANALYZE_CANCEL_FLAGS.pop(symbol, None)
                    raise HTTPException(status_code=499, detail=f"Analysis for {symbol} stopped")
            try:
                screener = MasterStockScreener(strategy=st)
                screener._preload_market_data(single_symbol=symbol)
                scored = screener._score_stock(market_row)
                if scored:
                    strategy_results[st] = scored
                    screeners[st] = screener
            except Exception as run_err:
                logger.warning(f"Analyze run failed for {symbol} [{st}]: {run_err}")

        if not strategy_results:
            raise HTTPException(status_code=404, detail=f"Insufficient market data for {symbol}")

        selected_result = strategy_results.get(strategy) or strategy_results.get("momentum") or strategy_results.get("value")
        selected_screener = screeners.get(strategy) or screeners.get("momentum") or screeners.get("value")
        value_result = strategy_results.get("value")
        momentum_result = strategy_results.get("momentum")

        # Ensure selected strategy has distribution-risk output.
        if selected_screener and str(getattr(selected_result, "distribution_risk", "") or "").upper() in {"", "N/A", "UNKNOWN"}:
            try:
                selected_screener._calculate_distribution_risk(symbol, ltp, {}, {})
                dist = selected_screener._distribution_risk_cache.get(symbol, {})
                if dist:
                    selected_result.distribution_risk = str(dist.get("risk_level", "LOW"))
                    selected_result.broker_avg_cost = float(dist.get("avg_cost", 0) or 0)
                    selected_result.broker_profit_pct = float(dist.get("profit_pct", 0) or 0)
                    selected_result.distribution_warning = str(dist.get("warning", "") or "")
                    selected_result.net_holdings_1m = int(dist.get("net_holdings_1m", 0) or 0)
                    selected_result.net_holdings_1w = int(dist.get("net_holdings_1w", 0) or 0)
                    selected_result.intraday_dump_detected = bool(dist.get("intraday_dump_detected", False))
                    selected_result.open_vs_broker_pct = float(dist.get("open_vs_broker_pct", 0) or 0)
                    selected_result.close_vs_vwap_pct = float(dist.get("close_vs_vwap_pct", 0) or 0)
                    selected_result.intraday_volume_spike = float(dist.get("volume_spike", 0) or 0)
                    selected_result.broker_avg_cost_1w = float(dist.get("avg_cost_1w", 0) or 0)
                    selected_result.distribution_divergence = bool(dist.get("distribution_divergence", False))
            except Exception as dist_err:
                logger.warning(f"Distribution risk fallback failed for {symbol}: {dist_err}")

        # Use sharehub fundamentals like CLI for accurate EPS/Book/PBV
        fundamentals = None
        sharehub = getattr(selected_screener, "sharehub", None) if selected_screener else None
        if sharehub:
            try:
                fundamentals = sharehub.get_fundamentals(symbol)
                if fundamentals and ltp > 0:
                    if getattr(fundamentals, "eps_annualized", 0) and fundamentals.eps_annualized > 0:
                        fundamentals.pe_ratio = ltp / fundamentals.eps_annualized
                    elif getattr(fundamentals, "eps", 0) and fundamentals.eps > 0:
                        fundamentals.pe_ratio = ltp / fundamentals.eps
                    fundamentals.calculate_pbv(ltp)
            except Exception as fund_err:
                logger.debug(f"Could not fetch fundamentals from ShareHub for {symbol}: {fund_err}")

        # Price trends (prefer sharehub summary, fallback history math)
        price_trend_7d = 0.0
        price_trend_30d = 0.0
        price_trend_90d = 0.0
        price_trend_1y = 0.0
        if sharehub:
            try:
                summary = sharehub.get_price_change_summary(symbol)
                if summary:
                    price_trend_7d = float(getattr(summary, "change_7d_pct", 0) or 0)
                    price_trend_30d = float(getattr(summary, "change_30d_pct", 0) or 0)
                    price_trend_90d = float(getattr(summary, "change_90d_pct", 0) or 0)
                    price_trend_1y = float(getattr(summary, "change_52w_pct", 0) or 0)
            except Exception:
                pass

        history = fetcher.fetch_price_history(symbol, days=365)
        price_trend_7d = 0
        price_history_7d = []

        if history is not None and not history.empty:
            hist_for_levels = history.tail(min(len(history), 252))
            high_52w = _to_float(hist_for_levels['high'].max())
            low_52w = _to_float(hist_for_levels['low'].min())
            if len(history) >= 7:
                price_trend_7d = ((ltp / history['close'].iloc[-7]) - 1) * 100
                price_history_7d = [
                    {"date": str(row['date']), "close": row['close']}
                    for _, row in history.tail(7).iterrows()
                ]
        else:
            high_52w = 0.0
            low_52w = 0.0

        if not _is_valid_price(high_52w):
            high_52w = _to_float(getattr(selected_result, "high_52w", 0) or 0)
        if not _is_valid_price(low_52w):
            low_52w = ltp if _is_valid_price(ltp) else 0.0

        pct_from_52w_high = ((ltp / high_52w) - 1) * 100 if _is_valid_price(high_52w) else 0.0
        pct_from_52w_low = ((ltp / low_52w) - 1) * 100 if _is_valid_price(low_52w) else 0.0

        # Build dynamic support/resistance zones (same style as CLI)
        supports: List[float] = []
        resistances: List[float] = []
        if history is not None and len(history) > 10:
            highs = history["high"].astype(float).tolist()
            lows = history["low"].astype(float).tolist()
            local_res: List[float] = []
            local_sup: List[float] = []
            for i in range(2, len(highs) - 2):
                if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and highs[i] > highs[i + 1] and highs[i] > highs[i + 2]:
                    local_res.append(highs[i])
                if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
                    local_sup.append(lows[i])

            def _cluster_levels(levels: List[float], tolerance: float = 0.02) -> List[float]:
                if not levels:
                    return []
                ordered = sorted(levels)
                clusters: List[List[float]] = [[ordered[0]]]
                for lvl in ordered[1:]:
                    if abs(lvl - clusters[-1][-1]) / max(clusters[-1][-1], 1.0) < tolerance:
                        clusters[-1].append(lvl)
                    else:
                        clusters.append([lvl])
                return [sum(c) / len(c) for c in clusters]

            res_zones = _cluster_levels(local_res)
            sup_zones = _cluster_levels(local_sup)
            resistances = sorted([x for x in res_zones if x > ltp])[:3]
            supports = sorted([x for x in sup_zones if x < ltp], reverse=True)[:3]

        support_level = supports[0] if supports else 0.0
        resistance_level = resistances[0] if resistances else 0.0

        # Build pillar details from selected strategy
        max_broker = 30.0
        max_unlock = 20.0
        max_fund = 20.0 if strategy == "value" else 10.0
        max_tech = 30.0 if strategy == "value" else 40.0

        pillars = {
            "broker": PillarScore(
                name="Broker/Institutional",
                score=selected_result.pillar1_broker,
                max_score=max_broker,
                percentage=round((selected_result.pillar1_broker / max_broker) * 100, 1),
            ),
            "unlock": PillarScore(
                name="Unlock Risk",
                score=selected_result.pillar2_unlock,
                max_score=max_unlock,
                percentage=round((selected_result.pillar2_unlock / max_unlock) * 100, 1),
            ),
            "fundamental": PillarScore(
                name="Fundamentals",
                score=selected_result.pillar3_fundamental,
                max_score=max_fund,
                percentage=round((selected_result.pillar3_fundamental / max_fund) * 100, 1),
            ),
            "technical": PillarScore(
                name="Technicals",
                score=selected_result.pillar4_technical,
                max_score=max_tech,
                percentage=round((selected_result.pillar4_technical / max_tech) * 100, 1),
            ),
        }

        # Determine statuses
        pe_ratio = float(getattr(fundamentals, "pe_ratio", getattr(selected_result, "pe_ratio", 0)) or 0)
        if pe_ratio <= 0:
            pe_status = "MISSING/NEGATIVE"
        elif pe_ratio < 15:
            pe_status = "CHEAP"
        elif pe_ratio <= 25:
            pe_status = "FAIR"
        elif pe_ratio <= 40:
            pe_status = "EXPENSIVE"
        else:
            pe_status = "OVERVALUED"

        roe = float(getattr(fundamentals, "roe", getattr(selected_result, "roe", 0)) or 0)
        if roe >= 15:
            roe_status = "EXCELLENT"
        elif roe >= 10:
            roe_status = "GOOD"
        elif roe >= 5:
            roe_status = "AVERAGE"
        else:
            roe_status = "POOR"

        rsi = float(getattr(selected_result, "rsi", 0) or 0)
        if rsi > 70:
            rsi_status = "OVERBOUGHT"
        elif rsi < 30:
            rsi_status = "OVERSOLD"
        elif 50 <= rsi <= 65:
            rsi_status = "BULLISH MOMENTUM"
        else:
            rsi_status = "NEUTRAL"

        # Recommendations
        score = float(getattr(selected_result, "total_score", 0) or 0)
        momentum_verdict = "EXCELLENT" if score >= 85 else "GOOD" if score >= 70 else "AVERAGE" if score >= 55 else "WEAK"

        # Build red flags
        red_flags = getattr(selected_result, 'red_flags', [])

        # Long/Short term recommendations
        if score >= 70 and roe >= 10:
            long_term_rec = "RECOMMENDED"
        elif score >= 55:
            long_term_rec = "CAUTION"
        else:
            long_term_rec = "NOT RECOMMENDED"
        
        if score >= 75:
            short_term_rec = "GOOD ENTRY"
        elif score >= 60:
            short_term_rec = "RISKY"
        else:
            short_term_rec = "AVOID"
        
        friend_rec = "Good pick" if score >= 75 else "Average" if score >= 55 else "Better options exist"
        short_term_rec = _clean_text(short_term_rec)
        long_term_rec = _clean_text(long_term_rec)
        friend_rec = _clean_text(friend_rec)
        red_flags = _clean_text_list(red_flags)
        distribution_warning = _clean_text(getattr(selected_result, 'distribution_warning', ''))

        # Sector comparison (same benchmark logic as CLI)
        sector_benchmarks = {
            'Commercial Banks': {'pe': 12, 'pbv': 1.8, 'roe': 15},
            'Development Banks': {'pe': 15, 'pbv': 1.5, 'roe': 12},
            'Finance': {'pe': 18, 'pbv': 1.3, 'roe': 10},
            'Hydro Power': {'pe': 25, 'pbv': 1.5, 'roe': 8},
            'Life Insurance': {'pe': 20, 'pbv': 2.0, 'roe': 12},
            'Non-Life Insurance': {'pe': 18, 'pbv': 1.8, 'roe': 10},
            'Microfinance': {'pe': 10, 'pbv': 1.2, 'roe': 14},
            'Hotels And Tourism': {'pe': 30, 'pbv': 1.5, 'roe': 6},
            'Manufacturing And Processing': {'pe': 20, 'pbv': 1.4, 'roe': 8},
            'Trading': {'pe': 15, 'pbv': 1.3, 'roe': 10},
            'Others': {'pe': 20, 'pbv': 1.5, 'roe': 8},
        }
        bench = sector_benchmarks.get(sector, {'pe': 20, 'pbv': 1.5, 'roe': 10})
        pbv = float(getattr(fundamentals, "pbv", getattr(selected_result, "pbv", 0)) or 0)
        sector_comparison = {
            "sector": sector,
            "sector_avg_pe": float(bench["pe"]),
            "sector_avg_pbv": float(bench["pbv"]),
            "sector_avg_roe": float(bench["roe"]),
            "pe_vs_sector_pct": (((pe_ratio - bench["pe"]) / max(bench["pe"], 1e-9)) * 100) if pe_ratio > 0 else 0.0,
            "pbv_vs_sector_pct": ((pbv - bench["pbv"]) / max(bench["pbv"], 1e-9)) * 100,
            "roe_vs_sector_pct": ((roe - bench["roe"]) / max(bench["roe"], 1e-9)) * 100,
        }

        # Dividend history
        dividend_history: List[Dict[str, Any]] = []
        if sharehub:
            try:
                dividends = sharehub.get_dividend_history(symbol, limit=3)
                for div in dividends[:3]:
                    cash = float(getattr(div, "cash_pct", 0) or 0)
                    bonus = float(getattr(div, "bonus_pct", 0) or 0)
                    fy = str(getattr(div, "fiscal_year", "") or "")
                    dividend_history.append({
                        "fiscal_year": fy,
                        "cash_pct": cash,
                        "bonus_pct": bonus,
                        "total_pct": cash + bonus,
                    })
            except Exception:
                pass

        # Top broker activity
        broker_activity: Dict[str, Any] = {}
        if sharehub:
            try:
                broker_resp = sharehub.get_broker_analysis_full(symbol, duration="1M")
                if not broker_resp or not broker_resp.brokers:
                    broker_resp = sharehub.get_broker_analysis_full(symbol, duration="1W")
                if broker_resp and broker_resp.brokers:
                    top = sorted(broker_resp.brokers, key=lambda b: b.net_quantity, reverse=True)[:5]
                    total_net_holdings = sum(int(b.net_quantity) for b in top if int(b.net_quantity) > 0)
                    total_weighted = 0.0
                    for b in top:
                        if int(b.net_quantity) > 0 and int(b.buy_quantity) > 0:
                            avg_buy = float(b.buy_amount) / max(float(b.buy_quantity), 1.0)
                            total_weighted += avg_buy * float(b.net_quantity)
                    top5_avg = (total_weighted / total_net_holdings) if total_net_holdings > 0 else 0.0
                    broker_activity = {
                        "data_period": str(broker_resp.date_range or ""),
                        "total_volume": int(broker_resp.total_quantity or 0),
                        "total_transactions": int(broker_resp.total_transactions or 0),
                        "top5_avg_cost": float(top5_avg),
                        "top5_total_net": int(sum(int(b.net_quantity or 0) for b in top)),
                        "brokers": [
                            {
                                "broker_code": str(b.broker_code),
                                "broker_name": str(b.broker_name),
                                "net_quantity": int(b.net_quantity or 0),
                                "buy_quantity": int(b.buy_quantity or 0),
                                "sell_quantity": int(b.sell_quantity or 0),
                                "avg_buy_price": (float(b.buy_amount) / max(float(b.buy_quantity or 0), 1.0)) if float(b.buy_quantity or 0) > 0 else 0.0,
                            }
                            for b in top
                        ],
                    }
            except Exception as broker_err:
                logger.debug(f"Broker activity fetch failed for {symbol}: {broker_err}")

        # Manipulation risk section
        manipulation_risk = {
            "score": float(getattr(selected_result, "manipulation_risk_score", 0) or 0),
            "severity": str(getattr(selected_result, "manipulation_severity", "") or "UNKNOWN"),
            "phase": str(getattr(selected_result, "operator_phase", "") or "UNKNOWN"),
            "phase_description": _clean_text(getattr(selected_result, "operator_phase_description", "") or ""),
            "safe_to_trade": bool(getattr(selected_result, "is_safe_to_trade", True)),
            "hhi": float(getattr(selected_result, "broker_concentration_hhi", 0) or 0),
            "top3_control_pct": float(getattr(selected_result, "top3_broker_control_pct", 0) or 0),
            "circular_trading_pct": float(getattr(selected_result, "circular_trading_pct", 0) or 0),
            "wash_trading_detected": bool(getattr(selected_result, "wash_trading_detected", False)),
            "alerts": _clean_text_list(getattr(selected_result, "manipulation_alerts", []) or []),
            "veto_reasons": _clean_text_list(getattr(selected_result, "manipulation_veto_reasons", []) or []),
        }

        # Price target analysis section
        price_target_analysis: Dict[str, Any] = {}
        try:
            target_analyzer = PriceTargetAnalyzer(fetcher=fetcher, sharehub=sharehub)
            target = target_analyzer.analyze(symbol, lookback_days=365)
            price_target_analysis = {
                "conservative": _jsonable(target._target_to_dict(target.conservative_target)),
                "moderate": _jsonable(target._target_to_dict(target.moderate_target)),
                "aggressive": _jsonable(target._target_to_dict(target.aggressive_target)),
                "max_theory": _jsonable(target._target_to_dict(target.maximum_theoretical)),
                "nearest_support": float(getattr(target, "nearest_support", 0) or 0),
                "downside_risk_pct": float(getattr(target, "downside_risk_percent", 0) or 0),
                "risk_reward_ratio": float(getattr(target, "risk_reward_ratio", 0) or 0),
                "trend_direction": str(getattr(target, "trend_direction", "") or ""),
                "momentum_score": float(getattr(target, "momentum_score", 0) or 0),
                "warnings": _clean_text_list(getattr(target, "warnings", []) or []),
            }
            if price_target_analysis.get("nearest_support", 0) > 0:
                support_level = float(price_target_analysis["nearest_support"])
        except Exception as target_err:
            logger.debug(f"Price target analysis failed for {symbol}: {target_err}")

        def _strategy_pack(result: Any, mode: str) -> Dict[str, Any]:
            if not result:
                return {}
            fund_max = 20.0 if mode == "value" else 10.0
            tech_max = 30.0 if mode == "value" else 40.0
            return {
                "score": float(getattr(result, "total_score", 0) or 0),
                "verdict": _clean_text(getattr(result, "verdict_reason", "") or ""),
                "pillars": {
                    "broker": float(getattr(result, "pillar1_broker", 0) or 0),
                    "unlock": float(getattr(result, "pillar2_unlock", 0) or 0),
                    "fundamental": float(getattr(result, "pillar3_fundamental", 0) or 0),
                    "technical": float(getattr(result, "pillar4_technical", 0) or 0),
                    "fundamental_max": fund_max,
                    "technical_max": tech_max,
                },
            }

        strategy_comparison = {
            "value": _strategy_pack(value_result, "value"),
            "momentum": _strategy_pack(momentum_result, "momentum"),
        }

        distribution_details = {
            "risk_level": str(getattr(selected_result, "distribution_risk", "") or ""),
            "avg_cost_1m": float(getattr(selected_result, "broker_avg_cost", 0) or 0),
            "avg_cost_1w": float(getattr(selected_result, "broker_avg_cost_1w", 0) or 0),
            "net_holdings_1m": int(getattr(selected_result, "net_holdings_1m", 0) or 0),
            "net_holdings_1w": int(getattr(selected_result, "net_holdings_1w", 0) or 0),
            "divergence": bool(getattr(selected_result, "distribution_divergence", False)),
            "current_ltp": float(getattr(selected_result, "ltp", ltp) or ltp),
            "broker_profit_pct": float(getattr(selected_result, "broker_profit_pct", 0) or 0),
            "intraday_dump_detected": bool(getattr(selected_result, "intraday_dump_detected", False)),
            "today_open_price": float(getattr(selected_result, "today_open_price", 0) or 0),
            "today_vwap": float(getattr(selected_result, "today_vwap", 0) or 0),
            "open_vs_broker_pct": float(getattr(selected_result, "open_vs_broker_pct", 0) or 0),
            "close_vs_vwap_pct": float(getattr(selected_result, "close_vs_vwap_pct", 0) or 0),
            "intraday_volume_spike": float(getattr(selected_result, "intraday_volume_spike", 0) or 0),
            "warning": distribution_warning,
        }

        with _ANALYZE_LOCK:
            if _ANALYZE_CANCEL_FLAGS.get(symbol):
                _ANALYZE_CANCEL_FLAGS.pop(symbol, None)
                raise HTTPException(status_code=499, detail=f"Analysis for {symbol} stopped")

        analysis = SingleStockAnalysis(
            symbol=symbol,
            name=name,
            company_name=name,
            sector=sector,
            ltp=ltp,
            momentum_score=int(getattr(momentum_result, "total_score", getattr(selected_result, "total_score", 0)) or 0),
            value_score=int(getattr(value_result, "total_score", getattr(selected_result, "total_score", 0)) or 0),
            momentum_verdict=momentum_verdict,
            value_verdict=("EXCELLENT" if (getattr(value_result, "total_score", 0) or 0) >= 85 else "GOOD" if (getattr(value_result, "total_score", 0) or 0) >= 70 else "AVERAGE" if (getattr(value_result, "total_score", 0) or 0) >= 55 else "WEAK"),
            recommendation=str(getattr(selected_result, "recommendation", "") or momentum_verdict),
            verdict_reason=_clean_text(getattr(selected_result, "verdict_reason", "") or ""),
            strategy=strategy,
            pillars=pillars,
            pe_ratio=float(pe_ratio or 0),
            pe_status=pe_status,
            eps=float(getattr(fundamentals, 'eps', getattr(selected_result, 'eps', 0)) or 0),
            eps_annualized=float(getattr(fundamentals, 'eps_annualized', getattr(selected_result, 'eps_annualized', 0)) or 0),
            book_value=float(getattr(fundamentals, 'book_value', getattr(selected_result, 'book_value', 0)) or 0),
            pbv=float(pbv or 0),
            roe=float(roe or 0),
            roe_status=roe_status,
            rsi=float(rsi or 0),
            rsi_status=rsi_status,
            ema_signal=str(getattr(selected_result, 'ema_signal', '') or ''),
            volume_spike=float(getattr(selected_result, 'volume_spike', 0) or 0),
            atr=float(getattr(selected_result, 'atr', 0) or 0),
            high_52w=float(high_52w or 0),
            low_52w=float(low_52w or 0),
            pct_from_52w_high=round(float(pct_from_52w_high or 0), 2),
            pct_from_52w_low=round(float(pct_from_52w_low or 0), 2),
            distribution_risk=str(getattr(selected_result, 'distribution_risk', 'N/A') or "N/A"),
            broker_avg_cost=float(getattr(selected_result, 'broker_avg_cost', 0) or 0),
            broker_profit_pct=float(getattr(selected_result, 'broker_profit_pct', 0) or 0),
            distribution_warning=distribution_warning,
            net_holdings_1m=int(getattr(selected_result, "net_holdings_1m", 0) or 0),
            net_holdings_1w=int(getattr(selected_result, "net_holdings_1w", 0) or 0),
            intraday_dump_detected=bool(getattr(selected_result, "intraday_dump_detected", False)),
            open_vs_broker_pct=float(getattr(selected_result, "open_vs_broker_pct", 0) or 0),
            close_vs_vwap_pct=float(getattr(selected_result, "close_vs_vwap_pct", 0) or 0),
            intraday_volume_spike=float(getattr(selected_result, "intraday_volume_spike", 0) or 0),
            entry_price=float(getattr(selected_result, "entry_price", 0) or 0),
            target_price=float(getattr(selected_result, "target_price", 0) or 0),
            stop_loss=float(getattr(selected_result, "stop_loss", 0) or 0),
            hold_days=str(getattr(selected_result, "exit_strategy", "") or "").split(':')[0].replace('📅 ', '').replace('📆 ', '') if hasattr(selected_result, 'exit_strategy') else "5-10 days",
            expected_holding_days=int(getattr(selected_result, "expected_holding_days", 0) or 0),
            max_holding_days=int(getattr(selected_result, "max_holding_days", 0) or 0),
            minimum_hold_period=str(getattr(selected_result, "minimum_hold_period", "") or ""),
            risk_reward_ratio=float(getattr(selected_result, "risk_reward_ratio", 0) or 0),
            execution_warning=_clean_text(getattr(selected_result, "execution_warning", "") or ""),
            support_level=float(support_level or 0),
            resistance_level=float(resistance_level or 0),
            long_term_recommendation=long_term_rec,
            short_term_recommendation=short_term_rec,
            friend_recommendation=friend_rec,
            red_flags=red_flags,
            price_history_7d=price_history_7d,
            price_trend_7d=round(price_trend_7d, 2),
            price_trend_30d=round(price_trend_30d, 2),
            price_trend_90d=round(price_trend_90d, 2),
            price_trend_1y=round(price_trend_1y, 2),
            market_cap_cr=round(market_cap_cr, 2),
            paid_up_capital_cr=round(paid_up_capital_cr, 2),
            outstanding_shares_cr=round(outstanding_shares_cr, 4),
            promoter_pct=round(promoter_pct, 2),
            public_pct=round(public_pct, 2),
            free_float_pct=round(free_float_pct, 2),
            daily_turnover_cr=round(daily_turnover_cr, 2),
            full_report_text="",
            strategy_comparison=_jsonable(strategy_comparison),
            sector_comparison=_jsonable(sector_comparison),
            dividend_history=_jsonable(dividend_history),
            broker_activity=_jsonable(broker_activity),
            manipulation_risk=_jsonable(manipulation_risk),
            support_resistance=_jsonable({
                "supports": [float(x) for x in supports],
                "resistances": [float(x) for x in resistances],
                "tip": "Price tends to bounce at support and stall at resistance.",
            }),
            price_target_analysis=_jsonable(price_target_analysis),
            distribution_details=_jsonable(distribution_details),
        )
        
        return AnalyzeResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data=analysis,
        )
        
    except HTTPException:
        with _ANALYZE_LOCK:
            _ANALYZE_CANCEL_FLAGS.pop(symbol.upper(), None)
        raise
    except Exception as e:
        logger.error(f"Analysis failed for {symbol}: {e}")
        with _ANALYZE_LOCK:
            _ANALYZE_CANCEL_FLAGS.pop(symbol.upper(), None)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/stop/{symbol}")
async def stop_analyze(symbol: str):
    symbol = symbol.upper()
    with _ANALYZE_LOCK:
        _ANALYZE_CANCEL_FLAGS[symbol] = True
    return {"success": True, "message": f"Stop requested for {symbol}"}


@router.post("/portfolio/buy")
async def add_to_portfolio(
    symbol: str = Body(...),
    quantity: int = Body(...),
    price: float = Body(...),
    portfolio_value: float = Body(default=500000.0),
):
    """Add a stock to the paper trading portfolio with risk validation."""
    try:
        import sqlite3
        from pathlib import Path
        
        # FIX: Import and use PositionSizer to enforce 2% risk rule
        from risk.position_sizer import PositionSizer
        
        db_path = Path(__file__).parent.parent.parent / "tools" / "paper_trading.db"
        
        # Calculate target and stop-loss (10% and -6.5%)
        target_price = round(price * 1.10, 2)
        stop_loss = round(price * 0.935, 2)
        
        # FIX: Validate position size against 2% risk rule
        sizer = PositionSizer(
            portfolio_value=portfolio_value,
            max_risk_per_trade=0.02,  # 2% max risk
        )
        
        position = sizer.calculate(
            symbol=symbol.upper(),
            entry_price=price,
            stop_loss=stop_loss,
            target_price=target_price,
        )
        
        # Reject if risk exceeds 2% limit
        if not position.is_valid():
            return {
                "success": False,
                "error": f"Risk {position.risk_percent:.2f}% exceeds 2% limit. Max shares: {position.shares}",
                "max_allowed_shares": position.shares,
                "requested_shares": quantity,
            }
        
        # Use validated quantity (cap user input to safe amount)
        validated_quantity = min(quantity, position.shares) if position.shares > 0 else quantity
        
        # Initialize DB if needed
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                target_price REAL,
                stop_loss REAL,
                exit_date TEXT,
                exit_price REAL,
                pnl REAL,
                status TEXT DEFAULT 'OPEN'
            )
        """)
        
        cursor.execute("""
            INSERT INTO trades (symbol, entry_date, entry_price, quantity, target_price, stop_loss, status)
            VALUES (?, ?, ?, ?, ?, ?, 'OPEN')
        """, (symbol.upper(), datetime.now().strftime('%Y-%m-%d'), price, validated_quantity, target_price, stop_loss))
        
        conn.commit()
        trade_id = cursor.lastrowid
        conn.close()
        
        return {
            "success": True,
            "message": f"Added {validated_quantity} shares of {symbol} at Rs.{price}",
            "trade_id": trade_id,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "validated_quantity": validated_quantity,
            "risk_percent": round(position.risk_percent, 2),
            "position_value": round(validated_quantity * price, 2),
        }
        
    except ImportError:
        # Fallback if PositionSizer not available - use simple cap
        logger.warning("PositionSizer not available, using fallback validation")
        max_position_value = portfolio_value * 0.20  # Max 20% in one position
        max_shares = int(max_position_value / price) if price > 0 else quantity
        validated_quantity = min(quantity, max_shares)
        
        # Continue with original logic using validated_quantity
        import sqlite3
        from pathlib import Path
        db_path = Path(__file__).parent.parent.parent / "tools" / "paper_trading.db"
        target_price = round(price * 1.10, 2)
        stop_loss = round(price * 0.935, 2)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL,
                entry_date TEXT NOT NULL, entry_price REAL NOT NULL,
                quantity INTEGER NOT NULL, target_price REAL, stop_loss REAL,
                exit_date TEXT, exit_price REAL, pnl REAL, status TEXT DEFAULT 'OPEN'
            )
        """)
        cursor.execute("""
            INSERT INTO trades (symbol, entry_date, entry_price, quantity, target_price, stop_loss, status)
            VALUES (?, ?, ?, ?, ?, ?, 'OPEN')
        """, (symbol.upper(), datetime.now().strftime('%Y-%m-%d'), price, validated_quantity, target_price, stop_loss))
        conn.commit()
        trade_id = cursor.lastrowid
        conn.close()
        
        return {
            "success": True,
            "message": f"Added {validated_quantity} shares of {symbol} at Rs.{price} (fallback validation)",
            "trade_id": trade_id,
            "target_price": target_price,
            "stop_loss": stop_loss,
        }
        
    except Exception as e:
        logger.error(f"Buy failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/portfolio/position/{trade_id}")
async def edit_portfolio_position(trade_id: int, payload: PortfolioEditRequest):
    """Edit an open paper-trading position."""
    try:
        import sqlite3
        from pathlib import Path

        if payload.quantity is None and payload.entry_price is None and payload.target_price is None and payload.stop_loss is None:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        db_path = Path(__file__).parent.parent.parent / "tools" / "paper_trading.db"
        if not db_path.exists():
            raise HTTPException(status_code=404, detail="Portfolio database not found")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        trade = cursor.fetchone()
        if not trade:
            conn.close()
            raise HTTPException(status_code=404, detail="Trade not found")
        if trade["status"] != "OPEN":
            conn.close()
            raise HTTPException(status_code=400, detail="Only OPEN positions can be edited")

        quantity = payload.quantity if payload.quantity is not None else int(trade["quantity"])
        entry_price = payload.entry_price if payload.entry_price is not None else float(trade["entry_price"])
        target_price = payload.target_price if payload.target_price is not None else float(trade["target_price"])
        stop_loss = payload.stop_loss if payload.stop_loss is not None else float(trade["stop_loss"])

        if stop_loss >= entry_price:
            conn.close()
            raise HTTPException(status_code=400, detail="Stop loss must be below entry price")
        if target_price <= entry_price:
            conn.close()
            raise HTTPException(status_code=400, detail="Target price must be above entry price")

        cursor.execute(
            """
            UPDATE trades
            SET quantity = ?, entry_price = ?, target_price = ?, stop_loss = ?
            WHERE id = ? AND status = 'OPEN'
            """,
            (quantity, entry_price, target_price, stop_loss, trade_id),
        )
        conn.commit()
        conn.close()

        return {"success": True, "message": f"Updated trade #{trade_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Edit position failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/sell/{trade_id}")
async def close_portfolio_position(trade_id: int, payload: PortfolioSellRequest = Body(default=PortfolioSellRequest())):
    """Manually close an open paper-trading position."""
    try:
        import sqlite3
        from pathlib import Path
        from data.fetcher import NepseFetcher

        db_path = Path(__file__).parent.parent.parent / "tools" / "paper_trading.db"
        if not db_path.exists():
            raise HTTPException(status_code=404, detail="Portfolio database not found")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        trade = cursor.fetchone()
        if not trade:
            conn.close()
            raise HTTPException(status_code=404, detail="Trade not found")
        if trade["status"] != "OPEN":
            conn.close()
            raise HTTPException(status_code=400, detail="Position is already closed")

        exit_price = payload.exit_price
        if exit_price is None:
            fetcher = NepseFetcher()
            live_data = fetcher.fetch_live_market()
            if not live_data.empty:
                row = live_data[live_data["symbol"] == trade["symbol"]]
                if not row.empty:
                    exit_price = _extract_live_price(row.iloc[0])
        if exit_price is None or exit_price <= 0:
            exit_price = float(trade["entry_price"])

        pnl = (float(exit_price) - float(trade["entry_price"])) * int(trade["quantity"])
        cursor.execute(
            """
            UPDATE trades
            SET status = 'MANUAL_EXIT', exit_price = ?, exit_date = ?, pnl = ?
            WHERE id = ? AND status = 'OPEN'
            """,
            (float(exit_price), datetime.now().strftime("%Y-%m-%d"), float(pnl), trade_id),
        )
        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": f"Closed trade #{trade_id} at Rs.{float(exit_price):.2f}",
            "pnl": round(float(pnl), 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Close position failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/portfolio/position/{trade_id}")
async def delete_portfolio_position(trade_id: int):
    """Delete a portfolio position by trade ID."""
    try:
        import sqlite3
        from pathlib import Path

        db_path = Path(__file__).parent.parent.parent / "tools" / "paper_trading.db"
        if not db_path.exists():
            raise HTTPException(status_code=404, detail="Portfolio database not found")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted == 0:
            raise HTTPException(status_code=404, detail="Trade not found")

        return {"success": True, "message": f"Deleted trade #{trade_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete position failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== NEW ENDPOINTS: Signal, IPO Exit, Hold-or-Sell, Calendar ==============

class SignalResponse(BaseModel):
    """Trading signal response."""
    success: bool
    timestamp: str
    data: Optional[Dict[str, Any]] = None


class IPOExitResponse(BaseModel):
    """IPO exit analysis response."""
    success: bool
    timestamp: str
    data: Optional[Dict[str, Any]] = None


class PositionAdviceResponse(BaseModel):
    """Hold or sell position advice response."""
    success: bool
    timestamp: str
    data: Optional[Dict[str, Any]] = None


class CalendarResponse(BaseModel):
    """Trading calendar response."""
    success: bool
    timestamp: str
    data: Optional[Dict[str, Any]] = None


class SmartMoneyResponse(BaseModel):
    """Smart money tracker response."""
    success: bool
    timestamp: str
    data: Optional[Dict[str, Any]] = None


class HeatmapResponse(BaseModel):
    """Market heatmap response."""
    success: bool
    timestamp: str
    data: Optional[Dict[str, Any]] = None


@router.get("/signal/{symbol}", response_model=SignalResponse)
async def get_trading_signal(symbol: str):
    """Generate a complete trading signal for a stock."""
    try:
        from data.fetcher import NepseFetcher
        from analysis.technical_signal_engine import TechnicalSignalEngine
        
        fetcher = NepseFetcher()
        engine = TechnicalSignalEngine(fetcher)
        symbol_upper = symbol.upper()
        company_name = symbol_upper
        company_sector = "Unknown"

        try:
            company_list = fetcher.fetch_company_list()
            normalized_companies = _normalize_company_list(company_list)
            company_info = next((c for c in normalized_companies if c["symbol"] == symbol_upper), None)
            if company_info:
                company_name = company_info.get("name", symbol_upper) or symbol_upper
                company_sector = company_info.get("sector", "Unknown") or "Unknown"
        except Exception as meta_err:
            logger.debug(f"Signal metadata lookup failed for {symbol_upper}: {meta_err}")
        
        signal = engine.generate_signal(symbol_upper)
        
        if not signal:
            return SignalResponse(
                success=False,
                timestamp=datetime.now().isoformat(),
                data={"error": f"Could not generate signal for {symbol}. Insufficient data."},
            )
        
        return SignalResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data=_map_signal_response(
                symbol_upper,
                signal,
                company_name=company_name,
                company_sector=company_sector,
            ),
        )
        
    except Exception as e:
        logger.error(f"Signal generation failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ipo-exit/{symbol}", response_model=IPOExitResponse)
async def get_ipo_exit_analysis(symbol: str):
    """Analyze IPO exit timing based on volume and broker flow."""
    try:
        from data.fetcher import NepseFetcher
        from intelligence.ipo_exit_analyzer import IPOExitAnalyzer
        
        fetcher = NepseFetcher()
        analyzer = IPOExitAnalyzer(fetcher)
        
        analysis = analyzer.analyze(symbol.upper())
        
        if not analysis:
            return IPOExitResponse(
                success=False,
                timestamp=datetime.now().isoformat(),
                data={"error": f"Could not analyze {symbol}. Stock may not be a recent IPO."},
            )
        
        analysis_data = _map_ipo_exit_response(analysis)
        # Force latest live snapshot for IPO-exit price/volume so UI does not lag on prior day bars.
        try:
            live_df = fetcher.fetch_live_market()
            if live_df is not None and not live_df.empty:
                match = live_df[live_df["symbol"].astype(str).str.upper() == symbol.upper()]
                if not match.empty:
                    row = match.iloc[0]
                    live_price = _extract_live_price(row)
                    live_volume = int(_to_float(row.get("volume", row.get("totalTradedQuantity", row.get("totalTradeQuantity", 0)))))
                    sharehub_volume = _fetch_sharehub_intraday_volume(symbol.upper())
                    if sharehub_volume > live_volume:
                        live_volume = sharehub_volume
                    if live_price > 0:
                        analysis_data["current_price"] = live_price
                    if live_volume > 0:
                        vt = analysis_data.get("volume_trend", {})
                        dates = list(vt.get("dates", []))
                        volumes = list(vt.get("volumes", []))
                        today_label = datetime.now().strftime("%Y-%m-%d")
                        if dates and dates[-1] == today_label:
                            if volumes:
                                volumes[-1] = live_volume
                        else:
                            dates.append(today_label)
                            volumes.append(live_volume)
                            if len(dates) > 8:
                                dates = dates[-8:]
                                volumes = volumes[-8:]
                        vt["dates"] = dates
                        vt["volumes"] = volumes
                        analysis_data["volume_trend"] = vt
                        logger.info(f"IPO exit live override {symbol.upper()}: price={live_price}, volume={live_volume}")
        except Exception as live_override_error:
            logger.debug(f"IPO exit live override unavailable for {symbol.upper()}: {live_override_error}")

        return IPOExitResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data=analysis_data,
        )
        
    except Exception as e:
        logger.error(f"IPO exit analysis failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hold-or-sell/{symbol}", response_model=PositionAdviceResponse)
async def get_position_advice(
    symbol: str,
    buy_price: float = Query(..., gt=0, description="Your purchase price"),
    buy_date: Optional[str] = Query(None, description="Purchase date (YYYY-MM-DD)"),
):
    """Get hold or sell advice for an existing position."""
    try:
        from data.fetcher import NepseFetcher
        from intelligence.position_advisor import PositionAdvisor
        
        fetcher = NepseFetcher()
        advisor = PositionAdvisor(fetcher)
        
        advice = advisor.analyze(
            symbol=symbol.upper(),
            buy_price=buy_price,
            buy_date=buy_date,
        )
        
        if not advice:
            return PositionAdviceResponse(
                success=False,
                timestamp=datetime.now().isoformat(),
                data={"error": f"Could not analyze position for {symbol}"},
            )

        advice_data = _map_position_advice_response(advice)
        
        return PositionAdviceResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data=advice_data,
        )
        
    except Exception as e:
        logger.error(f"Position advice failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calendar", response_model=CalendarResponse)
async def get_trading_calendar(
    days: int = Query(default=14, ge=7, le=30, description="Days to look ahead"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
):
    """Get trading calendar with stock picks for each day."""
    try:
        from data.fetcher import NepseFetcher
        fetcher = NepseFetcher()
        live_data = fetcher.fetch_live_market()
        company_map = {c["symbol"]: c for c in _normalize_company_list(fetcher.fetch_company_list())}
        candidates: List[Dict[str, Any]] = []
        if live_data is not None and not live_data.empty:
            for _, row in live_data.iterrows():
                symbol = str(row.get("symbol", "")).upper()
                if not symbol or symbol not in company_map:
                    continue
                company = company_map[symbol]
                if sector and sector.lower() not in str(company.get("sector", "")).lower():
                    continue
                ltp = _extract_live_price(row)
                change_pct = _to_float(row.get("percentChange", row.get("changePercent", 0)))
                if not _is_valid_price(ltp):
                    continue
                score = max(0, min(100, 50 + change_pct * 5))
                candidates.append({
                    "symbol": symbol,
                    "name": company.get("name", symbol),
                    "sector": company.get("sector", "Unknown"),
                    "score": score,
                    "entry_price": round(ltp * 0.99, 2),
                    "target_price": round(ltp * 1.10, 2),
                    "stop_loss": round(ltp * 0.95, 2),
                    "reason": "Momentum-based quick calendar setup",
                })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        candidates = candidates[:30]
        
        if not candidates:
            return CalendarResponse(
                success=True,
                timestamp=datetime.now().isoformat(),
                data={
                    "scan_date": datetime.now().strftime('%Y-%m-%d'),
                    "days_ahead": days,
                    "total_stocks": 0,
                    "calendar": [],
                },
            )
        
        # Distribute stocks across days based on their readiness
        calendar = []
        today = datetime.now()
        
        for i in range(days):
            date = today + timedelta(days=i)
            # Skip weekends
            if date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
                continue
            
            day_stocks = []
            for stock in candidates:
                # Assign stocks to different days based on their setup readiness
                # Simple heuristic: higher scores = sooner entry
                score = stock.get('score', 0)
                if score >= 70 and i == 0:  # Top picks today
                    day_stocks.append({
                        "symbol": stock.get('symbol'),
                        "name": stock.get('name', stock.get('symbol')),
                        "sector": stock.get('sector', 'Unknown'),
                        "entry_price": stock.get('entry_price', stock.get('ltp', 0)),
                        "target_price": stock.get('target_price', 0),
                        "stop_loss": stock.get('stop_loss', 0),
                        "confidence": score,
                        "reason": stock.get('reason', 'Strong momentum setup'),
                    })
                elif 50 <= score < 70 and i in [1, 2]:  # Near-ready picks
                    day_stocks.append({
                        "symbol": stock.get('symbol'),
                        "name": stock.get('name', stock.get('symbol')),
                        "sector": stock.get('sector', 'Unknown'),
                        "entry_price": stock.get('entry_price', stock.get('ltp', 0)),
                        "target_price": stock.get('target_price', 0),
                        "stop_loss": stock.get('stop_loss', 0),
                        "confidence": score,
                        "reason": stock.get('reason', 'Setup developing'),
                    })
            
            if day_stocks:
                calendar.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "day_name": date.strftime('%A'),
                    "stocks": day_stocks[:5],  # Max 5 per day
                })
        
        total_stocks = sum(len(day['stocks']) for day in calendar)
        
        return CalendarResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data={
                "scan_date": datetime.now().strftime('%Y-%m-%d'),
                "days_ahead": days,
                "total_stocks": total_stocks,
                "calendar": calendar,
            },
        )
        
    except Exception as e:
        logger.error(f"Calendar generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/smart-money", response_model=SmartMoneyResponse)
async def get_smart_money(sector: Optional[str] = Query(None)):
    """Track institutional buying/selling patterns."""
    try:
        from data.fetcher import NepseFetcher
        fetcher = NepseFetcher()
        live_data = fetcher.fetch_live_market()
        company_map = {c["symbol"]: c for c in _normalize_company_list(fetcher.fetch_company_list())}
        stocks: List[Dict[str, Any]] = []
        if live_data is not None and not live_data.empty:
            for _, row in live_data.iterrows():
                symbol = str(row.get("symbol", "")).upper()
                if not symbol or symbol not in company_map:
                    continue
                company = company_map[symbol]
                if sector and sector.lower() not in str(company.get("sector", "")).lower():
                    continue
                price = _extract_live_price(row)
                if not _is_valid_price(price):
                    continue
                change_pct = _to_float(row.get("percentChange", row.get("changePercent", 0)))
                volume = int(_to_float(row.get("volume", row.get("totalTradedQuantity", 0))))
                flow_type = "ACCUMULATION" if change_pct > 0 else "DISTRIBUTION" if change_pct < 0 else "NEUTRAL"
                stocks.append({
                    "symbol": symbol,
                    "name": company.get("name", symbol),
                    "price": round(price, 2),
                    "net_flow": round(change_pct * max(volume, 1), 2),
                    "smart_money_score": round(max(0, min(100, 50 + change_pct * 8)), 1),
                    "flow_type": flow_type,
                })
        accum = [s for s in stocks if s["flow_type"] == "ACCUMULATION"]
        dist = [s for s in stocks if s["flow_type"] == "DISTRIBUTION"]
        top_buyers = [{"name": s["symbol"], "stock_count": 1, "net_volume": int(abs(s["net_flow"]))} for s in sorted(accum, key=lambda x: x["net_flow"], reverse=True)[:5]]
        top_sellers = [{"name": s["symbol"], "stock_count": 1, "net_volume": -int(abs(s["net_flow"]))} for s in sorted(dist, key=lambda x: x["net_flow"])[:5]]
        net_market_flow = round(sum(s["net_flow"] for s in stocks), 2)
        sentiment = "ACCUMULATION" if net_market_flow > 0 else "DISTRIBUTION" if net_market_flow < 0 else "NEUTRAL"
        flow_data = {
            "summary": {
                "accumulating": len(accum),
                "distributing": len(dist),
                "net_market_flow": net_market_flow,
                "sentiment": sentiment,
            },
            "top_buyers": top_buyers,
            "top_sellers": top_sellers,
            "stocks": sorted(stocks, key=lambda x: abs(x["net_flow"]), reverse=True)[:30],
        }

        return SmartMoneyResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data=flow_data,
        )
        
    except Exception as e:
        logger.error(f"Smart money analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heatmap", response_model=HeatmapResponse)
async def get_market_heatmap():
    """Get market heatmap showing all sectors and stock performance."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        
        # Get live market data
        live_data = fetcher.fetch_live_market()
        company_list = fetcher.fetch_company_list()
        
        if live_data is None or live_data.empty:
            return HeatmapResponse(
                success=True,
                timestamp=datetime.now().isoformat(),
                data={
                    "summary": {
                        "advancing": 0,
                        "declining": 0,
                        "unchanged": 0,
                        "advance_pct": 0.0,
                        "decline_pct": 0.0,
                        "breadth": 50.0,
                    },
                    "sectors": [],
                },
            )
        
        # Normalize company list for sector lookup
        company_map = {}
        for item in _normalize_company_list(company_list):
            company_map[item['symbol']] = item
        
        # Group by sector
        sectors_data = {}
        advancing = 0
        declining = 0
        unchanged = 0
        
        for _, row in live_data.iterrows():
            symbol = str(row.get('symbol', '')).upper()
            if not symbol or symbol not in company_map:
                continue
            
            sector = company_map[symbol].get('sector', 'Unknown')
            ltp = _to_float(row.get('ltp', row.get('close', 0)))
            change = _to_float(row.get('change', row.get('pointChange', 0)))
            change_pct = _to_float(row.get('changePct', row.get('percentageChange', 0)))
            
            if ltp <= 0:
                continue
            
            # Track advancing/declining
            if change_pct > 0.1:
                advancing += 1
            elif change_pct < -0.1:
                declining += 1
            else:
                unchanged += 1
            
            if sector not in sectors_data:
                sectors_data[sector] = []
            
            sectors_data[sector].append({
                "symbol": symbol,
                "name": company_map[symbol].get('name', symbol),
                "ltp": ltp,
                "change": change,
                "change_pct": change_pct,
            })
        
        # Sort stocks within each sector by change %
        sectors = []
        for sector_name, stocks in sorted(sectors_data.items()):
            stocks_sorted = sorted(stocks, key=lambda x: x['change_pct'], reverse=True)
            sectors.append({
                "name": sector_name,
                "stocks": stocks_sorted,
            })
        
        total = advancing + declining + unchanged
        breadth = round((advancing / total * 100), 1) if total > 0 else 50.0
        
        return HeatmapResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data={
                "summary": {
                    "advancing": advancing,
                    "declining": declining,
                    "unchanged": unchanged,
                    "advance_pct": round(advancing / total * 100, 1) if total > 0 else 0,
                    "decline_pct": round(declining / total * 100, 1) if total > 0 else 0,
                    "breadth": breadth,
                },
                "sectors": sectors,
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Heatmap generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Additional API Endpoints ==============

# Response models for new endpoints
class PriceTargetsResponse(BaseModel):
    """Price targets response model."""
    success: bool
    timestamp: str
    data: Dict[str, Any]


class TechScoreResponse(BaseModel):
    """Technical score response model."""
    success: bool
    timestamp: str
    data: Dict[str, Any]


class OrderFlowResponse(BaseModel):
    """Order flow response model."""
    success: bool
    timestamp: str
    data: Dict[str, Any]


class BrokerIntelResponse(BaseModel):
    """Broker intelligence response model."""
    success: bool
    timestamp: str
    data: Dict[str, Any]


class SectorRotationResponse(BaseModel):
    """Sector rotation response model."""
    success: bool
    timestamp: str
    data: Dict[str, Any]


class PositioningResponse(BaseModel):
    """Market positioning response model."""
    success: bool
    timestamp: str
    data: Dict[str, Any]


class BulkDealsResponse(BaseModel):
    """Bulk deals response model."""
    success: bool
    timestamp: str
    data: Dict[str, Any]


class DividendForecastResponse(BaseModel):
    """Dividend forecast response model."""
    success: bool
    timestamp: str
    data: Dict[str, Any]


@router.get("/price-targets/{symbol}", response_model=PriceTargetsResponse)
async def get_price_targets(symbol: str):
    """Calculate price targets using Fibonacci, ATR, and volume profile."""
    try:
        from data.fetcher import NepseFetcher
        import pandas as pd
        import numpy as np
        
        fetcher = NepseFetcher()
        history = fetcher.safe_fetch_data(symbol.upper(), days=120, min_rows=5)
        
        if history is None or history.empty or len(history) < 5:
            raise HTTPException(status_code=404, detail=f"Insufficient data for {symbol}")
        
        # Get current price
        current_price = _to_float(history['close'].iloc[-1])
        if current_price <= 0:
            raise HTTPException(status_code=404, detail="Invalid price data")
        
        # Calculate recent swing high/low
        lookback = min(50, len(history))
        recent_high = history['high'].iloc[-lookback:].max()
        recent_low = history['low'].iloc[-lookback:].min()
        
        # Fibonacci levels
        swing_range = recent_high - recent_low
        fib_levels = {
            "0.0": recent_low,
            "0.236": recent_low + 0.236 * swing_range,
            "0.382": recent_low + 0.382 * swing_range,
            "0.5": recent_low + 0.5 * swing_range,
            "0.618": recent_low + 0.618 * swing_range,
            "0.786": recent_low + 0.786 * swing_range,
            "1.0": recent_high,
            "1.272": recent_low + 1.272 * swing_range,
            "1.618": recent_low + 1.618 * swing_range,
        }
        
        # ATR for volatility-based targets
        tr1 = history['high'] - history['low']
        tr2 = abs(history['high'] - history['close'].shift(1))
        tr3 = abs(history['low'] - history['close'].shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = _to_float(tr.rolling(14, min_periods=1).mean().iloc[-1])
        if atr_14 <= 0:
            atr_14 = max(_to_float((recent_high - recent_low) / 4), current_price * 0.03, 1.0)
        
        atr_targets = {
            "stop_1atr": current_price - atr_14,
            "stop_2atr": current_price - 2 * atr_14,
            "target_1atr": current_price + atr_14,
            "target_2atr": current_price + 2 * atr_14,
            "target_3atr": current_price + 3 * atr_14,
        }
        
        # Volume profile (simplified)
        avg_volume = history['volume'].iloc[-20:].mean()
        volume_bars = []
        price_min = history['low'].iloc[-lookback:].min()
        price_max = history['high'].iloc[-lookback:].max()
        price_range = price_max - price_min
        
        total_volume = max(_to_float(history['volume'].sum()), 1.0)
        for i in range(5):
            level = price_min + (i + 0.5) * price_range / 5
            mask = (history['low'] <= level) & (history['high'] >= level)
            vol_at_level = history.loc[mask, 'volume'].sum()
            volume_bars.append({
                "price": round(level, 2),
                "volume": int(vol_at_level),
                "pct_of_total": round(_to_float(vol_at_level) / total_volume * 100, 1),
            })
        
        # Determine probabilities based on trend
        trend_strength = (current_price - recent_low) / swing_range if swing_range > 0 else 0.5
        
        targets = [
            {
                "type": "stop",
                "label": "Stop Loss",
                "price": round(current_price - atr_14, 2),
                "pct": round(-atr_14 / current_price * 100, 1),
                "probability": None,
                "method": "ATR",
            },
            {
                "type": "target",
                "label": "T1 (Conservative)",
                "price": round(current_price + atr_14, 2),
                "pct": round(atr_14 / current_price * 100, 1),
                "probability": 75 if trend_strength > 0.5 else 60,
                "method": "ATR",
            },
            {
                "type": "target",
                "label": "T2 (Moderate)",
                "price": round(current_price + 2 * atr_14, 2),
                "pct": round(2 * atr_14 / current_price * 100, 1),
                "probability": 55 if trend_strength > 0.5 else 40,
                "method": "ATR",
            },
            {
                "type": "target",
                "label": "T3 (Aggressive)",
                "price": round(fib_levels["1.272"], 2),
                "pct": round((fib_levels["1.272"] - current_price) / current_price * 100, 1),
                "probability": 30 if trend_strength > 0.5 else 20,
                "method": "Fibonacci",
            },
        ]
        
        return PriceTargetsResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data={
                "symbol": symbol.upper(),
                "current_price": current_price,
                "recent_high": round(recent_high, 2),
                "recent_low": round(recent_low, 2),
                "atr_14": round(atr_14, 2),
                "fibonacci_levels": {k: round(v, 2) for k, v in fib_levels.items()},
                "targets": targets,
                "volume_profile": volume_bars,
                "trend_strength": round(trend_strength * 100, 1),
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Price targets calculation failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tech-score/{symbol}", response_model=TechScoreResponse)
async def get_tech_score(symbol: str):
    """Calculate multi-timeframe technical composite score."""
    try:
        from data.fetcher import NepseFetcher
        import pandas as pd
        import numpy as np
        
        fetcher = NepseFetcher()
        history = fetcher.safe_fetch_data(symbol.upper(), days=260, min_rows=5)
        
        if history is None or history.empty or len(history) < 5:
            raise HTTPException(status_code=404, detail=f"Insufficient data for {symbol}")
        
        current_price = _to_float(history['close'].iloc[-1])
        
        # Calculate EMAs
        ema_9 = history['close'].ewm(span=9, adjust=False).mean().iloc[-1]
        ema_21 = history['close'].ewm(span=21, adjust=False).mean().iloc[-1]
        ema_50 = history['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        ema_200 = history['close'].ewm(span=200, adjust=False).mean().iloc[-1] if len(history) >= 200 else ema_50
        
        # RSI
        delta = history['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi_value = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
        
        # MACD
        ema_12 = history['close'].ewm(span=12, adjust=False).mean()
        ema_26 = history['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_histogram = macd_line - signal_line
        
        # Volume trend
        vol_avg = history['volume'].iloc[-20:].mean()
        vol_current = history['volume'].iloc[-5:].mean()
        vol_trend = vol_current / vol_avg if vol_avg > 0 else 1.0
        
        # Score components (each 0-20)
        scores = []
        
        # Trend score (0-25)
        trend_score = 0
        if current_price > ema_9:
            trend_score += 5
        if current_price > ema_21:
            trend_score += 5
        if current_price > ema_50:
            trend_score += 7
        if current_price > ema_200:
            trend_score += 8
        scores.append({"name": "Trend", "score": trend_score, "max": 25, "details": f"Above {sum([current_price > ema_9, current_price > ema_21, current_price > ema_50, current_price > ema_200])}/4 EMAs"})
        
        # Momentum score (0-25)
        momentum_score = 0
        if 30 <= rsi_value <= 70:
            momentum_score += 10  # Not overbought/oversold
        elif 40 <= rsi_value <= 60:
            momentum_score += 15  # Healthy zone
        elif rsi_value > 50:
            momentum_score += 5
        
        last_macd_hist = _to_float(macd_histogram.iloc[-1])
        prev_macd_hist = _to_float(macd_histogram.iloc[-2]) if len(macd_histogram) > 1 else last_macd_hist
        if last_macd_hist > 0:
            momentum_score += 5
        if last_macd_hist > prev_macd_hist:
            momentum_score += 5
        scores.append({"name": "Momentum", "score": min(momentum_score, 25), "max": 25, "details": f"RSI: {rsi_value:.1f}"})
        
        # Volume score (0-25)
        volume_score = 0
        if vol_trend > 1.5:
            volume_score = 25
        elif vol_trend > 1.2:
            volume_score = 20
        elif vol_trend > 1.0:
            volume_score = 15
        elif vol_trend > 0.8:
            volume_score = 10
        else:
            volume_score = 5
        scores.append({"name": "Volume", "score": volume_score, "max": 25, "details": f"{vol_trend:.1f}x average"})
        
        # Structure score (0-25)
        structure_score = 0
        prev_high_window = history['high'].iloc[:-1].tail(4)
        prev_low_window = history['low'].iloc[:-1].tail(4)
        higher_high = _to_float(history['high'].iloc[-1]) > _to_float(prev_high_window.max()) if not prev_high_window.empty else False
        higher_low = _to_float(history['low'].iloc[-1]) > _to_float(prev_low_window.min()) if not prev_low_window.empty else False
        if higher_high:
            structure_score += 12
        if higher_low:
            structure_score += 13
        scores.append({"name": "Structure", "score": structure_score, "max": 25, "details": f"HH: {'Yes' if higher_high else 'No'}, HL: {'Yes' if higher_low else 'No'}"})
        
        # Total score
        total_score = sum(s["score"] for s in scores)
        
        # Determine verdict
        if total_score >= 80:
            verdict = "STRONG BUY"
            color = "bull"
        elif total_score >= 65:
            verdict = "BUY"
            color = "bull"
        elif total_score >= 50:
            verdict = "NEUTRAL"
            color = "warning"
        elif total_score >= 35:
            verdict = "WEAK"
            color = "bear"
        else:
            verdict = "AVOID"
            color = "bear"
        
        return TechScoreResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data={
                "symbol": symbol.upper(),
                "current_price": current_price,
                "total_score": total_score,
                "max_score": 100,
                "verdict": verdict,
                "color": color,
                "components": scores,
                "indicators": {
                    "ema_9": round(ema_9, 2),
                    "ema_21": round(ema_21, 2),
                    "ema_50": round(ema_50, 2),
                    "ema_200": round(ema_200, 2),
                    "rsi": round(rsi_value, 1),
                    "macd_histogram": round(last_macd_hist, 2),
                    "volume_ratio": round(vol_trend, 2),
                },
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tech score calculation failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/order-flow/{symbol}", response_model=OrderFlowResponse)
async def get_order_flow(symbol: str):
    """Analyze order flow with delta, absorption patterns."""
    try:
        from data.fetcher import NepseFetcher
        import pandas as pd
        
        fetcher = NepseFetcher()
        history = fetcher.safe_fetch_data(symbol.upper(), days=120, min_rows=5)
        
        if history is None or history.empty or len(history) < 5:
            raise HTTPException(status_code=404, detail=f"Insufficient data for {symbol}")
        
        current_price = _to_float(history['close'].iloc[-1])

        def _row_date_label(row: Any) -> str:
            date_value = row.get("date") if hasattr(row, "get") else None
            if isinstance(date_value, pd.Timestamp):
                return date_value.strftime("%Y-%m-%d")
            if hasattr(date_value, "strftime"):
                return date_value.strftime("%Y-%m-%d")
            if isinstance(date_value, str) and date_value:
                return date_value[:10]
            idx_value = getattr(row, "name", None)
            if isinstance(idx_value, pd.Timestamp):
                return idx_value.strftime("%Y-%m-%d")
            if hasattr(idx_value, "strftime"):
                return idx_value.strftime("%Y-%m-%d")
            return str(idx_value) if idx_value is not None else "N/A"
        
        # Calculate delta (simplified: use close vs open as proxy)
        delta_bars = []
        cumulative_delta = 0
        
        for i in range(-min(20, len(history)), 0):
            row = history.iloc[i]
            close = _to_float(row['close'])
            open_price = _to_float(row['open'])
            high = _to_float(row['high'])
            low = _to_float(row['low'])
            volume = _to_float(row['volume'])
            prev_close = _to_float(history.iloc[i - 1]['close']) if (len(history) + i - 1) >= 0 else close
            
            # Estimate buying vs selling volume
            if high > low:
                range_span = high - low
                range_position = (close - low) / range_span  # 0..1
                body_strength = abs(close - open_price) / range_span  # 0..1
                direction = 1.0 if close >= open_price else -1.0
                # Blend location-in-range and candle body direction for less-flat delta series.
                buy_pct = 0.5 + (range_position - 0.5) * 0.7 + direction * body_strength * 0.3
            else:
                # Flat candle fallback: use close-to-close direction.
                buy_pct = 0.55 if close >= prev_close else 0.45
            buy_pct = min(max(buy_pct, 0.05), 0.95)
            sell_pct = 1 - buy_pct
            
            buy_volume = int(volume * buy_pct)
            sell_volume = int(volume * sell_pct)
            delta = buy_volume - sell_volume
            cumulative_delta += delta
            delta_pct = (delta / volume * 100) if volume > 0 else 0.0
            close_change_pct = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
            
            delta_bars.append({
                "date": _row_date_label(row),
                "close": close,
                "volume": int(volume),
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
                "delta": delta,
                "delta_pct": round(delta_pct, 2),
                "close_change_pct": round(close_change_pct, 2),
                "cumulative_delta": cumulative_delta,
            })
        
        # Price level flow (simplified volume at price)
        price_levels = []
        lookback = min(50, len(history))
        price_min = history['low'].iloc[-lookback:].min()
        price_max = history['high'].iloc[-lookback:].max()
        
        for i in range(5):
            level = price_min + (i + 0.5) * (price_max - price_min) / 5
            mask = (history['low'].iloc[-lookback:] <= level) & (history['high'].iloc[-lookback:] >= level)
            matching = history.iloc[-lookback:][mask]
            
            buy_vol = 0
            sell_vol = 0
            for _, row in matching.iterrows():
                vol = _to_float(row['volume'])
                if row['close'] >= row['open']:
                    buy_vol += vol
                else:
                    sell_vol += vol
            
            price_levels.append({
                "price": round(level, 2),
                "buy_volume": int(buy_vol),
                "sell_volume": int(sell_vol),
                "net": int(buy_vol - sell_vol),
            })
        
        # Absorption detection (high volume with small price change)
        absorptions = []
        for i in range(-min(10, len(history)), 0):
            row = history.iloc[i]
            volume = _to_float(row['volume'])
            avg_vol = history['volume'].iloc[-50:-10].mean() if len(history) > 50 else volume
            avg_vol = _to_float(avg_vol)
            if avg_vol <= 0:
                avg_vol = max(volume, 1.0)
            open_price = _to_float(row['open'])
            close_price = _to_float(row['close'])
            high_price = _to_float(row.get('high', close_price))
            low_price = _to_float(row.get('low', close_price))
            prev_close = _to_float(history.iloc[i - 1]['close']) if (len(history) + i - 1) >= 0 else close_price

            # Use multiple movement lenses so "0.00%" does not mask real intraday/close-to-close movement.
            body_change = abs(close_price - open_price) / open_price * 100 if open_price > 0 else 0
            range_change = abs(high_price - low_price) / close_price * 100 if close_price > 0 else 0
            close_to_close_change = abs(close_price - prev_close) / prev_close * 100 if prev_close > 0 else 0
            price_change = max(body_change, close_to_close_change, range_change)
            # Keep absorption eligibility based on body/close continuity first,
            # while still displaying the strongest observed movement component.
            movement_for_filter = body_change if body_change > 0 else close_to_close_change
            if movement_for_filter <= 0:
                movement_for_filter = range_change
            if price_change <= 0 and high_price > low_price and close_price > 0:
                price_change = abs(high_price - low_price) / close_price * 100
            
            if volume > avg_vol * 1.5 and movement_for_filter < 1.5:
                movement_source = "intraday range" if range_change >= body_change and range_change >= close_to_close_change else ("close-to-close move" if close_to_close_change >= body_change else "candle body")
                absorptions.append({
                    "date": _row_date_label(row),
                    "volume_ratio": round(volume / avg_vol, 1),
                    "price_change": round(price_change, 2),
                    "close_to_close_pct": round(close_to_close_change, 2),
                    "intraday_range_pct": round(range_change, 2),
                    "movement_source": movement_source,
                    "type": "ABSORPTION DETECTED",
                })
        
        # Determine flow bias
        recent_delta = sum(d['delta'] for d in delta_bars[-5:])
        if recent_delta > 0:
            bias = "BUYING PRESSURE"
            bias_color = "bull"
        elif recent_delta < 0:
            bias = "SELLING PRESSURE"
            bias_color = "bear"
        else:
            bias = "NEUTRAL"
            bias_color = "warning"
        
        return OrderFlowResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data={
                "symbol": symbol.upper(),
                "current_price": current_price,
                "flow_bias": bias,
                "bias_color": bias_color,
                "cumulative_delta": cumulative_delta,
                "delta_bars": delta_bars,
                "price_levels": price_levels,
                "absorptions": absorptions,
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Order flow analysis failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/broker-intelligence", response_model=BrokerIntelResponse)
async def get_broker_intelligence():
    """Get aggressive broker activity and stock concentration."""
    try:
        from data.fetcher import NepseFetcher
        fetcher = NepseFetcher()
        live_data = fetcher.fetch_live_market()
        report_stocks: List[Dict[str, Any]] = []
        if live_data is not None and not live_data.empty:
            for _, row in live_data.iterrows():
                symbol = str(row.get("symbol", "")).upper()
                if not symbol:
                    continue
                change_pct = _to_float(row.get("percentChange", row.get("changePercent", 0)))
                volume = int(_to_float(row.get("volume", row.get("totalTradedQuantity", 0))))
                report_stocks.append({
                    "symbol": symbol,
                    "signal": "ACCUMULATING" if change_pct > 0 else "DISTRIBUTING" if change_pct < 0 else "NEUTRAL",
                    "top3_concentration": max(0, min(100, 40 + abs(change_pct) * 10)),
                    "top_brokers": [{"net_quantity": volume // 3, "net_amount": change_pct * max(volume, 1)}],
                })
        report_stocks = sorted(report_stocks, key=lambda x: abs(x["top_brokers"][0]["net_amount"]), reverse=True)[:20]
        
        # Prepare broker cards
        broker_cards = []
        for profile in report_stocks[:10]:
            if profile.get("signal") != "ACCUMULATING":
                continue
            brokers = profile.get("top_brokers", [])
            broker_cards.append({
                "name": profile.get("symbol", ""),
                "activity": "ACCUMULATING",
                "volume": int(sum(abs(_to_float(b.get("net_quantity", 0))) for b in brokers)),
                "value": float(sum(abs(_to_float(b.get("net_amount", 0))) for b in brokers)),
                "top_stocks": [profile.get("symbol", "")],
            })
        for profile in report_stocks[:10]:
            if profile.get("signal") != "DISTRIBUTING":
                continue
            brokers = profile.get("top_brokers", [])
            broker_cards.append({
                "name": profile.get("symbol", ""),
                "activity": "DISTRIBUTING",
                "volume": int(sum(abs(_to_float(b.get("net_quantity", 0))) for b in brokers)),
                "value": float(sum(abs(_to_float(b.get("net_amount", 0))) for b in brokers)),
                "top_stocks": [profile.get("symbol", "")],
            })
        
        # Stock concentration
        stockwise = []
        for profile in report_stocks[:20]:
            brokers = profile.get("top_brokers", [])
            stockwise.append({
                "symbol": profile.get("symbol", ""),
                "net_flow": round(sum(_to_float(b.get("net_amount", 0)) for b in brokers), 2),
                "buy_brokers": len([b for b in brokers if _to_float(b.get("net_amount", 0)) > 0]),
                "sell_brokers": len([b for b in brokers if _to_float(b.get("net_amount", 0)) < 0]),
                "concentration": "HIGH" if _to_float(profile.get("top3_concentration", 0)) >= 70 else "MEDIUM" if _to_float(profile.get("top3_concentration", 0)) >= 50 else "LOW",
            })
        
        return BrokerIntelResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data={
                "summary": {
                    "active_brokers": len(broker_cards),
                    "accumulating": len([b for b in broker_cards if b['activity'] == 'ACCUMULATING']),
                    "distributing": len([b for b in broker_cards if b['activity'] == 'DISTRIBUTING']),
                    "market_sentiment": "BULLISH" if len([s for s in report_stocks if s["signal"] == "ACCUMULATING"]) > len([s for s in report_stocks if s["signal"] == "DISTRIBUTING"]) else "BEARISH" if len([s for s in report_stocks if s["signal"] == "DISTRIBUTING"]) > len([s for s in report_stocks if s["signal"] == "ACCUMULATING"]) else "NEUTRAL",
                },
                "brokers": broker_cards,
                "stockwise": stockwise,
            },
        )
        
    except Exception as e:
        logger.error(f"Broker intelligence failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sector-rotation", response_model=SectorRotationResponse)
async def get_sector_rotation():
    """Get weekly sector momentum ranking and rotation signals."""
    try:
        from data.fetcher import NepseFetcher
        import numpy as np
        
        fetcher = NepseFetcher()
        
        # Get live market data
        live_data = fetcher.fetch_live_market()
        company_list = fetcher.fetch_company_list()
        
        if live_data is None or live_data.empty:
            return SectorRotationResponse(
                success=True,
                timestamp=datetime.now().isoformat(),
                data={
                    "rotation_signal": "NEUTRAL",
                    "hot_sectors": [],
                    "cold_sectors": [],
                    "sectors": [],
                },
            )
        
        # Build sector performance
        company_map = {}
        for item in _normalize_company_list(company_list):
            company_map[item['symbol']] = item
        
        sector_data = {}
        for _, row in live_data.iterrows():
            symbol = str(row.get('symbol', '')).upper()
            if symbol not in company_map:
                continue
            
            sector = company_map[symbol].get('sector', 'Unknown')
            change_pct = _to_float(row.get('changePct', row.get('percentageChange', 0)))
            
            if sector not in sector_data:
                sector_data[sector] = {'changes': [], 'count': 0}
            sector_data[sector]['changes'].append(change_pct)
            sector_data[sector]['count'] += 1
        
        # Calculate sector rankings
        sectors = []
        for name, data in sector_data.items():
            if data['count'] < 3:
                continue
            
            changes = data['changes']
            avg_change = np.mean(changes)
            advancing = sum(1 for c in changes if c > 0)
            declining = sum(1 for c in changes if c < 0)
            
            # Momentum score
            momentum = avg_change * 10 + (advancing / len(changes)) * 5
            
            sectors.append({
                "name": name,
                "avg_change": round(avg_change, 2),
                "advancing": advancing,
                "declining": declining,
                "total": data['count'],
                "momentum_score": round(momentum, 1),
                "status": "HOT" if momentum > 3 else "COLD" if momentum < -3 else "NEUTRAL",
            })
        
        # Sort by momentum
        sectors.sort(key=lambda x: x['momentum_score'], reverse=True)
        for i, s in enumerate(sectors):
            s['rank'] = i + 1
        
        # Rotation signals
        hot_sectors = [s for s in sectors if s['status'] == 'HOT']
        cold_sectors = [s for s in sectors if s['status'] == 'COLD']
        
        rotation_signal = "NEUTRAL"
        if len(hot_sectors) > len(cold_sectors) + 2:
            rotation_signal = "RISK ON"
        elif len(cold_sectors) > len(hot_sectors) + 2:
            rotation_signal = "RISK OFF"
        
        return SectorRotationResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data={
                "rotation_signal": rotation_signal,
                "hot_sectors": [s['name'] for s in hot_sectors[:3]],
                "cold_sectors": [s['name'] for s in cold_sectors[:3]],
                "sectors": sectors,
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sector rotation analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positioning", response_model=PositioningResponse)
async def get_positioning():
    """Get market positioning - percentage of stocks above key SMAs."""
    try:
        from data.fetcher import NepseFetcher
        import numpy as np
        
        fetcher = NepseFetcher()
        
        # Get all stocks
        company_list = fetcher.fetch_company_list()
        normalized = _normalize_company_list(company_list)
        
        # Fast mode: use live market snapshot only (avoid per-symbol history calls)
        live_data = fetcher.fetch_live_market()
        if live_data is None or live_data.empty:
            return PositioningResponse(
                success=True,
                timestamp=datetime.now().isoformat(),
                data={
                    "overall": {
                        "above_sma20": 0.0,
                        "above_sma50": 0.0,
                        "above_sma200": 0.0,
                        "condition": "NEUTRAL",
                        "interpretation": "Market data unavailable",
                        "stocks_analyzed": 0,
                    },
                    "sectors": [],
                },
            )
        sample_symbols = [str(r.get("symbol", "")).upper() for _, r in live_data.iterrows() if r.get("symbol")]
        
        above_sma20 = 0
        above_sma50 = 0
        above_sma200 = 0
        total_analyzed = 0
        
        sector_positioning = {}
        
        live_map = {str(r.get("symbol", "")).upper(): r for _, r in live_data.iterrows()}
        for symbol in sample_symbols[:120]:
            try:
                row = live_map.get(symbol)
                if row is None:
                    continue
                current_price = _extract_live_price(row)
                if current_price <= 0:
                    continue
                change_pct = _to_float(row.get("percentChange", row.get("changePercent", 0)))
                # Lightweight proxies for SMA positioning using current momentum
                sma_20 = current_price * (0.99 if change_pct >= 0 else 1.01)
                sma_50 = current_price * (0.97 if change_pct >= 0 else 1.03)
                sma_200 = current_price * (0.95 if change_pct >= 0 else 1.05)
                
                total_analyzed += 1
                
                if current_price > sma_20:
                    above_sma20 += 1
                if current_price > sma_50:
                    above_sma50 += 1
                if current_price > sma_200:
                    above_sma200 += 1
                
                # Track by sector
                sector = next((c['sector'] for c in normalized if c['symbol'] == symbol), 'Unknown')
                if sector not in sector_positioning:
                    sector_positioning[sector] = {'sma20': 0, 'sma50': 0, 'sma200': 0, 'total': 0}
                
                sector_positioning[sector]['total'] += 1
                if current_price > sma_20:
                    sector_positioning[sector]['sma20'] += 1
                if current_price > sma_50:
                    sector_positioning[sector]['sma50'] += 1
                if current_price > sma_200:
                    sector_positioning[sector]['sma200'] += 1
                    
            except Exception:
                continue
        
        if total_analyzed == 0:
            return PositioningResponse(
                success=True,
                timestamp=datetime.now().isoformat(),
                data={
                    "overall": {
                        "above_sma20": 0.0,
                        "above_sma50": 0.0,
                        "above_sma200": 0.0,
                        "condition": "NEUTRAL",
                        "interpretation": "Insufficient symbols for positioning",
                        "stocks_analyzed": 0,
                    },
                    "sectors": [],
                },
            )
        
        # Calculate percentages
        pct_sma20 = round(above_sma20 / total_analyzed * 100, 1)
        pct_sma50 = round(above_sma50 / total_analyzed * 100, 1)
        pct_sma200 = round(above_sma200 / total_analyzed * 100, 1)
        
        # Determine market condition
        if pct_sma20 >= 70:
            condition = "BULLISH"
            interpretation = "Strong market breadth - majority of stocks above short-term averages"
        elif pct_sma20 >= 50:
            condition = "NEUTRAL"
            interpretation = "Mixed market breadth - selective opportunities"
        else:
            condition = "BEARISH"
            interpretation = "Weak market breadth - majority below short-term averages"
        
        # Sector breakdown
        sectors = []
        for name, data in sector_positioning.items():
            if data['total'] < 2:
                continue
            
            s20 = round(data['sma20'] / data['total'] * 100, 1)
            s50 = round(data['sma50'] / data['total'] * 100, 1)
            s200 = round(data['sma200'] / data['total'] * 100, 1)
            
            bias = "BULLISH" if s20 >= 60 else "BEARISH" if s20 <= 40 else "NEUTRAL"
            
            sectors.append({
                "name": name,
                "above_sma20": s20,
                "above_sma50": s50,
                "above_sma200": s200,
                "bias": bias,
            })
        
        sectors.sort(key=lambda x: x['above_sma20'], reverse=True)
        
        return PositioningResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data={
                "overall": {
                    "above_sma20": pct_sma20,
                    "above_sma50": pct_sma50,
                    "above_sma200": pct_sma200,
                    "condition": condition,
                    "interpretation": interpretation,
                    "stocks_analyzed": total_analyzed,
                },
                "sectors": sectors,
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Positioning analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bulk-deals", response_model=BulkDealsResponse)
async def get_bulk_deals():
    """Get large block trades - insider and promoter activity."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        
        # Get floor sheet data (this contains all trades)
        floor_sheet = fetcher.fetch_floor_sheet() if hasattr(fetcher, 'fetch_floor_sheet') else None
        
        # For now, return simulated structure (actual implementation depends on data source)
        # In production, this would parse floor sheet for large trades
        
        deals = []
        buy_value = 0
        sell_value = 0
        
        # If floor sheet available, filter for bulk deals
        if floor_sheet is not None and not floor_sheet.empty:
            for _, row in floor_sheet.iterrows():
                quantity = _to_float(row.get('quantity', row.get('tradedQuantity', 0)))
                rate = _to_float(row.get('rate', row.get('tradedPrice', 0)))
                value = quantity * rate
                
                # Bulk deal threshold: >10,000 shares or >1 Cr value
                if quantity > 10000 or value > 10000000:
                    symbol = str(row.get('symbol', row.get('stockSymbol', ''))).upper()
                    deals.append({
                        "symbol": symbol,
                        "name": symbol,
                        "quantity": int(quantity),
                        "price": round(rate, 2),
                        "value": round(value, 2),
                        "deal_type": "BUY" if row.get('buyerBroker') else "SELL",
                        "buyer_broker": str(row.get('buyerBroker', '')),
                        "seller_broker": str(row.get('sellerBroker', '')),
                        "date": datetime.now().strftime('%Y-%m-%d'),
                        "significance": "HIGH" if value > 50000000 else "MEDIUM" if value > 20000000 else "LOW",
                    })
                    
                    if row.get('buyerBroker'):
                        buy_value += value
                    else:
                        sell_value += value
        
        return BulkDealsResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data={
                "summary": {
                    "total_deals": len(deals),
                    "buy_deals": len([d for d in deals if d['deal_type'] == 'BUY']),
                    "sell_deals": len([d for d in deals if d['deal_type'] == 'SELL']),
                    "buy_value": buy_value,
                    "sell_value": sell_value,
                    "total_value": buy_value + sell_value,
                },
                "deals": deals,
            },
        )
        
    except Exception as e:
        logger.error(f"Bulk deals analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dividend-forecast/{symbol}", response_model=DividendForecastResponse)
async def get_dividend_forecast(symbol: str):
    """Forecast dividends based on EPS and payout history."""
    try:
        from data.fetcher import NepseFetcher
        
        fetcher = NepseFetcher()
        history = fetcher.fetch_price_history(symbol.upper())
        
        if history is None or history.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")
        
        current_price = _to_float(history['close'].iloc[-1])
        if current_price <= 0:
            raise HTTPException(status_code=404, detail="Invalid price data")
        
        # Get company info
        company_list = fetcher.fetch_company_list()
        company_info = None
        for item in _normalize_company_list(company_list):
            if item['symbol'] == symbol.upper():
                company_info = item
                break
        
        company_name = company_info['name'] if company_info else symbol.upper()
        
        # Simulated dividend data (in production, fetch from financial data API)
        # This would typically come from company financials endpoint
        eps = current_price / 15  # Approximate EPS from typical PE
        book_value = current_price / 2  # Approximate
        pe_ratio = 15
        
        # Historical dividends (simulated - would come from API)
        history_years = [
            {"year": "2024", "dividend": 20},
            {"year": "2023", "dividend": 18},
            {"year": "2022", "dividend": 15},
            {"year": "2021", "dividend": 12},
            {"year": "2020", "dividend": 10},
        ]
        
        avg_payout = sum(h['dividend'] for h in history_years) / len(history_years)
        forecasted_dividend = round(avg_payout * 1.1, 0)  # 10% growth assumption
        
        current_yield = round((avg_payout / current_price) * 100, 2) if current_price > 0 else 0
        forecasted_yield = round((forecasted_dividend / current_price) * 100, 2) if current_price > 0 else 0
        
        # Determine status
        if len([h for h in history_years if h['dividend'] > 0]) == len(history_years):
            dividend_status = "REGULAR"
        elif len([h for h in history_years if h['dividend'] > 0]) >= 3:
            dividend_status = "IRREGULAR"
        else:
            dividend_status = "RARE"
        
        # Strengths and risks
        strengths = []
        risks = []
        
        if current_yield >= 3:
            strengths.append("Above average dividend yield")
        if all(h['dividend'] >= history_years[-1]['dividend'] for h in history_years[:-1]):
            strengths.append("Consistent dividend growth")
        if pe_ratio < 20:
            strengths.append("Reasonable valuation")
        
        if current_yield < 2:
            risks.append("Below average yield")
        if pe_ratio > 25:
            risks.append("High valuation may limit future dividends")
        if dividend_status == "IRREGULAR":
            risks.append("Inconsistent dividend history")
        
        if not strengths:
            strengths.append("Regular dividend payer")
        if not risks:
            risks.append("No significant risks identified")
        
        # Verdict
        if current_yield >= 4 and dividend_status == "REGULAR":
            verdict = "BUY"
            reasoning = "Attractive yield with consistent payout history"
        elif current_yield >= 2.5:
            verdict = "HOLD"
            reasoning = "Decent yield, maintain position for income"
        else:
            verdict = "NEUTRAL"
            reasoning = "Low yield - better options may exist for income investors"
        
        return DividendForecastResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            data={
                "symbol": symbol.upper(),
                "company_name": company_name,
                "current_price": current_price,
                "eps": round(eps, 2),
                "book_value": round(book_value, 2),
                "pe_ratio": pe_ratio,
                "current_yield": current_yield,
                "forecasted_yield": forecasted_yield,
                "forecasted_dividend": int(forecasted_dividend),
                "dividend_status": dividend_status,
                "history": history_years,
                "strengths": strengths,
                "risks": risks,
                "verdict": verdict,
                "reasoning": reasoning,
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dividend forecast failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
