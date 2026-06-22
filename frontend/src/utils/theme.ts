export const colors = {
  bgDark: '#0f172a',
  bgMid: '#1e293b',
  bgLight: '#f8fafc',
  bgCard: '#ffffff',
  primary: '#2563eb',
  primaryHov: '#1d4ed8',
  healthy: '#16a34a',
  warning: '#d97706',
  critical: '#dc2626',
  textPrimary: '#0f172a',
  textSecondary: '#64748b',
  textInverse: '#f1f5f9',
  border: '#e2e8f0',
  borderDark: '#334155',
};

export const healthColor = (score: number): string => {
  if (score >= 80) return colors.healthy;
  if (score >= 50) return colors.warning;
  return colors.critical;
};

export const priorityColor = (p: string): string =>
  ({ high: '#ef4444', medium: '#f59e0b', low: '#3b82f6' } as Record<string, string>)[p] ?? '#6b7280';

export const statusColor = (s: string): string =>
  ({
    open: '#f59e0b',
    in_progress: '#8b5cf6',
    resolved: '#16a34a',
    active: '#16a34a',
    cancelled: '#ef4444',
    past_due: '#f59e0b',
  } as Record<string, string>)[s] ?? '#6b7280';
