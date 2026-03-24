# 📱 NEPSE AI Trading Bot - Telegram Setup Guide

Get real-time trading alerts directly to your phone! This guide walks you through setting up Telegram notifications for your NEPSE AI Trading Bot.

---

## 🎯 What You'll Get

Once configured, you'll receive:
- **Daily Trading Signals** - Top picks with entry/target/stop-loss
- **Real-time Alerts** - When high-scoring opportunities appear
- **Crash Notifications** - If the bot encounters errors
- **Market Regime Updates** - Bull/Bear/Panic mode alerts

Example alert:
```
🟢🔥 DHPL - STRONG_BUY

📊 Technical Analysis
• Strategy: MOMENTUM
• TA Score: 8.5/10

💰 Trade Setup
• Entry: Rs. 332.00
• Target: Rs. 365.20 (+10.0%)
• Stop Loss: Rs. 310.42 (-6.5%)

🤖 AI Analysis
• Confidence: 8.2/10
• Strong volume surge with bullish EMA crossover...

🎯 Final Score: 86/100
📅 2026-03-22 14:30 NPT
```

---

## 📋 Step 1: Create Your Telegram Bot

### 1.1 Open BotFather
1. Open Telegram app on your phone
2. Search for `@BotFather` (official Telegram bot)
3. Click **Start** to begin

### 1.2 Create New Bot
Send these commands to BotFather:

```
/newbot
```

BotFather will ask:
```
Alright, a new bot. How are we going to call it? 
Please choose a name for your bot.
```

Reply with a name:
```
My NEPSE Trading Bot
```

Then BotFather asks for username:
```
Good. Now let's choose a username for your bot. 
It must end in `bot`. Like this, for example: TetrisBot or tetris_bot.
```

Reply with a unique username:
```
mynepse_trading_bot
```
(Must end with `bot` and be unique globally)

### 1.3 Save Your Bot Token
BotFather will respond with:
```
Done! Congratulations on your new bot. You will find it at t.me/mynepse_trading_bot. 
You can now add a description...

Use this token to access the HTTP API:
7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxx

Keep your token secure and store it safely!
```

**🔐 SAVE THIS TOKEN!** This is your `TELEGRAM_BOT_TOKEN`

---

## 📋 Step 2: Get Your Chat ID

Your Chat ID tells the bot WHERE to send messages.

### Method 1: Using @userinfobot (Easiest)
1. Search for `@userinfobot` on Telegram
2. Click **Start**
3. The bot immediately replies with your info:
   ```
   Id: 123456789
   First: Your Name
   Lang: en
   ```
4. **Save the `Id` number** - This is your `TELEGRAM_CHAT_ID`

### Method 2: Using @RawDataBot
1. Search for `@RawDataBot` on Telegram
2. Click **Start**
3. Look for `"id":` in the response
4. Save that number as your `TELEGRAM_CHAT_ID`

### Method 3: Manual (for Groups)
If you want alerts in a GROUP chat:
1. Add your bot to the group
2. Send any message in the group
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find `"chat":{"id":-XXXXXXXXX}` (group IDs are negative)
5. Save that number (including the minus sign)

---

## 📋 Step 3: Configure Your .env File

Open your `.env` file in the project directory:

```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse/nepse_ai_trading
nano .env
```

Add/update these lines:

```env
# ============ TELEGRAM ============
TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=123456789
```

**Replace with YOUR actual values!**

---

## 📋 Step 4: Install Telegram Library

```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse/nepse_ai_trading
pip install python-telegram-bot
```

---

## 📋 Step 5: Test Your Setup

### Quick Test Command
```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse/nepse_ai_trading
python3 -c "
from notifications.telegram_bot import TelegramNotifier
import asyncio

notifier = TelegramNotifier()
asyncio.run(notifier.send_message('🎉 NEPSE AI Bot Connected Successfully!'))
print('✅ Message sent! Check your Telegram.')
"
```

If configured correctly, you'll receive a test message on Telegram!

---

## 🚀 Step 6: Enable Telegram in Scans

### Option 1: Automatic Alerts (After Each Scan)
The bot automatically sends crash alerts. For trading alerts, use the `--with-telegram` flag:

```bash
# Run scan with Telegram notification
python tools/paper_trader.py --action=scan --strategy=momentum --with-telegram
```

### Option 2: Scheduled Daily Alerts
Set up a cron job to run daily at 2:45 PM (Golden Hour):

