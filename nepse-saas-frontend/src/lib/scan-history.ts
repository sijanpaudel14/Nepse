export interface ScanHistoryItem {
  id: string;
  label: string;
  value: string;
  timestamp: number;
}

export function loadScanHistory(key: string): ScanHistoryItem[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) =>
      item &&
      typeof item.id === 'string' &&
      typeof item.label === 'string' &&
      typeof item.value === 'string' &&
      typeof item.timestamp === 'number'
    ) as ScanHistoryItem[];
  } catch {
    return [];
  }
}

export function saveScanHistory(key: string, items: ScanHistoryItem[]) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(key, JSON.stringify(items));
}

export function pushScanHistory(
  key: string,
  entry: Omit<ScanHistoryItem, 'id' | 'timestamp'>,
  maxItems = 10
): ScanHistoryItem[] {
  const existing = loadScanHistory(key);
  const deduped = existing.filter((item) => item.value !== entry.value);
  const next: ScanHistoryItem[] = [
    {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      label: entry.label,
      value: entry.value,
      timestamp: Date.now(),
    },
    ...deduped,
  ].slice(0, maxItems);
  saveScanHistory(key, next);
  return next;
}

export function removeScanHistoryItem(key: string, id: string): ScanHistoryItem[] {
  const next = loadScanHistory(key).filter((item) => item.id !== id);
  saveScanHistory(key, next);
  return next;
}

export function clearScanHistory(key: string) {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(key);
}
