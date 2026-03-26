'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getOrderFlow, type OrderFlowResponse } from '@/lib/api';
import { 
  LineChart, 
  TrendingUp,
  TrendingDown,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Search,
  AlertTriangle,
  Info,
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

// Delta bar visualization
function DeltaBar({ buy, sell }: { buy: number; sell: number }) {
  const total = buy + sell;
  const buyPct = total > 0 ? (buy / total) * 100 : 50;
  const net = buy - sell;
  
  return (
    <div className="space-y-2">
      <div className="flex h-8 rounded-lg overflow-hidden border border-border">
        <div 
          className="bg-bull flex items-center justify-center text-xs font-bold text-white"
          style={{ width: `${buyPct}%` }}
        >
          {buyPct > 15 && `${(buy/1000).toFixed(0)}K`}
        </div>
        <div 
          className="bg-bear flex items-center justify-center text-xs font-bold text-white"
          style={{ width: `${100 - buyPct}%` }}
        >
          {100 - buyPct > 15 && `${(sell/1000).toFixed(0)}K`}
        </div>
      </div>
      <div className="flex justify-between text-xs">
        <span className="text-bull">Buy: {(buy/1000).toFixed(1)}K</span>
        <span className={cn('font-bold', net > 0 ? 'text-bull' : net < 0 ? 'text-bear' : 'text-muted-foreground')}>
          Net: {net > 0 ? '+' : ''}{(net/1000).toFixed(1)}K
        </span>
        <span className="text-bear">Sell: {(sell/1000).toFixed(1)}K</span>
      </div>
    </div>
  );
}

// Price level row
function PriceLevelRow({ level }: { level: { price: number; buy_volume: number; sell_volume: number; net: number } }) {
  const total = level.buy_volume + level.sell_volume;
  const buyPct = total > 0 ? (level.buy_volume / total) * 100 : 50;
  
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="w-20 font-mono text-sm">Rs. {level.price.toLocaleString()}</span>
      <div className="flex-1 h-3 bg-muted/20 rounded-full overflow-hidden flex">
        <div className="bg-bull h-full" style={{ width: `${buyPct}%` }} />
        <div className="bg-bear h-full" style={{ width: `${100 - buyPct}%` }} />
      </div>
      <span className={cn(
        'w-16 text-right font-mono text-xs',
        level.net > 0 ? 'text-bull' : 'text-bear'
      )}>
        {level.net > 0 ? '+' : ''}{(level.net / 1000).toFixed(1)}K
      </span>
    </div>
  );
}

// Delta bar item
function DeltaBarItem({ bar }: { bar: { date: string; delta: number; cumulative_delta: number; delta_pct?: number; close_change_pct?: number } }) {
  const maxDelta = 10000; // Scale factor
  const barHeight = Math.min(Math.abs(bar.delta) / maxDelta * 100, 100);
  const dateLabel = (() => {
    const raw = String(bar.date || '');
    const datePart = raw.replace('T', ' ').split(' ')[0];
    if (datePart.includes('-') && datePart.length >= 10) {
      return datePart.slice(5); // MM-DD
    }
    return raw.slice(0, 5);
  })();
  
  return (
    <div className="flex min-w-[46px] flex-col items-center gap-1">
      <div className="h-16 w-full flex flex-col justify-end items-center">
        <div 
          className={cn(
            'w-3/4 rounded-t transition-all',
            bar.delta >= 0 ? 'bg-bull' : 'bg-bear'
          )}
          style={{ height: `${barHeight}%` }}
        />
      </div>
      <span className="text-[10px] leading-none text-muted-foreground">
        {dateLabel}
      </span>
      <span className={cn('text-[10px] leading-none font-medium', (bar.delta_pct || 0) >= 0 ? 'text-bull' : 'text-bear')}>
        {(bar.delta_pct || 0) >= 0 ? '+' : ''}{(bar.delta_pct || 0).toFixed(1)}%
      </span>
    </div>
  );
}