```bash
# Edit crontab
crontab -e

# Add this line (runs Monday-Friday at 2:45 PM Nepal Time)
45 14 * * 1-5 cd /run/media/sijanpaudel/New\ Volume/Nepse/nepse_ai_trading && python3 tools/paper_trader.py --action=scan --strategy=momentum --with-telegram >> /tmp/nepse_scan.log 2>&1
```

---

## 📱 What Each Alert Type Looks Like

### 1. Daily Trading Signal
```
📊 NEPSE AI TRADING SIGNALS
📅 2026-03-22

Found 5 potential trades:

🔥 STRONG BUYS:
• DHPL (86/10) @ Rs.332
• NGPL (82/10) @ Rs.484

🟢 BUYS:
• MHNL (80/10) @ Rs.318
• HDHPC (78/10) @ Rs.265

🟡 RISKY (Review):
• UMHL (75/10)

────────────────────
⚠️ Paper trade first. Not financial advice.
```

### 2. Individual Stock Alert
```
🟢🔥 DHPL - STRONG_BUY

📊 Technical Analysis
• Strategy: MOMENTUM
• TA Score: 8.6/10

💰 Trade Setup
• Entry: Rs. 336.98
• Target: Rs. 366.78 (+8.8%)
• Stop Loss: Rs. 309.89 (-8.0%)

🤖 AI Analysis
• Confidence: 8.5/10
• Strong bullish momentum with EMA crossover...

⚠️ Risks: High PE ratio, monitor for reversal

🎯 Final Score: 86/100
📅 2026-03-22 14:45 NPT
```

### 3. Crash/Error Alert
```
🚨 NEPSE AI Trading Bot CRASHED!

Action: scan
Time: 2026-03-22 14:30:00
Error: API timeout on NEPSE server

The bot will automatically retry on next scheduled run.
```

---

## 🔧 Troubleshooting

### "Telegram not configured" Error
- Check your `.env` file has both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Make sure there are no extra spaces or quotes around the values

### "Unauthorized" Error
- Your bot token is incorrect
- Go back to @BotFather and copy the token again

### "Chat not found" Error
- Your chat ID is wrong
- You haven't started a conversation with your bot yet
- **Solution:** Open your bot in Telegram and send `/start`

### Messages Not Arriving
1. Make sure you've clicked "Start" on your bot
2. Check if bot is blocked (unblock it)
3. For groups: Make sure bot has permission to send messages

### Rate Limiting
Telegram limits: max 30 messages/second to same chat
- Don't spam the scan command
- The bot handles this automatically for bulk alerts

---

## 🎯 Pro Tips

### 1. Create a Trading Channel
Instead of personal DMs, create a private Telegram channel:
1. Create new channel → Make it private
2. Add your bot as administrator
3. Get channel ID using @RawDataBot (forward any message from channel)
4. Use the channel ID (format: `-100XXXXXXXXX`) as your `TELEGRAM_CHAT_ID`

**Benefits:** 
- History of all signals
- Share with trusted friends
- Mute notifications during market hours, review later

### 2. Set Notification Preferences
In Telegram, long-press on your bot → Notifications:
- Enable sound only for strong buy signals
- Keep silent for daily summaries

### 3. Pin Important Messages
Pin the daily summary message so you can quickly reference today's picks.

---

## 📅 Recommended Schedule

| Time | Action | Command |
|------|--------|---------|
| 9:00 AM | Morning prep (no alerts) | Manual review |
| 12:30 PM | Midday scan | `--action=scan --with-telegram` |
| 2:45 PM | Golden Hour scan | `--action=scan --with-telegram` |
| 6:00 PM | After-market analysis | `--action=analyze --symbol=XXX` |

---

## 🔐 Security Best Practices

1. **Never share your bot token publicly**
2. **Don't commit `.env` to Git** (it's already in `.gitignore`)
3. **Use a dedicated bot** - Don't reuse bots for other purposes
4. **Rotate token periodically** - Use `/revoke` in @BotFather if compromised

---

## ✅ Quick Setup Checklist

- [ ] Created bot with @BotFather
- [ ] Saved `TELEGRAM_BOT_TOKEN` 
- [ ] Got Chat ID from @userinfobot
- [ ] Saved `TELEGRAM_CHAT_ID`
- [ ] Updated `.env` file
- [ ] Installed `python-telegram-bot`
- [ ] Tested with quick test command
- [ ] Received test message ✓
- [ ] Set up cron job for daily alerts (optional)

---

**🎉 You're all set! Happy Trading!**

*Remember: Telegram alerts are for information only. Always verify signals before trading and manage your risk.*
