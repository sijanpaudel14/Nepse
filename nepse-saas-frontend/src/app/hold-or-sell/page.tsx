'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPositionAdvice, type PositionAdvisorResponse } from '@/lib/api';
import { 
  Scale, 
  TrendingUp,
  TrendingDown,
  Shield,
  Target,
  AlertTriangle,
  Calendar,
  Activity,
  Zap,
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
  PriceChange,
  TargetCard,
} from '@/components/ui';

export default function HoldOrSellPage() {
  const [symbol, setSymbol] = useState('');
  const [buyPrice, setBuyPrice] = useState<number>(0);
  const [buyDate, setBuyDate] = useState('');
  const [searchParams, setSearchParams] = useState<{ symbol: string; buyPrice: number; buyDate?: string } | null>(null);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['position-advice', searchParams],
    queryFn: () => searchParams ? getPositionAdvice({
      symbol: searchParams.symbol,
      buyPrice: searchParams.buyPrice,
      buyDate: searchParams.buyDate,
    }) : Promise.reject('No params'),
    enabled: !!searchParams,
    retry: 1,
  });

  const handleSubmit = () => {
    if (symbol.trim() && buyPrice > 0) {
      setSearchParams({
        symbol: symbol.trim().toUpperCase(),
        buyPrice,
        buyDate: buyDate || undefined,
      });
    }
  };

  const advice = data?.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Scale className="h-6 w-6 text-primary" />
          Position Advisor
        </h1>
        <p className="text-muted-foreground mt-1">
          Should you HOLD or SELL? Get personalized advice based on your entry price and holding period.
        </p>
      </div>

      {/* Input Form */}
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
              {isLoading ? (
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
          💡 Enter your actual purchase price to get personalized hold/sell advice based on your P/L position.
        </p>
      </div>

      {/* Results */}
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
          {/* Position Summary Card */}
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-bold">{advice.symbol}</h2>
                  <VerdictBadge verdict={advice.verdict} size="lg" />
                </div>
                <p className="text-muted-foreground mt-1">{advice.name}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Health Score</p>
                <ScoreCircle score={advice.health_score} size="md" />
              </div>
            </div>

            {/* P/L Display */}
            <div className="mt-6 grid md:grid-cols-4 gap-4">
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Buy Price</p>
                <p className="text-lg font-semibold">Rs. {advice.position.buy_price.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Current Price</p>
                <p className="text-lg font-semibold">Rs. {advice.position.current_price.toLocaleString()}</p>
              </div>
              <div className={cn(
                'rounded-lg p-4',
                advice.position.pnl_pct >= 0 ? 'bg-bull/10' : 'bg-bear/10'
              )}>
                <p className="text-sm text-muted-foreground">P/L</p>
                <p className={cn(
                  'text-lg font-bold',
                  advice.position.pnl_pct >= 0 ? 'text-bull' : 'text-bear'
                )}>
                  {advice.position.pnl_pct >= 0 ? '+' : ''}{advice.position.pnl_pct.toFixed(1)}%
                </p>
                <p className="text-xs">
                  Rs. {advice.position.pnl_amount >= 0 ? '+' : ''}{advice.position.pnl_amount.toLocaleString()}/share
                </p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Holding Period</p>
                <p className="text-lg font-semibold">{advice.position.holding_period}</p>
                <p className="text-xs text-muted-foreground">{advice.position.days_held} days</p>
              </div>
            </div>
          </div>

          {/* Technical Position */}
          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader title="📈 Technical Position" />
            <div className="grid md:grid-cols-5 gap-4">
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Trend</p>
                <p className="text-lg font-semibold">{advice.technical.trend}</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">Momentum</p>
                <p className="text-lg font-semibold">{advice.technical.momentum}</p>
              </div>
              <div className="rounded-lg bg-muted/20 p-4">
                <p className="text-sm text-muted-foreground">RSI</p>
                <p className="text-lg font-semibold">{advice.technical.rsi.toFixed(0)}</p>
              </div>
              <div className="rounded-lg bg-bull/10 p-4">
                <p className="text-sm text-muted-foreground">Support</p>
                <p className="text-lg font-semibold text-bull">Rs. {advice.technical.support.toLocaleString()}</p>
              </div>
              <div className="rounded-lg bg-bear/10 p-4">
                <p className="text-sm text-muted-foreground">Resistance</p>
                <p className="text-lg font-semibold text-bear">Rs. {advice.technical.resistance.toLocaleString()}</p>
              </div>
            </div>
          </div>

          {/* Health Score Breakdown */}
          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader title="🧮 Health Score Breakdown" />
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

          {/* Price Targets */}
          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader title="🎯 Your Targets" />
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

          {/* Verdict & Actions */}
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
              <span className="text-2xl">{advice.verdict_emoji}</span>
            </div>

            {/* Recommended Actions */}
            <div className="mb-4">
              <h4 className="text-sm font-medium text-muted-foreground mb-2">💡 Recommended Actions:</h4>
              <ol className="space-y-2">
                {advice.actions.map((action, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span className="font-bold text-primary">{i + 1}.</span>
                    {action}
                  </li>
                ))}
              </ol>
            </div>

            {/* Stop Loss */}
            <div className="flex items-center gap-2 p-3 rounded-lg bg-bear/20 mb-4">
              <Shield className="h-5 w-5 text-bear" />
              <span className="font-medium">Stop Loss:</span>
              <span className="font-bold text-bear">Rs. {advice.stop_loss.toLocaleString()}</span>
            </div>

            {/* Exit Triggers */}
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-2">🛑 Exit Immediately If:</h4>
              <ul className="space-y-1">
                {advice.exit_triggers.map((trigger, i) => (
                  <li key={i} className="text-sm flex items-start gap-2 text-bear">
                    <span>•</span>
                    {trigger}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Warnings */}
          {advice.warnings && advice.warnings.length > 0 && (
            <WarningBox warnings={advice.warnings} />
          )}

          {/* Disclaimer */}
          <div className="rounded-lg bg-muted/20 p-4 text-center text-sm text-muted-foreground">
            <AlertTriangle className="h-4 w-4 inline mr-1" />
            This is algorithmic analysis for educational purposes. Always do your own research.
          </div>
        </div>
      )}
    </div>
  );
}
