'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBulkDeals, type BulkDealsResponse } from '@/lib/api';
import { 
  AlertTriangle, 
  TrendingUp,
  TrendingDown,
  Activity,
  Building2,
  Users,
  Banknote,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { ScanHistoryPanel } from '@/components/ui';
import {
  loadScanHistory,
  pushScanHistory,
  removeScanHistoryItem,
  clearScanHistory,
  type ScanHistoryItem,
} from '@/lib/scan-history';

// Deal card
function DealCard({ 
  deal,
}: { 
  deal: {
    symbol: string;
    name: string;
    quantity: number;
    price: number;
    value: number;
    deal_type: 'BUY' | 'SELL';
    buyer_broker?: string;
    seller_broker?: string;
    date: string;
    significance: 'HIGH' | 'MEDIUM' | 'LOW';
  };
}) {
  const isBuy = deal.deal_type === 'BUY';
  
  return (
    <Link 
      href={`/analyze?symbol=${deal.symbol}`}
      className={cn(
        'block rounded-xl border p-4 transition-all hover:shadow-card-hover',
        isBuy ? 'border-bull/30 bg-bull/5 hover:border-bull/50' : 'border-bear/30 bg-bear/5 hover:border-bear/50'
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={cn(
            'p-2 rounded-lg',
            isBuy ? 'bg-bull/20' : 'bg-bear/20'
          )}>
            {isBuy ? <TrendingUp className="h-5 w-5 text-bull" /> : <TrendingDown className="h-5 w-5 text-bear" />}
          </div>
          <div>
            <p className="font-bold text-lg">{deal.symbol}</p>
            <p className="text-xs text-muted-foreground truncate max-w-[200px]">{deal.name}</p>
          </div>
        </div>
        <div className={cn(
          'px-2 py-1 rounded text-xs font-semibold',
          deal.significance === 'HIGH' ? 'bg-warning/20 text-warning' : 
          deal.significance === 'MEDIUM' ? 'bg-muted/20 text-muted-foreground' : 'bg-muted/10 text-muted'
        )}>
          {deal.significance}
        </div>
      </div>
      
      <div className="grid grid-cols-3 gap-3 mb-3 text-center">
        <div>
          <p className="text-xs text-muted-foreground">Quantity</p>
          <p className="font-mono font-semibold">{deal.quantity.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Price</p>
          <p className="font-mono font-semibold">Rs. {deal.price.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Value</p>
          <p className="font-mono font-semibold text-primary">
            {(deal.value / 10000000).toFixed(1)} Cr
          </p>
        </div>
      </div>
      
      <div className="flex items-center justify-between text-xs text-muted-foreground border-t border-border/50 pt-3">
        <div className="flex items-center gap-1">
          <Users className="h-3 w-3" />
          <span className="truncate max-w-[150px]">
            {isBuy ? deal.buyer_broker : deal.seller_broker}
          </span>
        </div>
        <span>{deal.date}</span>
        <ChevronRight className="h-4 w-4" />
      </div>
    </Link>
  );
}

// Summary stat
function StatCard({ 
  label, 
  value, 
  subValue,
  icon: Icon,
  variant = 'default',
}: { 
  label: string;
  value: string | number;
  subValue?: string;
  icon: React.ElementType;
  variant?: 'default' | 'bull' | 'bear';
}) {
  const variants = {
    default: 'border-border bg-card',
    bull: 'border-bull/30 bg-bull/10',
    bear: 'border-bear/30 bg-bear/10',
  };
  
  return (
    <div className={cn('rounded-xl border p-4', variants[variant])}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {subValue && <p className="text-xs text-muted-foreground mt-1">{subValue}</p>}
        </div>
        <div className="p-2 rounded-lg bg-muted/20">
          <Icon className="h-5 w-5 text-muted-foreground" />
        </div>
      </div>
    </div>
  );
}

export default function BulkDealsPage() {
  const HISTORY_KEY = 'nepse-bulk-deals-history-v1';
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);

  useEffect(() => {
    setHistory(loadScanHistory(HISTORY_KEY));
  }, []);

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['bulk-deals'],
    queryFn: () => getBulkDeals(),
    retry: 1,
    staleTime: 5 * 60 * 1000,
  });

  const result = data?.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <AlertTriangle className="h-6 w-6 text-warning" />
            Bulk Deals
          </h1>
          <p className="text-muted-foreground mt-1">
            Large block trades (&gt;1 Cr value or 10K+ shares) - insider and promoter activity
          </p>
        </div>
        <button
          onClick={() => {
            setHistory(
              pushScanHistory(HISTORY_KEY, {
                label: 'Bulk Deals Refresh',
                value: 'refresh',
              })
            );
            refetch();
          }}
          disabled={isFetching}
          className="btn-secondary mr-24"
        >
          {isLoading ? <Activity className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </button>
      </div>
      <div className="max-w-xl">
        <ScanHistoryPanel
          title="Bulk Deals History"
          items={history}
          onSelect={() => refetch()}
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
          <div className="grid md:grid-cols-2 gap-4">
            {[1,2,3,4].map(i => <div key={i} className="h-40 bg-muted/20 rounded-xl" />)}
          </div>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-xl border border-bear/30 bg-bear/10 p-6 text-center">
          <p className="text-bear font-medium">{(error as Error)?.message || 'Failed to load bulk deals'}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Summary Stats */}
          <div className="grid md:grid-cols-4 gap-4">
            <StatCard 
              label="Total Deals Today"
              value={result.summary.total_deals}
              icon={AlertTriangle}
            />
            <StatCard 
              label="Buy Side"
              value={result.summary.buy_deals}
              subValue={`${(result.summary.buy_value / 10000000).toFixed(1)} Cr`}
              icon={TrendingUp}
              variant="bull"
            />
            <StatCard 
              label="Sell Side"
              value={result.summary.sell_deals}
              subValue={`${(result.summary.sell_value / 10000000).toFixed(1)} Cr`}
              icon={TrendingDown}
              variant="bear"
            />
            <StatCard 
              label="Total Value"
              value={`${(result.summary.total_value / 10000000).toFixed(1)} Cr`}
              icon={Banknote}
            />
          </div>

          {/* High Significance Deals */}
          {result.deals.filter(d => d.significance === 'HIGH').length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-warning" />
                High Significance Deals
              </h2>
              <div className="grid md:grid-cols-2 gap-4">
                {result.deals.filter(d => d.significance === 'HIGH').map((deal, i) => (
                  <DealCard key={i} deal={deal} />
                ))}
              </div>
            </div>
          )}

          {/* All Deals */}
          <div>
            <h2 className="text-lg font-semibold mb-4">All Bulk Deals</h2>
            <div className="grid md:grid-cols-2 gap-4">
              {result.deals.map((deal, i) => (
                <DealCard key={i} deal={deal} />
              ))}
            </div>
            
            {result.deals.length === 0 && (
              <div className="rounded-xl border border-border bg-card p-12 text-center">
                <AlertTriangle className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold">No Bulk Deals Today</h3>
                <p className="text-muted-foreground mt-2">
                  No large block trades detected in today&apos;s session.
                </p>
              </div>
            )}
          </div>

          {/* Info */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h3 className="font-semibold mb-2">What are Bulk Deals?</h3>
            <p className="text-sm text-muted-foreground">
              Bulk deals are large trades that exceed normal transaction limits. They often indicate 
              promoter buying/selling, institutional positioning, or stake changes. High-significance 
              deals may signal important corporate developments.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
