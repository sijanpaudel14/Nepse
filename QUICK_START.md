# 🚀 QUICK START - NEPSE AUTOMATED LOGGER

## ⚡ Fastest Way to Get Started

### 1️⃣ Run Your First Analysis (RIGHT NOW!)

```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse
python nepse_ai_trading/tools/auto_market_logger.py --now
```

**Wait:** 5-10 minutes  
**Output:** `market_logs/YYYY-MM-DD_HHMM/` folder with 15-20 files

---

### 2️⃣ Read the Results

```bash
cd market_logs
ls -lt | head -5                    # Find latest session
cd 2026-03-23_1130                  # Enter folder (use your timestamp)
cat 00_MASTER_SUMMARY.md | less    # Read master guide
```

**Key files to read:**
- `00_MASTER_SUMMARY.md` ← **START HERE** (explains everything)
- `06_momentum_scan.md` ← **MOST IMPORTANT** (GOOD stocks list)
- `08_*_*.md` ← Deep dive on top picks

---

### 3️⃣ Understand the Output

The **00_MASTER_SUMMARY.md** will teach you:
- How to read each phase
- What to look for
- How to make trading decisions
- Beginner workflow

**Example Decision Framework:**
```
IF market strong (>70% stocks above 50-DMA)
   AND GOOD stocks exist in scan
   AND institutional buying detected
   → Consider entry (3-5% position size)

IF market weak
   → Stay cash, wait for better setup

IF uncertain
   → Paper trade first!
```

---

## 📅 Daily Workflow (For Beginners)

### Morning Routine (11:30 AM)
```bash
# Run analysis 30 min after market opens
python nepse_ai_trading/tools/auto_market_logger.py --now
```

### Evening Review (After Market)
```bash
# Read analysis offline
cd market_logs/<today's_session>/
cat 00_MASTER_SUMMARY.md

# Compare with yesterday
cd ../2026-03-22_1130/
cat 06_momentum_scan.md  # See if same stocks still GOOD
```

---

## 🔄 Automated Workflows

### Set-and-Forget (Recommended)
```bash
# Start scheduler (runs 3x daily)
python nepse_ai_trading/tools/auto_market_logger.py --schedule
```
**Runs at:** 11:30 AM, 1:00 PM, 2:45 PM  
**Keep running:** Leave terminal open or use screen/tmux

---

### Background Service
```bash
# Start daemon in background
nohup python nepse_ai_trading/tools/auto_market_logger.py --daemon \
  > /tmp/market.log 2>&1 &

# Check if running
ps aux | grep auto_market_logger

# Stop it later
pkill -f auto_market_logger
```
**Checks:** Every 30 min during market hours  
**Auto-stops:** When market closed

---

## 📖 What Each File Contains

```
00_MASTER_SUMMARY.md     → Complete guide + decision framework
01_market_positioning.md → Overbought/oversold? Market top/bottom?
02_market_heatmap.md     → How many stocks green/red today?
03_sector_rotation.md    → Which sectors are leading?
04_smart_money_flow.md   → What institutions are buying?
05_bulk_deals.md         → Any large insider trades?
06_momentum_scan.md      → GOOD/RISKY/WATCH stocks ⭐ CRITICAL!
07_portfolio_review.md   → Your holdings + P&L + signals
08_1_analysis_NGPL.md    → Full report on Stock #1
08_1_techscore_NGPL.md   → Technical alignment Stock #1
08_1_orderflow_NGPL.md   → Buy/sell pressure Stock #1
08_1_dividend_NGPL.md    → Dividend forecast Stock #1
... (similar for Stock #2, #3)
```

---

## 🎯 Beginner Learning Path

### Week 1: Observation Phase
✅ Run `--now` every day after market opens  
✅ Read all 5 phases offline  
✅ **Don't trade yet!** Just learn patterns  
✅ Notice: Which stocks appear repeatedly as GOOD?

