'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
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
  Sparkles,
  Lock,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavItem {
  name: string;
  href: string;
  icon: any;
  badge?: string;
  comingSoon?: boolean;
}

interface NavGroup {
  name: string;
  icon: any;
  items: NavItem[];
  defaultOpen?: boolean;
}

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
      { name: 'Trading Signal', href: '/signal', icon: Zap, badge: 'AI' },
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
      { name: 'Hold or Sell', href: '/hold-or-sell', icon: Scale, badge: 'AI' },
      { name: 'IPO Exit Timing', href: '/ipo-exit', icon: Clock, badge: 'NEW' },
    ],
  },
  {
    name: 'Market Scanner',
    icon: Radar,
    items: [
      { name: 'AI Scanner', href: '/scanner', icon: Brain, comingSoon: true },
      { name: 'Stealth Radar', href: '/stealth', icon: Radar, comingSoon: true },
      { name: 'Trading Calendar', href: '/calendar', icon: Calendar, comingSoon: true },
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
  
  useEffect(() => {
    if (hasActiveItem) {
      setIsOpen(true);
    }
  }, [hasActiveItem]);

  return (
    <div className="mb-2">
      {!collapsed ? (
        <>
          <motion.button
            onClick={() => setIsOpen(!isOpen)}
            className={cn(
              'nav-item flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
              hasActiveItem
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-surface-2/80 hover:text-foreground'
            )}
            whileHover={{ x: 2 }}
            whileTap={{ scale: 0.98 }}
            title={group.name}
          >
            <div className="flex items-center gap-2.5">
              <group.icon className={cn(
                'h-4 w-4 transition-colors',
                hasActiveItem ? 'text-primary' : ''
              )} />
              <span>{group.name}</span>
            </div>
            <motion.div
              animate={{ rotate: isOpen ? 180 : 0 }}
              transition={{ duration: 0.2 }}
            >
              <ChevronDown className="h-4 w-4" />
            </motion.div>
          </motion.button>

          <AnimatePresence>
            {isOpen && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="mt-1 ml-3 space-y-0.5 border-l border-border/50 pl-3">
                  {group.items.map((item, index) => {
                    const isActive = pathname === item.href;
                    if (item.comingSoon) {
                      return (
                        <motion.div
                          key={item.href}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: index * 0.05 }}
                          title="Available on localhost only — coming soon on web"
                        >
                          <div className="group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm cursor-not-allowed opacity-40 select-none">
                            <item.icon className="h-4 w-4" />
                            <span className="flex-1">{item.name}</span>
                            <Lock className="h-3 w-3 text-muted-foreground" />
                          </div>
                        </motion.div>
                      );
                    }
                    return (
                      <motion.div
                        key={item.href}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.05 }}
                      >
                        <Link
                          href={item.href}
                          className={cn(
                            'group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-all duration-200',
                            isActive
                              ? 'bg-primary/15 text-primary font-medium shadow-glow-sm'
                              : 'text-muted-foreground hover:bg-surface-2/60 hover:text-foreground hover:translate-x-1'
                          )}
                        >
                          <item.icon className={cn(
                            'h-4 w-4 transition-all duration-200',
                            isActive ? 'text-primary' : 'group-hover:text-foreground group-hover:scale-110'
                          )} />
                          <span className="flex-1">{item.name}</span>
                          {item.badge && (
                            <span className={cn(
                              'rounded-full px-1.5 py-0.5 text-[10px] font-bold',
                              item.badge === 'AI' 
                                ? 'bg-gradient-to-r from-primary/30 to-accent/30 text-primary border border-primary/20' 
                                : 'bg-primary/20 text-primary'
                            )}>
                              {item.badge}
                            </span>
                          )}
                          {isActive && (
                            <motion.div 
                              className="h-1.5 w-1.5 rounded-full bg-primary"
                              layoutId="activeIndicator"
                              transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                            />
                          )}
                        </Link>
                      </motion.div>
                    );
                  })}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      ) : (
        <div className="space-y-1">
          {group.items.map((item) => {
            const isActive = pathname === item.href;
            if (item.comingSoon) {
              return (
                <div
                  key={item.href}
                  title={`${item.name} — coming soon on web`}
                  className="flex w-full items-center justify-center rounded-lg px-2 py-2.5 opacity-30 cursor-not-allowed"
                >
                  <item.icon className="h-4 w-4" />
                </div>
              );
            }
            return (
              <Link
                key={item.href}
                href={item.href}
                title={item.name}
                className={cn(
                  'flex w-full items-center justify-center rounded-lg px-2 py-2.5 transition-all duration-200',
                  isActive
                    ? 'bg-primary/15 text-primary shadow-glow-sm'
                    : 'text-muted-foreground hover:bg-surface-2/60 hover:text-foreground hover:scale-110'
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

  return (
    <motion.aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-border/50 transition-all duration-300',
        collapsed ? 'w-20' : 'w-64'
      )}
      style={{
        background: 'linear-gradient(180deg, rgba(20, 20, 22, 0.95) 0%, rgba(9, 9, 11, 0.98) 100%)',
        backdropFilter: 'blur(20px)',
      }}
      initial={false}
      animate={{ width: collapsed ? 80 : 256 }}
      transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}
    >
      {/* Gradient overlay at top */}
      <div className="absolute inset-x-0 top-0 h-32 pointer-events-none" style={{ background: 'var(--gradient-sidebar)' }} />
      
      {/* Logo */}
      <div className={cn(
        'relative flex h-16 items-center border-b border-border/50 px-4',
        collapsed ? 'justify-center' : 'gap-3'
      )}>
        <motion.div 
          className="relative rounded-xl bg-gradient-to-br from-primary to-accent p-2.5 shadow-glow-sm"
          whileHover={{ scale: 1.05, rotate: 5 }}
          whileTap={{ scale: 0.95 }}
        >
          <Activity className="h-5 w-5 text-primary-foreground" />
          <div className="absolute inset-0 rounded-xl bg-white/10" />
        </motion.div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
            >
              <h1 className="text-base font-bold tracking-tight text-foreground flex items-center gap-1.5">
                NEPSE AI
                <Sparkles className="h-3.5 w-3.5 text-primary" />
              </h1>
              <p className="text-[10px] text-muted-foreground font-medium">Next Millionaire</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Collapse Toggle */}
      <div className="border-b border-border/30 p-2">
        <motion.button
          type="button"
          onClick={() => {
            setCollapsed((v) => {
              const next = !v;
              try {
                window.localStorage.setItem('nepse-sidebar-collapsed-v1', next ? '1' : '0');
              } catch {}
              return next;
            });
          }}
          className={cn(
            'inline-flex w-full items-center rounded-lg px-3 py-2 text-sm text-muted-foreground',
            'hover:bg-surface-2/60 hover:text-foreground transition-all duration-200',
            collapsed ? 'justify-center' : 'gap-2'
          )}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                Collapse
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-3 relative">
        {navigationGroups.map((group) => (
          <NavGroupComponent key={group.name} group={group} collapsed={collapsed} />
        ))}
      </nav>

      {/* Help Section */}
      <div className="border-t border-border/30 p-3">
        <Link
          href="/help"
          className={cn(
            'flex items-center rounded-lg px-3 py-2.5 text-sm text-muted-foreground',
            'hover:bg-surface-2/60 hover:text-foreground transition-all duration-200',
            collapsed ? 'justify-center' : 'gap-2'
          )}
        >
          <HelpCircle className="h-4 w-4" />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                Help & Docs
              </motion.span>
            )}
          </AnimatePresence>
        </Link>
        
        {/* Logout Button */}
        <button
          onClick={() => {
            localStorage.removeItem('nepse_auth_token');
            window.location.reload();
          }}
          className={cn(
            'w-full flex items-center rounded-lg px-3 py-2.5 text-sm text-red-400 mt-2',
            'hover:bg-red-500/10 hover:text-red-300 transition-all duration-200',
            collapsed ? 'justify-center' : 'gap-2'
          )}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                Logout
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>

      {/* Footer */}
      <div className="border-t border-border/30 p-4">
        <div className={cn(
          'flex items-center text-xs',
          collapsed ? 'justify-center' : 'gap-2'
        )}>
          <div className="status-dot online" />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                className="text-muted-foreground"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                API Connected
              </motion.span>
            )}
          </AnimatePresence>
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.p
              className="mt-2 text-[10px] text-muted"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              Safe Usuage • Educational Use Only
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </motion.aside>
  );
}
