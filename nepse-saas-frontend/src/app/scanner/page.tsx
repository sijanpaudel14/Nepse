'use client';

import { useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { runScan, addToPortfolio, type StockScanResult } from '@/lib/api';
import { 
  Search, 
  Zap, 
  TrendingUp, 
  TrendingDown,
  Loader2,
  AlertTriangle,
  ShoppingCart,
  RefreshCw,
  Filter,
  ChevronDown,
  Gem,
  CheckCircle,
  XCircle,
  Clock,
  Shield,
  AlertOctagon,
} from 'lucide-react';
import { cn, formatCurrency, formatPercent, getScoreColor, getRiskColor } from '@/lib/utils';
import Link from 'next/link';

// Strategy Selector
function StrategySelector({
  value,
  onChange,
}: {
  value: 'momentum' | 'value';
  onChange: (v: 'momentum' | 'value') => void;
}) {
  return (
    <div className="flex rounded-lg border border-border bg-card p-1">
      <button
        onClick={() => onChange('momentum')}
        className={cn(
          'flex-1 flex items-center justify-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition-colors',
          value === 'momentum' 
            ? 'bg-primary text-primary-foreground' 
            : 'text-muted-foreground hover:text-foreground'
        )}
      >
        <Zap className="h-4 w-4" />
        Momentum
      </button>
      <button
        onClick={() => onChange('value')}
        className={cn(
          'flex-1 flex items-center justify-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition-colors',
          value === 'value' 
            ? 'bg-primary text-primary-foreground' 
            : 'text-muted-foreground hover:text-foreground'
        )}
      >
        <Gem className="h-4 w-4" />
        Value
      </button>
    </div>
  );
}

// Sector Dropdown
function SectorDropdown({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const sectors = [
    { value: '', label: 'All Sectors' },
    { value: 'hydro', label: 'Hydropower' },
    { value: 'bank', label: 'Banking' },
    { value: 'finance', label: 'Finance' },
    { value: 'microfinance', label: 'Microfinance' },
    { value: 'life_insurance', label: 'Life Insurance' },
    { value: 'non_life_insurance', label: 'Non-Life Insurance' },
    { value: 'hotels', label: 'Hotels' },
    { value: 'trading', label: 'Trading' },
    { value: 'manufacturing', label: 'Manufacturing' },
  ];

  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none rounded-lg border border-border bg-card px-4 py-2 pr-10 text-sm font-medium text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      >
        {sectors.map((sector) => (
          <option key={sector.value} value={sector.value}>
            {sector.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
    </div>
  );
}

// Score Icon based on level
function ScoreIcon({ level, className }: { level: string; className?: string }) {
  switch (level) {
    case 'excellent':
      return <CheckCircle className={cn('h-3.5 w-3.5', className)} />;
    case 'good':
      return <TrendingUp className={cn('h-3.5 w-3.5', className)} />;
    case 'average':
      return <Clock className={cn('h-3.5 w-3.5', className)} />;
    default:
      return <XCircle className={cn('h-3.5 w-3.5', className)} />;
  }
}

// Risk Icon based on level  
function RiskIcon({ level, className }: { level: string; className?: string }) {
  switch (level) {
    case 'low':
      return <Shield className={cn('h-3.5 w-3.5', className)} />;
    case 'medium':
      return <AlertTriangle className={cn('h-3.5 w-3.5', className)} />;
    case 'high':
    case 'critical':
      return <AlertOctagon className={cn('h-3.5 w-3.5', className)} />;
    default:
      return <AlertTriangle className={cn('h-3.5 w-3.5', className)} />;
  }
}

// Score Badge
function ScoreBadge({ score }: { score: number }) {
  const { bgColor, textColor, label, level } = getScoreColor(score);
  return (
    <div className={cn(
      'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold',
      bgColor, textColor
    )}>
      <ScoreIcon level={level} />
      {score}/100 {label}
    </div>
  );
}

// Risk Badge
function RiskBadge({ risk }: { risk: string }) {
  const { bgColor, textColor, level } = getRiskColor(risk);
  return (
    <div className={cn(
      'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
      bgColor, textColor
    )}>
      <RiskIcon level={level} />
      {risk}
    </div>
  );
}

// Results Table
function ResultsTable({ 
  results,
  onBuy,
  buyingSymbol,
}: { 
  results: StockScanResult[];
  onBuy: (symbol: string, price: number) => void;
  buyingSymbol: string | null;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="w-full">
        <thead className="table-header border-b border-border">
          <tr>
            <th className="px-4 py-3 text-left">#</th>
            <th className="px-4 py-3 text-left">Symbol</th>
            <th className="px-4 py-3 text-center">Score</th>
            <th className="px-4 py-3 text-right">Entry</th>
            <th className="px-4 py-3 text-right">Target</th>
            <th className="px-4 py-3 text-right">Stop</th>
            <th className="px-4 py-3 text-center">VWAP Risk</th>
            <th className="px-4 py-3 text-center">RSI</th>
            <th className="px-4 py-3 text-center">Volume</th>
            <th className="px-4 py-3 text-center">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/50">
          {results.map((stock, idx) => (
            <tr key={stock.symbol} className="table-row transition-colors">
              <td className="px-4 py-4 font-mono text-muted-foreground">{idx + 1}</td>
              <td className="px-4 py-4">
                <div>
                  <Link
                    href={`/analyze?symbol=${stock.symbol}`}
                    className="font-mono text-lg font-bold text-primary hover:text-primary/80 transition-colors"
                  >
                    {stock.symbol}
                  </Link>
                  <p className="text-xs text-muted-foreground">{stock.sector}</p>
                </div>
              </td>
              <td className="px-4 py-4 text-center">
                <ScoreBadge score={stock.score} />
              </td>
              <td className="px-4 py-4 text-right font-mono font-semibold text-foreground">
                {formatCurrency(stock.entry_price)}
              </td>
              <td className="px-4 py-4 text-right font-mono font-semibold text-bull-text">
                {formatCurrency(stock.target_price)}
              </td>
              <td className="px-4 py-4 text-right font-mono font-semibold text-bear-text">
                {formatCurrency(stock.stop_loss)}
              </td>
              <td className="px-4 py-4 text-center">
                <RiskBadge risk={stock.distribution_risk} />
              </td>
              <td className="px-4 py-4 text-center">
                <span className={cn(
                  'font-mono font-semibold',
                  stock.rsi >= 70 ? 'text-bear-text' :
                  stock.rsi >= 50 ? 'text-bull-text' :
                  stock.rsi >= 30 ? 'text-neutral-text' : 'text-bear-text'
                )}>
                  {stock.rsi?.toFixed(1)}
                </span>
              </td>
              <td className="px-4 py-4 text-center">
                <span className={cn(
                  'font-mono font-semibold',
                  stock.volume_spike >= 2 ? 'text-bull-text' :
                  stock.volume_spike >= 1.5 ? 'text-primary' :
                  'text-muted-foreground'
                )}>
                  {stock.volume_spike?.toFixed(1)}x
                </span>
              </td>
              <td className="px-4 py-4 text-center">
                <button
                  onClick={() => onBuy(stock.symbol, stock.entry_price)}
                  disabled={buyingSymbol === stock.symbol}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold transition-all',
                    'bg-bull-muted text-bull-text border border-bull/20',
                    'hover:bg-bull/20 hover:border-bull/40',
                    'active:scale-[0.98]',
                    buyingSymbol === stock.symbol && 'cursor-not-allowed opacity-50'
                  )}
                >
                  {buyingSymbol === stock.symbol ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ShoppingCart className="h-4 w-4" />
                  )}
                  Buy
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Pillar Breakdown (collapsible)
function PillarBreakdown({ stock }: { stock: StockScanResult }) {
  const [open, setOpen] = useState(false);
  
  const pillars = [
    { name: 'Technical', score: stock.pillar_technical, max: 40 },
    { name: 'Broker/Inst', score: stock.pillar_broker, max: 30 },
    { name: 'Unlock Risk', score: stock.pillar_unlock, max: 20 },
    { name: 'Fundamental', score: stock.pillar_fundamental, max: 10 },
  ];

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ChevronDown className={cn('h-3 w-3 transition-transform', open && 'rotate-180')} />
        {open ? 'Hide' : 'Show'} Pillar Breakdown
      </button>
      {open && (
        <div className="mt-2 space-y-1 rounded-lg bg-card-hover p-3">
          {pillars.map((p) => (
            <div key={p.name} className="flex items-center gap-2 text-xs">
              <span className="w-20 text-muted-foreground">{p.name}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-background">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{ width: `${(p.score / p.max) * 100}%` }}
                />
              </div>
              <span className="w-12 text-right font-mono">
                {p.score.toFixed(1)}/{p.max}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ScannerPage() {
  const queryClient = useQueryClient();
  const scanAbortRef = useRef<AbortController | null>(null);
  const [strategy, setStrategy] = useState<'momentum' | 'value'>('momentum');
  const [sector, setSector] = useState('');
  const [maxPrice, setMaxPrice] = useState<number | ''>('');
  const [buyingSymbol, setBuyingSymbol] = useState<string | null>(null);
  const [isScanRunning, setIsScanRunning] = useState(false);

  // Scan query
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['scan', strategy, sector, maxPrice],
    queryFn: async () => {
      const controller = new AbortController();
      scanAbortRef.current = controller;
      setIsScanRunning(true);
      try {
        return await runScan({
          strategy,
          sector: sector || undefined,
          quick: true,
          maxPrice: maxPrice || undefined,
          limit: 10,
        }, controller.signal);
      } finally {
        setIsScanRunning(false);
        scanAbortRef.current = null;
      }
    },
    enabled: false, // Manual trigger only
  });

  // Feedback state
  const [buyFeedback, setBuyFeedback] = useState<{ symbol: string; success: boolean; message: string } | null>(null);

  // Buy mutation
  const buyMutation = useMutation({
    mutationFn: ({ symbol, price }: { symbol: string; price: number }) =>
      addToPortfolio(symbol, 10, price), // Default 10 shares
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      setBuyingSymbol(null);
      setBuyFeedback({
        symbol: variables.symbol,
        success: true,
        message: `Added ${variables.symbol} at Rs.${variables.price} to portfolio!`,
      });
      // Clear feedback after 4 seconds
      setTimeout(() => setBuyFeedback(null), 4000);
    },
    onError: (error, variables) => {
      setBuyingSymbol(null);
      setBuyFeedback({
        symbol: variables.symbol,
        success: false,
        message: `Failed to add ${variables.symbol}: ${error instanceof Error ? error.message : 'Unknown error'}`,
      });
      setTimeout(() => setBuyFeedback(null), 4000);
    },
  });

  const handleBuy = (symbol: string, price: number) => {
    setBuyingSymbol(symbol);
    buyMutation.mutate({ symbol, price });
  };

  const handleScan = () => {
    refetch();
  };

  const handleStopScan = () => {
    if (scanAbortRef.current) {
      scanAbortRef.current.abort();
      scanAbortRef.current = null;
      setIsScanRunning(false);
      setBuyFeedback({
        symbol: '',
        success: false,
        message: 'Scan stopped by user.',
      });
      setTimeout(() => setBuyFeedback(null), 3000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Buy Feedback Toast */}
      {buyFeedback && (
        <div className={cn(
          'fixed top-4 right-4 z-50 flex items-center gap-3 rounded-lg px-4 py-3 shadow-lg animate-in slide-in-from-top-2',
          buyFeedback.success
            ? 'bg-bull/20 border border-bull/30 text-bull-text'
            : 'bg-bear/20 border border-bear/30 text-bear-text'
        )}>
          {buyFeedback.success ? (
            <CheckCircle className="h-5 w-5" />
          ) : (
            <XCircle className="h-5 w-5" />
          )}
          <span className="text-sm font-medium">{buyFeedback.message}</span>
          <button 
            onClick={() => setBuyFeedback(null)}
            className="ml-2 opacity-60 hover:opacity-100"
          >
            <XCircle className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Market Scanner</h1>
        <p className="text-muted-foreground">
          AI-powered stock screening with 4-Pillar analysis
        </p>
      </div>

      {/* Controls */}
      <div className="card flex flex-wrap items-center gap-4 rounded-xl border border-border p-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Strategy:</span>
        </div>
        <StrategySelector value={strategy} onChange={setStrategy} />
        
        <div className="h-8 w-px bg-border" />
        
        <SectorDropdown value={sector} onChange={setSector} />
        
        <div className="h-8 w-px bg-border" />
        
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Max Price:</span>
          <input
            type="number"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value ? Number(e.target.value) : '')}
            placeholder="Any"
            className="w-24 rounded-lg border border-border bg-surface-2 px-3 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
          />
        </div>

        <div className="flex-1" />

        <button
          onClick={handleScan}
          disabled={isLoading || isFetching || isScanRunning}
          className="btn-primary"
        >
          {isLoading || isFetching || isScanRunning ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              Scanning...
            </>
          ) : (
            <>
              <Zap className="h-5 w-5" />
              Run AI Scan
            </>
          )}
        </button>
        <button
          onClick={handleStopScan}
          disabled={!isScanRunning}
          className={cn(
            'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold transition-colors',
            isScanRunning
              ? 'border-bear/40 bg-bear/10 text-bear hover:bg-bear/20'
              : 'cursor-not-allowed border-border bg-card text-muted-foreground opacity-50'
          )}
        >
          <XCircle className="h-4 w-4" />
          Stop
        </button>
      </div>

      {/* Market Regime Banner */}
      {data && (
        <div className={cn(
          'flex items-center justify-between rounded-lg border px-4 py-3',
          data.market_regime === 'BULL' ? 'border-bull/30 bg-bull-muted/30' :
          data.market_regime === 'BEAR' ? 'border-bear/30 bg-bear-muted/30' :
          'border-warning/30 bg-neutral-muted/30'
        )}>
          <div className="flex items-center gap-3">
            {data.market_regime === 'BULL' ? (
              <TrendingUp className="h-5 w-5 text-bull-text" />
            ) : (
              <TrendingDown className="h-5 w-5 text-bear-text" />
            )}
            <span className="font-medium">
              Market Regime: {data.market_regime}
            </span>
          </div>
          <div className="text-sm text-muted-foreground">
            Analyzed {data.total_analyzed} stocks • Strategy: {data.strategy.toUpperCase()}
            {data.sector && ` • Sector: ${data.sector}`}
          </div>
        </div>
      )}

      {/* Results */}
      {data?.results && data.results.length > 0 ? (
        <ResultsTable 
          results={data.results} 
          onBuy={handleBuy}
          buyingSymbol={buyingSymbol}
        />
      ) : data?.results && data.results.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-card py-16">
          <AlertTriangle className="h-12 w-12 text-warning" />
          <h3 className="mt-4 text-xl font-semibold">No Opportunities Found</h3>
          <p className="mt-2 text-center text-muted-foreground">
            No stocks passed the 4-Pillar criteria with current filters.<br />
            Try adjusting your strategy or sector.
          </p>
        </div>
      ) : !isLoading && !data ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-16">
          <Search className="h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-xl font-semibold">Ready to Scan</h3>
          <p className="mt-2 text-center text-muted-foreground">
            Configure your filters above and click "Run AI Scan" to find<br />
            the best trading opportunities in the market.
          </p>
        </div>
      ) : null}

      {/* Loading State */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
          <p className="mt-4 text-lg font-medium">Running 4-Pillar Analysis...</p>
          <p className="text-sm text-muted-foreground">This may take 30-60 seconds</p>
        </div>
      )}

      {/* Detailed Cards (Mobile/Alternative View) */}
      {data?.results && data.results.length > 0 && (
        <div className="lg:hidden space-y-4">
          {data.results.map((stock, idx) => (
            <div key={stock.symbol} className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">#{idx + 1}</span>
                    <Link
                      href={`/analyze?symbol=${stock.symbol}`}
                      className="font-mono text-xl font-bold text-primary hover:underline"
                    >
                      {stock.symbol}
                    </Link>
                  </div>
                  <p className="text-sm text-muted-foreground">{stock.sector}</p>
                </div>
                <ScoreBadge score={stock.score} />
              </div>
              
              <div className="mt-4 grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-xs text-muted-foreground">Entry</p>
                  <p className="font-mono font-semibold">{formatCurrency(stock.entry_price)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Target</p>
                  <p className="font-mono font-semibold text-bull">{formatCurrency(stock.target_price)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Stop</p>
                  <p className="font-mono font-semibold text-bear">{formatCurrency(stock.stop_loss)}</p>
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between">
                <RiskBadge risk={stock.distribution_risk} />
                <button
                  onClick={() => handleBuy(stock.symbol, stock.entry_price)}
                  disabled={buyingSymbol === stock.symbol}
                  className="flex items-center gap-1 rounded-lg bg-bull/20 px-4 py-2 text-sm font-medium text-bull"
                >
                  <ShoppingCart className="h-4 w-4" />
                  Buy
                </button>
              </div>

              <PillarBreakdown stock={stock} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
