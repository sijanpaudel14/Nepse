// Shared UI Components for NEPSE AI Trading Terminal
'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { 
  Loader2, 
  TrendingUp, 
  TrendingDown, 
  Minus,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
  Clock,
  Target,
  Shield,
  ChevronDown,
  Check,
  History,
  X,
  Trash2,
} from 'lucide-react';

// ============== LOADING STATES ==============

export function PageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-48 bg-muted/30 rounded-lg" />
      <div className="h-4 w-96 bg-muted/20 rounded" />
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="h-32 bg-muted/20 rounded-xl" />
        ))}
      </div>
      <div className="h-96 bg-muted/20 rounded-xl" />
    </div>
  );
}

export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('animate-pulse rounded-xl border border-border bg-card p-6', className)}>
      <div className="h-4 w-24 bg-muted/30 rounded mb-4" />
      <div className="h-8 w-32 bg-muted/20 rounded mb-2" />
      <div className="h-3 w-48 bg-muted/10 rounded" />
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="animate-pulse space-y-3">
      <div className="h-10 bg-muted/20 rounded-lg" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-12 bg-muted/10 rounded-lg" />
      ))}
    </div>
  );
}

export function LoadingSpinner({ size = 'md', className }: { size?: 'sm' | 'md' | 'lg'; className?: string }) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
  };
  
  return <Loader2 className={cn('animate-spin', sizeClasses[size], className)} />;
}

// ============== VERDICT BADGES ==============

type Verdict = 
  | 'BUY' | 'SELL' | 'HOLD' | 'WAIT'
  | 'STRONG_HOLD' | 'HOLD_CAUTIOUSLY' | 'BOOK_PARTIAL' | 'AVERAGE_DOWN' | 'EXIT' | 'URGENT_EXIT'
  | 'STRONG_BUY' | 'STRONG_SELL'
  | 'WATCH' | 'CONSIDER_PARTIAL' | 'URGENT_SELL'
  | 'BULLISH' | 'BEARISH' | 'NEUTRAL'
  | 'OVERBOUGHT' | 'OVERSOLD';

const verdictConfig: Record<string, { bg: string; text: string; icon: any }> = {
  // Buy/Sell signals
  BUY: { bg: 'bg-bull/20', text: 'text-bull', icon: TrendingUp },
  STRONG_BUY: { bg: 'bg-bull/30', text: 'text-bull', icon: TrendingUp },
  SELL: { bg: 'bg-bear/20', text: 'text-bear', icon: TrendingDown },
  STRONG_SELL: { bg: 'bg-bear/30', text: 'text-bear', icon: TrendingDown },
  HOLD: { bg: 'bg-warning/20', text: 'text-warning', icon: Minus },
  WAIT: { bg: 'bg-muted/30', text: 'text-muted-foreground', icon: Clock },
  
  // Position verdicts
  STRONG_HOLD: { bg: 'bg-bull/30', text: 'text-bull', icon: Shield },
  HOLD_CAUTIOUSLY: { bg: 'bg-warning/20', text: 'text-warning', icon: AlertTriangle },
  BOOK_PARTIAL: { bg: 'bg-warning/30', text: 'text-warning', icon: Target },
  AVERAGE_DOWN: { bg: 'bg-primary/20', text: 'text-primary', icon: TrendingDown },
  EXIT: { bg: 'bg-bear/20', text: 'text-bear', icon: XCircle },
  URGENT_EXIT: { bg: 'bg-bear/40', text: 'text-bear', icon: AlertTriangle },
  
  // IPO verdicts
  WATCH: { bg: 'bg-warning/20', text: 'text-warning', icon: Clock },
  CONSIDER_PARTIAL: { bg: 'bg-warning/30', text: 'text-warning', icon: Target },
  URGENT_SELL: { bg: 'bg-bear/40', text: 'text-bear', icon: AlertTriangle },
  
  // Market sentiment
  BULLISH: { bg: 'bg-bull/20', text: 'text-bull', icon: TrendingUp },
  BEARISH: { bg: 'bg-bear/20', text: 'text-bear', icon: TrendingDown },
  NEUTRAL: { bg: 'bg-muted/30', text: 'text-muted-foreground', icon: Minus },
  OVERBOUGHT: { bg: 'bg-bear/20', text: 'text-bear', icon: AlertTriangle },
  OVERSOLD: { bg: 'bg-bull/20', text: 'text-bull', icon: AlertTriangle },
};

