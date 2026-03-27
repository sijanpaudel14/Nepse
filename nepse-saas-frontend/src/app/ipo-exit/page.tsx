'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getIPOExit, type IPOExitResponse } from '@/lib/api';
import { 
  Clock, 
  TrendingUp,
  TrendingDown,
  Users,
  BarChart3,
  AlertTriangle,
  Target,
  Shield,
  ArrowUp,
  ArrowDown,
  Activity,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  PageSkeleton,
  VerdictBadge,
  ScoreCircle,
  ScoreBar,
  WarningBox,
  SectionHeader,
  SymbolInput,
  EmptyState,
  InfoBox,
  PriceChange,
  ScanHistoryPanel,
} from '@/components/ui';
import {
  loadScanHistory,
  pushScanHistory,
  removeScanHistoryItem,
  clearScanHistory,
  type ScanHistoryItem,
} from '@/lib/scan-history';

// Volume bar chart component
function VolumeChart({ dates, volumes, trend }: { 
  dates: string[]; 
  volumes: number[]; 
  trend: string;
}) {
  const maxVolume = Math.max(...volumes);
  
  return (
    <div className="space-y-2">
      {dates.map((date, i) => {
        const vol = volumes[i];
        const pct = (vol / maxVolume) * 100;
        const isSpike = vol > maxVolume * 0.8;
        
        return (
          <div key={date} className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground w-20">{date}</span>
            <div className="flex-1 h-4 bg-muted/20 rounded overflow-hidden">
              <div 
                className={cn(
                  'h-full rounded transition-all',
                  isSpike ? 'bg-warning' : 'bg-primary'
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs font-mono w-16 text-right">
              {vol.toLocaleString()}
            </span>
            {isSpike && <span className="text-xs text-warning">Spike</span>}
          </div>
        );
      })}
    </div>
  );
}

// Broker flow component
function BrokerFlow({ flow }: { flow: IPOExitResponse['data']['broker_flow'] }) {
  const flowColors = {
    STRONG_ACCUMULATION: 'text-bull bg-bull/20',
    ACCUMULATION: 'text-bull bg-bull/10',
    NEUTRAL: 'text-warning bg-warning/20',
    DISTRIBUTION: 'text-bear bg-bear/10',
    STRONG_DISTRIBUTION: 'text-bear bg-bear/20',
  };
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">Net Flow</span>
        <span className={cn(
          'px-3 py-1 rounded-full text-sm font-semibold',
          flowColors[flow.flow_type] || 'text-muted-foreground bg-muted/20'
        )}>
          {flow.net_quantity > 0 ? '+' : ''}{flow.net_quantity.toLocaleString()} shares
        </span>
      </div>
      
      <p className="text-sm text-muted-foreground">{flow.interpretation}</p>
      
      <div className="grid md:grid-cols-2 gap-4">
        {/* Top Buyers */}
        <div className="rounded-lg bg-bull/10 p-3">
          <h4 className="text-sm font-medium text-bull mb-2">Top Buyers</h4>
          <div className="space-y-1">
            {flow.top_buyers.slice(0, 3).map((buyer, i) => (
              <div key={i} className="flex justify-between text-sm">
                <span className="truncate">{buyer.name}</span>
                <span className="font-mono text-bull">+{buyer.quantity.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
        
        {/* Top Sellers */}
        <div className="rounded-lg bg-bear/10 p-3">
          <h4 className="text-sm font-medium text-bear mb-2">Top Sellers</h4>
          <div className="space-y-1">
            {flow.top_sellers.slice(0, 3).map((seller, i) => (
              <div key={i} className="flex justify-between text-sm">
                <span className="truncate">{seller.name}</span>
                <span className="font-mono text-bear">-{seller.quantity.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function IPOExitPage() {
  const STORAGE_KEY = 'nepse-ipo-exit-state-v1';
  const HISTORY_KEY = 'nepse-ipo-exit-history-v1';
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
    queryKey: ['ipo-exit', searchSymbol],
    queryFn: () => getIPOExit({ symbol: searchSymbol }),
    enabled: !!searchSymbol,
    retry: 1,
    staleTime: 0, // Always fetch fresh data
    gcTime: 0, // Don't keep in cache (renamed from cacheTime in React Query v5)
  });

  const handleSubmit = () => {
    const clean = symbol.trim().toUpperCase();
    if (!clean) return;
    setHistory(pushScanHistory(HISTORY_KEY, { label: clean, value: clean }));
    if (clean === searchSymbol) {
      refetch();
    } else {
      setSearchSymbol(clean);
    }
  };

  const ipo = data?.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Clock className="h-6 w-6 text-primary" />
          IPO Exit Analyzer
        </h1>
        <p className="text-muted-foreground mt-1">
          Know when to sell newly listed stocks by analyzing volume, broker flow, and price patterns
        </p>
      </div>

      {/* Symbol Input */}
      <div className="max-w-2xl flex gap-2">
        <div className="flex-1">
          <SymbolInput
            value={symbol}
            onChange={setSymbol}
            onSubmit={handleSubmit}
            placeholder="Enter IPO symbol (e.g., SOHL)"
            isLoading={isLoading}
          />
        </div>
        <button
          onClick={() => {
            const clean = symbol.trim().toUpperCase();
            if (!clean) return;
            setHistory(pushScanHistory(HISTORY_KEY, { label: clean, value: clean }));
            setSearchSymbol(clean); // This will trigger a fresh fetch
          }}
          disabled={isLoading || !symbol.trim()}
          className="px-6 py-2.5 bg-primary text-primary-foreground hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground rounded-lg font-semibold transition-colors flex items-center gap-2"
        >
          <Activity className="h-4 w-4" />
          Analyze
        </button>
      </div>
      <div className="max-w-md">
        <ScanHistoryPanel
          title="IPO Exit History"
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

      {/* Results */}
      {isLoading && <PageSkeleton />}
      
      {isError && (
        <InfoBox title="Error" variant="error">
          {(error as Error)?.message || 'Failed to analyze IPO. Make sure the stock is newly listed (< 30 days).'}
        </InfoBox>
      )}

      {!searchSymbol && !isLoading && (
        <EmptyState
          icon={Clock}
          title="Enter an IPO Symbol"
          description="Type a newly listed stock symbol to analyze exit timing. Best for stocks listed within the last 30 days."
        />
      )}

      {ipo && (
        <div className="space-y-6">
          {/* Main Status Card */}
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-bold">{ipo.symbol}</h2>
                  <VerdictBadge verdict={ipo.verdict} size="lg" />
                </div>
                <p className="text-muted-foreground mt-1">
                  Listed {ipo.days_listed} days ago
                </p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-bold">Rs. {ipo.current_price.toLocaleString()}</p>
                <div className="flex items-center gap-2 justify-end mt-1">
                  <span className="text-sm text-muted-foreground">from listing</span>
                  <PriceChange percentage={ipo.gain_loss_pct} />
                </div>
              </div>
            </div>

            {/* Status Row */}
            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="rounded-lg bg-muted/20 p-4 flex flex-col items-center justify-center">
                <ScoreCircle score={ipo.total_exit_score} size="md" />
                <p className="mt-2 text-xs font-medium text-muted-foreground">Exit Score</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Listing Price</p>
                <p className="text-lg font-semibold mt-1">Rs. {ipo.listing_price.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Days Listed</p>
                <p className="text-lg font-semibold mt-1">{ipo.days_listed} days</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Stop Loss</p>
                <p className="text-lg font-semibold text-bear mt-1">Rs. {ipo.stop_loss.toLocaleString()}</p>
              </div>
            </div>
          </div>

          {/* Volume Trend */}
          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader 
              title="Volume Trend" 
              subtitle={`Trend: ${ipo.volume_trend.trend}`}
            />
            <VolumeChart 
              dates={ipo.volume_trend.dates}
              volumes={ipo.volume_trend.volumes}
              trend={ipo.volume_trend.trend}
            />
            <p className="mt-4 text-sm text-muted-foreground">
              {ipo.volume_trend.interpretation}
            </p>
          </div>

          {/* Broker Flow */}
          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader 
              title="Who's Trading?" 
              subtitle={ipo.broker_flow.analysis_period ? `Broker flow analysis (${ipo.broker_flow.analysis_period})` : 'Broker flow analysis'}
            />
            <BrokerFlow flow={ipo.broker_flow} />
          </div>

          {/* Price Pattern */}
          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader title="Price Pattern" />
            <div className="grid md:grid-cols-3 gap-4">
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Day 2 Low</p>
                <p className="text-lg font-semibold">Rs. {ipo.price_pattern.day2_low.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">Critical support level</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Buffer Above Low</p>
                <p className="text-lg font-semibold">{ipo.price_pattern.buffer_pct.toFixed(1)}%</p>
              </div>
              <div className={cn(
                'rounded-lg p-4',
                ipo.price_pattern.trend === 'UPTREND' ? 'bg-bull/10' :
                ipo.price_pattern.trend === 'BREAKDOWN' ? 'bg-bear/10' : 'bg-warning/10'
              )}>
                <p className="text-sm text-muted-foreground">Trend</p>
                <p className={cn(
                  'text-lg font-semibold',
                  ipo.price_pattern.trend === 'UPTREND' ? 'text-bull' :
                  ipo.price_pattern.trend === 'BREAKDOWN' ? 'text-bear' : 'text-warning'
                )}>
                  {ipo.price_pattern.trend}
                </p>
              </div>
            </div>
          </div>

          {/* Exit Signals */}
          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader 
              title="Exit Signals" 
              subtitle={`Total Score: ${ipo.total_exit_score}/100`}
            />
            <div className="space-y-3">
              {ipo.exit_signals.map((signal, i) => (
                <div key={i} className="flex items-center gap-4">
                  <div className={cn(
                    'h-3 w-3 rounded-full',
                    signal.triggered ? 'bg-bear' : 'bg-muted/30'
                  )} />
                  <div className="flex-1">
                    <p className="font-medium">{signal.name}</p>
                  </div>
                  <div className="text-right">
                    <span className={cn(
                      'font-mono text-sm',
                      signal.triggered ? 'text-bear' : 'text-muted-foreground'
                    )}>
                      {signal.score}/{signal.max_score}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="mt-4 pt-4 border-t border-border">
              <ScoreBar score={ipo.total_exit_score} label="Exit Pressure" />
            </div>
          </div>

          {/* Verdict & Action */}
          <div className={cn(
            'rounded-xl border p-6',
            ipo.verdict.includes('SELL') || ipo.verdict === 'URGENT_SELL' 
              ? 'border-bear/30 bg-bear/10' 
              : ipo.verdict === 'WATCH' || ipo.verdict === 'CONSIDER_PARTIAL'
              ? 'border-warning/30 bg-warning/10'
              : 'border-bull/30 bg-bull/10'
          )}>
            <div className="flex items-center gap-3 mb-4">
              <VerdictBadge verdict={ipo.verdict} size="lg" />
            </div>
            
            <p className="text-lg font-medium mb-4">{ipo.action}</p>
            
            <div className="flex items-center gap-2 p-3 rounded-lg bg-bear/20">
              <Shield className="h-5 w-5 text-bear" />
              <span className="font-medium">Stop Loss:</span>
              <span className="font-bold text-bear">Rs. {ipo.stop_loss.toLocaleString()}</span>
            </div>
            
            {/* Reasons */}
            <div className="mt-4">
              <h4 className="text-sm font-medium text-muted-foreground mb-2">Reasons:</h4>
              <ul className="space-y-1">
                {ipo.reasons.map((reason, i) => (
                  <li key={i} className="text-sm flex items-start gap-2">
                    <span className="text-primary mt-0.5">•</span>
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Warnings */}
          {ipo.warnings && ipo.warnings.length > 0 && (
            <WarningBox warnings={ipo.warnings} />
          )}

          {/* Disclaimer */}
          <div className="rounded-lg bg-muted/20 p-4 text-center text-sm text-muted-foreground">
            <AlertTriangle className="h-4 w-4 inline mr-1" />
            IPO timing is inherently risky. This analysis is for educational purposes only.
          </div>
        </div>
      )}
    </div>
  );
}
