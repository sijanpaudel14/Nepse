# NEPSE AI Trading System — Quantitative Overhaul Implementation Guide

> **Version:** 2.0 — Post-Implementation  
> **Status:** All Phases (0–5) Implemented  
> **Audience:** System operator / trader

---

## Table of Contents

1. [What Changed — Summary](#1-what-changed--summary)
2. [New Module Reference](#2-new-module-reference)
3. [CSS (Composite Signal Score) System](#3-css-composite-signal-score-system)
4. [Backtest Engine](#4-backtest-engine)
5. [Risk Engine](#5-risk-engine)
6. [Intelligence Layer](#6-intelligence-layer)
7. [Daily Trading Workflow](#7-daily-trading-workflow)
8. [Configuration Reference](#8-configuration-reference)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. What Changed — Summary

### Phase 0: Critical Bug Fixes

| Fix                            | File                                    | Impact                       |
| ------------------------------ | --------------------------------------- | ---------------------------- |
| JWT secret randomized          | `core/config.py`                        | Prevents auth bypass         |
| SQLite NullPool + WAL          | `core/database.py`                      | No more "database is locked" |
| UTC timestamps                 | `core/database.py`                      | Consistent time handling     |
| Slippage direction fix         | `risk/portfolio_manager.py`             | Stops trigger correctly      |
| Half-Kelly → Quarter-Kelly     | `risk/position_sizer.py`                | Smaller, safer bet sizes     |
| Sector rotation duplicate keys | `intelligence/sector_rotation.py`       | Month 7/8 both work now      |
| PE benchmarks per sector       | `intelligence/signal_aggregator.py`     | No more blanket PE<15        |
| Support bounce target uncapped | `analysis/strategies/support_bounce.py` | Natural targets              |
| Smart money denominators       | `intelligence/smart_money_tracker.py`   | Realistic score scaling      |

### Phase 1: Data Foundation

| Fix                    | File              | Impact                |
| ---------------------- | ----------------- | --------------------- |
| Bulk upsert for prices | `data/fetcher.py` | 50x faster data saves |
| Data freshness checker | `data/fetcher.py` | Warns on stale data   |

### Phase 2: Indicator Engine

| Module                  | File                             | Purpose                       |
| ----------------------- | -------------------------------- | ----------------------------- |
| Quant Indicators (MEIS) | `analysis/quant_indicators.py`   | 22 indicators, one call       |
| CSS Signal Scorer       | `analysis/signal_scorer.py`      | 6-component weighted score    |
| Operator Cycle Detector | `intelligence/operator_cycle.py` | 14-21 day pump/dump detection |

### Phase 3: Backtest Engine

| Feature                   | Location                | Description                                     |
| ------------------------- | ----------------------- | ----------------------------------------------- |
| Volume-dependent slippage | `backtesting/engine.py` | 5 tiers: 0.3% (liquid) to 2% (illiquid)         |
| CSS signal generation     | `backtesting/engine.py` | Backtest using CSS instead of legacy strategies |
| NEPSE cost model          | `backtesting/engine.py` | 0.36% broker + 0.015% SEBON + Rs.25 DP          |
| T+2 settlement            | `backtesting/engine.py` | Blocks exits < 3 trading days                   |
| Walk-forward backtest     | `backtesting/engine.py` | 6-month train, 2-month test windows             |
| Monte Carlo test          | `backtesting/engine.py` | Shuffle returns, compute p-value                |
| Strategy comparison       | `backtesting/engine.py` | Compare all strategies side-by-side             |

### Phase 4: Risk Engine

| Module                | File                            | Purpose                              |
| --------------------- | ------------------------------- | ------------------------------------ |
| ATR Dynamic Stops     | `risk/atr_stops.py`             | Entry - 2×ATR, progressive trailing  |
| Portfolio Risk Engine | `risk/portfolio_risk_engine.py` | 8 pre-trade checks, hard enforcement |
| LivePosition model    | `core/database.py`              | Position persistence across restarts |

### Phase 5: Intelligence Layer

| Module                   | File                                 | Purpose                             |
| ------------------------ | ------------------------------------ | ----------------------------------- |
| Broker Profile Tracker   | `intelligence/broker_profiles.py`    | 30/60/90 day net position tracking  |
| Syndicate Detection      | `intelligence/syndicate_detector.py` | Cross-broker coordination detection |
| Floorsheet Concentration | `intelligence/floorsheet_tracker.py` | HHI computation per stock           |
| NRB Macro Engine         | `intelligence/macro_engine.py`       | Macro scoring framework             |
| Breadth History          | `intelligence/market_breadth.py`     | DB-persisted A/D data               |
| Circuit Breaker in CSS   | `analysis/signal_scorer.py`          | CBP penalty in operator score       |
| DB Models                | `core/database.py`                   | DailyBreadth + MacroSnapshot tables |

---

## 2. New Module Reference

### `analysis/quant_indicators.py` — MEIS (Minimal Effective Indicator Set)

```python
from analysis.quant_indicators import QuantIndicators

qi = QuantIndicators()
indicators = qi.get_latest_indicators(df)  # df = OHLCV DataFrame
# Returns dict with 22 keys:
#   vwap, rvol, obv_slope, ad_slope, atr, bb_pctb, bb_width,
#   bb_width_pctl, stochrsi_k, stochrsi_d, squeeze, ema10, ema30,
#   ema10_slope, adx, supertrend_dir, rsi, close, volume, ...
```

### `analysis/signal_scorer.py` — CSS Engine

```python
from analysis.signal_scorer import compute_css, analyze_stock_css

# Quick analysis for a stock
result = analyze_stock_css("NABIL", indicators, profile="swing")
# result.css          → float 0-1 (final score)
# result.signal       → "BUY" / "HOLD" / "SELL"
# result.confidence   → "HIGH" / "MEDIUM" / "LOW"
# result.components   → dict of 6 sub-scores

# Direct CSS computation
from analysis.signal_scorer import compute_css
css_result = compute_css(
    symbol="NABIL",
    indicators=indicators,
    profile="swing",       # "short_term", "swing", "investment"
    broker_data={...},     # Optional: broker intelligence data
    fundamentals={...},    # Optional: PE, ROE, sector
    circuit_breaker_pct_used=0,  # Optional: % of circuit range used
)
```

**CSS Weight Profiles:**

| Component   | Short-Term | Swing | Investment |
| ----------- | ---------- | ----- | ---------- |
| Trend       | 0.15       | 0.20  | 0.15       |
| Momentum    | 0.25       | 0.20  | 0.10       |
| Volume      | 0.25       | 0.25  | 0.15       |
| Volatility  | 0.15       | 0.10  | 0.10       |
| Operator    | 0.15       | 0.15  | 0.20       |
| Fundamental | 0.05       | 0.10  | 0.30       |

**Signal Thresholds:**

- CSS ≥ 0.65 → **BUY**
- CSS ≤ 0.35 → **SELL**
- Between → **HOLD**

### `risk/atr_stops.py` — Dynamic ATR Stops

```python
from risk.atr_stops import create_stop_state, update_stop_state

# At entry
state = create_stop_state(
    entry_price=500.0,
    atr=15.0,
    symbol="NABIL"
)
# state.initial_stop = 470.0  (entry - 2×ATR)
# state.trailing_stop = 470.0

# Daily update with latest high price
state = update_stop_state(state, current_high=530.0, current_atr=14.0)
# Trailing stop ratchets up (never goes down)
```

**Progressive Trailing Stop Tiers:**

| ATR Profit Multiple | Trail Distance     |
| ------------------- | ------------------ |
| 0-1 ATR profit      | 2.0 × ATR (loose)  |
| 1-2 ATR profit      | 1.5 × ATR          |
| 2-3 ATR profit      | 1.0 × ATR          |
| 3+ ATR profit       | 0.75 × ATR (tight) |

### `risk/portfolio_risk_engine.py` — Hard Risk Enforcement

```python
from risk.portfolio_risk_engine import PortfolioRiskEngine

engine = PortfolioRiskEngine(capital=1_000_000)

# Pre-trade check (8 sequential checks)
result = engine.pre_trade_check(
    symbol="NABIL",
    price=500.0,
    shares=100,
    sector="Commercial Banks",
    atr=15.0
)
if result.allowed:
    engine.register_entry("NABIL", 500.0, 100, "Commercial Banks", 15.0)
else:
    print(f"BLOCKED: {result.reason}")

# Daily: update prices and check stops
engine.update_prices({"NABIL": 520.0})
```

**8 Pre-Trade Checks (in order):**

1. Daily loss limit (3%) — blocks all trading
2. Max drawdown (20%) — system halt
3. Max open positions (5)
4. Max per-stock allocation (25%)
5. Sector concentration (30%)
6. Correlation check (max 3 same-sector)
7. Minimum signal quality (CSS ≥ 0.6)
8. Risk budget check (Kelly + ATR sizing)

---

## 3. CSS (Composite Signal Score) System

The CSS replaces the old 4-pillar scoring with a 6-component quantitative score:

```
CSS = w₁×Trend + w₂×Momentum + w₃×Volume + w₄×Volatility + w₅×Operator + w₆×Fundamental
```

Each component is scored 0-1. The weighted sum produces the final CSS (0-1).

### Component Details

**Trend (0-1):** EMA alignment, ADX strength, SuperTrend direction
**Momentum (0-1):** StochRSI position, RSI zone, EMA slope
**Volume (0-1):** Relative volume (RVOL), OBV slope, A/D slope
**Volatility (0-1):** Bollinger %B, squeeze detection, BB width percentile
**Operator (0-1):** Broker concentration, buyer dominance, distribution risk, circuit breaker proximity
**Fundamental (0-1):** Sector-specific PE, ROE quality, dividend history

### Signal Freshness

CSS applies a decay factor: `score × 0.8^days` where `days` = trading days since data was last updated. Stale data gets penalized automatically.

---

## 4. Backtest Engine

### Quick CSS Backtest

```python
from backtesting.engine import quick_backtest

result = quick_backtest(
    df=ohlcv_data,        # DataFrame with OHLCV + volume
    initial_capital=1_000_000,
    mode="css_swing",     # "css_swing", "css_short", "css_invest"
)
print(f"Return: {result.total_return_pct:.1f}%")
print(f"Sharpe: {result.sharpe_ratio:.2f}")
print(f"Max DD: {result.max_drawdown_pct:.1f}%")
```

### Walk-Forward Validation

```python
from backtesting.engine import walk_forward_backtest

results = walk_forward_backtest(
    df=ohlcv_data,
    train_months=6,
    test_months=2,
    initial_capital=1_000_000,
    mode="css_swing",
)
# Returns list of BacktestResult for each test window
for r in results:
    print(f"Window {r.start_date}–{r.end_date}: {r.total_return_pct:.1f}%")
```

### Monte Carlo Statistical Test

```python
from backtesting.engine import monte_carlo_test

stats = monte_carlo_test(
    df=ohlcv_data,
    n_simulations=1000,
    mode="css_swing",
)
# stats = {"actual_return": 15.2, "p_value": 0.03, "percentile_95": 8.1}
# p_value < 0.05 = strategy return is statistically significant
```

### Compare All Strategies

```python
from backtesting.engine import compare_strategies

df_comparison = compare_strategies(ohlcv_data, initial_capital=1_000_000)
print(df_comparison.to_string())
# Shows: strategy, return%, sharpe, max_dd%, win_rate, trades
```

### NEPSE Cost Model

Every backtest includes realistic NEPSE costs:

- **Broker commission:** 0.36% each side (buy + sell)
- **SEBON fee:** 0.015% each side
- **DP charge:** Rs. 25 per sell transaction
- **Slippage:** Volume-dependent (0.3% to 2.0%)

### Slippage Tiers

| Average Daily Volume | Slippage           |
| -------------------- | ------------------ |
| < 5,000              | 2.0% (micro-cap)   |
| 5,000–20,000         | 1.0% (small-cap)   |
| 20,000–100,000       | 0.5% (mid-cap)     |
| 100,000–500,000      | 0.4% (large-cap)   |
| > 500,000            | 0.3% (very liquid) |

---

## 5. Risk Engine

### ATR Stop System

Every position gets a dynamic stop based on the stock's actual volatility:

1. **Initial stop:** Entry price - 2×ATR (floored at 15% max loss)
2. **Trailing stop:** Ratchets up as price rises, tightens with profit
3. **Never moves down** — once raised, the stop stays

### Portfolio Risk Engine Flow

```
Signal Generated → Pre-Trade Check (8 gates) → Allowed?
    → YES: Size position (Quarter-Kelly), set ATR stop, register entry
    → NO:  Blocked with reason, skip this trade
```

### Position Persistence

Positions are now stored in SQLite (`live_positions` table). The system survives:

- Process restarts
- Power failures
- Crashes

On startup, `PortfolioRiskEngine` loads all OPEN positions from DB.

---

## 6. Intelligence Layer

### Broker Profile Tracking (30/60/90 day)

```python
from intelligence.broker_profiles import build_broker_profiles

summary = build_broker_profiles(broker_data, symbol="NABIL")
# summary.top_buyers   → List[BrokerProfile] sorted by 30d net
# summary.top_sellers  → List[BrokerProfile]
# summary.is_concentrated_buying → True if HHI > 0.25 and net positive
# summary.signal_strength → "STRONG_ACCUMULATION" / "MILD_ACCUMULATION" / "DISTRIBUTION" / "NEUTRAL"
```

Each `BrokerProfile` has:

- `net_30d`, `net_60d`, `net_90d` — rolling net quantity
- `is_accumulating` — net positive across all windows
- `trend_reversal` — detects flip from accumulation to distribution (or vice versa)

### Syndicate Detection

```python
from intelligence.syndicate_detector import detect_syndicate

signal = detect_syndicate(
    target_symbol="NABIL",
    broker_net_positions={
        "broker_36": {"NABIL": 5000, "SBL": 3000, "NICA": 2000},
        "broker_58": {"NABIL": 4000, "SBL": 2500, "NICA": 1500},
        "broker_12": {"NABIL": 3000, "SBL": 2000, "NICA": 1000},
    },
)
# signal.syndicate_detected → True (3 brokers buying same basket)
# signal.confidence → 0.72
# signal.common_stocks → ["SBL", "NICA"]
```

### Floorsheet Concentration (HHI)

```python
from intelligence.floorsheet_tracker import analyze_floorsheet_concentration

result = analyze_floorsheet_concentration(trades, symbol="NABIL")
# result.hhi → 3200 (highly concentrated = operator)
# result.top3_share_pct → 45.2% (top 3 brokers control 45%)
# result.is_operator_likely → True
```

**HHI Interpretation:**
| HHI | Level | Meaning |
|-----|-------|---------|
| < 1500 | LOW | Competitive, normal trading |
| 1500–2500 | MODERATE | Some concentration |
| > 2500 | HIGH | Operator activity likely |

### NRB Macro Scoring

```python
from intelligence.macro_engine import compute_macro_score

score = compute_macro_score(
    interbank_rate=4.5,     # NRB daily interbank rate
    ccd_ratio=72.0,         # Credit-to-Core-Deposit %
    inflation_rate=5.2,     # YoY CPI
    remittance_growth=8.0,  # Monthly remittance growth %
    base_rate=7.0,          # NRB base rate
)
# score.liquidity_score → 68.0 (good liquidity)
# score.banking_health_score → 52.0
# score.overall_macro_score → 60.5
# score.macro_signal → "MILD_BULLISH"
# score.css_adjustment → +0.04 (add to CSS fundamental component)
```

### Market Breadth History

```python
from intelligence.market_breadth import MarketBreadthAnalyzer

analyzer = MarketBreadthAnalyzer()

# Save today's breadth to DB
snapshot = analyzer.get_market_breadth()
analyzer.save_breadth_snapshot(snapshot)

# Get 30 days of history
history = analyzer.get_breadth_history(days=30)
# Returns DataFrame: date, advancing, declining, breadth_pct, regime, ...

# Detect multi-day divergence
warning = analyzer.detect_multi_day_divergence(days=5)
# "BEARISH DIVERGENCE (5d): Index rising but avg breadth only 38% — narrow rally, correction risk"
```

---

## 7. Daily Trading Workflow

### Morning Routine (Before 11:00 AM)

```bash
# 1. Fetch latest data
python main.py --fetch-only

# 2. Check market breadth
python -c "
from intelligence.market_breadth import MarketBreadthAnalyzer
a = MarketBreadthAnalyzer()
snap = a.get_market_breadth()
a.save_breadth_snapshot(snap)
print(a.format_report(snap))
div = a.detect_multi_day_divergence()
if div: print(div)
"

# 3. Run CSS screening
python main.py --screen-only
```

### Signal Evaluation

When a BUY signal appears:

1. Check CSS score (≥ 0.65 required)
2. Check CSS components — which ones are strong/weak?
3. Check pre-trade risk engine (passes all 8 gates?)
4. Check ATR stop level — is the stop acceptable?
5. Check NRB macro score — is macro environment supportive?
6. Check breadth regime — is the market healthy?

### Position Management

```python
# Daily: update prices and check stops
from risk.portfolio_risk_engine import PortfolioRiskEngine
engine = PortfolioRiskEngine(capital=1_000_000)

# Update with today's prices
engine.update_prices({
    "NABIL": current_nabil_price,
    "SBL": current_sbl_price,
    # ...
})
# Prints stop-hit warnings automatically
```

### Weekly Review

1. Run backtest comparison: `compare_strategies(df)`
2. Update NRB macro data: `compute_macro_score(interbank_rate=..., ...)`
3. Check walk-forward results for recent periods
4. Review breadth divergence history

---

## 8. Configuration Reference

### `core/config.py` Key Settings

| Setting                       | Default | Description                 |
| ----------------------------- | ------- | --------------------------- |
| `broker_commission_pct`       | 0.0036  | 0.36% per transaction       |
| `sebon_fee_pct`               | 0.00015 | 0.015% SEBON regulatory fee |
| `dp_charge`                   | 25.0    | Rs. 25 per sell transaction |
| `nepse_trading_days_per_year` | 230     | NEPSE has ~230 trading days |
| `risk_free_rate`              | 0.055   | NRB T-bill rate (~5.5%)     |
| `risk_per_trade`              | 0.02    | 2% capital risk per trade   |
| `max_positions`               | 5       | Max concurrent positions    |
| `sector_concentration_limit`  | 0.30    | 30% max in one sector       |

### Environment Variables

| Variable              | Required | Description                 |
| --------------------- | -------- | --------------------------- |
| `OPENAI_API_KEY`      | Yes      | GPT-4o-mini for AI analysis |
| `TELEGRAM_BOT_TOKEN`  | Yes      | Telegram notifications      |
| `TELEGRAM_CHAT_ID`    | Yes      | Your Telegram chat ID       |
| `SHAREHUB_AUTH_TOKEN` | No       | ShareHub bearer token       |
| `JWT_SECRET_KEY`      | Auto     | Auto-generated if not set   |

---

## 9. Troubleshooting

### "database is locked" errors

Already fixed: SQLite now uses NullPool + WAL mode. If you still see this, ensure only one process writes at a time.

### CSS returns 0.5 for everything

This means no indicator data is being passed. Ensure you call `QuantIndicators.get_latest_indicators(df)` with a valid OHLCV DataFrame with at least 50 rows.

### Backtest shows 0 trades

Check that:

- Your data has at least 100 rows
- CSS mode is specified: `quick_backtest(df, mode="css_swing")`
- Volume column is present (needed for RVOL calculation)

### Walk-forward returns empty

Need at least 8 months of data (6 months train + 2 months test).

### Pre-trade check always blocks

Check `result.reason` — common blockers:

- Daily loss limit hit (reset at market open)
- Max positions reached (close one first)
- Sector concentration exceeded

### Macro score is always 50

NRB data must be entered manually. Use `compute_macro_score()` with actual NRB figures from https://www.nrb.org.np.
