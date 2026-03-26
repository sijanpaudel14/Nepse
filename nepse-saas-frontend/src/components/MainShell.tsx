'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Sidebar } from '@/components/Sidebar';
import { cn } from '@/lib/utils';

const pageVariants = {
  initial: { 
    opacity: 0, 
    y: 8,
  },
  animate: { 
    opacity: 1, 
    y: 0,
    transition: {
      duration: 0.3,
      ease: 'easeOut' as const,
    },
  },
  exit: { 
    opacity: 0,
    y: -4,
    transition: {
      duration: 0.15,
    },
  },
};

export function MainShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

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
      <motion.main
        className={cn(
          'flex-1 p-6 lg:p-8 transition-[margin] duration-300',
          collapsed ? 'ml-20' : 'ml-64'
        )}
        initial={false}
        animate={{ marginLeft: collapsed ? 80 : 256 }}
        transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={pathname}
            initial="initial"
            animate="animate"
            exit="exit"
            variants={pageVariants}
            className="min-h-[calc(100vh-4rem)]"
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </motion.main>
    </div>
  );
}
