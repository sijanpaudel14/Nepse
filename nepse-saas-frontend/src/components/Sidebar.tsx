'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  Search,
  Radar,
  Wallet,
  TrendingUp,
  ChevronDown,
  ChevronRight,
  Activity,
  Zap,
  Calendar,
  BarChart3,
  PieChart,
  Brain,
  Target,
  Clock,
  Banknote,
  Users,
  LineChart,
  Gauge,
  AlertTriangle,
  HelpCircle,
  BookOpen,
  Scale,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavItem {
  name: string;
  href: string;
  icon: any;
  badge?: string;
}

interface NavGroup {
  name: string;
  icon: any;
  items: NavItem[];
  defaultOpen?: boolean;
}

// Organized navigation matching paper_trader.py features
const navigationGroups: NavGroup[] = [
  {
    name: 'Dashboard',
    icon: LayoutDashboard,
    defaultOpen: true,
    items: [
      { name: 'Overview', href: '/', icon: LayoutDashboard },
      { name: 'Portfolio', href: '/portfolio', icon: Wallet },
    ],
  },
  {
    name: 'Stock Analysis',
    icon: Search,
    defaultOpen: true,
    items: [
      { name: 'Analyze Stock', href: '/analyze', icon: Search },
      { name: 'Trading Signal', href: '/signal', icon: Zap, badge: 'NEW' },
      { name: 'Price Targets', href: '/price-targets', icon: Target },
      { name: 'Tech Score', href: '/tech-score', icon: Gauge },
      { name: 'Order Flow', href: '/order-flow', icon: LineChart },
    ],
  },
  {
    name: 'Position Tools',
    icon: Scale,
    defaultOpen: true,
    items: [
      { name: 'Hold or Sell', href: '/hold-or-sell', icon: Scale, badge: 'NEW' },
      { name: 'IPO Exit Timing', href: '/ipo-exit', icon: Clock, badge: 'NEW' },
    ],
  },
  {
    name: 'Market Scanner',
    icon: Radar,
    items: [
      { name: 'AI Scanner', href: '/scanner', icon: Brain },
      { name: 'Stealth Radar', href: '/stealth', icon: Radar },
      { name: 'Trading Calendar', href: '/calendar', icon: Calendar, badge: 'NEW' },
    ],
  },
  {
    name: 'Market Intelligence',
    icon: BarChart3,
    items: [
      { name: 'Smart Money', href: '/smart-money', icon: Banknote },
      { name: 'Broker Intelligence', href: '/broker-intel', icon: Users },
      { name: 'Sector Rotation', href: '/sector-rotation', icon: PieChart },
      { name: 'Market Heatmap', href: '/heatmap', icon: BarChart3 },
      { name: 'Positioning', href: '/positioning', icon: TrendingUp },
      { name: 'Bulk Deals', href: '/bulk-deals', icon: AlertTriangle },
    ],
  },
  {
    name: 'Research',
    icon: BookOpen,
    items: [
      { name: 'Dividend Forecast', href: '/dividend', icon: Banknote },
    ],
  },
];

