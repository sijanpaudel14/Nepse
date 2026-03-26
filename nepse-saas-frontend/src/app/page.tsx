'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getMarketRegime, getPortfolioStatus } from '@/lib/api';
import { motion } from 'framer-motion';
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
  Sparkles,
} from 'lucide-react';
import { cn, formatCurrency, formatPercent, getValueColor } from '@/lib/utils';
import Link from 'next/link';

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.4, ease: 'easeOut' as const },
  },
};

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

// Metric Card Component - Enhanced
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
    default: 'border-border/60',
    bull: 'border-bull/30',
    bear: 'border-bear/30',
    warning: 'border-warning/30',
  };
  
  const glowStyles = {
    default: '',
    bull: 'hover:shadow-glow-sm',
    bear: 'hover:shadow-glow-red',
    warning: '',
  };

  const iconStyles = {
    default: 'bg-muted/20 text-muted-foreground border-muted/30',
    bull: 'bg-bull/10 text-bull border-bull/20',
    bear: 'bg-bear/10 text-bear border-bear/20',
    warning: 'bg-warning/10 text-warning border-warning/20',
  };

  return (
    <motion.div
      className={cn(
        'card card-hover card-shine rounded-xl border p-6 transition-all duration-300',
        variantStyles[variant],
        glowStyles[variant]
      )}
      whileHover={{ y: -2, transition: { duration: 0.2 } }}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="metric-label text-xs uppercase tracking-wider">{title}</p>
          {isLoading ? (
            <div className="mt-3 h-8 w-28 skeleton rounded-md" />
          ) : (
            <p className="mt-3 metric-value text-foreground">{value}</p>
          )}
          {subtitle && (
            <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>
          )}
          {trendValue && !isLoading && (
            <div className={cn(
              'mt-3 flex items-center gap-1.5 text-sm font-semibold',
              trend === 'up' ? 'text-bull' : trend === 'down' ? 'text-bear' : 'text-warning'
            )}>
              {trend === 'up' ? <ArrowUpRight className="h-4 w-4" /> : 
               trend === 'down' ? <ArrowDownRight className="h-4 w-4" /> : null}
              {trendValue}
            </div>
          )}
        </div>
        <div className={cn(
          'rounded-xl p-3 border transition-all duration-300',
          iconStyles[variant]
        )}>
          {isLoading ? (
            <Loader2 className="h-6 w-6 animate-spin" />
          ) : (
            <Icon className="h-6 w-6" />
          )}
        </div>
      </div>
    </motion.div>
  );
}

// Quick Action Button - Enhanced
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
    <Link href={href}>
      <motion.div
        className="group card card-interactive flex items-center gap-4 rounded-xl border border-border/60 p-5"
        whileHover={{ y: -4, transition: { duration: 0.2 } }}
        whileTap={{ scale: 0.98 }}
      >
        <div className="rounded-xl bg-primary/10 p-3 text-primary border border-primary/20 transition-all duration-300 group-hover:bg-primary/20 group-hover:shadow-glow-sm">
          <Icon className="h-5 w-5 transition-transform duration-300 group-hover:scale-110" />
        </div>
        <div>
          <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors">{title}</h3>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <ArrowUpRight className="ml-auto h-4 w-4 text-muted-foreground opacity-0 -translate-y-1 translate-x-1 transition-all duration-300 group-hover:opacity-100 group-hover:translate-y-0 group-hover:translate-x-0 group-hover:text-primary" />
      </motion.div>
    </Link>
  );
}

