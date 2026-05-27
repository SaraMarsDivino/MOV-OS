import { getCsrfToken } from './csrf';

export async function apiGet<T>(url: string): Promise<T> {
  const res = await fetch(url, { credentials: 'include' });
  const ct = res.headers.get('content-type') || '';
  if (!ct.includes('application/json')) {
    window.location.href = '/login/';
    throw new Error('Non-JSON response');
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as any;
    throw new Error(data?.error || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function apiPost<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(body),
  });
  const ct = res.headers.get('content-type') || '';
  if (!ct.includes('application/json')) {
    window.location.href = '/login/';
    throw new Error('Non-JSON response');
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as any;
    throw new Error(data?.error || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}
