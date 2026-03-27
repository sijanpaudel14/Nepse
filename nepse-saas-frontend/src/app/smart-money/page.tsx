'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getSmartMoney, type SmartMoneyResponse } from '@/lib/api';
import { 
  Eye, 
  TrendingUp,
  TrendingDown,
  Building2,
  Zap,
  Target,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  PageSkeleton,
  SectionHeader,
  EmptyState,
  InfoBox,
  VerdictBadge,
  ScanHistoryPanel,
} from '@/components/ui';
import Link from 'next/link';
import {
  loadScanHistory,
  pushScanHistory,
  removeScanHistoryItem,
  clearScanHistory,
  type ScanHistoryItem,
} from '@/lib/scan-history';

// Flow indicator component
function FlowIndicator({ type, size = 'md' }: { type: 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL', size?: 'sm' | 'md' | 'lg' }) {
  const config = {
    ACCUMULATION: { color: 'text-bull', bg: 'bg-bull/10', icon: TrendingUp, label: 'Accumulation' },
    DISTRIBUTION: { color: 'text-bear', bg: 'bg-bear/10', icon: TrendingDown, label: 'Distribution' },
    NEUTRAL: { color: 'text-muted-foreground', bg: 'bg-muted/20', icon: Activity, label: 'Neutral' },
  };
  
  const { color, bg, icon: Icon, label } = config[type];
  const sizeClass = size === 'sm' ? 'text-xs px-2 py-1' : size === 'lg' ? 'text-base px-4 py-2' : 'text-sm px-3 py-1.5';
  
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full font-medium', bg, color, sizeClass)}>
      <Icon className={size === 'sm' ? 'h-3 w-3' : size === 'lg' ? 'h-5 w-5' : 'h-4 w-4'} />
      {label}
    </span>
  );
}

