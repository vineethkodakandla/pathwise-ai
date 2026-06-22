import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../../utils/apiClient';
import { healthColor } from '../../utils/theme';
import AdminLayout from '../../components/layout/AdminLayout';

interface PlatformOverview {
  total_users: number;
  active_users: number;
  total_sites: number;
  mrr: number;
  open_tickets: number;
  urgent_tickets: number;
}

interface AdminUser {
  id: string; name: string; email: string; company: string; industry: string;
  plan_name: string; monthly_price: number; sub_status: string;
  site_count: number; open_tickets: number; is_active: boolean;
  role: string;
}

export default function AdminDashboard() {
  const [overview, setOverview] = useState<PlatformOverview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [revenue, setRevenue] = useState<any>(null);
  const nav = useNavigate();

  useEffect(() => {
    api.get<PlatformOverview>('/admin/platform/overview').then(setOverview).catch(() => {});
    api.get<{ users: AdminUser[] }>('/admin/users').then(d => setUsers((d.users || []).filter(u => u.role !== 'SUPER_ADMIN'))).catch(() => {});
    api.get<any>('/billing/admin/revenue').then(setRevenue).catch(() => {});
  }, []);

  const cards = overview ? [
    { label: 'Total Users', value: overview.total_users, color: '#3b82f6' },
    { label: 'Active Subscriptions', value: overview.active_users, color: '#16a34a' },
    { label: 'Monthly Revenue', value: `$${overview.mrr.toLocaleString()}`, color: '#8b5cf6' },
    { label: 'Total Sites', value: overview.total_sites, color: '#0ea5e9' },
    { label: 'Open Tickets', value: overview.open_tickets, color: overview.open_tickets > 0 ? '#ef4444' : '#6b7280' },
    { label: 'Platform Uptime', value: '99.97%', color: '#16a34a' },
  ] : [];

  return (
    <AdminLayout>
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">Platform Overview</h1>

        {/* KPI Cards */}
        <div className="grid grid-cols-3 gap-4">
          {cards.map(c => (
            <div key={c.label} className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
              <p className="text-sm text-slate-500">{c.label}</p>
              <p className="text-2xl font-bold mt-1" style={{ color: c.color }}>{c.value}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-6">
          {/* User Health Table */}
          <div className="col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm">
            <div className="p-4 border-b border-slate-200 flex justify-between items-center">
              <h2 className="font-semibold text-slate-900">User Health Status</h2>
              <button onClick={() => nav('/admin/users')}
                className="text-sm text-blue-600 hover:underline">View All</button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="text-left p-3">User</th>
                    <th className="text-left p-3">Company</th>
                    <th className="text-left p-3">Plan</th>
                    <th className="text-center p-3">Sites</th>
                    <th className="text-center p-3">Tickets</th>
                    <th className="text-center p-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id} className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                        onClick={() => nav('/admin/users')}>
                      <td className="p-3 font-medium">{u.name}</td>
                      <td className="p-3 text-slate-600">{u.company}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
                          {u.plan_name}
                        </span>
                      </td>
                      <td className="p-3 text-center">{u.site_count}</td>
                      <td className="p-3 text-center">
                        {u.open_tickets > 0
                          ? <span className="px-2 py-0.5 rounded-full text-xs bg-red-50 text-red-600">{u.open_tickets}</span>
                          : <span className="text-slate-400">0</span>}
                      </td>
                      <td className="p-3 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${u.is_active ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                          {u.is_active ? 'Active' : 'Suspended'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {users.length === 0 && (
                <p className="p-6 text-center text-slate-400">Loading users...</p>
              )}
            </div>
          </div>

          {/* Revenue Mini Chart */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
            <h2 className="font-semibold text-slate-900 mb-4">Monthly Revenue</h2>
            {revenue?.monthly_trend?.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={revenue.monthly_trend.slice(0, 6).reverse()}>
                  <XAxis dataKey="month" tickFormatter={(v: string) => v?.slice(5, 7)} tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="revenue" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[200px] text-slate-400 text-sm">
                {revenue ? `MRR: $${revenue.total_mrr}` : 'Loading revenue data...'}
              </div>
            )}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
