"""
NEPSE Expert Analysis — 6-Gate Buy Verification Engine
======================================================
Combines 3-Timeframe Technical Analysis (NepseAlpha chart data)
with 4-Pillar Fundamental Scoring (ShareHub broker/fundamental/unlock)
to produce a single definitive BUY/AVOID verdict.

Gates:
  1. Technical Foundation   (25 pts)  — 13-Point WIDGET_GUIDE Checklist
  2. Multi-TF Confluence    (15 pts)  — 7-Timeframe Alignment
  3. 4-Pillar Fundamentals  (25 pts)  — Broker + Unlock + PE/ROE + Technicals
  4. CSS Confirmation       (15 pts)  — Composite Signal Score (trend+momentum+volume+operator)
  5. Risk Clearance         (10 pts)  — Manipulation + Distribution + Dump Detection
  6. Market Regime          (10 pts)  — BULL / BEAR / PANIC Kill Switch

Verdicts:
  BLIND BUY  — All 6 gates clear, score ≥ 85, bull market. Execute immediately.
  STRONG BUY — 5+ gates clear, score ≥ 70. One minor flag — acceptable risk.
  BUY        — 4+ gates clear, score ≥ 55. Manual review recommended.
  RISKY      — 2-3 gates, score ≥ 40. Too many red flags.
  AVOID      — <40, PANIC mode, or CRITICAL manipulation/distribution.

Usage:
  python expert_analysis.py NABIL                       # Single stock deep analysis
  python expert_analysis.py --scan                      # Full market scan
  python expert_analysis.py --scan --sector "Commercial Banks"
  python expert_analysis.py --scan --top 10             # More per sector

  nepse expert NABIL                                    # Via alias
  nepse expert --scan                                   # Via alias
"""

import sys
import asyncio
import argparse
import os
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime, timezone

# ── Path Setup ───────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent          # tools/
_AI_ROOT = _THIS_DIR.parent                          # nepse_ai_trading/
_CHART_BACKEND = _AI_ROOT.parent / "nepse-chart-extension" / "backend"

# Chart backend MUST be inserted AFTER AI root so screener.py's
# `sys.path.insert(0, ...)` at import time places it first — ensuring
# `from main import ...` resolves to the chart extension's main.py.
for _p in [str(_AI_ROOT), str(_CHART_BACKEND)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load .env for ShareHub / OpenAI credentials
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_AI_ROOT / ".env", override=True)
except Exception:
    pass

# ── Technical Analysis (chart extension's screener.py) ───────────────
import aiohttp
from screener import (
    fetch_ohlcv,
    run_analysis,
    compute_checklist_score,
    compute_composite_score,
    fetch_intraday_ohlcv,
    analyze_intraday,
    compute_intraday_checks,
    scan_all_stocks,
    save_watchlist,
    _fsk,
)

# ── Fundamental Analysis (nepse_ai_trading) ──────────────────────────
from analysis.master_screener import MasterStockScreener, ScreenedStock
from core.database import init_db

# Suppress noisy logs — expert tool has its own progress output
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="ERROR")

# ── Intelligence Modules (fail-safe — work even if API down) ──────────
try:
    from intelligence.macro_engine import compute_macro_score, MacroScore as _MacroScore
    _HAS_MACRO = True
except ImportError:
    _HAS_MACRO = False
    _MacroScore = None  # type: ignore

try:
    from intelligence.sector_rotation import get_leading_sectors, get_lagging_sectors
    _HAS_SECTOR = True
except ImportError:
    _HAS_SECTOR = False

try:
    from intelligence.market_breadth import MarketBreadthAnalyzer
    _HAS_BREADTH = True
except ImportError:
    _HAS_BREADTH = False

try:
    from risk.position_sizer import PositionSizer
    _HAS_SIZER = True
except ImportError:
    _HAS_SIZER = False

# ── Macro config path ─────────────────────────────────────────────────
_MACRO_CONFIG = _AI_ROOT / "config" / "macro.json"


def _load_macro_context() -> Optional[object]:
    """Load NRB macro indicators from config/macro.json → MacroScore (or None)."""
    if not _HAS_MACRO:
        return None
    try:
        import json
        with open(_MACRO_CONFIG) as _f:
            _d = json.load(_f)
        return compute_macro_score(
            interbank_rate=_d.get("interbank_rate"),
            ccd_ratio=_d.get("ccd_ratio"),
            inflation_rate=_d.get("inflation_rate"),
            remittance_growth=_d.get("remittance_growth"),
            base_rate=_d.get("base_rate"),
        )
    except FileNotFoundError:
        return compute_macro_score()  # all-neutral defaults (50/50/50)
    except Exception:
        return None


# ── NepseUnofficialApi (live price during market hours) ──────────────
_NEPSE_API_ROOT = _AI_ROOT.parent / "NepseUnofficialApi"