// Error State Component - Enhanced
function ErrorState({ 
  message, 
  onRetry 
}: { 
  message: string; 
  onRetry: () => void;
}) {
  return (
    <motion.div 
      className="flex flex-col items-center justify-center rounded-xl border border-bear/30 py-12 px-6"
      style={{ background: 'rgba(127, 29, 29, 0.1)' }}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className="rounded-full bg-bear/10 p-4 border border-bear/20">
        <WifiOff className="h-8 w-8 text-bear" />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-foreground">Connection Error</h3>
      <p className="mt-2 text-sm text-muted-foreground text-center max-w-md">{message}</p>
      <motion.button
        onClick={onRetry}
        className="btn-primary mt-6"
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        <RefreshCw className="h-4 w-4" />
        Retry Connection
      </motion.button>
      <p className="mt-4 text-xs text-muted-foreground">
        Make sure the API server is running on port 8000
      </p>
    </motion.div>
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
    <motion.div 
      className="space-y-8"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header Section with Hero Gradient */}
      <motion.div 
        className="page-header relative"
        variants={itemVariants}
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <span className="text-gradient">Dashboard</span>
              <Sparkles className="h-6 w-6 text-primary animate-pulse" />
            </h1>
            <p className="text-muted-foreground mt-1">
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
            <motion.button
              onClick={handleRetry}
              disabled={isFetching}
              className="btn-icon"
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
            </motion.button>
            <motion.button
              onClick={handleStopLoading}
              disabled={!isFetching}
              className={cn(
                'rounded-lg border p-2.5 transition-all duration-200',
                isFetching
                  ? 'border-bear/40 bg-bear/10 text-bear hover:bg-bear/20'
                  : 'cursor-not-allowed border-border/50 bg-card/50 text-muted-foreground opacity-50'
              )}
              whileHover={isFetching ? { scale: 1.05 } : {}}
              whileTap={isFetching ? { scale: 0.95 } : {}}
            >
              <XCircle className="h-4 w-4" />
            </motion.button>
            
            {/* Market Status Badge - Enhanced */}
            <motion.div 
              className={cn(
                'flex items-center gap-2.5 rounded-full px-4 py-2 text-sm border backdrop-blur-sm',
                regimeVariant === 'bull' ? 'border-bull/30 bg-bull/10' :
                regimeVariant === 'bear' ? 'border-bear/30 bg-bear/10' :
                'border-border/50 bg-card/50'
              )}
              whileHover={{ scale: 1.02 }}
            >
              <div className={cn(
                'h-2 w-2 rounded-full',
                regimeVariant === 'bull' ? 'bg-bull' :
                regimeVariant === 'bear' ? 'bg-bear' :
                hasError ? 'bg-bear' :
                isFetching ? 'bg-warning' :
                'bg-muted'
              )}>
                {(regimeVariant === 'bull' || regimeVariant === 'bear' || isFetching) && (
                  <span className="absolute inset-0 rounded-full animate-ping opacity-50" 
                    style={{ 
                      background: regimeVariant === 'bull' ? 'rgb(16, 185, 129)' : 
                                  regimeVariant === 'bear' ? 'rgb(239, 68, 68)' : 
                                  'rgb(217, 119, 6)' 
                    }} 
                  />
                )}
              </div>
              <span className="font-medium flex items-center gap-1.5">
                Market: 
                {isFetching && !hasError ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RegimeIcon regime={marketRegime} className="h-4 w-4" />
                )}
                {hasError ? 'OFFLINE' : marketRegime}
              </span>
            </motion.div>
          </div>
        </div>
      </motion.div>

      {/* Error State */}
      {hasError && !isInitialLoading && (
        <motion.div variants={itemVariants}>
          <ErrorState 
            message="Could not connect to the trading API. Make sure the backend is running."
            onRetry={handleRetry}
          />
        </motion.div>
      )}

      {/* Metric Cards Grid */}
      <motion.div 
        className="grid gap-6 md:grid-cols-2 lg:grid-cols-4"
        variants={itemVariants}
      >
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
      </motion.div>

      {/* Quick Actions */}
      <motion.div variants={itemVariants}>
        <h2 className="mb-4 text-lg font-semibold flex items-center gap-2">
          Quick Actions
          <span className="text-xs text-muted-foreground font-normal">(4 tools)</span>
        </h2>
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
      </motion.div>

      {/* Open Positions Table (if any) */}
      {portfolio?.positions && portfolio.positions.length > 0 && (
        <motion.div 
          className="card rounded-xl border border-border/60 overflow-hidden"
          variants={itemVariants}
        >
          <div className="border-b border-border/50 p-5 flex items-center justify-between">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Wallet className="h-5 w-5 text-primary" />
              Open Positions
            </h2>
            <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded-full font-medium">
              {portfolio.positions.length} active
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/50 bg-surface-2/50">
                  <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">Symbol</th>
                  <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">Entry</th>
                  <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">Current</th>
                  <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">P&L</th>
                  <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">Target</th>
                  <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">Stop</th>
                  <th className="px-5 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">Days</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.positions.map((pos, index) => (
                  <motion.tr 
                    key={pos.id} 
                    className="border-b border-border/30 last:border-0 hover:bg-surface-2/30 transition-colors"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                  >
                    <td className="px-5 py-4">
                      <Link 
                        href={`/analyze?symbol=${pos.symbol}`}
                        className="font-mono font-bold text-primary hover:underline decoration-primary/50 transition-all"
                      >
                        {pos.symbol}
                      </Link>
                    </td>
                    <td className="px-5 py-4 text-right font-mono text-sm">{formatCurrency(pos.entry_price)}</td>
                    <td className="px-5 py-4 text-right font-mono text-sm">{formatCurrency(pos.current_price)}</td>
                    <td className="px-5 py-4 text-right">
                      <div className={cn(
                        'inline-flex items-center gap-1.5 font-mono text-sm font-semibold px-2 py-1 rounded-md',
                        pos.unrealized_pnl > 0 ? 'bg-bull/10 text-bull' : 
                        pos.unrealized_pnl < 0 ? 'bg-bear/10 text-bear' : ''
                      )}>
                        {pos.unrealized_pnl > 0 ? (
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        ) : pos.unrealized_pnl < 0 ? (
                          <ArrowDownRight className="h-3.5 w-3.5" />
                        ) : null}
                        {formatCurrency(pos.unrealized_pnl)}
                        <span className="text-xs opacity-70">({formatPercent(pos.unrealized_pnl_pct)})</span>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-right font-mono text-sm text-bull">{formatCurrency(pos.target_price)}</td>
                    <td className="px-5 py-4 text-right font-mono text-sm text-bear">{formatCurrency(pos.stop_loss)}</td>
                    <td className="px-5 py-4 text-center">
                      <span className="font-mono text-sm bg-muted/20 px-2 py-1 rounded">{pos.days_held}d</span>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}

      {/* Footer Info */}
      <motion.div 
        className="rounded-xl border border-warning/20 bg-warning/5 p-4 text-sm text-muted-foreground flex items-center justify-center gap-3"
        variants={itemVariants}
      >
        <AlertTriangle className="h-4 w-4 text-warning" />
        <p>This is algorithmic analysis for <span className="font-medium text-foreground">educational purposes only</span>. Not financial advice. Always do your own research.</p>
      </motion.div>
    </motion.div>
  );
}
