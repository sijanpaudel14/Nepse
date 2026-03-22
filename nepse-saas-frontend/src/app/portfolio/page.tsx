'use client';

import { useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getPortfolioStatus, updatePortfolio, type PortfolioPosition } from '@/lib/api';
import { 
  Wallet,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Loader2,
  Target,
  AlertTriangle,
  Clock,
  DollarSign,
  BarChart3,
  XCircle,
  CheckCircle,
} from 'lucide-react';
import { cn, formatCurrency, formatPercent, getValueColor } from '@/lib/utils';
import Link from 'next/link';

// Stat Card
function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = 'default',
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: any;
  variant?: 'default' | 'bull' | 'bear';
}) {
  return (
    <div className={cn(
      'rounded-xl border bg-card p-4',
      variant === 'bull' ? 'border-bull/30 bg-bull/5' :
      variant === 'bear' ? 'border-bear/30 bg-bear/5' :
      'border-border'
    )}>
      <div className="flex items-center gap-3">
        <div className={cn(
          'rounded-lg p-2',
          variant === 'bull' ? 'bg-bull/20 text-bull' :
          variant === 'bear' ? 'bg-bear/20 text-bear' :
          'bg-primary/20 text-primary'
        )}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-xl font-bold">{value}</p>
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </div>
    </div>
  );
}

// Position Status Badge
function PositionStatus({ status, daysHeld }: { status: string; daysHeld: number }) {
  const isOverdue = daysHeld > 12;
  
  if (status === 'TARGET_HIT') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-bull/20 px-2 py-0.5 text-xs font-medium text-bull">
        <CheckCircle className="h-3 w-3" /> Target Hit
      </span>
    );
  }
  if (status === 'STOPPED_OUT') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-bear/20 px-2 py-0.5 text-xs font-medium text-bear">
        <XCircle className="h-3 w-3" /> Stopped Out
      </span>
    );
  }
  if (isOverdue) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-warning/20 px-2 py-0.5 text-xs font-medium text-warning">
        <AlertTriangle className="h-3 w-3" /> Overdue ({daysHeld}d)
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-primary/20 px-2 py-0.5 text-xs font-medium text-primary">
      <Clock className="h-3 w-3" /> Holding ({daysHeld}d)
    </span>
  );
}

// Progress to Target/Stop
function ProgressBar({ current, entry, target, stop }: { 
  current: number; 
  entry: number; 
  target: number; 
  stop: number;
}) {
  const range = target - stop;
  const position = ((current - stop) / range) * 100;
  const entryPosition = ((entry - stop) / range) * 100;
  
  return (
    <div className="relative h-2 w-full rounded-full bg-background">
      {/* Stop zone */}
      <div className="absolute left-0 top-0 h-full w-1/4 rounded-l-full bg-bear/30" />
      {/* Target zone */}
      <div className="absolute right-0 top-0 h-full w-1/4 rounded-r-full bg-bull/30" />
      {/* Entry marker */}
      <div 
        className="absolute top-0 h-full w-0.5 bg-muted-foreground"
        style={{ left: `${Math.min(100, Math.max(0, entryPosition))}%` }}
      />
      {/* Current position */}
      <div 
        className={cn(
          'absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background',
          position >= 75 ? 'bg-bull' :
          position <= 25 ? 'bg-bear' :
          'bg-primary'
        )}
        style={{ left: `${Math.min(100, Math.max(0, position))}%` }}
      />
    </div>
  );
}

