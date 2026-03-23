# 🚀 NEPSE Advanced Intelligence Features Guide

## Overview
Your NEPSE AI Trading Engine now includes **9 Advanced Intelligence Modules** that go beyond basic technical analysis to give you institutional-grade market insights.

---

## 📋 Quick Command Reference

```bash
# 1. Bulk Deal Tracker - Track insider/promoter activity
python nepse_ai_trading/tools/paper_trader.py --bulk-deals
python nepse_ai_trading/tools/paper_trader.py --bulk-deals --sector=hydro

# 2. Sector Rotation Map - See which sectors are hot
python nepse_ai_trading/tools/paper_trader.py --sector-rotation

# 3. Smart Money Tracker - Follow institutional money
python nepse_ai_trading/tools/paper_trader.py --smart-money
python nepse_ai_trading/tools/paper_trader.py --smart-money --sector=bank

# 4. Market Heatmap - Market breadth overview
python nepse_ai_trading/tools/paper_trader.py --heatmap

# 5. Technical Composite Score - Multi-timeframe scoring
python nepse_ai_trading/tools/paper_trader.py --tech-score NGPL

# 6. Order Flow Analysis - See buying/selling pressure
python nepse_ai_trading/tools/paper_trader.py --order-flow NABIL

# 7. Portfolio Optimizer - Optimize allocation
python nepse_ai_trading/tools/paper_trader.py --optimize-portfolio GVL PPCL NABIL

# 8. Dividend Forecaster - Predict future dividends
python nepse_ai_trading/tools/paper_trader.py --dividend-forecast NABIL

# 9. Quant Positioning - Market positioning indicators
python nepse_ai_trading/tools/paper_trader.py --positioning
```

---

## 📊 Feature Details

### 1. 🔍 Bulk Deal Tracker
**What:** Tracks large block trades (>10,000 shares or >Rs. 1Cr value)  
**Why:** Insiders/promoters signal their intentions through bulk deals  
**Signals:**
- Bulk buying at -10% LTP → **PUMP COMING**
- Promoter bulk sell → **DUMP WARNING**
- >50L shares bought → **STRONG ACCUMULATION**

**Example Output:**
```
📊 BULK DEAL ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Timeframe: Last 30 days

🔥 TOP BULK BUYERS
#1 NGPL:  1.2M shares | Avg Rs.485 | 12 deals | ACCUMULATION
#2 HPPL:  890K shares | Avg Rs.528 | 8 deals  | ACCUMULATION
```

---

### 2. 🔄 Sector Rotation Map
**What:** Weekly sector momentum ranking  
**Why:** Money flows between sectors (hydro→banks→micro)  
**Signals:**
- Hydro: +12% (Week 1) → **OVERBOUGHT**
- Banks: +8% (Week 2) → **MOMENTUM LEADER**
- Micro: -3% → **AVOID**

**Example Output:**
```
📊 SECTOR ROTATION MAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#1 Hydro Power        +8.5%  🟢 LEADING
#2 Commercial Banks   +4.2%  🟢 LAGGING_BULLISH
#3 Finance            -2.1%  🔴 LAGGING_BEARISH

💡 ROTATION SIGNALS:
→ Money flowing INTO: Hydro Power, Commercial Banks
→ Money flowing OUT: Manufacturing, Hotels
```

---

### 3. 💰 Smart Money Tracker
**What:** Track institutional buying (mutual funds, insurance, banks)  
**Why:** Institutions drive 70% of NEPSE moves  
**Signals:**
- Mutual fund net buying >5Cr/week → **BULLISH**
- Insurance companies accumulating → **SAFE MONEY**
- Bank treasuries selling → **MARKET TOP**

**Example Output:**
```
💰 SMART MONEY FLOW ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 ACCUMULATION STOCKS (Institutional Buying)
#1 NGPL   90/100 | Net: +1.1M shares | Top 3: 65% | ✅ STRONG
#2 NABIL  85/100 | Net: +820K shares | Top 3: 58% | ✅ STRONG
```

---