def _is_market_hours_expert() -> bool:
    """True during NEPSE trading hours (10:55–15:05 KTM, Mon–Fri)."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Kathmandu"))
        if now.weekday() >= 5:
            return False
        t = now.hour * 60 + now.minute
        return 655 <= t <= 905  # 10:55 – 15:05
    except Exception:
        return False


def _get_live_price_expert(symbol: str) -> Optional[float]:
    """Live LTP from NepseUnofficialApi (no cookie expiry). Returns None on failure."""
    try:
        _np = str(_NEPSE_API_ROOT)
        if _np not in sys.path:
            sys.path.insert(0, _np)
        from nepse import Nepse as _Nepse  # type: ignore
        _api = _Nepse()
        _api.setTLSVerification(False)
        data = _api.getLiveMarket()
        q = next((x for x in data if x.get("symbol") == symbol), None)
        if q and q.get("lastTradedPrice"):
            return float(q["lastTradedPrice"])
    except Exception:
        pass
    return None


def _get_all_live_prices() -> dict:
    """Fetch live LTP for all stocks → {symbol: ltp}. Returns {} on failure."""
    try:
        _np = str(_NEPSE_API_ROOT)
        if _np not in sys.path:
            sys.path.insert(0, _np)
        from nepse import Nepse as _Nepse  # type: ignore
        _api = _Nepse()
        _api.setTLSVerification(False)
        data = _api.getLiveMarket()
        return {
            x["symbol"]: float(x["lastTradedPrice"])
            for x in data
            if x.get("lastTradedPrice")
        }
    except Exception:
        return {}


# ═════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═════════════════════════════════════════════════════════════════════

@dataclass
class GateResult:
    """Result of a single gate evaluation."""
    name: str
    score: float
    max_score: float
    status: str  # PASS, PARTIAL, FAIL
    details: List[str] = field(default_factory=list)


@dataclass
class ExpertVerdict:
    """Combined verdict from all 6 gates."""
    symbol: str
    sector: str = ""
    company_name: str = ""
    ltp: float = 0.0

    final_score: float = 0.0
    verdict: str = ""  # BLIND BUY, STRONG BUY, BUY, RISKY, AVOID

    gates: List[GateResult] = field(default_factory=list)
    gates_passed: int = 0
    gates_partial: int = 0
    gates_failed: int = 0

    # Trade plan
    entry_price: float = 0.0
    target_price: float = 0.0
    stop_loss: float = 0.0
    risk_reward: float = 0.0
    entry_status: str = "DAILY ONLY"
    holding_days: int = 7

    # Summary fields for scan display
    checklist_score: int = 0
    composite_score: float = 0.0
    p1_broker: float = 0.0
    p2_unlock: float = 0.0
    p3_fundamental: float = 0.0
    p4_technical: float = 0.0
    master_score: float = 0.0
    css_score: float = 0.0
    css_signal: str = ""

    # Enrichment context (macro + breadth + sector rotation)
    macro_signal: str = ""
    macro_score: float = 50.0
    breadth_pct: float = 0.0
    breadth_signal: str = ""
    sector_phase: str = ""        # HOT / COLD / ""

    # Price location relative to S/R levels
    price_location: str = ""     # NEAR_SUPPORT / NEAR_RESISTANCE / MID_RANGE / ABOVE_RESISTANCE
    nearest_support: float = 0.0
    nearest_resistance: float = 0.0
    support_dist_pct: float = 0.0
    resistance_dist_pct: float = 0.0
    is_near_support: bool = False
    is_near_resistance: bool = False
    entry_reason: str = ""       # why entry_status was set / overridden
    entry_mode: str = ""         # BREAKOUT / PULLBACK / PRE-BREAKOUT

    # Position sizing (default Rs. 10L portfolio, 2% risk rule)
    pos_shares: int = 0
    pos_capital: float = 0.0
    pos_risk_rs: float = 0.0


# ═════════════════════════════════════════════════════════════════════
# LOCATION HELPER
# ═════════════════════════════════════════════════════════════════════

def _detect_location(ta: dict) -> tuple[str, float, float, float, float]:
    """
    Classify price position relative to nearest support/resistance.
    Returns (location_label, nearest_support, nearest_resistance, support_dist_pct, resistance_dist_pct)

    Labels:
      ABOVE_RESISTANCE  — price already broke above resistance (breakout territory)
      NEAR_RESISTANCE   — price within 5% below resistance (caution zone)
      NEAR_SUPPORT      — price within 5% above support (good entry zone)
      MID_RANGE         — stuck between S/R, too far from either (wait zone)
    """
    nearest_r = ta.get("nearest_resistance") or 0.0
    nearest_s = ta.get("nearest_support") or 0.0
    r_dist = ta.get("resistance_distance_pct") or 0.0   # positive = price below resistance
    s_dist = ta.get("support_distance_pct") or 0.0     # positive = price above support
    price = ta.get("current_price") or 0.0

    if nearest_r and price >= nearest_r * 0.998:  # at or above resistance
        location = "ABOVE_RESISTANCE"
    elif nearest_r and r_dist <= 5.0:              # within 5% below resistance
        location = "NEAR_RESISTANCE"
    elif nearest_s and s_dist <= 5.0:              # within 5% above support
        location = "NEAR_SUPPORT"
    else:
        location = "MID_RANGE"

    return location, nearest_s, nearest_r, s_dist, r_dist


# ═════════════════════════════════════════════════════════════════════
# 6-GATE FUNCTIONS
# ═════════════════════════════════════════════════════════════════════

def _gate1_technical(chk: dict) -> GateResult:
    """Gate 1: Technical Foundation — 13-Point WIDGET_GUIDE Checklist (max 25)."""
    score_13 = chk.get("total_score", 0)
    keys = [
        ("verdict_buy", "Verdict BUY"),
        ("trend_confirmed", "Trend + ADX>20 + EMA10>EMA30"),
        ("rsi_safe", "RSI 40-70"),
        ("price_above_sma50", "Price > SMA50"),
        ("macd_bullish", "MACD Bullish"),
        ("multi_tf_aligned", "Multi-TF ≥50% BUY"),
        ("no_red_flags", "No Death Cross / RSI 80+ / Bear Div"),
        ("volume_confirmed", "Volume ratio ≥ 1.2"),
        ("entry_timing", "Near support ≤8% or breakout"),
        ("wyckoff_favorable", "Accumulation / Markup phase"),
        ("no_operator_distribution", "No operator distribution"),
        ("not_chasing_52w_top", "Not chasing 52w high"),
        ("rr_ratio_ok", "R:R ≥ 1.5"),
    ]
    details = [f"Checklist: {score_13}/13"]
    for k, label in keys:
        icon = "✅" if chk.get(k, False) else "❌"
        details.append(f"{icon} {label}")

    if score_13 >= 10:
        return GateResult("Technical Foundation", 25, 25, "PASS", details)
    if score_13 >= 8:
        return GateResult("Technical Foundation", 15, 25, "PARTIAL", details)
    return GateResult("Technical Foundation", 0, 25, "FAIL", details)


def _gate2_multi_tf(ta: dict) -> GateResult:
    """Gate 2: Multi-Timeframe Confluence — 7 TF alignment (max 15)."""
    tfs = [
        ("Daily", ta.get("verdict")),
        ("Bi-Weekly", ta.get("biweekly_verdict")),
        ("Weekly", ta.get("weekly_verdict")),
        ("Monthly", ta.get("monthly_verdict")),
        ("Quarterly", ta.get("quarterly_verdict")),
        ("Semi-Yr", ta.get("semi_yearly_verdict")),
        ("Yearly", ta.get("yearly_verdict")),
    ]
    buy = sum(1 for _, v in tfs if v in ("BUY", "STRONG BUY"))
    total = sum(1 for _, v in tfs if v)
    details = []
    for name, v in tfs:
        icon = "✅" if v in ("BUY", "STRONG BUY") else ("❌" if v else "⚪")
        details.append(f"{icon} {name}={v or '—'}")
    details.append(f"Aligned: {buy}/{total}")

    ratio = buy / total if total else 0
    if ratio >= 0.7:
        return GateResult("Multi-TF Confluence", 15, 15, "PASS", details)
    if ratio >= 0.5:
        return GateResult("Multi-TF Confluence", 10, 15, "PARTIAL", details)
    return GateResult("Multi-TF Confluence", 0, 15, "FAIL", details)


def _gate3_four_pillar(
    s: Optional[ScreenedStock],
    sector_is_leading: bool = False,
    sector_is_lagging: bool = False,
) -> GateResult:
    """Gate 3: 4-Pillar Fundamentals — Broker+Unlock+Fundamental+Technical (max 25)."""
    if not s:
        return GateResult("4-Pillar Fundamentals", 0, 25, "FAIL", ["❌ 4-Pillar scoring unavailable"])

    ms = s.total_score
    details = [
        f"Master Score: {ms:.1f}/100",
        f"  Broker      {_bar(s.pillar1_broker, 30, 10)}  {s.pillar1_broker:.1f}/30",
        f"  Unlock      {_bar(s.pillar2_unlock, 20, 10)}  {s.pillar2_unlock:.1f}/20",
        f"  Fundamental {_bar(s.pillar3_fundamental, 20, 10)}  {s.pillar3_fundamental:.1f}/20",
        f"  Technical   {_bar(s.pillar4_technical, 30, 10)}  {s.pillar4_technical:.1f}/30",
    ]
    if s.pe_ratio > 0:
        details.append(f"  PE {s.pe_ratio:.1f}x | EPS Rs.{s.eps:.2f} | ROE {s.roe:.1f}% | PBV {s.pbv:.2f}x")
    winner = getattr(s, "winner", "")
    buyer_dom = getattr(s, "buyer_dominance_pct", 0)
    if winner:
        details.append(f"  Broker Dominance: {winner} ({buyer_dom:.0f}%)")

    # Sector rotation bonus/penalty (±3 pts)
    sector_bonus = 0.0
    if sector_is_leading:
        sector_bonus = 3.0
        details.append(f"  🔥 Sector Rotation BONUS: Sector is HOT (+{sector_bonus:.0f} pts)")
    elif sector_is_lagging:
        sector_bonus = -2.0
        details.append(f"  ❄️ Sector Rotation PENALTY: Sector is COLD ({sector_bonus:.0f} pts)")
    base = ms / 4.0  # Scale 0-100 → 0-25
    final_score = min(25.0, max(0.0, base + sector_bonus))

    if ms >= 70:
        return GateResult("4-Pillar Fundamentals", final_score, 25, "PASS", details)
    if ms >= 55:
        return GateResult("4-Pillar Fundamentals", min(15.0 + sector_bonus, 25), 25, "PARTIAL", details)
    return GateResult("4-Pillar Fundamentals", max(0.0, sector_bonus), 25, "FAIL", details)


def _gate4_css(s: Optional[ScreenedStock]) -> GateResult:
    """Gate 4: CSS Confirmation — Composite Signal Score (max 15)."""
    if not s or not s.css_score:
        return GateResult("CSS Confirmation", 0, 15, "FAIL", ["❌ CSS engine unavailable or no data"])

    css = s.css_score
    sig = s.css_signal
    conf = s.css_confidence
    details = [f"CSS: {css:.3f} [{sig}] confidence {conf:.0f}%"]

    if css >= 0.60 and sig in ("STRONG_BUY", "BUY"):
        return GateResult("CSS Confirmation", 15, 15, "PASS", details)
    if css >= 0.45 and sig not in ("SELL", "STRONG_SELL"):
        return GateResult("CSS Confirmation", 8, 15, "PARTIAL", details)
    return GateResult("CSS Confirmation", 0, 15, "FAIL", details)


def _gate5_risk(s: Optional[ScreenedStock]) -> GateResult:
    """Gate 5: Risk Clearance — Manipulation + Distribution + Dump (max 10)."""
    if not s:
        return GateResult("Risk Clearance", 5, 10, "PARTIAL", ["⚪ Risk data unavailable — TA only"])

    pts = 0.0
    details = []

    # Manipulation (5 pts)
    manip = str(getattr(s, "manipulation_severity", "NONE") or "NONE")
    if manip in ("NONE", "LOW"):
        pts += 5
        details.append(f"✅ Manipulation: {manip}")
    elif manip == "MEDIUM":
        pts += 2
        details.append("🟡 Manipulation: MEDIUM")
    else:
        details.append(f"🚨 Manipulation: {manip}")
        return GateResult("Risk Clearance", 0, 10, "FAIL", details)

    # Distribution risk (3 pts)
    dist = str(getattr(s, "distribution_risk", "") or "")
    bpp = getattr(s, "broker_profit_pct", 0) or 0
    if dist in ("LOW", "N/A", ""):
        pts += 3
        details.append(f"✅ Distribution: {dist or 'N/A'}" + (f" (brokers {bpp:+.1f}%)" if bpp else ""))
    elif dist == "MEDIUM":
        pts += 1
        details.append(f"🟡 Distribution: MEDIUM (brokers {bpp:+.1f}%)")
    elif dist == "CRITICAL":
        details.append(f"🚨 Distribution: CRITICAL (brokers {bpp:+.1f}%)")
        return GateResult("Risk Clearance", 0, 10, "FAIL", details)
    else:
        details.append(f"🔴 Distribution: {dist} (brokers {bpp:+.1f}%)")

    # Intraday dump (2 pts)
    if not getattr(s, "intraday_dump_detected", False):
        pts += 2
        details.append("✅ No intraday dump pattern")
    else:
        details.append("🔴 Intraday pump-and-dump detected!")

    status = "PASS" if pts >= 8 else ("PARTIAL" if pts >= 4 else "FAIL")
    return GateResult("Risk Clearance", pts, 10, status, details)


def _gate6_regime(
    regime: str,
    reason: str = "",
    macro_score: Optional[float] = None,
    breadth_pct: Optional[float] = None,
    breadth_signal: str = "",
) -> GateResult:
    """Gate 6: Market Regime — BULL/BEAR/PANIC kill switch + macro + breadth (max 10)."""
    details = [f"Regime: {regime}"]
    if reason:
        details.append(reason)

    # Market breadth context
    if breadth_pct is not None and breadth_pct > 0:
        b_bar = "🟢" if breadth_pct >= 60 else ("🟡" if breadth_pct >= 40 else "🔴")
        details.append(f"📊 Breadth: {b_bar} {breadth_pct:.0f}% advancing"
                       + (f"  — {breadth_signal}" if breadth_signal else ""))

    # NRB macro context
    if macro_score is not None:
        macro_label = (
            "BULLISH" if macro_score >= 70 else
            "MILD_BULLISH" if macro_score >= 55 else
            "NEUTRAL" if macro_score >= 45 else
            "MILD_BEARISH" if macro_score >= 30 else "BEARISH"
        )
        m_icon = "🟢" if macro_score >= 70 else ("🔵" if macro_score >= 55 else ("⚪" if macro_score >= 45 else "🟠"))
        details.append(f"🏦 NRB Macro: {m_icon} {macro_label} ({macro_score:.0f}/100)")

    if regime == "PANIC":
        details.append("🚨 KILL SWITCH — No buying allowed")
        return GateResult("Market Regime", 0, 10, "FAIL", details)

    if regime == "BEAR":
        details.append("🐻 Bear market — tight stops, reduce size 50%")
        # Improving macro in bear = potential early recovery signal (+1)
        bear_score = 3.0
        if macro_score is not None and macro_score >= 65:
            bear_score = 5.0
            details.append("  ↑ Strong macro improving during bear — possible early recovery")
        return GateResult("Market Regime", bear_score, 10, "PARTIAL", details)

    # NEUTRAL / BULL
    base_score = 10.0 if regime == "BULL" else 7.0

    # Breadth penalty: weak breadth even in bull = index not broad
    if breadth_pct is not None and breadth_pct > 0 and breadth_pct < 35:
        base_score = max(base_score - 2.0, 0.0)
        details.append("  ↓ Narrow breadth (<35%) — possible index-level trap, reduce size")

    # Macro adjustments
    if macro_score is not None:
        if macro_score >= 70:
            details.append("  ↑ Strong NRB macro tailwind — favorable for all sectors")
        elif macro_score < 40:
            base_score = max(base_score - 1.0, 0.0)
            details.append("  ↓ NRB macro headwind — consider 25% size reduction")

    details.append(f"{'🐂' if regime == 'BULL' else '📊'} Favorable environment")
    return GateResult("Market Regime", base_score, 10, "PASS", details)


# ═════════════════════════════════════════════════════════════════════
# VERDICT ENGINE
# ═════════════════════════════════════════════════════════════════════

def _compute_verdict(
    symbol: str,
    ta: dict,
    chk: dict,
    screened: Optional[ScreenedStock],
    regime: str,
    regime_reason: str,
    entry_status: str = "DAILY ONLY",
    enrichment: Optional[Dict] = None,
) -> ExpertVerdict:
    """Compute the 6-Gate Expert Verdict for one stock."""
    enrich = enrichment or {}

    gates = [
        _gate1_technical(chk),
        _gate2_multi_tf(ta),
        _gate3_four_pillar(
            screened,
            sector_is_leading=enrich.get("sector_leading", False),
            sector_is_lagging=enrich.get("sector_lagging", False),
        ),
        _gate4_css(screened),
        _gate5_risk(screened),
        _gate6_regime(
            regime, regime_reason,
            macro_score=enrich.get("macro_score"),
            breadth_pct=enrich.get("breadth_pct"),
            breadth_signal=enrich.get("breadth_signal", ""),
        ),
    ]

    total = sum(g.score for g in gates)
    passed = sum(1 for g in gates if g.status == "PASS")
    partial = sum(1 for g in gates if g.status == "PARTIAL")
    failed = sum(1 for g in gates if g.status == "FAIL")

    risk_fail = any(g.name == "Risk Clearance" and g.status == "FAIL" for g in gates)

    # Price location detection — used by entry_status override and output
    location, loc_support, loc_resistance, loc_s_dist, loc_r_dist = _detect_location(ta)
    is_near_sup = location == "NEAR_SUPPORT"
    is_near_res = location in ("NEAR_RESISTANCE", "ABOVE_RESISTANCE")

    # entry_status overrides based on price location
    entry_reason = ""
    breakout_status = ta.get("breakout_status") or ""
    active_breakout = "Bullish Breakout" in breakout_status or "BB Upper" in breakout_status

    if entry_status not in ("ENTRY READY",):
        if location == "MID_RANGE":
            # Within 2% of resistance? Breakout watch — still WAIT but with context
            if loc_resistance and loc_r_dist <= 2.0:
                entry_status = "WAIT"
                entry_reason = "Near breakout zone (watch Rs.{:.0f})".format(loc_resistance)
            else:
                entry_status = "WAIT"
                entry_reason = "Mid-range (no edge)"
        elif location == "NEAR_RESISTANCE" and not active_breakout:
            # Very close? Pre-breakout zone. Otherwise standard resistance wait.
            if loc_r_dist <= 2.0:
                entry_status = "WAIT"
                entry_reason = "Pre-breakout zone — watch Rs.{:.0f} for compression + volume".format(
                    loc_resistance if loc_resistance else 0
                )
            else:
                entry_status = "WAIT"
                entry_reason = "Near resistance — wait for breakout above Rs.{:.0f}".format(
                    loc_resistance if loc_resistance else 0
                )
        elif location == "NEAR_SUPPORT":
            # Price at support = actionable pullback zone — upgrade WAIT → ENTRY ZONE
            if entry_status == "WAIT":
                entry_status = "ENTRY ZONE"
                entry_reason = "Pullback to support — watch for bullish rejection candle"

    # Entry mode — the STRATEGY for entering this setup
    if active_breakout or location == "ABOVE_RESISTANCE":
        entry_mode = "BREAKOUT"
    elif location == "NEAR_RESISTANCE" and not active_breakout and loc_r_dist <= 2.0:
        entry_mode = "PRE-BREAKOUT"
    elif location == "NEAR_SUPPORT":
        entry_mode = "PULLBACK"
    else:
        entry_mode = "BREAKOUT"  # default — wait for conventional breakout

    # Safety net: PRE-BREAKOUT can NEVER become ENTRY ZONE.
    # 80% of fake trades come from pre-breakout positions entered too early.
    # Rule: PRE-BREAKOUT = prepare + monitor. Entry only when breakout CONFIRMS.
    if entry_mode == "PRE-BREAKOUT" and entry_status != "ENTRY READY":
        entry_status = "WAIT"
        entry_reason = "PRE-BREAKOUT — monitor only, wait for confirmed breakout above Rs.{:.0f}".format(
            loc_resistance if loc_resistance else 0
        )

    # Verdict determination — strict gated logic
    if regime == "PANIC" or risk_fail:
        verdict = "AVOID"
    elif total >= 85 and failed == 0 and regime not in ("BEAR",):
        verdict = "BLIND BUY"
    elif total >= 70 and failed <= 1:
        verdict = "STRONG BUY"
    elif total >= 55 and failed <= 2:
        verdict = "BUY"
    elif total >= 40:
        verdict = "RISKY"
    else:
        verdict = "AVOID"

    # Trade plan — prefer 4-Pillar (realistic slippage-adjusted)
    ltp = ta.get("current_price", 0)
    if screened and screened.entry_price_with_slippage > 0:
        entry = screened.entry_price_with_slippage
        target = screened.target_price
        sl = screened.stop_loss_with_slippage
        rr = screened.risk_reward_ratio
        hold = screened.expected_holding_days
    else:
        entry = ltp
        target = ta.get("suggested_target", ltp * 1.10)
        sl = ta.get("suggested_sl", ltp * 0.95)
        risk_ = abs(ltp - sl) if sl else 1
        rr = round(abs(target - ltp) / risk_, 2) if risk_ > 0 else 0
        hold = 7

    # Position sizing (default Rs. 10L portfolio, 2% risk rule)
    pos_shares, pos_capital, pos_risk_rs = 0, 0.0, 0.0
    portfolio_value = enrich.get("portfolio_value", 1_000_000)
    if _HAS_SIZER and entry > 0 and sl > 0 and entry > sl and verdict not in ("AVOID",):
        try:
            _sizer = PositionSizer(portfolio_value=portfolio_value)
            _ps = _sizer.calculate(
                symbol=symbol,
                entry_price=entry,
                stop_loss=sl,
                target_price=target if target > 0 else None,
            )
            pos_shares = _ps.shares
            pos_capital = _ps.position_value
            pos_risk_rs = _ps.risk_amount
        except Exception:
            pass

    return ExpertVerdict(
        symbol=symbol,
        sector=ta.get("sector", ""),
        company_name=ta.get("company_name", symbol),
        ltp=ltp,
        final_score=round(total, 1),
        verdict=verdict,
        gates=gates,
        gates_passed=passed,
        gates_partial=partial,
        gates_failed=failed,
        entry_price=round(entry, 2),
        target_price=round(target, 2),
        stop_loss=round(sl, 2),
        risk_reward=rr,
        entry_status=entry_status,
        holding_days=hold,
        checklist_score=chk.get("total_score", 0),
        composite_score=ta.get("composite_score", 0),
        p1_broker=screened.pillar1_broker if screened else 0,
        p2_unlock=screened.pillar2_unlock if screened else 0,
        p3_fundamental=screened.pillar3_fundamental if screened else 0,
        p4_technical=screened.pillar4_technical if screened else 0,
        master_score=screened.total_score if screened else 0,
        css_score=screened.css_score if screened else 0,
        css_signal=screened.css_signal if screened else "",
        # Enrichment
        macro_signal=enrich.get("macro_signal", ""),
        macro_score=enrich.get("macro_score", 50.0) or 50.0,
        breadth_pct=enrich.get("breadth_pct", 0.0) or 0.0,
        breadth_signal=enrich.get("breadth_signal", ""),
        sector_phase=enrich.get("sector_phase", ""),
        # Price location
        price_location=location,
        nearest_support=loc_support or 0.0,
        nearest_resistance=loc_resistance or 0.0,
        support_dist_pct=loc_s_dist or 0.0,
        resistance_dist_pct=loc_r_dist or 0.0,
        is_near_support=is_near_sup,
        is_near_resistance=is_near_res,
        entry_reason=entry_reason,
        entry_mode=entry_mode,
        # Position sizing
        pos_shares=pos_shares,
        pos_capital=pos_capital,
        pos_risk_rs=pos_risk_rs,
    )


# ═════════════════════════════════════════════════════════════════════
# SCREENER HELPERS
# ═════════════════════════════════════════════════════════════════════

def _init_screener():
    """Init MasterStockScreener, return (screener, regime, regime_reason)."""
    init_db()
    ms = MasterStockScreener(strategy="value")
    regime, reason = ms.check_market_regime()
    if regime != "PANIC":
        ms._preload_market_data()
        if ms.sharehub and hasattr(ms.sharehub, "auth_token") and ms.sharehub.auth_token:
            ms.sharehub_token = ms.sharehub.auth_token
    return ms, regime, reason


def _score_with_screener(
    ms: MasterStockScreener, symbol: str, ltp: float, sector: str = ""
) -> Optional[ScreenedStock]:
    """Score one stock through MasterStockScreener's 4-Pillar + CSS engine."""
    try:
        holdings = ms._broker_accumulation.get(symbol, {})
        ms._calculate_distribution_risk(symbol, ltp, holdings, {})
    except Exception:
        pass
    row = {
        "symbol": symbol,
        "securityName": symbol,
        "sectorName": sector,
        "lastTradedPrice": ltp,
        "totalTradeQuantity": 0,
    }
    try:
        return ms._score_stock(row)
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════════════
# SINGLE STOCK ANALYSIS
# ═════════════════════════════════════════════════════════════════════

