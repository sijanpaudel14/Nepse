'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPriceTargets, type PriceTargetsResponse } from '@/lib/api';
import { 
  Target, 
  TrendingUp,
  TrendingDown,
  Activity,
  Info,
  ChevronRight,
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

// Price level bar component
function PriceLevelBar({ 
  label, 
  price, 
  currentPrice,
  type,
}: { 
  label: string; 
  price: number; 
  currentPrice: number;
  type: 'support' | 'resistance' | 'fibonacci' | 'current';
}) {
  const pctFromCurrent = ((price - currentPrice) / currentPrice) * 100;
  const position = Math.min(Math.max((price / (currentPrice * 1.3)) * 100, 5), 95);
  
  const colors = {
    support: 'bg-bull border-bull/40',
    resistance: 'bg-bear border-bear/40',
    fibonacci: 'bg-accent border-accent/40',
    current: 'bg-primary border-primary/40',
  };
  
  return (
    <div className="relative h-10 bg-surface-2 rounded-lg border border-border overflow-hidden">
      <div 
        className={cn('absolute h-full w-1 border-l-2', colors[type])}
        style={{ left: `${position}%` }}
      />
      <div 
        className="absolute h-full flex items-center px-2 text-xs"
        style={{ left: `${position}%` }}
      >
        <div className="ml-2 bg-background/90 px-2 py-0.5 rounded whitespace-nowrap">
          <span className="font-medium">{label}</span>
          <span className="text-muted-foreground ml-2">Rs. {price.toLocaleString()}</span>
          <span className={cn(
            'ml-2 font-mono',
            pctFromCurrent > 0 ? 'text-bull' : pctFromCurrent < 0 ? 'text-bear' : 'text-muted-foreground'
          )}>
            ({pctFromCurrent > 0 ? '+' : ''}{pctFromCurrent.toFixed(1)}%)
          </span>
        </div>
      </div>
    </div>
  );
}

// Target card with probability
function TargetCard({ 
  level, 
  price, 
  method,
  probability,
  currentPrice,
}: { 
  level: string;
  price: number;
  method: string;
  probability: number;
  currentPrice: number;
}) {
  const gainPct = ((price - currentPrice) / currentPrice) * 100;
  const isAbove = gainPct > 0;
  
  return (
    <div className={cn(
      'rounded-xl border p-4 transition-all hover:shadow-card-hover',
      isAbove ? 'border-bull/20 bg-bull/5 hover:border-bull/40' : 'border-bear/20 bg-bear/5 hover:border-bear/40'
    )}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-sm text-muted-foreground">{level}</p>
          <p className="text-2xl font-bold mt-1">Rs. {price.toLocaleString()}</p>
        </div>
        <div className={cn(
          'text-right',
          isAbove ? 'text-bull' : 'text-bear'
        )}>
          <p className="text-lg font-bold">{gainPct > 0 ? '+' : ''}{gainPct.toFixed(1)}%</p>
          {isAbove ? <TrendingUp className="h-4 w-4 ml-auto" /> : <TrendingDown className="h-4 w-4 ml-auto" />}
        </div>
      </div>
      
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Method</span>
          <span className="font-medium">{method}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Probability</span>
          <div className="flex items-center gap-2">
            <div className="w-16 h-1.5 bg-muted/30 rounded-full overflow-hidden">
              <div 
                className={cn('h-full rounded-full', isAbove ? 'bg-bull' : 'bg-bear')}
                style={{ width: `${probability}%` }}
              />
            </div>
            <span className="font-medium">{probability}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PriceTargetsPage() {
  const STORAGE_KEY = 'nepse-price-targets-state-v1';
  const HISTORY_KEY = 'nepse-price-targets-history-v1';
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

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['price-targets', searchSymbol],
    queryFn: () => getPriceTargets(searchSymbol),
    enabled: !!searchSymbol,
    retry: 1,
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
          <Target className="h-6 w-6 text-primary" />
          Price Targets
        </h1>
        <p className="text-muted-foreground mt-1">
          Intelligent price predictions using Fibonacci, ATR, Volume Profile & Support/Resistance
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
            className="w-full rounded-lg border border-border bg-card px-4 py-3 pr-12 text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary font-mono"
          />
          <kbd className="absolute right-4 top-1/2 -translate-y-1/2 rounded bg-muted/30 px-1.5 py-0.5 text-[10px] text-muted-foreground">
            ↵
          </kbd>
        </div>
        <button
          type="submit"
          disabled={!symbol.trim() || isLoading}
          className="btn-primary"
        >
          {isLoading ? (
            <Activity className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <Target className="h-4 w-4" />
              Calculate
            </>
          )}
        </button>
      </form>
      <div className="max-w-md">
        <ScanHistoryPanel
          title="Price Target History"
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
          <div className="h-32 bg-muted/20 rounded-xl" />
          <div className="grid md:grid-cols-3 gap-4">
            {[1,2,3].map(i => <div key={i} className="h-40 bg-muted/20 rounded-xl" />)}
          </div>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-xl border border-bear/30 bg-bear/10 p-6 text-center">
          <p className="text-bear font-medium">{(error as Error)?.message || 'Failed to calculate price targets'}</p>
        </div>
      )}

      {/* Empty State */}
      {!searchSymbol && !isLoading && (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <Target className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">Calculate Price Targets</h3>
          <p className="text-muted-foreground mt-2 max-w-md mx-auto">
            Enter a stock symbol to get intelligent price targets based on Fibonacci retracements, 
            ATR projections, volume profile, and key support/resistance levels.
          </p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Current Price Header */}
          <div className="rounded-xl border border-primary/30 bg-primary/5 p-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Current Price</p>
                <p className="text-3xl font-bold mt-1">{result.symbol}</p>
                <p className="text-4xl font-bold text-primary mt-2">
                  Rs. {result.current_price.toLocaleString()}
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Recent Range</p>
                <p className="font-mono mt-1">
                  Rs. {result.recent_low.toLocaleString()} - Rs. {result.recent_high.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {(((result.current_price - result.recent_low) / (result.recent_high - result.recent_low)) * 100).toFixed(0)}% of range
                </p>
              </div>
            </div>
          </div>

          {/* Target Levels */}
          <div>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-bull" />
              Upside Targets (Resistance)
            </h2>
            <div className="grid md:grid-cols-3 gap-4">
              {result.targets.filter(t => t.type === 'target').map((target, i) => (
                <TargetCard
                  key={i}
                  level={target.label}
                  price={target.price}
                  method={target.method}
                  probability={target.probability || 0}
                  currentPrice={result.current_price}
                />
              ))}
            </div>
          </div>

          {/* Support Levels */}
          <div>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <TrendingDown className="h-5 w-5 text-bear" />
              Downside Support
            </h2>
            <div className="grid md:grid-cols-3 gap-4">
              {result.targets.filter(t => t.type === 'stop').map((target, i) => (
                <TargetCard
                  key={i}
                  level={target.label}
                  price={target.price}
                  method={target.method}
                  probability={target.probability || 0}
                  currentPrice={result.current_price}
                />
              ))}
            </div>
          </div>

          {/* Method Explanation */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="font-semibold flex items-center gap-2 mb-3">
              <Info className="h-4 w-4 text-primary" />
              How Targets Are Calculated
            </h3>
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
              <div className="p-3 rounded-lg bg-muted/10">
                <p className="font-medium text-primary">Fibonacci</p>
                <p className="text-muted-foreground mt-1">
                  Key retracement levels (38.2%, 50%, 61.8%) from recent swing
                </p>
              </div>
              <div className="p-3 rounded-lg bg-muted/10">
                <p className="font-medium text-accent">ATR Projection</p>
                <p className="text-muted-foreground mt-1">
                  Average True Range × multiplier for volatility-based targets
                </p>
              </div>
              <div className="p-3 rounded-lg bg-muted/10">
                <p className="font-medium text-warning">Volume Profile</p>
                <p className="text-muted-foreground mt-1">
                  High-volume price zones where buyers/sellers concentrated
                </p>
              </div>
              <div className="p-3 rounded-lg bg-muted/10">
                <p className="font-medium text-bull">S/R Levels</p>
                <p className="text-muted-foreground mt-1">
                  Historical support and resistance from price action
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
