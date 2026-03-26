// API client for NEPSE AI Trading backend
// Comprehensive API covering all paper_trader.py features

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ScanParams {
  strategy?: 'momentum' | 'value';
  sector?: string;
  quick?: boolean;
  maxPrice?: number;
  limit?: number;
}

interface StealthParams {
  sector?: string;
  maxPrice?: number;
}

interface AnalyzeParams {
  strategy?: 'momentum' | 'value';
}

interface SignalParams {
  symbol: string;
}

interface IPOExitParams {
  symbol: string;
}

interface PositionAdvisorParams {
  symbol: string;
  buyPrice: number;
  buyDate?: string;
}

interface CalendarParams {
  days?: number;
  maxStocks?: number;
  sector?: string;
}

interface SmartMoneyParams {
  sector?: string;
}

interface BrokerIntelligenceParams {
  sector?: string;
}

// Generic fetch wrapper with error handling
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

// Market Scanner
export async function runScan(params: ScanParams = {}, signal?: AbortSignal) {
  const searchParams = new URLSearchParams();
  if (params.strategy) searchParams.set('strategy', params.strategy);
  if (params.sector) searchParams.set('sector', params.sector);
  if (params.quick !== undefined) searchParams.set('quick', String(params.quick));
  if (params.maxPrice) searchParams.set('max_price', String(params.maxPrice));
  if (params.limit) searchParams.set('limit', String(params.limit));

  return fetchAPI<ScanResponse>(`/api/scan?${searchParams}`, { signal });
}

// Stealth Radar
export async function runStealthScan(params: StealthParams = {}, signal?: AbortSignal) {
  const searchParams = new URLSearchParams();
  if (params.sector) searchParams.set('sector', params.sector);
  if (params.maxPrice) searchParams.set('max_price', String(params.maxPrice));

  return fetchAPI<StealthResponse>(`/api/stealth-scan?${searchParams}`, { signal });
}

// Market Regime
export async function getMarketRegime(signal?: AbortSignal) {
  return fetchAPI<MarketRegimeResponse>('/api/market-regime', { signal });
}

// Portfolio Status
export async function getPortfolioStatus(signal?: AbortSignal) {
  return fetchAPI<PortfolioResponse>('/api/portfolio/status', { signal });
}

// Update Portfolio (check targets/stops)
export async function updatePortfolio(signal?: AbortSignal) {
  return fetchAPI<{ success: boolean; updates: any[]; message?: string }>('/api/portfolio/update', {
    method: 'POST',
    signal,
  });
}

// Single Stock Analysis
export async function analyzeStock(symbol: string, params: AnalyzeParams = {}, signal?: AbortSignal) {
  const searchParams = new URLSearchParams();
  if (params.strategy) searchParams.set('strategy', params.strategy);

  return fetchAPI<AnalyzeResponse>(`/api/analyze/${symbol}?${searchParams}`, { signal });
}

// Add to Portfolio
export async function addToPortfolio(symbol: string, quantity: number, price: number) {
  return fetchAPI<{ success: boolean; trade_id: number }>('/api/portfolio/buy', {
    method: 'POST',
    body: JSON.stringify({ symbol, quantity, price }),
  });
}

// ============== NEW ENDPOINTS ==============

// Trading Signal Generator (--signal)
export async function getSignal(params: SignalParams, signal?: AbortSignal) {
  return fetchAPI<SignalResponse>(`/api/signal/${params.symbol}`, { signal });
}

// IPO Exit Analyzer (--ipo-exit)
export async function getIPOExit(params: IPOExitParams, signal?: AbortSignal) {
  return fetchAPI<IPOExitResponse>(`/api/ipo-exit/${params.symbol}`, { signal });
}

// Position Advisor (--hold-or-sell)
export async function getPositionAdvice(params: PositionAdvisorParams, signal?: AbortSignal) {
  const searchParams = new URLSearchParams();
  searchParams.set('buy_price', String(params.buyPrice));
  if (params.buyDate) searchParams.set('buy_date', params.buyDate);
  
  return fetchAPI<PositionAdvisorResponse>(`/api/hold-or-sell/${params.symbol}?${searchParams}`, { signal });
}