async def analyze_single(symbol: str) -> Optional[ExpertVerdict]:
    """Full 6-Gate analysis for one stock."""
    symbol = symbol.upper().strip()

    print(f"\n{'═' * 70}")
    print(f"  🎯 NEPSE EXPERT ANALYSIS — {symbol}")
    print(f"     6-Gate Buy Verification Engine")
    print(f"     {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═' * 70}")

    # ── Phase 1: Technical Analysis (NepseAlpha) ─────────────────────
    print(f"\n  ⏳ Phase 1: Chart data + 13-Point Checklist + Multi-TF...")
    entry_status = "DAILY ONLY"

    async with aiohttp.ClientSession() as session:
        bars = await fetch_ohlcv(session, symbol)
        if not bars:
            print(f"  ❌ Could not fetch chart data for {symbol}. Check the symbol.")
            return None

        ta = run_analysis(symbol, bars)
        if not ta:
            print(f"  ❌ Technical analysis failed for {symbol}.")
            return None

        # Override stale daily close with live LTP during market hours
        if _is_market_hours_expert():
            _live = _get_live_price_expert(symbol)
            if _live:
                ta["current_price"] = _live

        chk = compute_checklist_score(ta)
        ta["checklist"] = chk
        ta["checklist_score"] = chk["total_score"]
        ta["composite_score"] = compute_composite_score(ta, chk)

        # Intraday (1H + 15m)
        try:
            intra_bars = await fetch_intraday_ohlcv(session, symbol)
            if intra_bars:
                intra = analyze_intraday(intra_bars)
                ic = compute_intraday_checks(intra)
                if ic.get("hourly_zone_ok") and ic.get("intraday_trigger_ok"):
                    entry_status = "ENTRY READY"
                elif ic.get("hourly_zone_ok"):
                    entry_status = "ENTRY ZONE"
                else:
                    entry_status = "WAIT"
        except Exception:
            pass

    print(f"  ✅ Phase 1 complete:")
    print(f"     Checklist {chk['total_score']}/13 | Composite {ta['composite_score']:.1f}")
    print(f"     Verdict: {ta['verdict']} | Trend: {ta['trend']} | RSI: {ta.get('rsi_14', 0):.1f}")
    print(f"     Multi-TF: Daily={ta['verdict']} Wk={ta.get('weekly_verdict', '—')}"
          f" Mon={ta.get('monthly_verdict', '—')} Yr={ta.get('yearly_verdict', '—')}")

    # ── Phase 2: 4-Pillar + CSS (ShareHub) ───────────────────────────
    print(f"\n  ⏳ Phase 2: 4-Pillar Fundamental + CSS scoring...")
    screened = None
    regime, regime_reason = "UNKNOWN", ""

    try:
        ms, regime, regime_reason = _init_screener()
        regime_icon = {"PANIC": "🚨", "BEAR": "🐻", "BULL": "🐂"}.get(regime, "📊")
        print(f"     {regime_icon} Market Regime: {regime} — {regime_reason}")

        if regime == "PANIC":
            print(f"  🚨 PANIC MODE — All verdicts forced to AVOID.")
        else:
            screened = _score_with_screener(ms, symbol, ta["current_price"], ta.get("sector", ""))
            if screened:
                print(f"  ✅ Phase 2 complete:")
                print(f"     Master Score: {screened.total_score:.1f}/100")
                print(f"     Broker {screened.pillar1_broker:.1f}/30 | Unlock {screened.pillar2_unlock:.1f}/20"
                      f" | Fund {screened.pillar3_fundamental:.1f}/20 | Tech {screened.pillar4_technical:.1f}/30")
                if screened.css_score:
                    print(f"     CSS: {screened.css_score:.3f} [{screened.css_signal}]")
                dist = getattr(screened, "distribution_risk", "N/A") or "N/A"
                print(f"     Distribution: {dist} | Manipulation: "
                      f"{getattr(screened, 'manipulation_severity', 'N/A') or 'N/A'}")
            else:
                print(f"  ⚠️  4-Pillar scoring failed — using TA-only verdict.")
    except Exception as e:
        print(f"  ⚠️  4-Pillar unavailable ({e}) — TA-only verdict.")

    # ── Phase 3: enrichment context (macro + breadth + sector) ──────────
    enrichment: Dict = {}
    try:
        _macro = _load_macro_context()
        if _macro:
            enrichment["macro_score"] = _macro.overall_macro_score
            enrichment["macro_signal"] = _macro.macro_signal
    except Exception:
        pass
    try:
        if _HAS_BREADTH:
            _ba = MarketBreadthAnalyzer()
            _bs = _ba.get_market_breadth()
            if _bs.total_stocks > 0:
                enrichment["breadth_pct"] = _bs.breadth_pct
                enrichment["breadth_signal"] = _bs.breadth_signal
    except Exception:
        pass
    try:
        if _HAS_SECTOR and ta.get("sector"):
            _leading = get_leading_sectors()
            _lagging = get_lagging_sectors()
            _sec = ta.get("sector", "")
            if _sec in _leading:
                enrichment["sector_leading"] = True
                enrichment["sector_phase"] = "HOT"
            elif _sec in _lagging:
                enrichment["sector_lagging"] = True
                enrichment["sector_phase"] = "COLD"
    except Exception:
        pass

    # ── Phase 4: 6-Gate Verdict ──────────────────────────────────────
    return _compute_verdict(symbol, ta, chk, screened, regime, regime_reason, entry_status,
                            enrichment=enrichment)

