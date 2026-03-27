'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPositionAdvice } from '@/lib/api';
import { 
  Scale,
  TrendingUpIcon,
  TrendingDownIcon,
  Shield,
  CircleDollarSign,
  ArrowRightLeft,
  ListChecks,
  AlertTriangle,
  Activity,
  CheckCircle2,
  XCircle,
  MinusCircle,
  BarChart3,
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
  PriceInput,
  DateInput,
  EmptyState,
  InfoBox,
  TargetCard,
  ScanHistoryPanel,
} from '@/components/ui';
import {
  loadScanHistory,
  pushScanHistory,
  removeScanHistoryItem,
  clearScanHistory,
  type ScanHistoryItem,
} from '@/lib/scan-history';

const fmtPrice = (value: number) => `Rs. ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
const fmtPct = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;

export default function HoldOrSellPage() {
  const STORAGE_KEY = 'nepse-hold-sell-state-v1';
  const HISTORY_KEY = 'nepse-hold-sell-history-v1';
  const [symbol, setSymbol] = useState('');
  const [buyPrice, setBuyPrice] = useState<number>(0);
  const [buyDate, setBuyDate] = useState('');
  const [searchParams, setSearchParams] = useState<{ symbol: string; buyPrice: number; buyDate?: string } | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (typeof parsed.symbol === 'string') setSymbol(parsed.symbol);
      if (typeof parsed.buyPrice === 'number') setBuyPrice(parsed.buyPrice);
      if (typeof parsed.buyDate === 'string') setBuyDate(parsed.buyDate);
      if (parsed.searchParams && typeof parsed.searchParams.symbol === 'string') setSearchParams(parsed.searchParams);
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
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ symbol, buyPrice, buyDate, searchParams })
    );
  }, [symbol, buyPrice, buyDate, searchParams, hydrated]);

  const { data, isLoading, isFetching, isError, error } = useQuery({
    queryKey: ['position-advice', searchParams],
    queryFn: () => searchParams ? getPositionAdvice({
      symbol: searchParams.symbol,
      buyPrice: searchParams.buyPrice,
      buyDate: searchParams.buyDate,
    }) : Promise.reject('No params'),
    enabled: !!searchParams,
    retry: 1,
    staleTime: 0,
  });

  const handleSubmit = () => {
    if (symbol.trim() && buyPrice > 0) {
      const clean = symbol.trim().toUpperCase();
      setHistory(
        pushScanHistory(HISTORY_KEY, {
          label: `${clean} @ Rs. ${buyPrice}`,
          value: JSON.stringify({ symbol: clean, buyPrice, buyDate: buyDate || '' }),
        })
      );
      setSearchParams({
        symbol: clean,
        buyPrice,
        buyDate: buyDate || undefined,
      });
    }
  };

  const advice = data?.data;
  const isProfit = (advice?.position.pnl_pct ?? 0) >= 0;
  const rr = advice?.risk_reward;
  const sr = advice?.support_resistance;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Scale className="h-6 w-6 text-primary" />
          Position Advisor
        </h1>
        <p className="text-muted-foreground mt-1">
          Should you HOLD or SELL? Get personalized advice based on your entry price and holding period.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card p-6">
        <div className="grid md:grid-cols-4 gap-4">
          <div className="md:col-span-1">
            <label className="block text-sm text-muted-foreground mb-1">Stock Symbol</label>
            <SymbolInput
              value={symbol}
              onChange={setSymbol}
              placeholder="e.g., NABIL"
            />
          </div>
          
          <div className="md:col-span-1">
            <PriceInput
              value={buyPrice}
              onChange={setBuyPrice}
              label="Your Buy Price"
              placeholder="500"
            />
          </div>
          
          <div className="md:col-span-1">
            <DateInput
              value={buyDate}
              onChange={setBuyDate}
              label="Buy Date (Optional)"
            />
          </div>
          
          <div className="md:col-span-1 flex items-end">
            <button
              onClick={handleSubmit}
              disabled={!symbol.trim() || buyPrice <= 0 || isLoading}
              className="w-full btn-primary"
            >
              {isFetching ? (
                <span className="flex items-center gap-2">
                  <Activity className="h-4 w-4 animate-spin" />
                  Analyzing...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Scale className="h-4 w-4" />
                  Analyze Position
                </span>
              )}
            </button>
          </div>
        </div>
        
        <p className="mt-3 text-xs text-muted-foreground">
          Enter your actual purchase price to get personalized hold or sell advice based on your P/L position.
        </p>
      </div>
      <div className="max-w-md">
        <ScanHistoryPanel
          title="Position Advisor History"
          items={history}
          onSelect={(value) => {
            try {
              const parsed = JSON.parse(value) as { symbol: string; buyPrice: number; buyDate?: string };
              if (!parsed?.symbol || !parsed?.buyPrice) return;
              setSymbol(parsed.symbol);
              setBuyPrice(parsed.buyPrice);
              setBuyDate(parsed.buyDate || '');
              setSearchParams({
                symbol: parsed.symbol,
                buyPrice: parsed.buyPrice,
                buyDate: parsed.buyDate || undefined,
              });
            } catch {
              // ignore invalid history entry
            }
          }}
          onDelete={(id) => setHistory(removeScanHistoryItem(HISTORY_KEY, id))}
          onClear={() => {
            clearScanHistory(HISTORY_KEY);
            setHistory([]);
          }}
        />
      </div>

      {isLoading && <PageSkeleton />}

      {isError && (
        <InfoBox title="Error" variant="error">
          {(error as Error)?.message || 'Failed to analyze position. Please check the symbol and try again.'}
        </InfoBox>
      )}

      {!searchParams && !isLoading && (
        <EmptyState
          icon={Scale}
          title="Enter Your Position Details"
          description="Fill in the stock symbol and your buy price above to get personalized hold/sell advice."
        />
      )}

      {advice && (
        <div className="space-y-6">
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-bold">{advice.symbol}</h2>
                  <VerdictBadge verdict={advice.verdict} size="lg" />
                </div>
                <p className="text-muted-foreground mt-1">
                  {advice.verdict_text || advice.name}
                </p>
              </div>

              <div className="flex items-center gap-3 rounded-lg border border-border/60 bg-muted/10 px-4 py-2">
                <ScoreCircle score={advice.health_score} size="sm" />
                <div>
                  <p className="text-xs text-muted-foreground">Health Score</p>
                  <p className="text-lg font-semibold">
                    {advice.health_score}/100
                    {advice.health_grade ? ` (${advice.health_grade})` : ''}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-6 grid md:grid-cols-4 gap-4">
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Buy Price</p>
                <p className="text-lg font-semibold">{fmtPrice(advice.position.buy_price)}</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Current Price</p>
                <p className="text-lg font-semibold">{fmtPrice(advice.position.current_price)}</p>
              </div>
              <div className={cn(
                'rounded-lg p-4',
                isProfit ? 'bg-bull/10' : 'bg-bear/10'
              )}>
                <p className="text-sm text-muted-foreground">P/L</p>
                <p className={cn(
                  'text-lg font-bold',
                  isProfit ? 'text-bull' : 'text-bear'
                )}>
                  {fmtPct(advice.position.pnl_pct)}
                </p>
                <p className="text-xs">
                  {fmtPrice(advice.position.pnl_amount)}/share
                </p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Holding Period</p>
                <p className="text-lg font-semibold">{advice.position.holding_period}</p>
                <p className="text-xs text-muted-foreground">
                  {advice.position.days_held} calendar days
                  {typeof advice.position.trading_days_held === 'number' ? ` • ${advice.position.trading_days_held} trading days` : ''}
                </p>
              </div>
            </div>

            {advice.position.example_100_shares && (
              <div className="mt-4 rounded-lg border border-border/60 bg-muted/10 p-4">
                <p className="text-sm font-medium flex items-center gap-2">
                  <CircleDollarSign className="h-4 w-4 text-primary" />
                  Position Snapshot (100 shares)
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {fmtPrice(advice.position.example_100_shares.invested)} → {fmtPrice(advice.position.example_100_shares.current_value)} ({fmtPrice(advice.position.example_100_shares.pnl_amount)})
                </p>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader title="Technical Position" />
            <div className="grid md:grid-cols-3 gap-4">
              <div className="rounded-lg bg-muted/20 p-4 space-y-1">
                <p className="text-sm text-muted-foreground">Trend</p>
                <p className="text-lg font-semibold flex items-center gap-2">
                  {advice.technical.trend === 'BULLISH' ? (
                    <TrendingUpIcon className="h-4 w-4 text-bull" />
                  ) : advice.technical.trend === 'BEARISH' ? (
                    <TrendingDownIcon className="h-4 w-4 text-bear" />
                  ) : (
                    <MinusCircle className="h-4 w-4 text-warning" />
                  )}
                  {advice.technical.trend}
                </p>
                <p className="text-xs text-muted-foreground">Strength: {advice.technical.trend_strength ?? 0}%</p>
              </div>

              <div className="rounded-lg bg-muted/20 p-4 space-y-1">
                <p className="text-sm text-muted-foreground">Momentum</p>
                <p className="text-lg font-semibold">{advice.technical.momentum}</p>
                <p className="text-xs text-muted-foreground">RSI: {advice.technical.rsi.toFixed(0)}</p>
              </div>

              <div className="rounded-lg bg-muted/20 p-4 space-y-1">
                <p className="text-sm text-muted-foreground">EMA Position</p>
                <p className="text-lg font-semibold">
                  {advice.technical.ema_above_count ?? 0}/{advice.technical.ema_total ?? 4} above
                </p>
                <p className="text-xs text-muted-foreground">{advice.technical.ema_alignment || 'N/A'}</p>
              </div>
            </div>

            <div className="mt-4 grid md:grid-cols-3 gap-4">
              <div className="rounded-lg bg-bull/10 p-4">
                <p className="text-sm text-muted-foreground">Support</p>
                <p className="text-lg font-semibold text-bull">{fmtPrice(advice.technical.support)}</p>
              </div>
              <div className="rounded-lg bg-bear/10 p-4">
                <p className="text-sm text-muted-foreground">Resistance</p>
                <p className="text-lg font-semibold text-bear">{fmtPrice(advice.technical.resistance)}</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Volume Trend</p>
                <p className="text-lg font-semibold">{advice.technical.volume_trend || 'NORMAL'}</p>
              </div>
            </div>
          </div>

          {sr && (
            <div className="rounded-xl border border-border bg-card p-5">
              <SectionHeader title="Support & Resistance Context" />
              <div className="grid md:grid-cols-2 gap-4">
                <div className="rounded-lg bg-muted/20 p-4">
                  <p className="text-sm text-muted-foreground">Nearest Support</p>
                  <p className="text-lg font-semibold">{fmtPrice(sr.immediate_support)}</p>
                  <p className="text-xs text-muted-foreground">{sr.support_distance_pct.toFixed(1)}% below current</p>
                </div>
                <div className="rounded-lg bg-muted/20 p-4">
                  <p className="text-sm text-muted-foreground">Nearest Resistance</p>
                  <p className="text-lg font-semibold">{fmtPrice(sr.immediate_resistance)}</p>
                  <p className="text-xs text-muted-foreground">{sr.resistance_distance_pct.toFixed(1)}% above current</p>
                </div>
              </div>

              <div className="mt-3 rounded-lg border border-border/60 bg-muted/10 p-3 text-sm">
                {sr.entry_vs_support === 'below' && (
                  <p className="flex items-start gap-2 text-bull"><CheckCircle2 className="h-4 w-4 mt-0.5" />Your entry is below support, providing downside buffer.</p>
                )}
                {sr.entry_vs_support === 'above' && (
                  <p className="flex items-start gap-2 text-warning"><AlertTriangle className="h-4 w-4 mt-0.5" />You bought at a higher level than support. If price pulls back, it may fall toward support first, so keep your stop loss disciplined.</p>
                )}
                {sr.entry_vs_support !== 'below' && sr.entry_vs_support !== 'above' && (
                  <p className="flex items-start gap-2 text-muted-foreground"><MinusCircle className="h-4 w-4 mt-0.5" />Entry and support context is neutral.</p>
                )}
              </div>
            </div>
          )}

          {rr && (
            <div className="rounded-xl border border-border bg-card p-5">
              <SectionHeader title="Risk / Reward From Current Price" />
              <div className="grid md:grid-cols-4 gap-4">
                <div className="rounded-lg bg-muted/20 p-4">
                  <p className="text-sm text-muted-foreground">Risk to Support</p>
                  <p className="text-lg font-semibold text-bear">-{rr.risk_to_support_pct.toFixed(1)}%</p>
                </div>
                <div className="rounded-lg bg-muted/20 p-4">
                  <p className="text-sm text-muted-foreground">Reward to Resistance</p>
                  <p className="text-lg font-semibold text-bull">+{rr.reward_to_resistance_pct.toFixed(1)}%</p>
                </div>
                <div className="rounded-lg bg-muted/20 p-4">
                  <p className="text-sm text-muted-foreground">R:R Ratio</p>
                  <p className="text-lg font-semibold">1:{rr.ratio.toFixed(1)}</p>
                </div>
                <div className={cn('rounded-lg p-4', rr.favorable ? 'bg-bull/10' : 'bg-warning/10')}>
                  <p className="text-sm text-muted-foreground">Assessment</p>
                  <p className={cn('text-lg font-semibold', rr.favorable ? 'text-bull' : 'text-warning')}>
                    {rr.favorable ? 'Favorable' : 'Unfavorable'}
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader title="Health Score Breakdown" />
            <div className="space-y-3">
              {advice.health_breakdown.map((factor, i) => (
                <div key={i}>
                  <ScoreBar 
                    score={factor.score} 
                    maxScore={factor.max_score} 
                    label={`${factor.factor} (${factor.weight_pct}%)`}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader title="Your Targets" />
            <div className="grid md:grid-cols-3 gap-4">
              {advice.targets.map((target, i) => (
                <TargetCard
                  key={i}
                  level={target.level}
                  price={target.price}
                  gainPct={target.gain_pct}
                  currentPrice={advice.position.current_price}
                />
              ))}
            </div>
          </div>

          <div className={cn(
            'rounded-xl border p-6',
            advice.verdict.includes('EXIT') || advice.verdict === 'URGENT_EXIT' 
              ? 'border-bear/30 bg-bear/10' 
              : advice.verdict === 'HOLD_CAUTIOUSLY' || advice.verdict === 'BOOK_PARTIAL'
              ? 'border-warning/30 bg-warning/10'
              : 'border-bull/30 bg-bull/10'
          )}>
            <div className="flex items-center gap-3 mb-4">
              <VerdictBadge verdict={advice.verdict} size="lg" />
            </div>

            <div className="mb-4">
              <h4 className="text-sm font-medium text-muted-foreground mb-2">Recommended Actions:</h4>
              <ol className="space-y-2">
                {advice.actions.map((action, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <ArrowRightLeft className="h-4 w-4 mt-0.5 text-primary" />
                    <span>{action}</span>
                  </li>
                ))}
              </ol>
            </div>

            <div className="flex items-center gap-2 p-3 rounded-lg bg-bear/20 mb-4">
              <Shield className="h-5 w-5 text-bear" />
              <span className="font-medium">Stop Loss:</span>
              <span className="font-bold text-bear">{fmtPrice(advice.stop_loss)}</span>
              {advice.trade_plan && (
                <span className="text-xs text-muted-foreground">
                  ({advice.trade_plan.stop_loss_pct_from_current.toFixed(1)}% from current)
                </span>
              )}
            </div>

            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-2">Exit Immediately If:</h4>
              <ul className="space-y-1">
                {advice.exit_triggers.map((trigger, i) => (
                  <li key={i} className="text-sm flex items-start gap-2 text-bear">
                    <XCircle className="h-4 w-4 mt-0.5" />
                    <span>{trigger}</span>
                  </li>
                ))}
              </ul>
            </div>

            {advice.hold_checklist && advice.hold_checklist.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-medium text-muted-foreground mb-2">Weekly Check-in (Continue Holding If):</h4>
                <ul className="space-y-1">
                  {advice.hold_checklist.map((check, i) => (
                    <li key={i} className="text-sm flex items-start gap-2 text-bull">
                      <CheckCircle2 className="h-4 w-4 mt-0.5" />
                      <span>{check}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {advice.warnings && advice.warnings.length > 0 && (
            <WarningBox warnings={advice.warnings} />
          )}

          <div className="rounded-lg bg-muted/20 p-4 text-center text-sm text-muted-foreground">
            <AlertTriangle className="h-4 w-4 inline mr-1" />
            This is algorithmic analysis for educational purposes. Always do your own research.
          </div>
        </div>
      )}
    </div>
  );
}