export function VerdictBadge({ verdict, size = 'md' }: { verdict: string; size?: 'sm' | 'md' | 'lg' }) {
  const config = verdictConfig[verdict] || { bg: 'bg-muted/30', text: 'text-muted-foreground', icon: Info };
  const Icon = config.icon;
  
  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs gap-1',
    md: 'px-3 py-1 text-sm gap-1.5',
    lg: 'px-4 py-2 text-base gap-2',
  };
  
  const iconSizes = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4',
    lg: 'h-5 w-5',
  };
  
  return (
    <span className={cn(
      'inline-flex items-center rounded-full font-semibold',
      config.bg,
      config.text,
      sizeClasses[size]
    )}>
      <Icon className={iconSizes[size]} />
      {verdict.replace(/_/g, ' ')}
    </span>
  );
}

// ============== SCORE DISPLAYS ==============

export function ScoreCircle({ 
  score, 
  maxScore = 100, 
  size = 'md',
  label,
}: { 
  score: number; 
  maxScore?: number; 
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}) {
  const percentage = (score / maxScore) * 100;
  const circumference = 2 * Math.PI * 40;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;
  
  const getColor = (pct: number) => {
    if (pct >= 70) return 'stroke-bull';
    if (pct >= 40) return 'stroke-warning';
    return 'stroke-bear';
  };
  
  const sizeClasses = {
    sm: { container: 'h-16 w-16', text: 'text-lg', label: 'text-[10px]' },
    md: { container: 'h-24 w-24', text: 'text-2xl', label: 'text-xs' },
    lg: { container: 'h-32 w-32', text: 'text-3xl', label: 'text-sm' },
  };
  
  return (
    <div className={cn('relative', sizeClasses[size].container)}>
      <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100">
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          className="text-muted/20"
        />
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className={cn('transition-all duration-500', getColor(percentage))}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn('font-bold', sizeClasses[size].text)}>{Math.round(score)}</span>
        {label && (
          <span className={cn('text-muted-foreground', sizeClasses[size].label)}>{label}</span>
        )}
      </div>
    </div>
  );
}