function NavGroupComponent({ group, collapsed }: { group: NavGroup; collapsed: boolean }) {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(group.defaultOpen ?? false);
  
  const hasActiveItem = group.items.some(item => pathname === item.href);
  
  // Auto-open group if it has an active item
  if (hasActiveItem && !isOpen) {
    setIsOpen(true);
  }

  return (
    <div className="mb-1">
      {!collapsed ? (
        <>
          <button
            onClick={() => setIsOpen(!isOpen)}
            className={cn(
              'flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              hasActiveItem
                ? 'bg-primary-muted/50 text-primary'
                : 'text-muted-foreground hover:bg-surface-2 hover:text-foreground'
            )}
            title={group.name}
          >
            <div className="flex items-center gap-2">
              <group.icon className="h-4 w-4" />
              <span>{group.name}</span>
            </div>
            {isOpen ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>

          {isOpen && (
            <div className="mt-1 ml-3 space-y-0.5 border-l border-border pl-3">
              {group.items.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      'group flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all duration-200',
                      isActive
                        ? 'bg-primary-muted text-primary font-medium'
                        : 'text-muted-foreground hover:bg-surface-2 hover:text-foreground'
                    )}
                  >
                    <item.icon className={cn(
                      'h-4 w-4 transition-colors',
                      isActive ? 'text-primary' : 'group-hover:text-foreground'
                    )} />
                    <span className="flex-1">{item.name}</span>
                    {item.badge && (
                      <span className="rounded-full bg-primary/20 px-1.5 py-0.5 text-[10px] font-bold text-primary">
                        {item.badge}
                      </span>
                    )}
                    {isActive && (
                      <div className="h-1.5 w-1.5 rounded-full bg-primary shadow-glow-sm" />
                    )}
                  </Link>
                );
              })}
            </div>
          )}
        </>
      ) : (
        <div className="space-y-1">
          {group.items.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                title={item.name}
                className={cn(
                  'flex w-full items-center justify-center rounded-lg px-2 py-2 transition-colors',
                  isActive
                    ? 'bg-primary-muted text-primary'
                    : 'text-muted-foreground hover:bg-surface-2 hover:text-foreground'
                )}
              >
                <item.icon className="h-4 w-4" />
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem('nepse-sidebar-collapsed-v1') === '1');
    } catch {
      setCollapsed(false);
    }
  }, []);
  const widthClass = collapsed ? 'w-20' : 'w-64';

  return (
    <aside className={cn('fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-border bg-surface-1 transition-all', widthClass)}>
      {/* Logo */}
      <div className={cn('flex h-16 items-center border-b border-border px-4', collapsed ? 'justify-center' : 'gap-3')}>
        <div className="rounded-lg bg-gradient-to-br from-primary to-primary/60 p-2 shadow-glow-sm">
          <Activity className="h-5 w-5 text-primary-foreground" />
        </div>
        {!collapsed && <div>
          <h1 className="text-base font-bold tracking-tight text-foreground">NEPSE AI</h1>
          <p className="text-[10px] text-muted-foreground">Trading Terminal v2.0</p>
        </div>}
      </div>

      <div className="border-b border-border p-2">
        <button
          type="button"
          onClick={() => {
            setCollapsed((v) => {
              const next = !v;
              try {
                window.localStorage.setItem('nepse-sidebar-collapsed-v1', next ? '1' : '0');
              } catch {
                // ignore storage write issues
              }
              return next;
            });
          }}
          className={cn('inline-flex w-full items-center rounded-lg px-2 py-2 text-sm text-muted-foreground hover:bg-surface-2 hover:text-foreground', collapsed ? 'justify-center' : 'gap-2')}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-3">
        {navigationGroups.map((group) => (
          <NavGroupComponent key={group.name} group={group} collapsed={collapsed} />
        ))}
      </nav>

      {/* Help Section */}
      <div className="border-t border-border p-3">
        <Link
          href="/help"
          className={cn('flex items-center rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors', collapsed ? 'justify-center' : 'gap-2')}
          title="Help & Docs"
        >
          <HelpCircle className="h-4 w-4" />
          {!collapsed && <span>Help & Docs</span>}
        </Link>
      </div>

      {/* Footer */}
      <div className="border-t border-border p-4">
        <div className={cn('flex items-center text-xs text-muted-foreground', collapsed ? 'justify-center' : 'gap-2')}>
          <div className="h-2 w-2 rounded-full bg-primary animate-pulse shadow-glow-sm" />
          {!collapsed && <span>API Connected</span>}
        </div>
        {!collapsed && <p className="mt-2 text-[10px] text-muted">v2.0.0 • Educational Use Only</p>}
      </div>
    </aside>
  );
}
