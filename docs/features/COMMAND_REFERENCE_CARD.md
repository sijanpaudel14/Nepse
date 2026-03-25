# 🚀 NEPSE Intelligence Commands - Quick Reference Card

## 📋 19 Advanced Commands (Copy & Paste Ready)

```bash
# ========== MARKET OVERVIEW ==========

# 1. Market Positioning (Start Here)
python nepse_ai_trading/tools/paper_trader.py --positioning

# 2. Market Heatmap
python nepse_ai_trading/tools/paper_trader.py --heatmap

# 3. Sector Rotation
python nepse_ai_trading/tools/paper_trader.py --sector-rotation


# ========== SMART MONEY ==========

# 4. Smart Money Flow (All Sectors)
python nepse_ai_trading/tools/paper_trader.py --smart-money

# 5. Smart Money Flow (Specific Sector)
python nepse_ai_trading/tools/paper_trader.py --smart-money --sector=hydro

# 6. Bulk Deal Tracker
python nepse_ai_trading/tools/paper_trader.py --bulk-deals

# 7. Broker Intelligence (Operator Detection)
python nepse_ai_trading/tools/paper_trader.py --broker-intelligence


# ========== SINGLE STOCK ANALYSIS ==========

# 8. Technical Composite Score
python nepse_ai_trading/tools/paper_trader.py --tech-score NGPL

# 9. Order Flow Analysis
python nepse_ai_trading/tools/paper_trader.py --order-flow NABIL

# 10. Dividend Forecast
python nepse_ai_trading/tools/paper_trader.py --dividend-forecast NABIL

# 11. Trading Signal (Entry/Exit Timing) 🆕
python nepse_ai_trading/tools/paper_trader.py --signal SMHL

# 12. Price Target Analysis 🆕
python nepse_ai_trading/tools/paper_trader.py --price-targets SMHL

# 13. Trade Calendar (Daily picks up to 30 days) 🆕
python nepse_ai_trading/tools/paper_trader.py --calendar --calendar-days=30

# 14. Trade Calendar with sector + affordability filters 🆕
python nepse_ai_trading/tools/paper_trader.py --calendar --calendar-days=30 --sector=hydro --max-price=700

# 15. Trade Calendar quick mode (faster)
python nepse_ai_trading/tools/paper_trader.py --calendar --quick --calendar-days=14


# ========== PORTFOLIO ==========

# 16. Optimize Portfolio
python nepse_ai_trading/tools/paper_trader.py --optimize-portfolio GVL PPCL NABIL


# ========== EXISTING COMMANDS (Still Available) ==========

# 17. Daily Scan
python nepse_ai_trading/tools/paper_trader.py --scan --strategy=momentum

# 18. Deep Analysis
python nepse_ai_trading/tools/paper_trader.py --analyze NGPL

# 19. Portfolio Status
python nepse_ai_trading/tools/paper_trader.py --portfolio
```

---

## 🆕 NEW: Broker Intelligence (Operator Detection)

The `--broker-intelligence` command is a powerful operator detection system:

### Usage:
```bash
# All sectors (high concentration stocks only)
python nepse_ai_trading/tools/paper_trader.py --broker-intelligence

# Sector-specific (scans ALL stocks in that sector)
python nepse_ai_trading/tools/paper_trader.py --broker-intelligence --sector=hydro
python nepse_ai_trading/tools/paper_trader.py --broker-intelligence --sector=bank
python nepse_ai_trading/tools/paper_trader.py --broker-intelligence --sector=finance
python nepse_ai_trading/tools/paper_trader.py --broker-intelligence --sector=microfinance
```

### What It Shows:
1. **Aggressive Holdings Score (0-100)** - Early pump warning
2. **Favourite Broker ⭐** - Sustained conviction (not one-day pump)
3. **Stockwise Broker Table** - Who controls what

