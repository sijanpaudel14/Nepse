"""
AI Advisor using OpenAI.

Takes technical analysis signals and news, uses GPT to generate
a final trading recommendation with human-readable analysis.

PRODUCTION HARDENING:
- 15-second timeout on OpenAI calls
- 3 retries with 2-second wait between attempts
- Graceful degradation if API unavailable
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import json
from loguru import logger

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not installed. AI advisor will be disabled.")

# Retry logic for production reliability
try:
    from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    logger.debug("Tenacity not installed. Retries disabled.")

from core.config import settings
from core.exceptions import AIAdvisorError


# Timeout constant
OPENAI_TIMEOUT_SECONDS = 15.0


@dataclass
class AIVerdict:
    """AI's trading verdict."""
    verdict: str  # STRONG_BUY, BUY, RISKY, AVOID
    confidence: float  # 1-10
    summary: str  # 3-sentence summary
    entry_price: float
    target_price: float
    stop_loss: float
    reasoning: str  # Detailed reasoning
    risks: str  # Key risks to watch


class AIAdvisor:
    """
    AI-powered trading advisor using OpenAI.
    
    Takes technical signals and news, provides human-readable analysis.
    """
    
    SYSTEM_PROMPT = """You are an expert NEPSE (Nepal Stock Exchange) swing trader and financial analyst. 
Your job is to analyze technical signals and news to provide trading recommendations.

IMPORTANT CONTEXT:
- NEPSE uses T+2 settlement, so day trading is impossible
- We focus on swing trades (hold 3-15 days)
- Nepali market has lower liquidity than international markets
- Be extra cautious about penny stocks and manipulation
- The user is a beginner in finance, explain things simply

STRICT RULES:
1. You MUST respond ONLY with a valid JSON object. No markdown, no conversational text.
2. If the 'RECENT NEWS' section says "No recent news available" or is empty, you MUST:
   - Set "summary" to exactly: "No recent news available for this company."
   - Set "risks" to exactly: "Technical trading only. Monitor for hidden fundamental risks."
   - DO NOT invent or fabricate any news-based narrative.
3. Only discuss news if actual news headlines are provided.
4. Base your verdict on the technical data when no news is available.

Your response must be a JSON object with these exact fields:
{
    "verdict": "STRONG_BUY" | "BUY" | "RISKY" | "AVOID",
    "confidence": <1-10 score>,
    "summary": "<3 sentence summary - ONLY based on actual provided news>",
    "entry_price": <recommended entry price>,
    "target_price": <target price, typically 8-12% above entry>,
    "stop_loss": <stop loss price, typically 4-6% below entry>,
    "reasoning": "<detailed reasoning for your verdict based on technicals>",
    "risks": "<key risks - ONLY based on actual provided news>"
}

Verdict meanings:
- STRONG_BUY: High confidence, multiple confirmations, favorable news
- BUY: Good technical setup, acceptable risk
- RISKY: Some positive signals but concerns exist
- AVOID: Don't buy, too risky or negative signals"""

    def __init__(self, model: str = None, max_tokens: int = 800):
        """
        Initialize AI advisor.
        
        Args:
            model: OpenAI model to use
            max_tokens: Max response tokens
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI is required. Run: pip install openai")
        
        if not settings.openai_api_key:
            raise AIAdvisorError("OPENAI_API_KEY not configured")
        
        self.model = model or settings.openai_model
        self.max_tokens = max_tokens
        self.client = OpenAI(api_key=settings.openai_api_key)
    
    def _format_technical_data(self, signal_data: Dict[str, Any]) -> str:
        """Format technical data for the AI prompt."""
        lines = ["TECHNICAL ANALYSIS:"]
        
        # Basic info
        lines.append(f"Symbol: {signal_data.get('symbol', 'N/A')}")
        lines.append(f"Current Price: Rs. {signal_data.get('entry_price', 0):.2f}")
        lines.append(f"Strategy Trigger: {signal_data.get('strategy_name', 'N/A')}")
        lines.append(f"Initial Confidence: {signal_data.get('confidence', 0):.1f}/10")
        
        # Indicators
        indicators = signal_data.get("indicators", {})
        
        if "rsi" in indicators and indicators["rsi"]:
            rsi = indicators["rsi"]
            rsi_status = "Oversold" if rsi < 30 else "Overbought" if rsi > 70 else "Neutral" if rsi < 50 else "Bullish"
            lines.append(f"RSI(14): {rsi:.1f} ({rsi_status})")
        
        if "ema_9" in indicators and "ema_21" in indicators:
            ema9 = indicators["ema_9"]
            ema21 = indicators["ema_21"]
            if ema9 and ema21:
                trend = "Uptrend" if ema9 > ema21 else "Downtrend"
                lines.append(f"EMA(9): {ema9:.2f}, EMA(21): {ema21:.2f} ({trend})")
        
        if "volume_spike" in indicators and indicators["volume_spike"]:
            vol = indicators["volume_spike"]
            lines.append(f"Volume: {vol:.1f}x average ({'High' if vol > 1.5 else 'Normal'})")
        
        if "macd_histogram" in indicators and indicators["macd_histogram"]:
            macd = indicators["macd_histogram"]
            lines.append(f"MACD Histogram: {macd:.2f} ({'Bullish' if macd > 0 else 'Bearish'})")
        
        if "adx" in indicators and indicators["adx"]:
            adx = indicators["adx"]
            strength = "Strong" if adx > 25 else "Weak"
            lines.append(f"ADX: {adx:.1f} ({strength} trend)")
        
        # Signal reason
        if "reason" in signal_data:
            lines.append(f"\nSignal Triggers: {signal_data['reason']}")
        
        return "\n".join(lines)
    
    def _call_openai_with_retry(self, messages: list, symbol: str) -> Dict:
        """
        Call OpenAI API with retry logic and timeout.
        
        PRODUCTION HARDENING:
        - 15-second timeout per request
        - 3 retry attempts with 2-second wait
        - Returns fallback dict on total failure
        
        Args:
            messages: Chat messages for OpenAI
            symbol: Stock symbol (for logging)
            
        Returns:
            Parsed JSON response or fallback dict
        """
        import httpx
        
        max_attempts = 3
        last_error = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug(f"OpenAI call attempt {attempt}/{max_attempts} for {symbol}")
                
                # Create client with timeout
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    timeout=OPENAI_TIMEOUT_SECONDS,
                )
                
                content = response.choices[0].message.content
                return json.loads(content)
                
            except json.JSONDecodeError as e:
                logger.warning(f"Attempt {attempt}: JSON parse error for {symbol}: {e}")
                last_error = e
                
            except Exception as e:
                error_str = str(e).lower()
                logger.warning(f"Attempt {attempt}: OpenAI error for {symbol}: {e}")
                last_error = e
                
                # Don't retry on certain errors
                if "rate_limit" in error_str or "quota" in error_str:
                    logger.error(f"Rate limit/quota exceeded. Not retrying.")
                    break
                if "invalid_api_key" in error_str:
                    logger.error(f"Invalid API key. Not retrying.")
                    break
            
            # Wait before retry (except on last attempt)
            if attempt < max_attempts:
                import time
                time.sleep(2)
        
        # All retries failed - return fallback
        logger.error(f"All {max_attempts} OpenAI attempts failed for {symbol}. Last error: {last_error}")
        return {
            "verdict": "RISKY",
            "confidence": 5.0,
            "summary": f"⚠️ AI Verdict Unavailable: API Timeout after {max_attempts} attempts.",
            "reasoning": "Mathematical scores are still valid. AI analysis could not be completed.",
            "risks": "Review raw technical/fundamental scores manually.",
        }
    
    def analyze(
        self, 
        signal_data: Dict[str, Any], 
        news_text: str,
    ) -> AIVerdict:
        """
        Get AI analysis for a trading signal.
        
        PRODUCTION HARDENING:
        - Uses retry logic with timeout
        - Returns fallback verdict on API failure (doesn't crash)
        
        Args:
            signal_data: Dict with technical data and signal info
            news_text: Formatted news articles
            
        Returns:
            AIVerdict with recommendation
        """
        symbol = signal_data.get('symbol', 'unknown')
        
        # Format the prompt
        technical_section = self._format_technical_data(signal_data)
        
        user_prompt = f"""{technical_section}

RECENT NEWS:
{news_text if news_text else "No recent news available for this stock."}

Based on the technical analysis and news, provide your trading recommendation as a JSON object."""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        
        try:
            logger.debug(f"Calling OpenAI for {symbol}")
            
            # Use retry-enabled call
            data = self._call_openai_with_retry(messages, symbol)
            
            # Create verdict
            verdict = AIVerdict(
                verdict=data.get("verdict", "RISKY"),
                confidence=float(data.get("confidence", 5)),
                summary=data.get("summary", ""),
                entry_price=float(data.get("entry_price", signal_data.get("entry_price", 0))),
                target_price=float(data.get("target_price", 0)),
                stop_loss=float(data.get("stop_loss", 0)),
                reasoning=data.get("reasoning", ""),
                risks=data.get("risks", ""),
            )
            
            logger.info(f"AI Verdict for {symbol}: {verdict.verdict}")
            return verdict
            
        except Exception as e:
            # Final fallback - return safe verdict instead of crashing
            logger.error(f"Critical AI error for {symbol}: {e}")
            return AIVerdict(
                verdict="RISKY",
                confidence=5.0,
                summary=f"⚠️ AI Analysis Failed: {str(e)[:50]}",
                entry_price=float(signal_data.get("entry_price", 0)),
                target_price=float(signal_data.get("target_price", 0)),
                stop_loss=float(signal_data.get("stop_loss", 0)),
                reasoning="Mathematical scores are still valid.",
                risks="AI unavailable - review raw scores manually.",
            )
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate API cost for tracking.
        
        Args:
            input_tokens: Input token count
            output_tokens: Output token count
            
        Returns:
            Estimated cost in USD
        """
        # Pricing for gpt-4o-mini (as of 2024)
        input_cost = input_tokens * 0.00015 / 1000
        output_cost = output_tokens * 0.0006 / 1000
        return input_cost + output_cost


def get_ai_verdict(signal_data: Dict[str, Any], news_text: str) -> AIVerdict:
    """
    Convenience function to get AI verdict.
    
    Args:
        signal_data: Technical signal data
        news_text: Formatted news
        
    Returns:
        AIVerdict
    """
    if not OPENAI_AVAILABLE or not settings.openai_api_key:
        # Return a default verdict if AI not available
        return AIVerdict(
            verdict="RISKY",
            confidence=signal_data.get("confidence", 5),
            summary="AI analysis not available. Proceed with caution based on technical signals only.",
            entry_price=signal_data.get("entry_price", 0),
            target_price=signal_data.get("target_price", 0),
            stop_loss=signal_data.get("stop_loss", 0),
            reasoning="OpenAI API not configured.",
            risks="Unable to analyze news sentiment.",
        )
    
    advisor = AIAdvisor()
    return advisor.analyze(signal_data, news_text)
