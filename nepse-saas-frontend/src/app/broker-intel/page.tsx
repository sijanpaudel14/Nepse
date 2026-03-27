'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBrokerIntelligence, type BrokerIntelligenceResponse } from '@/lib/api';
import { 
  Users, 
  TrendingUp,
  TrendingDown,
  Activity,
  Building2,
  Target,
  AlertTriangle,
  ChevronRight,
  RefreshCw,
  Filter,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { ScanHistoryPanel, PrettySelect } from '@/components/ui';
import {
  loadScanHistory,
  pushScanHistory,
  removeScanHistoryItem,
  clearScanHistory,
  type ScanHistoryItem,
} from '@/lib/scan-history';

// Broker card
function BrokerCard({ 
  broker,
  rank,
}: { 
  broker: {
    name: string;
    activity: 'ACCUMULATING' | 'DISTRIBUTING';
    volume: number;
    value: number;
    top_stocks: string[];
  };
  rank: number;
}) {
  const isAccumulating = broker.activity === 'ACCUMULATING';
  
  return (
    <div className={cn(
      'rounded-xl border p-4 hover:shadow-card-hover transition-all',
      isAccumulating ? 'border-bull/30 bg-bull/10' : 'border-bear/30 bg-bear/10'
    )}>
      <div className="flex items-start gap-3 mb-3">
        <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center text-primary font-bold">
          {rank}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold truncate">{broker.name}</p>
          <p className="text-xs text-muted-foreground">
            {(broker.value / 1000000).toFixed(1)}M value
          </p>
        </div>
        <span className={cn(
          'px-2 py-0.5 rounded text-xs font-semibold',
          isAccumulating ? 'bg-bull/20 text-bull' : 'bg-bear/20 text-bear'
        )}>
          {broker.activity}
        </span>
      </div>
      
      <div className="flex items-center gap-3 mb-3">
        {isAccumulating ? (
          <TrendingUp className="h-4 w-4 text-bull" />
        ) : (
          <TrendingDown className="h-4 w-4 text-bear" />
        )}
        <p className={cn(
          'font-mono text-lg font-bold',
          isAccumulating ? 'text-bull' : 'text-bear'
        )}>
          {(broker.volume / 1000).toFixed(0)}K shares
        </p>
      </div>
      
      {broker.top_stocks.length > 0 && (
        <div className="border-t border-border/50 pt-2">
          <p className="text-xs text-muted-foreground mb-1">Top Stocks</p>
          <div className="flex flex-wrap gap-1">
            {broker.top_stocks.map((symbol, i) => (
              <Link 
                key={i} 
                href={`/analyze?symbol=${symbol}`}
                className="px-1.5 py-0.5 bg-muted/20 rounded text-xs hover:bg-muted/40 transition-colors"
              >
                {symbol}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Stock table row
function StockRow({ 
  stock,
}: { 
  stock: {
    symbol: string;
    net_flow: number;
    buy_brokers: number;
    sell_brokers: number;
    concentration: 'HIGH' | 'MEDIUM' | 'LOW';
  };
}) {
  const concentrationConfig = {
    HIGH: { bg: 'bg-warning/20', text: 'text-warning' },
    MEDIUM: { bg: 'bg-muted/20', text: 'text-muted-foreground' },
    LOW: { bg: 'bg-muted/10', text: 'text-muted' },
  };
  
  const config = concentrationConfig[stock.concentration];
  
  return (
    <Link 
      href={`/analyze?symbol=${stock.symbol}`}
      className="flex items-center gap-4 px-3 py-2 hover:bg-muted/10 transition-colors"
    >
      <div className="w-20 font-semibold">{stock.symbol}</div>
      <div className="w-24 text-center">
        <span className="text-bull">{stock.buy_brokers}</span>
        <span className="text-muted-foreground mx-1">vs</span>
        <span className="text-bear">{stock.sell_brokers}</span>
      </div>
      <div className={cn(
        'w-24 text-right font-mono',
        stock.net_flow > 0 ? 'text-bull' : 'text-bear'
      )}>
        {stock.net_flow > 0 ? '+' : ''}{stock.net_flow.toLocaleString()}
      </div>
      <div className="w-20">
        <span className={cn('px-2 py-0.5 rounded text-xs', config.bg, config.text)}>
          {stock.concentration}
        </span>
      </div>
      <ChevronRight className="h-4 w-4 text-muted-foreground ml-auto" />
    </Link>
  );
}

export default function BrokerIntelPage() {
  const STORAGE_KEY = 'nepse-broker-intel-ui-v1';
  const HISTORY_KEY = 'nepse-broker-intel-history-v1';
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);
  const [sector, setSector] = useState('');

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

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['broker-intelligence', sector],
    queryFn: () => getBrokerIntelligence({ sector: sector || undefined }),
    retry: 1,
    staleTime: 5 * 60 * 1000,
  });

  const result = data?.data;

  const sectors = [
    { value: '', label: 'All Sectors' },
    { value: 'hydro', label: 'Hydropower' },
    { value: 'bank', label: 'Banking' },
    { value: 'commercial', label: 'Commercial Banks' },
    { value: 'finance', label: 'Finance' },
    { value: 'microfinance', label: 'Microfinance' },
    { value: 'life', label: 'Life Insurance' },
    { value: 'non_life', label: 'Non-Life Insurance' },
    { value: 'hotel', label: 'Hotels & Tourism' },
    { value: 'manufacturing', label: 'Manufacturing' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Users className="h-6 w-6 text-primary" />
            Broker Intelligence
          </h1>
          <p className="text-muted-foreground mt-1">
            Track aggressive broker activity and stock concentration patterns
          </p>
        </div>
        <button
          onClick={() => {
            setHistory(
              pushScanHistory(HISTORY_KEY, {
                label: `Broker Intel | ${sector || 'All sectors'}`,
                value: JSON.stringify({ sector }),
              })
            );
            refetch();
          }}
          disabled={isFetching}
          className="btn-secondary mr-24"
        >
          {isFetching ? <Activity className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </button>
      </div>

      {/* Sector Filter */}
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <PrettySelect
          value={sector}
          onChange={setSector}
          options={sectors}
          className="min-w-[240px]"
        />
      </div>

      <div className="max-w-xl">
        <ScanHistoryPanel
          title="Broker Intelligence History"
          items={history}
          onSelect={(value) => {
            try {
              const parsed = JSON.parse(value) as { sector: string };
              if (typeof parsed.sector === 'string') setSector(parsed.sector);
              setTimeout(() => refetch(), 0);
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

      {/* Loading */}
      {isLoading && (
        <div className="animate-pulse space-y-4">
          <div className="grid md:grid-cols-4 gap-4">
            {[1,2,3,4].map(i => <div key={i} className="h-24 bg-muted/20 rounded-xl" />)}
          </div>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-xl border border-bear/30 bg-bear/10 p-6 text-center">
          <p className="text-bear font-medium">{(error as Error)?.message || 'Failed to load broker data'}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Summary Stats */}
          <div className="grid md:grid-cols-4 gap-4">
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Active Brokers</p>
              <p className="text-2xl font-bold">{result.summary.active_brokers}</p>
            </div>
            <div className="rounded-xl border border-bull/30 bg-bull/10 p-4">
              <p className="text-sm text-muted-foreground">Accumulating</p>
              <p className="text-2xl font-bold text-bull">{result.summary.accumulating}</p>
            </div>
            <div className="rounded-xl border border-bear/30 bg-bear/10 p-4">
              <p className="text-sm text-muted-foreground">Distributing</p>
              <p className="text-2xl font-bold text-bear">{result.summary.distributing}</p>
            </div>
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">Market Sentiment</p>
              <p className={cn(
                'text-xl font-bold',
                result.summary.market_sentiment === 'BULLISH' ? 'text-bull' :
                result.summary.market_sentiment === 'BEARISH' ? 'text-bear' : 'text-muted-foreground'
              )}>
                {result.summary.market_sentiment}
              </p>
            </div>
          </div>

          {/* Broker Cards */}
          {result.brokers.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-warning" />
                Active Broker Flow
              </h2>
              <div className="grid md:grid-cols-3 gap-4">
                {result.brokers.map((broker, i) => (
                  <BrokerCard key={i} broker={broker} rank={i + 1} />
                ))}
              </div>
            </div>
          )}

          {/* Stock-wise Table */}
          {result.stockwise.length > 0 && (
            <div className="rounded-xl border border-border bg-card">
              <div className="p-4 border-b border-border">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <Building2 className="h-5 w-5 text-primary" />
                  Stock Concentration
                </h2>
              </div>
              <div className="divide-y divide-border/50">
                <div className="flex items-center gap-4 px-3 py-2 bg-muted/10 text-xs font-semibold text-muted-foreground">
                  <div className="w-20">Symbol</div>
                  <div className="w-24 text-center">Buy vs Sell</div>
                  <div className="w-24 text-right">Net Flow</div>
                  <div className="w-20">Concentration</div>
                  <div className="flex-1" />
                </div>
                {result.stockwise.map((stock, i) => (
                  <StockRow key={i} stock={stock} />
                ))}
              </div>
            </div>
          )}

          {/* Empty State */}
          {result.brokers.length === 0 && result.stockwise.length === 0 && (
            <div className="rounded-xl border border-border bg-card p-12 text-center">
              <Users className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold">No Broker Data Available</h3>
              <p className="text-muted-foreground mt-2">
                Broker intelligence data is not available at this time.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
