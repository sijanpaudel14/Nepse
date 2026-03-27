'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getTechScore, type TechScoreResponse } from '@/lib/api';
import { 
  Gauge, 
  TrendingUp,
  TrendingDown,
  Activity,
  Clock,
  BarChart3,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ScanHistoryPanel } from '@/components/ui';
import {
  loadScanHistory,
  pushScanHistory,
  removeScanHistoryItem,
  clearScanHistory,
  type ScanHistoryItem,
} from '@/lib/scan-history';

// Circular gauge component
function CircularGauge({ 
  score, 
  maxScore = 100,
  size = 'lg',
  label,
}: { 
  score: number; 
  maxScore?: number;
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}) {
  const percentage = (score / maxScore) * 100;
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;
  
  const getColor = (pct: number) => {
    if (pct >= 70) return { stroke: 'stroke-bull', text: 'text-bull', label: 'BULLISH' };
    if (pct >= 50) return { stroke: 'stroke-warning', text: 'text-warning', label: 'NEUTRAL' };
    if (pct >= 30) return { stroke: 'stroke-warning', text: 'text-warning', label: 'WEAK' };
    return { stroke: 'stroke-bear', text: 'text-bear', label: 'BEARISH' };
  };
  
  const config = getColor(percentage);
  
  const sizes = {
    sm: { container: 'h-20 w-20', text: 'text-xl', label: 'text-[8px]' },
    md: { container: 'h-28 w-28', text: 'text-2xl', label: 'text-[10px]' },
    lg: { container: 'h-40 w-40', text: 'text-4xl', label: 'text-xs' },
  };
  
  return (
    <div className={cn('relative', sizes[size].container)}>
      <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100">
        <circle
          cx="50" cy="50" r="45"
          fill="none"
          stroke="currentColor"
          strokeWidth="6"
          className="text-muted/20"
        />
        <circle
          cx="50" cy="50" r="45"
          fill="none"
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className={cn('transition-all duration-700', config.stroke)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn('font-bold', sizes[size].text, config.text)}>
          {Math.round(score)}
        </span>
        <span className={cn('text-muted-foreground', sizes[size].label)}>
          {label || config.label}
        </span>
      </div>
    </div>
  );
}

// Timeframe score bar
function TimeframeBar({ 
  timeframe, 
  score,
  signal,
}: { 
  timeframe: string; 
  score: number;
  signal: 'BUY' | 'SELL' | 'HOLD';
}) {
  const colors = {
    BUY: { bg: 'bg-bull', text: 'text-bull' },
    SELL: { bg: 'bg-bear', text: 'text-bear' },
    HOLD: { bg: 'bg-warning', text: 'text-warning' },
  };
  
  return (
    <div className="flex items-center gap-4 p-4 rounded-xl border border-border bg-card hover:bg-card-hover transition-colors">
      <div className="w-16 text-sm font-medium text-muted-foreground">{timeframe}</div>
      <div className="flex-1">
        <div className="h-2 bg-muted/20 rounded-full overflow-hidden">
          <div 
            className={cn('h-full rounded-full transition-all duration-500', colors[signal].bg)}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>
      <div className="w-12 text-right font-mono font-bold">{score}</div>
      <div className={cn(
        'w-16 text-center px-2 py-1 rounded-full text-xs font-semibold',
        signal === 'BUY' ? 'bg-bull/20 text-bull' : signal === 'SELL' ? 'bg-bear/20 text-bear' : 'bg-warning/20 text-warning'
      )}>
        {signal}
      </div>
    </div>
  );
}

// Indicator row
function IndicatorRow({ 
  name, 
  value, 
  signal,
  description,
}: { 
  name: string; 
  value: string | number;
  signal: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  description?: string;
}) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-muted/5 hover:bg-muted/10 transition-colors">
      <div>
        <p className="font-medium">{name}</p>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      <div className="flex items-center gap-3">
        <span className="font-mono">{value}</span>
        <span className={cn(
          'px-2 py-0.5 rounded text-xs font-semibold',
          signal === 'BULLISH' ? 'bg-bull/20 text-bull' : signal === 'BEARISH' ? 'bg-bear/20 text-bear' : 'bg-muted/20 text-muted-foreground'
        )}>
          {signal}
        </span>
      </div>
    </div>
  );
}

