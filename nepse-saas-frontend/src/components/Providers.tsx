'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';
import { useMemo, useState } from 'react';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 10 * 60 * 1000, // 10 minutes
            gcTime: 24 * 60 * 60 * 1000, // 24 hours in cache
            refetchOnWindowFocus: false,
            refetchOnMount: false,   // Don't refetch when component mounts
            refetchOnReconnect: false,
            retry: 1,                // Only 1 retry on failure
            retryDelay: 1000,
          },
        },
      })
  );

  const persister = useMemo(() => {
    if (typeof window === 'undefined') return undefined;
    return createSyncStoragePersister({
      storage: window.localStorage,
      key: 'nepse-query-cache-v1',
    });
  }, []);

  if (!persister) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: 24 * 60 * 60 * 1000,
      }}
    >
      {children}
    </PersistQueryClientProvider>
  );
}
