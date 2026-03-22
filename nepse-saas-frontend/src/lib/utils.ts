import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Format number with commas (Nepali style)
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-IN').format(num);
}

// Format currency
export function formatCurrency(num: number | undefined | null): string {
  if (num === undefined || num === null || isNaN(num)) return 'Rs. ---';
  return `Rs. ${formatNumber(Math.round(num * 100) / 100)}`;
}

// Format percentage
export function formatPercent(num: number | undefined | null): string {
  if (num === undefined || num === null || isNaN(num)) return '0.00%';
  const sign = num >= 0 ? '+' : '';
  return `${sign}${num.toFixed(2)}%`;
}

// Get color class based on value
export function getValueColor(value: number): string {
  if (value > 0) return 'text-bull-text';
  if (value < 0) return 'text-bear-text';
  return 'text-neutral-text';
}

// Score thresholds
export type ScoreLevel = 'excellent' | 'good' | 'average' | 'weak';

// Get score color and label - Premium design with proper contrast
export function getScoreColor(score: number): { 
  bgColor: string; 
  textColor: string; 
  label: string;
  level: ScoreLevel;
} {
  if (score >= 85) {
    return { 
      bgColor: 'bg-bull-muted', 
      textColor: 'text-bull-text', 
      label: 'EXCELLENT', 
      level: 'excellent' 
    };
  }
  if (score >= 70) {
    return { 
      bgColor: 'bg-primary-muted', 
      textColor: 'text-primary', 
      label: 'GOOD', 
      level: 'good' 
    };
  }
  if (score >= 55) {
    return { 
      bgColor: 'bg-neutral-muted', 
      textColor: 'text-neutral-text', 
      label: 'AVERAGE', 
      level: 'average' 
    };
  }
  return { 
    bgColor: 'bg-bear-muted', 
    textColor: 'text-bear-text', 
    label: 'WEAK', 
    level: 'weak' 
  };
}

// Risk levels
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical' | 'unknown';

// Get distribution risk color - Premium design with proper contrast
export function getRiskColor(risk: string): {
  bgColor: string;
  textColor: string;
  level: RiskLevel;
} {
  switch (risk?.toUpperCase()) {
    case 'LOW':
      return { 
        bgColor: 'bg-bull-muted', 
        textColor: 'text-bull-text', 
        level: 'low' 
      };
    case 'MEDIUM':
      return { 
        bgColor: 'bg-neutral-muted', 
        textColor: 'text-neutral-text', 
        level: 'medium' 
      };
    case 'HIGH':
      return { 
        bgColor: 'bg-bear-muted', 
        textColor: 'text-bear-text', 
        level: 'high' 
      };
    case 'CRITICAL':
      return { 
        bgColor: 'bg-destructive-muted', 
        textColor: 'text-destructive-foreground', 
        level: 'critical' 
      };
    default:
      return { 
        bgColor: 'bg-muted', 
        textColor: 'text-muted-foreground', 
        level: 'unknown' 
      };
  }
}
