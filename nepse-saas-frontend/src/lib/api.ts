// API client for NEPSE AI Trading backend
// Comprehensive API covering all paper_trader.py features

// In deployed setup, frontend and backend are served behind same origin (`/api` ingress).
// Fallback to same-origin unless an explicit external API URL is provided.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

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
  quick?: boolean;
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
  maxPrice?: number;
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
  if (params.quick !== undefined) searchParams.set('quick', String(params.quick));

  // Returns StealthResponse (quick) OR {status:'pending', job_id} (full scan)
  return fetchAPI<StealthResponse | StealthJobPending>(`/api/stealth-scan?${searchParams}`, { signal });
}

export async function pollStealthJob(jobId: string): Promise<StealthJobStatus> {
  return fetchAPI<StealthJobStatus>(`/api/stealth-scan/status/${jobId}`);
}

// Stop running scans
export async function stopScan(): Promise<{ success: boolean; message: string }> {
  return fetchAPI('/api/scan/stop', { method: 'POST' });
}

export async function stopStealthScan(jobId?: string): Promise<{ success: boolean; message: string }> {
  if (jobId) {
    return fetchAPI(`/api/stealth-scan/stop/${jobId}`, { method: 'POST' });
  }
  return fetchAPI('/api/stealth-scan/stop', { method: 'POST' });
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

export async function stopAnalyze(symbol: string) {
  const encoded = encodeURIComponent(symbol);
  return fetchAPI<{ success: boolean; message: string }>(`/api/analyze/stop/${encoded}`, {
    method: 'POST',
  });
}

// Add to Portfolio
export async function addToPortfolio(symbol: string, quantity: number, price: number) {
  return fetchAPI<{ success: boolean; trade_id: number; message?: string }>('/api/portfolio/buy', {
    method: 'POST',
    body: JSON.stringify({ symbol, quantity, price }),
  });
}

// Edit existing portfolio position
export async function editPortfolioPosition(
  tradeId: number,
  payload: { quantity?: number; entry_price?: number; target_price?: number; stop_loss?: number }
) {
  return fetchAPI<{ success: boolean; message: string }>(`/api/portfolio/position/${tradeId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

// Close a portfolio position manually
export async function closePortfolioPosition(tradeId: number, exitPrice?: number) {
  return fetchAPI<{ success: boolean; message: string }>(`/api/portfolio/sell/${tradeId}`, {
    method: 'POST',
    body: JSON.stringify({ exit_price: exitPrice }),
  });
}

// Delete a portfolio position
export async function deletePortfolioPosition(tradeId: number) {
  return fetchAPI<{ success: boolean; message: string }>(`/api/portfolio/position/${tradeId}`, {
    method: 'DELETE',
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
  if (params.maxPrice) searchParams.set('max_price', String(params.maxPrice));
  
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

export interface StealthJobPending {
  success: boolean;
  status: 'pending';
  job_id: string;
  message: string;
}

export interface StealthJobStatus {
  status: 'pending' | 'running' | 'done' | 'error' | 'cancelled';
  started_at?: string;
  completed_at?: string;
  result?: StealthResponse;
  error?: string;
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
  company_name?: string;
  sector: string;
  ltp: number;
  momentum_score: number;
  value_score: number;
  momentum_verdict: string;
  value_verdict: string;
  recommendation?: string;
  verdict_reason?: string;
  strategy?: string;
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
  high_52w?: number;
  low_52w?: number;
  pct_from_52w_high?: number;
  pct_from_52w_low?: number;
  distribution_risk: string;
  broker_avg_cost: number;
  broker_profit_pct: number;
  distribution_warning: string;
  net_holdings_1m?: number;
  net_holdings_1w?: number;
  intraday_dump_detected?: boolean;
  open_vs_broker_pct?: number;
  close_vs_vwap_pct?: number;
  intraday_volume_spike?: number;
  entry_price: number;
  target_price: number;
  stop_loss: number;
  hold_days: string;
  expected_holding_days?: number;
  max_holding_days?: number;
  minimum_hold_period?: string;
  risk_reward_ratio?: number;
  execution_warning?: string;
  support_level?: number;
  resistance_level?: number;
  long_term_recommendation: string;
  short_term_recommendation: string;
  friend_recommendation: string;
  red_flags: string[];
  price_history_7d: Array<{ date: string; close: number }>;
  price_trend_7d: number;
  price_trend_30d: number;
  price_trend_90d: number;
  price_trend_1y?: number;
  market_cap_cr?: number;
  paid_up_capital_cr?: number;
  outstanding_shares_cr?: number;
  promoter_pct?: number;
  public_pct?: number;
  free_float_pct?: number;
  daily_turnover_cr?: number;
  full_report_text?: string;
  strategy_comparison?: {
    value?: {
      score: number;
      verdict: string;
      pillars: {
        broker: number;
        unlock: number;
        fundamental: number;
        technical: number;
        fundamental_max: number;
        technical_max: number;
      };
    };
    momentum?: {
      score: number;
      verdict: string;
      pillars: {
        broker: number;
        unlock: number;
        fundamental: number;
        technical: number;
        fundamental_max: number;
        technical_max: number;
      };
    };
  };
  sector_comparison?: {
    sector: string;
    sector_avg_pe: number;
    sector_avg_pbv: number;
    sector_avg_roe: number;
    pe_vs_sector_pct: number;
    pbv_vs_sector_pct: number;
    roe_vs_sector_pct: number;
  };
  dividend_history?: Array<{
    fiscal_year: string;
    cash_pct: number;
    bonus_pct: number;
    total_pct: number;
  }>;
  broker_activity?: {
    data_period: string;
    total_volume: number;
    total_transactions: number;
    top5_avg_cost: number;
    top5_total_net: number;
    brokers: Array<{
      broker_code: string;
      broker_name: string;
      net_quantity: number;
      buy_quantity: number;
      sell_quantity: number;
      avg_buy_price: number;
    }>;
  };
  manipulation_risk?: {
    score: number;
    severity: string;
    phase: string;
    phase_description: string;
    safe_to_trade: boolean;
    hhi: number;
    top3_control_pct: number;
    circular_trading_pct: number;
    wash_trading_detected: boolean;
    alerts: string[];
    veto_reasons: string[];
  };
  support_resistance?: {
    supports: number[];
    resistances: number[];
    tip: string;
  };
  price_target_analysis?: {
    conservative?: { level: number; upside_percent: number; probability: number; days_estimate: number };
    moderate?: { level: number; upside_percent: number; probability: number; days_estimate: number };
    aggressive?: { level: number; upside_percent: number; probability: number; days_estimate: number };
    max_theory?: { level: number; upside_percent: number };
    nearest_support: number;
    downside_risk_pct: number;
    risk_reward_ratio: number;
    trend_direction: string;
    momentum_score: number;
    warnings: string[];
  };
  distribution_details?: {
    risk_level: string;
    avg_cost_1m: number;
    avg_cost_1w: number;
    net_holdings_1m: number;
    net_holdings_1w: number;
    divergence: boolean;
    current_ltp: number;
    broker_profit_pct: number;
    intraday_dump_detected: boolean;
    today_open_price: number;
    today_vwap: number;
    open_vs_broker_pct: number;
    close_vs_vwap_pct: number;
    intraday_volume_spike: number;
    warning: string;
  };
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
      analysis_period?: string;
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
      trading_days_held?: number;
      example_100_shares?: {
        invested: number;
        current_value: number;
        pnl_amount: number;
      };
    };
    
    // Technical Position
    technical: {
      trend: string;
      momentum: string;
      support: number;
      resistance: number;
      rsi: number;
      trend_strength?: number;
      volume_trend?: string;
      ema_above_count?: number;
      ema_total?: number;
      ema_alignment?: string;
    };

    support_resistance?: {
      immediate_support: number;
      strong_support: number;
      immediate_resistance: number;
      strong_resistance: number;
      entry_vs_support: string;
      support_distance_pct: number;
      resistance_distance_pct: number;
    };

    risk_reward?: {
      risk_to_support_pct: number;
      reward_to_resistance_pct: number;
      ratio: number;
      favorable: boolean;
    };
    
    // Health Score
    health_score: number;
    health_grade?: string;
    health_breakdown: Array<{
      factor: string;
      score: number;
      max_score: number;
      weight_pct: number;
    }>;
    
    // Verdict
    verdict: 'STRONG_HOLD' | 'HOLD' | 'HOLD_CAUTIOUSLY' | 'BOOK_PARTIAL' | 'AVERAGE_DOWN' | 'EXIT' | 'URGENT_EXIT';
    verdict_text?: string;
    verdict_emoji: string;
    
    // Recommendations
    actions: string[];
    exit_triggers: string[];
    hold_checklist?: string[];
    stop_loss: number;
    targets: Array<{ level: string; price: number; gain_pct: number }>;
    trade_plan?: {
      stop_loss_pct_from_current: number;
    };
    
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
    rotation_signal: string;
    hot_sectors: string[];
    cold_sectors: string[];
    
    sectors: Array<{
      name: string;
      avg_change: number;
      advancing: number;
      declining: number;
      total: number;
      momentum_score: number;
      status: 'HOT' | 'COLD' | 'NEUTRAL';
      rank: number;
    }>;
  };
}

// Positioning Types
export interface PositioningResponse {
  success: boolean;
  timestamp: string;
  data: {
    overall: {
      above_sma20: number;
      above_sma50: number;
      above_sma200: number;
      condition: 'BULLISH' | 'NEUTRAL' | 'BEARISH';
      interpretation: string;
      stocks_analyzed: number;
    };
    
    sectors: Array<{
      name: string;
      above_sma20: number;
      above_sma50: number;
      above_sma200: number;
      bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    }>;
  };
}

// Broker Intelligence Types
export interface BrokerIntelligenceResponse {
  success: boolean;
  timestamp: string;
  data: {
    summary: {
      active_brokers: number;
      accumulating: number;
      distributing: number;
      market_sentiment: string;
    };
    
    brokers: Array<{
      name: string;
      activity: 'ACCUMULATING' | 'DISTRIBUTING';
      volume: number;
      value: number;
      top_stocks: string[];
    }>;
    
    stockwise: Array<{
      symbol: string;
      net_flow: number;
      buy_brokers: number;
      sell_brokers: number;
      concentration: 'HIGH' | 'MEDIUM' | 'LOW';
    }>;
  };
}

// Tech Score Types
export interface TechScoreResponse {
  success: boolean;
  timestamp: string;
  data: {
    symbol: string;
    current_price: number;
    total_score: number;
    max_score: number;
    verdict: 'STRONG BUY' | 'BUY' | 'NEUTRAL' | 'WEAK' | 'AVOID';
    color: 'bull' | 'bear' | 'warning';
    
    components: Array<{
      name: string;
      score: number;
      max: number;
      details: string;
    }>;
    
    indicators: {
      ema_9: number;
      ema_21: number;
      ema_50: number;
      ema_200: number;
      rsi: number;
      macd_histogram: number;
      volume_ratio: number;
    };
  };
}

// Price Targets Types
export interface PriceTargetsResponse {
  success: boolean;
  timestamp: string;
  data: {
    symbol: string;
    current_price: number;
    recent_high: number;
    recent_low: number;
    atr_14: number;
    trend_strength: number;
    
    fibonacci_levels: Record<string, number>;
    
    targets: Array<{
      type: 'stop' | 'target';
      label: string;
      price: number;
      pct: number;
      probability: number | null;
      method: string;
    }>;
    
    volume_profile: Array<{
      price: number;
      volume: number;
      pct_of_total: number;
    }>;
  };
}

// Order Flow Types
export interface OrderFlowResponse {
  success: boolean;
  timestamp: string;
  data: {
    symbol: string;
    current_price: number;
    flow_bias: 'BUYING PRESSURE' | 'SELLING PRESSURE' | 'NEUTRAL';
    bias_color: 'bull' | 'bear' | 'warning';
    cumulative_delta: number;
    
    delta_bars: Array<{
      date: string;
      close: number;
      volume: number;
      buy_volume: number;
      sell_volume: number;
      delta: number;
      delta_pct?: number;
      close_change_pct?: number;
      cumulative_delta: number;
    }>;
    
    price_levels: Array<{
      price: number;
      buy_volume: number;
      sell_volume: number;
      net: number;
    }>;
    
    absorptions: Array<{
      date: string;
      volume_ratio: number;
      price_change: number;
      close_to_close_pct?: number;
      intraday_range_pct?: number;
      movement_source?: string;
      type: string;
    }>;
  };
}

// Bulk Deals Types
export interface BulkDealsResponse {
  success: boolean;
  timestamp: string;
  data: {
    summary: {
      total_deals: number;
      buy_deals: number;
      sell_deals: number;
      buy_value: number;
      sell_value: number;
      total_value: number;
    };
    
    deals: Array<{
      symbol: string;
      name: string;
      quantity: number;
      price: number;
      value: number;
      deal_type: 'BUY' | 'SELL';
      buyer_broker?: string;
      seller_broker?: string;
      date: string;
      significance: 'HIGH' | 'MEDIUM' | 'LOW';
    }>;
  };
}

// Dividend Forecast Types
export interface DividendForecastResponse {
  success: boolean;
  timestamp: string;
  data: {
    symbol: string;
    company_name: string;
    current_price: number;
    eps: number;
    book_value: number;
    pe_ratio: number;
    current_yield: number;
    forecasted_yield: number;
    forecasted_dividend: number;
    dividend_status: 'REGULAR' | 'IRREGULAR' | 'RARE';
    
    history: Array<{
      year: string;
      dividend: number;
    }>;
    
    strengths: string[];
    risks: string[];
    verdict: 'BUY' | 'HOLD' | 'NEUTRAL';
    reasoning: string;
  };
}
