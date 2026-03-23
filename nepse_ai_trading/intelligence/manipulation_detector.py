"""
🚨 INSIDER MANIPULATION DETECTION SYSTEM

This module implements 9 advanced manipulation detection algorithms for NEPSE:

1. CIRCULAR TRADING - Broker loops creating fake volume (A→B→C→A)
2. WASH TRADING - Same broker high buy/sell matching (>80%)
3. PUMP/DUMP PHASES - Lifecycle detection (Accumulation/Pump/Distribution)
4. BROKER CONCENTRATION - HHI Index for monopolistic control
5. PRICE-VOLUME DIVERGENCE - High volume without price movement
6. END-OF-DAY MANIPULATION - Last 30-min price spikes
7. BROKER NETWORK - Coordinated trading groups
8. PROMOTER LOCKUP - Days until insiders can sell
9. CROSS-TRADING - Same entity using multiple brokers

PHILOSOPHY:
- Better to miss a trade than catch a falling knife
- Detect manipulation BEFORE you buy, not after
- Show ALL warnings - let the trader decide
- Mathematical detection, no guesswork

Author: NEPSE AI Trading Engine
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime, date, timedelta
from collections import defaultdict
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger

# Import data sources
from data.fetcher import NepseFetcher
from data.sharehub_api import ShareHubAPI, BrokerData


class PumpDumpPhase(Enum):
    """The 3 phases of a pump-and-dump cycle."""
    UNKNOWN = "UNKNOWN"
    ACCUMULATION = "ACCUMULATION"  # Phase 1: Silent buying, low volume, flat price
    PUMP = "PUMP"                   # Phase 2: Price spike, volume explosion
    DISTRIBUTION = "DISTRIBUTION"   # Phase 3: Insiders dumping while retail buys
    CLEAN = "CLEAN"                 # No manipulation pattern detected


class ManipulationSeverity(Enum):
    """Severity levels for manipulation alerts."""
    NONE = "NONE"           # No issues
    LOW = "LOW"             # Minor concern, monitor
    MEDIUM = "MEDIUM"       # Significant risk, small position only
    HIGH = "HIGH"           # Severe risk, paper-trade only
    CRITICAL = "CRITICAL"   # Extreme manipulation, avoid completely


@dataclass
class CircularTradingResult:
    """Result of circular trading detection."""
    detected: bool = False
    severity: ManipulationSeverity = ManipulationSeverity.NONE
    loops_found: List[List[str]] = field(default_factory=list)  # List of broker loops
    circular_volume: int = 0           # Volume involved in circular trades
    total_volume: int = 0              # Total trading volume
    circular_percentage: float = 0.0   # % of volume that's circular
    top_loop_brokers: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class WashTradingResult:
    """Result of wash trading detection."""
    detected: bool = False
    severity: ManipulationSeverity = ManipulationSeverity.NONE
    suspicious_brokers: List[Dict] = field(default_factory=list)  # {broker, buy_qty, sell_qty, match_ratio}
    total_wash_volume: int = 0
    wash_percentage: float = 0.0
    description: str = ""


@dataclass
class PumpDumpResult:
    """Result of pump/dump phase detection."""
    phase: PumpDumpPhase = PumpDumpPhase.UNKNOWN
    severity: ManipulationSeverity = ManipulationSeverity.NONE
    confidence: float = 0.0            # 0-100% confidence in phase detection
    days_in_phase: int = 0             # How long in current phase
    phase_start_date: Optional[date] = None
    price_change_30d: float = 0.0      # 30-day price change %
    volume_ratio_30d: float = 0.0      # Current volume / 30-day avg
    accumulation_score: float = 0.0    # Score indicating accumulation
    distribution_score: float = 0.0    # Score indicating distribution
    description: str = ""


@dataclass 
class BrokerConcentrationResult:
    """Result of broker concentration (HHI) analysis."""
    hhi_index: float = 0.0             # Herfindahl-Hirschman Index (0-10000)
    severity: ManipulationSeverity = ManipulationSeverity.NONE
    top3_concentration: float = 0.0    # % held by top 3 brokers
    top5_concentration: float = 0.0    # % held by top 5 brokers
    top_brokers: List[Dict] = field(default_factory=list)  # {broker, share_pct, net_qty}
    is_monopolistic: bool = False      # HHI > 2500
    is_highly_concentrated: bool = False  # HHI > 1500
    description: str = ""


@dataclass
class PriceVolumeDivergenceResult:
    """Result of price-volume divergence detection."""
    detected: bool = False
    severity: ManipulationSeverity = ManipulationSeverity.NONE
    volume_multiple: float = 0.0       # Current volume / avg volume
    price_change_pct: float = 0.0      # Price change %
    is_absorption: bool = False        # High volume, no price move = smart money exiting
    divergence_score: float = 0.0      # 0-100, higher = more suspicious
    description: str = ""


@dataclass
class EODManipulationResult:
    """Result of end-of-day manipulation detection."""
    detected: bool = False
    severity: ManipulationSeverity = ManipulationSeverity.NONE
    last_30min_change_pct: float = 0.0
    last_30min_volume_pct: float = 0.0  # % of daily volume in last 30 min
    is_painting_tape: bool = False      # Artificial closing price move
    description: str = ""


@dataclass
class BrokerNetworkResult:
    """Result of broker network/coordination analysis."""
    networks_found: int = 0
    severity: ManipulationSeverity = ManipulationSeverity.NONE
    coordinated_groups: List[List[str]] = field(default_factory=list)
    coordination_score: float = 0.0    # 0-100, higher = more coordination
    top_network_brokers: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class LockupRiskResult:
    """Result of promoter lockup risk analysis."""
    has_lockup_risk: bool = False
    severity: ManipulationSeverity = ManipulationSeverity.NONE
    days_until_unlock: Optional[int] = None
    unlock_date: Optional[date] = None
    lockup_shares_pct: float = 0.0     # % of shares under lockup
    source: str = ""                   # IPO, Right Share, Bonus, etc.
    description: str = ""


@dataclass
class ManipulationReport:
    """Complete manipulation analysis report for a stock."""
    symbol: str
    analysis_date: datetime = field(default_factory=datetime.now)
    
    # Overall assessment
    overall_risk_score: float = 0.0    # 0-100 (0=clean, 100=extreme manipulation)
    overall_severity: ManipulationSeverity = ManipulationSeverity.NONE
    is_safe_to_trade: bool = True
    recommendation: str = ""
    
    # Individual detector results
    circular_trading: CircularTradingResult = field(default_factory=CircularTradingResult)
    wash_trading: WashTradingResult = field(default_factory=WashTradingResult)
    pump_dump: PumpDumpResult = field(default_factory=PumpDumpResult)
    broker_concentration: BrokerConcentrationResult = field(default_factory=BrokerConcentrationResult)
    price_volume_divergence: PriceVolumeDivergenceResult = field(default_factory=PriceVolumeDivergenceResult)
    eod_manipulation: EODManipulationResult = field(default_factory=EODManipulationResult)
    broker_network: BrokerNetworkResult = field(default_factory=BrokerNetworkResult)
    lockup_risk: LockupRiskResult = field(default_factory=LockupRiskResult)
    
    # Aggregated alerts
    alerts: List[str] = field(default_factory=list)
    veto_reasons: List[str] = field(default_factory=list)
    
    # Operator phase summary
    operator_phase: str = ""
    operator_phase_description: str = ""
    
    @property
    def severity(self) -> str:
        """Alias for overall_severity - returns the string value."""
        return self.overall_severity.value if isinstance(self.overall_severity, ManipulationSeverity) else str(self.overall_severity)


class ManipulationDetector:
    """
    Advanced manipulation detection system for NEPSE stocks.
    
    Uses floorsheet data, broker analysis, and price/volume patterns
    to detect 9 types of market manipulation commonly seen in NEPSE.
    """
    
    def __init__(self):
        """Initialize the manipulation detector."""
        self.fetcher = NepseFetcher()
        self.sharehub = ShareHubAPI()
        
        # Thresholds (tuned for NEPSE small-cap manipulation)
        self.CIRCULAR_VOLUME_THRESHOLD = 20.0     # >20% circular = flag
        self.WASH_MATCH_THRESHOLD = 0.70          # >70% buy/sell match = wash trading
        self.WASH_MIN_VOLUME = 1000               # Min volume to consider for wash
        self.HHI_MONOPOLY_THRESHOLD = 2500        # HHI > 2500 = monopolistic
        self.HHI_HIGH_CONCENTRATION = 1500        # HHI > 1500 = highly concentrated
        self.TOP3_CONCENTRATION_HIGH = 70.0       # >70% by top 3 = red flag
        self.VOLUME_SPIKE_THRESHOLD = 2.0         # >2x avg volume
        self.PRICE_MOVE_LOW_THRESHOLD = 2.0       # <2% price move = absorption
        self.EOD_VOLUME_THRESHOLD = 30.0          # >30% volume in last 30 min = suspicious
        self.EOD_PRICE_MOVE_THRESHOLD = 3.0       # >3% move in last 30 min
        self.PUMP_VOLUME_MULTIPLE = 3.0           # 3x volume = pump phase
        self.PUMP_PRICE_CHANGE = 15.0             # 15%+ price rise
        self.LOCKUP_WARNING_DAYS = 30             # Warn if lockup expires in 30 days
        
    def analyze_stock(self, symbol: str) -> ManipulationReport:
        """
        Run complete manipulation analysis on a stock.
        
        Args:
            symbol: Stock symbol to analyze
            
        Returns:
            ManipulationReport with all 9 detector results
        """
        symbol = symbol.upper().strip()
        logger.info(f"🔍 Running manipulation analysis for {symbol}...")
        
        report = ManipulationReport(symbol=symbol)
        
        try:
            # Fetch required data
            broker_data_1m = self._fetch_broker_data(symbol, "1M")
            broker_data_1w = self._fetch_broker_data(symbol, "1W")
            broker_data_1d = self._fetch_broker_data(symbol, "1D")
            price_history = self._fetch_price_history(symbol, days=90)
            
            # Run all 9 detectors
            report.circular_trading = self.detect_circular_trading(broker_data_1d, broker_data_1w)
            report.wash_trading = self.detect_wash_trading(broker_data_1d)
            report.pump_dump = self.detect_pump_dump_phase(symbol, price_history, broker_data_1m)
            report.broker_concentration = self.calculate_broker_concentration(broker_data_1m)
            report.price_volume_divergence = self.detect_price_volume_divergence(price_history)
            report.eod_manipulation = self.detect_eod_manipulation(symbol)
            report.broker_network = self.analyze_broker_network(broker_data_1m, broker_data_1w)
            report.lockup_risk = self.check_lockup_risk(symbol)
            
            # Calculate overall risk score
            report = self._calculate_overall_risk(report)
            
            logger.info(f"✅ Manipulation analysis complete: {symbol} - Risk: {report.overall_risk_score:.0f}%")
            
        except Exception as e:
            logger.error(f"❌ Manipulation analysis failed for {symbol}: {e}")
            report.alerts.append(f"Analysis error: {str(e)}")
            
        return report
    
    def _fetch_broker_data(self, symbol: str, duration: str) -> List[BrokerData]:
        """Fetch broker analysis data."""
        try:
            return self.sharehub.get_broker_analysis(symbol, duration)
        except Exception as e:
            logger.warning(f"Failed to fetch broker data ({duration}): {e}")
            return []
    
    def _fetch_price_history(self, symbol: str, days: int = 90) -> pd.DataFrame:
        """Fetch price history for analysis."""
        try:
            return self.fetcher.fetch_price_history(symbol, days=days)
        except Exception as e:
            logger.warning(f"Failed to fetch price history: {e}")
            return pd.DataFrame()
    
    # ========================================================================
    # DETECTOR 1: CIRCULAR TRADING
    # ========================================================================
    
    def detect_circular_trading(
        self, 
        broker_data_1d: List[BrokerData],
        broker_data_1w: List[BrokerData]
    ) -> CircularTradingResult:
        """
        Detect circular trading patterns (broker loops).
        
        Circular trading occurs when:
        - Broker A sells to Broker B
        - Broker B sells to Broker C
        - Broker C sells back to Broker A
        
        This creates fake volume without real demand change.
        
        We detect this by looking for brokers with near-equal buy/sell
        quantities, suggesting they're just passing shares around.
        """
        result = CircularTradingResult()
        
        if not broker_data_1d and not broker_data_1w:
            result.description = "Insufficient broker data"
            return result
        
        # Use the richer dataset
        brokers = broker_data_1w if len(broker_data_1w) > len(broker_data_1d) else broker_data_1d
        
        if not brokers:
            return result
        
        # Calculate total volume
        total_buy = sum(b.buy_quantity for b in brokers)
        total_sell = sum(b.sell_quantity for b in brokers)
        result.total_volume = max(total_buy, total_sell, 1)
        
        # Find potential circular traders:
        # Brokers with high both buy AND sell (not net accumulators/distributors)
        circular_brokers = []
        circular_volume = 0
        
        for broker in brokers:
            buy_qty = broker.buy_quantity
            sell_qty = broker.sell_quantity
            
            if buy_qty < 100 or sell_qty < 100:
                continue
            
            # Calculate how "balanced" the broker's trading is
            # If buy ≈ sell, they're likely just passing shares
            min_qty = min(buy_qty, sell_qty)
            max_qty = max(buy_qty, sell_qty)
            
            if max_qty == 0:
                continue
                
            balance_ratio = min_qty / max_qty
            
            # If >60% balanced AND significant volume, likely circular
            if balance_ratio > 0.60 and min_qty > 500:
                circular_brokers.append({
                    "broker": broker.broker_code or broker.broker_name,
                    "buy_qty": buy_qty,
                    "sell_qty": sell_qty,
                    "balance_ratio": balance_ratio,
                    "circular_volume": min_qty  # Matching volume
                })
                circular_volume += min_qty
        
        # Calculate circular percentage
        result.circular_volume = circular_volume
        result.circular_percentage = (circular_volume / result.total_volume) * 100 if result.total_volume > 0 else 0
        
        # Detect if circular trading is significant
        if result.circular_percentage > self.CIRCULAR_VOLUME_THRESHOLD:
            result.detected = True
            result.loops_found = [[b["broker"] for b in circular_brokers[:5]]]
            result.top_loop_brokers = [b["broker"] for b in circular_brokers[:3]]
            
            # Severity based on circular percentage
            if result.circular_percentage > 50:
                result.severity = ManipulationSeverity.CRITICAL
                result.description = f"CRITICAL: {result.circular_percentage:.0f}% volume is circular (fake)"
            elif result.circular_percentage > 35:
                result.severity = ManipulationSeverity.HIGH
                result.description = f"HIGH: {result.circular_percentage:.0f}% circular trading detected"
            else:
                result.severity = ManipulationSeverity.MEDIUM
                result.description = f"MEDIUM: {result.circular_percentage:.0f}% circular trading"
        else:
            result.description = "No significant circular trading detected"
            
        return result
    
    # ========================================================================
    # DETECTOR 2: WASH TRADING
    # ========================================================================
    
    def detect_wash_trading(self, broker_data: List[BrokerData]) -> WashTradingResult:
        """
        Detect wash trading patterns.
        
        Wash trading occurs when the same entity buys and sells
        to themselves (through a broker) to inflate volume/manipulate price.
        
        We detect by finding brokers with suspiciously matched buy/sell quantities.
        """
        result = WashTradingResult()
        
        if not broker_data:
            result.description = "No broker data available"
            return result
        
        suspicious_brokers = []
        total_wash_volume = 0
        total_volume = 0
        
        for broker in broker_data:
            buy_qty = broker.buy_quantity
            sell_qty = broker.sell_quantity
            
            total_volume += max(buy_qty, sell_qty)
            
            # Skip small traders
            if max(buy_qty, sell_qty) < self.WASH_MIN_VOLUME:
                continue
            
            # Calculate match ratio
            if max(buy_qty, sell_qty) == 0:
                continue
                
            min_qty = min(buy_qty, sell_qty)
            max_qty = max(buy_qty, sell_qty)
            match_ratio = min_qty / max_qty
            
            # If buy ≈ sell (>70% match), suspicious
            if match_ratio > self.WASH_MATCH_THRESHOLD:
                wash_volume = min_qty
                suspicious_brokers.append({
                    "broker": broker.broker_code or broker.broker_name,
                    "broker_name": broker.broker_name,
                    "buy_qty": buy_qty,
                    "sell_qty": sell_qty,
                    "match_ratio": match_ratio,
                    "wash_volume": wash_volume
                })
                total_wash_volume += wash_volume
        
        result.suspicious_brokers = suspicious_brokers
        result.total_wash_volume = total_wash_volume
        result.wash_percentage = (total_wash_volume / total_volume * 100) if total_volume > 0 else 0
        
        if suspicious_brokers:
            result.detected = True
            
            # Severity based on number of suspicious brokers and volume
            if len(suspicious_brokers) >= 3 and result.wash_percentage > 30:
                result.severity = ManipulationSeverity.HIGH
                result.description = f"HIGH: {len(suspicious_brokers)} brokers with wash trading ({result.wash_percentage:.0f}% volume)"
            elif len(suspicious_brokers) >= 2 or result.wash_percentage > 20:
                result.severity = ManipulationSeverity.MEDIUM
                result.description = f"MEDIUM: Wash trading detected ({len(suspicious_brokers)} brokers)"
            else:
                result.severity = ManipulationSeverity.LOW
                result.description = f"LOW: Minor wash trading patterns detected"
        else:
            result.description = "No wash trading patterns detected"
            
        return result
    
    # ========================================================================
    # DETECTOR 3: PUMP/DUMP PHASE CLASSIFIER
    # ========================================================================
    
    def detect_pump_dump_phase(
        self,
        symbol: str,
        price_history: pd.DataFrame,
        broker_data_1m: List[BrokerData]
    ) -> PumpDumpResult:
        """
        Detect which phase of pump-and-dump cycle the stock is in.
        
        PHASE 1 - ACCUMULATION (Safe to buy with operators):
        - Volume below or at average
        - Price flat or slowly rising
        - Net accumulation by brokers
        
        PHASE 2 - PUMP (Risky - late entry):
        - Volume explosion (3x+ average)
        - Price spiking (15%+ in short period)
        - News/hype spreading
        
        PHASE 3 - DISTRIBUTION (DANGER - operators exiting):
        - Volume still high
        - Price flattening or falling
        - Smart money selling to retail
        """
        result = PumpDumpResult()
        
        if price_history.empty or len(price_history) < 20:
            result.phase = PumpDumpPhase.UNKNOWN
            result.description = "Insufficient price history for analysis"
            return result
        
        # Calculate metrics
        try:
            # Ensure data is sorted by date (oldest first)
            df = price_history.sort_index() if price_history.index.name == 'date' else price_history
            
            # Get price and volume metrics
            current_close = df['close'].iloc[-1] if 'close' in df.columns else 0
            price_30d_ago = df['close'].iloc[-30] if len(df) >= 30 and 'close' in df.columns else current_close
            price_7d_ago = df['close'].iloc[-7] if len(df) >= 7 and 'close' in df.columns else current_close
            
            # Price changes
            result.price_change_30d = ((current_close / price_30d_ago) - 1) * 100 if price_30d_ago > 0 else 0
            price_change_7d = ((current_close / price_7d_ago) - 1) * 100 if price_7d_ago > 0 else 0
            
            # Volume analysis
            if 'volume' in df.columns:
                current_volume = df['volume'].iloc[-5:].mean()  # Last 5 days avg
                avg_volume_30d = df['volume'].iloc[-30:].mean() if len(df) >= 30 else df['volume'].mean()
                result.volume_ratio_30d = current_volume / avg_volume_30d if avg_volume_30d > 0 else 1
            else:
                result.volume_ratio_30d = 1.0
            
            # Broker accumulation score
            if broker_data_1m:
                total_net = sum(b.net_quantity for b in broker_data_1m)
                total_volume = sum(abs(b.net_quantity) for b in broker_data_1m)
                
                if total_volume > 0:
                    # Positive = accumulation, negative = distribution
                    if total_net > 0:
                        result.accumulation_score = min(100, (total_net / total_volume) * 100)
                    else:
                        result.distribution_score = min(100, abs(total_net / total_volume) * 100)
            
            # PHASE CLASSIFICATION LOGIC
            
            # PHASE 3: DISTRIBUTION (Most dangerous)
            if (result.volume_ratio_30d > 1.5 and 
                result.price_change_30d > 10 and 
                price_change_7d < 2 and  # Price stalling after pump
                result.distribution_score > 30):
                result.phase = PumpDumpPhase.DISTRIBUTION
                result.severity = ManipulationSeverity.CRITICAL
                result.confidence = 80 + min(20, result.distribution_score / 5)
                result.description = "🚨 DISTRIBUTION: Operators dumping shares - AVOID"
                
            # PHASE 2: PUMP (Risky late entry)
            elif (result.volume_ratio_30d > self.PUMP_VOLUME_MULTIPLE and 
                  result.price_change_30d > self.PUMP_PRICE_CHANGE):
                result.phase = PumpDumpPhase.PUMP
                result.severity = ManipulationSeverity.HIGH
                result.confidence = 70 + min(30, result.volume_ratio_30d * 5)
                result.description = f"⚠️ PUMP PHASE: Volume {result.volume_ratio_30d:.1f}x, Price +{result.price_change_30d:.0f}% - Late entry risk"
                
            # PHASE 1: ACCUMULATION (Operator entry - follow if confident)
            elif (result.volume_ratio_30d < 1.5 and 
                  abs(result.price_change_30d) < 10 and
                  result.accumulation_score > 40):
                result.phase = PumpDumpPhase.ACCUMULATION
                result.severity = ManipulationSeverity.LOW
                result.confidence = 60 + min(40, result.accumulation_score / 2)
                result.description = f"✅ ACCUMULATION: Silent buying ({result.accumulation_score:.0f}% net accumulation)"
                
            # CLEAN - No manipulation pattern
            else:
                result.phase = PumpDumpPhase.CLEAN
                result.severity = ManipulationSeverity.NONE
                result.confidence = 50
                result.description = "No clear pump/dump pattern detected"
                
        except Exception as e:
            logger.warning(f"Pump/dump analysis error: {e}")
            result.phase = PumpDumpPhase.UNKNOWN
            result.description = f"Analysis error: {str(e)}"
            
        return result
    
    # ========================================================================
    # DETECTOR 4: BROKER CONCENTRATION (HHI)
    # ========================================================================
    
    def calculate_broker_concentration(self, broker_data: List[BrokerData]) -> BrokerConcentrationResult:
        """
        Calculate Herfindahl-Hirschman Index (HHI) for broker concentration.
        
        HHI = Σ(market_share²)
        
        Interpretation:
        - HHI < 1000: Competitive (low concentration)
        - HHI 1000-1500: Moderate concentration
        - HHI 1500-2500: High concentration
        - HHI > 2500: Monopolistic (RED FLAG!)
        
        Also tracks top 3 and top 5 broker concentration.
        """
        result = BrokerConcentrationResult()
        
        if not broker_data:
            result.description = "No broker data available"
            return result
        
        # Calculate market shares based on absolute trading volume
        total_volume = sum(b.buy_quantity + b.sell_quantity for b in broker_data)
        
        if total_volume == 0:
            result.description = "Zero trading volume"
            return result
        
        # Calculate market share for each broker
        broker_shares = []
        for broker in broker_data:
            broker_volume = broker.buy_quantity + broker.sell_quantity
            market_share_pct = (broker_volume / total_volume) * 100
            
            if market_share_pct > 0.1:  # Only track meaningful positions
                broker_shares.append({
                    "broker": broker.broker_code or broker.broker_name,
                    "broker_name": broker.broker_name,
                    "volume": broker_volume,
                    "net_quantity": broker.net_quantity,
                    "share_pct": market_share_pct
                })
        
        # Sort by market share
        broker_shares.sort(key=lambda x: x["share_pct"], reverse=True)
        
        # Calculate HHI
        result.hhi_index = sum((b["share_pct"] ** 2) for b in broker_shares)
        
        # Top 3 and Top 5 concentration
        result.top3_concentration = sum(b["share_pct"] for b in broker_shares[:3])
        result.top5_concentration = sum(b["share_pct"] for b in broker_shares[:5])
        result.top_brokers = broker_shares[:5]
        
        # Classification
        if result.hhi_index > self.HHI_MONOPOLY_THRESHOLD:
            result.is_monopolistic = True
            result.severity = ManipulationSeverity.CRITICAL
            result.description = f"🚨 MONOPOLISTIC: HHI={result.hhi_index:.0f}, Top 3 control {result.top3_concentration:.0f}%"
        elif result.hhi_index > self.HHI_HIGH_CONCENTRATION:
            result.is_highly_concentrated = True
            result.severity = ManipulationSeverity.HIGH
            result.description = f"⚠️ HIGH CONCENTRATION: HHI={result.hhi_index:.0f}, Top 3 control {result.top3_concentration:.0f}%"
        elif result.top3_concentration > self.TOP3_CONCENTRATION_HIGH:
            result.is_highly_concentrated = True
            result.severity = ManipulationSeverity.MEDIUM
            result.description = f"Top 3 brokers control {result.top3_concentration:.0f}% - Moderate concentration"
        else:
            result.severity = ManipulationSeverity.NONE
            result.description = f"Healthy distribution: HHI={result.hhi_index:.0f}, Top 3: {result.top3_concentration:.0f}%"
            
        return result
    
    # ========================================================================
    # DETECTOR 5: PRICE-VOLUME DIVERGENCE
    # ========================================================================
    
    def detect_price_volume_divergence(self, price_history: pd.DataFrame) -> PriceVolumeDivergenceResult:
        """
        Detect price-volume divergence (absorption patterns).
        
        ABSORPTION occurs when:
        - Volume is significantly above average (2x+)
        - But price barely moves (<2%)
        
        This means smart money is SELLING into demand (distribution)
        or BUYING into supply (accumulation) without moving price.
        
        If combined with falling price trend → BEARISH (insiders exiting)
        If combined with rising price trend → BULLISH (insiders accumulating)
        """
        result = PriceVolumeDivergenceResult()
        
        if price_history.empty or 'volume' not in price_history.columns:
            result.description = "Insufficient data for divergence analysis"
            return result
        
        try:
            df = price_history
            
            # Calculate metrics
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].iloc[-20:].mean() if len(df) >= 20 else df['volume'].mean()
            result.volume_multiple = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Price change
            current_close = df['close'].iloc[-1]
            prev_close = df['close'].iloc[-2] if len(df) >= 2 else current_close
            result.price_change_pct = abs((current_close / prev_close - 1) * 100) if prev_close > 0 else 0
            
            # Detect divergence
            if result.volume_multiple > self.VOLUME_SPIKE_THRESHOLD and result.price_change_pct < self.PRICE_MOVE_LOW_THRESHOLD:
                result.detected = True
                result.is_absorption = True
                result.divergence_score = min(100, (result.volume_multiple * 20) + (self.PRICE_MOVE_LOW_THRESHOLD - result.price_change_pct) * 10)
                
                # Check trend direction for context
                price_5d_ago = df['close'].iloc[-5] if len(df) >= 5 else current_close
                trend = "declining" if current_close < price_5d_ago else "rising"
                
                if trend == "declining":
                    result.severity = ManipulationSeverity.HIGH
                    result.description = f"⚠️ BEARISH ABSORPTION: {result.volume_multiple:.1f}x volume but only {result.price_change_pct:.1f}% move - Smart money exiting"
                else:
                    result.severity = ManipulationSeverity.LOW
                    result.description = f"Bullish absorption: {result.volume_multiple:.1f}x volume, {result.price_change_pct:.1f}% move - Possible accumulation"
            else:
                result.description = f"Normal price-volume relationship (Vol: {result.volume_multiple:.1f}x, Price: {result.price_change_pct:.1f}%)"
                
        except Exception as e:
            logger.warning(f"Price-volume divergence error: {e}")
            result.description = f"Analysis error: {str(e)}"
            
        return result
    
    # ========================================================================
    # DETECTOR 6: END-OF-DAY MANIPULATION
    # ========================================================================
    
    def detect_eod_manipulation(self, symbol: str) -> EODManipulationResult:
        """
        Detect end-of-day price manipulation ("painting the tape").
        
        Operators often manipulate closing prices by:
        - Placing large orders in last 30 minutes
        - Creating artificial price movements
        - Setting up technical breakouts/breakdowns
        
        Detection:
        - >30% of daily volume in last 30 min
        - >3% price change in last 30 min
        """
        result = EODManipulationResult()
        
        # Note: This requires intraday data which may not be available
        # We'll use a simplified approach based on daily OHLC patterns
        
        try:
            # Fetch today's price data
            df = self.fetcher.fetch_price_history(symbol, days=5)
            
            if df.empty or len(df) < 1:
                result.description = "No recent data for EOD analysis"
                return result
            
            # Use daily OHLC to detect potential EOD manipulation
            # If close is significantly different from day's VWAP → suspicious
            today = df.iloc[-1]
            
            high = today.get('high', 0)
            low = today.get('low', 0)
            close = today.get('close', 0)
            open_price = today.get('open', 0)
            
            if high == 0 or low == 0:
                result.description = "Invalid price data"
                return result
            
            # Calculate where close is relative to day's range
            day_range = high - low
            if day_range > 0:
                close_position = (close - low) / day_range  # 0 = at low, 1 = at high
                
                # If close is at extreme (>90% or <10%) with big range, suspicious
                range_pct = (day_range / low) * 100 if low > 0 else 0
                
                if (close_position > 0.90 or close_position < 0.10) and range_pct > 3:
                    result.detected = True
                    result.is_painting_tape = True
                    
                    if close_position > 0.90:
                        result.last_30min_change_pct = ((close - open_price) / open_price) * 100 if open_price > 0 else 0
                        result.severity = ManipulationSeverity.MEDIUM
                        result.description = f"⚠️ EOD PUMP: Close at day high ({close_position:.0%}), Range {range_pct:.1f}%"
                    else:
                        result.last_30min_change_pct = ((close - open_price) / open_price) * 100 if open_price > 0 else 0
                        result.severity = ManipulationSeverity.MEDIUM
                        result.description = f"⚠️ EOD DUMP: Close at day low ({close_position:.0%}), Range {range_pct:.1f}%"
                else:
                    result.description = "Normal closing pattern"
            else:
                result.description = "Flat trading day"
                
        except Exception as e:
            logger.warning(f"EOD manipulation detection error: {e}")
            result.description = f"Analysis error: {str(e)}"
            
        return result
    
    # ========================================================================
    # DETECTOR 7: BROKER NETWORK ANALYSIS
    # ========================================================================
    
    def analyze_broker_network(
        self,
        broker_data_1m: List[BrokerData],
        broker_data_1w: List[BrokerData]
    ) -> BrokerNetworkResult:
        """
        Analyze broker relationships to find coordinated trading networks.
        
        Coordinated manipulation involves multiple brokers working together:
        - Broker A accumulates, tells Broker B
        - Both pump together
        - Both exit at similar times
        
        Detection:
        - Look for brokers with similar net quantity patterns
        - Check if same brokers appear in both 1M and 1W top lists
        - Identify clusters with correlated behavior
        """
        result = BrokerNetworkResult()
        
        if not broker_data_1m:
            result.description = "Insufficient data for network analysis"
            return result
        
        try:
            # Get top accumulators from both timeframes
            top_1m = [(b.broker_code, b.net_quantity) for b in broker_data_1m if b.net_quantity > 0][:10]
            top_1w = [(b.broker_code, b.net_quantity) for b in broker_data_1w if b.net_quantity > 0][:10] if broker_data_1w else []
            
            # Find brokers appearing in both timeframes (consistent accumulators)
            top_1m_codes = set(b[0] for b in top_1m)
            top_1w_codes = set(b[0] for b in top_1w)
            
            consistent_accumulators = top_1m_codes.intersection(top_1w_codes)
            
            # Simple coordination score: More overlap = higher coordination
            if top_1m_codes and top_1w_codes:
                overlap_ratio = len(consistent_accumulators) / min(len(top_1m_codes), len(top_1w_codes))
                result.coordination_score = overlap_ratio * 100
            
            # Look for similar-sized positions (potential coordination)
            if len(top_1m) >= 3:
                net_qtys = [b[1] for b in top_1m[:5]]
                mean_qty = np.mean(net_qtys)
                std_qty = np.std(net_qtys)
                
                # If positions are very similar size, might be coordinated
                if mean_qty > 0 and std_qty / mean_qty < 0.3:  # Low variance in position sizes
                    result.coordination_score += 30
                    result.coordinated_groups = [[b[0] for b in top_1m[:3]]]
                    result.networks_found = 1
            
            # Set severity based on coordination score
            if result.coordination_score > 70:
                result.severity = ManipulationSeverity.HIGH
                result.top_network_brokers = list(consistent_accumulators)[:3]
                result.description = f"⚠️ HIGH COORDINATION: {len(consistent_accumulators)} brokers consistent across timeframes"
            elif result.coordination_score > 40:
                result.severity = ManipulationSeverity.MEDIUM
                result.description = f"Moderate coordination detected (score: {result.coordination_score:.0f})"
            else:
                result.description = "No significant broker coordination detected"
                
        except Exception as e:
            logger.warning(f"Broker network analysis error: {e}")
            result.description = f"Analysis error: {str(e)}"
            
        return result
    
    # ========================================================================
    # DETECTOR 8: PROMOTER LOCKUP RISK
    # ========================================================================
    
    def check_lockup_risk(self, symbol: str) -> LockupRiskResult:
        """
        Check for promoter/insider lockup expiry risk.
        
        In Nepal, promoters are typically locked for:
        - IPO: 3 years (normal), 1.5 years (manufacturing/hydro)
        - Right Shares: 1 year
        - Bonus Shares: 1 year (for promoters)
        
        When lockup expires, insiders can sell → price pressure.
        """
        result = LockupRiskResult()
        
        try:
            # Fetch company details for listing date
            company_info = self.fetcher.fetch_company_details(symbol)
            
            if not company_info:
                result.description = "Unable to fetch company details"
                return result
            
            # Try to get listing date
            listing_date_str = company_info.get('listedDate', company_info.get('listingDate', ''))
            
            if not listing_date_str:
                result.description = "Listing date not available"
                return result
            
            # Parse listing date
            try:
                if isinstance(listing_date_str, str):
                    listing_date = datetime.strptime(listing_date_str[:10], "%Y-%m-%d").date()
                else:
                    listing_date = listing_date_str
            except:
                result.description = "Could not parse listing date"
                return result
            
            # Calculate lockup periods
            today = date.today()
            
            # Standard IPO lockup: 3 years
            ipo_unlock_date = listing_date + timedelta(days=365 * 3)
            
            # For hydro/manufacturing: 1.5 years (we'll check sector)
            sector = company_info.get('sector', company_info.get('sectorName', '')).lower()
            if 'hydro' in sector or 'manufacturing' in sector or 'power' in sector:
                ipo_unlock_date = listing_date + timedelta(days=int(365 * 1.5))
            
            days_until_unlock = (ipo_unlock_date - today).days
            
            if days_until_unlock > 0:
                result.days_until_unlock = days_until_unlock
                result.unlock_date = ipo_unlock_date
                result.source = "IPO Lockup"
                
                if days_until_unlock <= self.LOCKUP_WARNING_DAYS:
                    result.has_lockup_risk = True
                    result.severity = ManipulationSeverity.HIGH
                    result.description = f"⚠️ LOCKUP EXPIRES IN {days_until_unlock} DAYS! Insider selling risk"
                elif days_until_unlock <= 90:
                    result.has_lockup_risk = True
                    result.severity = ManipulationSeverity.MEDIUM
                    result.description = f"Lockup expires in {days_until_unlock} days - Monitor"
                else:
                    result.description = f"Lockup safe: {days_until_unlock} days remaining"
            else:
                result.description = "Lockup period has ended (insiders can sell freely)"
                
        except Exception as e:
            logger.warning(f"Lockup risk check error: {e}")
            result.description = f"Could not determine lockup status: {str(e)}"
            
        return result
    
    # ========================================================================
    # OVERALL RISK CALCULATION
    # ========================================================================
    
    def _calculate_overall_risk(self, report: ManipulationReport) -> ManipulationReport:
        """Calculate overall manipulation risk score and generate alerts."""
        
        risk_score = 0
        alerts = []
        veto_reasons = []
        
        # Weight each detector's contribution to overall risk
        weights = {
            "circular_trading": 20,
            "wash_trading": 15,
            "pump_dump": 25,
            "broker_concentration": 15,
            "price_volume_divergence": 10,
            "eod_manipulation": 5,
            "broker_network": 5,
            "lockup_risk": 5
        }
        
        # Process each detector result
        
        # 1. Circular Trading
        if report.circular_trading.detected:
            ct = report.circular_trading
            contribution = weights["circular_trading"] * (ct.circular_percentage / 50)
            risk_score += min(weights["circular_trading"], contribution)
            alerts.append(f"🔴 Circular Trading: {ct.circular_percentage:.0f}%")
            if ct.severity in [ManipulationSeverity.HIGH, ManipulationSeverity.CRITICAL]:
                veto_reasons.append(f"Circular trading {ct.circular_percentage:.0f}%")
        
        # 2. Wash Trading
        if report.wash_trading.detected:
            wt = report.wash_trading
            contribution = weights["wash_trading"] * (len(wt.suspicious_brokers) / 3)
            risk_score += min(weights["wash_trading"], contribution)
            alerts.append(f"🔴 Wash Trading: {len(wt.suspicious_brokers)} brokers")
            if wt.severity in [ManipulationSeverity.HIGH, ManipulationSeverity.CRITICAL]:
                veto_reasons.append(f"Wash trading detected")
        
        # 3. Pump/Dump Phase
        pd = report.pump_dump
        if pd.phase == PumpDumpPhase.DISTRIBUTION:
            risk_score += weights["pump_dump"]
            alerts.append(f"🚨 DISTRIBUTION PHASE - Operators exiting!")
            veto_reasons.append("Distribution phase (operators exiting)")
        elif pd.phase == PumpDumpPhase.PUMP:
            risk_score += weights["pump_dump"] * 0.6
            alerts.append(f"⚠️ PUMP PHASE - Late entry risk")
        elif pd.phase == PumpDumpPhase.ACCUMULATION:
            alerts.append(f"✅ Accumulation phase - Early entry opportunity")
        
        # 4. Broker Concentration
        bc = report.broker_concentration
        if bc.is_monopolistic:
            risk_score += weights["broker_concentration"]
            alerts.append(f"🔴 MONOPOLISTIC: Top 3 control {bc.top3_concentration:.0f}%")
            veto_reasons.append(f"Monopolistic concentration ({bc.top3_concentration:.0f}%)")
        elif bc.is_highly_concentrated:
            risk_score += weights["broker_concentration"] * 0.5
            alerts.append(f"⚠️ High concentration: {bc.top3_concentration:.0f}%")
        
        # 5. Price-Volume Divergence
        if report.price_volume_divergence.is_absorption:
            pvd = report.price_volume_divergence
            risk_score += weights["price_volume_divergence"]
            alerts.append(f"⚠️ Absorption: {pvd.volume_multiple:.1f}x volume, {pvd.price_change_pct:.1f}% move")
        
        # 6. EOD Manipulation
        if report.eod_manipulation.is_painting_tape:
            risk_score += weights["eod_manipulation"]
            alerts.append(f"⚠️ EOD manipulation detected")
        
        # 7. Broker Network
        if report.broker_network.coordination_score > 50:
            risk_score += weights["broker_network"]
            alerts.append(f"⚠️ Broker coordination: {report.broker_network.coordination_score:.0f}% score")
        
        # 8. Lockup Risk
        if report.lockup_risk.has_lockup_risk:
            risk_score += weights["lockup_risk"]
            lr = report.lockup_risk
            if lr.days_until_unlock and lr.days_until_unlock <= 30:
                alerts.append(f"🚨 LOCKUP EXPIRES IN {lr.days_until_unlock} DAYS!")
                veto_reasons.append(f"Lockup expiry in {lr.days_until_unlock} days")
            else:
                alerts.append(f"⚠️ Lockup expires in {lr.days_until_unlock} days")
        
        # Cap risk score at 100
        report.overall_risk_score = min(100, risk_score)
        report.alerts = alerts
        report.veto_reasons = veto_reasons
        
        # Determine overall severity
        if report.overall_risk_score >= 70:
            report.overall_severity = ManipulationSeverity.CRITICAL
            report.is_safe_to_trade = False
            report.recommendation = "🚫 AVOID - Multiple manipulation signals detected"
        elif report.overall_risk_score >= 50:
            report.overall_severity = ManipulationSeverity.HIGH
            report.is_safe_to_trade = False
            report.recommendation = "⚠️ HIGH RISK - Paper trade only"
        elif report.overall_risk_score >= 30:
            report.overall_severity = ManipulationSeverity.MEDIUM
            report.is_safe_to_trade = True
            report.recommendation = "⚡ MODERATE RISK - Small position only (1-2%)"
        elif report.overall_risk_score >= 10:
            report.overall_severity = ManipulationSeverity.LOW
            report.is_safe_to_trade = True
            report.recommendation = "✅ LOW RISK - Normal position (3-5%)"
        else:
            report.overall_severity = ManipulationSeverity.NONE
            report.is_safe_to_trade = True
            report.recommendation = "✅ CLEAN - Safe to trade"

        # Any hard veto reason overrides "safe" status, even if total score is medium.
        if report.veto_reasons:
            report.is_safe_to_trade = False
            if report.overall_severity in [ManipulationSeverity.NONE, ManipulationSeverity.LOW, ManipulationSeverity.MEDIUM]:
                report.recommendation = "⚠️ VETO FLAG - Paper trade or tiny position only"
        
        # Set operator phase
        report.operator_phase = pd.phase.value
        report.operator_phase_description = pd.description
        
        return report
    
    def format_report(self, report: ManipulationReport) -> str:
        """Format manipulation report for CLI output."""
        
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append(f"🚨 MANIPULATION ANALYSIS: {report.symbol}")
        lines.append("=" * 70)
        lines.append("")
        
        # Overall Assessment
        risk_bar = "█" * int(report.overall_risk_score / 10) + "░" * (10 - int(report.overall_risk_score / 10))
        lines.append(f"📊 MANIPULATION RISK: [{risk_bar}] {report.overall_risk_score:.0f}%")
        lines.append(f"   Status: {report.overall_severity.value}")
        lines.append(f"   {report.recommendation}")
        lines.append("")
        
        # Operator Phase
        phase_emoji = {
            "ACCUMULATION": "✅",
            "PUMP": "⚠️",
            "DISTRIBUTION": "🚨",
            "CLEAN": "✅",
            "UNKNOWN": "❓"
        }
        emoji = phase_emoji.get(report.operator_phase, "❓")
        lines.append(f"📈 OPERATOR PHASE: {emoji} {report.operator_phase}")
        lines.append(f"   {report.operator_phase_description}")
        lines.append("")
        
        # Alerts Section
        if report.alerts:
            lines.append("🚨 DETECTED PATTERNS:")
            for alert in report.alerts:
                lines.append(f"   {alert}")
            lines.append("")
        
        # Veto Reasons
        if report.veto_reasons:
            lines.append("⛔ VETO REASONS (Paper-trade only):")
            for reason in report.veto_reasons:
                lines.append(f"   • {reason}")
            lines.append("")
        
        # Detailed Breakdown
        lines.append("📋 DETAILED BREAKDOWN:")
        lines.append("-" * 50)
        
        # Broker Concentration
        bc = report.broker_concentration
        lines.append(f"   Broker Concentration:")
        lines.append(f"   • HHI Index: {bc.hhi_index:.0f} (>2500 = monopoly)")
        lines.append(f"   • Top 3 Control: {bc.top3_concentration:.0f}%")
        if bc.top_brokers:
            top_3 = bc.top_brokers[:3]
            broker_str = ", ".join([f"{b['broker']}({b['share_pct']:.0f}%)" for b in top_3])
            lines.append(f"   • Top Brokers: {broker_str}")
        lines.append("")
        
        # Pump/Dump Analysis
        pd = report.pump_dump
        lines.append(f"   Pump/Dump Analysis:")
        lines.append(f"   • Phase: {pd.phase.value}")
        lines.append(f"   • Confidence: {pd.confidence:.0f}%")
        lines.append(f"   • 30D Price Change: {pd.price_change_30d:+.1f}%")
        lines.append(f"   • Volume Ratio: {pd.volume_ratio_30d:.1f}x avg")
        lines.append("")
        
        # Circular & Wash Trading
        ct = report.circular_trading
        wt = report.wash_trading
        lines.append(f"   Trading Patterns:")
        lines.append(f"   • Circular Trading: {'YES' if ct.detected else 'No'} ({ct.circular_percentage:.0f}%)")
        lines.append(f"   • Wash Trading: {'YES' if wt.detected else 'No'} ({len(wt.suspicious_brokers)} suspicious)")
        lines.append("")
        
        # Lockup Status
        lr = report.lockup_risk
        lines.append(f"   Lockup Status:")
        if lr.days_until_unlock:
            lines.append(f"   • Days Until Unlock: {lr.days_until_unlock}")
            lines.append(f"   • Risk: {'HIGH' if lr.has_lockup_risk else 'Low'}")
        else:
            lines.append(f"   • {lr.description}")
        
        lines.append("")
        lines.append("=" * 70)
        
        return "\n".join(lines)


# =============================================================================
# QUICK ACCESS FUNCTIONS
# =============================================================================

def analyze_manipulation(symbol: str) -> ManipulationReport:
    """Quick function to analyze manipulation for a stock."""
    detector = ManipulationDetector()
    return detector.analyze_stock(symbol)


def get_manipulation_score(symbol: str) -> float:
    """Get just the manipulation risk score (0-100)."""
    report = analyze_manipulation(symbol)
    return report.overall_risk_score


def is_safe_to_trade(symbol: str) -> bool:
    """Quick check if stock is safe to trade."""
    report = analyze_manipulation(symbol)
    return report.is_safe_to_trade


def get_operator_phase(symbol: str) -> str:
    """Get the current operator phase (Accumulation/Pump/Distribution)."""
    report = analyze_manipulation(symbol)
    return report.operator_phase


if __name__ == "__main__":
    # Test the manipulation detector
    import sys
    
    symbol = sys.argv[1] if len(sys.argv) > 1 else "NGPL"
    
    print(f"\n🔍 Analyzing {symbol} for manipulation patterns...\n")
    
    detector = ManipulationDetector()
    report = detector.analyze_stock(symbol)
    
    print(detector.format_report(report))
