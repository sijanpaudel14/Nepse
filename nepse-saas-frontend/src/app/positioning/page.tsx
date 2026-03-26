'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPositioning, type PositioningResponse } from '@/lib/api';
import { 
  TrendingUp,
  Activity,
  BarChart3,
  AlertTriangle,
  ThumbsUp,
  ThumbsDown,
  Minus,
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

// SMA gauge
function SMAGauge({ 
  label, 
  percentage, 
  description,
}: { 
  label: string;
  percentage: number;
  description: string;
}) {
  const getColor = (pct: number) => {
    if (pct >= 70) return { stroke: 'stroke-bull', text: 'text-bull', label: 'OVERBOUGHT' };
    if (pct >= 50) return { stroke: 'stroke-bull', text: 'text-bull', label: 'BULLISH' };
    if (pct >= 30) return { stroke: 'stroke-warning', text: 'text-warning', label: 'NEUTRAL' };
    return { stroke: 'stroke-bear', text: 'text-bear', label: 'OVERSOLD' };
  };
  
  const config = getColor(percentage);
  const circumference = 2 * Math.PI * 40;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;
  
  return (
    <div className="rounded-xl border border-border bg-card p-5 text-center">
      <p className="text-sm text-muted-foreground mb-3">{label}</p>
      <div className="relative h-28 w-28 mx-auto">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50" cy="50" r="40"
            fill="none"
            stroke="currentColor"
            strokeWidth="8"
            className="text-muted/20"
          />
          <circle
            cx="50" cy="50" r="40"
            fill="none"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className={cn('transition-all duration-700', config.stroke)}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn('text-2xl font-bold', config.text)}>{percentage.toFixed(0)}%</span>
          <span className="text-[10px] text-muted-foreground">{config.label}</span>
        </div>
      </div>
      <p className="text-xs text-muted-foreground mt-3">{description}</p>
    </div>
  );
}

// Sector positioning bar
function SectorPositionBar({ 
  sector,
}: { 
  sector: {
    name: string;
    above_sma20: number;
    above_sma50: number;
    above_sma200: number;
    bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  };
}) {
  const biasConfig = {
    BULLISH: { bg: 'bg-bull/10', border: 'border-bull/30', icon: ThumbsUp, text: 'text-bull' },
    BEARISH: { bg: 'bg-bear/10', border: 'border-bear/30', icon: ThumbsDown, text: 'text-bear' },
    NEUTRAL: { bg: 'bg-muted/10', border: 'border-border', icon: Minus, text: 'text-muted-foreground' },
  };
  
  const config = biasConfig[sector.bias];
  const Icon = config.icon;
  
  return (
    <div className={cn('rounded-lg border p-4 transition-all hover:shadow-card-hover', config.border, config.bg)}>
      <div className="flex items-center justify-between mb-3">
        <span className="font-medium">{sector.name}</span>
        <div className={cn('flex items-center gap-1', config.text)}>
          <Icon className="h-4 w-4" />
          <span className="text-xs font-semibold">{sector.bias}</span>
        </div>
      </div>
      
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="w-16 text-xs text-muted-foreground">SMA20</span>
          <div className="flex-1 h-2 bg-muted/20 rounded-full overflow-hidden">
            <div className="h-full bg-primary rounded-full" style={{ width: `${sector.above_sma20}%` }} />
          </div>
          <span className="w-10 text-xs font-mono text-right">{sector.above_sma20}%</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-16 text-xs text-muted-foreground">SMA50</span>
          <div className="flex-1 h-2 bg-muted/20 rounded-full overflow-hidden">
            <div className="h-full bg-accent rounded-full" style={{ width: `${sector.above_sma50}%` }} />
          </div>
          <span className="w-10 text-xs font-mono text-right">{sector.above_sma50}%</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-16 text-xs text-muted-foreground">SMA200</span>
          <div className="flex-1 h-2 bg-muted/20 rounded-full overflow-hidden">
            <div className="h-full bg-warning rounded-full" style={{ width: `${sector.above_sma200}%` }} />
          </div>
          <span className="w-10 text-xs font-mono text-right">{sector.above_sma200}%</span>
        </div>
      </div>
    </div>
  );
}

