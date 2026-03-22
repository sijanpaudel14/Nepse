"""
Signal Aggregator.

Combines technical analysis signals, fundamental analysis, news sentiment,
and AI verdict into a final trading recommendation.

MILLIONAIRE EDGE:
This module is where all analysis comes together. The weighting system
determines how much each factor influences the final decision:
- Technical Analysis: 40% (price action, momentum)
- Fundamental Analysis: 30% (company health, valuation)
- AI Verdict: 20% (pattern recognition, sentiment)
- News: 10% (catalyst, event-driven)

A truly great trade has ALL factors aligned (TA + FA + AI + News).
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict, Any, Optional
from loguru import logger

from analysis.screener import ScreenerResult
from analysis.strategies import StrategySignal
from analysis.fundamentals import FundamentalAnalyzer, FundamentalData
from intelligence.news_scraper import NewsScraper, NewsItem, scrape_news_for_stock
from intelligence.ai_advisor import AIAdvisor, AIVerdict, get_ai_verdict


@dataclass
class FinalSignal:
    """
    Final aggregated trading signal with all analysis combined.
    """
    # Basic info
    symbol: str
    date: date
    
    # Technical analysis
    ta_signals: List[StrategySignal] = field(default_factory=list)
    ta_confidence: float = 0.0
    primary_strategy: str = ""
    
    # Fundamental analysis (NEW)
    fundamentals: Optional[FundamentalData] = None
    fundamental_score: float = 0.0
    valuation_verdict: str = ""          # UNDERVALUED, FAIR, OVERVALUED
    pe_ratio: float = 0.0
    pb_ratio: float = 0.0
    roe: float = 0.0
    eps: float = 0.0
    
    # Broker analysis (NEW)
    broker_signal: str = ""              # ACCUMULATING, DISTRIBUTING, NEUTRAL
    top_buyers: List[str] = field(default_factory=list)
    top_sellers: List[str] = field(default_factory=list)
    
    # News
    news_items: List[NewsItem] = field(default_factory=list)
    news_summary: str = ""
    
    # AI analysis
    ai_verdict: Optional[AIVerdict] = None
    
    # Final recommendation
    final_verdict: str = "HOLD"  # STRONG_BUY, BUY, HOLD, AVOID
    final_confidence: float = 0.0
    entry_price: float = 0.0
    target_price: float = 0.0
    stop_loss: float = 0.0
    
    # Summary
    reasoning: str = ""
    risks: str = ""
    
    # Additional metrics
    risk_reward_ratio: float = 0.0
    position_recommendation: str = ""    # FULL, HALF, QUARTER
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "symbol": self.symbol,
            "date": str(self.date),
            "final_verdict": self.final_verdict,
            "final_confidence": self.final_confidence,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "primary_strategy": self.primary_strategy,
            "ta_confidence": self.ta_confidence,
            # Fundamental data
            "fundamental_score": self.fundamental_score,
            "valuation_verdict": self.valuation_verdict,
            "pe_ratio": self.pe_ratio,
            "pb_ratio": self.pb_ratio,
            "roe": self.roe,
            "eps": self.eps,
            # Broker data
            "broker_signal": self.broker_signal,
            "top_buyers": self.top_buyers,
            "top_sellers": self.top_sellers,
            # Other
            "reasoning": self.reasoning,
            "risks": self.risks,
            "news_count": len(self.news_items),
            "risk_reward_ratio": self.risk_reward_ratio,
            "position_recommendation": self.position_recommendation,
        }


class SignalAggregator:
    """
    Aggregates all analysis into final trading signals.
    
    This is the brain of the system - it combines:
    1. Technical Analysis (price patterns, momentum)
    2. Fundamental Analysis (PE, ROE, broker activity)
    3. News Sentiment (recent headlines)
    4. AI Analysis (GPT-powered verdict)
    
    The final verdict uses weighted scoring to provide
    actionable trading recommendations.
    """
    
    def __init__(
        self,
        use_ai: bool = True,
        scrape_news: bool = True,
        use_fundamentals: bool = True,
    ):
        """
        Initialize aggregator.
        
        Args:
            use_ai: Whether to use OpenAI for analysis
            scrape_news: Whether to scrape news
            use_fundamentals: Whether to analyze fundamentals
        """
        self.use_ai = use_ai
        self.scrape_news = scrape_news
        self.use_fundamentals = use_fundamentals
        self.news_scraper = NewsScraper() if scrape_news else None
        self.fundamental_analyzer = FundamentalAnalyzer() if use_fundamentals else None
    
    def aggregate_signal(
        self,
        result: ScreenerResult,
        include_broker_analysis: bool = True,
    ) -> FinalSignal:
        """
        Create a final signal from screener result.
        
        Args:
            result: ScreenerResult with technical signals
            include_broker_analysis: Whether to include broker analysis
            
        Returns:
            FinalSignal with complete analysis
        """
        symbol = result.symbol
        primary = result.primary_signal
        
        logger.info(f"Aggregating signal for {symbol}")
        
        # Initialize final signal
        final = FinalSignal(
            symbol=symbol,
            date=date.today(),
            ta_signals=result.signals,
            ta_confidence=result.combined_confidence,
            primary_strategy=primary.strategy_name if primary else "",
            entry_price=primary.entry_price if primary else 0,
            target_price=primary.target_price if primary else 0,
            stop_loss=primary.stop_loss if primary else 0,
        )
        
        # Calculate risk/reward ratio
        if final.entry_price > 0 and final.stop_loss > 0 and final.target_price > 0:
            risk = final.entry_price - final.stop_loss
            reward = final.target_price - final.entry_price
            if risk > 0:
                final.risk_reward_ratio = round(reward / risk, 2)
        
        # Get fundamental analysis
        if self.use_fundamentals and self.fundamental_analyzer:
            self._add_fundamental_analysis(final, include_broker_analysis)
        
        # Scrape news
        if self.scrape_news:
            self._add_news_analysis(final)
        
        # Get AI verdict
        if self.use_ai and primary:
            self._add_ai_analysis(final)
        
        # Calculate final recommendation
        self._calculate_final_verdict(final)
        
        return final
    
    def _add_fundamental_analysis(
        self,
        final: FinalSignal,
        include_broker: bool = True,
    ):
        """Add fundamental analysis to signal."""
        try:
            if include_broker:
                # Get comprehensive analysis (includes broker)
                analysis = self.fundamental_analyzer.get_complete_analysis(final.symbol)
                
                final.fundamentals = analysis.fundamentals
                final.fundamental_score = analysis.overall_score
                
                # Valuation verdict
                if analysis.fundamentals:
                    pe = analysis.fundamentals.pe_ratio
                    pb = analysis.fundamentals.pb_ratio
                    final.pe_ratio = pe
                    final.pb_ratio = pb
                    final.roe = analysis.fundamentals.roe
                    final.eps = analysis.fundamentals.eps
                    
                    # Determine valuation
                    if pe < 15 and pb < 2:
                        final.valuation_verdict = "UNDERVALUED"
                    elif pe > 30 or pb > 4:
                        final.valuation_verdict = "OVERVALUED"
                    else:
                        final.valuation_verdict = "FAIR"
                
                # Broker analysis
                if analysis.broker_analysis:
                    ba = analysis.broker_analysis
                    final.broker_signal = ba.signal
                    final.top_buyers = [b[0] for b in ba.top_buyers[:3]]
                    final.top_sellers = [s[0] for s in ba.top_sellers[:3]]
            else:
                # Just fundamentals
                fundamentals = self.fundamental_analyzer.get_fundamentals(final.symbol)
                if fundamentals:
                    final.fundamentals = fundamentals
                    final.pe_ratio = fundamentals.pe_ratio
                    final.pb_ratio = fundamentals.pb_ratio
                    final.roe = fundamentals.roe
                    final.eps = fundamentals.eps
                    
                    # Calculate score
                    score = self.fundamental_analyzer._calculate_valuation_score(fundamentals)
                    final.fundamental_score = score
                    
        except Exception as e:
            logger.warning(f"Fundamental analysis failed for {final.symbol}: {e}")
    
    def _add_news_analysis(self, final: FinalSignal):
        """Add news analysis to signal."""
        try:
            final.news_items = scrape_news_for_stock(final.symbol, limit=3)
            news_text = self._format_news(final.news_items)
            final.news_summary = news_text
        except Exception as e:
            logger.warning(f"News scraping failed for {final.symbol}: {e}")
            final.news_items = []
            final.news_summary = ""
    
    def _add_ai_analysis(self, final: FinalSignal):
        """Add AI analysis to signal."""
        try:
            primary = final.ta_signals[0] if final.ta_signals else None
            if not primary:
                return
            
            # Include fundamental data in AI prompt
            signal_data = {
                "symbol": final.symbol,
                "entry_price": primary.entry_price,
                "target_price": primary.target_price,
                "stop_loss": primary.stop_loss,
                "strategy_name": primary.strategy_name,
                "confidence": primary.confidence,
                "reason": primary.reason,
                "indicators": primary.indicators,
                # Add fundamental context
                "pe_ratio": final.pe_ratio,
                "pb_ratio": final.pb_ratio,
                "roe": final.roe,
                "eps": final.eps,
                "valuation": final.valuation_verdict,
                "broker_signal": final.broker_signal,
            }
            
            # Add fundamental context to news
            fundamental_context = ""
            if final.fundamentals:
                fundamental_context = f"\n\nFundamental Data: PE={final.pe_ratio:.1f}, PB={final.pb_ratio:.2f}, ROE={final.roe:.1f}%, EPS=Rs.{final.eps:.2f}"
                if final.broker_signal:
                    fundamental_context += f", Broker Signal: {final.broker_signal}"
            
            final.ai_verdict = get_ai_verdict(
                signal_data,
                final.news_summary + fundamental_context
            )
            
        except Exception as e:
            logger.warning(f"AI analysis failed for {final.symbol}: {e}")
            final.ai_verdict = None
    
    def _format_news(self, news_items: List[NewsItem]) -> str:
        """Format news items for display and AI."""
        if not news_items:
            return ""
        
        lines = []
        for item in news_items:
            line = f"[{item.source}] {item.title}"
            if item.date:
                line += f" ({item.date})"
            lines.append(line)
        
        return "\n".join(lines)
    
    def _calculate_final_verdict(self, final: FinalSignal):
        """
        Calculate the final verdict combining all analysis.
        
        Enhanced Weighting System:
        - Technical Analysis: 40% (price action is primary)
        - Fundamental Analysis: 30% (company health matters)
        - AI Verdict: 20% (pattern recognition)
        - News: 10% (catalyst/event)
        
        Position sizing recommendation based on confidence:
        - FULL position: 80%+ confidence + good fundamentals
        - HALF position: 60-80% confidence
        - QUARTER position: 40-60% confidence
        """
        scores = {}
        
        # Technical Analysis Score (40% weight)
        ta_score = final.ta_confidence / 10.0  # Normalize to 0-1
        scores["ta"] = ta_score
        
        # Fundamental Analysis Score (30% weight)
        fa_score = final.fundamental_score / 100.0  # Already 0-100, normalize to 0-1
        scores["fa"] = fa_score
        
        # Adjust for valuation
        valuation_adjustment = 0
        if final.valuation_verdict == "UNDERVALUED":
            valuation_adjustment = 0.1
        elif final.valuation_verdict == "OVERVALUED":
            valuation_adjustment = -0.15
        
        # Adjust for broker signal
        broker_adjustment = 0
        if final.broker_signal == "ACCUMULATING":
            broker_adjustment = 0.05
        elif final.broker_signal == "DISTRIBUTING":
            broker_adjustment = -0.1
        
        fa_score = min(1.0, max(0, fa_score + valuation_adjustment + broker_adjustment))
        scores["fa_adjusted"] = fa_score
        
        # AI Score (20% weight)
        ai_score = 0.5  # Default neutral
        if final.ai_verdict:
            verdict_scores = {
                "STRONG_BUY": 1.0,
                "BUY": 0.7,
                "RISKY": 0.4,
                "AVOID": 0.1,
            }
            ai_score = verdict_scores.get(final.ai_verdict.verdict, 0.5)
            ai_score *= (final.ai_verdict.confidence / 10.0)  # Weight by confidence
        scores["ai"] = ai_score
        
        # News Score (10% weight)
        news_score = 0.5  # Neutral if no news
        if final.news_items:
            # Having recent news is slightly positive (shows activity)
            news_score = 0.6 + (min(len(final.news_items), 3) * 0.1)
        scores["news"] = news_score
        
        # Calculate weighted combination
        combined_score = (
            (scores["ta"] * 0.40) +
            (fa_score * 0.30) +
            (scores["ai"] * 0.20) +
            (scores["news"] * 0.10)
        )
        
        # Risk/Reward adjustment
        if final.risk_reward_ratio >= 2.0:
            combined_score *= 1.1  # Boost for good R:R
        elif final.risk_reward_ratio < 1.0:
            combined_score *= 0.9  # Penalize poor R:R
        
        combined_score = min(1.0, combined_score)  # Cap at 1.0
        
        # Update prices from AI if available
        if final.ai_verdict:
            final.entry_price = final.ai_verdict.entry_price or final.entry_price
            final.target_price = final.ai_verdict.target_price or final.target_price
            final.stop_loss = final.ai_verdict.stop_loss or final.stop_loss
            final.reasoning = final.ai_verdict.summary
            final.risks = final.ai_verdict.risks
        else:
            final.reasoning = f"Technical: {final.primary_strategy}"
            if final.valuation_verdict:
                final.reasoning += f" | Valuation: {final.valuation_verdict}"
            if final.broker_signal:
                final.reasoning += f" | Broker: {final.broker_signal}"
            final.risks = "AI analysis not available. Review manually."
        
        # Determine final verdict
        if combined_score >= 0.75:
            final.final_verdict = "STRONG_BUY"
        elif combined_score >= 0.55:
            final.final_verdict = "BUY"
        elif combined_score >= 0.35:
            final.final_verdict = "HOLD"
        else:
            final.final_verdict = "AVOID"
        
        # Position sizing recommendation
        if combined_score >= 0.8 and fa_score >= 0.5:
            final.position_recommendation = "FULL"
        elif combined_score >= 0.6:
            final.position_recommendation = "HALF"
        else:
            final.position_recommendation = "QUARTER"
        
        final.final_confidence = round(combined_score * 10, 1)
        
        logger.debug(
            f"{final.symbol} scoring: TA={scores['ta']:.2f}, "
            f"FA={fa_score:.2f}, AI={scores['ai']:.2f}, "
            f"News={scores['news']:.2f}, Final={combined_score:.2f}"
        )
    
    def aggregate_all(self, results: List[ScreenerResult]) -> List[FinalSignal]:
        """
        Aggregate multiple screener results.
        
        Args:
            results: List of ScreenerResults
            
        Returns:
            List of FinalSignals sorted by confidence
        """
        signals = []
        
        for result in results:
            try:
                final = self.aggregate_signal(result)
                signals.append(final)
            except Exception as e:
                logger.error(f"Failed to aggregate {result.symbol}: {e}")
                continue
        
        # Sort by final confidence
        signals.sort(key=lambda s: s.final_confidence, reverse=True)
        
        return signals
    
    def format_signal_for_telegram(self, signal: FinalSignal) -> str:
        """
        Format a final signal for Telegram notification.
        
        Args:
            signal: FinalSignal to format
            
        Returns:
            Formatted string with emojis
        """
        # Emoji based on verdict
        verdict_emoji = {
            "STRONG_BUY": "🟢🔥",
            "BUY": "🟢",
            "HOLD": "🟡",
            "AVOID": "🔴",
        }
        
        emoji = verdict_emoji.get(signal.final_verdict, "⚪")
        
        lines = [
            f"{emoji} **{signal.symbol}** - {signal.final_verdict}",
            f"",
            f"📊 *Technical Analysis*",
            f"└ Strategy: {signal.primary_strategy}",
            f"└ TA Confidence: {signal.ta_confidence:.1f}/10",
            f"",
        ]
        
        # Add fundamental data
        if signal.pe_ratio > 0 or signal.roe > 0:
            lines.extend([
                f"📈 *Fundamentals*",
                f"└ PE: {signal.pe_ratio:.1f} | PB: {signal.pb_ratio:.2f}",
                f"└ ROE: {signal.roe:.1f}% | EPS: Rs.{signal.eps:.2f}",
            ])
            if signal.valuation_verdict:
                lines.append(f"└ Valuation: {signal.valuation_verdict}")
            lines.append("")
        
        # Add broker analysis
        if signal.broker_signal:
            lines.extend([
                f"🏦 *Broker Activity*",
                f"└ Signal: {signal.broker_signal}",
            ])
            if signal.top_buyers:
                lines.append(f"└ Top Buyers: {', '.join(signal.top_buyers[:3])}")
            if signal.top_sellers:
                lines.append(f"└ Top Sellers: {', '.join(signal.top_sellers[:3])}")
            lines.append("")
        
        lines.extend([
            f"💰 *Trade Setup*",
            f"└ Entry: Rs. {signal.entry_price:.2f}",
            f"└ Target: Rs. {signal.target_price:.2f} (+{((signal.target_price/signal.entry_price)-1)*100:.1f}%)" if signal.entry_price > 0 else "└ Target: N/A",
            f"└ Stop Loss: Rs. {signal.stop_loss:.2f} ({((signal.stop_loss/signal.entry_price)-1)*100:.1f}%)" if signal.entry_price > 0 else "└ Stop Loss: N/A",
            f"└ Risk:Reward = 1:{signal.risk_reward_ratio:.1f}" if signal.risk_reward_ratio > 0 else "",
            f"",
        ])
        
        # Position recommendation
        if signal.position_recommendation:
            pos_emoji = {"FULL": "🎯", "HALF": "📊", "QUARTER": "📉"}
            lines.append(f"{pos_emoji.get(signal.position_recommendation, '📌')} Position Size: {signal.position_recommendation}")
            lines.append("")
        
        if signal.ai_verdict:
            lines.extend([
                f"🤖 *AI Analysis*",
                f"└ Confidence: {signal.ai_verdict.confidence:.1f}/10",
                f"└ {signal.reasoning}",
                f"",
            ])
        
        if signal.news_items:
            lines.append("📰 *Recent News*")
            for news in signal.news_items[:2]:
                lines.append(f"└ {news.title[:60]}...")
        
        if signal.risks:
            lines.extend([
                f"",
                f"⚠️ *Risks*: {signal.risks}",
            ])
        
        lines.extend([
            f"",
            f"📅 Generated: {signal.date}",
            f"🎯 Final Confidence: {signal.final_confidence}/10",
        ])
        
        return "\n".join([l for l in lines if l is not None])