// Trading Calendar (--calendar)
export async function getTradingCalendar(params: CalendarParams = {}, signal?: AbortSignal) {
  const searchParams = new URLSearchParams();
  if (params.days) searchParams.set('days', String(params.days));
  if (params.maxStocks) searchParams.set('max_stocks', String(params.maxStocks));
  if (params.sector) searchParams.set('sector', params.sector);
  
  return fetchAPI<CalendarResponse>(`/api/calendar?${searchParams}`, { signal });
}

// Smart Money Flow (--smart-money)
export async function getSmartMoney(params: SmartMoneyParams = {}, signal?: AbortSignal) {
  const searchParams = new URLSearchParams();
  if (params.sector) searchParams.set('sector', params.sector);
  
  return fetchAPI<SmartMoneyResponse>(`/api/smart-money?${searchParams}`, { signal });
}

// Market Heatmap (--heatmap)
export async function getHeatmap(signal?: AbortSignal) {
  return fetchAPI<HeatmapResponse>('/api/heatmap', { signal });
}

// Sector Rotation (--sector-rotation)
export async function getSectorRotation(signal?: AbortSignal) {
  return fetchAPI<SectorRotationResponse>('/api/sector-rotation', { signal });
}

// Market Positioning (--positioning)
export async function getPositioning(signal?: AbortSignal) {
  return fetchAPI<PositioningResponse>('/api/positioning', { signal });
}

// Broker Intelligence (--broker-intelligence)
export async function getBrokerIntelligence(params: BrokerIntelligenceParams = {}, signal?: AbortSignal) {
  const searchParams = new URLSearchParams();
  if (params.sector) searchParams.set('sector', params.sector);
  
  return fetchAPI<BrokerIntelligenceResponse>(`/api/broker-intelligence?${searchParams}`, { signal });
}

// Tech Score (--tech-score)
export async function getTechScore(symbol: string, signal?: AbortSignal) {
  return fetchAPI<TechScoreResponse>(`/api/tech-score/${symbol}`, { signal });
}

// Price Targets (--price-targets)
export async function getPriceTargets(symbol: string, signal?: AbortSignal) {
  return fetchAPI<PriceTargetsResponse>(`/api/price-targets/${symbol}`, { signal });
}

// Order Flow (--order-flow)
export async function getOrderFlow(symbol: string, signal?: AbortSignal) {
  return fetchAPI<OrderFlowResponse>(`/api/order-flow/${symbol}`, { signal });
}

// Bulk Deals (--bulk-deals)
export async function getBulkDeals(signal?: AbortSignal) {
  return fetchAPI<BulkDealsResponse>('/api/bulk-deals', { signal });
}

// Dividend Forecast (--dividend-forecast)
export async function getDividendForecast(symbol: string, signal?: AbortSignal) {
  return fetchAPI<DividendForecastResponse>(`/api/dividend-forecast/${symbol}`, { signal });
}

// ============== Type Definitions ==============

export interface StockScanResult {
  rank: number;
  symbol: string;
  name: string;
  sector: string;
  ltp: number;
  score: number;
  verdict: string;
  verdict_emoji: string;
  entry_price: number;
  target_price: number;
  stop_loss: number;
  hold_days: string;
  pillar_broker: number;
  pillar_unlock: number;
  pillar_fundamental: number;
  pillar_technical: number;
  distribution_risk: string;
  distribution_risk_emoji: string;
  broker_profit_pct: number;
  vwap_cost: number;
  rsi: number;
  volume_spike: number;
  buyer_dominance: number;
  pe_ratio: number;
  roe: number;
  key_signals: string[];
  red_flags: string[];
}