### 4. 🗺️ Market Heatmap
**What:** Live market breadth analysis  
**Why:** Detect overbought/oversold regimes  
**Signals:**
- 80% stocks green → **MARKET TOP**
- 20% stocks green → **MARKET BOTTOM**
- Advance/Decline ratio → **TREND STRENGTH**

**Example Output:**
```
🗺️ NEPSE MARKET BREADTH HEATMAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall: 58% stocks UP | 42% DOWN
Regime: 🟢 BULLISH

SECTOR BREAKDOWN:
Hydro Power:         ████████░░ 78% UP  🟢 STRONG
Commercial Banks:    ██████░░░░ 62% UP  🟢 BULLISH
```

---

### 5. 📈 Technical Composite Score
**What:** 12 indicators → 0-100 multi-timeframe score  
**Why:** Institutions use Weekly+Daily+Monthly confluence  
**Methodology:**
- Daily (40%), Weekly (40%), Monthly (20%)
- Trend (40%), Momentum (30%), Volume (30%)

**Example Output:**
```
📈 TECHNICAL COMPOSITE SCORE: NGPL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Overall Score: 82/100 ✅ STRONG BUY

TIMEFRAME BREAKDOWN:
Daily (40%):    85/100  🟢 Bullish
Weekly (40%):   80/100  🟢 Bullish  
Monthly (20%):  78/100  🟢 Bullish
→ ✅ ALIGNED: All timeframes bullish
```

---

### 6. 📊 Order Flow Analysis
**What:** Intraday buy/sell aggression analysis  
**Why:** See institutions trapping retail  
**Signals:**
- **ABSORPTION:** 3x volume, price flat → Institutions selling
- **DELTA POSITIVE:** Buy vol > sell vol → Bullish
- **LIQUIDITY GRAB:** Fake breakdown → Buy opportunity

**Example Output:**
```
📊 ORDER FLOW ANALYSIS: NABIL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Date: 23-Mar | LTP: Rs.1,185

📈 BUY/SELL DELTA:
Buy Volume:  820,450 (58%)
Sell Volume: 595,320 (42%)
Delta:       +225,130 shares  🟢 BUYERS CONTROL

🚨 DETECTED PATTERNS:
✅ NO absorption detected
✅ NO liquidity grab detected
```

---

### 7. ⚖️ Portfolio Optimizer
**What:** Risk-adjusted portfolio construction  
**Why:** Maximize Sharpe ratio, minimize drawdown  
**Methodology:** Modern Portfolio Theory adapted for NEPSE

**Example Output:**
```
⚖️ OPTIMAL ALLOCATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GVL      40%  ████████
PPCL     35%  ███████
NABIL    25%  █████

Expected Return: +18.5%
Volatility:      12.3%
Sharpe Ratio:    1.02

🔗 CORRELATION MATRIX:
       GVL    PPCL   NABIL
GVL    1.00   0.35   0.22
PPCL   0.35   1.00   0.18
NABIL  0.22   0.18   1.00

💡 Low correlation = Good diversification
```

---

### 8. 💵 Dividend Forecaster
**What:** Predict future dividends using EPS + cash flow  
**Why:** NEPSE yields 20-50% (cash+bonus)  
**Methodology:**
- 3-5 year dividend history
- Payout ratio × current EPS
- Sector-specific patterns

**Example Output:**
```
💰 DIVIDEND FORECAST: NABIL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Current Price: Rs.1,185
Current EPS:   Rs.42.5
Current Yield: 4.2%

🔮 FORECAST (Next Year):
Predicted Cash Dividend:  20.0%
Predicted Bonus:          12.0%
Predicted Total:          32.0%

Forecast Dividend:        Rs.32.0 per share
Forecast Yield:           2.7%

Confidence:               HIGH (75%)

📅 EXPECTED TIMING:
AGM Period:      August-September
Book Closure:    1-2 weeks before AGM
```

---

### 9. 📊 Quant Positioning
**What:** Market-wide positioning indicators  
**Why:** Extreme positioning = reversal  
**Methodology:**
- % stocks above 50-day SMA (breadth)
- % stocks above 200-day SMA (trend)
- % stocks at 52-week high/low

