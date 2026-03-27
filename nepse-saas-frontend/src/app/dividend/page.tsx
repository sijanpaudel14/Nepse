'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDividendForecast, type DividendForecastResponse } from '@/lib/api';
import { 
  Coins,
  Search,
  TrendingUp,
  TrendingDown,
  Calendar,
  Percent,
  Calculator,
  Activity,
  AlertTriangle,
  CheckCircle,
  XCircle,
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

// Yield indicator
function YieldGauge({ 
  yield_pct,
  label,
}: { 
  yield_pct: number;
  label: string;
}) {
  const getColor = (y: number) => {
    if (y >= 5) return { fill: 'bg-bull', text: 'text-bull', label: 'EXCELLENT' };
    if (y >= 3) return { fill: 'bg-primary', text: 'text-primary', label: 'GOOD' };
    if (y >= 1.5) return { fill: 'bg-warning', text: 'text-warning', label: 'FAIR' };
    return { fill: 'bg-muted', text: 'text-muted-foreground', label: 'LOW' };
  };
  
  const config = getColor(yield_pct);
  
  return (
    <div className="rounded-lg border border-border bg-card p-4 text-center">
      <p className="text-xs text-muted-foreground mb-2">{label}</p>
      <p className={cn('text-3xl font-bold', config.text)}>{yield_pct.toFixed(2)}%</p>
      <div className="mt-2 h-2 bg-muted/20 rounded-full overflow-hidden">
        <div 
          className={cn('h-full rounded-full transition-all', config.fill)} 
          style={{ width: `${Math.min(yield_pct * 10, 100)}%` }} 
        />
      </div>
      <p className="text-xs text-muted-foreground mt-2">{config.label}</p>
    </div>
  );
}

// Dividend history bar
function DividendBar({ year, dividend, maxDividend }: { year: string; dividend: number; maxDividend: number }) {
  const pct = maxDividend > 0 ? (dividend / maxDividend) * 100 : 0;
  
  return (
    <div className="flex items-center gap-3">
      <span className="w-16 text-sm text-muted-foreground">{year}</span>
      <div className="flex-1 h-6 bg-muted/20 rounded-full overflow-hidden">
        <div 
          className="h-full bg-primary rounded-full flex items-center justify-end pr-2"
          style={{ width: `${Math.max(pct, 10)}%` }}
        >
          <span className="text-[10px] font-mono font-semibold">{dividend}%</span>
        </div>
      </div>
    </div>
  );
}

export default function DividendPage() {
  const STORAGE_KEY = 'nepse-dividend-state-v1';
  const HISTORY_KEY = 'nepse-dividend-history-v1';
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
    queryKey: ['dividend-forecast', searchSymbol],
    queryFn: () => getDividendForecast(searchSymbol),
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Coins className="h-6 w-6 text-primary" />
          Dividend Forecast
        </h1>
        <p className="text-muted-foreground mt-1">
          EPS-based dividend prediction and yield analysis
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
            placeholder="Enter symbol (e.g., NABIL, NICA, UPPER)"
            className="w-full pl-10 pr-4 py-2.5 bg-surface-1 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>
        <button type="submit" disabled={!symbol.trim() || isLoading} className="btn-primary">
          {isLoading ? <Activity className="h-4 w-4 animate-spin" /> : 'Analyze'}
        </button>
      </form>
      <div className="max-w-md">
        <ScanHistoryPanel
          title="Dividend History"
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
            {[1,2,3].map(i => <div key={i} className="h-24 bg-muted/20 rounded-xl" />)}
          </div>
        </div>
      )}

      {/* Error */}
      {isError && searchSymbol && (
        <div className="rounded-xl border border-bear/30 bg-bear/10 p-6 text-center">
          <p className="text-bear font-medium">{(error as Error)?.message || 'Failed to forecast dividend'}</p>
        </div>
      )}

      {/* Empty State */}
      {!searchSymbol && !isLoading && (
        <div className="rounded-xl border border-border bg-card p-12 text-center">
          <Coins className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">Dividend Analysis</h3>
          <p className="text-muted-foreground mt-2">
            Enter a stock symbol to see dividend history, yield forecast, and payout predictions.
          </p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Header Card */}
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-2xl font-bold">{result.symbol}</p>
                <p className="text-sm text-muted-foreground">{result.company_name}</p>
              </div>
              <div className={cn(
                'px-3 py-1.5 rounded-lg font-semibold',
                result.dividend_status === 'REGULAR' ? 'bg-bull/20 text-bull' :
                result.dividend_status === 'IRREGULAR' ? 'bg-warning/20 text-warning' : 'bg-bear/20 text-bear'
              )}>
                {result.dividend_status} DIVIDEND PAYER
              </div>
            </div>
            
            <div className="grid md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Current Price</p>
                <p className="text-xl font-semibold">Rs. {result.current_price.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">EPS (TTM)</p>
                <p className="text-xl font-semibold">Rs. {result.eps.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Book Value</p>
                <p className="text-xl font-semibold">Rs. {result.book_value.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">PE Ratio</p>
                <p className="text-xl font-semibold">{result.pe_ratio.toFixed(1)}</p>
              </div>
            </div>
          </div>

          {/* Yield Analysis */}
          <div className="grid md:grid-cols-3 gap-4">
            <YieldGauge 
              yield_pct={result.current_yield}
              label="Current Dividend Yield"
            />
            <YieldGauge 
              yield_pct={result.forecasted_yield}
              label="Forecasted Yield (Next Year)"
            />
            <div className="rounded-lg border border-border bg-card p-4 text-center flex flex-col justify-center">
              <p className="text-xs text-muted-foreground mb-2">Predicted Dividend</p>
              <p className="text-3xl font-bold text-primary">{result.forecasted_dividend}%</p>
              <p className="text-xs text-muted-foreground mt-2">
                ~Rs. {((result.forecasted_dividend / 100) * 100).toFixed(2)} per share
              </p>
            </div>
          </div>

          {/* Dividend History */}
          <div className="rounded-xl border border-border bg-card p-6">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Calendar className="h-5 w-5 text-primary" />
              Dividend History (Last 5 Years)
            </h2>
            <div className="space-y-3">
              {result.history.map((h, i) => (
                <DividendBar 
                  key={i} 
                  year={h.year} 
                  dividend={h.dividend} 
                  maxDividend={Math.max(...result.history.map(x => x.dividend))}
                />
              ))}
            </div>
          </div>

          {/* Analysis */}
          <div className="grid md:grid-cols-2 gap-4">
            {/* Strengths */}
            <div className="rounded-xl border border-bull/30 bg-bull/10 p-5">
              <h3 className="font-semibold text-bull mb-3 flex items-center gap-2">
                <CheckCircle className="h-5 w-5" />
                Strengths
              </h3>
              <ul className="space-y-2">
                {result.strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <TrendingUp className="h-4 w-4 text-bull mt-0.5" />
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
            
            {/* Risks */}
            <div className="rounded-xl border border-bear/30 bg-bear/10 p-5">
              <h3 className="font-semibold text-bear mb-3 flex items-center gap-2">
                <XCircle className="h-5 w-5" />
                Risks
              </h3>
              <ul className="space-y-2">
                {result.risks.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <TrendingDown className="h-4 w-4 text-bear mt-0.5" />
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Verdict */}
          <div className={cn(
            'rounded-xl border p-6',
            result.verdict === 'BUY' ? 'border-bull/30 bg-bull/10' : 'border-border bg-card'
          )}>
            <div className="flex items-center gap-3">
              <Calculator className="h-6 w-6 text-primary" />
              <span className="text-xl font-bold">Dividend Investor Verdict: {result.verdict}</span>
            </div>
            <p className="text-muted-foreground mt-2">{result.reasoning}</p>
          </div>
        </div>
      )}
    </div>
  );
}
