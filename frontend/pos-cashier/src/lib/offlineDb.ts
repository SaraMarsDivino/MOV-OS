const DB_NAME = 'movos-offline';
const DB_VERSION = 1;
const CATALOG_STORE = 'catalog';
const QUEUE_STORE = 'sales_queue';

export interface CatalogProduct {
  id: number;
  nombre: string;
  precio_venta: number;
  stock: number;
  permitir_venta_sin_stock: boolean;
  en_sucursal: boolean;
  categoria_id: number | null;
  categoria_nombre: string | null;
}

export interface CatalogSnapshot {
  sucursal_id: number;
  sucursal_nombre: string;
  products: CatalogProduct[];
  timestamp: string;
}

export interface QueuedSale {
  offline_idempotency_key: string;
  offline_timestamp: string;
  payload: Record<string, unknown>;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => resolve(req.result as IDBDatabase);
    req.onupgradeneeded = (e) => {
      const db = (e.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(CATALOG_STORE)) {
        db.createObjectStore(CATALOG_STORE, { keyPath: 'key' });
      }
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        db.createObjectStore(QUEUE_STORE, { keyPath: 'offline_idempotency_key' });
      }
    };
  });
}

export async function saveCatalogSnapshot(snapshot: CatalogSnapshot): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(CATALOG_STORE, 'readwrite');
    tx.objectStore(CATALOG_STORE).put({ key: 'snapshot', ...snapshot });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function loadCatalogSnapshot(): Promise<CatalogSnapshot | null> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(CATALOG_STORE, 'readonly');
    const req = tx.objectStore(CATALOG_STORE).get('snapshot');
    req.onsuccess = () => {
      const r = req.result as (CatalogSnapshot & { key?: string }) | undefined;
      if (!r) { resolve(null); return; }
      const { key: _k, ...snap } = r;
      resolve(snap as CatalogSnapshot);
    };
    req.onerror = () => reject(req.error);
  });
}

export async function queueSale(sale: QueuedSale): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, 'readwrite');
    tx.objectStore(QUEUE_STORE).put(sale);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function loadQueuedSales(): Promise<QueuedSale[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, 'readonly');
    const req = tx.objectStore(QUEUE_STORE).getAll();
    req.onsuccess = () => resolve(req.result as QueuedSale[]);
    req.onerror = () => reject(req.error);
  });
}

export async function removeSaleFromQueue(key: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, 'readwrite');
    tx.objectStore(QUEUE_STORE).delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getPendingCount(): Promise<number> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, 'readonly');
    const req = tx.objectStore(QUEUE_STORE).count();
    req.onsuccess = () => resolve(req.result as number);
    req.onerror = () => reject(req.error);
  });
}
