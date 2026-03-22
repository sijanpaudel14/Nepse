'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getMarketRegime, getPortfolioStatus } from '@/lib/api';
import { 
  TrendingUp, 
  TrendingDown, 
  Activity,
  Wallet,
  Target,
  AlertTriangle,
  BarChart3,
  Zap,
  Radar,
  Search,
  RefreshCw,
  Loader2,
  WifiOff,
  CheckCircle,
  XCircle,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';
import { cn, formatCurrency, formatPercent, getValueColor } from '@/lib/utils';
import Link from 'next/link';

// Regime Icon Component
function RegimeIcon({ regime, className }: { regime: string; className?: string }) {
  switch (regime) {
    case 'BULL':
      return <TrendingUp className={cn('text-bull', className)} />;
    case 'BEAR':
      return <TrendingDown className={cn('text-bear', className)} />;
    case 'PANIC':
      return <AlertTriangle className={cn('text-warning', className)} />;
    default:
      return <Activity className={cn('text-muted-foreground', className)} />;
  }
}

// Metric Card Component
function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendValue,
  variant = 'default',
  isLoading = false,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: any;
  trend?: 'up' | 'down' | 'neutral';
  trendValue?: string;
  variant?: 'default' | 'bull' | 'bear' | 'warning';
  isLoading?: boolean;
}) {
  const variantStyles = {
    default: 'border-border bg-card',
    bull: 'border-bull/30 bg-bull-muted/20',
    bear: 'border-bear/30 bg-bear-muted/20',
    warning: 'border-warning/30 bg-neutral-muted/20',
  };

  const iconStyles = {
    default: 'bg-muted/30 text-muted-foreground',
    bull: 'bg-bull-muted text-bull-text',
    bear: 'bg-bear-muted text-bear-text',
    warning: 'bg-neutral-muted text-neutral-text',
  };

  return (
    <div className={cn(
      'card card-hover rounded-xl border p-6 transition-all duration-200',
      variantStyles[variant]
    )}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="metric-label">{title}</p>
          {isLoading ? (
            <div className="mt-2 h-8 w-24 skeleton" />
          ) : (
            <p className="mt-2 metric-value text-foreground">{value}</p>
          )}
          {subtitle && (
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          )}
          {trendValue && !isLoading && (
            <div className={cn(
              'mt-2 flex items-center gap-1 text-sm font-semibold',
              trend === 'up' ? 'text-bull-text' : trend === 'down' ? 'text-bear-text' : 'text-neutral-text'
            )}>
              {trend === 'up' ? <ArrowUpRight className="h-4 w-4" /> : 
               trend === 'down' ? <ArrowDownRight className="h-4 w-4" /> : null}
              {trendValue}
            </div>
          )}
        </div>
        <div className={cn('rounded-xl p-3', iconStyles[variant])}>
          {isLoading ? (
            <Loader2 className="h-6 w-6 animate-spin" />
          ) : (
            <Icon className="h-6 w-6" />
          )}
        </div>
      </div>
    </div>
  );
}

// Quick Action Button
function QuickAction({
  href,
  icon: Icon,
  title,
  description,
}: {
  href: string;
  icon: any;
  title: string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="group card card-interactive flex items-center gap-4 rounded-xl border border-border p-4"
    >
      <div className="rounded-xl bg-primary-muted p-3 text-primary transition-colors group-hover:bg-primary/20">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </Link>
  );
}

// Error State Component
function ErrorState({ 
  message, 
  onRetry 
}: { 
  message: string; 
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-bear/30 bg-bear-muted/20 py-12 px-6">
      <div className="rounded-full bg-bear-muted p-4">
        <WifiOff className="h-8 w-8 text-bear-text" />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-foreground">Connection Error</h3>
      <p className="mt-2 text-sm text-muted-foreground text-center max-w-md">{message}</p>
      <button
        onClick={onRetry}
        className="btn-primary mt-6"
      >
        <RefreshCw className="h-4 w-4" />
        Retry Connection
      </button>
      <p className="mt-4 text-xs text-muted-foreground">
        Make sure the API server is running on port 8000
      </p>
    </div>
  );
}