# ═════════════════════════════════════════════════════════════════════
# SCAN MODE
# ═════════════════════════════════════════════════════════════════════

async def scan_expert(sector: str = None, top_n: int = 5) -> List[ExpertVerdict]:
    """Full market scan with 6-Gate verification on all candidates."""

    print(f"\n{'═' * 70}")
    print(f"  🎯 NEPSE EXPERT SCAN — 6-Gate Buy Verification")
    print(f"     {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═' * 70}")

    # ── Phase 1: Technical Analysis scan ─────────────────────────────
    print(f"\n  Phase 1: Full market TA scan (NepseAlpha)...")
    scan_top = max(top_n, 10)  # Get at least 10 per sector for better candidate pool
    result = await scan_all_stocks(sector_filter=sector, top_n=scan_top)
    save_watchlist(result)

    # Collect all stocks with checklist ≥ 5
    candidates = []
    for sec_stocks in result.get("sectors", {}).values():
        for s in sec_stocks:
            if s.get("checklist_score", 0) >= 5:
                candidates.append(s)
    candidates.sort(key=lambda x: x.get("composite_score", 0), reverse=True)

    if not candidates:
        print(f"  ⚪ No candidates with checklist ≥ 5/13. Market conditions very weak.")
        return []

    print(f"  ✅ Phase 1 complete: {len(candidates)} candidates (checklist ≥ 5/13)")

    # ── Phase 2: 4-Pillar + CSS scoring ──────────────────────────────
    print(f"\n  Phase 2: 4-Pillar + CSS scoring for {len(candidates)} candidates...")
    regime, regime_reason = "UNKNOWN", ""
    ms = None

    try:
        ms, regime, regime_reason = _init_screener()
        regime_icon = {"PANIC": "🚨", "BEAR": "🐻", "BULL": "🐂"}.get(regime, "📊")
        print(f"  {regime_icon}  Market Regime: {regime} — {regime_reason}")
    except Exception as e:
        print(f"  ⚠️  4-Pillar init failed: {e}. Using TA-only verdicts.")

    # ── Enrichment context (gathered once for whole scan) ────────────
    enrichment: Dict = {}
    try:
        _macro = _load_macro_context()
        if _macro:
            enrichment["macro_score"] = _macro.overall_macro_score
            enrichment["macro_signal"] = _macro.macro_signal
    except Exception:
        pass
    try:
        if _HAS_BREADTH:
            _ba = MarketBreadthAnalyzer()
            _bs = _ba.get_market_breadth()
            if _bs.total_stocks > 0:
                enrichment["breadth_pct"] = _bs.breadth_pct
                enrichment["breadth_signal"] = _bs.breadth_signal
    except Exception:
        pass
    try:
        if _HAS_SECTOR:
            _leading = get_leading_sectors()
            _lagging = get_lagging_sectors()
        else:
            _leading, _lagging = [], []
    except Exception:
        _leading, _lagging = [], []

    if regime == "PANIC":
        print(f"  🚨 PANIC MODE ACTIVE — All verdicts = AVOID\n")
        return [
            _compute_verdict(
                s["symbol"], s, s.get("checklist", {}), None,
                "PANIC", regime_reason, s.get("entry_status", ""),
                enrichment=enrichment,
            )
            for s in candidates
        ]

    # Override stale daily close with live prices during market hours (single API call)
    if _is_market_hours_expert():
        _live_prices = _get_all_live_prices()
        if _live_prices:
            print(f"  📡 Live LTP loaded for {len(_live_prices)} symbols.")
            for _s in candidates:
                _lp = _live_prices.get(_s["symbol"])
                if _lp:
                    _s["current_price"] = _lp

    verdicts = []
    for i, s in enumerate(candidates, 1):
        sym = s["symbol"]
        ltp = float(s["current_price"])
        print(f"\r  [{i:3d}/{len(candidates)}] Scoring {sym:<12}", end="", flush=True)

        screened = _score_with_screener(ms, sym, ltp, s.get("sector", "")) if ms else None
        _sec = s.get("sector", "")
        sec_enrich = dict(enrichment)
        sec_enrich["sector_leading"] = _sec in _leading
        sec_enrich["sector_lagging"] = _sec in _lagging
        sec_enrich["sector_phase"] = "HOT" if _sec in _leading else ("COLD" if _sec in _lagging else "")
        v = _compute_verdict(
            sym, s, s.get("checklist", {}), screened,
            regime, regime_reason, s.get("entry_status", "DAILY ONLY"),
            enrichment=sec_enrich,
        )
        v.company_name = s.get("company_name", sym)
        verdicts.append(v)

    print(f"\n  ✅ Phase 2 complete: {len(verdicts)} stocks scored.\n")

    verdicts.sort(key=lambda x: x.final_score, reverse=True)
    return verdicts


