'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getSignal, type SignalResponse } from '@/lib/api';
import { 
  Zap, 
  TrendingUp,
  TrendingDown,
  Clock,
  Target,
  Shield,
  AlertTriangle,
  ArrowRight,
  Calendar,
  CheckCircle,
  Percent,
  Activity,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  PageSkeleton,
  VerdictBadge,
  ScoreCircle,
  PriceLevel,
  TargetCard,
  WarningBox,
  SectionHeader,
  SymbolInput,
  EmptyState,
  InfoBox,
  ScanHistoryPanel,
} from '@/components/ui';
import {
  loadScanHistory,
  pushScanHistory,
  removeScanHistoryItem,
  clearScanHistory,
  type ScanHistoryItem,
} from '@/lib/scan-history';

export default function SignalPage() {
  const STORAGE_KEY = 'nepse-signal-state-v1';
  const HISTORY_KEY = 'nepse-signal-history-v1';
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
    queryKey: ['signal', searchSymbol],
    queryFn: () => getSignal({ symbol: searchSymbol }),
    enabled: !!searchSymbol,
    retry: 1,
    staleTime: 0,
  });

  const handleSubmit = () => {
    const clean = symbol.trim().toUpperCase();
    if (!clean) return;
    setHistory(
      pushScanHistory(HISTORY_KEY, {
        label: clean,
        value: clean,
      })
    );
    if (clean === searchSymbol) {
      refetch();
    } else {
      setSearchSymbol(clean);
    }
  };

  const signal = data?.data;

  const normalizeCondition = (raw: string) => {
    const text = (raw || '').replace(/[_-]+/g, ' ').trim();
    const mappings: Array<[RegExp, string]> = [
      [/golden\s*cross.*ema9.*ema21/i, 'Golden cross confirmed (EMA 9 above EMA 21)'],
      [/pullback\s*to\s*support.*ema20/i, 'Healthy pullback toward EMA20 support'],
      [/price\s*near\s*support/i, 'Price trading near support zone'],
      [/price\s*at\s*resistance/i, 'Price near resistance zone (wait for breakout confirmation)'],
      [/uptrend.*markup/i, 'Uptrend phase remains intact'],
      [/rsi.*healthy/i, 'RSI is in a healthy momentum range'],
    ];
    for (const [pattern, replacement] of mappings) {
      if (pattern.test(text)) return replacement;
    }
    return text.charAt(0).toUpperCase() + text.slice(1);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Zap className="h-6 w-6 text-primary" />
          Trading Signal Generator
        </h1>
        <p className="text-muted-foreground mt-1">
          Get precise entry/exit timing with confidence scores and price targets
        </p>
      </div>

      {/* Symbol Input */}
      <div className="max-w-md">
        <SymbolInput
          value={symbol}
          onChange={setSymbol}
          onSubmit={handleSubmit}
          placeholder="Enter stock symbol (e.g., NABIL)"
          isLoading={isFetching}
        />
      </div>
      <div className="max-w-md">
        <ScanHistoryPanel
          title="Signal History"
          items={history}
          onSelect={(value) => {
            setSymbol(value);
            if (value === searchSymbol) {
              refetch();
            } else {
              setSearchSymbol(value);
            }
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
          {(error as Error)?.message || 'Failed to generate signal. Please try again.'}
        </InfoBox>
      )}

      {!searchSymbol && !isLoading && (
        <EmptyState
          icon={Zap}
          title="Enter a Stock Symbol"
          description="Type a stock symbol above and press Enter to generate a trading signal with entry/exit timing."
        />
      )}

      {signal && (
        <div className="space-y-6">
          {/* Main Signal Card */}
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-bold">{signal.symbol}</h2>
                  <VerdictBadge verdict={signal.signal} size="lg" />
                </div>
                <p className="text-muted-foreground mt-1">{signal.name} • {signal.sector}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Current Price</p>
                <p className="text-2xl font-bold">Rs. {signal.current_price.toLocaleString()}</p>
              </div>
            </div>

            {/* Confidence & Trend */}
            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="rounded-lg bg-muted/20 p-4 flex flex-col items-center justify-center">
                <ScoreCircle score={signal.confidence} size="md" />
                <p className="mt-2 text-xs font-medium text-muted-foreground">Confidence</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Trend Phase</p>
                <p className="text-lg font-semibold mt-1">{signal.trend_phase}</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Hold Duration</p>
                <p className="text-lg font-semibold mt-1">{signal.hold.duration_days} days</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Risk/Reward</p>
                <p className="text-lg font-semibold mt-1">1:{signal.risk.risk_reward.toFixed(1)}</p>
              </div>
            </div>
          </div>

          {/* Three-Phase Plan */}
          <div className="grid md:grid-cols-3 gap-4">
            {/* Phase 1: Entry */}
            <div className="rounded-xl border border-primary/30 bg-primary/5 p-5">
              <div className="flex items-center gap-2 text-primary font-semibold mb-4">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/20 text-sm font-semibold leading-none">
                  1
                </div>
                <span>ENTRY (When to Buy)</span>
              </div>
              
              <div className="space-y-3">
                <div>
                  <p className="text-sm text-muted-foreground">Target Entry Zone</p>
                  <p className="text-lg font-semibold">
                    Rs. {signal.entry.target_zone_low.toLocaleString()} - Rs. {signal.entry.target_zone_high.toLocaleString()}
                  </p>
                </div>
                
                <div>
                  <p className="text-sm text-muted-foreground">Price Gap</p>
                  <p className="font-medium">{signal.entry.price_gap_pct.toFixed(1)}% from zone</p>
                </div>
                
                <div>
                  <p className="text-sm text-muted-foreground">Entry Conditions</p>
                  <ul className="mt-1 space-y-1">
                    {signal.entry.conditions.map((condition, i) => (
                      <li key={i} className="text-sm flex items-start gap-2">
                        <CheckCircle className="h-4 w-4 text-primary" />
                        {normalizeCondition(condition)}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* Phase 2: Hold */}
            <div className="rounded-xl border border-warning/30 bg-warning/5 p-5">
              <div className="flex items-center gap-2 text-warning font-semibold mb-4">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-warning/20 text-sm font-semibold leading-none">
                  2
                </div>
                <span>HOLD (How Long)</span>
              </div>
              
              <div className="space-y-3">
                <div>
                  <p className="text-sm text-muted-foreground">Duration</p>
                  <p className="text-lg font-semibold">~{signal.hold.duration_days} trading days</p>
                </div>
                
                <div className="rounded-lg border border-bear/30 bg-bear/10 p-3">
                  <div className="flex items-center gap-2 text-bear text-sm font-medium">
                    <Shield className="h-4 w-4" />
                    Stop Loss
                  </div>
                  <p className="text-lg font-bold text-bear">
                    Rs. {signal.hold.stop_loss.toLocaleString()}
                  </p>
                  <p className="text-xs text-bear/80">
                    {signal.hold.stop_loss_pct.toFixed(1)}% max loss
                  </p>
                </div>
                
                <div>
                  <p className="text-sm text-muted-foreground">Trail Stop</p>
                  <p className="font-medium">{signal.hold.trail_stop_pct.toFixed(1)}% below peak</p>
                </div>
              </div>
            </div>

            {/* Phase 3: Exit */}
            <div className="rounded-xl border border-bull/30 bg-bull/5 p-5">
              <div className="flex items-center gap-2 text-bull font-semibold mb-4">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-bull/20 text-sm font-semibold leading-none">
                  3
                </div>
                <span>EXIT (When to Sell)</span>
              </div>
              
              <div className="space-y-2">
                {signal.targets.map((target, i) => (
                  <div key={i} className="rounded-lg bg-bull/10 p-3">
                    <div className="flex justify-between items-center">
                      <span className="font-medium text-bull">{target.level}</span>
                      <span className="text-xs text-muted-foreground">{target.probability}% likely</span>
                    </div>
                    <p className="text-lg font-bold mt-1">Rs. {target.price.toLocaleString()}</p>
                    <p className="text-sm text-bull">+{target.gain_pct.toFixed(1)}%</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Risk Management */}
          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader title="Risk Management" />
            
            <div className="grid md:grid-cols-4 gap-4">
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Risk/Reward</p>
                <p className="text-xl font-bold mt-1">1:{signal.risk.risk_reward.toFixed(1)}</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Position Size</p>
                <p className="text-xl font-bold mt-1">{signal.risk.position_size_pct.toFixed(1)}%</p>
                <p className="text-xs text-muted-foreground">of portfolio</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Trailing Stop</p>
                <p className="text-xl font-bold mt-1">{signal.risk.trailing_stop_pct.toFixed(1)}%</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Hold Duration</p>
                <p className="text-xl font-bold mt-1">~{signal.hold.duration_days}d</p>
              </div>
            </div>
          </div>

          {/* Recommendation */}
          <div className="rounded-xl border border-primary/30 bg-primary/5 p-5">
            <SectionHeader title="Recommendation" />
            <p className="text-lg">{signal.recommendation}</p>
          </div>

          {/* Warnings */}
          {signal.warnings && signal.warnings.length > 0 && (
            <WarningBox warnings={signal.warnings} />
          )}

          {/* Disclaimer */}
          <div className="rounded-lg bg-muted/20 p-4 text-center text-sm text-muted-foreground">
            <AlertTriangle className="h-4 w-4 inline mr-1" />
            This is algorithmic analysis for educational purposes. Always do your own research before trading.
          </div>
        </div>
      )}
    </div>
  );
}
