import { getCsrfToken } from './csrf';

function isSessionExpired(status: number, ct: string): boolean {
  if (status === 401 || status === 403) return true;
  // status 200 with HTML = fetch followed a redirect to the login page
  // status 5xx with HTML = server error, NOT a session issue
  return status === 200 && ct.includes('text/html');
}

export async function apiGet<T>(url: string): Promise<T> {
  const res = await fetch(url, { credentials: 'include' });
  const ct = res.headers.get('content-type') || '';
  if (isSessionExpired(res.status, ct)) {
    window.location.href = '/login/';
    throw new Error('Session expired');
  }
  if (!ct.includes('application/json')) {
    throw new Error(`Server error ${res.status}`);
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
  if (isSessionExpired(res.status, ct)) {
    window.location.href = '/login/';
    throw new Error('Session expired');
  }
  if (!ct.includes('application/json')) {
    throw new Error(`Server error ${res.status}`);
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as any;
    throw new Error(data?.error || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}