export interface ScanResponse {
  success: boolean;
  timestamp: string;
  market_regime: string;
  market_regime_emoji: string;
  strategy: string;
  sector: string | null;
  total_analyzed: number;
  results: StockScanResult[];
}

export interface StealthStock {
  symbol: string;
  sector: string;
  ltp: number;
  broker_score: number;
  broker_score_pct: number;
  technical_score: number;
  technical_score_pct: number;
  distribution_risk: string;
  broker_profit_pct: number;
  buyer_dominance: number;
}

export interface SectorRotation {
  sector: string;
  stock_count: number;
  avg_broker_score: number;
  stocks: StealthStock[];
}

export interface StealthResponse {
  success: boolean;
  timestamp: string;
  total_stealth_stocks: number;
  sectors: SectorRotation[];
}

export interface MarketRegimeResponse {
  regime: string;
  regime_emoji: string;
  reason: string;
  nepse_index: number;
  ema50: number;
  timestamp: string;
}

export interface PortfolioPosition {
  id: number;
  symbol: string;
  entry_date: string;
  entry_price: number;
  quantity: number;
  current_price: number;
  target_price: number;
  stop_loss: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  days_held: number;
  status: string;
}

export interface PortfolioStats {
  total_trades: number;
  open_positions: number;
  closed_positions: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  best_trade: number;
  worst_trade: number;
}

export interface PortfolioResponse {
  success: boolean;
  timestamp: string;
  stats: PortfolioStats;
  positions: PortfolioPosition[];
}

export interface PillarScore {
  name: string;
  score: number;
  max_score: number;
  percentage: number;
}

export interface SingleStockAnalysis {
  symbol: string;
  name: string;
  sector: string;
  ltp: number;
  momentum_score: number;
  value_score: number;
  momentum_verdict: string;
  value_verdict: string;
  pillars: Record<string, PillarScore>;
  pe_ratio: number;
  pe_status: string;
  eps: number;
  eps_annualized: number;
  book_value: number;
  pbv: number;
  roe: number;
  roe_status: string;
  rsi: number;
  rsi_status: string;
  ema_signal: string;
  volume_spike: number;
  atr: number;
  distribution_risk: string;
  broker_avg_cost: number;
  broker_profit_pct: number;
  distribution_warning: string;
  entry_price: number;
  target_price: number;
  stop_loss: number;
  hold_days: string;
  long_term_recommendation: string;
  short_term_recommendation: string;
  friend_recommendation: string;
  red_flags: string[];
  price_history_7d: Array<{ date: string; close: number }>;
  price_trend_7d: number;
  price_trend_30d: number;
  price_trend_90d: number;
}

export interface AnalyzeResponse {
  success: boolean;
  timestamp: string;
  data: SingleStockAnalysis;
}

// ============== NEW TYPE DEFINITIONS ==============

// Signal Generator Types
export interface SignalResponse {
  success: boolean;
  timestamp: string;
  data: {
    symbol: string;
    name: string;
    sector: string;
    current_price: number;
    signal: 'BUY' | 'SELL' | 'HOLD' | 'WAIT';
    signal_emoji: string;
    confidence: number;
    trend_phase: string;
    
    // Entry Analysis
    entry: {
      target_zone_low: number;
      target_zone_high: number;
      price_gap_pct: number;
      entry_date: string;
      conditions: string[];
    };
    
    // Hold Analysis
    hold: {
      duration_days: number;
      stop_loss: number;
      stop_loss_pct: number;
      trail_stop_pct: number;
    };
    
    // Exit Targets
    targets: Array<{
      level: string;
      price: number;
      gain_pct: number;
      probability: number;
    }>;
    
    // Risk Management
    risk: {
      risk_reward: number;
      position_size_pct: number;
      trailing_stop_pct: number;
    };
    
    warnings: string[];
    recommendation: string;
  };
}