export default function PositioningPage() {
  const HISTORY_KEY = 'nepse-positioning-history-v1';
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);

  useEffect(() => {
    setHistory(loadScanHistory(HISTORY_KEY));
  }, []);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['positioning'],
    queryFn: () => getPositioning(),
    retry: 1,
    staleTime: 5 * 60 * 1000,
  });

  const result = data?.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-primary" />
            Market Positioning
          </h1>
          <p className="text-muted-foreground mt-1">
            Quantitative market breadth - percentage of stocks above key SMAs
          </p>
        </div>
        <button
          onClick={() => {
            setHistory(
              pushScanHistory(HISTORY_KEY, {
                label: 'Market Positioning Refresh',
                value: 'refresh',
              })
            );
            refetch();
          }}
          disabled={isLoading}
          className="btn-secondary"
        >
          {isLoading ? <Activity className="h-4 w-4 animate-spin" /> : 'Refresh'}
        </button>
      </div>
      <div className="max-w-xl">
        <ScanHistoryPanel
          title="Positioning History"
          items={history}
          onSelect={() => refetch()}
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
          <div className="grid md:grid-cols-3 gap-4">
            {[1,2,3].map(i => <div key={i} className="h-48 bg-muted/20 rounded-xl" />)}
          </div>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-xl border border-bear/30 bg-bear/10 p-6 text-center">
          <p className="text-bear font-medium">{(error as Error)?.message || 'Failed to load positioning data'}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Market Overview */}
          <div className="grid md:grid-cols-3 gap-4">
            <SMAGauge 
              label="% Above 20 SMA"
              percentage={result.overall.above_sma20}
              description="Short-term trend"
            />
            <SMAGauge 
              label="% Above 50 SMA"
              percentage={result.overall.above_sma50}
              description="Medium-term trend"
            />
            <SMAGauge 
              label="% Above 200 SMA"
              percentage={result.overall.above_sma200}
              description="Long-term trend"
            />
          </div>

          {/* Market Condition Summary */}
          <div className={cn(
            'rounded-xl border p-6',
            result.overall.condition === 'BULLISH' ? 'border-bull/30 bg-bull/10' :
            result.overall.condition === 'BEARISH' ? 'border-bear/30 bg-bear/10' : 'border-border bg-card'
          )}>
            <div className="flex items-center gap-3 mb-3">
              {result.overall.condition === 'BULLISH' ? (
                <TrendingUp className="h-6 w-6 text-bull" />
              ) : result.overall.condition === 'BEARISH' ? (
                <AlertTriangle className="h-6 w-6 text-bear" />
              ) : (
                <Activity className="h-6 w-6 text-muted-foreground" />
              )}
              <span className="text-xl font-bold">Market: {result.overall.condition}</span>
            </div>
            <p className="text-sm text-muted-foreground">{result.overall.interpretation}</p>
          </div>

          {/* Sector Breakdown */}
          <div>
            <h2 className="text-lg font-semibold mb-4">Sector Positioning</h2>
            <div className="grid md:grid-cols-2 gap-4">
              {result.sectors.map((sector, i) => (
                <SectorPositionBar key={i} sector={sector} />
              ))}
            </div>
          </div>

          {/* Legend */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="font-semibold mb-3">How to Read This</h3>
            <div className="grid md:grid-cols-3 gap-4 text-sm">
              <div>
                <p className="font-medium text-bull">&gt;70% Above SMA</p>
                <p className="text-muted-foreground">Market is overbought - potential pullback</p>
              </div>
              <div>
                <p className="font-medium text-warning">30-70% Above SMA</p>
                <p className="text-muted-foreground">Normal range - healthy market</p>
              </div>
              <div>
                <p className="font-medium text-bear">&lt;30% Above SMA</p>
                <p className="text-muted-foreground">Market is oversold - potential bounce</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
