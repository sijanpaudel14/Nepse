'use client';

import { Suspense, useEffect, useRef, useState, type ComponentType } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { analyzeStock, stopAnalyze, type SingleStockAnalysis } from '@/lib/api';
import { 
  Search,
  Loader2,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Target,
  Shield,
  BarChart3,
  DollarSign,
  Users,
  Clock,
  Zap,
  Info,
  ChevronRight,
  CheckCircle,
  XCircle,
  AlertOctagon,
} from 'lucide-react';
import { cn, formatCurrency, formatNumber, formatPercent, getScoreColor, getRiskColor, type RiskLevel } from '@/lib/utils';
import { ScanHistoryPanel } from '@/components/ui';
import {
  loadScanHistory,
  pushScanHistory,
  removeScanHistoryItem,
  clearScanHistory,
  type ScanHistoryItem,
} from '@/lib/scan-history';

// Risk Icon Component
function RiskIcon({ level, className }: { level: RiskLevel; className?: string }) {
  switch (level) {
    case 'low':
      return <Shield className={cn('h-4 w-4', className)} />;
    case 'medium':
      return <AlertTriangle className={cn('h-4 w-4', className)} />;
    case 'high':
    case 'critical':
      return <AlertOctagon className={cn('h-4 w-4', className)} />;
    default:
      return <AlertTriangle className={cn('h-4 w-4', className)} />;
  }
}

// Pillar Progress Ring
function PillarRing({
  name,
  score,
  maxScore,
  icon: Icon,
  color,
}: {
  name: string;
  score: number;
  maxScore: number;
  icon: ComponentType<{ className?: string }>;
  color: string;
}) {
  const percentage = (score / maxScore) * 100;
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex min-w-[140px] flex-col items-center">
      <div className="relative h-32 w-32">
        <svg className="h-32 w-32 -rotate-90 transform">
          {/* Background circle */}
          <circle
            cx="64"
            cy="64"
            r={radius}
            stroke="currentColor"
            strokeWidth="10"
            fill="none"
            className="text-background"
          />
          {/* Progress circle */}
          <circle
            cx="64"
            cy="64"
            r={radius}
            stroke={color}
            strokeWidth="10"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-500"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <Icon className="h-6 w-6 text-muted-foreground" />
          <span className="mt-1 text-xl font-bold leading-none">{score.toFixed(0)}</span>
          <span className="mt-0.5 text-xs text-muted-foreground">/ {maxScore}</span>
        </div>
      </div>
      <p className="mt-2 text-center text-sm font-semibold">{name}</p>
    </div>
  );
}

// Metric Row
function MetricRow({
  label,
  value,
  status,
  statusColor,
}: {
  label: string;
  value: string | number;
  status?: string;
  statusColor?: 'bull' | 'bear' | 'neutral' | 'warning';
}) {
  const colorClass = {
    bull: 'text-bull',
    bear: 'text-bear',
    neutral: 'text-neutral',
    warning: 'text-warning',
  }[statusColor || 'neutral'];

  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className="font-mono font-semibold">{value}</span>
        {status && (
          <span className={cn('text-xs font-medium', colorClass)}>
            {status}
          </span>
        )}
      </div>
    </div>
  );
}

