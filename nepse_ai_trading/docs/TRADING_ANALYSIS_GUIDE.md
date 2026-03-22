# 🎯 NEPSE Trading Analysis Guide
## Complete Guide to Stock Analysis for Millionaire Trading

This guide explains every metric, indicator, and analysis method used by the NEPSE AI Trading Bot.
As a beginner in finance, you'll learn what to look for and why each value matters.

---

## 📊 Table of Contents

1. [Understanding Stock Prices](#1-understanding-stock-prices)
2. [Technical Analysis (TA)](#2-technical-analysis-ta)
3. [Fundamental Analysis (FA)](#3-fundamental-analysis-fa)
4. [Momentum Analysis](#4-momentum-analysis)
5. [Broker Analysis (The Game Changer!)](#5-broker-analysis-the-game-changer)
6. [Promoter Unlock Risk](#6-promoter-unlock-risk)
7. [Banking Sector Specifics](#7-banking-sector-specifics)
8. [The Complete Analysis Workflow](#8-the-complete-analysis-workflow)
9. [Red Flags to Avoid](#9-red-flags-to-avoid)
10. [Green Flags to Look For](#10-green-flags-to-look-for)

---

## 1. Understanding Stock Prices

### Key Price Terms

| Term | What It Means | Why It Matters |
|------|---------------|----------------|
| **LTP** (Last Traded Price) | The most recent price a stock was bought/sold | Current market value |
| **Open** | First trade price of the day | Shows overnight sentiment |
| **High** | Highest price today | Resistance level |
| **Low** | Lowest price today | Support level |
| **Close** | Last price of previous day | Base for today's change |
| **52W High** | Highest in last 52 weeks | Resistance ceiling |
| **52W Low** | Lowest in last 52 weeks | Support floor |

### Price Position Analysis

```
📈 BULLISH SIGNAL: LTP near 52W High
   → Stock is breaking out, momentum is strong
   → But be careful of overbought conditions!

📉 VALUE OPPORTUNITY: LTP near 52W Low
   → Could be cheap entry point
   → But check WHY it's low (fundamentals matter!)

✅ IDEAL: LTP in middle range, trending upward
   → Room to grow, not overextended
```

---

## 2. Technical Analysis (TA)

Technical Analysis uses price patterns and indicators to predict future movement.
**Weight in our system: 35%**

### 2.1 Moving Averages (EMA)

**What**: Smoothed average of recent prices
**Why**: Shows trend direction

| Indicator | How to Read |
|-----------|-------------|
| **9 EMA** | Short-term trend (fast) |
| **21 EMA** | Medium-term trend (slow) |
| **50 EMA** | Long-term trend |

#### 🎯 Golden Cross (BUY Signal)
```
When 9 EMA crosses ABOVE 21 EMA
→ Short-term momentum turning positive
→ Potential start of uptrend
→ Our bot looks for this!
```

#### ⚠️ Death Cross (SELL Signal)
```
When 9 EMA crosses BELOW 21 EMA
→ Short-term momentum turning negative
→ Potential start of downtrend
→ Consider selling/avoiding
```

### 2.2 RSI (Relative Strength Index)

**Range**: 0 to 100
**What**: Measures if stock is overbought or oversold

| RSI Value | Meaning | Action |
|-----------|---------|--------|
| 0-30 | OVERSOLD | 🟢 Potential buy (too cheap) |
| 30-50 | BEARISH | ⚠️ Weak momentum |
| **50-65** | **OPTIMAL** | ✅ **Our target range!** |
| 65-70 | BULLISH | Good momentum |
| 70-100 | OVERBOUGHT | 🔴 Risky to buy (too expensive) |

**Our Rule**: RSI between 50-65 is ideal for swing trading

### 2.3 MACD (Moving Average Convergence Divergence)

**What**: Shows momentum and trend changes

| Signal | Meaning |
|--------|---------|
| MACD > Signal Line | 🟢 Bullish momentum |
| MACD < Signal Line | 🔴 Bearish momentum |
| MACD crossing above | BUY signal |
| MACD crossing below | SELL signal |

### 2.4 Volume Analysis

**Critical Rule**: Volume confirms price movement!

```
📈 Price UP + Volume UP = Strong move (GOOD)
📈 Price UP + Volume DOWN = Weak move (CAUTION)
📉 Price DOWN + Volume UP = Panic selling (AVOID)
📉 Price DOWN + Volume DOWN = Weak selling (watch for reversal)
```

**Our Rule**: Today's volume > 1.5x 20-day average = Breakout signal!

---

## 3. Fundamental Analysis (FA)

Fundamental Analysis looks at the company's financial health.
**Weight in our system: 30%**

### 3.1 PE Ratio (Price to Earnings)

**Formula**: PE = Stock Price / Earnings Per Share (EPS)
**What**: How much you pay for each rupee of earnings

| PE Value | Interpretation | Action |
|----------|----------------|--------|
| < 10 | Very cheap! | 🟢 Strong buy signal |
| 10-15 | Fair value | ✅ Good entry |
| 15-25 | Slightly expensive | 🟡 Okay if growth is strong |
| 25-40 | Expensive | ⚠️ Need strong reasons |
| > 40 | Very expensive | 🔴 Avoid unless exceptional growth |

**NEPSE Context**: Average PE around 15-20 for banks

### 3.2 PB Ratio (Price to Book Value)

**Formula**: PB = Stock Price / Book Value Per Share
**What**: How much you pay for the company's assets

| PB Value | Interpretation | Action |
|----------|----------------|--------|
| < 1.0 | Below book value! | 🟢 Undervalued opportunity |
| 1.0-2.0 | Fair value | ✅ Good |
| 2.0-3.0 | Slightly premium | 🟡 Check other metrics |
| > 3.0 | Expensive | ⚠️ Needs justification |

**Key Insight**: PB < 1 means you're paying less than the company's assets are worth!

### 3.3 EPS (Earnings Per Share)

**Formula**: EPS = Net Profit / Total Shares
**What**: How much profit per share

| EPS Value | Interpretation |
|-----------|----------------|
| Positive & Growing | 🟢 Company is profitable and improving |
| Positive & Stable | ✅ Consistent business |
| Positive & Declining | ⚠️ Profitability issues |
| Negative | 🔴 Company losing money - AVOID |

**Our Rule**: EPS must be positive!

### 3.4 ROE (Return on Equity)

**Formula**: ROE = Net Profit / Shareholder Equity × 100
**What**: How efficiently company uses your money

| ROE Value | Interpretation |
|-----------|----------------|
| > 15% | 🟢 Excellent - management is efficient |
| 10-15% | ✅ Good |
| 5-10% | 🟡 Average |
| < 5% | 🔴 Poor - money not being used well |

**Our Target**: ROE > 12%

### 3.5 Book Value

**What**: Net worth of company per share
**Formula**: (Total Assets - Total Liabilities) / Shares

If LTP < Book Value → Stock might be undervalued!

---

## 4. Momentum Analysis

Momentum shows how fast the price is moving.
**Weight in our system: 15%**

### Return Periods

| Period | What It Shows | Good Value |
|--------|---------------|------------|
| 7-Day Return | Short-term momentum | > +3% |
| 30-Day Return | Monthly trend | > +10% |
| 52-Week Return | Yearly performance | > +20% |

### Reading Momentum

```
✅ STRONG MOMENTUM:
   7D: +5%, 30D: +15%, 52W: +30%
   → Stock is consistently moving up
   → Good time to buy

⚠️ WEAK MOMENTUM:
   7D: -2%, 30D: +5%, 52W: +10%
   → Short-term pullback in uptrend
   → Could be buying opportunity

🔴 NEGATIVE MOMENTUM:
   7D: -5%, 30D: -10%, 52W: -20%
   → Stock is in downtrend
   → AVOID until trend reverses
```

---

## 5. Broker Analysis (The Game Changer!)

**This is the SECRET that most retail traders don't know!**
**Weight in our system: 20%**

### 5.1 Understanding the Game

```
In NEPSE, big brokers (and their clients) move the market:

1. When big brokers ACCUMULATE (buy quietly)
   → They know something
   → Supply decreases
   → Price will go UP

2. When big brokers DISTRIBUTE (sell quietly)
   → They're taking profits
   → Supply increases
   → Price will go DOWN

Your job: Follow the big money!
```

### 5.2 Broker Accumulation Signal

**Key Metric**: Top 3 Brokers Holding Percentage

| Holding % | Signal | Meaning |
|-----------|--------|---------|
| > 80% | 🔴 EXTREME | Big players loading HEAVILY |
| 60-80% | 🟠 STRONG | Significant institutional interest |
| 40-60% | 🟡 MODERATE | Some accumulation happening |
| < 40% | 🟢 NORMAL | Distributed among many |

**Trading Rule**:
```
High concentration (>50%) + Price stable/rising = BIG MOVE COMING
High concentration (>50%) + Price dropping = Distribution (AVOID)
```

### 5.3 What to Look For

1. **Few brokers, high volume** = Concentrated buying (BULLISH)
2. **Many brokers, low volume** = Normal trading
3. **Sudden spike in holding %** = Smart money entering

---

## 6. Promoter Unlock Risk

**🔴 CRITICAL: This can DESTROY your profits!**

### What is Lock-in Period?

When a company goes public (IPO):
- Promoters must LOCK their shares for 6 months to 3 years
- They CANNOT sell during this period
- When lock-in ends, they can FLOOD the market with shares

### Why It Matters

```
Before Unlock:
├── Supply = Limited (only public shares)
├── Demand = Normal
└── Price = Stable or Rising

After Unlock:
├── Supply = INCREASED (promoters can sell!)
├── Demand = Same or Lower (fear)
└── Price = Usually DROPS
```

### Our Risk Levels

| Days Until Unlock | Risk Level | Action |
|-------------------|------------|--------|
| ≤ 7 days | 🔴 CRITICAL | AVOID completely! |
| ≤ 14 days | 🔴 HIGH | Do NOT buy, consider selling |
| ≤ 30 days | 🟠 MEDIUM | Be very cautious |
| ≤ 60 days | 🟡 MONITOR | Keep watching |
| > 90 days | 🟢 SAFE | No immediate concern |

### Locked Shares Percentage Impact

```
If locked shares = 30% of total → HIGH IMPACT when unlocked
If locked shares = 5% of total → LOW IMPACT
```

---

## 7. Banking Sector Specifics

Banks dominate NEPSE. Special metrics for them:

### 7.1 NPL (Non-Performing Loan)

**What**: Percentage of loans not being repaid
**Lower is better!**

| NPL | Quality |
|-----|---------|
| < 2% | 🟢 Excellent - well-managed bank |
| 2-4% | ✅ Good |
| 4-5% | 🟡 Acceptable |
| > 5% | 🔴 Problem - risky bank! |

### 7.2 CD Ratio (Credit to Deposit)

**What**: How much of deposits are given as loans
**Ideal**: 70-80%

| CD Ratio | Meaning |
|----------|---------|
| < 60% | Bank not lending enough (lazy) |
| 60-80% | Healthy balance |
| 80-90% | Aggressive lending (watch NPL!) |
| > 90% | 🔴 Overleveraged - risky |

### 7.3 Capital Adequacy Ratio

**What**: Bank's capital vs risky assets
**NRB Requirement**: > 11%

| CAR | Status |
|-----|--------|
| > 14% | 🟢 Strong buffer |
| 11-14% | ✅ Compliant |
| < 11% | 🔴 Below requirement - AVOID |

---

## 8. The Complete Analysis Workflow

### Our Bot's Scoring System

```
TOTAL SCORE = (Technical × 35%) + (Fundamental × 30%) + 
              (Momentum × 15%) + (Broker × 20%)

Score Range: 0-100
```

### Recommendation Mapping

| Score | Recommendation | Action |
|-------|----------------|--------|
| ≥ 75 | 🟢 STRONG BUY | Enter position confidently |
| 60-74 | 🟢 BUY | Good entry with normal position |
| 45-59 | 🟡 HOLD | Wait for better entry or keep existing |
| 30-44 | 🟠 WEAK | Not recommended |
| < 30 | 🔴 AVOID | Stay away! |

### Step-by-Step Analysis

```
1. FILTER (Automatic)
   ├── Price > Rs. 100 (avoid penny stocks)
   ├── Volume > 1,000 (liquidity)
   └── No promoter unlock within 14 days

2. TECHNICAL CHECK
   ├── EMA: 9 > 21? (Uptrend)
   ├── RSI: 50-65? (Optimal momentum)
   └── Volume: > 1.5x average? (Breakout)

3. FUNDAMENTAL CHECK
   ├── EPS: Positive? (Profitable)
   ├── PE: < 25? (Not overpriced)
   ├── ROE: > 10%? (Efficient)
   └── For banks: NPL < 3%?

4. MOMENTUM CHECK
   ├── 7D Return: Positive? (Short-term up)
   ├── 30D Return: Positive? (Monthly up)
   └── 52W Return: Strong? (Yearly trend)

5. BROKER CHECK
   ├── Top 3 holding > 50%? (Accumulation!)
   └── Few brokers involved? (Concentrated)

6. FINAL SCORE & TARGETS
   ├── Entry Price: LTP
   ├── Target: LTP × 1.10 (10% profit)
   └── Stop Loss: LTP × 0.95 (5% protection)
```

---

## 9. Red Flags to Avoid

### 🔴 NEVER BUY IF:

1. **Negative EPS** - Company losing money
2. **NPL > 5%** (for banks) - Too many bad loans
3. **PE > 50** - Extremely overvalued
4. **Promoter unlock < 14 days** - Supply increase coming
5. **RSI > 80** - Severely overbought
6. **Volume spike + Price drop** - Smart money exiting
7. **Death cross just happened** - Downtrend starting

### ⚠️ BE CAUTIOUS IF:

1. **PE > 30** - Expensive, needs justification
2. **ROE < 5%** - Poor capital efficiency
3. **52W Return < -20%** - Stock in long downtrend
4. **Promoter unlock < 60 days** - Watch closely

---

## 10. Green Flags to Look For

### 🟢 STRONG BUY SIGNALS:

1. **Golden Cross** (9 EMA > 21 EMA) + High Volume
2. **PE < 15** with **ROE > 15%** - Cheap AND efficient
3. **PB < 1** - Trading below book value!
4. **Top 3 broker holding > 60%** + Price stable
5. **RSI 50-55** after pullback - Perfect entry
6. **NPL < 2%** (banks) - Well managed

### ✅ IDEAL STOCK PROFILE:

```
📊 Technical: BUY signal from ShareHub
📈 Momentum: 7D +3-8%, 30D +10-20%
💰 Valuation: PE 10-15, PB < 2
🏦 Quality: ROE > 12%, EPS growing
🤝 Broker: Top 3 holding > 50%
📅 Safety: No unlock within 90 days
```

---

## Quick Reference Card

```
╔════════════════════════════════════════════════════════════╗
║                 NEPSE TRADING CHEAT SHEET                  ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  ✅ BUY WHEN:                                              ║
║  ├── PE < 15, ROE > 12%, EPS positive                     ║
║  ├── RSI 50-65, 9 EMA > 21 EMA                            ║
║  ├── Volume > 1.5x average                                ║
║  └── Broker accumulation > 50%                            ║
║                                                            ║
║  🔴 AVOID WHEN:                                            ║
║  ├── Negative EPS or PE > 40                              ║
║  ├── Promoter unlock < 30 days                            ║
║  ├── RSI > 70 (overbought)                                ║
║  └── NPL > 5% (for banks)                                 ║
║                                                            ║
║  📊 TARGETS:                                               ║
║  ├── Profit Target: +10%                                  ║
║  ├── Stop Loss: -5%                                       ║
║  └── Risk:Reward = 2:1                                    ║
║                                                            ║
║  🎯 SCORING:                                               ║
║  ├── Score ≥ 75 → STRONG BUY                              ║
║  ├── Score 60-74 → BUY                                    ║
║  ├── Score 45-59 → HOLD                                   ║
║  └── Score < 45 → AVOID                                   ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

---

## API Endpoints Summary

| Endpoint | Purpose |
|----------|---------|
| `GET /api/analysis/top-picks` | Get top stocks to buy |
| `GET /api/analysis/promoter-unlock` | Stocks to AVOID |
| `GET /api/analysis/broker-accumulated` | Big money movement |
| `GET /api/analysis/complete/{symbol}` | Full stock analysis |
| `GET /api/analysis/fundamentals/{symbol}` | Financial metrics |
| `GET /api/analysis/technical/{symbol}` | Technical indicators |

---

*Document generated by NEPSE AI Trading Bot*
*Remember: Past performance doesn't guarantee future results. Always manage your risk!*
