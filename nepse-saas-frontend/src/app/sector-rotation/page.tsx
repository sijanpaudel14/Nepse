'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getSectorRotation, type SectorRotationResponse } from '@/lib/api';
import { 
  PieChart, 
  TrendingUp,
  TrendingDown,
  Activity,
  ArrowRight,
  Flame,
  Snowflake,
  RefreshCw,
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

// Sector bar with ranking
function SectorBar({ 
  sector,
  rank,
}: { 
  sector: {
    name: string;
    avg_change: number;
    advancing: number;
    declining: number;
    total: number;
    momentum_score: number;
    status: 'HOT' | 'COLD' | 'NEUTRAL';
    rank: number;
  };
  rank: number;
}) {
  const signalConfig = {
    HOT: { bg: 'bg-bull/20', text: 'text-bull', icon: Flame, border: 'border-bull/30' },
    NEUTRAL: { bg: 'bg-muted/20', text: 'text-muted-foreground', icon: Activity, border: 'border-border' },
    COLD: { bg: 'bg-bear/20', text: 'text-bear', icon: Snowflake, border: 'border-bear/30' },
  };
  
  const config = signalConfig[sector.status];
  const Icon = config.icon;
  
  return (
    <div className={cn(
      'rounded-xl border p-4 transition-all hover:shadow-card-hover',
      config.border, config.bg
    )}>
      <div className="flex items-center gap-4">
        <div className={cn(
          'w-10 h-10 rounded-lg flex items-center justify-center font-bold text-lg',
          rank <= 3 ? 'bg-primary text-primary-foreground' : 'bg-muted/30 text-muted-foreground'
        )}>
          {rank}
        </div>
        
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <p className="font-semibold">{sector.name}</p>
            <Icon className={cn('h-4 w-4', config.text)} />
          </div>
          <p className="text-xs text-muted-foreground">{sector.total} stocks ({sector.advancing}↑ {sector.declining}↓)</p>
        </div>
        
        <div className="text-right">
          <div className="flex items-center gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Avg</p>
              <p className={cn(
                'font-mono font-bold',
                sector.avg_change > 0 ? 'text-bull' : sector.avg_change < 0 ? 'text-bear' : 'text-muted-foreground'
              )}>
                {sector.avg_change > 0 ? '+' : ''}{sector.avg_change.toFixed(1)}%
              </p>
            </div>
            <div className="w-20">
              <p className="text-xs text-muted-foreground">Score</p>
              <div className="flex items-center gap-1">
                <div className="flex-1 h-2 bg-muted/20 rounded-full overflow-hidden">
                  <div 
                    className={cn('h-full rounded-full', 
                      sector.momentum_score > 0 ? 'bg-bull' : 'bg-bear'
                    )}
                    style={{ width: `${Math.min(Math.abs(sector.momentum_score) * 10, 100)}%` }}
                  />
                </div>
                <span className="font-mono text-xs font-bold">{sector.momentum_score.toFixed(1)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Rotation signal card
function RotationSignalCard({ 
  from, 
  to, 
  strength,
  description,
}: { 
  from: string;
  to: string;
  strength: number;
  description: string;
}) {
  return (
    <div className="rounded-xl border border-primary/30 bg-primary/5 p-4">
      <div className="flex items-center gap-3 mb-3">
        <div className="px-3 py-1.5 rounded-lg bg-bear/20 text-bear font-medium text-sm">
          {from}
        </div>
        <ArrowRight className="h-5 w-5 text-primary" />
        <div className="px-3 py-1.5 rounded-lg bg-bull/20 text-bull font-medium text-sm">
          {to}
        </div>
        <div className="ml-auto text-sm font-mono text-primary">
          {strength}% confidence
        </div>
      </div>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

export default function SectorRotationPage() {
  const HISTORY_KEY = 'nepse-sector-rotation-history-v1';
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);

  useEffect(() => {
    setHistory(loadScanHistory(HISTORY_KEY));
  }, []);

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['sector-rotation'],
    queryFn: () => getSectorRotation(),
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
            <PieChart className="h-6 w-6 text-primary" />
            Sector Rotation
          </h1>
          <p className="text-muted-foreground mt-1">
            Weekly momentum ranking - which sectors are heating up or cooling down
          </p>
        </div>
        <button
          onClick={() => {
            setHistory(
              pushScanHistory(HISTORY_KEY, {
                label: 'Sector Rotation Refresh',
                value: 'refresh',
              })
            );
            refetch();
          }}
          disabled={isFetching}
          className="btn-secondary mr-24"
        >
          {isFetching ? <Activity className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </button>
      </div>
      <div className="max-w-xl">
        <ScanHistoryPanel
          title="Sector Rotation History"
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
          {[1,2,3,4,5].map(i => <div key={i} className="h-20 bg-muted/20 rounded-xl" />)}
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-xl border border-bear/30 bg-bear/10 p-6 text-center">
          <p className="text-bear font-medium">{(error as Error)?.message || 'Failed to load sector data'}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Market Rotation Signal */}
          <div className={cn(
            'rounded-xl border p-6',
            result.rotation_signal === 'RISK ON' ? 'border-bull/30 bg-bull/10' :
            result.rotation_signal === 'RISK OFF' ? 'border-bear/30 bg-bear/10' : 'border-border bg-card'
          )}>
            <div className="flex items-center gap-3">
              {result.rotation_signal === 'RISK ON' ? (
                <TrendingUp className="h-6 w-6 text-bull" />
              ) : result.rotation_signal === 'RISK OFF' ? (
                <TrendingDown className="h-6 w-6 text-bear" />
              ) : (
                <Activity className="h-6 w-6 text-muted-foreground" />
              )}
              <span className="text-xl font-bold">Market: {result.rotation_signal}</span>
            </div>
          </div>

          {/* Hot/Cold Summary */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-bull/30 bg-bull/10 p-5">
              <h3 className="font-semibold flex items-center gap-2 mb-3">
                <Flame className="h-5 w-5 text-bull" />
                Hot Sectors
              </h3>
              <div className="space-y-2">
                {result.hot_sectors.map((sector, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span>{sector}</span>
                    <span className="font-mono text-bull">HOT</span>
                  </div>
                ))}
                {result.hot_sectors.length === 0 && (
                  <p className="text-sm text-muted-foreground">No hot sectors this week</p>
                )}
              </div>
            </div>
            
            <div className="rounded-xl border border-bear/30 bg-bear/10 p-5">
              <h3 className="font-semibold flex items-center gap-2 mb-3">
                <Snowflake className="h-5 w-5 text-bear" />
                Cold Sectors
              </h3>
              <div className="space-y-2">
                {result.cold_sectors.map((sector, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span>{sector}</span>
                    <span className="font-mono text-bear">COLD</span>
                  </div>
                ))}
                {result.cold_sectors.length === 0 && (
                  <p className="text-sm text-muted-foreground">No cold sectors this week</p>
                )}
              </div>
            </div>
          </div>

          {/* Full Ranking */}
          <div>
            <h2 className="text-lg font-semibold mb-4">Sector Momentum Ranking</h2>
            <div className="space-y-3">
              {result.sectors.map((sector, i) => (
                <SectorBar key={i} sector={sector} rank={i + 1} />
              ))}
            </div>
          </div>

          {/* Info */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="font-semibold mb-2">How Sector Rotation Works</h3>
            <p className="text-sm text-muted-foreground">
              Money flows between sectors based on market cycles. Hot sectors attract capital from cold sectors.
              Look for rotation signals to catch early moves. A sector warming up after being cold often 
              presents the best opportunities.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
