import React, { useEffect, useState } from 'react';
import { api } from '../../utils/apiClient';
import { priorityColor, statusColor } from '../../utils/theme';
import AdminLayout from '../../components/layout/AdminLayout';

interface Ticket {
  id: string; user_id: string; user_name: string; user_company: string; user_email: string;
  subject: string; description: string; priority: string; status: string;
  category: string; admin_response: string | null; created_at: string; updated_at: string;
}

export default function TicketDashboard() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [filter, setFilter] = useState('all');
  const [prioFilter, setPrioFilter] = useState('all');
  const [responding, setResponding] = useState<Ticket | null>(null);
  const [response, setResponse] = useState('');
  const [responseStatus, setResponseStatus] = useState('resolved');
  const [msg, setMsg] = useState('');

  const load = () => api.get<{ tickets: Ticket[] }>('/tickets/admin/all').then(d => setTickets(d.tickets)).catch(() => {});
  useEffect(() => { load(); }, []);

  const filtered = tickets.filter(t => {
    if (filter !== 'all' && t.status !== filter) return false;
    if (prioFilter !== 'all' && t.priority !== prioFilter) return false;
    return true;
  });

  const counts = {
    open: tickets.filter(t => t.status === 'open').length,
    in_progress: tickets.filter(t => t.status === 'in_progress').length,
    resolved: tickets.filter(t => t.status === 'resolved').length,
    high: tickets.filter(t => t.priority === 'high' && t.status === 'open').length,
  };

  const respond = async () => {
    if (!responding || response.length < 20) return;
    await api.put(`/tickets/admin/${responding.id}/respond`, { admin_response: response, status: responseStatus });
    setResponding(null);
    setResponse('');
    setMsg('Response sent successfully.');
    setTimeout(() => setMsg(''), 3000);
    load();
  };

  return (
    <AdminLayout>
      <div className="p-6 space-y-4">
        <h1 className="text-2xl font-bold text-slate-900">Support Tickets</h1>

        {msg && <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-2 text-sm">{msg}</div>}

        {/* Stats */}
        <div className="flex gap-3">
          {[
            { label: 'Open', count: counts.open, color: '#f59e0b' },
            { label: 'In Progress', count: counts.in_progress, color: '#8b5cf6' },
            { label: 'Resolved', count: counts.resolved, color: '#16a34a' },
            { label: 'High Priority', count: counts.high, color: '#ef4444' },
          ].map(s => (
            <div key={s.label} className="bg-white rounded-lg px-4 py-3 border border-slate-200 flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ background: s.color }} />
              <span className="text-sm text-slate-600">{s.label}</span>
              <span className="font-bold text-slate-900">{s.count}</span>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          {['all','open','in_progress','resolved'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize ${filter === f ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
              {f.replace('_', ' ')}
            </button>
          ))}
          <span className="mx-2 text-slate-300">|</span>
          {['all','high','medium','low'].map(p => (
            <button key={p} onClick={() => setPrioFilter(p)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize ${prioFilter === p ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
              {p}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left p-3">ID</th>
                <th className="text-left p-3">User</th>
                <th className="text-left p-3">Subject</th>
                <th className="text-center p-3">Category</th>
                <th className="text-center p-3">Priority</th>
                <th className="text-center p-3">Status</th>
                <th className="text-left p-3">Raised</th>
                <th className="text-center p-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(t => (
                <tr key={t.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="p-3 font-mono text-xs text-slate-500">{t.id}</td>
                  <td className="p-3">
                    <p className="font-medium">{t.user_name}</p>
                    <p className="text-xs text-slate-500">{t.user_company}</p>
                  </td>
                  <td className="p-3 max-w-[200px] truncate">{t.subject}</td>
                  <td className="p-3 text-center">
                    <span className="px-2 py-0.5 rounded-full text-xs bg-slate-100">{t.category}</span>
                  </td>
                  <td className="p-3 text-center">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium text-white"
                      style={{ background: priorityColor(t.priority) }}>{t.priority}</span>
                  </td>
                  <td className="p-3 text-center">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium text-white"
                      style={{ background: statusColor(t.status) }}>{t.status.replace('_', ' ')}</span>
                  </td>
                  <td className="p-3 text-xs text-slate-500">{new Date(t.created_at).toLocaleDateString()}</td>
                  <td className="p-3 text-center">
                    {t.status !== 'resolved' ? (
                      <button onClick={() => { setResponding(t); setResponse(''); }}
                        className="px-3 py-1 rounded-lg text-xs bg-blue-50 text-blue-600 hover:bg-blue-100">Respond</button>
                    ) : (
                      <span className="text-xs text-slate-400">Done</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && <p className="p-6 text-center text-slate-400">No tickets match filters.</p>}
        </div>

        {/* Response Modal */}
        {responding && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4">
              <h3 className="text-lg font-semibold">Respond to Ticket</h3>
              <div className="bg-slate-50 rounded-lg p-3 text-sm">
                <p className="font-medium">{responding.user_name} — {responding.user_company}</p>
                <p className="text-slate-600 mt-1">{responding.subject}</p>
                <p className="text-slate-500 mt-2 text-xs">{responding.description}</p>
              </div>
              <textarea value={response} onChange={e => setResponse(e.target.value)}
                placeholder="Type your response (min 20 characters)..."
                rows={4} className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm" />
              <div className="flex gap-2">
                <select value={responseStatus} onChange={e => setResponseStatus(e.target.value)}
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm">
                  <option value="in_progress">In Progress</option>
                  <option value="resolved">Resolved</option>
                </select>
                <button onClick={respond} disabled={response.length < 20}
                  className="flex-1 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                  Send Response
                </button>
                <button onClick={() => setResponding(null)}
                  className="px-4 py-2 rounded-lg bg-slate-100 text-slate-600 text-sm">Cancel</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
