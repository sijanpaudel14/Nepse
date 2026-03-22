"""
Email Notification Module.

Sends trading signals and alerts via email.
Uses aiosmtplib for async email sending.

Setup:
1. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD in .env
2. Set EMAIL_FROM and EMAIL_TO addresses

For Gmail:
- Enable "Less secure apps" or use App Password
- SMTP_HOST=smtp.gmail.com, SMTP_PORT=587
"""

import os
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime
from loguru import logger

try:
    import aiosmtplib
    SMTP_AVAILABLE = True
except ImportError:
    SMTP_AVAILABLE = False


class EmailNotifier:
    """
    Sends email notifications for trading signals.
    
    Usage:
        notifier = EmailNotifier()
        await notifier.send_signal_alert(signal)
        await notifier.send_daily_summary(signals)
    """
    
    def __init__(
        self,
        smtp_host: str = None,
        smtp_port: int = None,
        smtp_user: str = None,
        smtp_password: str = None,
        from_email: str = None,
        to_emails: List[str] = None,
    ):
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER", "")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD", "")
        self.from_email = from_email or os.getenv("EMAIL_FROM", self.smtp_user)
        self.to_emails = to_emails or [os.getenv("EMAIL_TO", "")]
        
        self.enabled = bool(self.smtp_user and self.smtp_password)
        
        if not SMTP_AVAILABLE:
            logger.warning("aiosmtplib not installed. Email notifications disabled.")
            self.enabled = False
    
    async def send_email(
        self,
        subject: str,
        body: str,
        html: bool = True,
    ) -> bool:
        """
        Send an email.
        
        Args:
            subject: Email subject
            body: Email body (HTML or plain text)
            html: If True, send as HTML email
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.debug("Email notifications disabled")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.to_emails)
            
            # Attach body
            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type))
            
            # Send
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True,
            )
            
            logger.info(f"Email sent: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    async def send_signal_alert(self, signal) -> bool:
        """
        Send alert for a trading signal.
        
        Args:
            signal: TradingSignal or similar object
        """
        subject = f"🚨 NEPSE Signal: {signal.signal_type} {signal.symbol}"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #1a1a1a; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #2d2d2d; border-radius: 10px; padding: 20px;">
                <h2 style="color: #4CAF50; margin-top: 0;">
                    {'🟢' if 'BUY' in signal.signal_type.upper() else '🔴'} 
                    {signal.signal_type} Alert: {signal.symbol}
                </h2>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #444;">Entry Price:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #444; text-align: right;">
                            <strong>Rs. {signal.entry_price:,.2f}</strong>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #444; color: #4CAF50;">Target:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #444; text-align: right; color: #4CAF50;">
                            <strong>Rs. {signal.target_price:,.2f}</strong>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #444; color: #f44336;">Stop Loss:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #444; text-align: right; color: #f44336;">
                            <strong>Rs. {signal.stop_loss:,.2f}</strong>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #444;">Confidence:</td>
                        <td style="padding: 10px; border-bottom: 1px solid #444; text-align: right;">
                            <strong>{signal.confidence:.0f}%</strong>
                        </td>
                    </tr>
                </table>
                
                <div style="margin-top: 15px; padding: 10px; background-color: #333; border-radius: 5px;">
                    <strong>Strategies:</strong> {', '.join(signal.strategies)}
                </div>
                
                {f'<div style="margin-top: 15px; padding: 15px; background-color: #1e3a5f; border-radius: 5px;"><strong>AI Analysis:</strong><br>{signal.ai_verdict}</div>' if hasattr(signal, 'ai_verdict') and signal.ai_verdict else ''}
                
                <p style="color: #888; font-size: 12px; margin-top: 20px;">
                    Generated by NEPSE AI Trading Bot at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                </p>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(subject, body, html=True)
    
    async def send_daily_summary(
        self,
        signals: List,
        market_summary: dict = None,
    ) -> bool:
        """
        Send daily market and signal summary.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        subject = f"📊 NEPSE Daily Summary - {today}"
        
        signal_rows = ""
        for s in signals[:10]:  # Top 10 signals
            color = "#4CAF50" if "BUY" in s.signal_type.upper() else "#f44336"
            signal_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #444;">{s.symbol}</td>
                <td style="padding: 8px; border-bottom: 1px solid #444; color: {color};">{s.signal_type}</td>
                <td style="padding: 8px; border-bottom: 1px solid #444; text-align: right;">Rs. {s.entry_price:,.2f}</td>
                <td style="padding: 8px; border-bottom: 1px solid #444; text-align: right;">{s.confidence:.0f}%</td>
            </tr>
            """
        
        nepse_index = market_summary.get("nepse_index", "--") if market_summary else "--"
        nepse_change = market_summary.get("change_pct", 0) if market_summary else 0
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #1a1a1a; color: #ffffff; padding: 20px;">
            <div style="max-width: 700px; margin: 0 auto; background-color: #2d2d2d; border-radius: 10px; padding: 20px;">
                <h2 style="color: #2196F3; margin-top: 0;">📊 Daily Market Summary</h2>
                <p style="color: #888;">{today}</p>
                
                <div style="display: flex; gap: 20px; margin-bottom: 20px;">
                    <div style="flex: 1; padding: 15px; background-color: #333; border-radius: 8px;">
                        <div style="color: #888; font-size: 12px;">NEPSE Index</div>
                        <div style="font-size: 24px; font-weight: bold;">{nepse_index}</div>
                        <div style="color: {'#4CAF50' if nepse_change >= 0 else '#f44336'};">
                            {'+' if nepse_change >= 0 else ''}{nepse_change:.2f}%
                        </div>
                    </div>
                    <div style="flex: 1; padding: 15px; background-color: #333; border-radius: 8px;">
                        <div style="color: #888; font-size: 12px;">Signals Found</div>
                        <div style="font-size: 24px; font-weight: bold;">{len(signals)}</div>
                        <div style="color: #4CAF50;">
                            {len([s for s in signals if 'BUY' in s.signal_type.upper()])} Buy Signals
                        </div>
                    </div>
                </div>
                
                <h3 style="color: #4CAF50;">🎯 Top Trading Signals</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background-color: #333;">
                            <th style="padding: 10px; text-align: left;">Symbol</th>
                            <th style="padding: 10px; text-align: left;">Signal</th>
                            <th style="padding: 10px; text-align: right;">Entry</th>
                            <th style="padding: 10px; text-align: right;">Confidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        {signal_rows if signal_rows else '<tr><td colspan="4" style="padding: 20px; text-align: center; color: #888;">No signals today</td></tr>'}
                    </tbody>
                </table>
                
                <p style="margin-top: 20px; padding: 15px; background-color: #1e3a5f; border-radius: 5px; font-size: 14px;">
                    💡 <strong>Tip:</strong> Use these signals as a starting point. Always verify with 
                    additional analysis before trading.
                </p>
                
                <p style="color: #666; font-size: 11px; margin-top: 20px; text-align: center;">
                    NEPSE AI Trading Bot | This is not financial advice
                </p>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(subject, body, html=True)


# Convenience function for quick alerts
async def send_email_alert(
    subject: str,
    message: str,
    to_email: str = None,
) -> bool:
    """Quick email alert."""
    notifier = EmailNotifier()
    if to_email:
        notifier.to_emails = [to_email]
    return await notifier.send_email(subject, message, html=False)