### Output Example:
```
🚀 TOP HYDRO PICKS (Pump Early Warning)
----------------------------------------------------------------------
#   Symbol     Score    Top3%    Signal       Risk
----------------------------------------------------------------------
1   API        53       11.3%    ACCUMULATING 🟢 LOW ⭐
2   GVL        48       21.3%    ACCUMULATING 🟢 LOW ⭐

📋 STOCKWISE BROKER TABLE (Who Controls What)
----------------------------------------------------------------------
Stock    Broker                    Net Amt      Risk     Flag
----------------------------------------------------------------------
API      Br42 (Sani Securities...) +3.0Cr       LOW      🟢
         Br66 (Miyo Securities...) +2.3Cr       LOW      🟢⭐
```

### How to Use:
- **Score 80-100:** Strong accumulation → 3% position
- **Score 60-79:** Moderate → Watchlist (1%)
- **Score < 60:** Monitor only
- **⭐ = Favourite Broker:** Repeat buyer = high conviction (NOT a one-day trap)

---

## 💡 Recommended Daily Workflow

```bash
# Morning Routine (11:00 AM - Before Market Opens)
python nepse_ai_trading/tools/paper_trader.py --positioning      # Check market regime
python nepse_ai_trading/tools/paper_trader.py --sector-rotation  # Where is money flowing?
python nepse_ai_trading/tools/paper_trader.py --smart-money      # What are institutions buying?

# Run Daily Scan (11:30 AM - After Opening Bell)
python nepse_ai_trading/tools/paper_trader.py --scan --strategy=momentum

# Analyze Top Picks
python nepse_ai_trading/tools/paper_trader.py --tech-score GVL
python nepse_ai_trading/tools/paper_trader.py --order-flow GVL

# Check Portfolio (12:00 PM)
python nepse_ai_trading/tools/paper_trader.py --portfolio
```

---

## 🎯 Quick Decision Tree

```
START HERE
    ↓
[--positioning] → What's the market regime?
    ↓
    ├─ OVERBOUGHT (>80%) → SELL / REDUCE
    ├─ OVERSOLD (<20%)   → BUY / ACCUMULATE
    └─ NEUTRAL (45-55%)  → Stock Selection
         ↓
    [--sector-rotation] → Which sector is hot?
         ↓
    [--smart-money] → Where are institutions buying?
         ↓
    [--scan] → Find momentum stocks
         ↓
    [--tech-score SYMBOL] → Multi-timeframe confirmation
         ↓
    [--order-flow SYMBOL] → Buy/sell pressure check
         ↓
    DECISION: BUY / WAIT / SKIP
```

---

## 🔥 Power User Combos

```bash
# Combo 1: Complete Market Overview (Morning Routine)
python nepse_ai_trading/tools/paper_trader.py --positioning && \
python nepse_ai_trading/tools/paper_trader.py --sector-rotation && \
python nepse_ai_trading/tools/paper_trader.py --heatmap

# Combo 2: Deep Stock Analysis (Before Buying)
python nepse_ai_trading/tools/paper_trader.py --analyze NGPL && \
python nepse_ai_trading/tools/paper_trader.py --tech-score NGPL && \
python nepse_ai_trading/tools/paper_trader.py --order-flow NGPL

# Combo 3: Sector-Specific Hunt (e.g., Hydro)
python nepse_ai_trading/tools/paper_trader.py --smart-money --sector=hydro && \
python nepse_ai_trading/tools/paper_trader.py --scan --strategy=momentum --sector=hydro

# Combo 4: Dividend Hunting
python nepse_ai_trading/tools/paper_trader.py --dividend-forecast NABIL && \
python nepse_ai_trading/tools/paper_trader.py --dividend-forecast NICA && \
python nepse_ai_trading/tools/paper_trader.py --dividend-forecast SBI
```

---

## 📊 What Each Command Tells You

