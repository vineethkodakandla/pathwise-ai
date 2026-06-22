import React, { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../../components/layout/AdminLayout';
import { api } from '../../utils/apiClient';

interface UserPriority {
  user_id: string;
  apps: { app: string; priority: string }[];
}

const PRIORITY_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  NORMAL: '#3b82f6',
  LOW: '#64748b',
  BLOCKED: '#6b7280',
};

const AppQoSOverview: React.FC = () => {
  const [data, setData] = useState<UserPriority[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get<{ users: UserPriority[] }>('/apps/admin/all-priorities');
      setData(resp.users || []);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return (
    <AdminLayout>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#0f172a', margin: 0 }}>
          App QoS Overview
        </h1>
        <p style={{ fontSize: 13, color: '#64748b', marginTop: 4 }}>
          View all users' current application priority rules across the platform.
        </p>
      </div>

      <div
        style={{
          backgroundColor: '#ffffff',
          borderRadius: 12,
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
        }}
      >
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8', fontSize: 13 }}>
            Loading...
          </div>
        ) : data.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8', fontSize: 13 }}>
            No active app priority rules
          </div>
        ) : (
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: 13,
            }}
          >
            <thead>
              <tr
                style={{
                  backgroundColor: '#f8fafc',
                  borderBottom: '1px solid #e2e8f0',
                }}
              >
                <th
                  style={{
                    textAlign: 'left',
                    padding: '12px 16px',
                    fontWeight: 600,
                    color: '#475569',
                    fontSize: 12,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  User
                </th>
                <th
                  style={{
                    textAlign: 'left',
                    padding: '12px 16px',
                    fontWeight: 600,
                    color: '#475569',
                    fontSize: 12,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  App Priorities
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr
                  key={row.user_id}
                  style={{ borderBottom: '1px solid #f1f5f9' }}
                >
                  <td
                    style={{
                      padding: '12px 16px',
                      fontWeight: 500,
                      color: '#0f172a',
                      verticalAlign: 'top',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.user_id}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {row.apps.map((entry, idx) => {
                        const color = PRIORITY_COLORS[entry.priority] || '#64748b';
                        return (
                          <span
                            key={idx}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 6,
                              padding: '4px 10px',
                              borderRadius: 6,
                              fontSize: 12,
                              fontWeight: 500,
                              backgroundColor: `${color}14`,
                              color: color,
                              border: `1px solid ${color}33`,
                            }}
                          >
                            {entry.app}
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 700,
                                textTransform: 'uppercase',
                              }}
                            >
                              {entry.priority}
                            </span>
                          </span>
                        );
                      })}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </AdminLayout>
  );
};

export default AppQoSOverview;