// IPO Exit Types
export interface IPOExitResponse {
  success: boolean;
  timestamp: string;
  data: {
    symbol: string;
    current_price: number;
    listing_price: number;
    gain_loss_pct: number;
    days_listed: number;
    
    // Volume Analysis
    volume_trend: {
      dates: string[];
      volumes: number[];
      trend: 'DECAY' | 'SPIKE' | 'DISTRIBUTION' | 'STABLE';
      interpretation: string;
    };
    
    // Broker Flow
    broker_flow: {
      net_quantity: number;
      flow_type: 'STRONG_ACCUMULATION' | 'ACCUMULATION' | 'NEUTRAL' | 'DISTRIBUTION' | 'STRONG_DISTRIBUTION';
      interpretation: string;
      top_buyers: Array<{ name: string; quantity: number }>;
      top_sellers: Array<{ name: string; quantity: number }>;
    };
    
    // Price Pattern
    price_pattern: {
      day2_low: number;
      buffer_pct: number;
      trend: 'UPTREND' | 'BREAKDOWN' | 'CONSOLIDATION';
    };
    
    // Exit Signals (scored)
    exit_signals: Array<{
      name: string;
      triggered: boolean;
      score: number;
      max_score: number;
    }>;
    total_exit_score: number;
    
    verdict: 'STRONG_HOLD' | 'HOLD' | 'WATCH' | 'CONSIDER_PARTIAL' | 'SELL' | 'URGENT_SELL';
    verdict_emoji: string;
    action: string;
    stop_loss: number;
    reasons: string[];
    warnings: string[];
  };
}

// Position Advisor Types
export interface PositionAdvisorResponse {
  success: boolean;
  timestamp: string;
  data: {
    symbol: string;
    name: string;
    
    // Position Info
    position: {
      buy_price: number;
      current_price: number;
      pnl_amount: number;
      pnl_pct: number;
      holding_period: string;
      days_held: number;
    };
    
    // Technical Position
    technical: {
      trend: string;
      momentum: string;
      support: number;
      resistance: number;
      rsi: number;
    };
    
    // Health Score
    health_score: number;
    health_breakdown: Array<{
      factor: string;
      score: number;
      max_score: number;
      weight_pct: number;
    }>;
    
    // Verdict
    verdict: 'STRONG_HOLD' | 'HOLD' | 'HOLD_CAUTIOUSLY' | 'BOOK_PARTIAL' | 'AVERAGE_DOWN' | 'EXIT' | 'URGENT_EXIT';
    verdict_emoji: string;
    
    // Recommendations
    actions: string[];
    exit_triggers: string[];
    stop_loss: number;
    targets: Array<{ level: string; price: number; gain_pct: number }>;
    
    warnings: string[];
  };
}

// Trading Calendar Types
export interface CalendarResponse {
  success: boolean;
  timestamp: string;
  data: {
    scan_date: string;
    days_ahead: number;
    total_stocks: number;
    
    calendar: Array<{
      date: string;
      day_name: string;
      stocks: Array<{
        symbol: string;
        name: string;
        sector: string;
        entry_price: number;
        target_price: number;
        stop_loss: number;
        confidence: number;
        reason: string;
      }>;
    }>;
  };
}

// Smart Money Types
export interface SmartMoneyResponse {
  success: boolean;
  timestamp: string;
  data: {
    summary: {
      accumulating: number;
      distributing: number;
      net_market_flow: number;
      sentiment: 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL';
    };
    
    top_buyers: Array<{
      name: string;
      stock_count: number;
      net_volume: number;
    }>;
    
    top_sellers: Array<{
      name: string;
      stock_count: number;
      net_volume: number;
    }>;
    
    stocks: Array<{
      symbol: string;
      name: string;
      price: number;
      flow_type: 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL';
      net_flow: number;
      smart_money_score: number;
    }>;
  };
}

// Heatmap Types
export interface HeatmapResponse {
  success: boolean;
  timestamp: string;
  data: {
    summary: {
      advancing: number;
      declining: number;
      unchanged: number;
      advance_pct: number;
      decline_pct: number;
      breadth: number;
    };
    
    sectors: Array<{
      name: string;
      stocks: Array<{
        symbol: string;
        name: string;
        ltp: number;
        change: number;
        change_pct: number;
      }>;
    }>;
  };
}