export default function OrderFlowPage() {
  const STORAGE_KEY = 'nepse-order-flow-state-v1';
  const HISTORY_KEY = 'nepse-order-flow-history-v1';
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
    queryKey: ['order-flow', searchSymbol],
    queryFn: () => getOrderFlow(searchSymbol),
    enabled: searchSymbol.length >= 2,
    retry: 1,
    staleTime: 5 * 60 * 1000,
  });

  const result = data?.data;

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

  // Calculate totals from delta bars
  const totalBuy = result?.delta_bars.reduce((sum, b) => sum + b.buy_volume, 0) || 0;
  const totalSell = result?.delta_bars.reduce((sum, b) => sum + b.sell_volume, 0) || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <LineChart className="h-6 w-6 text-primary" />
          Order Flow Analysis
        </h1>
        <p className="text-muted-foreground mt-1">
          Simple view of who is stronger: buyers or sellers
        </p>
      </div>

      {/* Search */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="Enter symbol (e.g., NABIL, NICA)"
            className="w-full pl-10 pr-4 py-2.5 bg-surface-1 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>
        <button type="submit" disabled={!symbol.trim() || isLoading} className="btn-primary">
          {isLoading ? <Activity className="h-4 w-4 animate-spin" /> : 'Analyze Flow'}
        </button>
      </form>
      <div className="max-w-md">
        <ScanHistoryPanel
          title="Order Flow History"
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
          <div className="h-48 bg-muted/20 rounded-xl" />
        </div>
      )}

      {/* Error */}
      {isError && searchSymbol && (
        <div className="rounded-xl border border-bear/30 bg-bear/10 p-6 text-center">
          <p className="text-bear font-medium">{(error as Error)?.message || 'Failed to analyze order flow'}</p>
        </div>
      )}

      {/* Empty State */}
      {!searchSymbol && !isLoading && (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <LineChart className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">Order Flow Analysis</h3>
          <p className="text-muted-foreground mt-2">
            Enter a symbol to analyze buying and selling pressure through delta analysis.
          </p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-2xl font-bold">{result.symbol}</p>
                <p className="text-sm text-muted-foreground">
                  Current: Rs. {result.current_price.toLocaleString()}
                </p>
              </div>
              <div className={cn(
                'px-4 py-2 rounded-lg flex items-center gap-2',
                result.cumulative_delta > 0 ? 'bg-bull/20 text-bull' : 'bg-bear/20 text-bear'
              )}>
                {result.cumulative_delta > 0 ? <ArrowUpRight className="h-5 w-5" /> : <ArrowDownRight className="h-5 w-5" />}
                <span className="font-bold text-lg">
                  {result.cumulative_delta > 0 ? '+' : ''}{(result.cumulative_delta / 1000).toFixed(1)}K
                </span>
                <span className="text-sm opacity-80">Cumulative Delta</span>
              </div>
            </div>
            
            <DeltaBar buy={totalBuy} sell={totalSell} />
            <div className="mt-3 rounded-lg border border-border/60 bg-muted/10 p-3 text-sm text-muted-foreground">
              <p><strong>How to read:</strong> Green means buyers were stronger. Red means sellers were stronger.</p>
              <p className="mt-1">Cumulative Delta is the running buy-sell gap over recent sessions.</p>
            </div>
          </div>

          {/* Flow Bias */}
          <div className={cn(
            'rounded-xl border p-5',
            result.bias_color === 'bull' ? 'border-bull/30 bg-bull/10' :
            result.bias_color === 'bear' ? 'border-bear/30 bg-bear/10' : 'border-border bg-card'
          )}>
            <div className="flex items-center gap-3">
              {result.bias_color === 'bull' ? (
                <TrendingUp className="h-6 w-6 text-bull" />
              ) : result.bias_color === 'bear' ? (
                <TrendingDown className="h-6 w-6 text-bear" />
              ) : (
                <Activity className="h-6 w-6 text-muted-foreground" />
              )}
              <span className="text-xl font-bold">{result.flow_bias}</span>
            </div>
          </div>

          {/* Delta Bars */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h2 className="text-lg font-semibold mb-4">Daily Delta (Last 20 Days)</h2>
            <div className="mb-3 rounded-lg border border-border/60 bg-muted/10 p-3 text-xs text-muted-foreground">
              Each bar shows who dominated that day.
            </div>
            <div className="flex gap-1 items-end h-32 overflow-x-auto pb-8">
              {result.delta_bars.map((bar, i) => (
                <DeltaBarItem key={i} bar={bar} />
              ))}
            </div>
            <div className="mt-3 grid md:grid-cols-3 gap-3">
              {result.delta_bars.slice(-3).map((bar, i) => (
                <div key={i} className="rounded-lg border border-border/60 bg-muted/10 p-3">
                  <p className="text-xs text-muted-foreground">{bar.date}</p>
                  <p className={cn('text-sm font-semibold', bar.delta >= 0 ? 'text-bull' : 'text-bear')}>
                    Buyer-Seller Gap: {bar.delta >= 0 ? '+' : ''}{(bar.delta / 1000).toFixed(1)}K ({(bar.delta_pct || 0).toFixed(1)}%)
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Price move: {(bar.close_change_pct || 0) >= 0 ? '+' : ''}{(bar.close_change_pct || 0).toFixed(2)}%
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Price Levels */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h2 className="text-lg font-semibold mb-4">Volume at Price</h2>
            <div className="mb-3 rounded-lg border border-border/60 bg-muted/10 p-3 text-xs text-muted-foreground">
              Shows where heavy trading happened. Large green at a price means stronger buying at that zone.
            </div>
            <div className="space-y-1">
              {result.price_levels.map((level, i) => (
                <PriceLevelRow key={i} level={level} />
              ))}
            </div>
          </div>

          {/* Absorptions */}
          {result.absorptions.length > 0 && (
            <div className="rounded-xl border border-warning/30 bg-warning/10 p-5">
              <h3 className="font-semibold text-warning mb-3 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Absorption Patterns Detected
              </h3>
              <div className="mb-3 rounded-lg border border-warning/30 bg-card/60 p-3 text-xs text-muted-foreground flex items-start gap-2">
                <Info className="h-4 w-4 mt-0.5 text-warning" />
                <span>
                  Absorption means high volume traded, but price did not move much. That can signal hidden large buyers/sellers absorbing orders.
                </span>
              </div>
              <div className="space-y-2">
                {result.absorptions.map((abs, i) => (
                  <div key={i} className="rounded-lg border border-warning/20 bg-card/60 p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">{abs.date}</span>
                      <span className="text-warning font-semibold">{abs.volume_ratio}x normal volume</span>
                    </div>
                    <div className="mt-1 grid md:grid-cols-3 gap-2 text-xs">
                      <span>
                        Day range: <strong>{(abs.intraday_range_pct ?? abs.price_change).toFixed(2)}%</strong>
                      </span>
                      <span>
                        Daily close move: <strong>{(abs.close_to_close_pct ?? 0).toFixed(2)}%</strong>
                      </span>
                      <span>
                        Net movement used: <strong>{abs.price_change.toFixed(2)}%</strong>
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Interpretation: High volume but limited movement can mean large players are quietly absorbing orders.
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
