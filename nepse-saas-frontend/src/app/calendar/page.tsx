'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getTradingCalendar, type CalendarResponse } from '@/lib/api';
import { 
  Calendar, 
  ChevronLeft,
  ChevronRight,
  Target,
  Shield,
  TrendingUp,
  Clock,
  Filter,
  Activity,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  PageSkeleton,
  SectionHeader,
  EmptyState,
  InfoBox,
  ScoreCircle,
  PrettySelect,
  ScanHistoryPanel,
} from '@/components/ui';
import {
  loadScanHistory,
  pushScanHistory,
  removeScanHistoryItem,
  clearScanHistory,
  type ScanHistoryItem,
} from '@/lib/scan-history';
import Link from 'next/link';

// Stock card in calendar
function CalendarStockCard({ stock }: { stock: CalendarResponse['data']['calendar'][0]['stocks'][0] }) {
  return (
    <Link 
      href={`/signal?symbol=${stock.symbol}`}
      className="block rounded-lg border border-border bg-card p-3 hover:border-primary hover:bg-card-hover transition-all"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="font-bold text-primary">{stock.symbol}</p>
          <p className="text-xs text-muted-foreground truncate max-w-[120px]">{stock.name}</p>
        </div>
        <ScoreCircle score={stock.confidence} size="sm" />
      </div>
      
      <div className="mt-2 space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Entry</span>
          <span className="font-mono">Rs. {stock.entry_price.toLocaleString()}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Target</span>
          <span className="font-mono text-bull">Rs. {stock.target_price.toLocaleString()}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Stop</span>
          <span className="font-mono text-bear">Rs. {stock.stop_loss.toLocaleString()}</span>
        </div>
      </div>
      
      <p className="mt-2 text-xs text-muted-foreground line-clamp-2">{stock.reason}</p>
      
      <div className="mt-2 text-xs text-muted-foreground bg-muted/20 rounded px-2 py-1">
        {stock.sector}
      </div>
    </Link>
  );
}

// Day column in calendar
function CalendarDay({ day }: { day: CalendarResponse['data']['calendar'][0] }) {
  const isToday = day.date === new Date().toISOString().split('T')[0];
  const hasStocks = day.stocks.length > 0;
  
  return (
    <div className={cn(
      'rounded-xl border p-4 min-h-[200px]',
      isToday ? 'border-primary bg-primary/5' : 'border-border bg-card',
      !hasStocks && 'opacity-60'
    )}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className={cn(
            'text-sm font-medium',
            isToday ? 'text-primary' : 'text-foreground'
          )}>
            {day.day_name}
          </p>
          <p className="text-xs text-muted-foreground">{day.date}</p>
        </div>
        {isToday && (
          <span className="rounded-full bg-primary px-2 py-0.5 text-[10px] font-bold text-primary-foreground">
            TODAY
          </span>
        )}
      </div>
      
      {hasStocks ? (
        <div className="space-y-2">
          {day.stocks.map((stock, i) => (
            <CalendarStockCard key={i} stock={stock} />
          ))}
        </div>
      ) : (
        <div className="flex items-center justify-center h-24 text-muted-foreground text-sm">
          No picks for this day
        </div>
      )}
    </div>
  );
}