**Example Output:**
```
📊 QUANT POSITIONING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Above 20-SMA:  68.5% ████████░░ (BULLISH)
Above 50-SMA:  55.2% ██████░░░░ (BULLISH)
Above 200-SMA: 42.8% █████░░░░░ (NEUTRAL)

At 52W High: 12 stocks (4.8%)
At 52W Low:  8 stocks (3.2%)

Overall Regime: 🟢 BULLISH

💡 TRADING GUIDANCE:
Signal: NEUTRAL
Market positioning is balanced. Focus on individual stock
selection and sector rotation.
```

---

## 🎯 Usage Patterns

### Daily Workflow
```bash
# 1. Morning: Check market positioning
python nepse_ai_trading/tools/paper_trader.py --positioning

# 2. Check sector rotation
python nepse_ai_trading/tools/paper_trader.py --sector-rotation

# 3. Find smart money flow
python nepse_ai_trading/tools/paper_trader.py --smart-money

# 4. Run momentum scan
python nepse_ai_trading/tools/paper_trader.py --scan --strategy=momentum
```

### Single Stock Analysis
```bash
# Complete stock analysis
python nepse_ai_trading/tools/paper_trader.py --analyze NGPL
python nepse_ai_trading/tools/paper_trader.py --tech-score NGPL
python nepse_ai_trading/tools/paper_trader.py --order-flow NGPL
python nepse_ai_trading/tools/paper_trader.py --dividend-forecast NGPL
```

### Portfolio Management
```bash
# Check current portfolio
python nepse_ai_trading/tools/paper_trader.py --portfolio

# Optimize new allocation
python nepse_ai_trading/tools/paper_trader.py --optimize-portfolio GVL PPCL HPPL NABIL
```

---

## 📚 Data Sources

All features use existing NEPSE data:
- **ShareHub API:** Bulk transactions, broker holdings, player favorites
- **NepseFetcher:** Historical OHLCV, sector indices, live market data
- **Floorsheet:** Transaction-level data for order flow

No new APIs required. All data already available in your system.

---

## 🚨 Limitations

### Skipped Features (No Data Available)
1. **Order Book Analysis** - No Level 2 (bid/ask) data from NEPSE
2. **Social Sentiment** - Would require Facebook/Telegram scraping
3. **Insider Transactions** - No structured SEBON Form 25/26 API

### Proxies Used
- **Order Flow:** Uses daily close position within high-low range (not tick-by-tick)
- **Smart Money:** Uses broker concentration as proxy (no explicit institutional flag)
- **Institutional Buying:** Top 3 broker concentration >60% = institutional

---

## 🏆 Implementation Status

```
✅ Sprint 1 (DONE): Bulk Deals, Sector Rotation, Smart Money
✅ Sprint 2 (DONE): Heatmap, Tech Composite, Order Flow
✅ Sprint 3 (DONE): Portfolio Optimizer, Dividend, Positioning
✅ CLI Integration (DONE): 9 commands added
✅ Documentation (DONE): This guide

Total: 9/15 Features Implemented (Feasible subset)
```

---

## 💡 Pro Tips

1. **Combine Features:** Use --smart-money + --sector-rotation to find where institutions are rotating
2. **Daily Routine:** --positioning → --sector-rotation → --smart-money → --scan
3. **Deep Dive:** --analyze SYMBOL → --tech-score SYMBOL → --order-flow SYMBOL
4. **Risk Management:** --optimize-portfolio before large positions
5. **Income Strategy:** --dividend-forecast for high-yield picks

---

## 🔥 Next Steps

1. **Test Each Module:** Run all 9 commands to familiarize yourself
2. **Integrate Into Workflow:** Add to your daily scan routine
3. **Monitor Performance:** Track which signals give best results
4. **Customize:** Adjust thresholds in module code as needed

---

## 📞 Support

For issues or questions:
1. Check module docstrings: `nepse_ai_trading/intelligence/`
2. Review code comments for methodology
3. Test with known stocks first (NABIL, NGPL, NICA)

---

**Built with institutional-grade logic. Adapted for NEPSE reality.**  
**Now you have the tools. Master them.** 🚀
