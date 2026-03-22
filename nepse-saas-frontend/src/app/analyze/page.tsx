'use client';

import { Suspense, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { analyzeStock, type SingleStockAnalysis } from '@/lib/api';
import { 
  Search,
  Loader2,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Target,
  Shield,
  BarChart3,
  DollarSign,
  Users,
  Clock,
  Zap,
  Info,
  ChevronRight,
  CheckCircle,
  XCircle,
  AlertOctagon,
} from 'lucide-react';
import { cn, formatCurrency, formatPercent, getScoreColor, getRiskColor, type RiskLevel } from '@/lib/utils';

// Risk Icon Component
function RiskIcon({ level, className }: { level: RiskLevel; className?: string }) {
  switch (level) {
    case 'low':
      return <Shield className={cn('h-4 w-4', className)} />;
    case 'medium':
      return <AlertTriangle className={cn('h-4 w-4', className)} />;
    case 'high':
    case 'critical':
      return <AlertOctagon className={cn('h-4 w-4', className)} />;
    default:
      return <AlertTriangle className={cn('h-4 w-4', className)} />;
  }
}

// Pillar Progress Ring
function PillarRing({
  name,
  score,
  maxScore,
  icon: Icon,
  color,
}: {
  name: string;
  score: number;
  maxScore: number;
  icon: any;
  color: string;
}) {
  const percentage = (score / maxScore) * 100;
  const circumference = 2 * Math.PI * 40;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-24 w-24">
        <svg className="h-24 w-24 -rotate-90 transform">
          {/* Background circle */}
          <circle
            cx="48"
            cy="48"
            r="40"
            stroke="currentColor"
            strokeWidth="8"
            fill="none"
            className="text-background"
          />
          {/* Progress circle */}
          <circle
            cx="48"
            cy="48"
            r="40"
            stroke={color}
            strokeWidth="8"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-500"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <Icon className="h-5 w-5 text-muted-foreground" />
          <span className="mt-1 text-lg font-bold">{score.toFixed(0)}</span>
          <span className="text-xs text-muted-foreground">/ {maxScore}</span>
        </div>
      </div>
      <p className="mt-2 text-sm font-medium">{name}</p>
    </div>
  );
}

// Metric Row
function MetricRow({
  label,
  value,
  status,
  statusColor,
}: {
  label: string;
  value: string | number;
  status?: string;
  statusColor?: 'bull' | 'bear' | 'neutral' | 'warning';
}) {
  const colorClass = {
    bull: 'text-bull',
    bear: 'text-bear',
    neutral: 'text-neutral',
    warning: 'text-warning',
  }[statusColor || 'neutral'];

  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className="font-mono font-semibold">{value}</span>
        {status && (
          <span className={cn('text-xs font-medium', colorClass)}>
            {status}
          </span>
        )}
      </div>
    </div>
  );
}

