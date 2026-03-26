'use client';

import { useEffect, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { cn } from '@/lib/utils';

export function MainShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const read = () => {
      try {
        setCollapsed(window.localStorage.getItem('nepse-sidebar-collapsed-v1') === '1');
      } catch {
        setCollapsed(false);
      }
    };
    read();
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'nepse-sidebar-collapsed-v1') read();
    };
    window.addEventListener('storage', onStorage);
    const interval = window.setInterval(read, 400);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.clearInterval(interval);
    };
  }, []);

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className={cn('flex-1 p-6 transition-all', collapsed ? 'ml-20' : 'ml-64')}>
        {children}
      </main>
    </div>
  );
}