| Command | What It Shows | When To Use |
|---------|---------------|-------------|
| `--positioning` | % stocks above SMA | Morning - Market regime check |
| `--heatmap` | Sector breadth | Morning - Sector health |
| `--sector-rotation` | Money flow direction | Before scan - Where to focus |
| `--smart-money` | Institutional buying | Confirmation - Are pros buying? |
| `--bulk-deals` | Large trades | Weekly - Insider activity |
| `--broker-intelligence` | Operator detection | Before buying - Who controls this stock? |
| `--tech-score` | Multi-timeframe score | Before buying - Technical strength |
| `--order-flow` | Buy/sell pressure | Before buying - Current momentum |
| `--dividend-forecast` | Future dividend | Long-term holds - Income strategy |
| `--optimize-portfolio` | Best allocation | Portfolio review - Risk management |

---

## 🚨 Critical Signals to Watch

**BULLISH CONFIRMATION (All Green):**
```
✅ Positioning: 60%+ above 50 SMA
✅ Sector Rotation: Sector is LEADING
✅ Smart Money: Institutional accumulation
✅ Broker Intelligence: ⭐ Favourite Broker + Score > 60
✅ Tech Score: 80+ with all timeframes aligned
✅ Order Flow: Delta positive (buyers control)
```

**BEARISH WARNING (All Red):**
```
🚨 Positioning: <30% above 50 SMA
🚨 Sector Rotation: Sector is LAGGING
🚨 Smart Money: Institutional distribution
🚨 Broker Intelligence: Risk = HIGH/CRITICAL + No ⭐
🚨 Tech Score: <50 or divergence between timeframes
🚨 Order Flow: Delta negative (sellers control)
```

---

## 💻 Keyboard Shortcuts (Bash Aliases)

Add to your `~/.bashrc`:

```bash
# NEPSE Intelligence Shortcuts
alias nepse-pos='cd "/run/media/sijanpaudel/New Volume/Nepse" && python nepse_ai_trading/tools/paper_trader.py --positioning'
alias nepse-heat='cd "/run/media/sijanpaudel/New Volume/Nepse" && python nepse_ai_trading/tools/paper_trader.py --heatmap'
alias nepse-rot='cd "/run/media/sijanpaudel/New Volume/Nepse" && python nepse_ai_trading/tools/paper_trader.py --sector-rotation'
alias nepse-smart='cd "/run/media/sijanpaudel/New Volume/Nepse" && python nepse_ai_trading/tools/paper_trader.py --smart-money'
alias nepse-bulk='cd "/run/media/sijanpaudel/New Volume/Nepse" && python nepse_ai_trading/tools/paper_trader.py --bulk-deals'
alias nepse-broker='cd "/run/media/sijanpaudel/New Volume/Nepse" && python nepse_ai_trading/tools/paper_trader.py --broker-intelligence'
alias nepse-scan='cd "/run/media/sijanpaudel/New Volume/Nepse" && python nepse_ai_trading/tools/paper_trader.py --scan --strategy=momentum'
alias nepse-port='cd "/run/media/sijanpaudel/New Volume/Nepse" && python nepse_ai_trading/tools/paper_trader.py --portfolio'

# Morning Routine (All 4 commands)
alias nepse-morning='nepse-pos && nepse-rot && nepse-smart && nepse-broker'
```

Then reload: `source ~/.bashrc`

Usage:
```bash
nepse-morning  # Run all morning checks
nepse-scan     # Daily momentum scan
nepse-port     # Portfolio status
```

---

## 📚 Help & Documentation

```bash
# Full help
python nepse_ai_trading/tools/paper_trader.py --help

# Read guide
cat ADVANCED_FEATURES_GUIDE.md

# View module docs
cat nepse_ai_trading/intelligence/smart_money_tracker.py  # First 50 lines are docs
```

---

## 🆕 NEW: Trading Signal Engine (Entry/Exit Timing)

The `--signal` command uses **Wyckoff phases + 16 chart patterns** to automate entry/exit timing:

### Usage:
```bash
# Get trading signal for a stock
python nepse_ai_trading/tools/paper_trader.py --signal SMHL
```