// Sector Rotation Types  
export interface SectorRotationResponse {
  success: boolean;
  timestamp: string;
  data: {
    ranking: Array<{
      rank: number;
      sector: string;
      momentum_score: number;
      weekly_change_pct: number;
      monthly_change_pct: number;
      signal: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG_SELL';
      signal_emoji: string;
    }>;
    
    rotation_signal: string;
    hot_sectors: string[];
    cold_sectors: string[];
  };
}

// Positioning Types
export interface PositioningResponse {
  success: boolean;
  timestamp: string;
  data: {
    overall: {
      stocks_above_sma20_pct: number;
      stocks_above_sma50_pct: number;
      stocks_above_sma200_pct: number;
      market_condition: 'OVERBOUGHT' | 'BULLISH' | 'NEUTRAL' | 'BEARISH' | 'OVERSOLD';
    };
    
    sectors: Array<{
      sector: string;
      above_sma20_pct: number;
      above_sma50_pct: number;
      condition: string;
    }>;
  };
}

// Broker Intelligence Types
export interface BrokerIntelligenceResponse {
  success: boolean;
  timestamp: string;
  data: {
    aggressive_brokers: Array<{
      broker: string;
      total_buying: number;
      stocks: Array<{ symbol: string; quantity: number }>;
    }>;
    
    stockwise: Array<{
      symbol: string;
      top_buyer: string;
      buyer_quantity: number;
      top_seller: string;
      seller_quantity: number;
      net_flow: number;
    }>;
  };
}

// Tech Score Types
export interface TechScoreResponse {
  success: boolean;
  timestamp: string;
  data: {
    symbol: string;
    composite_score: number;
    
    timeframes: Array<{
      timeframe: string;
      score: number;
      trend: string;
      signals: string[];
    }>;
    
    overall_signal: string;
  };
}

// Price Targets Types
export interface PriceTargetsResponse {
  success: boolean;
  timestamp: string;
  data: {
    symbol: string;
    current_price: number;
    
    targets: Array<{
      method: string;
      target_price: number;
      upside_pct: number;
      confidence: number;
    }>;
    
    support_levels: number[];
    resistance_levels: number[];
    
    consensus_target: number;
    consensus_upside_pct: number;
  };
}

// Order Flow Types
export interface OrderFlowResponse {
  success: boolean;
  timestamp: string;
  data: {
    symbol: string;
    
    delta: {
      buy_volume: number;
      sell_volume: number;
      net_delta: number;
      delta_pct: number;
    };
    
    absorption: {
      detected: boolean;
      type: 'BUYING' | 'SELLING' | 'NONE';
      strength: number;
    };
    
    liquidity_grabs: Array<{
      date: string;
      type: 'LOW_GRAB' | 'HIGH_GRAB';
      price: number;
    }>;
    
    signal: string;
  };
}

// Bulk Deals Types
export interface BulkDealsResponse {
  success: boolean;
  timestamp: string;
  data: {
    deals: Array<{
      date: string;
      symbol: string;
      buyer: string;
      seller: string;
      quantity: number;
      rate: number;
      value: number;
      signal: 'INSIDER_BUY' | 'INSIDER_SELL' | 'BLOCK_DEAL' | 'PROMOTER_ACTIVITY';
    }>;
  };
}

// Dividend Forecast Types
export interface DividendForecastResponse {
  success: boolean;
  timestamp: string;
  data: {
    symbol: string;
    
    historical: Array<{
      year: string;
      dividend_pct: number;
      eps: number;
    }>;
    
    forecast: {
      expected_dividend_pct: number;
      expected_amount_per_share: number;
      yield_on_current_price: number;
      confidence: number;
    };
    
    recommendation: string;
  };
}
