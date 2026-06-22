import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';
import { api } from '../../utils/apiClient';
import { healthColor } from '../../utils/theme';
import AdminLayout from '../../components/layout/AdminLayout';

interface AdminUser { id: string; name: string; company: string; site_count: number; }

export default function SiteAnalytics() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [selectedUser, setSelectedUser] = useState('');
  const [analytics, setAnalytics] = useState<any[]>([]);

  useEffect(() => {
    api.get<{ users: AdminUser[] }>('/admin/users').then(d => {
      const biz = (d.users || []).filter((u: any) => u.role !== 'SUPER_ADMIN');
      setUsers(biz);
      if (biz.length > 0) setSelectedUser(biz[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedUser) return;
    api.get<{ analytics: any[] }>(`/admin/users/${selectedUser}/analytics?hours=24`)
      .then(d => setAnalytics(d.analytics)).catch(() => setAnalytics([]));
  }, [selectedUser]);

  return (
    <AdminLayout>
      <div className="p-6 space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold text-slate-900">Site Analytics</h1>
          <select value={selectedUser} onChange={e => setSelectedUser(e.target.value)}
            className="px-4 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none">
            {users.map(u => (
              <option key={u.id} value={u.id}>{u.name} — {u.company}</option>
            ))}
          </select>
        </div>

        {analytics.length > 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="text-left p-3">Site</th>
                  <th className="text-left p-3">Link</th>
                  <th className="text-right p-3">Avg Latency</th>
                  <th className="text-right p-3">Avg Health</th>
                  <th className="text-right p-3">Avg Loss</th>
                  <th className="text-right p-3">Data Points</th>
                </tr>
              </thead>
              <tbody>
                {analytics.map((r, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="p-3 font-medium">{r.site_name}</td>
                    <td className="p-3 capitalize">{r.link_type}</td>
                    <td className="p-3 text-right">{r.avg_latency} ms</td>
                    <td className="p-3 text-right">
                      <span className="font-bold" style={{ color: healthColor(r.avg_health) }}>{r.avg_health}</span>
                    </td>
                    <td className="p-3 text-right">{r.avg_loss}%</td>
                    <td className="p-3 text-right text-slate-500">{r.data_points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 text-center">
            <p className="text-slate-400">
              {selectedUser ? 'No telemetry data available for this user yet.' : 'Select a user to view analytics.'}
            </p>
            <p className="text-xs text-slate-400 mt-2">Data appears once the continuous simulator is running.</p>
          </div>
        )}

        {/* Cross-user comparison */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <h2 className="font-semibold text-slate-900 mb-4">All Users — Health Overview</h2>
          <div className="grid grid-cols-4 gap-3">
            {users.map(u => (
              <div key={u.id} className="bg-slate-50 rounded-lg p-3 cursor-pointer hover:bg-slate-100 transition-colors"
                   onClick={() => setSelectedUser(u.id)}>
                <p className="font-medium text-sm text-slate-900">{u.name}</p>
                <p className="text-xs text-slate-500">{u.company}</p>
                <p className="text-xs text-slate-400 mt-1">{u.site_count} sites</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
