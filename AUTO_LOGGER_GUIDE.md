# 🚀 NEPSE AUTOMATED MARKET LOGGER - USER GUIDE

## 📖 What Is This?

A **simple background automation tool** that runs all your trading intelligence commands in the optimal sequence and saves everything to timestamped Markdown files.

**Perfect for beginners** - No need to remember which command to run when. Just start it and review analysis offline!

---

## 🎯 What It Does

### Runs 5 Phases Automatically:

**Phase 1: Market Overview**
- Market positioning (overbought/oversold?)
- Market heatmap (how many stocks green?)
- Sector rotation (which sectors leading?)

**Phase 2: Institutional Activity**
- Smart money flow (what institutions buying?)
- Bulk deals (any insider trades?)

**Phase 3: Momentum Scan**
- Full momentum scan (GOOD/RISKY/WATCH stocks)

**Phase 4: Portfolio Management**
- Your current holdings review
- P&L and sell signals

**Phase 5: Deep Dive**
- Full analysis of top 3 stocks
- Technical composite scores
- Order flow analysis
- Dividend forecasts

---

## 🚀 Quick Start

### Option 1: Run Once NOW
```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse
python nepse_ai_trading/tools/auto_market_logger.py --now
```
**Takes:** ~5-10 minutes  
**Creates:** Full analysis in `market_logs/YYYY-MM-DD_HHMM/`

---

### Option 2: Schedule (3 times daily)
```bash
python nepse_ai_trading/tools/auto_market_logger.py --schedule
```
**Runs automatically at:**
- 11:30 AM (30 min after market open)
- 1:00 PM (mid-day check)
- 2:45 PM (15 min before close)

**Keeps running in foreground** - Use Ctrl+C to stop

---

### Option 3: Daemon Mode (Background)
```bash
# Run in background
nohup python nepse_ai_trading/tools/auto_market_logger.py --daemon > /tmp/market_logger.log 2>&1 &

# Check if running
ps aux | grep auto_market_logger

# Stop it
pkill -f auto_market_logger
```
**Behavior:** Checks every 30 minutes during market hours, sleeps when market closed

---

## 📁 Output Structure

```
market_logs/
└── 2026-03-23_1130/                    ← Session folder (timestamped)
    ├── 00_MASTER_SUMMARY.md            ← START HERE! Complete guide
    ├── 01_market_positioning.md        ← Phase 1: Overbought/oversold
    ├── 02_market_heatmap.md            ← Phase 1: Breadth analysis
    ├── 03_sector_rotation.md           ← Phase 1: Money flow
    ├── 04_smart_money_flow.md          ← Phase 2: Institutions
    ├── 05_bulk_deals.md                ← Phase 2: Insider trades
    ├── 06_momentum_scan.md             ← Phase 3: GOOD stocks
    ├── 07_portfolio_review.md          ← Phase 4: Your holdings
    ├── 08_1_analysis_NGPL.md           ← Phase 5: Stock 1 full report
    ├── 08_1_techscore_NGPL.md          ← Phase 5: Stock 1 tech score
    ├── 08_1_orderflow_NGPL.md          ← Phase 5: Stock 1 order flow
    ├── 08_1_dividend_NGPL.md           ← Phase 5: Stock 1 dividend
    └── ... (similar for Stock 2, 3)
```

---

## 📖 How to Read the Analysis (Beginner Workflow)

### Step 1: Open `00_MASTER_SUMMARY.md`
This is your **table of contents** and **learning guide**. It explains:
- What each phase means
- Which files to read
- What to look for
- Decision framework

### Step 2: Read Phase 1 (Market Overview)
**Files:** `01_*.md`, `02_*.md`, `03_*.md`

**Questions to answer:**
- Is market strong or weak?
- Are most stocks green or red?
- Which sector is leading?

**Example interpretation:**
```
✅ If 70% stocks above 50-DMA → Market strong
✅ If Hydropower sector +4% → Buy hydro stocks
⚠️ If 80% stocks green today → Possible top, be careful
```

### Step 3: Read Phase 2 (Institutional Activity)
**Files:** `04_*.md`, `05_*.md`

**Questions to answer:**
- What are institutions accumulating?
- Any bulk deals (insider buying/selling)?

**Example interpretation:**
```
✅ If NGPL has institutional accumulation → Strong candidate
✅ If 10L+ bulk buy on PPCL → Insiders know something
⚠️ If bulk sell on BARUN → Stay away!
```

### Step 4: Read Phase 3 (Momentum Scan)
**File:** `06_momentum_scan.md`

**Look for GOOD stocks:**
```
✅ GOOD SETUPS (3-5% portfolio):
   #1 NGPL 85/100 → Entry Rs.491 | Target Rs.534
   
This means:
- Score: 85/100 (strong)
- Buy at: Rs.491
- Sell target: Rs.534 (+10%)
- Position size: 3-5% of your capital
```

### Step 5: Read Phase 5 (Deep Dive)
**Files:** `08_*_*.md` (multiple files per stock)

For each GOOD stock, read:
- **Full analysis** → Overall verdict
- **Tech score** → Technical alignment
- **Order flow** → Is buying pressure strong?
- **Dividend** → Bonus coming?

### Step 6: Make Decision
Use the decision framework in `00_MASTER_SUMMARY.md`:

```
IF market strong (>70% above 50-DMA)
   AND sector rotation positive
   AND GOOD stocks exist
   AND institutional buying
   → Consider entry (3-5% size)

IF market weak (<30% above 50-DMA)
   → Stay cash, wait

IF uncertain
   → Paper trade first!
```