export function ScoreBar({ 
  score, 
  maxScore = 100, 
  label,
  showValue = true,
}: { 
  score: number; 
  maxScore?: number; 
  label?: string;
  showValue?: boolean;
}) {
  const percentage = (score / maxScore) * 100;
  
  const getColor = (pct: number) => {
    if (pct >= 70) return 'bg-bull';
    if (pct >= 40) return 'bg-warning';
    return 'bg-bear';
  };
  
  return (
    <div className="space-y-1">
      {(label || showValue) && (
        <div className="flex justify-between text-sm">
          {label && <span className="text-muted-foreground">{label}</span>}
          {showValue && <span className="font-medium">{Math.round(score)}/{maxScore}</span>}
        </div>
      )}
      <div className="h-2 rounded-full bg-muted/20 overflow-hidden">
        <div 
          className={cn('h-full rounded-full transition-all duration-500', getColor(percentage))}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

export function PrettySelect({
  value,
  onChange,
  options,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const selected = options.find((option) => option.value === value) || options[0];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={rootRef} className={cn('relative min-w-[220px]', className)}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex h-10 w-full items-center justify-between rounded-lg border border-border bg-card px-3 text-sm font-medium text-foreground transition-colors hover:bg-card-hover focus:outline-none focus:ring-2 focus:ring-primary/40"
      >
        <span className="truncate">{selected?.label || 'Select'}</span>
        <ChevronDown className={cn('h-4 w-4 text-muted-foreground transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-border bg-card p-1 shadow-elegant">
          {options.map((option) => {
            const isSelected = option.value === value;
            return (
              <button
                key={option.value || '__all'}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className={cn(
                  'flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors',
                  isSelected ? 'bg-primary/15 text-primary' : 'text-foreground hover:bg-card-hover'
                )}
              >
                <span className="truncate">{option.label}</span>
                {isSelected && <Check className="h-4 w-4" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ============== PRICE DISPLAYS ==============

export function PriceChange({ 
  value, 
  percentage, 
  size = 'md',
  showIcon = true,
}: { 
  value?: number; 
  percentage?: number; 
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}) {
  const isPositive = (percentage ?? value ?? 0) > 0;
  const isNegative = (percentage ?? value ?? 0) < 0;
  
  const sizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
  };
  
  const iconSizes = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4',
    lg: 'h-5 w-5',
  };
  
  const Icon = isPositive ? TrendingUp : isNegative ? TrendingDown : Minus;
  const colorClass = isPositive ? 'text-bull' : isNegative ? 'text-bear' : 'text-muted-foreground';
  
  return (
    <span className={cn('inline-flex items-center gap-1 font-semibold', colorClass, sizeClasses[size])}>
      {showIcon && <Icon className={iconSizes[size]} />}
      {value !== undefined && (
        <span>{isPositive ? '+' : ''}{value.toLocaleString('en-NP', { minimumFractionDigits: 2 })}</span>
      )}
      {percentage !== undefined && (
        <span>({isPositive ? '+' : ''}{percentage.toFixed(2)}%)</span>
      )}
    </span>
  );
}

export function PriceLevel({
  label,
  price,
  currentPrice,
  variant = 'default',
}: {
  label: string;
  price: number;
  currentPrice?: number;
  variant?: 'target' | 'stop' | 'entry' | 'default';
}) {
  const variantStyles = {
    target: 'border-bull/30 bg-bull/10',
    stop: 'border-bear/30 bg-bear/10',
    entry: 'border-primary/30 bg-primary/10',
    default: 'border-border bg-card',
  };
  
  const labelStyles = {
    target: 'text-bull',
    stop: 'text-bear',
    entry: 'text-primary',
    default: 'text-muted-foreground',
  };
  
  const percentFromCurrent = currentPrice 
    ? ((price - currentPrice) / currentPrice) * 100 
    : null;
  
  return (
    <div className={cn('rounded-lg border p-3', variantStyles[variant])}>
      <div className={cn('text-xs font-medium', labelStyles[variant])}>{label}</div>
      <div className="mt-1 text-lg font-bold">Rs. {price.toLocaleString()}</div>
      {percentFromCurrent !== null && (
        <PriceChange percentage={percentFromCurrent} size="sm" />
      )}
    </div>
  );
}

// ============== TARGET DISPLAY ==============

export function TargetCard({
  level,
  price,
  gainPct,
  probability,
  currentPrice,
}: {
  level: string;
  price: number;
  gainPct: number;
  probability?: number;
  currentPrice?: number;
}) {
  return (
    <div className="rounded-lg border border-bull/30 bg-bull/5 p-4 hover:bg-bull/10 transition-colors">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-bull">{level}</span>
        {probability !== undefined && (
          <span className="text-xs text-muted-foreground">{probability}% likely</span>
        )}
      </div>
      <div className="mt-2 text-xl font-bold">Rs. {price.toLocaleString()}</div>
      <div className="mt-1 text-sm text-bull">+{gainPct.toFixed(1)}%</div>
    </div>
  );
}

// ============== WARNINGS & ALERTS ==============

export function WarningBox({ warnings }: { warnings: string[] }) {
  if (!warnings || warnings.length === 0) return null;
  
  return (
    <div className="rounded-lg border border-warning/30 bg-warning/10 p-4">
      <div className="flex items-center gap-2 text-warning font-medium mb-2">
        <AlertTriangle className="h-4 w-4" />
        <span>Warnings</span>
      </div>
      <ul className="space-y-1">
        {warnings.map((warning, i) => (
          <li key={i} className="text-sm text-warning/80 flex items-start gap-2">
            <span className="mt-1.5 h-1 w-1 rounded-full bg-warning/60 flex-shrink-0" />
            {warning}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function InfoBox({ title, children, variant = 'info' }: { 
  title: string; 
  children: React.ReactNode;
  variant?: 'info' | 'success' | 'warning' | 'error';
}) {
  const variants = {
    info: { border: 'border-primary/30', bg: 'bg-primary/10', icon: Info, color: 'text-primary' },
    success: { border: 'border-bull/30', bg: 'bg-bull/10', icon: CheckCircle, color: 'text-bull' },
    warning: { border: 'border-warning/30', bg: 'bg-warning/10', icon: AlertTriangle, color: 'text-warning' },
    error: { border: 'border-bear/30', bg: 'bg-bear/10', icon: XCircle, color: 'text-bear' },
  };
  
  const config = variants[variant];
  const Icon = config.icon;
  
  return (
    <div className={cn('rounded-lg border p-4', config.border, config.bg)}>
      <div className={cn('flex items-center gap-2 font-medium mb-2', config.color)}>
        <Icon className="h-4 w-4" />
        <span>{title}</span>
      </div>
      <div className="text-sm text-foreground/80">{children}</div>
    </div>
  );
}

// ============== STAT CARDS ==============

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  variant = 'default',
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: any;
  trend?: { value: number; label?: string };
  variant?: 'default' | 'bull' | 'bear' | 'warning';
}) {
  const variants = {
    default: 'border-border bg-card',
    bull: 'border-bull/30 bg-bull/10',
    bear: 'border-bear/30 bg-bear/10',
    warning: 'border-warning/30 bg-warning/10',
  };
  
  return (
    <div className={cn('rounded-xl border p-5', variants[variant])}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="mt-1 text-2xl font-bold">{value}</p>
          {subtitle && (
            <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
          )}
          {trend && (
            <PriceChange percentage={trend.value} size="sm" />
          )}
        </div>
        {Icon && (
          <div className="rounded-lg bg-muted/30 p-2">
            <Icon className="h-5 w-5 text-muted-foreground" />
          </div>
        )}
      </div>
    </div>
  );
}

// ============== SECTION HEADERS ==============

export function SectionHeader({ 
  title, 
  subtitle,
  action,
}: { 
  title: string; 
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        {subtitle && (
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        )}
      </div>
      {action}
    </div>
  );
}

// ============== EMPTY STATES ==============

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: any;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {Icon && (
        <div className="rounded-full bg-muted/30 p-4 mb-4">
          <Icon className="h-8 w-8 text-muted-foreground" />
        </div>
      )}
      <h3 className="text-lg font-semibold">{title}</h3>
      {description && (
        <p className="mt-1 text-sm text-muted-foreground max-w-md">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// ============== INPUT COMPONENTS ==============

export function SymbolInput({
  value,
  onChange,
  onSubmit,
  placeholder = 'Enter stock symbol...',
  isLoading = false,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  placeholder?: string;
  isLoading?: boolean;
}) {
  return (
    <div className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase())}
        onKeyDown={(e) => e.key === 'Enter' && onSubmit?.()}
        placeholder={placeholder}
        className="w-full rounded-lg border border-border bg-card px-4 py-2.5 pr-12 text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary font-mono"
      />
      {isLoading ? (
        <LoadingSpinner size="sm" className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground" />
      ) : (
        <kbd className="absolute right-4 top-1/2 -translate-y-1/2 rounded bg-muted/30 px-1.5 py-0.5 text-[10px] text-muted-foreground">
          ↵
        </kbd>
      )}
    </div>
  );
}

export function PriceInput({
  value,
  onChange,
  label,
  placeholder = '0.00',
}: {
  value: number | string;
  onChange: (value: number) => void;
  label?: string;
  placeholder?: string;
}) {
  return (
    <div>
      {label && (
        <label className="block text-sm text-muted-foreground mb-1">{label}</label>
      )}
      <div className="relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">Rs.</span>
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          placeholder={placeholder}
          className="w-full rounded-lg border border-border bg-card px-4 py-2.5 pl-12 text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary font-mono"
        />
      </div>
    </div>
  );
}

export function DateInput({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  label?: string;
}) {
  return (
    <div>
      {label && (
        <label className="block text-sm text-muted-foreground mb-1">{label}</label>
      )}
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-border bg-card px-4 py-2.5 text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      />
    </div>
  );
}

export function ScanHistoryPanel({
  title = 'Recent Scans',
  items,
  onSelect,
  onDelete,
  onClear,
}: {
  title?: string;
  items: Array<{ id: string; label: string; value: string; timestamp: number }>;
  onSelect: (value: string) => void;
  onDelete: (id: string) => void;
  onClear?: () => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed right-6 top-6 z-40 inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-semibold text-foreground shadow-elegant hover:bg-card-hover"
      >
        <History className="h-4 w-4 text-primary" />
        History
      </button>

      {open && (
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-40 bg-black/40"
          aria-label="Close history panel"
        />
      )}

      <aside
        className={cn(
          'fixed right-0 top-0 z-50 h-full w-full max-w-sm border-l border-border bg-card p-4 shadow-elegant transition-transform duration-300',
          open ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold">{title}</h3>
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-card-hover hover:text-foreground"
            aria-label="Close history"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mb-3 flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            {items.length ? `${items.length} saved scans` : 'No saved scans yet'}
          </p>
          {onClear && items.length > 0 && (
            <button
              type="button"
              onClick={onClear}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Clear all
            </button>
          )}
        </div>

        <div className="space-y-2 overflow-y-auto pb-4">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between gap-2 rounded-lg border border-border/70 bg-card-hover px-3 py-2"
            >
              <button
                type="button"
                onClick={() => {
                  onSelect(item.value);
                  setOpen(false);
                }}
                className="min-w-0 flex-1 text-left"
              >
                <p className="truncate text-sm font-medium">{item.label}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(item.timestamp).toLocaleString()}
                </p>
              </button>
              <button
                type="button"
                onClick={() => onDelete(item.id)}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-bear/10 hover:text-bear"
                aria-label={`Delete scan ${item.label}`}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </aside>
    </>
  );
}
