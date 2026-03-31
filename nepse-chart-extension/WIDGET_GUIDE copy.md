# NEPSE Pro Analyzer v3.0 — The Complete Expert Guide (Professional Edition)

> **Your edge over every other trader on NEPSE.** This Chrome/Edge extension intercepts ShareHub's live chart data, runs 27 candlestick pattern scans, 15+ technical indicators, multi-timeframe confluence, support/resistance with distance tracking, Fibonacci, Pivot Points, breakout detection, Wyckoff market phase analysis, market structure detection, momentum profiling, RSI divergence scanning, and delivers a professional-grade verdict — all in real time, right on your chart.

---

## Table of Contents

1. [Quick Setup](#1-quick-setup)
2. [ShareHub Chart Controls — All Timeframes](#2-sharehub-chart-controls--all-timeframes)
3. [Widget Layout — The 6-Tab Interface](#3-widget-layout--the-6-tab-interface)
4. [How to Analyze: 1-Hour Market (Intraday)](#4-how-to-analyze-1-hour-market-intraday)
5. [How to Analyze: 1-Day Market (Swing Trading)](#5-how-to-analyze-1-day-market-swing-trading)
6. [How to Analyze: 1-Month Market (Position Trading)](#6-how-to-analyze-1-month-market-position-trading)
7. [How to Analyze: 3-Month Market (Trend Following)](#7-how-to-analyze-3-month-market-trend-following)
8. [How to Analyze: 6-Month Market (Sector Rotation)](#8-how-to-analyze-6-month-market-sector-rotation)
9. [How to Analyze: 1-Year Market (Investor Grade)](#9-how-to-analyze-1-year-market-investor-grade)
10. [How to Analyze: 5-Year Market (Wealth Building)](#10-how-to-analyze-5-year-market-wealth-building)
11. [Multi-Timeframe Confluence — The Master Skill](#11-multi-timeframe-confluence--the-master-skill)
12. [The Complete Buying Decision Framework](#12-the-complete-buying-decision-framework)
13. [All 27 Candlestick Patterns — Expert Guide](#13-all-27-candlestick-patterns--expert-guide)
14. [All Technical Indicators — How Experts Read Them](#14-all-technical-indicators--how-experts-read-them)
15. [Support, Resistance & Key Levels — Pro Usage](#15-support-resistance--key-levels--pro-usage)
16. [The Scoring System](#16-the-scoring-system)
17. [New v3.0 Features — Complete Reference](#17-new-v30-features--complete-reference)
18. [NEPSE-Specific Rules](#18-nepse-specific-rules)
19. [Warnings Reference](#19-warnings-reference)
20. [Troubleshooting](#20-troubleshooting)

---

## 1. Quick Setup

| Step              | Command / Action                                                  |
| ----------------- | ----------------------------------------------------------------- |
| 1. Start Backend  | `cd nepse-chart-extension/backend && uvicorn main:app --reload`   |
| 2. Load Extension | Edge → `edge://extensions/` → Load Unpacked → `extension/` folder |
| 3. Open ShareHub  | Go to `https://sharehubnepal.com/technical-chart/SYMBOL`          |

Widget appears automatically in the bottom-right within 2–3 seconds.

---

## 2. ShareHub Chart Controls — All Timeframes

ShareHub provides two controls on the chart that determine what data the widget analyzes:

### Resolution Dropdown (Candle Size)

This sets how big each individual candle/bar is:

| Category    | Resolution | Each Candle =       | Best For                 |
| ----------- | ---------- | ------------------- | ------------------------ |
| **MINUTES** | 1 minute   | 1 min of trading    | Scalping, entry timing   |
|             | 5 minutes  | 5 min               | Intraday momentum        |
|             | 15 minutes | 15 min              | Short-term swings        |
|             | 30 minutes | 30 min              | Half-session analysis    |
| **HOURS**   | 1 hour ⭐  | 1 hour (~4 per day) | **Intraday analysis**    |
| **DAYS**    | 1 day ⭐   | 1 trading day       | **Best for NEPSE swing** |
|             | 2 days     | 2 trading days      | Smoothed daily           |
|             | 3 days     | 3 trading days      | Short-term swing         |
|             | 1 week ⭐  | 5 trading days      | Medium-term position     |
|             | 1 month    | ~22 trading days    | Long-term investing      |
|             | 3 months   | ~66 trading days    | Macro trend              |
|             | 6 months   | ~132 trading days   | Strategic allocation     |

### Range Bar (How Much History)

The quick bar at the bottom sets how far back to look:

| Button | History Shown       | Use Case                |
| ------ | ------------------- | ----------------------- |
| **1d** | Last 1 trading day  | Today's intraday action |
| **5d** | Last 5 trading days | This week's movement    |
| **1m** | Last 1 month        | Recent trend (30 days)  |
| **3m** | Last 3 months       | Quarter trend           |
| **6m** | Last 6 months       | Half-year trend         |
| **1y** | Last 1 year         | Annual cycle            |
| **5y** | Last 5 years        | Full historical context |

> **The combination matters:** Setting resolution to **1 day** and range to **1 year** gives you 252 daily candles — ideal for swing trading with reliable indicators (SMA200 needs 200+ bars).

### What the Widget Does with Each Resolution

When you select a resolution, the backend automatically resamples your data to higher timeframes for multi-TF analysis:

| You Select    | Widget Also Computes  | Total Insight                     |
| ------------- | --------------------- | --------------------------------- |
| 1/5/15/30 min | → Hourly + Daily      | Intraday with daily context       |
| 1 hour        | → Daily + Weekly      | Intraday with swing context       |
| 1 day         | → Weekly + Monthly    | **Swing with full macro context** |
| 1 week        | → Monthly + Quarterly | Position with long-term context   |
| 1 month       | → Quarterly + Yearly  | Investor with macro context       |
| 3/6 months    | → Yearly              | Strategic macro view              |

---

## 3. Widget Layout — The 6-Tab Interface

The v3.0 widget has 6 tabs: **📊 Overview** | **⚡ Momentum** | **📈 Technical** | **🔄 Multi-TF** | **🎯 Levels** | **🏛️ Market**

### 📊 Overview Tab (Default)

Your 10-second decision screen:

- **Verdict Banner** — STRONG BUY / BUY / HOLD / SELL / STRONG SELL with confidence % bar
- **Price** — Current price with change % (▲ green, ▼ red)
- **Summary Badges** — Oscillators / Moving Avg / Overall (TradingView-style Buy/Sell/Neutral)
- **4 Status Cards** — Quick-glance cards showing:
  - 🔓 **Breakout** — Bullish Breakout / Bearish Breakdown / Testing Resistance / BB Breakout / Near Zone / Range-Bound
  - 📈 **Trend** — UPTREND / DOWNTREND / SIDEWAYS with color coding
  - 🏗️ **Structure** — HH/HL Bullish / LH/LL Bearish / Expanding Range / Contracting (Squeeze) / Transitioning
  - 🔄 **Phase** — Markup / Markdown / Accumulation / Distribution / Consolidation (Wyckoff-style)
- **Candlestick Patterns** — Detected patterns with ▲/▼ direction AND strength score (e.g., +200, -150)
- **Quick Indicators** — 4-cell grid:
  - RSI(14) with gauge bar and zone label (Extreme Overbought / Overbought / Bullish Zone / Neutral Zone / Bearish Zone / Oversold / Extreme Oversold)
  - ADX(14) with strength label (Very Strong / Strong / Developing / Weak/No Trend)
  - MACD direction (▲ Bullish / ▼ Bearish / → Neutral)
  - Momentum Status (Strong Bullish/Bearish Momentum, Accelerating, Decelerating)
- **Operator Activity** — Volume anomaly detection with volume ratio
- **Nearest S/R Quick View** — Closest resistance above and closest support below with exact price and % distance
- **Price Targets** — Target (with +% upside), Stop Loss (with -% risk), Risk:Reward ratio with quality badge (✅ Good ≥2:1 / ⚠️ Fair ≥1.5:1 / 🔴 Poor <1.5:1)
- **Warnings** — Alerts for extremes, circuit breakers, crossovers, and more

### ⚡ Momentum Tab (NEW in v3.0)

Deep momentum and volume analysis:

- **4 Info Cards** — Quick momentum overview:
  - **Momentum Status** — Strong Bullish/Bearish Momentum, Bullish/Bearish Acceleration, Decelerating, Neutral (based on ROC(14) + MACD histogram)
  - **Volume Profile** — Accumulation (Buying Pressure) / Distribution (Selling Pressure) / Neutral (based on price-volume relationship over 10 bars)
  - **BB Position** — Above Upper BB / Below Lower BB / Near Upper/Lower / Mid-Band (Bollinger Band %B interpretation)
  - **RSI Divergence** — Bullish Divergence / Bearish Divergence / None Detected (price vs RSI swing comparison)
- **Large RSI Gauge** — Visual RSI bar with color-coded zones (red=overbought, yellow=neutral, green=oversold) plus needle indicator and exact reading with zone label
- **Oscillator Details Grid** — StochRSI K/D (with OB/OS labels), Williams %R (with OB/OS), CCI(20), ROC(14) (with direction color), Volatility %
- **Volume Analysis Grid** — Volume Ratio (x avg), Avg Volume (20-bar), OBV Trend (Rising/Falling/Flat), Volume Profile

### 📈 Technical Tab

Deep dive into every indicator:

- **Oscillators Table** — RSI, StochRSI, Williams %R, CCI, ROC, MACD with individual Buy/Sell/Neutral signals
- **Moving Averages Table** — EMA(10/20/30/50), SMA(20/50/200) with individual signals
- **Trend & Bands Detail Grid** — expanded in v3.0:
  - Trend Direction (with icon and color)
  - ADX Strength (with numeric value + label)
  - **DI+** (Directional Indicator Plus — green) — measures upward pressure
  - **DI-** (Directional Indicator Minus — red) — measures downward pressure
  - MACD Line, Signal Line, Histogram (color-coded green/red)
  - ATR(14)
  - Bollinger Bands Upper/Middle/Lower (color-coded resistance/pivot/support)
  - BB %B (position within bands)
  - MA Crossover (Golden Cross / Death Cross with color)

### 🔄 Multi-TF Tab

Higher timeframe validation:

- Comparison table (Current / Higher-TF-1 / Higher-TF-2)
- RSI, MACD direction, Trend direction, Verdict per timeframe
- Alignment indicator: ✅ Fully Bullish Aligned / ⚠️ Partially Aligned / 🔴 Fully Bearish Aligned

### 🎯 Levels Tab (Enhanced in v3.0)

Key prices that act as walls:

- **Support / Resistance Table** — With header row (Level | Price | Distance) and exact % distance from current price for every S/R level
- **Breakout Status Banner** — Color-coded alert showing current breakout state (Bullish Breakout, Bearish Breakdown, Testing Resistance, BB Breakout, Near Zone, Range-Bound)
- **Fibonacci Retracement** (7 levels) — Near-price levels highlighted
- **Pivot Points** (Classic: PP, R1-R3, S1-S3)
- **52-Week Range** — Visual bar with current position marker, % from high AND % from low
- **Price Targets** (SL/Target/R:R)

### 🏛️ Market Tab (NEW in v3.0)

Institutional-grade market intelligence:

- **4 Market Intelligence Cards** — Each with value and explanatory hint:
  - **Market Phase** — Wyckoff-style detection: Markup (price rising, volume rising), Markdown (price falling), Accumulation (flat price, rising volume, low ADX), Distribution (flat price, falling volume), Consolidation
  - **Market Structure** — HH/HL Bullish (bullish swing structure) / LH/LL Bearish / Expanding Range / Contracting Squeeze / Transitioning
  - **Breakout Status** — Real-time breakout detection using S/R levels + Bollinger Bands + volume confirmation
  - **RSI Divergence** — Compares price swing lows/highs with RSI swing lows/highs over 20 bars
- **7-Point Buy/Sell Checklist** — Live pass/fail/neutral indicators:
  1. ✅/❌ Trend (UPTREND = pass, DOWNTREND = fail)
  2. ✅/⚠️ RSI in Safe Range (30-70)
  3. ✅/❌ MACD (Bullish = pass, Bearish = fail)
  4. ✅/⚠️ Volume Confirmation (≥1.0x avg = pass)
  5. ✅/❌ OBV (Rising = pass, Falling = fail)
  6. ✅/⚠️ ADX > 20 (Trending market)
  7. ✅/❌ R:R Ratio ≥ 2
- **Glossary** — 10 share market terms with definitions:
  - Breakout, Breakdown, Accumulation, Distribution, HH/HL, LH/LL, Golden Cross, Death Cross, Divergence, Confluence

---

## 4. How to Analyze: 1-Hour Market (Intraday)

**When to use:** You want to time your entry within the NEPSE trading session (11:00–15:05).

### Setup

1. Open chart → Set resolution to **1 hour**
2. Set range to **5d** or **1m** (gives you enough hourly bars)
3. Widget automatically shows Hourly analysis + resampled Daily + Weekly

### What to Look For

| Widget Element | Bullish (BUY) Signal              | Bearish (AVOID) Signal               |
| -------------- | --------------------------------- | ------------------------------------ |
| **Verdict**    | BUY or STRONG BUY                 | SELL or STRONG SELL                  |
| **RSI**        | 30–50 (momentum building)         | >70 (overbought for the hour)        |
| **MACD**       | Bullish (line above signal)       | Bearish                              |
| **Pattern**    | Hammer, Bullish Engulfing, Kicker | Shooting Star, Evening Star          |
| **Volume**     | Rising with price = genuine move  | Spike with flat price = trap         |
| **Multi-TF**   | Daily also BUY = high confidence  | Daily = SELL → this is a fake bounce |

### Expert Hourly Analysis Strategy

**NEPSE trades only ~4 hours per day.** Each hourly candle is significant:

| Hour       | Time        | Character                     | Expert Behavior                                                                                                                               |
| ---------- | ----------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hour 1** | 11:00–12:00 | Opening volatility, gap fills | **DO NOT BUY.** Wait for the noise to settle. Operators and institutions place large orders that create false signals.                        |
| **Hour 2** | 12:00–13:00 | Trend establishment           | If direction is clear (MACD Bullish + RSI rising from 40–50), this is the **safest entry window**.                                            |
| **Hour 3** | 13:00–14:00 | Momentum peak                 | Strongest volume usually here. If RSI > 65 on hourly, the move is getting old — don't chase.                                                  |
| **Hour 4** | 14:00–15:05 | End-of-day positioning        | Late buying = next-day confidence. Late selling = distribution. If widget shows BUY in hour 4 + high volume → **strong signal** for next day. |

### Hourly Indicator Priority

| Priority | Indicator    | Why It Matters on Hourly                                                                                  |
| -------- | ------------ | --------------------------------------------------------------------------------------------------------- |
| 1st      | **MACD**     | On hourly, MACD crossovers happen 1–2 times per day. A bullish crossover at hour 2 is highly reliable.    |
| 2nd      | **RSI**      | RSI 30–50 on hourly = room to run. RSI >65 = the move already happened.                                   |
| 3rd      | **Volume**   | Each hourly bar should have progressively more volume if the trend is real. Declining volume = fake move. |
| 4th      | **Patterns** | A Bullish Engulfing on the hourly chart at 12:00 after a morning dip = textbook entry.                    |

### Critical Rule

> **NEVER buy solely on an hourly signal.** Always confirm the **Daily chart** shows BUY or at least HOLD. Check the Multi-TF tab: if Daily = SELL but Hourly = BUY, it's a temporary bounce — you'll lose money.

---

## 5. How to Analyze: 1-Day Market (Swing Trading)

**When to use:** This is the **bread and butter** of NEPSE trading. Most profits come from holding 5–20 days.

### Setup

1. Open chart → Set resolution to **1 day** ⭐
2. Set range to **1y** (gives ~252 daily bars — enough for SMA200, all indicators)
3. Widget computes Daily + auto-resampled Weekly + Monthly

### The Complete Daily Analysis Checklist

**Step 1: Overview Tab — 10-second verdict**

- Verdict = BUY or STRONG BUY? → Proceed
- Confidence > 65%? → Good signal
- Both Oscillator + MA badge = Buy? → Strong confluence
- Status Cards: Breakout = Bullish? Structure = HH/HL? Phase = Markup or Accumulation?
- Nearest S/R Quick View: Support close (<2%) = good entry zone

**Step 2: Momentum Tab — 30-second momentum check** (NEW in v3.0)

| Check               | Bullish                                | Bearish                           |
| ------------------- | -------------------------------------- | --------------------------------- |
| **Momentum Status** | Bullish Acceleration or Strong Bullish | Decelerating or Bearish           |
| **Volume Profile**  | Accumulation                           | Distribution                      |
| **RSI Gauge**       | 35-55 with room to run                 | >70 overbought or <30 oversold    |
| **RSI Divergence**  | None or Bullish                        | Bearish Divergence = exit warning |
| **Volume Ratio**    | ≥1.0x (adequate participation)         | Spiking 3x+ on down day = selling |

**Step 3: Technical Tab — 2-minute deep dive**

| Check            | What to Confirm                                   | Red Flag (Skip the Trade)                          |
| ---------------- | ------------------------------------------------- | -------------------------------------------------- |
| **RSI(14)**      | 30–55 = ideal buy zone (coming out of oversold)   | >70 = don't buy, already overbought                |
| **StochRSI**     | K crossing above D from below 20 = perfect timing | K > 80 = too late                                  |
| **Williams %R**  | < −80 then rising = momentum turning              | > −20 = overbought                                 |
| **CCI(20)**      | Rising from below −100                            | > +100 falling = distribution                      |
| **ROC(14)**      | Positive and increasing                           | Negative and falling                               |
| **MACD**         | Line above Signal + Histogram turning green       | Line below Signal, histogram getting more negative |
| **All 7 MAs**    | Price above most = uptrend                        | Price below most = downtrend, don't buy            |
| **OBV Trend**    | Rising = smart money accumulating                 | Falling = distribution                             |
| **MA Crossover** | Golden Cross = long-term bullish                  | Death Cross = stay away                            |
| **DI+/DI-**      | DI+ > DI- = bullish pressure confirmed            | DI- > DI+ = bearish pressure dominating            |

**Step 4: Market Tab — 30-second intelligence check** (NEW in v3.0)

- Market Phase = Markup or Accumulation → Favorable conditions
- Market Structure = HH/HL Bullish → Trend intact
- Quick Checklist: Count ✅ marks → 5+ = proceed, <4 = skip

**Step 5: Multi-TF Tab — 1-minute macro check**

- Weekly verdict = BUY → You're aligned with the medium trend → **High confidence**
- Monthly verdict = BUY → The stock is in a macro bull cycle → **Highest confidence**
- ✅ Fully Aligned → This is the best trade on your watchlist

**Step 4: Levels Tab — 30-second price check**

- Current price near S1/S2 (Support) → Buying at a floor → **Great entry**
- Current price near R1/R2 (Resistance) → Buying near a ceiling → **Limited upside, skip**
- Fibonacci: Near 38.2% or 61.8% retracement → Classic bounce zone
- 52-Week Range: Near bottom quarter → **Value zone**; Near top = chasing

### Expert Daily Interpretation

**The "Perfect Daily Setup" (when all align):**

```
✅ Verdict: BUY (75%+)
✅ RSI: 35–50 (coming out of oversold, room to run)
✅ MACD: Just crossed bullish (histogram turned green from red)
✅ Trend: UPTREND (EMA10 > EMA30, ADX > 20)
✅ Pattern: Morning Star or Bullish Engulfing or Three Inside Up
✅ Volume: Normal or slightly above average
✅ Weekly: BUY
✅ Monthly: BUY or HOLD
✅ Price near Support or Fib 38.2%/61.8%
✅ OBV: Rising
✅ Market Phase: Accumulation or Markup (check Market tab)
✅ Momentum Status: Bullish (check Momentum tab)
✅ Market Structure: HH/HL Bullish (check Market tab)
```

**If you see 10+ of these 13 checkmarks → This is a high-probability trade.** Risk 2–3% of your portfolio.

### How Long to Hold (Daily Charts)

| Signal     | Hold Duration | Exit Trigger                             |
| ---------- | ------------- | ---------------------------------------- |
| STRONG BUY | 10–20 days    | Target hit or Evening Star on daily      |
| BUY        | 5–10 days     | Target hit, RSI > 70, or bearish pattern |
| HOLD       | 0 days        | Don't enter; re-evaluate in 2 days       |

---

## 6. How to Analyze: 1-Month Market (Position Trading)

**When to use:** You want to hold a stock for 1–3 months. You're looking for $stocks in a clear trend and riding the wave.

### Setup

1. Set resolution to **1 week** (gives ~52 weekly bars per year)
2. Set range to **1y** or **3m**
3. Widget computes Weekly + auto-resampled Monthly + Quarterly

OR:

1. Set resolution to **1 day**, range to **1m**
2. Look at only the last 22 bars (1 trading month)

### What Monthly Analysis Tells You

| Widget Element   | Bullish Monthly Signal                 | Bearish Monthly Signal                 |
| ---------------- | -------------------------------------- | -------------------------------------- |
| **Weekly Trend** | UPTREND for 4+ weeks                   | DOWNTREND for 4+ weeks                 |
| **Monthly RSI**  | 40–60 (healthy trend, not overheated)  | >75 (monthly overbought = major top)   |
| **SMA(50)**      | Price above SMA50                      | Price below SMA50                      |
| **SMA(200)**     | Price above SMA200 = bull market stock | Price below SMA200 = bear market stock |
| **MACD Monthly** | Bullish                                | Bearish                                |
| **Golden Cross** | SMA50 just crossed above SMA200        | Death Cross = exit                     |

### Expert Monthly Rules

1. **The SMA200 Rule:** If a stock is below its SMA(200) on the daily chart, it is in a **bear market**. Do not buy for position trades regardless of other signals. Wait for price to reclaim SMA200.

2. **Monthly RSI Sweet Spot:** The best 1-month trades start when monthly RSI is 40–55 and rising. This means the stock just came out of a correction and has a full 15–30 points of RSI room to run.

3. **Volume Trend:** Over 4 weeks, volume should be gradually increasing on up-days and decreasing on down-days. The OBV should be Rising.

4. **Fibonacci for Position Entry:** After a stock pulls back from a 1-month high, enter at the 38.2% or 50% Fibonacci retracement level. This is where institutions typically re-enter.

---

## 7. How to Analyze: 3-Month Market (Trend Following)

**When to use:** You're identifying which stocks are in the strongest trends over a quarter.

### Setup

1. Set resolution to **1 week**, range to **6m** or **1y**
2. You get ~26–52 weekly bars — perfect for trend analysis
3. Widget multi-TF shows Monthly + Quarterly analysis

### The 3-Month Trend Framework

| Phase               | RSI Range       | EMA State                                    | Volume                   | Widget Shows          | Action                         |
| ------------------- | --------------- | -------------------------------------------- | ------------------------ | --------------------- | ------------------------------ |
| **Accumulation**    | 30–45           | EMA10 below EMA30 but flattening             | Low but increasing       | HOLD / early BUY      | Start watching; prepare to buy |
| **Mark-Up (Early)** | 45–55           | EMA10 just crossed above EMA30               | Increasing               | BUY 65%+              | **BEST ENTRY POINT**           |
| **Mark-Up (Mid)**   | 55–65           | EMA10 well above EMA30, both rising          | Consistently high        | BUY / STRONG BUY      | Still safe to buy, trail stop  |
| **Distribution**    | 65–80           | EMA10 flattening while price makes new highs | Very high then declining | BUY → HOLD transition | **START TAKING PROFIT**        |
| **Mark-Down**       | <50 and falling | EMA10 below EMA30                            | Declining                | SELL / STRONG SELL    | Exit all positions             |

### Expert 3-Month Analysis

**The Quarterly Sector Rotation:**
Every 3 months, money flows between NEPSE sectors. Use the widget on multiple sector leaders:

1. Analyze 5+ stocks from different sectors (Banking: NABIL, NICA; Hydro: BPCL, API; Insurance: NLIC; Manufacturing: UNL)
2. Which sectors show the most BUY signals with Weekly + Monthly alignment?
3. That sector is leading the current quarter — focus your capital there
4. Sectors showing SELL + falling RSI = money is leaving → avoid

### Key Indicators for 3-Month View

| Indicator            | Bullish (Entering Trend)                          | Bearish (Trend Ending)                            |
| -------------------- | ------------------------------------------------- | ------------------------------------------------- |
| **ADX**              | Rising from 15 → 25+                              | Falling from 30+ → below 20                       |
| **MACD Histogram**   | Getting taller (green) for 3+ weeks               | Getting shorter or turning red                    |
| **SMA50 vs SMA200**  | SMA50 rising toward SMA200 (pending Golden Cross) | SMA50 falling toward SMA200 (pending Death Cross) |
| **Fibonacci**        | Price bouncing from 61.8% of 3-month range        | Price breaking below 61.8%                        |
| **52-Week Position** | In bottom 25–50% of range = value                 | In top 10% = exhaustion risk                      |

---

## 8. How to Analyze: 6-Month Market (Sector Rotation)

**When to use:** Strategic capital allocation. Which sectors and stocks deserve your money for the next half-year?

### Setup

1. Set resolution to **1 week**, range to **1y** (52 weekly bars)
2. Or set resolution to **1 month**, range to **1y** or **5y**
3. Widget shows Monthly + Quarterly context

### The 6-Month Strategic Framework

Over 6 months, you're not looking at individual candles — you're looking at the **shape of the trend**:

| Chart Shape                    | What It Means                 | Widget Signature                       | Action                                    |
| ------------------------------ | ----------------------------- | -------------------------------------- | ----------------------------------------- |
| **Higher highs + Higher lows** | Healthy uptrend               | BUY, RSI 45–65, EMA10>EMA30            | Accumulate on pullbacks                   |
| **Flat channel (range-bound)** | Consolidation before breakout | HOLD, RSI 40–60, ADX <20               | Wait for breakout direction               |
| **Lower highs + Lower lows**   | Downtrend                     | SELL, RSI <45 falling, EMA10<EMA30     | Do not buy, wait 3+ months                |
| **V-shaped bounce**            | Panic selling → recovery      | BUY, RSI rapidly rising from <30       | Enter after confirmation (2nd higher low) |
| **Rounding bottom**            | Long-term reversal forming    | HOLD→BUY transition, RSI slowly rising | Best long-term entry zone                 |

### Expert 6-Month Indicators

**What matters most on 6-month horizon:**

1. **SMA200** — This is the single most important line. Stocks above SMA200 are in bull territory. Below = bear territory. In 6-month analysis, only buy stocks that have been above SMA200 for 3+ months.

2. **Monthly RSI Divergence** — If price makes new 6-month lows but RSI makes higher lows → **Bullish divergence** = the stock is about to reverse upward. This is one of the most powerful signals in technical analysis.

3. **Volume Profile** — Look at the OBV trend over 6 months. If OBV is steadily rising while price has been flat → Smart money is quietly accumulating. When the stock breaks out, it will be powerful.

4. **Fibonacci from 6-Month Range** — Calculate Fibonacci from the 6-month high to 6-month low. If price is sitting at the 38.2% or 50% level → ideal re-entry.

### NEPSE 6-Month Calendar Strategy

| Period              | NEPSE Character                                       | Widget Use                                           |
| ------------------- | ----------------------------------------------------- | ---------------------------------------------------- |
| **Mid-July – Sept** | Q1 results season, dividend announcements             | Screen for stocks showing BUY right before results   |
| **Oct – Dec**       | Post-dividend correction → value opportunities        | Look for RSI < 40 on good companies with HOLD/BUY    |
| **Jan – March**     | Q2 results, fiscal year-end positioning               | Banks/finance show strength — check sector alignment |
| **April – July**    | Tax-loss selling → year-end pressure → new year rally | Best 6-month buying window; look for STRONG BUY      |

---

## 9. How to Analyze: 1-Year Market (Investor Grade)

**When to use:** You're making investment decisions, not trading decisions. Holding 6–18 months.

### Setup

1. Set resolution to **1 week**, range to **5y** (gives ~260 weekly bars)
2. Or set resolution to **1 month**, range to **5y** (gives 60 monthly bars)
3. Widget shows Quarterly + Yearly analysis

### The Annual Analysis Framework

| Question                    | Where to Look                    | Bullish Answer                       | Bearish Answer      |
| --------------------------- | -------------------------------- | ------------------------------------ | ------------------- |
| Is the stock above SMA200?  | Technical Tab → MA table         | ✅ Price > SMA200                    | ❌ Price < SMA200   |
| Is the macro trend up?      | Multi-TF Tab → Quarterly verdict | Quarterly = BUY or HOLD              | Quarterly = SELL    |
| Where in the 52-week range? | Levels Tab → 52-Week bar         | Bottom 40% (value)                   | Top 15% (risky)     |
| Is there a Golden Cross?    | Warnings section                 | ✨ Golden Cross = bullish year ahead | 💀 Death Cross      |
| Is volume confirming?       | Technical Tab → OBV Trend        | Rising OBV                           | Flat/Falling OBV    |
| Are institutions buying?    | Overview → Operator Activity     | Volume spike + BUY = accumulation    | Volume spike + SELL |

### Expert Annual Cycle Analysis

**The 4 Phases of a Stock's Annual Cycle:**

```
Phase 1: BASE (2–4 months)
├── RSI: 30–45, sideways
├── ADX: < 20 (no trend)
├── Volume: Low
├── Widget: HOLD (45–55% confidence)
└── Action: Add to watchlist, DO NOT BUY YET

Phase 2: ADVANCE (2–4 months)
├── RSI: 45–65, rising
├── ADX: Rising above 20 → 30+
├── Volume: Increasing on up-days
├── Widget: BUY → STRONG BUY (65–85%)
├── Golden Cross may appear
└── Action: ★★★ PRIMARY BUY ZONE ★★★

Phase 3: TOP (1–3 months)
├── RSI: 65–80, flattening
├── ADX: > 30 but declining
├── Volume: High but erratic
├── Widget: BUY → HOLD transition
├── Bearish patterns start appearing (Evening Star, Dark Cloud)
└── Action: TAKE PROFIT, move SL to breakeven

Phase 4: DECLINE (2–4 months)
├── RSI: < 50, falling
├── ADX: Still > 20 (strong downtrend)
├── Volume: Spikes on down-days
├── Widget: SELL → STRONG SELL (65–90%)
├── Death Cross may appear
└── Action: DO NOT BUY. Wait for Phase 1 to form again.
```

### The Annual SMA200 Strategy (Most Reliable)

This single strategy beats most NEPSE traders:

1. **Buy** when price crosses above SMA200 and stays above for 5 consecutive daily bars
2. Widget confirms: Golden Cross warning + BUY verdict + Weekly BUY
3. **Hold** as long as price is above SMA200
4. **Sell** when price crosses below SMA200 and stays below for 5 bars
5. Widget confirms: Death Cross warning + SELL verdict

This avoids the major declines and captures the major rallies. It trades 1–3 times per year per stock.

---

## 10. How to Analyze: 5-Year Market (Wealth Building)

**When to use:** You're building a long-term portfolio. Selecting stocks to hold for years.

### Setup

1. Set resolution to **1 month**, range to **5y** (60 monthly bars)
2. Or set resolution to **3 months** or **6 months**, range to **5y**
3. Widget shows overview of the macro cycle

### What 5-Year Analysis Reveals

On a 5-year chart, you're looking at the **mega-trend** — the overall direction of a company's stock price over its recent history. This is not about timing; it's about selection.

| 5-Year Pattern                  | Meaning                       | Investment Decision                                            |
| ------------------------------- | ----------------------------- | -------------------------------------------------------------- |
| **Steady upward slope**         | Consistently growing business | ✅ Core portfolio holding — invest on any significant pullback |
| **Flat with occasional spikes** | No real growth, speculative   | ⚠️ Trading stock only — not for long-term                      |
| **Gradual decline**             | Business deteriorating        | ❌ Do not invest regardless of current BUY signal              |
| **Sharp decline then recovery** | Crisis/recovery cycle         | ✅ If fundamentals are fixed, the recovery is the opportunity  |
| **Explosive growth then flat**  | Growth phase is over          | ⚠️ Only if new growth catalyst exists                          |

### Expert 5-Year Analysis Rules

1. **The "Higher Year-Over-Year" Rule:** Each year's high should be higher than the previous year's high, and each year's low should be higher than the previous year's low. If both are true → the stock is in a **SECULAR UPTREND**. These are the safest investments.

2. **Historic Support Zones:** On a 5-year chart, the Fibonacci levels in the Levels tab show the most important support/resistance of the stock's entire recent history. The 61.8% retracement of a 5-year rally is where institutions will aggressively buy.

3. **5-Year RSI:** If the monthly RSI drops below 30 on a stock that has been in a 5-year uptrend, this is a **generational buying opportunity**. It means the long-term trend is intact but the stock had a temporary panic. Examples: Post-COVID crash, post-earthquake recovery.

4. **Volume Tells the Story:** On a 5-year chart with monthly candles, look for gradually increasing volume over the years = growing market interest in the stock. Decreasing volume over years = the stock is being abandoned.

---

## 11. Multi-Timeframe Confluence — The Master Skill

> **This is the single most important section of this guide.** If you learn only one thing, learn this. Multi-timeframe confluence is what separates profitable traders from everyone else.

### The Principle

**Higher timeframes overrule lower timeframes.**

- If the monthly chart says SELL, a daily BUY is just noise.
- If the weekly chart says BUY and the daily says BUY, the probability doubles.
- If monthly + weekly + daily all say BUY, you have a maximum-confidence setup.

### Confluence Decision Matrix

| Monthly | Weekly | Daily | Action                                              | Confidence |
| ------- | ------ | ----- | --------------------------------------------------- | ---------- |
| BUY     | BUY    | BUY   | ✅ **MAXIMUM BUY** — Full position, widest stop     | 90%+       |
| BUY     | BUY    | HOLD  | ✅ Buy on next daily BUY signal (wait 1–3 days)     | 80%        |
| BUY     | BUY    | SELL  | ⚠️ Wait — daily is pulling back within a bull trend | Wait       |
| BUY     | HOLD   | BUY   | ✅ Buy with half position                           | 70%        |
| BUY     | SELL   | BUY   | ❌ Skip — weekly divergence is dangerous            | Skip       |
| HOLD    | BUY    | BUY   | ✅ Buy with normal position                         | 75%        |
| HOLD    | HOLD   | BUY   | ⚠️ Scalp only — no trend backing the move           | 50%        |
| SELL    | BUY    | BUY   | ❌ **DO NOT BUY** — you're fighting the macro trend | 0%         |
| SELL    | SELL   | BUY   | ❌ **DANGEROUS** — this is a bear market bounce     | 0%         |
| SELL    | SELL   | SELL  | 🔴 **MAXIMUM SELL** — exit immediately              | 95%        |

### How to Read the Widget's Multi-TF Tab

1. Open chart with **1D resolution**, **1Y range**
2. Click the **🔄 Multi-TF** tab
3. Read the three rows: Current (Daily) / Weekly / Monthly
4. Look for:
   - **✅ Fully Bullish Aligned** → All green → Highest confidence BUY
   - **⚠️ Partially Aligned** → Mixed → Trade cautiously or wait
   - **🔴 Fully Bearish Aligned** → All red → DO NOT BUY

### Real-World NEPSE Example

Suppose you're analyzing NABIL:

```
Current (Daily):  RSI 42  |  MACD ▲  |  Trend ▲  |  BUY
Weekly:           RSI 48  |  MACD ▲  |  Trend ▲  |  BUY
Monthly:          RSI 55  |  MACD ▲  |  Trend →  |  HOLD
Alignment: ⚠️ Partially Aligned
```

**Expert interpretation:** Daily + Weekly agree on BUY (strong), but Monthly is HOLD (neutral). This means the stock is in an uptrend that started recently (weekly) but the bigger monthly cycle hasn't fully confirmed. **Action:** Buy with normal position size, but use the widget's suggested stop loss strictly.

---

## 12. The Complete Buying Decision Framework

### The 7-Point Buy Checklist

Before buying ANY stock, check all 7 points. Score each ✅ or ❌:

| #   | Check                   | Where         | Criteria                                       |
| --- | ----------------------- | ------------- | ---------------------------------------------- |
| 1   | **Verdict**             | Overview Tab  | BUY or STRONG BUY                              |
| 2   | **Multi-TF Alignment**  | Multi-TF Tab  | At least 2 of 3 timeframes = BUY               |
| 3   | **RSI Position**        | Technical Tab | RSI 30–55 (room to run upward)                 |
| 4   | **Trend Confirmation**  | Technical Tab | UPTREND (EMA10>EMA30, ADX>20)                  |
| 5   | **Price at Support**    | Levels Tab    | Near S1/S2, or Fibonacci 38.2%/61.8%           |
| 6   | **Volume Confirmation** | Technical Tab | OBV Rising + no operator anomaly               |
| 7   | **No Red Flags**        | Warnings      | No Death Cross, no RSI 80+, no circuit breaker |

**Scoring:**

- 7/7 ✅ → **STRONG BUY** — 3% of portfolio
- 5–6/7 ✅ → **BUY** — 2% of portfolio
- 4/7 ✅ → **Small position** — 1% of portfolio
- 3 or less → **DO NOT BUY** — add to watchlist only

### Entry Timing After Confirmation

Once the daily chart passes the 7-point check:

1. Switch to **1 hour** resolution
2. Wait for an hourly bullish pattern (Hammer, Engulfing, Kicker) during Hour 2 or 3
3. Enter at the close of that hourly candle or next bar open
4. Set stop loss = the widget's suggested SL from the daily chart

### Position Sizing Formula

```
Risk per trade = Portfolio × 0.02 (2%)
Risk per share = Entry Price − Stop Loss
Position size  = Risk per trade / Risk per share

Example:
  Portfolio = Rs. 300,000
  Entry = Rs. 750
  SL = Rs. 720 (from widget)

  Risk per trade = 300,000 × 0.02 = Rs. 6,000
  Risk per share = 750 − 720 = Rs. 30
  Position = 6,000 / 30 = 200 shares (Rs. 150,000)
```

### Exit Rules

| Condition                                  | Action                                     |
| ------------------------------------------ | ------------------------------------------ |
| Target price hit                           | Sell 70%, trail stop on remaining 30%      |
| Daily widget changes to SELL               | Exit full position at next open            |
| Evening Star or Three Black Crows on daily | Exit immediately                           |
| RSI > 75 on daily + weekly                 | Take profit — overbought on two timeframes |
| Stop Loss hit                              | Exit 100%, no exceptions                   |
| 20 trading days with no progress           | Exit — opportunity cost, capital is stuck  |

---

## 13. All 27 Candlestick Patterns — Expert Guide

Each pattern has a **strength rating** — higher = more reliable signal:

| Strength | Meaning          | Action Level              |
| -------- | ---------------- | ------------------------- |
| ±100     | Basic signal     | Use as confirmation only  |
| ±150     | Moderate signal  | Act with other confluence |
| ±200     | Strong signal    | High-probability setup    |
| ±250     | Rarest/strongest | Near-certain reversal     |

### Single-Bar Patterns

| Pattern               | Dir       | Str  | Expert Usage                                                                                         |
| --------------------- | --------- | ---- | ---------------------------------------------------------------------------------------------------- |
| **Doji**              | Neutral   | ±100 | Indecision. After 5+ up bars = bearish. After 5+ down bars = bullish. Always wait for confirmation.  |
| **Dragonfly Doji**    | Bullish   | +150 | Long lower wick, close at high. Buyers completely rejected the lows. At support → strong buy.        |
| **Gravestone Doji**   | Bearish   | -150 | Long upper wick, close at low. Sellers completely rejected the highs. At resistance → exit.          |
| **Marubozu**          | Bull/Bear | ±200 | Full body candlestick with no wicks. Strongest single-bar signal. Bullish Marubozu = momentum entry. |
| **Spinning Top**      | Neutral   | ±100 | Small body, both wicks. Indecision at current level. Wait for direction.                             |
| **Hammer**            | Bullish   | +100 | Long lower wick after downtrend. Buyers rejected lower prices. Enter on next bar if it opens higher. |
| **Hanging Man**       | Bearish   | -100 | Same shape as Hammer but after uptrend. Warning sign — tighten stop.                                 |
| **Shooting Star**     | Bearish   | -100 | Long upper wick after uptrend. Price rejected at highs. Begin exit.                                  |
| **Inverted Hammer**   | Bullish   | +100 | Long upper wick after downtrend. Buyers attempting takeover. Confirm with next bar.                  |
| **Bullish Belt Hold** | Bullish   | +150 | Opens at low, closes near high, no lower wick. Aggressive institutional buying.                      |
| **Bearish Belt Hold** | Bearish   | -150 | Opens at high, closes near low. Institutional selling.                                               |

### Two-Bar Patterns

| Pattern                   | Dir     | Str  | Expert Usage                                                                                      |
| ------------------------- | ------- | ---- | ------------------------------------------------------------------------------------------------- |
| **Bullish Engulfing**     | Bullish | +200 | Large bull bar engulfs prior bear bar. Classic reversal. Enter immediately if at support.         |
| **Bearish Engulfing**     | Bearish | -200 | Large bear bar engulfs prior bull bar. Exit signal — sells often follow strongly.                 |
| **Bullish Harami**        | Bullish | +100 | Small bullish inside large bearish. Momentum slowing — potential reversal. Wait for confirmation. |
| **Bearish Harami**        | Bearish | -100 | Small bearish inside large bullish. Trend losing steam.                                           |
| **Piercing Line**         | Bullish | +100 | Opens below prior low, closes above midpoint. Partial recovery — moderate buy.                    |
| **Dark Cloud Cover**      | Bearish | -100 | Opens above prior high, closes below midpoint. Distribution starting.                             |
| **Tweezer Bottom**        | Bullish | +150 | Two bars share exact same low. Double rejection at a support = very strong support level.         |
| **Tweezer Top**           | Bearish | -150 | Two bars share exact same high. Double rejection at resistance.                                   |
| **Bullish Kicker**        | Bullish | +200 | Bearish bar → gap UP opening above prior open. Institutional buying. Enter immediately.           |
| **Bearish Kicker**        | Bearish | -200 | Bullish bar → gap DOWN below prior open. Powerful exit signal.                                    |
| **Bullish Counterattack** | Bullish | +150 | Bear bar gaps lower but rallies to close at same level. Buyers defending.                         |
| **Bearish Counterattack** | Bearish | -150 | Bull bar gaps higher but closes at same level. Sellers defending.                                 |
| **Rising Window**         | Bullish | +150 | Gap up (bar low > prior bar high). Gaps act as support.                                           |
| **Falling Window**        | Bearish | -150 | Gap down (bar high < prior bar low). Gaps act as resistance.                                      |

### Three-Bar Patterns

| Pattern                   | Dir     | Str  | Expert Usage                                                                            |
| ------------------------- | ------- | ---- | --------------------------------------------------------------------------------------- |
| **Morning Star**          | Bullish | +200 | Bear → Star → Bull. Classic bottom. One of the most reliable buy signals in any market. |
| **Evening Star**          | Bearish | -200 | Bull → Star → Bear. Classic top. Exit immediately when this appears on daily.           |
| **Three White Soldiers**  | Bullish | +200 | Three consecutive large bull bars. Unstoppable momentum. Enter early in the move.       |
| **Three Black Crows**     | Bearish | -200 | Three consecutive large bear bars. Do not fight this — exit and wait.                   |
| **Three Inside Up**       | Bullish | +200 | Bear → harami → confirmation above. Most reliable 3-bar reversal.                       |
| **Three Inside Down**     | Bearish | -200 | Bull → harami → confirmation below. Strong top signal.                                  |
| **Upside Tasuki Gap**     | Bullish | +150 | Gap up → pullback fails to close gap. Gap = support, trend continues.                   |
| **Downside Tasuki Gap**   | Bearish | -150 | Gap down → bounce fails to close gap. Trend continues down.                             |
| **Abandoned Baby (Bull)** | Bullish | +250 | Bear → gapped doji → gap up bull. RAREST signal. Near-certain bottom. All-in buy.       |
| **Abandoned Baby (Bear)** | Bearish | -250 | Bull → gapped doji → gap down bear. Strongest top signal. Immediate exit.               |

### Top 10 Buy Patterns (Ranked)

| Rank | Pattern                        | When to Act                             |
| ---- | ------------------------------ | --------------------------------------- |
| 1    | **Abandoned Baby (Bull)** +250 | Buy immediately at next open            |
| 2    | **Three Inside Up** +200       | Buy at close of 3rd bar                 |
| 3    | **Morning Star** +200          | Buy at close of 3rd bar                 |
| 4    | **Bullish Kicker** +200        | Buy immediately — institutional signal  |
| 5    | **Bullish Engulfing** +200     | Buy at close or next open               |
| 6    | **Three White Soldiers** +200  | Enter if not already in                 |
| 7    | **Tweezer Bottom** +150        | Buy — double rejection confirms support |
| 8    | **Dragonfly Doji** +150        | Buy if at key support level             |
| 9    | **Bullish Belt Hold** +150     | Buy — aggressive institutional demand   |
| 10   | **Rising Window** +150         | Buy on gap — hold as long as gap holds  |

---

## 14. All Technical Indicators — How Experts Read Them

### Oscillators (Momentum)

| Indicator           | Range     | Buy Zone          | Sell Zone          | Expert Reading                                                                                                                                                                              |
| ------------------- | --------- | ----------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **RSI(14)**         | 0–100     | <30 → oversold    | >70 → overbought   | The most important oscillator. When RSI crosses 50 from below = bullish momentum confirmed. When it diverges from price (price makes new low but RSI doesn't) = powerful reversal signal.   |
| **StochRSI K/D**    | 0–100     | K < 20            | K > 80             | Faster than RSI. K crossing above D from oversold = early buy signal. But more false signals than RSI.                                                                                      |
| **Williams %R(14)** | -100 to 0 | < -80             | > -20              | Similar to StochRSI but inverted. Professional traders watch for %R to leave the -80 zone (start rising) = buy.                                                                             |
| **CCI(20)**         | Unbounded | < -100            | > 100              | Measures deviation from average price. Below -100 then turning up = entering from extreme weakness. The further below -200 and recovering → the more powerful the reversal.                 |
| **ROC(14)**         | Unbounded | Positive & rising | Negative & falling | Rate of Change — pure momentum. When ROC crosses zero from below → bullish momentum just started.                                                                                           |
| **MACD**            | Unbounded | Line > Signal     | Line < Signal      | MACD = EMA12 − EMA26. Signal = EMA9 of MACD. Histogram = MACD − Signal. **Histogram direction is more important than line position.** When histogram turns from negative to positive → buy. |

### Moving Averages (Trend)

| MA           | What It Shows          | Expert Use                                                                                                                        |
| ------------ | ---------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **EMA(10)**  | Last 2-week sentiment  | Fastest MA. Price above = short-term bullish.                                                                                     |
| **EMA(20)**  | Last 1-month trend     | Swing trading anchor. Buy when price bounces off EMA20.                                                                           |
| **EMA(30)**  | Last 6-week trend      | Crossover with EMA10 defines the trend direction.                                                                                 |
| **EMA(50)**  | Last 2.5-month trend   | Institutional reference line.                                                                                                     |
| **SMA(20)**  | Last 1-month average   | Bollinger Band center. Price below = short-term weakness.                                                                         |
| **SMA(50)**  | Last 2.5-month average | **Key institutional level.** Golden/Death Cross component.                                                                        |
| **SMA(200)** | Last 10-month average  | **THE most important line in trading.** Above = bull market. Below = bear market. Institutions make decisions based on this line. |

### Trend Indicators

| Indicator        | Expert Reading                                                                                                                                                                                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **ADX(14)**      | ADX < 20 = no trend (range-bound) → trade S/R, not momentum. ADX 20–30 = developing trend → enter with the EMA direction. ADX > 30 = strong trend → ride it. ADX > 45 = trend exhaustion likely.                                                                               |
| **DI+ / DI-**    | Directional Indicators (NEW in v3.0). DI+ measures upward pressure, DI- measures downward pressure. DI+ > DI- = bullish. DI- > DI+ = bearish. Combined with ADX > 20 = confirmed trend. Visible in Technical Tab → Trend & Bands.                                              |
| **OBV Trend**    | On-Balance Volume. If OBV is rising while price is flat → Accumulation (smart money buying before price moves). If OBV is falling while price rises → Distribution (insiders selling into strength). OBV divergence from price is one of the most powerful predictive signals. |
| **Bollinger %B** | Below 0 = price is below lower band (extreme oversold). Above 1 = above upper band (extreme overbought). **Bollinger Band squeeze** (bands narrowing) → volatility contraction → breakout imminent. Widget's ATR squeeze warning catches this.                                 |
| **MA Crossover** | Golden Cross (SMA50 above SMA200) = buy. Death Cross = sell. These are lagging but extremely reliable on NEPSE daily charts.                                                                                                                                                   |

---

## 15. Support, Resistance & Key Levels — Pro Usage

### Support & Resistance

Computed from swing highs and lows over 50 bars:

- **Resistance (R1, R2, R3)** — Price has been rejected here before. Sellers are waiting.
- **Support (S1, S2, S3)** — Price bounced here before. Buyers are waiting.
- **Distance %** (NEW in v3.0) — Each S/R level now shows how far it is from the current price as a percentage. This helps you instantly gauge how close you are to key levels.

**Pro strategy:** Buy near S1/S2 when daily verdict = BUY. Target = R1. Stop = just below S2. Check the % distance — if nearest support is <2% away, you're in a great entry zone.

> **Nearest S/R Quick View** (Overview tab): Shows the single closest support and resistance with exact % distance — use this for instant buy/sell decisions without switching to the Levels tab.

### Fibonacci Retracement

| Level     | Pro Meaning                                                                                                                        |
| --------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **23.6%** | Shallow pullback, strong trend. Aggressive entry.                                                                                  |
| **38.2%** | Most common retracement in strong trends. **Primary buy zone.**                                                                    |
| **50.0%** | Psychological midpoint. Good entry in moderate trends.                                                                             |
| **61.8%** | The "Golden Ratio." **Strongest retracement level.** If price holds here → trend continues. If it breaks → trend may be reversing. |
| **78.6%** | Deep retracement. Trend is weak. Only buy with very strong volume confirmation.                                                    |

### Pivot Points (Classic)

- **PP** = (High + Low + Close) / 3
- Institutional traders use pivot points for intraday and daily targets.
- **Buy rule:** Buy near S1 or S2, target PP or R1.
- **Sell rule:** Sell near R1 or R2, target PP or S1.
- If price breaks R3 or S3 → expect a major directional day.

### 52-Week Range

- **Bottom 20%** → Deep value territory. If fundamentals are good → buy heavily.
- **20–50%** → Fair value zone. Buy on technical signals.
- **50–80%** → Above average. Only buy with strong trend confirmation.
- **Top 20%** → Expensive. Only buy with ALL timeframes BUY + momentum.
- **New 52-week high** → Breakout. If volume is high → can run further.

---

## 16. The Scoring System

| Factor                     | Condition                 | Points      |
| -------------------------- | ------------------------- | ----------- |
| **RSI**                    | < 30                      | +3          |
| **RSI**                    | 30–40                     | +1          |
| **RSI**                    | 60–70                     | −1          |
| **RSI**                    | > 70                      | −3          |
| **Trend**                  | UPTREND                   | +2          |
| **Trend**                  | DOWNTREND                 | −2          |
| **MACD**                   | Bullish                   | +1          |
| **MACD**                   | Bearish                   | −1          |
| **BB %B**                  | < 0                       | +2          |
| **BB %B**                  | 0–0.2                     | +1          |
| **BB %B**                  | 0.8–1.0                   | −1          |
| **BB %B**                  | > 1.0                     | −2          |
| **Patterns**               | Each bullish (latest bar) | +1 (max +3) |
| **Patterns**               | Each bearish (latest bar) | −1 (max −3) |
| **Strong pattern (200+)**  | Bullish/Bearish           | +1/−1 extra |
| **Volume spike + bullish** | Operators buying          | +1          |
| **Volume spike + bearish** | Operators selling         | −2          |
| **StochRSI**               | K > D & K < 30            | +1          |
| **StochRSI**               | K < D & K > 70            | −1          |
| **Williams %R**            | < −80                     | +1          |
| **Williams %R**            | > −20                     | −1          |
| **CCI**                    | < −100                    | +1          |
| **CCI**                    | > 100                     | −1          |
| **Multi-TF**               | All TFs bullish           | +2          |
| **Multi-TF**               | All TFs bearish           | −2          |
| **Multi-TF**               | More bullish than bearish | +1          |
| **Multi-TF**               | More bearish than bullish | −1          |

**Score → Verdict:**

```
≥ 7   →  STRONG BUY   (70–95% confidence)
4–6   →  BUY          (55–85% confidence)
1–3   →  HOLD         (40–60% confidence)
-3–0  →  SELL         (40–75% confidence)
≤ -4  →  STRONG SELL  (70–95% confidence)
```

---

## 17. New v3.0 Features — Complete Reference

### 15 New Analysis Fields

v3.0 added these backend analysis fields that power the new tabs:

| Field                     | What It Shows                                                  | Where Visible                   | How to Use It                                                                    |
| ------------------------- | -------------------------------------------------------------- | ------------------------------- | -------------------------------------------------------------------------------- |
| **DI+**                   | Directional Indicator Plus — measures upward price pressure    | Technical Tab → Trend & Bands   | DI+ > DI- = bullish pressure. DI+ < DI- = bearish pressure                       |
| **DI-**                   | Directional Indicator Minus — measures downward price pressure | Technical Tab → Trend & Bands   | Together with ADX: ADX>20 + DI+>DI- = confirmed uptrend                          |
| **Breakout Status**       | Whether price is breaking through key levels                   | Overview + Levels + Market Tabs | Bullish Breakout = strong buy. Bearish Breakdown = exit. Testing = watch closely |
| **Market Structure**      | Swing high/low pattern (HH/HL vs LH/LL)                        | Overview + Market Tabs          | HH/HL = trend intact. LH/LL = trend broken. Expanding/Contracting = phase change |
| **Momentum Status**       | Combined ROC + MACD histogram momentum                         | Overview + Momentum Tabs        | Strong Bullish = ride the wave. Decelerating = prepare to exit                   |
| **Volume Profile**        | Accumulation vs Distribution classification                    | Momentum + Market Tabs          | Accumulation + BUY = institutions loading up. Distribution + SELL = get out      |
| **BB Position**           | Price location within Bollinger Bands                          | Momentum Tab                    | Above Upper = overbought risk. Below Lower = oversold opportunity                |
| **RSI Divergence**        | Price vs RSI direction mismatch                                | Momentum + Market Tabs          | Bullish Divergence = reversal up coming. Bearish Divergence = decline ahead      |
| **Market Phase**          | Wyckoff cycle phase                                            | Overview + Market Tabs          | Accumulation→Markup = BUY. Distribution→Markdown = SELL                          |
| **Nearest Support**       | Closest support level below current price                      | Overview Tab → S/R Quick View   | How far you could fall — tighter = safer entry                                   |
| **Nearest Resistance**    | Closest resistance level above current price                   | Overview Tab → S/R Quick View   | Your first profit target — or obstacle                                           |
| **Support Distance %**    | % distance to nearest support                                  | Overview Tab → S/R Quick View   | <2% = very near support = good buy zone                                          |
| **Resistance Distance %** | % distance to nearest resistance                               | Overview Tab → S/R Quick View   | <2% = near resistance = risky buy, limited upside                                |
| **Volatility %**          | ATR as % of price                                              | Momentum Tab                    | High volatility = wider stops needed. Low = tighter stops                        |
| **Avg Volume**            | 20-bar average volume                                          | Momentum Tab                    | Baseline to compare today's volume against                                       |

### Using the Momentum Tab for Entry Timing

The Momentum tab answers: "Is the current move real or exhausting?"

**Perfect Momentum Setup (BUY):**

```
✅ Momentum Status: Bullish Acceleration
✅ Volume Profile: Accumulation
✅ BB Position: Near Lower BB or Mid-Band (room to run)
✅ RSI Divergence: None or Bullish
✅ RSI Reading: 35-55 (not overbought)
✅ Volume Ratio: ≥1.5x (above average participation)
✅ OBV: Rising
```

**Exit Momentum Signals:**

```
🔴 Momentum Status: Decelerating (was bullish, now weakening)
🔴 Volume Profile: Distribution (selling pressure)
🔴 BB Position: Above Upper BB (overextended)
🔴 RSI > 70 + Bearish Divergence
🔴 Volume Ratio: Spiking 3x+ on a down day
```

### Using the Market Tab for Decision Making

#### The 7-Point Checklist — How to Read It

The Market tab's Quick Checklist gives you an instant buy/sell decision:

| Points Passed | Decision                                             | Confidence |
| ------------- | ---------------------------------------------------- | ---------- |
| 7/7 ✅        | **STRONG BUY** — All systems go. Use 3% of portfolio | 90%+       |
| 5-6/7         | **BUY** — Good setup. Use 2% of portfolio            | 70-85%     |
| 4/7           | **Small position** — Some risk. Use 1% only          | 55-65%     |
| 3 or less     | **DO NOT BUY** — Too many red flags. Watchlist only  | Skip       |

**The 7 checks explained:**

1. **Trend = UPTREND** — Are you trading WITH the trend? (Most important check)
2. **RSI 30-70** — Is the momentum safe? Not overbought or oversold at extremes
3. **MACD = Bullish** — Is the short-term momentum positive?
4. **Volume ≥1x avg** — Is there enough participation in this move?
5. **OBV = Rising** — Is real money flowing INTO this stock?
6. **ADX > 20** — Is there an actual trend, or is the market just drifting?
7. **R:R ≥ 2** — Will you make at least 2x what you risk?

#### Market Intelligence Cards — Expert Reading

**Market Phase (Wyckoff Cycle):**

| Phase             | What's Happening                                           | Action                                   |
| ----------------- | ---------------------------------------------------------- | ---------------------------------------- |
| **Accumulation**  | Smart money buying at lows, ADX low, volume quietly rising | 🟢 Best buy zone — enter with patience   |
| **Markup**        | Price rising with volume, trend confirmed                  | 🟢 Buy if not already in — ride the wave |
| **Distribution**  | Smart money selling at highs, volume erratic               | 🔴 Take profits — exit longs             |
| **Markdown**      | Price falling, trend down                                  | 🔴 Stay out — wait for Accumulation      |
| **Consolidation** | Range-bound, low ADX, no clear direction                   | ⬜ Wait — breakout direction unknown     |

**Market Structure:**

| Structure                 | Meaning                                       | Action                         |
| ------------------------- | --------------------------------------------- | ------------------------------ |
| **HH/HL Bullish**         | Higher Highs + Higher Lows — textbook uptrend | ✅ Buy on pullbacks to HL      |
| **LH/LL Bearish**         | Lower Highs + Lower Lows — textbook downtrend | ❌ Do not buy                  |
| **Expanding Range**       | Volatility increasing, swings getting larger  | ⚠️ Wide stops needed, risky    |
| **Contracting (Squeeze)** | Volatility decreasing, bands tightening       | ⚡ Breakout imminent — prepare |
| **Transitioning**         | Structure changing, not yet clear             | ⬜ Wait for confirmation       |

**Breakout Status:**

| Status                  | What It Means                            | Action                               |
| ----------------------- | ---------------------------------------- | ------------------------------------ |
| **Bullish Breakout**    | Price broke above resistance with volume | 🟢 Buy — momentum is strong          |
| **Bearish Breakdown**   | Price broke below support with volume    | 🔴 Exit immediately                  |
| **Testing Resistance**  | Price at resistance, hasn't broken yet   | ⬜ Wait for confirmation close above |
| **BB Breakout (Upper)** | Price above Bollinger Upper Band         | ⚠️ Overbought — don't chase          |
| **BB Breakout (Lower)** | Price below Bollinger Lower Band         | 🟡 Oversold — potential bounce       |
| **Near Zone**           | Price close to a key S/R level           | ⬜ Watch closely for break or bounce |
| **Range-Bound**         | No breakout, trading within range        | ⬜ Trade S/R levels, not momentum    |

**RSI Divergence:**

| Type                   | What It Means                                        | Reliability | Action                                 |
| ---------------------- | ---------------------------------------------------- | ----------- | -------------------------------------- |
| **Bullish Divergence** | Price making lower lows but RSI making higher lows   | Very High   | 🟢 Reversal up coming — prepare to buy |
| **Bearish Divergence** | Price making higher highs but RSI making lower highs | Very High   | 🔴 Reversal down coming — take profits |
| **None Detected**      | Price and RSI moving in same direction               | Normal      | — Continue with other signals          |

### The Glossary — Quick Reference

The Market tab includes a glossary of essential share market terms:

| Term             | Definition                                      | Trading Significance                                      |
| ---------------- | ----------------------------------------------- | --------------------------------------------------------- |
| **Breakout**     | Price breaks above resistance with volume       | Often starts a new uptrend — buy signal                   |
| **Breakdown**    | Price falls below support with volume           | Often starts a new downtrend — sell signal                |
| **Accumulation** | Smart money buying during a range               | Price will eventually break up — watch for entry          |
| **Distribution** | Smart money selling at the top                  | Price will eventually break down — prepare to exit        |
| **HH/HL**        | Higher High / Higher Low                        | Bullish market structure — trend is healthy               |
| **LH/LL**        | Lower High / Lower Low                          | Bearish market structure — trend is broken                |
| **Golden Cross** | SMA50 crosses above SMA200                      | Long-term bullish signal — multi-month uptrend ahead      |
| **Death Cross**  | SMA50 crosses below SMA200                      | Long-term bearish signal — multi-month downtrend ahead    |
| **Divergence**   | Price and indicator move in opposite directions | Leading reversal signal — very reliable                   |
| **Confluence**   | Multiple indicators agree on direction          | Higher probability trade — more indicators agree = better |

---

## 18. NEPSE-Specific Rules

### T+2 Settlement

You cannot sell before T+2 (2 trading days). Minimum hold = 3 trading days. The widget's SL/Target are designed for this.

### Circuit Breakers ±10%

Target capped at +15% (2-day circuit). Stop Loss floor at −8%.

### Operator Activity

Volume ≥ 3× average flags manipulation. With BUY verdict → ride with tight stop. With SELL → avoid.

### ADX Threshold

NEPSE uses ADX > 20 (vs. global 25) due to lower liquidity.

### Sector-Specific Timeframes

| Sector            | Best Analysis Timeframe | Why                                       |
| ----------------- | ----------------------- | ----------------------------------------- |
| **Banking**       | Daily + Weekly          | Banks move slowly, trend for weeks/months |
| **Hydropower**    | Weekly + Monthly        | Seasonal (monsoon cycle), longer trends   |
| **Insurance**     | Daily                   | More speculative, operator-driven         |
| **Manufacturing** | Weekly                  | Fundamental-driven, quarterly cycles      |
| **Microfinance**  | Daily                   | High volatility, quick moves              |

---

## 19. Warnings Reference

| Warning                 | Trigger              | Action                              |
| ----------------------- | -------------------- | ----------------------------------- |
| ⚡ Near circuit breaker | >8% daily move       | Wait for next session               |
| 🚨 Volume anomaly       | Volume ≥ 3x avg      | Follow direction, strict SL         |
| 🔴 RSI 80+              | Extremely overbought | Don't buy; exit                     |
| 🟢 RSI 20−              | Extremely oversold   | Wait for confirmation bar           |
| 📉 ATR squeeze          | Volatility < 1.5%    | Breakout coming — direction unknown |
| ✨ Golden Cross         | SMA50 > SMA200       | Bullish long-term                   |
| 💀 Death Cross          | SMA50 < SMA200       | Bearish long-term                   |
| ⏱️ Intraday data        | 1/5/15/30 min        | Confirm with daily chart            |
| 🕐 Hourly data          | 60 min               | Good for timing, confirm daily      |
| 📅 T+2 settlement       | Daily resolution     | Minimum 3-day hold                  |
| 📆 Weekly chart         | 1W resolution        | 2–6 week signal horizon             |
| 📊 Monthly chart        | 1M resolution        | 3–12 month horizon                  |
| 📈 Macro chart          | 3M/6M resolution     | 1–5 year horizon                    |

---

## 20. Troubleshooting

| Problem                     | Solution                                                                                     |
| --------------------------- | -------------------------------------------------------------------------------------------- |
| Widget doesn't appear       | Backend running? `http://127.0.0.1:8000/health`. Extension loaded? Hard-reload: Ctrl+Shift+R |
| "Analysis Failed"           | Start backend: `cd backend && uvicorn main:app --reload`                                     |
| N/A fields / low confidence | Not enough bars. Use wider range (1y for daily resolution)                                   |
| Multi-TF shows empty        | Switch to 1D or 1W resolution with 1y range                                                  |
| Outdated data               | Debounce = 30s. Switch resolution back and forth to force refresh                            |
| Patterns always "None"      | Normal for most bars. Check different stocks or wait for new candles                         |

---

## Architecture Reference

```
ShareHub Page
│
├── inject.js (MAIN world)
│   ├── Intercepts fetch() + XMLHttpRequest
│   └── Dispatches NEPSE_CHART_DATA via postMessage
│
├── content_script.js (ISOLATED world)
│   ├── Receives chart data
│   ├── Forwards to background.js
│   └── Renders 6-tab Shadow DOM widget (v3.0)
│
├── background.js (Service Worker)
│   ├── POST to http://127.0.0.1:8000/analyze
│   └── Returns RENDER_RESULT to content_script
│
└── Backend: FastAPI (v3.0 Professional)
    ├── 15+ oscillator/MA indicators
    ├── 27 candlestick patterns (pure Python)
    ├── Multi-TF for ALL resolutions:
    │   ├── Minute → Hourly + Daily
    │   ├── Hour → Daily + Weekly
    │   ├── Day → Weekly + Monthly
    │   ├── Week → Monthly + Quarterly
    │   └── Month → Quarterly + Yearly
    ├── Support/Resistance with distance tracking
    ├── Breakout detection (S/R + BB based)
    ├── Market structure (swing high/low analysis)
    ├── Market phase (Wyckoff-style)
    ├── Momentum profiling (ROC + MACD)
    ├── Volume profiling (Accumulation/Distribution)
    ├── RSI divergence scanning
    ├── DI+/DI- directional indicators
    ├── Fibonacci, Pivots, 52-week range
    ├── Golden/Death Cross detection
    ├── TradingView-style signal summaries
    └── NEPSE-calibrated scoring engine
```

---

_Last updated: March 2026 | NEPSE Pro Analyzer v2.0 — Expert Edition_
