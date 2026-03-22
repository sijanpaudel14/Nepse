"""
Telegram Bot for sending trading alerts.

Uses python-telegram-bot for async Telegram integration.
"""

import asyncio
from typing import List, Optional
from datetime import datetime
from loguru import logger

try:
    from telegram import Bot
    from telegram.constants import ParseMode
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("python-telegram-bot not installed. Telegram notifications disabled.")

from core.config import settings
from core.exceptions import NotificationError
from intelligence.signal_aggregator import FinalSignal


class TelegramNotifier:
    """
    Telegram notification sender.
    """
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        """
        Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram bot token
            chat_id: Target chat ID for messages
        """
        if not TELEGRAM_AVAILABLE:
            raise ImportError("python-telegram-bot required. Run: pip install python-telegram-bot")
        
        self.bot_token = bot_token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id
        
        if not self.bot_token or not self.chat_id:
            raise NotificationError("Telegram bot token and chat ID required")
        
        self.bot = Bot(token=self.bot_token)
    
    async def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message to Telegram.
        
        Args:
            message: Message text
            parse_mode: Markdown or HTML
            
        Returns:
            True if sent successfully
        """
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode,
            )
            logger.info("Telegram message sent successfully")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
            raise NotificationError(f"Failed to send Telegram message: {e}")
    
    async def send_signal_alert(self, signal: FinalSignal) -> bool:
        """
        Send a trading signal alert.
        
        Args:
            signal: FinalSignal to send
            
        Returns:
            True if sent successfully
        """
        message = self._format_signal_message(signal)
        return await self.send_message(message)
    
    async def send_daily_summary(self, signals: List[FinalSignal]) -> bool:
        """
        Send a daily summary of all signals.
        
        Args:
            signals: List of FinalSignals
            
        Returns:
            True if sent successfully
        """
        message = self._format_daily_summary(signals)
        return await self.send_message(message)
    
    def _format_signal_message(self, signal: FinalSignal) -> str:
        """Format a single signal for Telegram."""
        # Emoji based on verdict
        verdict_emoji = {
            "STRONG_BUY": "🟢🔥",
            "BUY": "🟢",
            "RISKY": "🟡",
            "AVOID": "🔴",
        }
        
        emoji = verdict_emoji.get(signal.final_verdict, "⚪")
        
        # Calculate percentages
        if signal.entry_price > 0:
            target_pct = ((signal.target_price / signal.entry_price) - 1) * 100
            sl_pct = ((signal.stop_loss / signal.entry_price) - 1) * 100
        else:
            target_pct = 0
            sl_pct = 0
        
        lines = [
            f"{emoji} *{signal.symbol}* - {signal.final_verdict}",
            "",
            "📊 *Technical Analysis*",
            f"• Strategy: {signal.primary_strategy}",
            f"• TA Score: {signal.ta_confidence:.1f}/10",
            "",
            "💰 *Trade Setup*",
            f"• Entry: Rs. {signal.entry_price:.2f}",
            f"• Target: Rs. {signal.target_price:.2f} (+{target_pct:.1f}%)",
            f"• Stop Loss: Rs. {signal.stop_loss:.2f} ({sl_pct:.1f}%)",
        ]
        
        if signal.ai_verdict:
            lines.extend([
                "",
                "🤖 *AI Analysis*",
                f"• Confidence: {signal.ai_verdict.confidence:.1f}/10",
                f"• {signal.reasoning[:150]}...",
            ])
        
        if signal.news_items:
            lines.append("")
            lines.append("📰 *Recent News*")
            for news in signal.news_items[:2]:
                title = news.title[:50] + "..." if len(news.title) > 50 else news.title
                lines.append(f"• {title}")
        
        if signal.risks:
            lines.extend([
                "",
                f"⚠️ *Risks*: {signal.risks[:100]}",
            ])
        
        lines.extend([
            "",
            f"🎯 *Final Score*: {signal.final_confidence}/10",
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')} NPT",
        ])
        
        return "\n".join(lines)
    
    def _format_daily_summary(self, signals: List[FinalSignal]) -> str:
        """Format daily summary for Telegram."""
        now = datetime.now()
        
        lines = [
            "📊 *NEPSE AI TRADING SIGNALS*",
            f"📅 {now.strftime('%Y-%m-%d')}",
            "",
            f"Found {len(signals)} potential trades:",
            "",
        ]
        
        # Group by verdict
        strong_buys = [s for s in signals if s.final_verdict == "STRONG_BUY"]
        buys = [s for s in signals if s.final_verdict == "BUY"]
        risky = [s for s in signals if s.final_verdict == "RISKY"]
        
        if strong_buys:
            lines.append("🔥 *STRONG BUYS:*")
            for s in strong_buys[:3]:
                lines.append(f"• {s.symbol} ({s.final_confidence}/10) @ Rs.{s.entry_price:.0f}")
            lines.append("")
        
        if buys:
            lines.append("🟢 *BUYS:*")
            for s in buys[:5]:
                lines.append(f"• {s.symbol} ({s.final_confidence}/10) @ Rs.{s.entry_price:.0f}")
            lines.append("")
        
        if risky:
            lines.append("🟡 *RISKY (Review):*")
            for s in risky[:3]:
                lines.append(f"• {s.symbol} ({s.final_confidence}/10)")
        
        lines.extend([
            "",
            "─" * 20,
            "⚠️ _Paper trade first. Not financial advice._",
        ])
        
        return "\n".join(lines)


def send_telegram_alert(signal: FinalSignal) -> bool:
    """
    Convenience function to send a Telegram alert.
    
    Args:
        signal: FinalSignal to send
        
    Returns:
        True if sent successfully
    """
    if not TELEGRAM_AVAILABLE:
        logger.warning("Telegram not available, skipping notification")
        return False
    
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram not configured, skipping notification")
        return False
    
    try:
        notifier = TelegramNotifier()
        return asyncio.run(notifier.send_signal_alert(signal))
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
        return False


def send_daily_summary(signals: List[FinalSignal]) -> bool:
    """
    Send daily summary to Telegram.
    
    Args:
        signals: List of FinalSignals
        
    Returns:
        True if sent successfully
    """
    if not TELEGRAM_AVAILABLE or not settings.telegram_bot_token:
        logger.warning("Telegram not available")
        return False
    
    try:
        notifier = TelegramNotifier()
        return asyncio.run(notifier.send_daily_summary(signals))
    except Exception as e:
        logger.error(f"Failed to send daily summary: {e}")
        return False