// Red Flag Alert
function RedFlagAlert({ flags }: { flags: string[] }) {
  if (!flags || flags.length === 0) return null;

  return (
    <div className="rounded-xl border border-bear/50 bg-bear/5 p-4">
      <h3 className="flex items-center gap-2 font-semibold text-bear">
        <AlertTriangle className="h-5 w-5" />
        Red Flags ({flags.length})
      </h3>
      <ul className="mt-3 space-y-2">
        {flags.map((flag, idx) => (
          <li key={idx} className="flex items-start gap-2 text-sm">
            <ChevronRight className="mt-0.5 h-4 w-4 flex-shrink-0 text-bear" />
            <span className="text-muted-foreground">{flag}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RecommendationBadge({
  value,
  type,
}: {
  value: string;
  type: 'short' | 'long' | 'friend';
}) {
  const text = (value || '').toUpperCase();
  let Icon = Info;
  let classes = 'bg-muted/30 text-muted-foreground';

  if (text.includes('GOOD') || text.includes('RECOMMENDED') || text.includes('PICK')) {
    Icon = CheckCircle;
    classes = 'bg-bull/15 text-bull';
  } else if (
    text.includes('RISK') ||
    text.includes('CAUTION') ||
    text.includes('WATCH') ||
    (type === 'friend' && text.includes('AVERAGE'))
  ) {
    Icon = AlertTriangle;
    classes = 'bg-warning/15 text-warning';
  } else if (
    text.includes('AVOID') ||
    text.includes('NOT RECOMMENDED') ||
    text.includes('BETTER OPTIONS')
  ) {
    Icon = XCircle;
    classes = 'bg-bear/15 text-bear';
  }

  return (
    <div className={cn('mt-2 inline-flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm font-medium', classes)}>
      <Icon className="h-4 w-4" />
      <span>{value}</span>
    </div>
  );
}

// Analysis Content
function AnalysisContent({ data }: { data: SingleStockAnalysis }) {
  const momentumColor = getScoreColor(data.momentum_score);
  const valueColor = getScoreColor(data.value_score);

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-3xl font-bold">{data.symbol}</h2>
            <p className="text-lg text-muted-foreground">{data.name}</p>
            <p className="text-sm text-primary">{data.sector}</p>
          </div>
          <div className="text-right">
            <p className="text-4xl font-bold">{formatCurrency(data.ltp)}</p>
            <p className="mt-1 text-sm text-muted-foreground">{data.recommendation || data.momentum_verdict}</p>
            <div className="mt-2 flex gap-2">
              <span className={cn(
                'inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold',
                momentumColor.bgColor, momentumColor.textColor
              )}>
                Momentum: {data.momentum_score}/100
              </span>
              <span className={cn(
                'inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold',
                valueColor.bgColor, valueColor.textColor
              )}>
                Value: {data.value_score}/100
              </span>
            </div>
          </div>
        </div>
        {data.verdict_reason && (
          <p className="mt-4 rounded-lg bg-muted/20 p-3 text-sm text-muted-foreground">{data.verdict_reason}</p>
        )}
      </div>

      {/* Company overview parity with backend */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
          <Info className="h-5 w-5 text-primary" />
          Company Overview
        </h3>
        <div className="grid gap-4 md:grid-cols-2">
          <MetricRow label="Market Cap" value={`${(data.market_cap_cr || 0).toFixed(0)} Cr`} />
          <MetricRow label="Paid-up Capital" value={`${(data.paid_up_capital_cr || 0).toFixed(0)} Cr`} />
          <MetricRow label="Outstanding Shares" value={`${(data.outstanding_shares_cr || 0).toFixed(2)} Cr`} />
          <MetricRow label="Daily Turnover" value={`${(data.daily_turnover_cr || 0).toFixed(1)} Cr`} />
          <MetricRow label="Promoter Holding" value={`${(data.promoter_pct || 0).toFixed(1)}%`} />
          <MetricRow label="Public Holding" value={`${(data.public_pct || 0).toFixed(1)}%`} />
          <MetricRow label="Free Float" value={`${(data.free_float_pct || 0).toFixed(1)}%`} />
          <MetricRow label="1Y Trend" value={formatPercent(data.price_trend_1y || 0)} statusColor={(data.price_trend_1y || 0) >= 0 ? 'bull' : 'bear'} />
        </div>
      </div>

      {/* 4 Pillars */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h3 className="mb-6 text-lg font-semibold">4-Pillar Analysis</h3>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <PillarRing
            name="Technical"
            score={data.pillars?.technical?.score || 0}
            maxScore={data.pillars?.technical?.max_score || 40}
            icon={BarChart3}
            color="#22c55e"
          />
          <PillarRing
            name="Broker/Inst"
            score={data.pillars?.broker?.score || 0}
            maxScore={data.pillars?.broker?.max_score || 30}
            icon={Users}
            color="#3b82f6"
          />
          <PillarRing
            name="Unlock Risk"
            score={data.pillars?.unlock?.score || 0}
            maxScore={data.pillars?.unlock?.max_score || 20}
            icon={Shield}
            color="#f59e0b"
          />
          <PillarRing
            name="Fundamental"
            score={data.pillars?.fundamental?.score || 0}
            maxScore={data.pillars?.fundamental?.max_score || 10}
            icon={DollarSign}
            color="#8b5cf6"
          />
        </div>
      </div>

      {/* Strategy Comparison (CLI parity) */}
      {data.strategy_comparison && (
        <div className="grid gap-6 md:grid-cols-2">
          <div className="rounded-xl border border-border bg-card p-6">
            <h3 className="mb-4 text-lg font-semibold">Value Strategy</h3>
            {data.strategy_comparison.value ? (
              <div className="space-y-2">
                <MetricRow label="Score" value={`${data.strategy_comparison.value.score.toFixed(0)}/100`} />
                <MetricRow label="Verdict" value={data.strategy_comparison.value.verdict} />
                <MetricRow label="Broker/Institutional" value={`${data.strategy_comparison.value.pillars.broker.toFixed(1)}/30`} />
                <MetricRow label="Unlock Risk" value={`${data.strategy_comparison.value.pillars.unlock.toFixed(1)}/20`} />
                <MetricRow label="Fundamentals" value={`${data.strategy_comparison.value.pillars.fundamental.toFixed(1)}/${data.strategy_comparison.value.pillars.fundamental_max.toFixed(0)}`} />
                <MetricRow label="Technicals" value={`${data.strategy_comparison.value.pillars.technical.toFixed(1)}/${data.strategy_comparison.value.pillars.technical_max.toFixed(0)}`} />
              </div>
            ) : <p className="text-sm text-muted-foreground">No value strategy data.</p>}
          </div>
          <div className="rounded-xl border border-border bg-card p-6">
            <h3 className="mb-4 text-lg font-semibold">Momentum Strategy</h3>
            {data.strategy_comparison.momentum ? (
              <div className="space-y-2">
                <MetricRow label="Score" value={`${data.strategy_comparison.momentum.score.toFixed(0)}/100`} />
                <MetricRow label="Verdict" value={data.strategy_comparison.momentum.verdict} />
                <MetricRow label="Broker/Institutional" value={`${data.strategy_comparison.momentum.pillars.broker.toFixed(1)}/30`} />
                <MetricRow label="Unlock Risk" value={`${data.strategy_comparison.momentum.pillars.unlock.toFixed(1)}/20`} />
                <MetricRow label="Fundamentals" value={`${data.strategy_comparison.momentum.pillars.fundamental.toFixed(1)}/${data.strategy_comparison.momentum.pillars.fundamental_max.toFixed(0)}`} />
                <MetricRow label="Technicals" value={`${data.strategy_comparison.momentum.pillars.technical.toFixed(1)}/${data.strategy_comparison.momentum.pillars.technical_max.toFixed(0)}`} />
              </div>
            ) : <p className="text-sm text-muted-foreground">No momentum strategy data.</p>}
          </div>
        </div>
      )}

      {/* Trade Setup */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Entry/Target/Stop */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <Target className="h-5 w-5 text-primary" />
            Trade Setup
          </h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-lg bg-card-hover p-3">
              <span className="text-muted-foreground">Entry Price</span>
              <span className="font-mono text-xl font-bold">
                {formatCurrency(data.entry_price)}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-bull/10 p-3">
              <span className="text-bull">Target</span>
              <span className="font-mono text-xl font-bold text-bull">
                {formatCurrency(data.target_price)}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-bear/10 p-3">
              <span className="text-bear">Stop Loss</span>
              <span className="font-mono text-xl font-bold text-bear">
                {formatCurrency(data.stop_loss)}
              </span>
            </div>
            <div className="flex items-center justify-between pt-2">
              <span className="flex items-center gap-1 text-muted-foreground">
                <Clock className="h-4 w-4" /> Hold Period
              </span>
              <span className="font-semibold">{data.hold_days}</span>
            </div>
          </div>
        </div>

        {/* Distribution Risk */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <AlertTriangle className="h-5 w-5 text-warning" />
            Distribution Risk
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span>Risk Level</span>
              <span className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-bold',
                getRiskColor(data.distribution_risk).bgColor,
                getRiskColor(data.distribution_risk).textColor
              )}>
                <RiskIcon level={getRiskColor(data.distribution_risk).level} />
                {data.distribution_risk}
              </span>
            </div>
            <MetricRow 
              label="Broker Avg Cost (VWAP)" 
              value={formatCurrency(data.broker_avg_cost)} 
            />
            <MetricRow 
              label="Broker Profit %" 
              value={formatPercent(data.broker_profit_pct)}
              status={data.broker_profit_pct > 10 ? 'HIGH RISK' : 'SAFE'}
              statusColor={data.broker_profit_pct > 10 ? 'bear' : 'bull'}
            />
            {data.distribution_warning && (
              <div className="mt-2 rounded-lg bg-warning/10 p-2 text-sm text-warning">
                <div className="flex items-center gap-2 font-medium">
                  <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                  Distribution warning
                </div>
                <div className="mt-1 space-y-1 pl-6">
                  {data.distribution_warning
                    .split(/(?<=[.!?])\s+/)
                    .filter(Boolean)
                    .map((line, idx) => (
                      <p key={idx}>{line}</p>
                    ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Technical & Fundamental */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Technical Indicators */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <BarChart3 className="h-5 w-5 text-primary" />
            Technical Indicators
          </h3>
          <div className="divide-y divide-border">
            <MetricRow 
              label="RSI (14)" 
              value={data.rsi?.toFixed(1) || 'N/A'}
              status={data.rsi_status}
              statusColor={
                data.rsi >= 70 ? 'bear' :
                data.rsi >= 50 ? 'bull' :
                data.rsi >= 30 ? 'neutral' : 'bear'
              }
            />
            <MetricRow 
              label="EMA Signal" 
              value={data.ema_signal}
              statusColor={data.ema_signal === 'BULLISH' ? 'bull' : 'bear'}
            />
            <MetricRow 
              label="Volume Spike" 
              value={`${data.volume_spike?.toFixed(2)}x`}
              statusColor={data.volume_spike >= 1.5 ? 'bull' : 'neutral'}
            />
            <MetricRow 
              label="ATR" 
              value={formatCurrency(data.atr)}
            />
            <MetricRow 
              label="7D Trend" 
              value={formatPercent(data.price_trend_7d)}
              statusColor={data.price_trend_7d > 0 ? 'bull' : 'bear'}
            />
            <MetricRow 
              label="30D Trend" 
              value={formatPercent(data.price_trend_30d)}
              statusColor={data.price_trend_30d > 0 ? 'bull' : 'bear'}
            />
            <MetricRow 
              label="90D Trend" 
              value={formatPercent(data.price_trend_90d)}
              statusColor={data.price_trend_90d > 0 ? 'bull' : 'bear'}
            />
            <MetricRow 
              label="52W High" 
              value={formatCurrency(data.high_52w || 0)}
            />
            <MetricRow 
              label="52W Low" 
              value={formatCurrency(data.low_52w || 0)}
            />
          </div>
        </div>

        {/* Fundamental Data */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <DollarSign className="h-5 w-5 text-primary" />
            Fundamental Data
          </h3>
          <div className="divide-y divide-border">
            <MetricRow 
              label="P/E Ratio" 
              value={data.pe_ratio?.toFixed(2) || 'N/A'}
              status={data.pe_status}
              statusColor={
                data.pe_ratio < 0 ? 'bear' :
                data.pe_ratio <= 15 ? 'bull' :
                data.pe_ratio <= 25 ? 'neutral' : 'bear'
              }
            />
            <MetricRow 
              label="EPS" 
              value={formatCurrency(data.eps)}
            />
            <MetricRow 
              label="EPS (Annualized)" 
              value={formatCurrency(data.eps_annualized)}
            />
            <MetricRow 
              label="Book Value" 
              value={formatCurrency(data.book_value)}
            />
            <MetricRow 
              label="P/BV Ratio" 
              value={data.pbv?.toFixed(2) || 'N/A'}
              statusColor={data.pbv <= 2 ? 'bull' : data.pbv <= 4 ? 'neutral' : 'bear'}
            />
            <MetricRow 
              label="ROE" 
              value={formatPercent(data.roe)}
              status={data.roe_status}
              statusColor={data.roe >= 15 ? 'bull' : data.roe >= 10 ? 'neutral' : 'bear'}
            />
          </div>
        </div>
      </div>

      {/* Sector comparison + dividends */}
      <div className="grid gap-6 md:grid-cols-2">
        {data.sector_comparison && (
          <div className="rounded-xl border border-border bg-card p-6">
            <h3 className="mb-4 text-lg font-semibold">Sector Comparison</h3>
            <div className="space-y-2">
              <MetricRow label="Sector" value={data.sector_comparison.sector} />
              <MetricRow label="Sector Avg PE" value={data.sector_comparison.sector_avg_pe.toFixed(1)} />
              <MetricRow label="Sector Avg PBV" value={data.sector_comparison.sector_avg_pbv.toFixed(1)} />
              <MetricRow label="Sector Avg ROE" value={`${data.sector_comparison.sector_avg_roe.toFixed(1)}%`} />
              <MetricRow label="PE vs Sector" value={formatPercent(data.sector_comparison.pe_vs_sector_pct)} statusColor={data.sector_comparison.pe_vs_sector_pct > 20 ? 'bear' : 'neutral'} />
              <MetricRow label="PBV vs Sector" value={formatPercent(data.sector_comparison.pbv_vs_sector_pct)} statusColor={data.sector_comparison.pbv_vs_sector_pct > 20 ? 'bear' : 'neutral'} />
              <MetricRow label="ROE vs Sector" value={formatPercent(data.sector_comparison.roe_vs_sector_pct)} statusColor={data.sector_comparison.roe_vs_sector_pct >= 0 ? 'bull' : 'bear'} />
            </div>
          </div>
        )}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold">Dividend History (3Y)</h3>
          {data.dividend_history && data.dividend_history.length > 0 ? (
            <div className="space-y-2">
              {data.dividend_history.map((d, i) => (
                <div key={`${d.fiscal_year}-${i}`} className="rounded-lg bg-card-hover p-3 text-sm">
                  <div className="font-semibold">{d.fiscal_year}</div>
                  <div className="text-muted-foreground">
                    Cash {d.cash_pct.toFixed(2)}% + Bonus {d.bonus_pct.toFixed(2)}% = Total {d.total_pct.toFixed(2)}%
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No dividend history available.</p>
          )}
        </div>
      </div>

      {/* Risk & Structure from backend */}
      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <Shield className="h-5 w-5 text-primary" />
            Price Structure
          </h3>
          <div className="divide-y divide-border">
            <MetricRow label="Support Level" value={formatCurrency(data.support_level || 0)} />
            <MetricRow label="Resistance Level" value={formatCurrency(data.resistance_level || 0)} />
            <MetricRow label="From 52W High" value={formatPercent(data.pct_from_52w_high || 0)} statusColor={(data.pct_from_52w_high || 0) > -10 ? 'neutral' : 'bear'} />
            <MetricRow label="From 52W Low" value={formatPercent(data.pct_from_52w_low || 0)} statusColor={(data.pct_from_52w_low || 0) > 10 ? 'bull' : 'neutral'} />
            <MetricRow label="Risk/Reward Ratio" value={`1:${(data.risk_reward_ratio || 0).toFixed(2)}`} statusColor={(data.risk_reward_ratio || 0) >= 1.5 ? 'bull' : 'warning'} />
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
            <Users className="h-5 w-5 text-primary" />
            Smart Money Context
          </h3>
          <div className="divide-y divide-border">
            <MetricRow label="1M Net Holdings" value={formatNumber(data.net_holdings_1m || 0)} statusColor={(data.net_holdings_1m || 0) >= 0 ? 'bull' : 'bear'} />
            <MetricRow label="1W Net Holdings" value={formatNumber(data.net_holdings_1w || 0)} statusColor={(data.net_holdings_1w || 0) >= 0 ? 'bull' : 'bear'} />
            <MetricRow label="Open vs Broker Avg" value={formatPercent(data.open_vs_broker_pct || 0)} statusColor={(data.open_vs_broker_pct || 0) >= 5 ? 'warning' : 'neutral'} />
            <MetricRow label="Close vs VWAP" value={formatPercent(data.close_vs_vwap_pct || 0)} statusColor={(data.close_vs_vwap_pct || 0) < 0 ? 'bear' : 'bull'} />
            <MetricRow label="Intraday Volume Spike" value={`${(data.intraday_volume_spike || 0).toFixed(2)}x`} statusColor={(data.intraday_volume_spike || 0) >= 1.5 ? 'warning' : 'neutral'} />
          </div>
          {data.intraday_dump_detected && (
            <div className="mt-4 rounded-lg bg-bear/10 p-3 text-sm text-bear">
              Intraday dump pattern detected today (high-volume rejection setup).
            </div>
          )}
          {data.execution_warning && (
            <div className="mt-2 rounded-lg bg-warning/10 p-3 text-sm text-warning">
              {data.execution_warning}
            </div>
          )}
        </div>
      </div>

      {/* Full distribution detail */}
      {data.distribution_details && (
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold">Broker Distribution Risk (Detailed)</h3>
          <div className="grid gap-4 md:grid-cols-2">
            <MetricRow label="Risk Level" value={data.distribution_details.risk_level} />
            <MetricRow label="Current LTP" value={formatCurrency(data.distribution_details.current_ltp)} />
            <MetricRow label="1M Avg Cost" value={formatCurrency(data.distribution_details.avg_cost_1m)} />
            <MetricRow label="1W Avg Cost" value={formatCurrency(data.distribution_details.avg_cost_1w)} />
            <MetricRow label="1M Net Holdings" value={formatNumber(data.distribution_details.net_holdings_1m)} statusColor={data.distribution_details.net_holdings_1m >= 0 ? 'bull' : 'bear'} />
            <MetricRow label="1W Net Holdings" value={formatNumber(data.distribution_details.net_holdings_1w)} statusColor={data.distribution_details.net_holdings_1w >= 0 ? 'bull' : 'bear'} />
            <MetricRow label="Broker Profit" value={formatPercent(data.distribution_details.broker_profit_pct)} statusColor={data.distribution_details.broker_profit_pct > 10 ? 'bear' : 'neutral'} />
            <MetricRow label="Open vs Broker" value={formatPercent(data.distribution_details.open_vs_broker_pct)} />
            <MetricRow label="Close vs VWAP" value={formatPercent(data.distribution_details.close_vs_vwap_pct)} statusColor={data.distribution_details.close_vs_vwap_pct < 0 ? 'bear' : 'bull'} />
            <MetricRow label="Intraday Volume Spike" value={`${data.distribution_details.intraday_volume_spike.toFixed(2)}x`} />
          </div>
          {data.distribution_details.divergence && (
            <div className="mt-3 rounded-lg bg-warning/10 p-3 text-sm text-warning">Divergence detected: 1M accumulation but 1W distribution.</div>
          )}
          {data.distribution_details.warning && (
            <div className="mt-3 rounded-lg bg-warning/10 p-3 text-sm text-warning">{data.distribution_details.warning}</div>
          )}
        </div>
      )}

      {/* Top broker activity */}
      {data.broker_activity && data.broker_activity.brokers?.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold">Top Broker Activity</h3>
          <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-lg bg-card-hover p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Data Period</p>
              <p className="mt-1 text-sm font-semibold leading-snug">{data.broker_activity.data_period || 'N/A'}</p>
            </div>
            <div className="rounded-lg bg-card-hover p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Total Volume</p>
              <p className="mt-1 text-sm font-semibold">{formatNumber(data.broker_activity.total_volume)}</p>
            </div>
            <div className="rounded-lg bg-card-hover p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Transactions</p>
              <p className="mt-1 text-sm font-semibold">{formatNumber(data.broker_activity.total_transactions)}</p>
            </div>
            <div className="rounded-lg bg-card-hover p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Top5 Avg Cost</p>
              <p className="mt-1 text-sm font-semibold">{formatCurrency(data.broker_activity.top5_avg_cost)}</p>
            </div>
          </div>
          <div className="mb-2 grid grid-cols-12 rounded-lg border border-border/60 bg-muted/20 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <div className="col-span-1">Code</div>
            <div className="col-span-5">Broker Name</div>
            <div className="col-span-2 text-right">Net Qty</div>
            <div className="col-span-2 text-right">Avg Buy</div>
            <div className="col-span-2 text-right">Sell Qty</div>
          </div>
          <div className="space-y-2">
            {data.broker_activity.brokers.map((b) => (
              <div key={`${b.broker_code}-${b.broker_name}`} className="grid grid-cols-12 rounded-lg bg-card-hover p-3 text-sm">
                <div className="col-span-1 font-semibold">{b.broker_code}</div>
                <div className="col-span-5 truncate">{b.broker_name}</div>
                <div className={cn('col-span-2 text-right font-semibold', b.net_quantity >= 0 ? 'text-bull' : 'text-bear')}>
                  {formatNumber(b.net_quantity)}
                </div>
                <div className="col-span-2 text-right">{formatCurrency(b.avg_buy_price)}</div>
                <div className="col-span-2 text-right text-muted-foreground">{formatNumber(b.sell_quantity)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Manipulation risk */}
      {data.manipulation_risk && (
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold">Manipulation Risk Analysis</h3>
          <div className="grid gap-4 md:grid-cols-2">
            <MetricRow label="Risk Score" value={`${data.manipulation_risk.score.toFixed(0)}%`} statusColor={data.manipulation_risk.score >= 60 ? 'bear' : data.manipulation_risk.score >= 35 ? 'warning' : 'bull'} />
            <MetricRow label="Severity" value={data.manipulation_risk.severity} />
            <MetricRow label="Operator Phase" value={data.manipulation_risk.phase} />
            <MetricRow label="Trading Status" value={data.manipulation_risk.safe_to_trade ? 'SAFE TO TRADE' : 'HIGH RISK'} statusColor={data.manipulation_risk.safe_to_trade ? 'bull' : 'bear'} />
            <MetricRow label="HHI" value={data.manipulation_risk.hhi.toFixed(0)} />
            <MetricRow label="Top3 Control" value={`${data.manipulation_risk.top3_control_pct.toFixed(0)}%`} />
            <div className="flex items-center justify-between rounded-lg border border-border/60 bg-card-hover px-3 py-2">
              <span className="text-muted-foreground">Circular Trading</span>
              <span className={cn('inline-flex items-center gap-1.5 font-semibold', data.manipulation_risk.circular_trading_pct > 20 ? 'text-bear' : 'text-bull')}>
                {data.manipulation_risk.circular_trading_pct > 20 ? <AlertOctagon className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
                {data.manipulation_risk.circular_trading_pct.toFixed(0)}%
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border/60 bg-card-hover px-3 py-2">
              <span className="text-muted-foreground">Wash Trading</span>
              <span className={cn('inline-flex items-center gap-1.5 font-semibold', data.manipulation_risk.wash_trading_detected ? 'text-bear' : 'text-bull')}>
                {data.manipulation_risk.wash_trading_detected ? <AlertOctagon className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
                {data.manipulation_risk.wash_trading_detected ? 'DETECTED' : 'NONE'}
              </span>
            </div>
          </div>
          {data.manipulation_risk.alerts?.length > 0 && (
            <div className="mt-4 rounded-lg bg-warning/10 p-3 text-sm text-warning">
              {data.manipulation_risk.alerts.map((a, i) => <p key={i}>{a}</p>)}
            </div>
          )}
        </div>
      )}

      {/* Support / resistance zones */}
      {data.support_resistance && (
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold">Support & Resistance Zones</h3>
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <p className="mb-2 text-sm font-semibold text-bear">Resistance</p>
              <div className="space-y-2">
                {(data.support_resistance.resistances || []).length > 0 ? data.support_resistance.resistances.map((r, i) => (
                  <div key={i} className="rounded-lg bg-bear/10 p-2 text-sm">{formatCurrency(r)} ({formatPercent(((r - data.ltp) / Math.max(data.ltp, 1)) * 100)})</div>
                )) : <p className="text-sm text-muted-foreground">No strong resistance above.</p>}
              </div>
            </div>
            <div>
              <p className="mb-2 text-sm font-semibold text-bull">Support</p>
              <div className="space-y-2">
                {(data.support_resistance.supports || []).length > 0 ? data.support_resistance.supports.map((s, i) => (
                  <div key={i} className="rounded-lg bg-bull/10 p-2 text-sm">{formatCurrency(s)} ({formatPercent(((s - data.ltp) / Math.max(data.ltp, 1)) * 100)})</div>
                )) : <p className="text-sm text-muted-foreground">No strong support below.</p>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Price target analysis */}
      {data.price_target_analysis && (
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold">Price Target Analysis</h3>
          <div className="grid gap-4 md:grid-cols-2">
            {data.price_target_analysis.conservative && (
              <MetricRow label="Conservative" value={`${formatCurrency(data.price_target_analysis.conservative.level)} (${formatPercent(data.price_target_analysis.conservative.upside_percent)})`} />
            )}
            {data.price_target_analysis.moderate && (
              <MetricRow label="Moderate" value={`${formatCurrency(data.price_target_analysis.moderate.level)} (${formatPercent(data.price_target_analysis.moderate.upside_percent)})`} />
            )}
            {data.price_target_analysis.aggressive && (
              <MetricRow label="Aggressive" value={`${formatCurrency(data.price_target_analysis.aggressive.level)} (${formatPercent(data.price_target_analysis.aggressive.upside_percent)})`} />
            )}
            {data.price_target_analysis.max_theory && (
              <MetricRow label="Max Theory" value={`${formatCurrency(data.price_target_analysis.max_theory.level)} (${formatPercent(data.price_target_analysis.max_theory.upside_percent)})`} />
            )}
            <MetricRow label="Nearest Support" value={formatCurrency(data.price_target_analysis.nearest_support)} />
            <MetricRow label="Downside Risk" value={`-${Math.abs(data.price_target_analysis.downside_risk_pct).toFixed(1)}%`} />
            <MetricRow label="Risk/Reward" value={`1:${(data.price_target_analysis.risk_reward_ratio || 0).toFixed(1)}`} />
            <MetricRow label="Trend / Momentum" value={`${data.price_target_analysis.trend_direction} / ${data.price_target_analysis.momentum_score.toFixed(0)}`} />
          </div>
          {data.price_target_analysis.warnings?.length > 0 && (
            <div className="mt-4 rounded-lg bg-warning/10 p-3 text-sm text-warning">
              {data.price_target_analysis.warnings.slice(0, 2).map((w, i) => <p key={i}>{w}</p>)}
            </div>
          )}
        </div>
      )}

      {/* Recommendations */}
      <div className="grid gap-6 md:grid-cols-3">
        <div className="rounded-xl border border-primary/50 bg-primary/5 p-4">
          <h4 className="flex items-center gap-2 font-semibold text-primary">
            <Zap className="h-4 w-4" />
            Short-Term (Swing)
          </h4>
          <RecommendationBadge value={data.short_term_recommendation} type="short" />
        </div>
        <div className="rounded-xl border border-bull/50 bg-bull/5 p-4">
          <h4 className="flex items-center gap-2 font-semibold text-bull">
            <TrendingUp className="h-4 w-4" />
            Long-Term (Investment)
          </h4>
          <RecommendationBadge value={data.long_term_recommendation} type="long" />
        </div>
        <div className="rounded-xl border border-warning/50 bg-warning/5 p-4">
          <h4 className="flex items-center gap-2 font-semibold text-warning">
            <Users className="h-4 w-4" />
            Friend Recommendation
          </h4>
          <RecommendationBadge value={data.friend_recommendation} type="friend" />
        </div>
      </div>

      {/* Red Flags */}
      <RedFlagAlert flags={data.red_flags} />

      {/* Removed compressed backend summary in favor of structured sections */}
    </div>
  );
}

// Inner component that handles the form and data
function AnalyzePageInner({ initialSymbol }: { initialSymbol: string }) {
  const ANALYZE_STATE_KEY = 'nepse-analyze-state-v1';
  const ANALYZE_RUNNING_KEY = 'nepse-analyze-running-v1';
  const ANALYZE_HISTORY_KEY = 'nepse-analyze-history-v1';
  const ANALYZE_RESULTS_CACHE_KEY = 'nepse-analyze-results-v1';
  type AnalyzeApiResponse = Awaited<ReturnType<typeof analyzeStock>>;
  type AnalyzeResultCache = Record<string, AnalyzeApiResponse>;
  const normalizedInitial = initialSymbol.toUpperCase().trim();
  const [symbol, setSymbol] = useState(normalizedInitial);
  const [submittedSymbol, setSubmittedSymbol] = useState(normalizedInitial);
  const [strategy, setStrategy] = useState<'momentum' | 'value'>('momentum');
  const [shouldFetch, setShouldFetch] = useState(false);
  const [restoredAnalysis, setRestoredAnalysis] = useState<AnalyzeApiResponse | null>(null);
  const analyzeAbortRef = useRef<AbortController | null>(null);
  const [isAnalyzeRunning, setIsAnalyzeRunning] = useState(false);
  const [activeAnalyzeSymbol, setActiveAnalyzeSymbol] = useState('');
  const [isHydrating, setIsHydrating] = useState(true);
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);
  const queryClient = useQueryClient();

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(ANALYZE_STATE_KEY);
      let parsedState: { symbol?: string; submittedSymbol?: string; strategy?: 'momentum' | 'value' } | null = null;
      if (raw) {
        parsedState = JSON.parse(raw);
        if (!normalizedInitial && typeof parsedState?.symbol === 'string') setSymbol(parsedState.symbol);
        if (!normalizedInitial && typeof parsedState?.submittedSymbol === 'string') setSubmittedSymbol(parsedState.submittedSymbol);
        if (parsedState?.strategy === 'momentum' || parsedState?.strategy === 'value') setStrategy(parsedState.strategy);
      }

      const cacheRaw = window.localStorage.getItem(ANALYZE_RESULTS_CACHE_KEY);
      if (cacheRaw) {
        const cache = JSON.parse(cacheRaw) as AnalyzeResultCache;
        const candidateSymbol = (normalizedInitial || parsedState?.submittedSymbol || '').toUpperCase().trim();
        const candidateStrategy = parsedState?.strategy === 'value' ? 'value' : 'momentum';
        const cached = cache[`${candidateSymbol}:${candidateStrategy}`];
        if (cached?.success) {
          setRestoredAnalysis(cached);
        }
      }

      const runningRaw = window.localStorage.getItem(ANALYZE_RUNNING_KEY);
      if (runningRaw) {
        window.localStorage.removeItem(ANALYZE_RUNNING_KEY);
      }
    } catch {
      // Ignore invalid persisted state
    } finally {
      setIsHydrating(false);
    }
  }, [normalizedInitial]);

  useEffect(() => {
    setHistory(loadScanHistory(ANALYZE_HISTORY_KEY));
  }, []);

  useEffect(() => {
    if (isHydrating) return;
    window.localStorage.setItem(
      ANALYZE_STATE_KEY,
      JSON.stringify({ symbol, submittedSymbol, strategy })
    );
  }, [symbol, submittedSymbol, strategy, isHydrating]);

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ['analyze', submittedSymbol, strategy],
    queryFn: async () => {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort('analyze-timeout'), 90_000);
      analyzeAbortRef.current = controller;
      setIsAnalyzeRunning(true);
      setActiveAnalyzeSymbol(submittedSymbol);
      window.localStorage.setItem(
        ANALYZE_RUNNING_KEY,
        JSON.stringify({ startedAt: Date.now(), symbol: submittedSymbol, strategy })
      );
      try {
        return await analyzeStock(submittedSymbol, { strategy }, controller.signal);
      } finally {
        window.clearTimeout(timeout);
        setIsAnalyzeRunning(false);
        setActiveAnalyzeSymbol('');
        analyzeAbortRef.current = null;
        window.localStorage.removeItem(ANALYZE_RUNNING_KEY);
      }
    },
    enabled: false,
    staleTime: 10 * 60 * 1000,
    placeholderData: keepPreviousData,
  });

  useEffect(() => {
    if (data?.success) {
      setRestoredAnalysis(data);
      try {
        const raw = window.localStorage.getItem(ANALYZE_RESULTS_CACHE_KEY);
        const cache = raw ? (JSON.parse(raw) as AnalyzeResultCache) : {};
        cache[`${submittedSymbol}:${strategy}`] = data;
        window.localStorage.setItem(ANALYZE_RESULTS_CACHE_KEY, JSON.stringify(cache));
      } catch {
        // Ignore cache persistence failures
      }
    }
  }, [data, submittedSymbol, strategy]);

  useEffect(() => {
    if (!shouldFetch || submittedSymbol.length < 3) return;
    void refetch();
    setShouldFetch(false);
  }, [shouldFetch, submittedSymbol, refetch]);

  useEffect(() => {
    if (isHydrating || !submittedSymbol || submittedSymbol.length < 3) return;
    if (isFetching || isAnalyzeRunning) return;
    try {
      const raw = window.localStorage.getItem(ANALYZE_RESULTS_CACHE_KEY);
      if (!raw) return;
      const cache = JSON.parse(raw) as AnalyzeResultCache;
      const cached = cache[`${submittedSymbol}:${strategy}`];
      if (cached?.success) {
        setRestoredAnalysis(cached);
      }
    } catch {
      // Ignore invalid cache data
    }
  }, [submittedSymbol, strategy, isHydrating, isFetching, isAnalyzeRunning]);

  useEffect(() => {
    if (!isFetching) {
      setIsAnalyzeRunning(false);
      window.localStorage.removeItem(ANALYZE_RUNNING_KEY);
    }
  }, [isFetching]);

  useEffect(() => {
    if (isHydrating) return;
  }, [isHydrating]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanSymbol = symbol.toUpperCase().trim();
    if (cleanSymbol.length < 3) return;
    setHistory(
      pushScanHistory(ANALYZE_HISTORY_KEY, {
        label: `${cleanSymbol} (${strategy})`,
        value: cleanSymbol,
      })
    );
    if (analyzeAbortRef.current) {
      analyzeAbortRef.current.abort();
      analyzeAbortRef.current = null;
      setIsAnalyzeRunning(false);
      setActiveAnalyzeSymbol('');
      window.localStorage.removeItem(ANALYZE_RUNNING_KEY);
    }
    // Always trigger a fresh analyze run when user clicks Analyze.
    setSubmittedSymbol(cleanSymbol);
    setShouldFetch(true);
  };

  const handleStopAnalyze = () => {
    const symbolToStop = activeAnalyzeSymbol || submittedSymbol || symbol.trim().toUpperCase();
    analyzeAbortRef.current?.abort();
    analyzeAbortRef.current = null;
    setIsAnalyzeRunning(false);
    setActiveAnalyzeSymbol('');
    window.localStorage.removeItem(ANALYZE_RUNNING_KEY);
    queryClient.cancelQueries({ queryKey: ['analyze'] });
    if (symbolToStop) {
      stopAnalyze(symbolToStop).catch(() => {
        // Best effort stop signal to backend
      });
    }
  };

  const isAbortError =
    error instanceof Error && /abort|aborted|timeout/i.test(error.message);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Stock Analysis</h1>
        <p className="text-muted-foreground">
          Deep-dive into any NEPSE stock with 4-Pillar scoring
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="flex flex-wrap gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="Enter stock symbol (e.g., NABIL)"
            className="w-full rounded-lg border border-border bg-card pl-10 pr-4 py-3 text-lg font-mono focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        
        <div className="inline-flex h-12 items-center rounded-lg border border-border bg-card p-1">
          <button
            type="button"
            onClick={() => setStrategy('momentum')}
            className={cn(
              'inline-flex h-10 items-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors',
              strategy === 'momentum'
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted/20'
            )}
          >
            <TrendingUp className="h-4 w-4" />
            Momentum
          </button>
          <button
            type="button"
            onClick={() => setStrategy('value')}
            className={cn(
              'inline-flex h-10 items-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors',
              strategy === 'value'
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted/20'
            )}
          >
            <DollarSign className="h-4 w-4" />
            Value
          </button>
        </div>

        <button
          type="submit"
          disabled={isFetching || isAnalyzeRunning || symbol.trim().length < 3}
          className={cn(
            'flex items-center gap-2 rounded-lg bg-primary px-6 py-3 font-semibold text-primary-foreground transition-colors hover:bg-primary/90',
            (isFetching || isAnalyzeRunning || symbol.trim().length < 3) && 'cursor-not-allowed opacity-50'
          )}
        >
          {isFetching || isAnalyzeRunning ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Search className="h-5 w-5" />
          )}
          Analyze
        </button>
        <button
          type="button"
          onClick={handleStopAnalyze}
          disabled={!(isAnalyzeRunning || isFetching)}
          className={cn(
            'flex items-center gap-2 rounded-lg border px-4 py-3 font-semibold transition-colors',
            isAnalyzeRunning || isFetching
              ? 'border-bear/40 bg-bear/10 text-bear hover:bg-bear/20'
              : 'cursor-not-allowed border-border bg-card text-muted-foreground opacity-50'
          )}
        >
          <XCircle className="h-5 w-5" />
          Stop
        </button>
      </form>

      <div className="max-w-md">
        <ScanHistoryPanel
          title="Analyze History"
          items={history}
          onSelect={(value) => {
            setSymbol(value);
            setShouldFetch(false);
            if (analyzeAbortRef.current) {
              analyzeAbortRef.current.abort();
              analyzeAbortRef.current = null;
              setIsAnalyzeRunning(false);
              setActiveAnalyzeSymbol('');
              window.localStorage.removeItem(ANALYZE_RUNNING_KEY);
            }
            setSubmittedSymbol(value);
            const cachedFromQuery = queryClient.getQueryData<AnalyzeApiResponse>(['analyze', value, strategy]);
            if (cachedFromQuery?.success) {
              setRestoredAnalysis(cachedFromQuery);
              return;
            }
            try {
              const raw = window.localStorage.getItem(ANALYZE_RESULTS_CACHE_KEY);
              if (!raw) return;
              const cache = JSON.parse(raw) as AnalyzeResultCache;
              const cached = cache[`${value}:${strategy}`];
              if (cached?.success) {
                setRestoredAnalysis(cached);
              }
            } catch {
              // Ignore invalid cache data
            }
          }}
          onDelete={(id) => setHistory(removeScanHistoryItem(ANALYZE_HISTORY_KEY, id))}
          onClear={() => {
            clearScanHistory(ANALYZE_HISTORY_KEY);
            setHistory([]);
          }}
        />
      </div>

      {/* Loading */}
      {(isFetching || isAnalyzeRunning) && (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
          <p className="mt-4 text-lg font-medium">Analyzing {activeAnalyzeSymbol || submittedSymbol || symbol} in background...</p>
          <p className="text-sm text-muted-foreground">Running 4-Pillar analysis</p>
        </div>
      )}

      {/* Error */}
      {error && !isAbortError && (
        <div className="rounded-xl border border-bear/50 bg-bear/5 p-6 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-bear" />
          <h3 className="mt-4 text-xl font-semibold">Analysis Failed</h3>
          <p className="mt-2 text-muted-foreground">
            {(error as Error).message || 'Could not analyze this stock'}
          </p>
        </div>
      )}

      {/* Results */}
      {(data ?? restoredAnalysis)?.success && (data ?? restoredAnalysis)?.data && (
        <AnalysisContent data={(data ?? restoredAnalysis)!.data} />
      )}

      {/* Empty State */}
      {!isLoading && !(data ?? restoredAnalysis) && !error && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-16">
          <Search className="h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-xl font-semibold">Enter a Stock Symbol</h3>
          <p className="mt-2 text-center text-muted-foreground">
            Type any NEPSE stock symbol above to get a<br />
            comprehensive 4-Pillar analysis with trade setup.
          </p>
        </div>
      )}
    </div>
  );
}

// Content wrapper that reads URL params
function AnalyzePageContent() {
  const searchParams = useSearchParams();
  const initialSymbol = searchParams.get('symbol') || '';
  
  return <AnalyzePageInner initialSymbol={initialSymbol} />;
}

// Main export with Suspense boundary
export default function AnalyzePage() {
  return (
    <Suspense fallback={
      <div className="flex flex-col items-center justify-center py-16">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
        <p className="mt-4 text-lg font-medium">Loading...</p>
      </div>
    }>
      <AnalyzePageContent />
    </Suspense>
  );
}
