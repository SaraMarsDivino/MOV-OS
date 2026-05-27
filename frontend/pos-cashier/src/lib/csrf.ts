function getCookieValues(name: string): string[] {
  if (typeof document === 'undefined') return [];
  const cookies = document.cookie ? document.cookie.split(';') : [];
  const values: string[] = [];
  for (const raw of cookies) {
    const trimmed = raw.trim();
    if (!trimmed.startsWith(name + '=')) continue;
    values.push(decodeURIComponent(trimmed.substring(name.length + 1)));
  }
  return values;
}

export function getCsrfToken(): string {
  const values = getCookieValues('csrftoken');
  // Match Django behavior: last cookie wins.
  return values.length ? values[values.length - 1] : '';
}
