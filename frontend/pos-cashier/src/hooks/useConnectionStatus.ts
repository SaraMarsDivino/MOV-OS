import { useCallback, useEffect, useRef, useState } from 'react';
import { getPendingCount, loadQueuedSales, removeSaleFromQueue } from '../lib/offlineDb';

export type SyncResult = {
  key: string;
  success: boolean;
  error?: string;
  venta_id?: number;
};

const HEARTBEAT_URL = '/cashier/api/heartbeat/';
const SYNC_URL = '/cashier/api/offline/sync-sale/';
const POLL_INTERVAL_MS = 10_000;

function getCsrfToken(): string {
  let last = '';
  for (const part of document.cookie.split(';')) {
    const c = part.trim();
    const eq = c.indexOf('=');
    if (eq <= 0) continue;
    if (c.slice(0, eq) !== 'csrftoken') continue;
    last = c.slice(eq + 1);
  }
  return last ? decodeURIComponent(last) : '';
}

export interface UseConnectionStatusOptions {
  onCatalogRefresh?: () => Promise<void>;
  onSyncComplete?: (results: SyncResult[]) => void;
}

export function useConnectionStatus(options: UseConnectionStatusOptions = {}) {
  const [isOffline, setIsOffline] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const wasOfflineRef = useRef(false);
  const syncingRef = useRef(false);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  const refreshPendingCount = useCallback(async () => {
    try {
      const n = await getPendingCount();
      setPendingCount(n);
    } catch {
      // IndexedDB unavailable — not critical
    }
  }, []);

  const syncAll = useCallback(async (): Promise<SyncResult[]> => {
    if (syncingRef.current) return [];
    syncingRef.current = true;
    const results: SyncResult[] = [];
    try {
      const queued = await loadQueuedSales();
      for (const sale of queued) {
        try {
          const res = await fetch(SYNC_URL, {
            method: 'POST',
            credentials: 'include',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify(sale.payload),
          });
          const json = (await res.json().catch(() => ({}))) as Record<string, unknown>;
          if (res.ok && json['success']) {
            await removeSaleFromQueue(sale.offline_idempotency_key);
            results.push({
              key: sale.offline_idempotency_key,
              success: true,
              venta_id: typeof json['venta_id'] === 'number' ? (json['venta_id'] as number) : undefined,
            });
          } else {
            results.push({
              key: sale.offline_idempotency_key,
              success: false,
              error: typeof json['error'] === 'string' ? (json['error'] as string) : `HTTP ${res.status}`,
            });
          }
        } catch (err) {
          results.push({
            key: sale.offline_idempotency_key,
            success: false,
            error: err instanceof Error ? err.message : String(err),
          });
        }
      }
    } finally {
      syncingRef.current = false;
      await refreshPendingCount();
      if (results.length > 0) {
        optionsRef.current.onSyncComplete?.(results);
      }
    }
    return results;
  }, [refreshPendingCount]);

  useEffect(() => {
    void refreshPendingCount();
  }, [refreshPendingCount]);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const res = await fetch(HEARTBEAT_URL, {
          credentials: 'include',
          cache: 'no-store',
          signal: AbortSignal.timeout(5000),
        });
        if (cancelled) return;
        if (res.ok) {
          const comingBack = wasOfflineRef.current;
          wasOfflineRef.current = false;
          setIsOffline(false);
          if (comingBack) {
            try { await optionsRef.current.onCatalogRefresh?.(); } catch { /* */ }
            void syncAll();
          }
        } else {
          throw new Error(`status ${res.status}`);
        }
      } catch {
        if (cancelled) return;
        wasOfflineRef.current = true;
        setIsOffline(true);
      }
    };

    void check();
    const id = setInterval(() => void check(), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [syncAll]);

  return { isOffline, pendingCount, syncAll, refreshPendingCount };
}
