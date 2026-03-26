'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { runStealthScan, type SectorRotation, type StealthStock } from '@/lib/api';
import { 
  Radar,
  Loader2,
  AlertTriangle,
  TrendingUp,
  Eye,
  ChevronDown,
  Flame,
  ThermometerSun,
  Activity,
  Info,
  ArrowDown,
  ArrowUp,
  Shield,
} from 'lucide-react';
import { cn, formatCurrency, formatPercent } from '@/lib/utils';
import { PrettySelect, ScanHistoryPanel } from '@/components/ui';
import {
  loadScanHistory,
  pushScanHistory,
  removeScanHistoryItem,
  clearScanHistory,
  type ScanHistoryItem,
} from '@/lib/scan-history';
import Link from 'next/link';

// Heat indicator for sectors
function SectorHeatBadge({ stockCount }: { stockCount: number }) {
  if (stockCount >= 5) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-bear/20 px-2.5 py-0.5 text-xs font-bold text-bear">
        <Flame className="h-3.5 w-3.5" />
        <Flame className="h-3.5 w-3.5 -ml-2" />
        <Flame className="h-3.5 w-3.5 -ml-2" />
        HOT
      </span>
    );
  } else if (stockCount >= 3) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-warning/20 px-2.5 py-0.5 text-xs font-bold text-warning">
        <ThermometerSun className="h-3.5 w-3.5" />
        WARM
      </span>
    );
  } else {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/20 px-2.5 py-0.5 text-xs font-bold text-primary">
        <Activity className="h-3.5 w-3.5" />
        ACTIVE
      </span>
    );
  }
}