export default function DashboardPage() {
  const queryClient = useQueryClient();

  // Fetch market regime
  const { 
    data: regime, 
    isLoading: regimeLoading, 
    isError: regimeError,
    error: regimeErrorObj,
    refetch: refetchRegime,
    isFetching: regimeFetching,
  } = useQuery({
    queryKey: ['market-regime'],
    queryFn: () => getMarketRegime(),
    // Only refetch every 5 minutes, and only if query succeeded before
    refetchInterval: (query) => query.state.data ? 5 * 60 * 1000 : false,
    retry: 1,
    retryDelay: 1000,
  });

  // Fetch portfolio status
  const { 
    data: portfolio, 
    isLoading: portfolioLoading,
    isError: portfolioError,
    refetch: refetchPortfolio,
    isFetching: portfolioFetching,
  } = useQuery({
    queryKey: ['portfolio'],
    queryFn: () => getPortfolioStatus(),
    // Only refetch every 5 minutes, and only if query succeeded before
    refetchInterval: (query) => query.state.data ? 5 * 60 * 1000 : false,
    retry: 1,
    retryDelay: 1000,
  });

  // Loading = initial load only, fetching = any load including refresh
  const isInitialLoading = regimeLoading || portfolioLoading;
  const isFetching = regimeFetching || portfolioFetching;
  const hasError = regimeError || portfolioError;

  const marketRegime = regime?.regime || 'OFFLINE';
  const regimeVariant = 
    marketRegime === 'BULL' ? 'bull' : 
    marketRegime === 'BEAR' ? 'bear' : 
    marketRegime === 'PANIC' ? 'warning' : 'default';

  const totalUnrealizedPnl = portfolio?.positions?.reduce(
    (sum, pos) => sum + pos.unrealized_pnl, 
    0
  ) || 0;

  const handleRetry = () => {
    refetchRegime();
    refetchPortfolio();
  };

  const handleStopLoading = () => {
    queryClient.cancelQueries({ queryKey: ['market-regime'] });
    queryClient.cancelQueries({ queryKey: ['portfolio'] });
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            NEPSE AI Trading Terminal • {new Date().toLocaleDateString('en-US', { 
              weekday: 'long', 
              year: 'numeric', 
              month: 'long', 
              day: 'numeric' 
            })}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Refresh Button */}
          <button
            onClick={handleRetry}
            disabled={isFetching}
            className="rounded-lg border border-border bg-card p-2 text-muted-foreground hover:bg-card-hover hover:text-foreground disabled:opacity-50"
          >
            <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
          </button>
          <button
            onClick={handleStopLoading}
            disabled={!isFetching}
            className={cn(
              'rounded-lg border p-2 transition-colors',
              isFetching
                ? 'border-bear/40 bg-bear/10 text-bear hover:bg-bear/20'
                : 'cursor-not-allowed border-border bg-card text-muted-foreground opacity-50'
            )}
          >
            <XCircle className="h-4 w-4" />
          </button>
          
          {/* Market Status Badge */}
          <div className="flex items-center gap-2 rounded-full bg-card px-4 py-2 text-sm border border-border">
            <div className={cn(
              'h-2 w-2 rounded-full',
              regimeVariant === 'bull' ? 'bg-bull animate-pulse' :
              regimeVariant === 'bear' ? 'bg-bear animate-pulse' :
              hasError ? 'bg-bear' :
              isFetching ? 'bg-warning animate-pulse' :
              'bg-muted'
            )} />
            <span className="font-medium flex items-center gap-1.5">
              Market: 
              {isFetching && !hasError ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RegimeIcon regime={marketRegime} className="h-4 w-4" />
              )}
              {hasError ? 'OFFLINE' : marketRegime}
            </span>
          </div>
        </div>
      </div>

      {/* Error State */}
      {hasError && !isInitialLoading && (
        <ErrorState 
          message="Could not connect to the trading API. Make sure the backend is running."
          onRetry={handleRetry}
        />
      )}

      {/* Metric Cards Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Market Regime"
          value={hasError ? 'OFFLINE' : marketRegime}
          subtitle={regime?.reason?.slice(0, 50) || (isInitialLoading ? 'Connecting...' : hasError ? 'API not available' : 'Offline')}
          icon={hasError ? WifiOff : regimeVariant === 'bull' ? TrendingUp : regimeVariant === 'bear' ? TrendingDown : Activity}
          variant={hasError ? 'bear' : regimeVariant}
          isLoading={regimeLoading}
        />
        
        <MetricCard
          title="NEPSE Index"
          value={regime?.nepse_index?.toLocaleString() || '---'}
          subtitle={`EMA50: ${regime?.ema50?.toLocaleString() || '---'}`}
          icon={BarChart3}
          trend={regime?.nepse_index && regime?.ema50 
            ? (regime.nepse_index > regime.ema50 ? 'up' : 'down')
            : 'neutral'
          }
          trendValue={regime?.nepse_index && regime?.ema50
            ? `${((regime.nepse_index / regime.ema50 - 1) * 100).toFixed(2)}% vs EMA50`
            : undefined
          }
          isLoading={regimeLoading}
        />

        <MetricCard
          title="Open Positions"
          value={portfolio?.stats?.open_positions || 0}
          subtitle={`${portfolio?.stats?.closed_positions || 0} closed trades`}
          icon={Wallet}
          variant={totalUnrealizedPnl > 0 ? 'bull' : totalUnrealizedPnl < 0 ? 'bear' : 'default'}
          trend={totalUnrealizedPnl > 0 ? 'up' : totalUnrealizedPnl < 0 ? 'down' : 'neutral'}
          trendValue={totalUnrealizedPnl !== 0 ? formatCurrency(totalUnrealizedPnl) : undefined}
          isLoading={portfolioLoading}
        />

        <MetricCard
          title="Win Rate"
          value={`${portfolio?.stats?.win_rate || 0}%`}
          subtitle={`${portfolio?.stats?.wins || 0}W / ${portfolio?.stats?.losses || 0}L`}
          icon={Target}
          variant={(portfolio?.stats?.win_rate || 0) >= 60 ? 'bull' : 
                   (portfolio?.stats?.win_rate || 0) >= 40 ? 'default' : 'bear'}
          isLoading={portfolioLoading}
        />
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="mb-4 text-lg font-semibold">Quick Actions</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <QuickAction
            href="/scanner"
            icon={Zap}
            title="Run AI Scan"
            description="Find today's top opportunities"
          />
          <QuickAction
            href="/stealth"
            icon={Radar}
            title="Stealth Radar"
            description="Detect smart money accumulation"
          />
          <QuickAction
            href="/portfolio"
            icon={Wallet}
            title="View Portfolio"
            description="Check open positions"
          />
          <QuickAction
            href="/analyze"
            icon={Search}
            title="Analyze Stock"
            description="Deep dive into any stock"
          />
        </div>
      </div>

      {/* Open Positions Table (if any) */}
      {portfolio?.positions && portfolio.positions.length > 0 && (
        <div className="rounded-xl border border-border bg-card">
          <div className="border-b border-border p-4">
            <h2 className="text-lg font-semibold">Open Positions</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-border bg-card-hover">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">Symbol</th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">Entry</th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">Current</th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">P&L</th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">Target</th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">Stop</th>
                  <th className="px-4 py-3 text-center text-sm font-medium text-muted-foreground">Days</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.positions.map((pos) => (
                  <tr key={pos.id} className="table-row-hover border-b border-border last:border-0">
                    <td className="px-4 py-3">
                      <Link 
                        href={`/analyze?symbol=${pos.symbol}`}
                        className="font-mono font-semibold text-primary hover:underline"
                      >
                        {pos.symbol}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">{formatCurrency(pos.entry_price)}</td>
                    <td className="px-4 py-3 text-right font-mono">{formatCurrency(pos.current_price)}</td>
                    <td className={cn(
                      'px-4 py-3 text-right font-mono font-semibold flex items-center justify-end gap-1',
                      getValueColor(pos.unrealized_pnl)
                    )}>
                      {pos.unrealized_pnl > 0 ? (
                        <CheckCircle className="h-3.5 w-3.5" />
                      ) : pos.unrealized_pnl < 0 ? (
                        <XCircle className="h-3.5 w-3.5" />
                      ) : null}
                      {formatCurrency(pos.unrealized_pnl)} ({formatPercent(pos.unrealized_pnl_pct)})
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-bull">{formatCurrency(pos.target_price)}</td>
                    <td className="px-4 py-3 text-right font-mono text-bear">{formatCurrency(pos.stop_loss)}</td>
                    <td className="px-4 py-3 text-center font-mono">{pos.days_held}d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Footer Info */}
      <div className="rounded-lg border border-border bg-card-hover p-4 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
        <AlertTriangle className="h-4 w-4" />
        <p>This is algorithmic analysis for educational purposes only. Not financial advice. Always do your own research.</p>
      </div>
    </div>
  );
}