// Stock row component
function StockRow({ stock }: { stock: SmartMoneyResponse['data']['stocks'][0] }) {
  return (
    <Link 
      href={`/analyze?symbol=${stock.symbol}`}
      className="flex items-center gap-4 p-4 rounded-lg border border-border bg-card hover:border-primary hover:bg-card-hover transition-all"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-bold text-primary">{stock.symbol}</span>
          <FlowIndicator type={stock.flow_type} size="sm" />
        </div>
        <p className="text-sm text-muted-foreground truncate">{stock.name}</p>
      </div>
      
      <div className="grid grid-cols-3 gap-4 text-center">
        <div>
          <p className="text-xs text-muted-foreground">Price</p>
          <p className="font-mono text-sm">Rs. {stock.price.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Net Flow</p>
          <p className={cn(
            'font-mono text-sm font-medium',
            stock.net_flow > 0 ? 'text-bull' : stock.net_flow < 0 ? 'text-bear' : 'text-muted-foreground'
          )}>
            {stock.net_flow > 0 ? '+' : ''}{stock.net_flow.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Score</p>
          <p className={cn(
            'font-mono text-sm font-bold',
            stock.smart_money_score >= 70 ? 'text-bull' : stock.smart_money_score >= 40 ? 'text-warning' : 'text-bear'
          )}>
            {stock.smart_money_score}
          </p>
        </div>
      </div>
      
      <ArrowUpRight className="h-5 w-5 text-muted-foreground" />
    </Link>
  );
}

// Broker card
function BrokerCard({ broker, rank }: { broker: SmartMoneyResponse['data']['top_buyers'][0], rank: number }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/10">
      <span className="w-6 h-6 flex items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold">
        {rank}
      </span>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate">{broker.name}</p>
        <p className="text-xs text-muted-foreground">{broker.stock_count} stocks</p>
      </div>
      <div className="text-right">
        <p className={cn(
          'text-sm font-bold',
          broker.net_volume > 0 ? 'text-bull' : 'text-bear'
        )}>
          {broker.net_volume > 0 ? '+' : ''}{(broker.net_volume / 1000).toFixed(0)}K
        </p>
        <p className="text-xs text-muted-foreground">shares</p>
      </div>
    </div>
  );
}

export default function SmartMoneyPage() {
  const STORAGE_KEY = 'nepse-smart-money-ui-v1';
  const HISTORY_KEY = 'nepse-smart-money-history-v1';
  const [sector, setSector] = useState('');
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (typeof parsed.sector === 'string') setSector(parsed.sector);
    } catch {
      // ignore invalid storage
    }
  }, []);

  useEffect(() => {
    setHistory(loadScanHistory(HISTORY_KEY));
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ sector }));
  }, [sector]);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['smart-money', sector],
    queryFn: () => getSmartMoney({ sector: sector || undefined }),
    retry: 1,
    staleTime: 5 * 60 * 1000,
  });

  const result = data?.data;

  const sectors = [
    { value: '', label: 'All Sectors' },
    { value: 'hydro', label: 'Hydropower' },
    { value: 'bank', label: 'Banking' },
    { value: 'finance', label: 'Finance' },
    { value: 'microfinance', label: 'Microfinance' },
    { value: 'life_insurance', label: 'Life Insurance' },
    { value: 'non_life_insurance', label: 'Non-Life Insurance' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Eye className="h-6 w-6 text-primary" />
            Smart Money Tracker
          </h1>
          <p className="text-muted-foreground mt-1">
            Track institutional buying and selling patterns to follow the smart money
          </p>
        </div>
        
        <button
          onClick={() => {
            setHistory(
              pushScanHistory(HISTORY_KEY, {
                label: `Smart Money | ${sector || 'All sectors'}`,
                value: sector,
              })
            );
            refetch();
          }}
          disabled={isLoading}
          className="btn-secondary mr-24"
        >
          {isLoading ? (
            <Activity className="h-4 w-4 animate-spin" />
          ) : (
            'Refresh'
          )}
        </button>
      </div>

      {/* Sector Filter */}
      <div className="flex flex-wrap gap-2">
        {sectors.map((s) => (
          <button
            key={s.value}
            onClick={() => {
              setSector(s.value);
              setHistory(
                pushScanHistory(HISTORY_KEY, {
                  label: `Smart Money | ${s.label}`,
                  value: s.value,
                })
              );
            }}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              sector === s.value 
                ? 'bg-primary text-primary-foreground' 
                : 'bg-muted/20 text-muted-foreground hover:text-foreground hover:bg-muted/40'
            )}
          >
            {s.label}
          </button>
        ))}
      </div>
      <div className="max-w-xl">
        <ScanHistoryPanel
          title="Smart Money History"
          items={history}
          onSelect={(value) => {
            setSector(value);
            setTimeout(() => refetch(), 0);
          }}
          onDelete={(id) => setHistory(removeScanHistoryItem(HISTORY_KEY, id))}
          onClear={() => {
            clearScanHistory(HISTORY_KEY);
            setHistory([]);
          }}
        />
      </div>

      {/* Loading State */}
      {isLoading && <PageSkeleton />}

      {/* Error State */}
      {isError && (
        <InfoBox title="Error" variant="error">
          {(error as Error)?.message || 'Failed to load smart money data. Please try again.'}
        </InfoBox>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Summary Stats */}
          <div className="grid md:grid-cols-4 gap-4">
            <div className="rounded-xl border border-bull/30 bg-bull/10 p-4">
              <p className="text-sm text-muted-foreground">Accumulation Stocks</p>
              <p className="text-2xl font-bold text-bull">{result.summary.accumulating}</p>
            </div>
            <div className="rounded-xl border border-bear/30 bg-bear/10 p-4">
              <p className="text-sm text-muted-foreground">Distribution Stocks</p>
              <p className="text-2xl font-bold text-bear">{result.summary.distributing}</p>
            </div>
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Net Market Flow</p>
              <p className={cn(
                'text-2xl font-bold',
                result.summary.net_market_flow > 0 ? 'text-bull' : 'text-bear'
              )}>
                {result.summary.net_market_flow > 0 ? '+' : ''}{(result.summary.net_market_flow / 1000000).toFixed(1)}M
              </p>
            </div>
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Market Sentiment</p>
              <FlowIndicator type={result.summary.sentiment} size="lg" />
            </div>
          </div>

          {/* Top Brokers */}
          <div className="grid md:grid-cols-2 gap-6">
            <div className="rounded-xl border border-bull/20 bg-card p-5">
              <SectionHeader title="Top Buyers (Aggressive Accumulation)" />
              <div className="space-y-2">
                {result.top_buyers.map((broker, i) => (
                  <BrokerCard key={i} broker={broker} rank={i + 1} />
                ))}
              </div>
            </div>
            
            <div className="rounded-xl border border-bear/20 bg-card p-5">
              <SectionHeader title="Top Sellers (Distribution)" />
              <div className="space-y-2">
                {result.top_sellers.map((broker, i) => (
                  <BrokerCard key={i} broker={broker} rank={i + 1} />
                ))}
              </div>
            </div>
          </div>

          {/* Stocks Under Accumulation */}
          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader title="Stocks Under Smart Money Accumulation" />
            <div className="space-y-2">
              {result.stocks
                .filter(s => s.flow_type === 'ACCUMULATION')
                .slice(0, 10)
                .map((stock, i) => (
                  <StockRow key={i} stock={stock} />
                ))}
              {result.stocks.filter(s => s.flow_type === 'ACCUMULATION').length === 0 && (
                <p className="text-center text-muted-foreground py-8">
                  No significant accumulation detected in this sector
                </p>
              )}
            </div>
          </div>

          {/* Stocks Under Distribution */}
          <div className="rounded-xl border border-border bg-card p-5">
            <SectionHeader title="Stocks Under Distribution (Caution)" />
            <div className="space-y-2">
              {result.stocks
                .filter(s => s.flow_type === 'DISTRIBUTION')
                .slice(0, 10)
                .map((stock, i) => (
                  <StockRow key={i} stock={stock} />
                ))}
              {result.stocks.filter(s => s.flow_type === 'DISTRIBUTION').length === 0 && (
                <p className="text-center text-muted-foreground py-8">
                  No significant distribution detected in this sector
                </p>
              )}
            </div>
          </div>
        </>
      )}

      {/* Info Box */}
      <InfoBox title="What is Smart Money?" variant="info">
        <p>
          &quot;Smart money&quot; refers to institutional investors and large brokers who often have better 
          information and analysis. By tracking their buying (accumulation) and selling (distribution) 
          patterns, retail traders can identify potential opportunities before the crowd.
        </p>
        <ul className="mt-2 space-y-1 text-sm">
          <li>• <strong>Accumulation:</strong> Large buyers quietly building positions = potential uptrend</li>
          <li>• <strong>Distribution:</strong> Large sellers offloading = potential downtrend</li>
          <li>• <strong>Net Flow:</strong> Total buy volume - Total sell volume</li>
        </ul>
      </InfoBox>
    </div>
  );
}