# ═════════════════════════════════════════════════════════════════════
# DISPLAY
# ═════════════════════════════════════════════════════════════════════

def _bar(val: float, mx: float, w: int = 10) -> str:
    """Unicode bar chart: ███░░░."""
    n = int((val / mx) * w) if mx > 0 else 0
    return "█" * min(n, w) + "░" * max(0, w - n)


_VERDICT_ICONS = {
    "BLIND BUY": "🟢", "STRONG BUY": "🔵", "BUY": "🟡",
    "RISKY": "🟠", "AVOID": "🔴",
}
_STATUS_ICONS = {"PASS": "✅", "PARTIAL": "🟡", "FAIL": "❌"}


def print_verdict(v: ExpertVerdict):
    """Print beautiful single-stock 6-Gate verdict."""
    icon = _VERDICT_ICONS.get(v.verdict, "⚪")
    bar = _bar(v.final_score, 100, 40)

    print(f"\n{'═' * 70}")
    print(f"  {icon}  {v.verdict}  —  {v.symbol}  ({v.company_name})")
    print(f"  Rs. {v.ltp:,.2f}  |  {v.sector}")
    print(f"  [{bar}]  {v.final_score}/100")
    print(f"  Gates: {v.gates_passed} PASS  {v.gates_partial} PARTIAL  {v.gates_failed} FAIL")
    print(f"{'═' * 70}")

    for g in v.gates:
        si = _STATUS_ICONS.get(g.status, "⚪")
        print(f"\n  ─── {g.name:<28} {si} {g.status:<8} {g.score:.0f}/{g.max_score:.0f}")
        for d in g.details:
            print(f"       {d}")

    # Trade plan
    if v.verdict not in ("AVOID",):
        gain_pct = ((v.target_price - v.entry_price) / v.entry_price * 100) if v.entry_price > 0 else 0
        loss_pct = ((v.stop_loss - v.entry_price) / v.entry_price * 100) if v.entry_price > 0 else 0
        entry_icons = {"ENTRY READY": "🟢", "ENTRY ZONE": "🟡", "WAIT": "🔴"}
        ei = entry_icons.get(v.entry_status, "⚪")

        # Location — split into state + bias (action required)
        _loc_labels = {
            "NEAR_SUPPORT":     ("🟢", "NEAR SUPPORT"),
            "NEAR_RESISTANCE":  ("🟡", "NEAR RESISTANCE"),
            "ABOVE_RESISTANCE": ("🚀", "ABOVE RESISTANCE"),
            "MID_RANGE":        ("🔴", "MID-RANGE"),
        }
        _loc_bias_map = {
            "NEAR_SUPPORT":     "Hold above Rs.{s:.0f} — watch for bullish candle on volume",
            "NEAR_RESISTANCE":  "Breakout above Rs.{r:.0f} required",
            "ABOVE_RESISTANCE": "Ride the trend — trail stop below last swing low",
            "MID_RANGE":        "Wait for price to reach Rs.{s:.0f} support or Rs.{r:.0f} resistance",
        }
        _loc_icon, _loc_state = _loc_labels.get(v.price_location, ("⚪", v.price_location or "Unknown"))
        _bias_tmpl = _loc_bias_map.get(v.price_location, "")
        _loc_bias = _bias_tmpl.format(
            r=v.nearest_resistance if v.nearest_resistance else 0,
            s=v.nearest_support if v.nearest_support else 0,
        ) if _bias_tmpl else ""

        # Mechanical trigger conditions (shown when waiting for a level)
        if v.price_location == "NEAR_RESISTANCE" and v.entry_status == "WAIT":
            _trigger_label = "🎯 TRIGGER"
            _trigger = (
                f"Price > Rs.{v.nearest_resistance:,.0f}  |  Volume ≥ 1.5x avg  |  Bullish candle close"
            )
        elif v.price_location == "NEAR_SUPPORT" and v.entry_status in ("WAIT", "ENTRY ZONE"):
            _trigger_label = "🔀 ALT TRIGGER (Pullback)"
            _trigger = (
                f"Price at Rs.{v.nearest_support:,.0f} support  |  Volume stable (no dump)  |  Bullish rejection candle"
            )
        elif v.price_location == "MID_RANGE" and v.nearest_resistance and v.resistance_dist_pct <= 2.0:
            _trigger_label = "🎯 TRIGGER"
            _trigger = (
                f"Price > Rs.{v.nearest_resistance:,.0f}  |  Volume ≥ 1.5x avg  |  Bullish candle close"
            )
        else:
            _trigger_label = ""
            _trigger = ""

        # DECISION line — single clear action
        if v.entry_status == "ENTRY READY":
            _dec_icon, _decision = "✅", "EXECUTE — conditions met, buy at entry price"
        elif v.entry_mode == "PRE-BREAKOUT":
            _dec_icon, _decision = "🔵", "MONITOR ONLY — PRE-BREAKOUT: prepare, do NOT enter until breakout confirms"
        elif v.entry_status == "ENTRY ZONE":
            _dec_icon, _decision = "🟡", "LIMIT ORDER — set limit at entry price, don't chase"
        elif v.price_location == "NEAR_SUPPORT":
            _dec_icon, _decision = "🟡", "EARLY ENTRY POSSIBLE — near support, run `nepse confirm` first"
        elif v.price_location == "NEAR_RESISTANCE":
            _dec_icon, _decision = "⏳", "MONITOR — setup ready, watch for breakout with volume"
        elif v.price_location == "MID_RANGE":
            _dec_icon, _decision = "⏳", "MONITOR — price between S/R levels, wait for it to reach a level"
        elif v.price_location == "ABOVE_RESISTANCE":
            _dec_icon, _decision = "⚠️", "CAUTION — late entry, breakout already in progress"
        else:
            _dec_icon, _decision = "⏳", "MONITOR — setup ready, entry not confirmed yet"

        print(f"\n{'═' * 70}")
        print(f"  📋 TRADE PLAN")
        print(f"{'─' * 70}")
        print(f"  LTP:        Rs. {v.ltp:>10,.2f}")
        print(f"  Entry:      Rs. {v.entry_price:>10,.2f}  (with slippage)")
        print(f"  Target:     Rs. {v.target_price:>10,.2f}  ({gain_pct:>+.1f}%)")
        print(f"  Stop Loss:  Rs. {v.stop_loss:>10,.2f}  ({loss_pct:>+.1f}%)")
        print(f"  R:R:        {v.risk_reward:.1f}x")
        print(f"  Hold:       ~{v.holding_days} trading days (max 15d)")
        if v.price_location:
            print(f"  Location:   {_loc_icon} {_loc_state}")
            if _loc_bias:
                print(f"  Bias:       {_loc_bias}")
        if v.nearest_support:
            print(f"  Support:    Rs. {v.nearest_support:,.2f}  ({v.support_dist_pct:+.1f}% away)")
        if v.nearest_resistance:
            print(f"  Resistance: Rs. {v.nearest_resistance:,.2f}  ({v.resistance_dist_pct:+.1f}% away)")
        _reason_suffix = f"  ({v.entry_reason})" if v.entry_reason else ""
        print(f"  Entry:      {ei} {v.entry_status}{_reason_suffix}")
        if v.entry_mode:
            _mode_icons = {"BREAKOUT": "🟡", "PULLBACK": "🟢", "PRE-BREAKOUT": "🔵"}
            _mode_icon = _mode_icons.get(v.entry_mode, "⚪")
            print(f"  Mode:       {_mode_icon} {v.entry_mode}")
            # PULLBACK requires candle confirmation — never enter blindly at support
            if v.entry_mode == "PULLBACK" and v.entry_status in ("ENTRY ZONE", "WAIT"):
                print(f"  ⚠️  PULLBACK rule: wait for bullish rejection candle + no heavy red volume before entering")
        print(f"{'─' * 70}")
        print(f"  📌 DECISION: {_dec_icon} {_decision}")
        if _trigger:
            print(f"  {_trigger_label}:  {_trigger}")
        print(f"{'─' * 70}")

        # Position sizing (Rs. 10L default portfolio)
        if v.pos_shares > 0:
            port_pct = v.pos_capital / 1_000_000 * 100
            print(f"  💰 POSITION SIZING  (Rs. 10L portfolio · 2% risk rule)")
            print(f"  Buy:        {v.pos_shares:>6,} shares")
            print(f"  Deploy:     Rs. {v.pos_capital:>10,.2f}  ({port_pct:.1f}% of portfolio)")
            print(f"  Max Risk:   Rs. {v.pos_risk_rs:>10,.2f}  (if stop hit)")

        if v.verdict == "BLIND BUY":
            print(f"\n  ✅ ALL 6 GATES PASSED — This is as good as it gets.")
            print(f"  ✅ Execute at next market open. Set stop-loss immediately after fill.")
        elif v.verdict == "STRONG BUY":
            print(f"\n  🔵 5+ gates passed — Strong setup with one minor caveat.")
            print(f"  🔵 Check the 🟡 PARTIAL gate above, then decide.")
        elif v.verdict == "BUY":
            print(f"\n  🟡 4+ gates passed — Good setup. Review FAIL gates before executing.")
        elif v.verdict == "RISKY":
            print(f"\n  🟠 Multiple gates failed — High risk. Consider waiting for better setup.")

        print(f"{'═' * 70}")
    else:
        print(f"\n{'═' * 70}")
        print(f"  ⛔ DO NOT TRADE — Too many risk flags or PANIC market.")
        print(f"  ⛔ Wait for conditions to improve. Cash is a position.")
        print(f"{'═' * 70}")

    # Macro + breadth context footer
    if v.macro_signal or (v.breadth_pct and v.breadth_pct > 0) or v.sector_phase:
        print(f"\n  🔬 MACRO & MARKET CONTEXT")
        print(f"{'─' * 70}")
        if v.macro_signal:
            _m_icon = {"BULLISH": "🟢", "MILD_BULLISH": "🔵", "NEUTRAL": "⚪",
                       "MILD_BEARISH": "🟠", "BEARISH": "🔴"}.get(v.macro_signal, "⚪")
            print(f"  NRB Macro:   {_m_icon} {v.macro_signal}  ({v.macro_score:.0f}/100)")
            print(f"               Update config/macro.json with live NRB data for accuracy.")
        if v.breadth_pct and v.breadth_pct > 0:
            _b_icon = "🟢" if v.breadth_pct >= 60 else ("🟡" if v.breadth_pct >= 40 else "🔴")
            print(f"  Market:      {_b_icon} {v.breadth_pct:.0f}% stocks advancing today")
        if v.sector_phase:
            _sp_icon = "🔥" if v.sector_phase == "HOT" else "❄️"
            print(f"  Sector:      {_sp_icon} {v.sector or 'this sector'} is {v.sector_phase} (rotation)")
        print(f"{'═' * 70}")

    print()


