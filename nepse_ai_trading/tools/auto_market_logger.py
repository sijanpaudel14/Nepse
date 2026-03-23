#!/usr/bin/env python3
"""
🚀 NEPSE AUTOMATED MARKET LOGGER
================================

Automatically runs all trading intelligence commands during NEPSE hours
and logs output to timestamped Markdown files for offline analysis.

Perfect for beginners - just run once and review all analysis later!

Usage:
    python auto_market_logger.py --now        # Run once immediately
    python auto_market_logger.py --schedule   # Run automatically at market hours
    python auto_market_logger.py --daemon     # Background service (keeps running)
"""

import sys
import os
from pathlib import Path
from datetime import datetime, time
import subprocess
import time as time_module
from typing import List, Tuple
import schedule
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")

# NEPSE Trading Hours (Nepal Time)
MARKET_OPEN = time(11, 0)   # 11:00 AM
MARKET_CLOSE = time(15, 0)  # 3:00 PM
NEPSE_CLOSED_DAYS = [4, 5]  # Friday=4, Saturday=5 (NEPSE closed)

# Output directory
LOGS_DIR = Path(__file__).parent.parent.parent / "market_logs"
LOGS_DIR.mkdir(exist_ok=True)

# Paper trader path
PAPER_TRADER = Path(__file__).parent / "paper_trader.py"


class MarketLogger:
    """Automated market intelligence logger."""
    
    def __init__(self, output_dir: Path = LOGS_DIR):
        self.output_dir = output_dir
        self.session_dir = None
        self.current_log = []
        
    def _create_session_dir(self) -> Path:
        """Create timestamped session directory."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        session_dir = self.output_dir / timestamp
        session_dir.mkdir(exist_ok=True)
        return session_dir
    
    def _run_command(self, cmd: List[str], description: str, timeout: int = None) -> Tuple[str, bool]:
        """
        Run a command and capture output.
        
        Args:
            cmd: Command and arguments
            description: Human-readable description
            timeout: Custom timeout in seconds (default: auto-detect)
            
        Returns:
            Tuple of (output_text, success)
        """
        # Auto-detect timeout based on command
        if timeout is None:
            # Slow commands need more time (API-heavy)
            if "--smart-money" in cmd or "--bulk-deals" in cmd:
                timeout = 300  # 5 minutes for API-heavy commands
            elif "--scan" in cmd:
                timeout = 360  # 6 minutes for full market scans (was 3min, too short!)
            else:
                timeout = 120  # 2 minutes default
        
        logger.info(f"📊 Running: {description} (timeout: {timeout}s)")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=PAPER_TRADER.parent
            )
            
            output = result.stdout
            if result.stderr and "ERROR" in result.stderr:
                output += f"\n\n⚠️ Warnings:\n{result.stderr}"
            
            success = result.returncode == 0
            
            if success:
                logger.info(f"✅ {description} - Complete")
            else:
                logger.warning(f"⚠️ {description} - Completed with warnings")
            
            return output, success
            
        except subprocess.TimeoutExpired:
            logger.error(f"❌ {description} - Timeout (>{timeout//60}min)")
            return f"# ⚠️ Command timed out after {timeout} seconds\n\nThis usually means:\n- Too many API calls (rate limiting)\n- Network issues\n- ShareHub API slow response\n\nTry running manually: python paper_trader.py {' '.join(cmd[-2:])}\n", False
        except Exception as e:
            logger.error(f"❌ {description} - Error: {e}")
            return f"# ❌ Error: {str(e)}\n", False
    
    def _save_section(self, filename: str, content: str, description: str):
        """Save a section to its own markdown file."""
        filepath = self.session_dir / filename
        
        header = f"""# {description}
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Session:** {self.session_dir.name}

---

