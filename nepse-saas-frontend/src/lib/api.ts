// API client for NEPSE AI Trading backend

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
