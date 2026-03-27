'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getHeatmap, type HeatmapResponse } from '@/lib/api';
import { 
  Grid3X3,
  Activity,
  TrendingUp,
  TrendingDown,
  BarChart3,
  RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  PageSkeleton,
  SectionHeader,
  EmptyState,
  InfoBox,
  ScanHistoryPanel,
} from '@/components/ui';
import Link from 'next/link';
import {
  loadScanHistory,
  pushScanHistory,
  removeScanHistoryItem,
  clearScanHistory,
  type ScanHistoryItem,
} from '@/lib/scan-history';

// Get color based on change percentage
function getChangeColor(change: number): string {
  if (change >= 5) return 'bg-bull text-white';
  if (change >= 2) return 'bg-bull/70 text-white';
  if (change >= 0.5) return 'bg-bull/40 text-foreground';
  if (change >= 0) return 'bg-muted/20 text-foreground';
  if (change >= -0.5) return 'bg-muted/40 text-foreground';
  if (change >= -2) return 'bg-bear/40 text-foreground';
  if (change >= -5) return 'bg-bear/70 text-white';
  return 'bg-bear text-white';
}

// Stock cell in heatmap
function StockCell({ stock }: { stock: HeatmapResponse['data']['sectors'][0]['stocks'][0] }) {
  return (
    <Link 
      href={`/analyze?symbol=${stock.symbol}`}
      className={cn(
        'block p-2 rounded-md transition-all hover:ring-2 hover:ring-primary',
        getChangeColor(stock.change_pct)
      )}
    >
      <p className="font-bold text-sm truncate">{stock.symbol}</p>
      <p className="text-xs font-mono">
        {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(1)}%
      </p>
    </Link>
  );
}

// Sector block
function SectorBlock({ sector }: { sector: HeatmapResponse['data']['sectors'][0] }) {
  const avgChange = sector.stocks.reduce((sum, s) => sum + s.change_pct, 0) / sector.stocks.length;
  
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className={cn(
        'px-4 py-3 flex items-center justify-between',
        avgChange >= 0 ? 'bg-bull/10' : 'bg-bear/10'
      )}>
        <div>
          <h3 className="font-bold">{sector.name}</h3>
          <p className="text-xs text-muted-foreground">{sector.stocks.length} stocks</p>
        </div>
        <div className={cn(
          'text-lg font-bold',
          avgChange >= 0 ? 'text-bull' : 'text-bear'
        )}>
          {avgChange >= 0 ? '+' : ''}{avgChange.toFixed(1)}%
        </div>
      </div>
      
      <div className="p-3 grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-2">
        {sector.stocks.map((stock, i) => (
          <StockCell key={i} stock={stock} />
        ))}
      </div>
    </div>
  );
}

// Summary stats card
function StatCard({ label, value, change, icon: Icon }: { 
  label: string; 
  value: number; 
  change: number;
  icon: React.ElementType;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-2 text-muted-foreground mb-2">
        <Icon className="h-4 w-4" />
        <span className="text-sm">{label}</span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
      <p className={cn(
        'text-sm font-medium',
        change >= 0 ? 'text-bull' : 'text-bear'
      )}>
        {change >= 0 ? '↑' : '↓'} {Math.abs(change)}%
      </p>
    </div>
  );
}

export default function HeatmapPage() {
  const HISTORY_KEY = 'nepse-heatmap-history-v1';
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);

  useEffect(() => {
    setHistory(loadScanHistory(HISTORY_KEY));
  }, []);

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['heatmap'],
    queryFn: () => getHeatmap(),
    retry: 1,
    staleTime: 60 * 1000, // 1 minute
  });

  const heatmap = data?.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Grid3X3 className="h-6 w-6 text-primary" />
            Market Heatmap
          </h1>
          <p className="text-muted-foreground mt-1">
            Visual overview of all sectors and stocks. Green = gaining, Red = losing.
          </p>
        </div>
        
        <button
          onClick={() => {
            setHistory(
              pushScanHistory(HISTORY_KEY, {
                label: 'Market Heatmap Refresh',
                value: 'refresh',
              })
            );
            refetch();
          }}
          disabled={isFetching}
          className="btn-secondary mr-24"
        >
          {isFetching ? (
            <Activity className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
        </button>
      </div>
      <div className="max-w-xl">
        <ScanHistoryPanel
          title="Heatmap History"
          items={history}
          onSelect={() => refetch()}
          onDelete={(id) => setHistory(removeScanHistoryItem(HISTORY_KEY, id))}
          onClear={() => {
            clearScanHistory(HISTORY_KEY);
            setHistory([]);
          }}
        />
      </div>

      {/* Loading State */}
      {isLoading && <PageSkeleton />}

      {/* Error State */}
      {isError && (
        <InfoBox title="Error" variant="error">
          {(error as Error)?.message || 'Failed to load heatmap. Please try again.'}
        </InfoBox>
      )}

      {/* Results */}
      {heatmap && (
        <>
          {/* Market Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard 
              label="Advancing" 
              value={heatmap.summary.advancing} 
              change={heatmap.summary.advance_pct}
              icon={TrendingUp}
            />
            <StatCard 
              label="Declining" 
              value={heatmap.summary.declining} 
              change={-heatmap.summary.decline_pct}
              icon={TrendingDown}
            />
            <StatCard 
              label="Unchanged" 
              value={heatmap.summary.unchanged} 
              change={0}
              icon={BarChart3}
            />
            <div className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-center gap-2 text-muted-foreground mb-2">
                <Activity className="h-4 w-4" />
                <span className="text-sm">Market Breadth</span>
              </div>
              <p className={cn(
                'text-2xl font-bold',
                heatmap.summary.breadth >= 50 ? 'text-bull' : 'text-bear'
              )}>
                {heatmap.summary.breadth}%
              </p>
              <p className="text-sm text-muted-foreground">
                {heatmap.summary.breadth >= 50 ? 'Bullish' : 'Bearish'}
              </p>
            </div>
          </div>

          {/* Color Legend */}
          <div className="flex items-center justify-center gap-2 flex-wrap">
            <span className="text-sm text-muted-foreground">Legend:</span>
            <span className="px-2 py-1 rounded text-xs bg-bear text-white">-5%+</span>
            <span className="px-2 py-1 rounded text-xs bg-bear/70 text-white">-2% to -5%</span>
            <span className="px-2 py-1 rounded text-xs bg-bear/40">-0.5% to -2%</span>
            <span className="px-2 py-1 rounded text-xs bg-muted/20">±0.5%</span>
            <span className="px-2 py-1 rounded text-xs bg-bull/40">+0.5% to +2%</span>
            <span className="px-2 py-1 rounded text-xs bg-bull/70 text-white">+2% to +5%</span>
            <span className="px-2 py-1 rounded text-xs bg-bull text-white">+5%+</span>
          </div>

          {/* Sector Heatmaps */}
          <div className="space-y-4">
            {heatmap.sectors.map((sector, i) => (
              <SectorBlock key={i} sector={sector} />
            ))}
          </div>
        </>
      )}

      {/* Info Box */}
      <InfoBox title="How to Use the Heatmap" variant="info">
        <ul className="space-y-1 text-sm">
          <li>• <strong>Bright Green:</strong> Stocks up 5%+ (strong momentum)</li>
          <li>• <strong>Bright Red:</strong> Stocks down 5%+ (heavy selling)</li>
          <li>• <strong>Market Breadth:</strong> % of stocks advancing - higher = healthier market</li>
          <li>• Click any stock to see full analysis</li>
        </ul>
      </InfoBox>
    </div>
  );
}