def print_scan(verdicts: List[ExpertVerdict]):
    """Print scan results grouped by verdict tier."""
    tiers = ["BLIND BUY", "STRONG BUY", "BUY", "RISKY", "AVOID"]
    counts = {t: sum(1 for v in verdicts if v.verdict == t) for t in tiers}

    print(f"\n{'═' * 100}")
    print(f"  🎯 EXPERT SCAN RESULTS — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Analyzed: {len(verdicts)} candidates through 6-Gate verification")
    print(f"{'─' * 100}")
    print(f"  🟢 BLIND BUY: {counts['BLIND BUY']:>3}   🔵 STRONG BUY: {counts['STRONG BUY']:>3}   "
          f"🟡 BUY: {counts['BUY']:>3}   🟠 RISKY: {counts['RISKY']:>3}   🔴 AVOID: {counts['AVOID']:>3}")
    print(f"{'═' * 100}")

    # Actionable tiers with details
    for tier in ["BLIND BUY", "STRONG BUY", "BUY"]:
        stocks = [v for v in verdicts if v.verdict == tier]
        if not stocks:
            continue

        icon = _VERDICT_ICONS[tier]
        print(f"\n  {icon}  {tier}  ({len(stocks)} stocks)")
        print(f"  {'─' * 96}")
        print(f"  {'#':<4} {'Symbol':<10} {'Score':>6} {'Gates':>7} {'Chk':>5} {'4-Pillar':>8} "
              f"{'CSS':>6} {'R:R':>5} {'Mode':<13} {'Entry':<12}")
        print(f"  {'─' * 4} {'─' * 10} {'─' * 6} {'─' * 7} {'─' * 5} {'─' * 8} "
              f"{'─' * 6} {'─' * 5} {'─' * 13} {'─' * 12}")

        for i, v in enumerate(stocks, 1):
            gates_str = f"{v.gates_passed}/{v.gates_passed + v.gates_partial + v.gates_failed}"
            css_str = f"{v.css_score:.2f}" if v.css_score else "  —"
            ms_str = f"{v.master_score:.0f}" if v.master_score else " —"
            ei = {"ENTRY READY": "🟢", "ENTRY ZONE": "🟡", "WAIT": "🔴"}.get(v.entry_status, "⚪")
            _mi = {"BREAKOUT": "🟡", "PULLBACK": "🟢", "PRE-BREAKOUT": "🔵"}.get(v.entry_mode, "⚪")
            _mode_str = f"{_mi}{v.entry_mode}" if v.entry_mode else "—"

            print(f"  {i:<4} {v.symbol:<10} {v.final_score:>5.1f} {gates_str:>7} "
                  f"{v.checklist_score:>3}/13 {ms_str:>6}/100 {css_str:>6} "
                  f"{v.risk_reward:>5.1f} {_mode_str:<14} {ei}{v.entry_status}")

        # Detailed view for all stocks in each tier
        for v in stocks:
            gain_pct = ((v.target_price - v.entry_price) / v.entry_price * 100) if v.entry_price > 0 else 0
            _mode_icons = {"BREAKOUT": "🟡", "PULLBACK": "🟢", "PRE-BREAKOUT": "🔵"}
            _mi = _mode_icons.get(v.entry_mode, "⚪")
            _status_short = "READY" if v.entry_status == "ENTRY READY" else v.entry_status
            _mode_tag = f" [{_mi} {v.entry_mode} | {_status_short}]" if v.entry_mode else ""
            print(f"\n     📌 {v.symbol} — Rs. {v.ltp:,.2f} → "
                  f"Target Rs. {v.target_price:,.2f} ({gain_pct:+.1f}%) "
                  f"SL Rs. {v.stop_loss:,.2f} | R:R {v.risk_reward:.1f}x | ~{v.holding_days}d{_mode_tag}")
            for g in v.gates:
                si = _STATUS_ICONS.get(g.status, "⚪")
                print(f"        {si} {g.name}: {g.score:.0f}/{g.max_score:.0f}")

    # Quick list of risky/avoid
    risky = [v for v in verdicts if v.verdict == "RISKY"]
    avoid = [v for v in verdicts if v.verdict == "AVOID"]
    if risky:
        print(f"\n  🟠 RISKY ({len(risky)}): {', '.join(v.symbol for v in risky[:15])}")
    if avoid:
        print(f"  🔴 AVOID ({len(avoid)}): {', '.join(v.symbol for v in avoid[:15])}")

    actionable = counts["BLIND BUY"] + counts["STRONG BUY"] + counts["BUY"]
    if not actionable:
        print(f"\n  ⚪ No actionable signals today. Cash is a position — wait for better setups.")
    else:
        print(f"\n  ✅ {actionable} actionable signal(s) found.")

    # ── TOP PICKS — Selectivity layer ─────────────────────────────────
    # Rank actionable signals with a selection score.
    # Objective: surface the 1-2 stocks that deserve capital, not just the best setups.
    actionable_verdicts = [v for v in verdicts if v.verdict in ("BLIND BUY", "STRONG BUY", "BUY")]
    if actionable_verdicts:
        def _selection_score(v: ExpertVerdict) -> int:
            s = 0
            # Setup quality
            if v.verdict == "BLIND BUY":   s += 4
            elif v.verdict == "STRONG BUY": s += 3
            elif v.verdict == "BUY":        s += 2
            # Entry type — PULLBACK > BREAKOUT > PRE-BREAKOUT
            if v.entry_mode == "PULLBACK":            s += 3
            elif v.entry_mode == "BREAKOUT":          s += 2
            elif v.entry_mode == "PRE-BREAKOUT":      s += 1
            # CSS signal strength
            if v.css_score >= 0.60:   s += 2
            elif v.css_score >= 0.50: s += 1
            elif v.css_score <= 0.0:  s -= 3   # zero CSS = unreliable; deprioritize hard
            # Near trigger (within 2% of resistance or at support)
            if v.resistance_dist_pct and v.resistance_dist_pct <= 2.0: s += 1
            if v.is_near_support:                                        s += 1
            # Fundamentals (pillar 3 = 0-20 range)
            if v.p3_fundamental <= 0:  s -= 3   # zero fundamentals = speculative; never primary
            elif v.p3_fundamental < 5: s -= 2   # near-zero
            elif v.p3_fundamental < 8: s -= 1   # weak
            # Entry status boosts
            if v.entry_status == "ENTRY READY": s += 2
            elif v.entry_status == "ENTRY ZONE": s += 1
            return s

        ranked = sorted(actionable_verdicts, key=_selection_score, reverse=True)
        top_picks = ranked[:2]
        others = ranked[2:]

        print(f"\n{'═' * 100}")
        print(f"  🎯 TOP PICKS  (Capital Allocation — Max 1-2 trades)")
        print(f"{'─' * 100}")

        _priority_labels = {0: "PRIMARY", 1: "SECONDARY"}
        for rank, v in enumerate(top_picks):
            sc = _selection_score(v)
            _mi = {"BREAKOUT": "🟡", "PULLBACK": "🟢", "PRE-BREAKOUT": "🔵"}.get(v.entry_mode, "⚪")
            _ei = {"ENTRY READY": "🟢", "ENTRY ZONE": "🟡", "WAIT": "🔴"}.get(v.entry_status, "⚪")
            label = _priority_labels.get(rank, f"#{rank+1}")
            gain_pct = ((v.target_price - v.entry_price) / v.entry_price * 100) if v.entry_price > 0 else 0
            print(f"\n  {'🥇' if rank == 0 else '🥈'} {label}: {v.symbol}  "
                  f"({v.verdict})  [{_mi} {v.entry_mode}]  {_ei} {v.entry_status}")
            print(f"     Score: {v.final_score:.0f}/100  |  Selection: {sc} pts  |  "
                  f"R:R: {v.risk_reward:.1f}x  |  Target: Rs.{v.target_price:,.0f} ({gain_pct:+.1f}%)")
            if v.entry_reason:
                print(f"     Note:  {v.entry_reason}")

        if others:
            print(f"\n  ⚪ DEPRIORITIZED: {', '.join(v.symbol for v in others)}  "
                  f"(lower selectivity score — skip unless top picks fail to trigger)")

        # Remind about PRE-BREAKOUT discipline
        pre_in_top = [v for v in top_picks if v.entry_mode == "PRE-BREAKOUT"]
        if pre_in_top:
            syms = ", ".join(v.symbol for v in pre_in_top)
            print(f"\n  ⚠️  DISCIPLINE: {syms} is PRE-BREAKOUT — MONITOR ONLY. "
                  f"No entry until breakout confirms with volume.")

    print(f"\n{'═' * 100}\n")


