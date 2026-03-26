'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Search,
  Radar,
  Wallet,
  TrendingUp,
  Settings,
  Activity,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Market Scanner', href: '/scanner', icon: Search },
  { name: 'Stealth Radar', href: '/stealth', icon: Radar },
  { name: 'Portfolio', href: '/portfolio', icon: Wallet },
  { name: 'Analyze Stock', href: '/analyze', icon: TrendingUp },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r border-border bg-surface-1">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-border px-6">
        <div className="rounded-lg bg-primary-muted p-2">
          <Activity className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="text-base font-bold tracking-tight text-foreground">NEPSE AI</h1>
          <p className="text-xs text-muted-foreground">Trading Terminal</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="space-y-1 p-4">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-primary-muted text-primary shadow-inner-glow'
                  : 'text-muted-foreground hover:bg-surface-2 hover:text-foreground'
              )}
            >
              <item.icon className={cn(
                'h-5 w-5 transition-colors',
                isActive ? 'text-primary' : 'group-hover:text-foreground'
              )} />
              {item.name}
              {isActive && (
                <div className="ml-auto h-1.5 w-1.5 rounded-full bg-primary shadow-glow-sm" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="absolute bottom-0 left-0 right-0 border-t border-border p-4">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <div className="h-2 w-2 rounded-full bg-primary animate-pulse shadow-glow-sm" />
          <span>API Connected</span>
        </div>
        <p className="mt-2 text-[10px] text-muted">v1.0.0 • Educational Use Only</p>
      </div>
    </aside>
  );
}