"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(header + content)
        
        logger.info(f"💾 Saved: {filename}")
    
    def run_full_analysis(self) -> Path:
        """
        Run complete market analysis in optimal order for beginners.
        
        Returns:
            Path to session directory with all logs
        """
        self.session_dir = self._create_session_dir()
        logger.info(f"🚀 Starting NEPSE Market Analysis Session")
        logger.info(f"📁 Output: {self.session_dir}")
        logger.info(f"⏱️  Estimated time: 13-15 minutes")
        logger.info(f"")
        
        total_phases = 5
        current_phase = 0
        
        master_log = []
        master_log.append(f"# 📊 NEPSE MARKET ANALYSIS SESSION\n")
        master_log.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        master_log.append(f"**Session ID:** {self.session_dir.name}\n\n")
        master_log.append("---\n\n")
        
        # ============================================================
        # PHASE 1: MARKET OVERVIEW (Understand overall market first)
        # ============================================================
        current_phase += 1
        logger.info(f"")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"📊 PHASE {current_phase}/{total_phases}: MARKET OVERVIEW")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"")
        
        master_log.append("## 🌍 PHASE 1: MARKET OVERVIEW\n\n")
        master_log.append("*Understand the overall market condition before diving into stocks.*\n\n")
        
        # 1. Market Positioning - Are we at top or bottom?
        output, _ = self._run_command(
            ["python", str(PAPER_TRADER), "--positioning"],
            "Market Positioning (Overbought/Oversold)"
        )
        self._save_section("01_market_positioning.md", output, "Market Positioning")
        master_log.append("### 1️⃣ Market Positioning\n")
        master_log.append("See: `01_market_positioning.md`\n\n")
        
        # 2. Market Heatmap - How many stocks are green/red?
        output, _ = self._run_command(
            ["python", str(PAPER_TRADER), "--heatmap"],
            "Market Heatmap (Breadth Analysis)"
        )
        self._save_section("02_market_heatmap.md", output, "Market Heatmap")
        master_log.append("### 2️⃣ Market Heatmap\n")
        master_log.append("See: `02_market_heatmap.md`\n\n")
        
        # 3. Sector Rotation - Which sectors are leading?
        output, _ = self._run_command(
            ["python", str(PAPER_TRADER), "--sector-rotation"],
            "Sector Rotation (Money Flow)"
        )
        self._save_section("03_sector_rotation.md", output, "Sector Rotation")
        master_log.append("### 3️⃣ Sector Rotation\n")
        master_log.append("See: `03_sector_rotation.md`\n\n")
        
        master_log.append("**📝 What to look for in Phase 1:**\n")
        master_log.append("- If >70% stocks above 50-DMA → Market strong\n")
        master_log.append("- If >80% stocks green today → Possible top (caution)\n")
        master_log.append("- Leading sectors = Where money is flowing (buy these)\n\n")
        master_log.append("---\n\n")
        
        # ============================================================
        # PHASE 2: INSTITUTIONAL ACTIVITY (Follow smart money)
        # ============================================================
        current_phase += 1
        logger.info(f"")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"💰 PHASE {current_phase}/{total_phases}: INSTITUTIONAL ACTIVITY (Slow - please wait)")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"")
        
        master_log.append("## 💰 PHASE 2: INSTITUTIONAL ACTIVITY\n\n")
        master_log.append("*Follow the institutions - they know before retail traders.*\n\n")
        
        # 4. Smart Money Flow - What are institutions buying?
        output, _ = self._run_command(
            ["python", str(PAPER_TRADER), "--smart-money"],
            "Smart Money Flow (Institutional Buying)"
        )
        self._save_section("04_smart_money_flow.md", output, "Smart Money Flow")
        master_log.append("### 4️⃣ Smart Money Flow\n")
        master_log.append("See: `04_smart_money_flow.md`\n\n")
        
        # 5. Bulk Deals - Any large insider trades?
        output, _ = self._run_command(
            ["python", str(PAPER_TRADER), "--bulk-deals"],
            "Bulk Deals (Insider Trades)"
        )
        self._save_section("05_bulk_deals.md", output, "Bulk Deals")
        master_log.append("### 5️⃣ Bulk Deals\n")
        master_log.append("See: `05_bulk_deals.md`\n\n")
        
        master_log.append("**📝 What to look for in Phase 2:**\n")
        master_log.append("- Stocks with institutional accumulation = Strong candidates\n")
        master_log.append("- Bulk buying (>10L shares) = Insiders know something\n")
        master_log.append("- Bulk selling = Stay away!\n\n")
        master_log.append("---\n\n")
        
        # ============================================================
        # PHASE 3: MOMENTUM SCAN (Find tradeable setups)
        # ============================================================
        current_phase += 1
        logger.info(f"")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"🚀 PHASE {current_phase}/{total_phases}: MOMENTUM SCAN")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"")
        
        master_log.append("## 🚀 PHASE 3: MOMENTUM SCAN\n\n")
        master_log.append("*Find stocks with technical momentum + fundamental safety.*\n\n")
        
        # 6. Full Momentum Scan
        output, _ = self._run_command(
            ["python", str(PAPER_TRADER), "--scan", "--strategy=momentum"],
            "Momentum Scan (GOOD/RISKY/WATCH)"
        )
        
        # Add scoring guide to the output
        scoring_guide = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SCORE INTERPRETATION GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ GOOD (80-100 points):
   - Action: Real trade (3% position) OR paper trade
   - Why: Strong technicals + fundamentals + low manipulation risk
   - Example: Score 85 = Buy Rs.491, Target Rs.540 (+10%), Stop Rs.467 (-5%)