---

## ⏰ NEPSE Trading Hours

**Market Open:** Sunday-Thursday, 11:00 AM - 3:00 PM Nepal Time  
**Market Closed:** Friday & Saturday

The logger **automatically detects** market hours. If you run it on Friday, it will skip and wait.

---

## 🛡️ Safety Features

### 1. Timeout Protection
Each command has 2-minute timeout. If stuck, it moves to next command.

### 2. Error Handling
If a command fails, logs the error and continues.

### 3. Market Hours Check
Only runs during NEPSE hours (or you can force with `--now`).

### 4. Separate Files
Each analysis in its own file - easy to review one at a time.

---

## 💡 Usage Tips

### Daily Workflow (Recommended)
```bash
# Morning: Run once after market opens
cd /run/media/sijanpaudel/New\ Volume/Nepse
python nepse_ai_trading/tools/auto_market_logger.py --now

# Wait 5-10 minutes...

# Read analysis
cd market_logs
ls -lt | head -5      # Find latest session
cd 2026-03-23_1130    # Enter session folder
cat 00_MASTER_SUMMARY.md | less   # Read master guide
```

### Weekly Workflow
```bash
# Sunday 11:00 AM: Start scheduler
python nepse_ai_trading/tools/auto_market_logger.py --schedule

# Let it run all week (3 times daily)
# Analyze on Sunday evening offline
```

### Set-and-Forget Workflow
```bash
# Start daemon once
nohup python nepse_ai_trading/tools/auto_market_logger.py --daemon > /tmp/market.log 2>&1 &

# Check logs daily
cd market_logs
ls -lt | head -10     # See all sessions
```

---

## 📊 Example Session Output

```
market_logs/2026-03-23_1130/
├── 00_MASTER_SUMMARY.md        (3 KB)
├── 01_market_positioning.md    (2 KB)
├── 02_market_heatmap.md        (2 KB)
├── 03_sector_rotation.md       (3 KB)
├── 04_smart_money_flow.md      (4 KB)
├── 05_bulk_deals.md            (2 KB)
├── 06_momentum_scan.md         (8 KB)  ← Most important!
├── 07_portfolio_review.md      (2 KB)
├── 08_1_analysis_NGPL.md       (12 KB)
├── 08_1_techscore_NGPL.md      (3 KB)
├── 08_1_orderflow_NGPL.md      (2 KB)
└── 08_1_dividend_NGPL.md       (2 KB)

Total: ~45 KB of analysis per session
```

---

## 🚨 Troubleshooting

### Logger hangs on a command
**Cause:** Command taking >2 minutes  
**Solution:** It will auto-timeout and continue

### No stocks in deep dive
**Cause:** No GOOD stocks found in scan  
**Solution:** Check `06_momentum_scan.md` for RISKY stocks manually

### Daemon not running
**Check:** `ps aux | grep auto_market_logger`  
**Restart:** Kill old process, start new one

### Market closed but want to test
**Solution:** Use `--now` flag to force run anytime

---

## 🎓 Learning Path for Beginners

### Week 1: Learn to Read
- Run `--now` daily
- Read `00_MASTER_SUMMARY.md` each time
- Don't trade yet, just observe

### Week 2: Identify Patterns
- Compare Monday vs Wednesday sessions
- Notice sector rotation patterns
- Track GOOD stocks that appear multiple times

### Week 3: Paper Trading
- Use `--buy-picks` command from GOOD stocks
- Track in `--portfolio`
- See if you would have made money

### Week 4: Small Real Trade
- If confident, start with 1-2% position sizes
- Only trade GOOD stocks
- Always set stop loss

---

## 🔗 Related Commands

After reviewing automated logs, you can run specific commands manually:

```bash
# Deep dive a specific stock
python paper_trader.py --analyze NGPL

# Check portfolio
python paper_trader.py --portfolio

# Paper trade a GOOD stock
python paper_trader.py --buy-picks NGPL PPCL

# Check just one metric
python paper_trader.py --heatmap
```

---

## ⚡ Advanced Usage

### Run for specific stock list
Edit `auto_market_logger.py` line 246 to override top stocks:
```python
top_stocks = ["NGPL", "NABIL", "PPCL"]  # Your watchlist
```

### Change schedule times
Edit lines 509-511:
```python
schedule.every().day.at("11:15").do(run_if_market_open)  # Earlier
schedule.every().day.at("14:50").do(run_if_market_open)  # Later
```

### Add more commands
Add to `run_full_analysis()` method:
```python
output, _ = self._run_command(
    ["python", str(PAPER_TRADER), "--your-command"],
    "Your Description"
)
self._save_section("09_your_file.md", output, "Your Title")
```

---

## 📝 Summary

**What:** Automated market analysis runner  
**When:** 3 times daily during NEPSE hours (or on-demand)  
**Where:** Saves to `market_logs/` with timestamps  
**How:** Read `00_MASTER_SUMMARY.md` first  
**Why:** Learn patterns without running commands manually  

---

## 🚀 Quick Command Reference

```bash
# Run once now
python auto_market_logger.py --now

# Schedule (3x daily)
python auto_market_logger.py --schedule

# Background daemon
nohup python auto_market_logger.py --daemon > /tmp/market.log 2>&1 &

# View latest session
cd market_logs && ls -lt | head -5

# Kill daemon
pkill -f auto_market_logger
```

---

**Perfect for beginners!** No need to memorize commands. Just run the logger and learn from the output! 🎉