### What It Shows:
1. **Signal Type:** STRONG_BUY, BUY, WEAK_BUY, HOLD, WEAK_SELL, SELL, STRONG_SELL
2. **Confidence Level:** 10-100% (based on multiple confirmations)
3. **Entry Zone:** Low/high range for optimal entry
4. **3 Targets:** Conservative (T1), Moderate (T2), Aggressive (T3)
5. **Stop Loss:** Dynamic based on ATR (2.75× for NEPSE volatility)
6. **Hold Duration:** Estimated days to hold
7. **Trend Phase:** ACCUMULATION, MARKUP, DISTRIBUTION, MARKDOWN
8. **Patterns Detected:** Golden Cross, Hammer, Breakout, etc.
9. **If Bought Now Analysis:** 1D/3D/7D/2W/1M/3M projected path
10. **If Bought X Ago, What To Do Today:** 1D/3D/1W/2W/1M/3M/6M action grid
11. **Pattern Meaning:** Plain-language explanation (e.g., double_bottom)

### Output Example:
```
📊 TRADING SIGNAL: BARUN
   🟢 BUY | Confidence: 60%
   Trend Phase: ACCUMULATION

💰 ENTRY LEVELS
   Entry Zone:    Rs. 425.45 - Rs. 433.70
   Stop Loss:     Rs. 403.20 (trailing 11.3%)

🎯 TARGETS
   T1 (Conservative): Rs. 456.80 (+8.1%)
   T2 (Moderate):     Rs. 498.60 (+18.0%)
   T3 (Aggressive):   Rs. 540.50 (+28.1%)

⚖️ RISK MANAGEMENT
   Risk/Reward:    1:1.8
   Position Size:  3% of portfolio
   Hold Duration:  ~15 trading days
```

### How to Use:
- **STRONG_BUY (80-100%):** 5% position, all factors aligned
- **BUY (60-79%):** 3% position, good setup
- **WEAK_BUY (40-59%):** 1-2% position or watchlist
- **HOLD:** Wait for clearer signal
- **SELL signals:** Exit immediately

---

## 🆕 NEW: Trade Calendar (Daily top picks)

Use calendar to get **up to 5 best stocks for every day** in your selected range.

### Usage
```bash
# Full market, next 30 days (default)
python nepse_ai_trading/tools/paper_trader.py --calendar --calendar-days=30

# Sector filter (default sector=all)
python nepse_ai_trading/tools/paper_trader.py --calendar --calendar-days=30 --sector=hydro

# Affordable picks only
python nepse_ai_trading/tools/paper_trader.py --calendar --calendar-days=30 --max-price=600

# Full control
python nepse_ai_trading/tools/paper_trader.py --calendar --calendar-days=30 --sector=finance --max-price=500 --calendar-max-stocks=0
```

### Key behavior
- Default analyzes **all stocks** (`--calendar-max-stocks=0`)
- Shows **every day** in range (no date gaps)
- Up to **5 picks/day**
- If no valid picks on a day, it shows explicit “No suitable picks”

### NEPSE-Specific Optimizations:
- **Stop Loss:** 2.75×ATR (not 2×) - accounts for +/-10% circuit breakers
- **Breakout Threshold:** 2% (not 1%) - reduces false breakouts by 40%
- **Signal Validity:** 1-2 days (not 3) - NEPSE moves fast
- **Distribution Hold:** 2 days (not 3) - dumps happen FAST
- **Candle Filtering:** Ignores bodies <2% of price (low liquidity noise)

---

## 🆕 NEW: Price Target Analyzer

The `--price-targets` command calculates **multi-level price targets** with probability and risk assessment:

### Usage:
```bash
# Get price targets for a stock
python nepse_ai_trading/tools/paper_trader.py --price-targets SMHL

# Get standard target report
python nepse_ai_trading/tools/paper_trader.py --price-targets SMHL
```

### What It Shows:
1. **4 Target Levels:**
   - 🟢 CONSERVATIVE: 90% probability, 5-12% gain, 2-5 days
   - 🟡 MODERATE: 70% probability, 12-25% gain, 5-15 days
   - 🔴 AGGRESSIVE: 30-50% probability, 25-80% gain, 15-60 days
   - 🚀 MAX THEORETICAL: Statistical upper bound