// Progress bar for scores
function ScoreBar({ 
  score, 
  maxScore, 
  label,
  color = 'primary',
}: { 
  score: number; 
  maxScore: number;
  label: string;
  color?: 'primary' | 'bull' | 'bear';
}) {
  const percentage = (score / maxScore) * 100;
  const colorClass = {
    primary: 'bg-primary',
    bull: 'bg-bull',
    bear: 'bg-bear',
  }[color];

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono font-medium">{percentage.toFixed(0)}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-background">
        <div
          className={cn('h-full rounded-full transition-all', colorClass)}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

// Sector Card with collapsible stock list
function SectorCard({ sector }: { sector: SectorRotation }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-card-hover transition-colors"
      >
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-xl">
            <Flame className={cn(
              'h-6 w-6',
              sector.stock_count >= 5 ? 'text-bear' :
              sector.stock_count >= 3 ? 'text-warning' : 'text-primary'
            )} />
          </div>
          <div className="text-left">
            <h3 className="text-lg font-bold">{sector.sector}</h3>
            <p className="text-sm text-muted-foreground">
              {sector.stock_count} stocks accumulating
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <SectorHeatBadge stockCount={sector.stock_count} />
          <ChevronDown className={cn(
            'h-5 w-5 text-muted-foreground transition-transform',
            expanded && 'rotate-180'
          )} />
        </div>
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="border-t border-border">
          {/* Average Score */}
          <div className="p-4 border-b border-border bg-card-hover">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Avg Broker Score:</span>
                <span className="ml-2 font-mono font-semibold text-bull">
                  {sector.avg_broker_score.toFixed(1)}%
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Stealth Level:</span>
                <span className={cn(
                  'ml-2 font-semibold',
                  sector.stock_count >= 5 ? 'text-bear' :
                  sector.stock_count >= 3 ? 'text-warning' : 'text-bull'
                )}>
                  {sector.stock_count >= 5 ? 'HEAVY' :
                   sector.stock_count >= 3 ? 'MODERATE' : 'LIGHT'}
                </span>
              </div>
            </div>
          </div>

          {/* Stock List */}
          <div className="divide-y divide-border">
            {sector.stocks.map((stock) => (
              <StealthStockRow key={stock.symbol} stock={stock} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Individual stock row
function StealthStockRow({ stock }: { stock: StealthStock }) {
  return (
    <div className="p-4 hover:bg-card-hover transition-colors">
      <div className="flex items-center justify-between mb-3">
        <Link
          href={`/analyze?symbol=${stock.symbol}`}
          className="font-mono text-lg font-bold text-primary hover:underline"
        >
          {stock.symbol}
        </Link>
        <span className="font-mono font-semibold">{formatCurrency(stock.ltp)}</span>
      </div>
      
      <div className="grid grid-cols-2 gap-3">
        <ScoreBar
          label="Broker Score (Target: >80%)"
          score={stock.broker_score_pct}
          maxScore={100}
          color="bull"
        />
        <ScoreBar
          label="Technical Score (Target: <40%)"
          score={stock.technical_score_pct}
          maxScore={100}
          color={stock.technical_score_pct < 40 ? 'bull' : 'bear'}
        />
      </div>

      <div className="mt-3 flex items-center justify-between text-sm">
        <div className="flex items-center gap-4">
          <span className="text-muted-foreground">
            Distribution Risk: <span className={cn(
              'font-medium',
              stock.distribution_risk === 'LOW' ? 'text-bull' :
              stock.distribution_risk === 'MEDIUM' ? 'text-warning' : 'text-bear'
            )}>{stock.distribution_risk}</span>
          </span>
          <span className="text-muted-foreground">
            Buyer Dominance: <span className={cn(
              'font-mono font-medium',
              stock.buyer_dominance > 50 ? 'text-bull' : 'text-bear'
            )}>{stock.buyer_dominance.toFixed(1)}%</span>
          </span>
        </div>
        <Link
          href={`/analyze?symbol=${stock.symbol}`}
          className="flex items-center gap-1 text-primary hover:underline"
        >
          <Eye className="h-4 w-4" />
          Analyze
        </Link>
      </div>
    </div>
  );
}

export default function StealthPage() {
  const STORAGE_KEY = 'nepse-stealth-ui-v1';
  const HISTORY_KEY = 'nepse-stealth-history-v1';
  const [sector, setSector] = useState('');
  const stealthAbortRef = useRef<AbortController | null>(null);
  const [isStealthRunning, setIsStealthRunning] = useState(false);
  const [history, setHistory] = useState<ScanHistoryItem[]>([]);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['stealth-scan', sector],
    queryFn: async () => {
      const controller = new AbortController();
      stealthAbortRef.current = controller;
      setIsStealthRunning(true);
      try {
        return await runStealthScan({ sector: sector || undefined }, controller.signal);
      } finally {
        setIsStealthRunning(false);
        stealthAbortRef.current = null;
      }
    },
    enabled: false,
  });

  useEffect(() => {
    setHistory(loadScanHistory(HISTORY_KEY));
  }, []);

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
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ sector }));
  }, [sector]);

  const handleScan = () => {
    setHistory(
      pushScanHistory(HISTORY_KEY, {
        label: `Stealth | ${sector || 'All sectors'}`,
        value: JSON.stringify({ sector }),
      })
    );
    refetch();
  };

  const handleStop = () => {
    if (stealthAbortRef.current) {
      stealthAbortRef.current.abort();
      stealthAbortRef.current = null;
      setIsStealthRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
          <Radar className="h-8 w-8 text-primary" />
          Stealth Radar
        </h1>
        <p className="text-muted-foreground">
          Detect smart money accumulation before the price breaks out
        </p>
      </div>

      {/* Info Banner */}
      <div className="rounded-xl border border-primary/50 bg-primary/5 p-4">
        <h3 className="font-semibold text-primary flex items-center gap-2">
          <Info className="h-4 w-4" />
          What is Stealth Accumulation?
        </h3>
        <p className="mt-2 text-sm text-muted-foreground">
          In NEPSE, operators rotate money between sectors. Before a sector pumps, they 
          <strong className="text-foreground"> quietly accumulate shares</strong>. During this phase:
        </p>
        <ul className="mt-2 space-y-1.5 text-sm text-muted-foreground">
          <li className="flex items-center gap-2">
            <ArrowDown className="h-4 w-4 text-bear" />
            <span><strong className="text-foreground">Technical Score is LOW</strong> — Price hasn&apos;t broken out yet</span>
          </li>
          <li className="flex items-center gap-2">
            <ArrowUp className="h-4 w-4 text-bull" />
            <span><strong className="text-foreground">Broker Score is HIGH</strong> — Heavy institutional buying</span>
          </li>
          <li className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-bull" />
            <span><strong className="text-foreground">Distribution Risk is LOW</strong> — Brokers are not selling</span>
          </li>
        </ul>
        <p className="mt-2 text-sm text-primary font-medium">
          This radar shows you which sectors the &quot;Smart Money&quot; is quietly rotating into!
        </p>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4">
        <PrettySelect
          value={sector}
          onChange={setSector}
          options={[
            { value: '', label: 'All Sectors' },
            { value: 'hydro', label: 'Hydropower' },
            { value: 'bank', label: 'Banking' },
            { value: 'finance', label: 'Finance' },
            { value: 'microfinance', label: 'Microfinance' },
            { value: 'life_insurance', label: 'Life Insurance' },
            { value: 'non_life_insurance', label: 'Non-Life Insurance' },
          ]}
        />

        <button
          onClick={handleScan}
          disabled={isLoading || isStealthRunning}
          className={cn(
            'flex items-center gap-2 rounded-lg bg-primary px-6 py-2.5 font-semibold text-primary-foreground transition-colors hover:bg-primary/90',
            (isLoading || isStealthRunning) && 'cursor-not-allowed opacity-50'
          )}
        >
          {isLoading || isStealthRunning ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              Scanning...
            </>
          ) : (
            <>
              <Radar className="h-5 w-5" />
              Run Stealth Scan
            </>
          )}
        </button>
        <button
          onClick={handleStop}
          disabled={!isStealthRunning}
          className={cn(
            'flex items-center gap-2 rounded-lg border px-4 py-2.5 font-semibold transition-colors',
            isStealthRunning
              ? 'border-bear/40 bg-bear/10 text-bear hover:bg-bear/20'
              : 'cursor-not-allowed border-border bg-card text-muted-foreground opacity-50'
          )}
        >
          <AlertTriangle className="h-5 w-5" />
          Stop
        </button>
      </div>
      <div className="max-w-xl">
        <ScanHistoryPanel
          title="Stealth Scan History"
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

      {/* Results */}
      {(isLoading || isStealthRunning) && (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
          <p className="mt-4 text-lg font-medium">Scanning for stealth accumulation...</p>
          <p className="text-sm text-muted-foreground">Analyzing broker patterns across all stocks</p>
        </div>
      )}

      {data && !isLoading && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border border-border bg-card p-4 text-center">
              <p className="text-2xl font-bold text-primary">{data.total_stealth_stocks}</p>
              <p className="text-sm text-muted-foreground">Stealth Stocks Found</p>
            </div>
            <div className="rounded-xl border border-border bg-card p-4 text-center">
              <p className="text-2xl font-bold text-warning">{data.sectors.length}</p>
              <p className="text-sm text-muted-foreground">Sectors with Accumulation</p>
            </div>
            <div className="rounded-xl border border-border bg-card p-4 text-center">
              <p className="text-2xl font-bold text-bear">
                {data.sectors.filter(s => s.stock_count >= 5).length}
              </p>
              <p className="text-sm text-muted-foreground">HOT Sectors</p>
            </div>
          </div>

          {/* Sector Cards */}
          {data.sectors.length > 0 ? (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">Sector Rotation Signals</h2>
              {data.sectors
                .sort((a, b) => b.stock_count - a.stock_count)
                .map((sector) => (
                  <SectorCard key={sector.sector} sector={sector} />
                ))
              }
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-card py-16">
              <TrendingUp className="h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-xl font-semibold">No Stealth Accumulation Detected</h3>
              <p className="mt-2 text-center text-muted-foreground">
                No stocks currently match the stealth criteria.<br />
                The market may be in distribution or consolidation phase.
              </p>
            </div>
          )}
        </div>
      )}

      {!data && !isLoading && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-16">
          <Radar className="h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-xl font-semibold">Ready to Detect Smart Money</h3>
          <p className="mt-2 text-center text-muted-foreground">
            Click &quot;Run Stealth Scan&quot; to identify sectors where<br />
            institutional money is quietly accumulating shares.
          </p>
        </div>
      )}
    </div>
  );
}