### Week 2: Pattern Recognition
✅ Compare Monday vs Thursday sessions  
✅ Track sector rotation patterns  
✅ Identify: Market top/bottom signals

### Week 3: Paper Trading
✅ Pick GOOD stocks from scan  
✅ Use `--buy-picks NGPL PPCL` to paper trade  
✅ Track in `--portfolio`  
✅ Would you have made money?

### Week 4+: Real Trading (Tiny Sizes)
✅ Start with 1-2% positions (not 3-5% yet!)  
✅ Only trade GOOD stocks (never RISKY/WATCH)  
✅ Always set stop loss at -5%  
✅ Take profit at +10%

---

## 🚨 Important Rules

### Position Sizing
- **GOOD stocks:** Max 3-5% of capital
- **RISKY stocks:** Max 1-2% or paper only
- **WATCH/VETO:** Never trade (paper only)

### Risk Management
- **Stop Loss:** Always -5% from entry
- **Target:** Always +10% from entry
- **Max Hold:** 7 days if no target hit
- **Max Positions:** 3-5 stocks at a time

### Trading Hours
- **NEPSE Open:** Sun-Thu 11:00 AM - 3:00 PM
- **Closed:** Friday & Saturday
- **Best Entry:** 11:30 AM - 12:00 PM (after volatility settles)

---

## 💡 Tips for Success

### Do's ✅
✅ Always read 00_MASTER_SUMMARY.md first  
✅ Compare multiple sessions to spot patterns  
✅ Start with paper trading  
✅ Follow stop loss strictly  
✅ Take notes on what works

### Don'ts ❌
❌ Don't trade RISKY/WATCH stocks initially  
❌ Don't skip the analysis (lazy trading fails)  
❌ Don't ignore stop losses  
❌ Don't overtrade (max 1 entry per day)  
❌ Don't revenge trade after a loss

---

## 🔍 Real Example

### Session Output (Typical)
```
market_logs/2026-03-23_1130/

Phase 1 says: Market strong (75% above 50-DMA)
Phase 2 says: Institutions buying NGPL, PPCL
Phase 3 says:
  ✅ GOOD: NGPL (85/100) → Entry Rs.491
  ⚠️ RISKY: HDHPC (72/100) → Has negative EPS
  
Phase 5 Deep Dive NGPL:
  - Technical Score: 78/100 (strong)
  - Order Flow: Buy pressure 65% (good)
  - Dividend: Expected Rs.35 (7% yield)

Decision: ✅ Buy NGPL 3% position at Rs.491
          Stop: Rs.467 (-5%)
          Target: Rs.540 (+10%)
```

---

## 📞 Troubleshooting

### Logger hangs?
- **Auto-timeout after 2 minutes** per command
- **Continues to next** command automatically

### No GOOD stocks found?
- **Check RISKY category** manually
- **Market may be weak** - stay cash

### Want to test without waiting for market?
- **Use `--now` flag** anytime (ignores market hours)

---

## 📚 Full Documentation

- **AUTO_LOGGER_GUIDE.md** - Complete guide (this doc)
- **ADVANCED_FEATURES_GUIDE.md** - All 9 intelligence features
- **COMMAND_REFERENCE_CARD.md** - Quick command reference

---

## 🎓 Next Steps

1. **Run first analysis NOW:**
   ```bash
   python nepse_ai_trading/tools/auto_market_logger.py --now
   ```

2. **Read the output:**
   ```bash
   cd market_logs/<latest>/
   cat 00_MASTER_SUMMARY.md
   ```

3. **Learn for 1 week** before trading

4. **Paper trade for 2 weeks** to test

5. **Start tiny real trades** (1-2% sizes)

---

## ✅ You're Ready!

**One command runs everything. One file explains everything.**

No stress. No confusion. Just learn and trade smart! 🚀

---

*Perfect for share market beginners. The system does the hard work, you just make decisions!*
