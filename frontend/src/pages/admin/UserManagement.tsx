import React, { useEffect, useState } from 'react';
import { api } from '../../utils/apiClient';
import { statusColor } from '../../utils/theme';
import AdminLayout from '../../components/layout/AdminLayout';

interface AdminUser {
  id: string; name: string; email: string; company: string; industry: string;
  role: string; plan_name: string; monthly_price: number; sub_status: string;
  site_count: number; open_tickets: number; is_active: boolean;
}

export default function UserManagement() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');

  const load = () => api.get<{ users: AdminUser[] }>('/admin/users').then(d => setUsers((d.users || []).filter(u => u.role !== 'SUPER_ADMIN'))).catch(() => {});
  useEffect(() => { load(); }, []);

  const filtered = users.filter(u => {
    if (filter === 'active' && !u.is_active) return false;
    if (filter === 'suspended' && u.is_active) return false;
    if (['starter','professional','enterprise'].includes(filter) && u.plan_name?.toLowerCase() !== filter) return false;
    if (search) {
      const s = search.toLowerCase();
      return u.name.toLowerCase().includes(s) || u.email.toLowerCase().includes(s) || u.company?.toLowerCase().includes(s);
    }
    return true;
  });

  const suspend = async (id: string) => {
    await api.put(`/admin/users/${id}/suspend`, {});
    load();
  };
  const reactivate = async (id: string) => {
    await api.put(`/admin/users/${id}/reactivate`, {});
    load();
  };

  const filters = ['all','active','suspended','starter','professional','enterprise'];

  return (
    <AdminLayout>
      <div className="p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold text-slate-900">User Management</h1>
          <span className="text-sm text-slate-500">{users.length} total users</span>
        </div>

        {/* Search + Filters */}
        <div className="flex gap-3 items-center">
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, email, company..."
            className="flex-1 px-4 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
          <div className="flex gap-1">
            {filters.map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                  filter === f ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}>{f}</button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left p-3">User</th>
                <th className="text-left p-3">Company</th>
                <th className="text-left p-3">Industry</th>
                <th className="text-left p-3">Plan</th>
                <th className="text-center p-3">Sites</th>
                <th className="text-right p-3">MRR</th>
                <th className="text-center p-3">Status</th>
                <th className="text-center p-3">Tickets</th>
                <th className="text-center p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(u => (
                <tr key={u.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs font-bold">
                        {u.name.split(' ').map(n => n[0]).join('')}
                      </div>
                      <div>
                        <p className="font-medium text-slate-900">{u.name}</p>
                        <p className="text-xs text-slate-500">{u.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="p-3 text-slate-700">{u.company}</td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded-full text-xs bg-slate-100 text-slate-600">{u.industry}</span>
                  </td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">{u.plan_name}</span>
                  </td>
                  <td className="p-3 text-center">{u.site_count}</td>
                  <td className="p-3 text-right font-medium">${u.monthly_price}</td>
                  <td className="p-3 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${u.is_active ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                      {u.is_active ? 'Active' : 'Suspended'}
                    </span>
                  </td>
                  <td className="p-3 text-center">
                    {u.open_tickets > 0
                      ? <span className="px-2 py-0.5 rounded-full text-xs bg-red-50 text-red-600 font-medium">{u.open_tickets}</span>
                      : <span className="text-slate-400">0</span>}
                  </td>
                  <td className="p-3 text-center">
                    {u.is_active ? (
                      <button onClick={() => suspend(u.id)}
                        className="px-3 py-1 rounded-lg text-xs bg-red-50 text-red-600 hover:bg-red-100 transition-colors">
                        Suspend
                      </button>
                    ) : (
                      <button onClick={() => reactivate(u.id)}
                        className="px-3 py-1 rounded-lg text-xs bg-green-50 text-green-600 hover:bg-green-100 transition-colors">
                        Reactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="p-6 text-center text-slate-400">
              {users.length === 0 ? 'Loading users...' : 'No users match your filters.'}
            </p>
          )}
        </div>
      </div>
    </AdminLayout>
  );
}