// Positions Table
function PositionsTable({ positions }: { positions: PortfolioPosition[] }) {
  if (positions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-12">
        <Wallet className="h-12 w-12 text-muted-foreground" />
        <h3 className="mt-4 text-lg font-semibold">No Open Positions</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Run a scan to find trading opportunities
        </p>
        <Link
          href="/scanner"
          className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Go to Scanner
        </Link>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full">
        <thead className="border-b border-border bg-card-hover">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">Symbol</th>
            <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">Entry</th>
            <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">Current</th>
            <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">P&L</th>
            <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">Progress</th>
            <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">Status</th>
            <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {positions.map((pos) => (
            <tr key={pos.id} className="table-row-hover">
              <td className="px-4 py-4">
                <Link
                  href={`/analyze?symbol=${pos.symbol}`}
                  className="font-mono text-lg font-bold text-primary hover:underline"
                >
                  {pos.symbol}
                </Link>
                <p className="text-xs text-muted-foreground">
                  {pos.entry_date} • {pos.quantity} shares
                </p>
              </td>
              <td className="px-4 py-4 text-right font-mono">
                {formatCurrency(pos.entry_price)}
              </td>
              <td className="px-4 py-4 text-right font-mono font-semibold">
                {formatCurrency(pos.current_price)}
              </td>
              <td className={cn(
                'px-4 py-4 text-right font-mono font-semibold',
                getValueColor(pos.unrealized_pnl)
              )}>
                {formatCurrency(pos.unrealized_pnl)}
                <span className="ml-1 text-xs">
                  ({formatPercent(pos.unrealized_pnl_pct)})
                </span>
              </td>
              <td className="px-4 py-4">
                <div className="mx-auto w-32">
                  <ProgressBar 
                    current={pos.current_price}
                    entry={pos.entry_price}
                    target={pos.target_price}
                    stop={pos.stop_loss}
                  />
                  <div className="mt-1 flex justify-between text-xs text-muted-foreground">
                    <span className="text-bear">{formatCurrency(pos.stop_loss)}</span>
                    <span className="text-bull">{formatCurrency(pos.target_price)}</span>
                  </div>
                </div>
              </td>
              <td className="px-4 py-4 text-center">
                <PositionStatus status={pos.status} daysHeld={pos.days_held} />
              </td>
              <td className="px-4 py-4 text-center">
                <Link
                  href={`/analyze?symbol=${pos.symbol}`}
                  className="text-sm text-primary hover:underline"
                >
                  View Analysis
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PortfolioPage() {
  const queryClient = useQueryClient();
  const [updateFeedback, setUpdateFeedback] = useState<{ success: boolean; message: string } | null>(null);
  const updateAbortRef = useRef<AbortController | null>(null);
  const [isUpdateRunning, setIsUpdateRunning] = useState(false);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['portfolio'],
    queryFn: () => getPortfolioStatus(),
  });

  const updateMutation = useMutation({
    mutationFn: async () => {
      const controller = new AbortController();
      updateAbortRef.current = controller;
      setIsUpdateRunning(true);
      try {
        return await updatePortfolio(controller.signal);
      } finally {
        setIsUpdateRunning(false);
        updateAbortRef.current = null;
      }
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      setUpdateFeedback({
        success: true,
        message: data.message || 'Portfolio prices updated!',
      });
      setTimeout(() => setUpdateFeedback(null), 4000);
    },
    onError: (error) => {
      setUpdateFeedback({
        success: false,
        message: error instanceof Error ? error.message : 'Failed to update portfolio',
      });
      setTimeout(() => setUpdateFeedback(null), 4000);
    },
  });

  const handleUpdate = () => {
    updateMutation.mutate();
  };

  const handleStopUpdate = () => {
    if (updateAbortRef.current) {
      updateAbortRef.current.abort();
      updateAbortRef.current = null;
      setIsUpdateRunning(false);
      setUpdateFeedback({
        success: false,
        message: 'Portfolio update stopped by user.',
      });
      setTimeout(() => setUpdateFeedback(null), 3000);
    }
  };

  const stats = data?.stats;
  const positions = data?.positions || [];
  const openPositions = positions.filter(p => p.status === 'OPEN');
  const closedPositions = positions.filter(p => p.status !== 'OPEN');

  const totalPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0);

  return (
    <div className="space-y-6">
      {/* Update Feedback Toast */}
      {updateFeedback && (
        <div className={cn(
          'fixed top-4 right-4 z-50 flex items-center gap-3 rounded-lg px-4 py-3 shadow-lg',
          updateFeedback.success
            ? 'bg-bull/20 border border-bull/30 text-bull-text'
            : 'bg-bear/20 border border-bear/30 text-bear-text'
        )}>
          {updateFeedback.success ? (
            <CheckCircle className="h-5 w-5" />
          ) : (
            <XCircle className="h-5 w-5" />
          )}
          <span className="text-sm font-medium">{updateFeedback.message}</span>
          <button 
            onClick={() => setUpdateFeedback(null)}
            className="ml-2 opacity-60 hover:opacity-100"
          >
            <XCircle className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Wallet className="h-8 w-8 text-primary" />
            Paper Trading Portfolio
          </h1>
          <p className="text-muted-foreground">
            Track your simulated trades and monitor performance
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleUpdate}
            disabled={updateMutation.isPending || isUpdateRunning}
            className={cn(
              'flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium transition-colors hover:bg-card-hover',
              (updateMutation.isPending || isUpdateRunning) && 'cursor-not-allowed opacity-50'
            )}
          >
            {updateMutation.isPending || isUpdateRunning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Update Prices
          </button>
          <button
            onClick={handleStopUpdate}
            disabled={!isUpdateRunning}
            className={cn(
              'flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors',
              isUpdateRunning
                ? 'border-bear/40 bg-bear/10 text-bear hover:bg-bear/20'
                : 'cursor-not-allowed border-border bg-card text-muted-foreground opacity-50'
            )}
          >
            <XCircle className="h-4 w-4" />
            Stop
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total P&L"
            value={formatCurrency(totalPnl)}
            subtitle={`${stats.open_positions} open positions`}
            icon={DollarSign}
            variant={totalPnl > 0 ? 'bull' : totalPnl < 0 ? 'bear' : 'default'}
          />
          <StatCard
            title="Win Rate"
            value={`${stats.win_rate.toFixed(1)}%`}
            subtitle={`${stats.wins}W / ${stats.losses}L`}
            icon={BarChart3}
            variant={stats.win_rate >= 55 ? 'bull' : stats.win_rate >= 45 ? 'default' : 'bear'}
          />
          <StatCard
            title="Avg Win"
            value={formatCurrency(stats.avg_win)}
            subtitle={`Best: ${formatCurrency(stats.best_trade)}`}
            icon={TrendingUp}
            variant="bull"
          />
          <StatCard
            title="Avg Loss"
            value={formatCurrency(stats.avg_loss)}
            subtitle={`Worst: ${formatCurrency(stats.worst_trade)}`}
            icon={TrendingDown}
            variant="bear"
          />
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
          <p className="mt-4 text-lg font-medium">Loading portfolio...</p>
        </div>
      )}

      {/* Open Positions */}
      {!isLoading && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">
            Open Positions ({openPositions.length})
          </h2>
          <PositionsTable positions={openPositions} />
        </div>
      )}

      {/* Closed Positions */}
      {closedPositions.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-muted-foreground">
            Recently Closed ({closedPositions.length})
          </h2>
          <div className="opacity-75">
            <PositionsTable positions={closedPositions} />
          </div>
        </div>
      )}

      {/* Info */}
      <div className="rounded-lg border border-border bg-card-hover p-4">
        <h3 className="font-semibold text-foreground flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-warning" />
          Paper Trading Rules
        </h3>
        <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
          <li>• Positions are automatically closed when they hit Target or Stop Loss</li>
          <li>• Overdue positions (&gt;12 days) should be manually reviewed</li>
          <li>• This is simulation only — no real money is involved</li>
          <li>• Use this to validate your strategy before real trading</li>
        </ul>
      </div>
    </div>
  );
}
