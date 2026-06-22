// In local dev VITE_API_URL is unset → BASE is the relative '/api/v1' served via
// the Vite proxy (→ :8000). In a cloud deploy set VITE_API_URL to the backend
// origin (e.g. https://pathwise-ai.onrender.com) and calls go there directly.
const API_ROOT =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_URL) || '';
const BASE = `${API_ROOT}/api/v1`;

function getToken(): string {
  const stored = localStorage.getItem('pathwise_user');
  return stored ? JSON.parse(stored).access_token : '';
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      ...options.headers,
    },
  });
  if (res.status === 401) {
    window.location.href = '/login';
  }
  if (!res.ok) {
    const e = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(e.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