// Red Flag Alert
function RedFlagAlert({ flags }: { flags: string[] }) {
  if (!flags || flags.length === 0) return null;

  return (
    <div className="rounded-xl border border-bear/50 bg-bear/5 p-4">
      <h3 className="flex items-center gap-2 font-semibold text-bear">
        <AlertTriangle className="h-5 w-5" />
        Red Flags ({flags.length})
      </h3>
      <ul className="mt-3 space-y-2">
        {flags.map((flag, idx) => (
          <li key={idx} className="flex items-start gap-2 text-sm">
            <ChevronRight className="mt-0.5 h-4 w-4 flex-shrink-0 text-bear" />
            <span className="text-muted-foreground">{flag}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Analysis Content
function AnalysisContent({ data }: { data: SingleStockAnalysis }) {
  const momentumColor = getScoreColor(data.momentum_score);
  const valueColor = getScoreColor(data.value_score);

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-3xl font-bold">{data.symbol}</h2>
            <p className="text-lg text-muted-foreground">{data.name}</p>
            <p className="text-sm text-primary">{data.sector}</p>
          </div>
          <div className="text-right">
            <p className="text-4xl font-bold">{formatCurrency(data.ltp)}</p>
            <div className="mt-2 flex gap-2">
              <span className={cn(
                'inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold',
                momentumColor.bgColor, momentumColor.textColor
              )}>
                ⚡ Momentum: {data.momentum_score}/100
              </span>
              <span className={cn(
                'inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold',
                valueColor.bgColor, valueColor.textColor
              )}>
                💎 Value: {data.value_score}/100
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 4 Pillars */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h3 className="mb-6 text-lg font-semibold">4-Pillar Analysis</h3>
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          <PillarRing
            name="Technical"
            score={data.pillars?.technical?.score || 0}
            maxScore={data.pillars?.technical?.max_score || 40}
            icon={BarChart3}
            color="#22c55e"
          />
          <PillarRing
            name="Broker/Inst"
            score={data.pillars?.broker?.score || 0}
            maxScore={data.pillars?.broker?.max_score || 30}
            icon={Users}
            color="#3b82f6"
          />
          <PillarRing
            name="Unlock Risk"
            score={data.pillars?.unlock?.score || 0}
            maxScore={data.pillars?.unlock?.max_score || 20}
            icon={Shield}
            color="#f59e0b"
          />
          <PillarRing
            name="Fundamental"
            score={data.pillars?.fundamental?.score || 0}
            maxScore={data.pillars?.fundamental?.max_score || 10}
            icon={DollarSign}
            color="#8b5cf6"
          />
        </div>
      </div>

      {/* Trade Setup */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Entry/Target/Stop */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <Target className="h-5 w-5 text-primary" />
            Trade Setup
          </h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-lg bg-card-hover p-3">
              <span className="text-muted-foreground">Entry Price</span>
              <span className="font-mono text-xl font-bold">
                {formatCurrency(data.entry_price)}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-bull/10 p-3">
              <span className="text-bull">🎯 Target</span>
              <span className="font-mono text-xl font-bold text-bull">
                {formatCurrency(data.target_price)}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-bear/10 p-3">
              <span className="text-bear">🛑 Stop Loss</span>
              <span className="font-mono text-xl font-bold text-bear">
                {formatCurrency(data.stop_loss)}
              </span>
            </div>
            <div className="flex items-center justify-between pt-2">
              <span className="flex items-center gap-1 text-muted-foreground">
                <Clock className="h-4 w-4" /> Hold Period
              </span>
              <span className="font-semibold">{data.hold_days}</span>
            </div>
          </div>
        </div>

        {/* Distribution Risk */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <AlertTriangle className="h-5 w-5 text-warning" />
            Distribution Risk
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span>Risk Level</span>
              <span className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-bold',
                getRiskColor(data.distribution_risk).bgColor,
                getRiskColor(data.distribution_risk).textColor
              )}>
                <RiskIcon level={getRiskColor(data.distribution_risk).level} />
                {data.distribution_risk}
              </span>
            </div>
            <MetricRow 
              label="Broker Avg Cost (VWAP)" 
              value={formatCurrency(data.broker_avg_cost)} 
            />
            <MetricRow 
              label="Broker Profit %" 
              value={formatPercent(data.broker_profit_pct)}
              status={data.broker_profit_pct > 10 ? 'HIGH RISK' : 'SAFE'}
              statusColor={data.broker_profit_pct > 10 ? 'bear' : 'bull'}
            />
            {data.distribution_warning && (
              <p className="mt-2 rounded-lg bg-warning/10 p-2 text-sm text-warning flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                {data.distribution_warning}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Technical & Fundamental */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Technical Indicators */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <BarChart3 className="h-5 w-5 text-primary" />
            Technical Indicators
          </h3>
          <div className="divide-y divide-border">
            <MetricRow 
              label="RSI (14)" 
              value={data.rsi?.toFixed(1) || 'N/A'}
              status={data.rsi_status}
              statusColor={
                data.rsi >= 70 ? 'bear' :
                data.rsi >= 50 ? 'bull' :
                data.rsi >= 30 ? 'neutral' : 'bear'
              }
            />
            <MetricRow 
              label="EMA Signal" 
              value={data.ema_signal}
              statusColor={data.ema_signal === 'BULLISH' ? 'bull' : 'bear'}
            />
            <MetricRow 
              label="Volume Spike" 
              value={`${data.volume_spike?.toFixed(2)}x`}
              statusColor={data.volume_spike >= 1.5 ? 'bull' : 'neutral'}
            />
            <MetricRow 
              label="ATR" 
              value={formatCurrency(data.atr)}
            />
            <MetricRow 
              label="7D Trend" 
              value={formatPercent(data.price_trend_7d)}
              statusColor={data.price_trend_7d > 0 ? 'bull' : 'bear'}
            />
            <MetricRow 
              label="30D Trend" 
              value={formatPercent(data.price_trend_30d)}
              statusColor={data.price_trend_30d > 0 ? 'bull' : 'bear'}
            />
          </div>
        </div>

        {/* Fundamental Data */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <DollarSign className="h-5 w-5 text-primary" />
            Fundamental Data
          </h3>
          <div className="divide-y divide-border">
            <MetricRow 
              label="P/E Ratio" 
              value={data.pe_ratio?.toFixed(2) || 'N/A'}
              status={data.pe_status}
              statusColor={
                data.pe_ratio < 0 ? 'bear' :
                data.pe_ratio <= 15 ? 'bull' :
                data.pe_ratio <= 25 ? 'neutral' : 'bear'
              }
            />
            <MetricRow 
              label="EPS" 
              value={formatCurrency(data.eps)}
            />
            <MetricRow 
              label="EPS (Annualized)" 
              value={formatCurrency(data.eps_annualized)}
            />
            <MetricRow 
              label="Book Value" 
              value={formatCurrency(data.book_value)}
            />
            <MetricRow 
              label="P/BV Ratio" 
              value={data.pbv?.toFixed(2) || 'N/A'}
              statusColor={data.pbv <= 2 ? 'bull' : data.pbv <= 4 ? 'neutral' : 'bear'}
            />
            <MetricRow 
              label="ROE" 
              value={formatPercent(data.roe)}
              status={data.roe_status}
              statusColor={data.roe >= 15 ? 'bull' : data.roe >= 10 ? 'neutral' : 'bear'}
            />
          </div>
        </div>
      </div>

      {/* Recommendations */}
      <div className="grid gap-6 md:grid-cols-3">
        <div className="rounded-xl border border-primary/50 bg-primary/5 p-4">
          <h4 className="flex items-center gap-2 font-semibold text-primary">
            <Zap className="h-4 w-4" />
            Short-Term (Swing)
          </h4>
          <p className="mt-2 text-sm">{data.short_term_recommendation}</p>
        </div>
        <div className="rounded-xl border border-bull/50 bg-bull/5 p-4">
          <h4 className="flex items-center gap-2 font-semibold text-bull">
            <TrendingUp className="h-4 w-4" />
            Long-Term (Investment)
          </h4>
          <p className="mt-2 text-sm">{data.long_term_recommendation}</p>
        </div>
        <div className="rounded-xl border border-warning/50 bg-warning/5 p-4">
          <h4 className="flex items-center gap-2 font-semibold text-warning">
            <Users className="h-4 w-4" />
            Friend Recommendation
          </h4>
          <p className="mt-2 text-sm">{data.friend_recommendation}</p>
        </div>
      </div>

      {/* Red Flags */}
      <RedFlagAlert flags={data.red_flags} />
    </div>
  );
}

// Inner component that handles the form and data
function AnalyzePageInner({ initialSymbol }: { initialSymbol: string }) {
  const normalizedInitial = initialSymbol.toUpperCase().trim();
  const [symbol, setSymbol] = useState(normalizedInitial);
  const [submittedSymbol, setSubmittedSymbol] = useState(normalizedInitial);
  const [strategy, setStrategy] = useState<'momentum' | 'value'>('momentum');
  const analyzeAbortRef = useRef<AbortController | null>(null);
  const [isAnalyzeRunning, setIsAnalyzeRunning] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['analyze', submittedSymbol, strategy],
    queryFn: async () => {
      const controller = new AbortController();
      analyzeAbortRef.current = controller;
      setIsAnalyzeRunning(true);
      try {
        return await analyzeStock(submittedSymbol, { strategy }, controller.signal);
      } finally {
        setIsAnalyzeRunning(false);
        analyzeAbortRef.current = null;
      }
    },
    enabled: !!submittedSymbol && submittedSymbol.length >= 3,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanSymbol = symbol.toUpperCase().trim();
    if (cleanSymbol.length < 3) return;
    if (cleanSymbol === submittedSymbol) {
      refetch();
    } else {
      setSubmittedSymbol(cleanSymbol);
    }
  };

  const handleStopAnalyze = () => {
    if (analyzeAbortRef.current) {
      analyzeAbortRef.current.abort();
      analyzeAbortRef.current = null;
      setIsAnalyzeRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Stock Analysis</h1>
        <p className="text-muted-foreground">
          Deep-dive into any NEPSE stock with 4-Pillar scoring
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="flex gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="Enter stock symbol (e.g., NABIL)"
            className="w-full rounded-lg border border-border bg-card pl-10 pr-4 py-3 text-lg font-mono focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        
        <select
          value={strategy}
          onChange={(e) => setStrategy(e.target.value as 'momentum' | 'value')}
          className="rounded-lg border border-border bg-card px-4 py-3 focus:border-primary focus:outline-none"
        >
          <option value="momentum">⚡ Momentum</option>
          <option value="value">💎 Value</option>
        </select>

        <button
          type="submit"
          disabled={isLoading || isAnalyzeRunning || symbol.trim().length < 3}
          className={cn(
            'flex items-center gap-2 rounded-lg bg-primary px-6 py-3 font-semibold text-primary-foreground transition-colors hover:bg-primary/90',
            (isLoading || isAnalyzeRunning || symbol.trim().length < 3) && 'cursor-not-allowed opacity-50'
          )}
        >
          {isLoading || isAnalyzeRunning ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Search className="h-5 w-5" />
          )}
          Analyze
        </button>
        <button
          type="button"
          onClick={handleStopAnalyze}
          disabled={!isAnalyzeRunning}
          className={cn(
            'flex items-center gap-2 rounded-lg border px-4 py-3 font-semibold transition-colors',
            isAnalyzeRunning
              ? 'border-bear/40 bg-bear/10 text-bear hover:bg-bear/20'
              : 'cursor-not-allowed border-border bg-card text-muted-foreground opacity-50'
          )}
        >
          <XCircle className="h-5 w-5" />
          Stop
        </button>
      </form>

      {/* Loading */}
      {(isLoading || isAnalyzeRunning) && (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
          <p className="mt-4 text-lg font-medium">Analyzing {submittedSymbol || symbol}...</p>
          <p className="text-sm text-muted-foreground">Running 4-Pillar analysis</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-bear/50 bg-bear/5 p-6 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-bear" />
          <h3 className="mt-4 text-xl font-semibold">Analysis Failed</h3>
          <p className="mt-2 text-muted-foreground">
            {(error as Error).message || 'Could not analyze this stock'}
          </p>
        </div>
      )}

      {/* Results */}
      {data?.success && data.data && (
        <AnalysisContent data={data.data} />
      )}

      {/* Empty State */}
      {!isLoading && !data && !error && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-16">
          <Search className="h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-xl font-semibold">Enter a Stock Symbol</h3>
          <p className="mt-2 text-center text-muted-foreground">
            Type any NEPSE stock symbol above to get a<br />
            comprehensive 4-Pillar analysis with trade setup.
          </p>
        </div>
      )}
    </div>
  );
}

// Content wrapper that reads URL params
function AnalyzePageContent() {
  const searchParams = useSearchParams();
  const initialSymbol = searchParams.get('symbol') || '';
  
  return <AnalyzePageInner initialSymbol={initialSymbol} />;
}

// Main export with Suspense boundary
export default function AnalyzePage() {
  return (
    <Suspense fallback={
      <div className="flex flex-col items-center justify-center py-16">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
        <p className="mt-4 text-lg font-medium">Loading...</p>
      </div>
    }>
      <AnalyzePageContent />
    </Suspense>
  );
}