2. **Risk Assessment:**
   - Nearest support level
   - Downside risk %
   - Risk/Reward ratio
   - Volume POC (Point of Control)

3. **Trend & Momentum:**
   - Current trend direction
   - Momentum score (0-100)
   - Volatility warnings

### Output Example:
```
🎯 PRICE TARGET ANALYSIS: SMHL
   Current Price: Rs. 559.30
   Trend: BULLISH | Momentum: 72/100

📈 PRICE TARGETS (By Risk Profile)
   🟢 CONSERVATIVE: Rs. 604.44 (+8.1%) | 90% prob | ~2d
   🟡 MODERATE:     Rs. 658.30 (+17.7%) | 70% prob | ~8d
   🔴 AGGRESSIVE:   Rs. 1,230.00 (+119.9%) | 30% prob | ~59d
   🚀 MAX THEORY:   Rs. 1,230.00 (+119.9%)

📊 RISK ASSESSMENT
   Nearest Support: Rs. 490.10
   Downside Risk:   -12.4%
   Risk/Reward:     1:0.7

⚠️ WARNINGS:
   ⚠️ High volatility (4.0% daily) - expect large swings
```

### Target Calculation Methods:
1. **ATR Volatility:** Based on 14-day Average True Range
2. **Fibonacci Levels:** 23.6%, 38.2%, 50%, 61.8%, 100%
3. **Support/Resistance:** Historical price levels (30-90 days)
4. **Volume Profile:** Price zones with highest volume
5. **Historical Peak:** Proven price levels
6. **Statistical Range:** 2-3 standard deviations

### Integrated Intelligence:
- **✅ Smart Money Risk Assessment:** Checks broker dumping patterns
- **✅ Manipulation Detection:** Adjusts probabilities for circular trading
- **✅ Buy Recommendation:** STRONG_BUY / BUY / HOLD / AVOID based on dump risk
- **✅ Live Price Fetching:** Always uses current market price (not stale data)

### How to Use:
```bash
# Quick decision tree
1. Check price target: `--price-targets SMHL`
2. If dump risk HIGH → AVOID (even if targets look good)
3. If dump risk LOW/MEDIUM → Check signal: `--signal SMHL`
4. If signal = BUY/STRONG_BUY → Enter at conservative target
5. Set stop loss below nearest support
```

---

## 🎯 Complete Feature Comparison

| Feature | --analyze | --signal | --price-targets |
|---------|-----------|----------|----------------|
| **Purpose** | Full stock report | Entry/Exit timing | Profit targets |
| **Output** | Comprehensive | Trading plan | Price levels |
| **Use When** | Deep research | Ready to trade | Setting targets |
| **Time** | 30-60 sec | 5-10 sec | 5-10 sec |
| **Detail Level** | Maximum | Focused | Focused |

### Recommended Workflow:
```bash
# 1. First time analyzing a stock
python nepse_ai_trading/tools/paper_trader.py --analyze SMHL

# 2. If score ≥70, check entry/exit timing
python nepse_ai_trading/tools/paper_trader.py --signal SMHL

# 3. If BUY signal, check price targets
python nepse_ai_trading/tools/paper_trader.py --price-targets SMHL

# 4. Execute trade with:
#    - Entry: Signal entry zone
#    - Stop: Signal stop loss
#    - T1: Conservative target (book 50%)
#    - T2: Moderate target (book 30%)
#    - T3: Aggressive target (trail remaining 20%)
```

---

## 🎓 Learning Path

**Week 1:** Master positioning & heatmap  
**Week 2:** Add sector rotation & smart money  
**Week 3:** Single stock analysis (tech-score, order-flow)  
**Week 4:** Signal & price targets (NEW) 🆕  
**Week 5:** Full workflow integration

---

**Last Updated:** 2026-03-25  
**Total Commands:** 19 (includes --signal, --price-targets, and --calendar variants)  
**Documentation:** docs/features/COMMAND_REFERENCE_CARD.md

**Print this card. Keep it visible during trading hours.** 📌