export default function TechScorePage() {
  const STORAGE_KEY = 'nepse-tech-score-state-v1';
  const HISTORY_KEY = 'nepse-tech-score-history-v1';
  const [symbol, setSymbol] = useState('');
  const [searchSymbol, setSearchSymbol] = useState('');
  const [hydrated, setHydrated] = useState(false);
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (typeof parsed.symbol === 'string') setSymbol(parsed.symbol);
      if (typeof parsed.searchSymbol === 'string') setSearchSymbol(parsed.searchSymbol);
    } catch {
      // ignore invalid storage
    } finally {
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    setHistory(loadScanHistory(HISTORY_KEY));
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ symbol, searchSymbol }));
  }, [symbol, searchSymbol, hydrated]);

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['tech-score', searchSymbol],
    queryFn: () => getTechScore(searchSymbol),
    enabled: !!searchSymbol,
    retry: 1,
    staleTime: 0,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = symbol.trim().toUpperCase();
    if (!clean) return;
    setHistory(pushScanHistory(HISTORY_KEY, { label: clean, value: clean }));
    if (clean === searchSymbol) {
      refetch();
    } else {
      setSearchSymbol(clean);
    }
  };

  const result = data?.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Gauge className="h-6 w-6 text-primary" />
          Technical Score
        </h1>
        <p className="text-muted-foreground mt-1">
          Multi-timeframe composite technical analysis score (0-100)
        </p>
      </div>

      {/* Search */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <div className="relative flex-1 max-w-md">
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="Enter stock symbol (e.g., NABIL)"
            className="w-full rounded-lg border border-border bg-card px-4 py-3 pr-12 font-mono"
          />
        </div>
        <button type="submit" disabled={!symbol.trim() || isLoading} className="btn-primary">
          {isFetching ? <Activity className="h-4 w-4 animate-spin" /> : <><Gauge className="h-4 w-4" /> Analyze</>}
        </button>
      </form>
      <div className="max-w-md">
        <ScanHistoryPanel
          title="Tech Score History"
          items={history}
          onSelect={(value) => {
            setSymbol(value);
            if (value === searchSymbol) refetch();
            else setSearchSymbol(value);
          }}
          onDelete={(id) => setHistory(removeScanHistoryItem(HISTORY_KEY, id))}
          onClear={() => {
            clearScanHistory(HISTORY_KEY);
            setHistory([]);
          }}
        />
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="animate-pulse space-y-4">
          <div className="flex justify-center"><div className="h-40 w-40 bg-muted/20 rounded-full" /></div>
          <div className="grid md:grid-cols-4 gap-4">
            {[1,2,3,4].map(i => <div key={i} className="h-20 bg-muted/20 rounded-xl" />)}
          </div>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-xl border border-bear/30 bg-bear/10 p-6 text-center">
          <p className="text-bear font-medium">{(error as Error)?.message || 'Failed to calculate tech score'}</p>
        </div>
      )}

      {/* Empty State */}
      {!searchSymbol && !isLoading && (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <Gauge className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">Calculate Technical Score</h3>
          <p className="text-muted-foreground mt-2 max-w-md mx-auto">
            Get a comprehensive technical score combining RSI, MACD, EMA alignment, 
            volume analysis, and momentum across multiple timeframes.
          </p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Main Score */}
          <div className="rounded-xl border border-border bg-card p-8 flex flex-col items-center">
            <p className="text-2xl font-bold mb-4">{result.symbol}</p>
            <CircularGauge score={result.total_score} size="lg" label="COMPOSITE" />
            <p className="mt-4 text-lg font-semibold">{result.verdict}</p>
            <p className="text-sm text-muted-foreground mt-1">Score: {result.total_score}/{result.max_score}</p>
          </div>

          {/* Component Breakdown */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Clock className="h-5 w-5 text-primary" />
              Score Components
            </h2>
            <div className="space-y-3">
              {result.components.map((comp, i) => (
                <div key={i} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{comp.name}</span>
                    <span className="font-mono">{comp.score}/{comp.max}</span>
                  </div>
                  <div className="h-2 bg-muted/20 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-primary rounded-full"
                      style={{ width: `${(comp.score / comp.max) * 100}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">{comp.details}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Indicator Breakdown */}
          <div className="grid md:grid-cols-2 gap-6">
            <div className="rounded-xl border border-border bg-card p-5">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-primary" />
                EMAs
              </h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span>EMA 9:</span>
                  <span className="font-mono">Rs. {result.indicators.ema_9.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span>EMA 21:</span>
                  <span className="font-mono">Rs. {result.indicators.ema_21.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span>EMA 50:</span>
                  <span className="font-mono">Rs. {result.indicators.ema_50.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span>EMA 200:</span>
                  <span className="font-mono">Rs. {result.indicators.ema_200.toLocaleString()}</span>
                </div>
              </div>
            </div>
            
            <div className="rounded-xl border border-border bg-card p-5">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Zap className="h-5 w-5 text-primary" />
                Momentum
              </h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span>RSI (14):</span>
                  <span className="font-mono">{result.indicators.rsi.toFixed(1)}</span>
                </div>
                <div className="flex justify-between">
                  <span>MACD Histogram:</span>
                  <span className="font-mono">{result.indicators.macd_histogram.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Volume Ratio:</span>
                  <span className="font-mono">{result.indicators.volume_ratio.toFixed(2)}x</span>
                </div>
              </div>
            </div>
          </div>

          {/* Summary */}
          <div className={cn(
            'rounded-xl border p-6',
            result.total_score >= 75 ? 'border-bull/30 bg-bull/5' : 
            result.total_score >= 50 ? 'border-warning/30 bg-warning/5' : 'border-bear/30 bg-bear/5'
          )}>
            <h3 className="font-semibold mb-2">Technical Summary</h3>
            <p className="text-sm text-muted-foreground">
              {result.verdict} - Overall technical score of {result.total_score}/{result.max_score} ({((result.total_score/result.max_score)*100).toFixed(0)}%)
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