export default function CalendarPage() {
  const STORAGE_KEY = 'nepse-calendar-ui-v1';
  const HISTORY_KEY = 'nepse-calendar-history-v1';
  const [days, setDays] = useState(14);
  const [sector, setSector] = useState('');
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (typeof parsed.days === 'number' && [7, 14, 30].includes(parsed.days)) setDays(parsed.days);
      if (typeof parsed.sector === 'string') setSector(parsed.sector);
    } catch {
      // ignore invalid storage
    }
  }, []);

  useEffect(() => {
    setHistory(loadScanHistory(HISTORY_KEY));
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ days, sector }));
  }, [days, sector]);

  useEffect(() => {
    setHistory(
      pushScanHistory(HISTORY_KEY, {
        label: `Calendar | ${days}d | ${sector || 'All sectors'}`,
        value: JSON.stringify({ days, sector }),
      })
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['trading-calendar', days, sector],
    queryFn: () => getTradingCalendar({ days, sector: sector || undefined }),
    retry: 1,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  const calendar = data?.data;

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
            <Calendar className="h-6 w-6 text-primary" />
            Trading Calendar
          </h1>
          <p className="text-muted-foreground mt-1">
            See which stocks to buy on which dates for the next {days} days
          </p>
        </div>
        
        <button
          onClick={() => refetch()}
          disabled={isLoading}
          className="btn-secondary"
        >
          {isLoading ? (
            <Activity className="h-4 w-4 animate-spin" />
          ) : (
            'Refresh'
          )}
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        {/* Days Selector */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Show:</span>
          <div className="flex rounded-lg border border-border bg-card p-1">
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={cn(
                  'px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
                  days === d 
                    ? 'bg-primary text-primary-foreground' 
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {d} days
              </button>
            ))}
          </div>
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
      </div>
      <div className="max-w-xl">
        <ScanHistoryPanel
          title="Calendar Scan History"
          items={history}
          onSelect={(value) => {
            try {
              const parsed = JSON.parse(value) as { days: number; sector: string };
              if (typeof parsed.days === 'number' && [7, 14, 30].includes(parsed.days)) setDays(parsed.days);
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

      {/* Calendar Stats */}
      {calendar && (
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Scan Date</p>
            <p className="text-lg font-semibold">{calendar.scan_date}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Days Ahead</p>
            <p className="text-lg font-semibold">{calendar.days_ahead} days</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Total Opportunities</p>
            <p className="text-lg font-semibold">{calendar.total_stocks} stocks</p>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && <PageSkeleton />}

      {/* Error State */}
      {isError && (
        <InfoBox title="Error" variant="error">
          {(error as Error)?.message || 'Failed to load calendar. Please try again.'}
        </InfoBox>
      )}

      {/* Calendar Grid */}
      {calendar && calendar.calendar.length > 0 && (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {calendar.calendar.map((day, i) => (
            <CalendarDay key={i} day={day} />
          ))}
        </div>
      )}

      {calendar && calendar.calendar.length === 0 && (
        <EmptyState
          icon={Calendar}
          title="No Opportunities Found"
          description="No trading opportunities detected for the selected period and sector. Try expanding your filters."
        />
      )}

      {/* Legend */}
      <div className="rounded-xl border border-border bg-card p-4">
        <SectionHeader title="How to Read the Calendar" />
        <div className="grid md:grid-cols-3 gap-4 text-sm">
          <div className="flex items-start gap-2">
            <ScoreCircle score={80} size="sm" />
            <div>
              <p className="font-medium">Confidence Score</p>
              <p className="text-muted-foreground">Higher = stronger setup. Look for 60+</p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <div className="rounded bg-bull/20 p-2">
              <Target className="h-4 w-4 text-bull" />
            </div>
            <div>
              <p className="font-medium">Entry Price</p>
              <p className="text-muted-foreground">Buy at or below this price</p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <div className="rounded bg-bear/20 p-2">
              <Shield className="h-4 w-4 text-bear" />
            </div>
            <div>
              <p className="font-medium">Stop Loss</p>
              <p className="text-muted-foreground">Exit if price drops below this</p>
            </div>
          </div>
        </div>
        
        <p className="mt-4 text-xs text-muted-foreground">
          Click any stock card to see the full trading signal with detailed entry and exit timing.
        </p>
      </div>

      {/* Disclaimer */}
      <div className="rounded-lg bg-muted/20 p-4 text-center text-sm text-muted-foreground">
        <Clock className="h-4 w-4 inline mr-1" />
        Calendar updates daily. Past dates are estimates based on historical patterns. Always verify before trading.
      </div>
    </div>
  );
}
