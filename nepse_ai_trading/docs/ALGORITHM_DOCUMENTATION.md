# 🎯 NEPSE AI Trading Bot - Algorithm Documentation

> **Last Updated:** 2026-03-21  
> **Version:** 1.0  
> **Author:** AI Quantitative Engine

---

## Table of Contents

1. [Overview](#overview)
2. [Data Flow Architecture](#data-flow-architecture)
3. [The Core Quantitative Scoring Algorithm](#the-core-quantitative-scoring-algorithm)
4. [Data Sources](#data-sources)
5. [Technical Indicator Calculations](#technical-indicator-calculations)
6. [Scoring Rules](#scoring-rules)
7. [API Endpoints](#api-endpoints)
8. [Usage Guide](#usage-guide)
9. [Disclaimer](#disclaimer)

---

## Overview

This is a **proprietary quantitative stock screening engine** for NEPSE (Nepal Stock Exchange). It is **NOT** a simple API wrapper that returns pre-computed recommendations.

### What This System Does:

1. **Fetches ALL 299+ active stocks** from NEPSE official API
2. **Loops through EVERY stock** and calculates a score
3. **Applies core scoring pillars** of analysis, then layered risk intelligence
4. **Uses pandas-ta** for real technical indicator calculations
5. **Returns ranked stocks** based on OUR scoring algorithm

### What This System Does NOT Do:

- ❌ Does NOT just return ShareHub's "Top Picks"
- ❌ Does NOT rely on any external recommendation service
- ❌ Does NOT use pre-computed scores from any API

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MASTER STOCK SCREENER FLOW                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: FETCH ALL 299 STOCKS FROM NEPSE API                               │
│          └── NepseFetcher.fetch_live_market() → 299 stocks                 │
│                                                                             │
│  STEP 2: CHECK MARKET REGIME (Bull/Bear Market):                           │
│          └── If NEPSE Index < 50-day EMA → BEAR MARKET (-15 penalty)       │
│                                                                             │
│  STEP 3: PRE-LOAD MARKET DATA (reduces API calls):                         │
│          ├── Player Favorites (buyer/seller dominance)                     │
│          ├── Unlock Risks (MutualFund + Promoter)                          │
│          └── Broker Accumulation (if auth token available)                 │
│                                                                             │
│  STEP 4: FOR EACH STOCK (loop 299 times):                                  │
│          │                                                                  │
│          ├── PILLAR 1: Broker Analysis (30 pts max)                        │
│          │   └── Calculate score from buyer/seller dominance               │
│          │                                                                  │
│          ├── PILLAR 2: Unlock Risk (20 pts or -50 penalty!)                │
│          │   └── Calculate days until unlock → apply penalty               │
│          │                                                                  │
│          ├── PILLAR 3: Fundamentals (20 pts max)                           │
│          │   └── Score PE, PBV, ROE with NEPSE-specific rules              │
│          │                                                                  │
│          ├── PILLAR 4: Technical (30 pts max)                              │
│          │   └── Fetch 60-day OHLCV → pandas-ta calculations               │
│          │   └── Score EMA, RSI, MACD, ADX, Volume                         │
│          │                                                                  │
│          └── OVERRIDE LAYER (Real-World Constraints):                      │
│              └── Apply Bear Market Penalty (-15 if applicable)             │
│              └── Calculate Slippage-Adjusted Trade Plan                    │
│              └── Add T+2 Settlement Warning                                │
│                                                                             │
│  STEP 5: TOTAL SCORE = P1 + P2 + P3 + P4 + Market_Penalty (0-100 scale)   │
│                                                                             │
│  STEP 6: SORT ALL STOCKS BY SCORE (descending)                             │
│                                                                             │
│  STEP 7: RETURN TOP N (filtered by min_score threshold)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The Core Quantitative Scoring Algorithm

### Overview

| Pillar | Weight | Max Points | What It Measures |
|--------|--------|------------|------------------|
| 1. Broker/Institutional | 30% | 30 pts | Who is buying/selling |
| 2. Unlock Risk | 20% | 20 pts (or -50!) | Supply flood risk |
| 3. Fundamental Safety | 20% | 20 pts | Valuation metrics |
| 4. Technical & Momentum | 30% | 30 pts | Chart patterns & trends |

### Total Score Formula

```python
base_score = pillar1_broker + pillar2_unlock + pillar3_fundamental + pillar4_technical
total_score = base_score + market_regime_penalty  # -15 if bear market
# Range: 0-100 (can go negative if heavy penalties apply)
```

---

## 🛡️ The Override Layer (Real-World NEPSE Constraints)

Before returning the final score and trade plan, the engine applies real-world NEPSE constraints that theoretical algorithms often ignore:

### 1. Market Risk Penalty (Bear Market Detection)

```python
# If NEPSE Index is below its 50-day EMA → Bear Market
if nepse_index < ema_50:
    market_regime_penalty = -15  # Applied to ALL stocks!
```

**Rationale:** In a bear market, even fundamentally strong stocks fall. This penalty reduces false "BUY" signals during market downturns.

### 2. Slippage Modeling (1.5% on Entry/Exit)

```python
SLIPPAGE_PERCENT = 0.015  # 1.5%

# Real-world trade execution
entry_price_with_slippage = ltp * 1.015    # We buy HIGHER than expected
stop_loss_with_slippage = ltp * 0.935      # We exit LOWER in panic (-6.5% instead of -5%)
```

**Rationale:** NEPSE has low liquidity. In a panic sell, you won't get your target stop-loss price. We model this by assuming 1.5% slippage.

### 3. T+2 Settlement Warning

```python
minimum_hold_period = "3 Trading Days (T+2)"

# Warning for volatile stocks
if rsi > 70 or volume_spike > 3.0:
    execution_warning = "⚠️ HIGH VOLATILITY: Cannot be panic-sold tomorrow due to T+2!"
```

**Rationale:** NEPSE follows T+2 settlement. You CANNOT sell what you buy today for 3 trading days. This is critical for swing trading.

### Updated Trade Plan Output

```json
"trade_plan": {
    "raw_ltp": 796.90,
    "entry_price_with_slippage": 808.85,
    "target_price": 876.59,
    "stop_loss_raw": 757.05,
    "stop_loss_with_slippage": 745.10,
    "risk_reward_ratio": 2.0,
    "minimum_hold_period": "3 Trading Days (T+2)",
    "execution_warning": "ℹ️ Standard T+2 settlement applies"
}
```

---

## Data Sources

### Pillar 1 - Broker Analysis
| Data | Source | URL |
|------|--------|-----|
| Player Favorites | ShareHub API | `https://sharehubnepal.com/live/api/v1/floorsheet/bulk-transactions/player-fav` |
| Broker Accumulation | ShareHub API (Auth Required) | `https://sharehubnepal.com/data/api/v1/floorsheet-analysis/broker-aggressive-holdings` |

**Note:** We fetch RAW data (buyer %, seller %, winner). The SCORE is calculated by our algorithm.

### Pillar 2 - Unlock Risk
| Data | Source | URL |
|------|--------|-----|
| Promoter Unlock | ShareHub API | `https://sharehubnepal.com/data/api/v1/lock-in-period?type=0` |
| MutualFund Unlock | ShareHub API | `https://sharehubnepal.com/data/api/v1/lock-in-period?type=1` |

**Note:** We fetch unlock DATES. We CALCULATE days until unlock and apply penalties.

### Pillar 3 - Fundamentals
| Data | Source | URL |
|------|--------|-----|
| Company Data | ShareHub API | `https://sharehubnepal.com/data/api/v1/companies/{symbol}` |

**Metrics Extracted:** PE Ratio, EPS, Book Value, ROE

### Pillar 4 - Technical
| Data | Source | Method |
|------|--------|--------|
| 60-day OHLCV | NEPSE Official API | `NepseUnofficialApi.getCompanyPriceHistory()` |
| Indicators | pandas-ta library | EMA, RSI, MACD, ADX, Volume |

---

## Technical Indicator Calculations

All technical indicators are calculated using the **pandas-ta** library on real OHLCV data:

```python
from analysis.indicators import TechnicalIndicators

indicators = TechnicalIndicators(df)  # df = 60-day OHLCV DataFrame
indicators.add_ema()           # EMA 9 and EMA 21
indicators.add_rsi()           # RSI 14
indicators.add_macd()          # MACD histogram
indicators.add_volume_indicators()  # Volume spike ratio
indicators.add_adx()           # ADX trend strength
indicators.detect_golden_cross()    # EMA crossover detection
```

### Indicator Formulas

| Indicator | Formula/Method | Period |
|-----------|----------------|--------|
| EMA Short | Exponential Moving Average | 9 days |
| EMA Long | Exponential Moving Average | 21 days |
| RSI | Relative Strength Index | 14 days |
| MACD | MACD(12,26,9) histogram | - |
| ADX | Average Directional Index | 14 days |
| Volume Spike | Today's volume / 20-day SMA volume | 20 days |

---

## Scoring Rules

### Pillar 1: Broker/Institutional (30 pts max)

```python
# Player Favorites (Buyer/Seller Dominance)
if winner == "Buyer":
    if weight >= 65:  score += 15  # STRONG buyer dominance
    elif weight >= 55: score += 10
    elif weight >= 50: score += 5
    
if winner == "Seller":
    if weight >= 65:  score -= 20  # HEAVY PENALTY!
    elif weight >= 55: score -= 15
    elif weight >= 50: score -= 5

# Broker Accumulation (Top 3 concentration)
if top3_pct >= 70: score += 15  # EXTREME accumulation
elif top3_pct >= 50: score += 10
elif top3_pct >= 30: score += 5
```

### Pillar 2: Unlock Risk (20 pts max, or -50 PENALTY!)

```python
DANGER_DAYS = 30
WARNING_DAYS = 60

if no_unlock:
    score = 20  # SAFE!
    
elif days <= DANGER_DAYS:
    score = -50  # INSTANT REJECT!
    if is_mutual_fund:
        score -= 10  # Extra penalty - MFs WILL sell!
        
elif days <= WARNING_DAYS:
    score = 5  # Warning
    if is_mutual_fund:
        score -= 5
        
else:  # > 60 days
    score = 15  # Relatively safe
```

### Pillar 3: Fundamental Safety (20 pts max)

```python
# NEPSE-SPECIFIC PE THRESHOLDS (not US market!)
if pe < 15:     score += 8   # Cheap
elif pe <= 20:  score += 5   # Fair value
elif pe <= 35:  score += 0   # Expensive
else:           score -= 10  # Overvalued for NEPSE!

# Negative Book Value (Insolvent companies)
if book_value < 0:
    score -= 10  # INSTANT PENALTY!

# PBV (Price to Book Value)
if pbv < 2:     score += 6   # Undervalued
elif pbv <= 3:  score += 3   # Fair
elif pbv > 5:   score -= 5   # Expensive

# ROE (Return on Equity)
if roe >= 15:   score += 6   # Excellent
elif roe >= 10: score += 3   # Good
elif roe < 5:   score -= 3   # Weak
```

### Pillar 4: Technical & Momentum (30 pts max)

```python
BASE_SCORE = 15  # (or 5 if no price history - penalty!)

# EMA Crossover
if ema9 > ema21:
    score += 10  # Bullish
    if golden_cross_recent:
        score += 5  # Bonus!
else:
    score -= 5  # Bearish

# RSI (Relative Strength Index)
if 50 <= rsi <= 65:    score += 8   # Optimal zone
elif 30 <= rsi < 40:   score += 6   # Oversold bounce
elif 40 <= rsi < 50:   score += 3   # Building momentum
elif rsi > 70:         score -= 5   # OVERBOUGHT!

# Volume Spike
if volume_spike >= 2.0: score += 10  # BIG interest!
elif volume_spike >= 1.5: score += 7
elif volume_spike >= 1.0: score += 3
elif volume_spike < 0.5: score -= 3  # Low interest

# ADX (Trend Strength)
if adx > 30:   score += 5  # Strong trend
elif adx > 25: score += 3  # Trending
elif adx < 20: score -= 2  # Weak/choppy

# MACD
if macd_histogram > 0:
    score += 3
    if macd_rising:
        score += 2  # Momentum increasing
else:
    score -= 2
```

---

## API Endpoints

### Main Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analysis/screener` | GET | 🎯 **MAIN** - Quantitative Screener |
| `/api/analysis/rejected-stocks` | GET | Stocks rejected by screener |
| `/api/analysis/top-picks` | GET | Legacy top picks endpoint |

### Supporting Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analysis/player-favorites` | GET | Buyer/Seller dominance data |
| `/api/analysis/market-sentiment` | GET | Overall market mood |
| `/api/analysis/unlock-risks` | GET | MF + Promoter unlock risks |
| `/api/analysis/fundamentals/{symbol}` | GET | PE, EPS, ROE for a stock |
| `/api/analysis/technical/{symbol}` | GET | RSI, MACD, ADX signals |
| `/api/analysis/complete/{symbol}` | GET | All-in-one stock analysis |

### Query Parameters for `/api/analysis/screener`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_score` | int | 65 | Minimum score to include (0-100) |
| `top_n` | int | 10 | Number of top stocks to return |

---

## Usage Guide

### Python Usage

```python
from analysis.master_screener import get_best_stocks, get_rejected_stocks

# Get top 5 stocks with score >= 70
stocks = get_best_stocks(min_score=70, top_n=5)

for stock in stocks:
    print(f"{stock['symbol']}: {stock['total_score']}/100")
    print(f"  Entry: Rs. {stock['trade_plan']['entry_price']}")
    print(f"  Target: Rs. {stock['trade_plan']['target_price']} (+10%)")
    print(f"  Stop Loss: Rs. {stock['trade_plan']['stop_loss']} (-5%)")

# Get rejected stocks (unlock risk)
rejected = get_rejected_stocks(limit=10)
for r in rejected:
    print(f"AVOID: {r['symbol']} - {r['reason']}")
```

### API Usage

```bash
# Start the server
cd nepse_ai_trading
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Call the main endpoint
curl "http://localhost:8000/api/analysis/screener?min_score=70&top_n=5"

# Get rejected stocks
curl "http://localhost:8000/api/analysis/rejected-stocks"
```

### Response Format

```json
{
  "success": true,
  "timestamp": "2026-03-21T18:51:18",
  "algorithm": "Core Quantitative Scoring Engine",
  "count": 5,
  "stocks": [
    {
      "symbol": "GBLBS",
      "total_score": 95.0,
      "recommendation": "🟢 STRONG BUY",
      "pillar_scores": {
        "broker_institutional": 25.0,
        "unlock_risk": 20.0,
        "fundamental": 20.0,
        "technical_momentum": 30.0
      },
      "trade_plan": {
        "entry_price": 796.90,
        "target_price": 876.59,
        "stop_loss": 757.05
      }
    }
  ]
}
```

---

## Recommendation Mapping

| Score Range | Recommendation | Action |
|-------------|----------------|--------|
| 80-100 | 🟢 STRONG BUY | High confidence entry |
| 70-79 | 🟢 BUY | Good opportunity |
| 60-69 | 🟡 HOLD/ACCUMULATE | Monitor closely |
| 50-59 | 🟠 WEAK | Consider avoiding |
| 0-49 | 🔴 AVOID | Major red flags |

---

## Disclaimer

⚠️ **IMPORTANT - READ BEFORE USING**

1. **No Guarantee:** This algorithm provides analysis, NOT financial advice. Past performance does not guarantee future results.

2. **Risk of Loss:** All stock market investments carry risk. You may lose some or all of your invested capital.

3. **NEPSE Specifics:**
   - T+2 settlement cycle - you cannot day trade
   - No automated stop-loss execution - you must manually sell
   - Slippage risk in falling markets

4. **Not Backtested:** This algorithm has not been backtested on historical NEPSE data.

5. **Your Responsibility:** By using this system, you accept full responsibility for your investment decisions.

---

## File Structure

```
nepse_ai_trading/
├── analysis/
│   ├── master_screener.py    # 🎯 Main quantitative scoring engine
│   ├── indicators.py         # pandas-ta wrapper
│   └── top_picks.py          # Legacy analyzer
├── data/
│   ├── fetcher.py            # NEPSE API client
│   └── sharehub_api.py       # ShareHub API client
├── api/
│   └── routes/
│       └── analysis.py       # FastAPI endpoints
└── docs/
    └── ALGORITHM_DOCUMENTATION.md  # This file
```

---

*Generated by NEPSE AI Trading Bot v1.0*
