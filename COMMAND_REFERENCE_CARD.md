# 🚀 NEPSE Intelligence Commands - Quick Reference Card

## 📋 9 Advanced Commands (Copy & Paste Ready)

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


# ========== SINGLE STOCK ANALYSIS ==========

# 7. Technical Composite Score
python nepse_ai_trading/tools/paper_trader.py --tech-score NGPL

# 8. Order Flow Analysis
python nepse_ai_trading/tools/paper_trader.py --order-flow NABIL

# 9. Dividend Forecast
python nepse_ai_trading/tools/paper_trader.py --dividend-forecast NABIL


# ========== PORTFOLIO ==========

# 10. Optimize Portfolio
python nepse_ai_trading/tools/paper_trader.py --optimize-portfolio GVL PPCL NABIL


# ========== EXISTING COMMANDS (Still Available) ==========

# Daily Scan
python nepse_ai_trading/tools/paper_trader.py --scan --strategy=momentum

# Deep Analysis
python nepse_ai_trading/tools/paper_trader.py --analyze NGPL

# Portfolio Status
python nepse_ai_trading/tools/paper_trader.py --portfolio
```

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
✅ Tech Score: 80+ with all timeframes aligned
✅ Order Flow: Delta positive (buyers control)
```

**BEARISH WARNING (All Red):**
```
🚨 Positioning: <30% above 50 SMA
🚨 Sector Rotation: Sector is LAGGING
🚨 Smart Money: Institutional distribution
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
alias nepse-scan='cd "/run/media/sijanpaudel/New Volume/Nepse" && python nepse_ai_trading/tools/paper_trader.py --scan --strategy=momentum'
alias nepse-port='cd "/run/media/sijanpaudel/New Volume/Nepse" && python nepse_ai_trading/tools/paper_trader.py --portfolio'

# Morning Routine (All 3 commands)
alias nepse-morning='nepse-pos && nepse-rot && nepse-smart'
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

## 🎓 Learning Path

**Week 1:** Master positioning & heatmap  
**Week 2:** Add sector rotation & smart money  
**Week 3:** Single stock analysis (tech-score, order-flow)  
**Week 4:** Full workflow integration

---

**Print this card. Keep it visible during trading hours.** 📌