⚠️ RISKY (60-79 points):
   - Action: Paper trade ONLY (1% if real)
   - Why: Good score but has warnings (RSI>70, negative EPS, etc.)
   - Example: Score 72 = Paper only, watch for confirmation

📋 WATCH (40-59 points):
   - Action: Monitor only, NO TRADE
   - Why: Developing setup, not ready yet
   - Example: Score 55 = Wait for 60+ before considering

🚫 VETO (<40 points):
   - Action: NEVER TRADE (paper only for learning)
   - Why: Multiple red flags (manipulation, weak fundamentals)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        output = scoring_guide + "\n" + output
        
        self._save_section("06_momentum_scan.md", output, "Momentum Scan")
        master_log.append("### 6️⃣ Momentum Scan\n")
        master_log.append("See: `06_momentum_scan.md`\n\n")
        
        master_log.append("**📝 What to look for in Phase 3:**\n")
        master_log.append("- **GOOD** stocks = Safe for small real trade (3-5%)\n")
        master_log.append("- **RISKY** stocks = Paper trade or tiny size (1-2%)\n")
        master_log.append("- **WATCH** stocks = Observe, don't trade yet\n\n")
        master_log.append("---\n\n")
        
        # ============================================================
        # PHASE 4: PORTFOLIO MANAGEMENT (If you have holdings)
        # ============================================================
        current_phase += 1
        logger.info(f"")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"💼 PHASE {current_phase}/{total_phases}: PORTFOLIO MANAGEMENT")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"")
        
        master_log.append("## 💼 PHASE 4: PORTFOLIO MANAGEMENT\n\n")
        master_log.append("*Review your current holdings and optimize allocation.*\n\n")
        
        # 7. Portfolio Review
        output, _ = self._run_command(
            ["python", str(PAPER_TRADER), "--portfolio"],
            "Portfolio Review (P&L + Signals)"
        )
        self._save_section("07_portfolio_review.md", output, "Portfolio Review")
        master_log.append("### 7️⃣ Portfolio Review\n")
        master_log.append("See: `07_portfolio_review.md`\n\n")
        
        master_log.append("**📝 What to look for in Phase 4:**\n")
        master_log.append("- Any SELL signals? (Profit target hit or stop loss)\n")
        master_log.append("- Days held > 7? (Review for exit)\n")
        master_log.append("- Negative P&L? (Consider cutting losses)\n\n")
        master_log.append("---\n\n")
        
        # ============================================================
        # PHASE 5: DEEP DIVE (Analyze top candidates)
        # ============================================================
        current_phase += 1
        logger.info(f"")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"🔬 PHASE {current_phase}/{total_phases}: DEEP DIVE ANALYSIS")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"")
        
        master_log.append("## 🔬 PHASE 5: DEEP DIVE ANALYSIS\n\n")
        master_log.append("*Detailed analysis of top 3 candidates from momentum scan.*\n\n")
        
        # Get top stocks from scan (parse the scan output)
        scan_file = self.session_dir / "06_momentum_scan.md"
        top_stocks = self._extract_top_stocks(scan_file)
        
        if top_stocks:
            for i, symbol in enumerate(top_stocks[:3], 1):
                master_log.append(f"### 🎯 Stock {i}: {symbol}\n\n")
                
                # Full analysis
                output, _ = self._run_command(
                    ["python", str(PAPER_TRADER), "--analyze", symbol],
                    f"Full Analysis: {symbol}"
                )
                self._save_section(f"08_{i}_analysis_{symbol}.md", output, f"Analysis: {symbol}")
                master_log.append(f"**Full Report:** `08_{i}_analysis_{symbol}.md`\n\n")
                
                # Technical composite score
                output, _ = self._run_command(
                    ["python", str(PAPER_TRADER), "--tech-score", symbol],
                    f"Technical Score: {symbol}"
                )
                self._save_section(f"08_{i}_techscore_{symbol}.md", output, f"Technical Score: {symbol}")
                master_log.append(f"**Tech Score:** `08_{i}_techscore_{symbol}.md`\n\n")
                
                # Order flow
                output, _ = self._run_command(
                    ["python", str(PAPER_TRADER), "--order-flow", symbol],
                    f"Order Flow: {symbol}"
                )
                self._save_section(f"08_{i}_orderflow_{symbol}.md", output, f"Order Flow: {symbol}")
                master_log.append(f"**Order Flow:** `08_{i}_orderflow_{symbol}.md`\n\n")
                
                # Dividend forecast
                output, _ = self._run_command(
                    ["python", str(PAPER_TRADER), "--dividend-forecast", symbol],
                    f"Dividend Forecast: {symbol}"
                )
                self._save_section(f"08_{i}_dividend_{symbol}.md", output, f"Dividend Forecast: {symbol}")
                master_log.append(f"**Dividend:** `08_{i}_dividend_{symbol}.md`\n\n")
                
                master_log.append("---\n\n")
        else:
            master_log.append("⚠️ No GOOD stocks found in scan. Check RISKY category manually.\n\n")
        
        # ============================================================
        # FINAL SUMMARY
        # ============================================================
        master_log.append("## 📋 HOW TO USE THIS ANALYSIS\n\n")
        master_log.append("### Step-by-Step Beginner Workflow:\n\n")
        master_log.append("1. **Read Phase 1** → Understand if market is strong/weak\n")
        master_log.append("2. **Read Phase 2** → See what institutions are buying\n")
        master_log.append("3. **Read Phase 3** → Check GOOD stocks list\n")
        master_log.append("4. **Read Phase 5** → Deep dive top 3 stocks\n")
        master_log.append("5. **Decision Time:**\n")
        master_log.append("   - If market strong + GOOD stocks + institutional buying → Consider entry\n")
        master_log.append("   - If market weak → Stay cash, wait for better setup\n")
        master_log.append("   - If uncertain → Paper trade first!\n\n")
        master_log.append("### 🚨 Key Rules:\n\n")
        master_log.append("- Only trade GOOD stocks (never trade VETO)\n")
        master_log.append("- Position size: 3-5% per stock maximum\n")
        master_log.append("- Always set stop loss at -5%\n")
        master_log.append("- Take profit at +10%\n")
        master_log.append("- Hold max 7 days if no target hit\n\n")
        master_log.append("### 📁 Files Generated:\n\n")
        
        # List all files
        for md_file in sorted(self.session_dir.glob("*.md")):
            if md_file.name != "00_MASTER_SUMMARY.md":
                master_log.append(f"- `{md_file.name}`\n")
        
        master_log.append("\n---\n\n")
        master_log.append(f"**Session completed at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        master_log.append(f"**Total files:** {len(list(self.session_dir.glob('*.md')))} markdown files\n")
        
        # Save master summary
        master_summary = "\n".join(master_log)
        with open(self.session_dir / "00_MASTER_SUMMARY.md", 'w', encoding='utf-8') as f:
            f.write(master_summary)
        
        logger.info("✅ Analysis Complete!")
        logger.info(f"📁 All files saved to: {self.session_dir}")
        logger.info(f"📖 Start reading: 00_MASTER_SUMMARY.md")
        
        return self.session_dir
    
    def _extract_top_stocks(self, scan_file: Path) -> List[str]:
        """Extract top GOOD stocks from momentum scan output."""
        if not scan_file.exists():
            return []
        
        try:
            with open(scan_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for GOOD stocks section
            stocks = []
            in_good_section = False
            
            for line in content.split('\n'):
                if "GOOD SETUPS" in line or "✅ GOOD" in line:
                    in_good_section = True
                    continue
                
                if in_good_section:
                    if line.strip().startswith('#') and not line.startswith('##'):
                        # New section started
                        break
                    
                    # Extract stock symbols (format: #1 SYMBOL score → ...)
                    if line.strip() and '#' in line and '→' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part.startswith('#') and i + 1 < len(parts):
                                symbol = parts[i + 1]
                                if symbol.isupper() and 2 <= len(symbol) <= 8:
                                    stocks.append(symbol)
                                    break
            
            return stocks[:3]  # Top 3
            
        except Exception as e:
            logger.error(f"Failed to extract top stocks: {e}")
            return []


def is_market_hours() -> bool:
    """Check if current time is within NEPSE trading hours."""
    now = datetime.now()
    
    # Check if it's a trading day (Sunday-Thursday in Nepal)
    if now.weekday() in NEPSE_CLOSED_DAYS:
        return False
    
    # Check if within market hours
    current_time = now.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def run_once():
    """Run analysis once immediately."""
    logger.info("🚀 Running market analysis NOW...")
    ml = MarketLogger()
    session_dir = ml.run_full_analysis()
    logger.info(f"✅ Done! Check: {session_dir}")


def run_scheduled():
    """Run analysis on schedule (market open + mid-day + close)."""
    logger.info("📅 Scheduler started. Will run at:")
    logger.info("  - 11:30 AM (30 min after open)")
    logger.info("  - 1:00 PM (mid-day)")
    logger.info("  - 2:45 PM (15 min before close)")
    
    schedule.every().day.at("11:30").do(run_if_market_open)
    schedule.every().day.at("13:00").do(run_if_market_open)
    schedule.every().day.at("14:45").do(run_if_market_open)
    
    logger.info("⏰ Waiting for scheduled time...")
    
    while True:
        schedule.run_pending()
        time_module.sleep(60)  # Check every minute


def run_if_market_open():
    """Run analysis only if market is open."""
    if is_market_hours():
        logger.info("✅ Market is open, running analysis...")
        run_once()
    else:
        logger.info("⏸️ Market is closed, skipping...")


def run_daemon():
    """Run as daemon - check every 30 minutes during market hours."""
    logger.info("🔄 Daemon mode started")
    logger.info("Will check every 30 minutes during market hours")
    
    while True:
        if is_market_hours():
            logger.info("✅ Market is open, running analysis...")
            run_once()
            logger.info("⏸️ Sleeping 30 minutes...")
            time_module.sleep(1800)  # 30 minutes
        else:
            now = datetime.now()
            logger.info(f"⏸️ Market closed. Current time: {now.strftime('%H:%M')}")
            logger.info("   NEPSE hours: 11:00-15:00 (Sun-Thu)")
            logger.info("⏳ Next check in 15 minutes...")
            time_module.sleep(900)  # 15 minutes


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage:")
        print("  python auto_market_logger.py --now        # Run once now")
        print("  python auto_market_logger.py --schedule   # Run at 11:30, 13:00, 14:45")
        print("  python auto_market_logger.py --daemon     # Run every 30 min during market")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "--now":
        run_once()
    elif mode == "--schedule":
        run_scheduled()
    elif mode == "--daemon":
        run_daemon()
    else:
        logger.error(f"Unknown mode: {mode}")
        logger.error("Use: --now, --schedule, or --daemon")
        sys.exit(1)


if __name__ == "__main__":
    main()