# ═════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="NEPSE Expert Analysis — 6-Gate Buy Verification Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s NABIL                            # Deep analysis of NABIL
  %(prog)s --scan                           # Full market scan
  %(prog)s --scan --sector "Commercial Banks"
  %(prog)s --scan --top 10                  # More stocks per sector

Via alias:
  nepse expert NABIL
  nepse expert --scan
        """,
    )
    parser.add_argument("symbol", nargs="?", default=None,
                        help="Stock symbol to analyze (e.g. NABIL, NICA)")
    parser.add_argument("--scan", action="store_true",
                        help="Scan entire market through 6-Gate verification")
    parser.add_argument("--sector", type=str, default=None,
                        help="Filter by sector name (e.g. 'Commercial Banks')")
    parser.add_argument("--top", type=int, default=5,
                        help="Top N stocks per sector for TA phase (default 5)")
    args = parser.parse_args()

    if not args.scan and not args.symbol:
        parser.print_help()
        sys.exit(1)

    start = time.time()

    if args.scan:
        verdicts = asyncio.run(scan_expert(sector=args.sector, top_n=args.top))
        print_scan(verdicts)
    else:
        v = asyncio.run(analyze_single(args.symbol))
        if v:
            print_verdict(v)
        else:
            print(f"\n  ❌ Analysis failed for {args.symbol}. Check symbol and try again.")
            sys.exit(1)

    elapsed = time.time() - start
    print(f"  ⏱  Total time: {elapsed:.1f}s\n")


if __name__ == "__main__":
    main()
