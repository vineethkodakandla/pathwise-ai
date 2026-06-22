import React, { useEffect, useState } from 'react';
import { api } from '../../utils/apiClient';
import { priorityColor, statusColor } from '../../utils/theme';
import UserLayout from '../../components/layout/UserLayout';

interface Ticket {
  id: string; subject: string; description: string; priority: string;
  status: string; category: string; admin_response: string | null;
  created_at: string; updated_at: string;
}

export default function SupportTickets() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [form, setForm] = useState({ subject: '', description: '', priority: 'medium', category: 'general' });
  const [msg, setMsg] = useState('');

  const load = () => api.get<{ tickets: Ticket[] }>('/tickets/my').then(d => setTickets(d.tickets)).catch(() => {});
  useEffect(() => { load(); }, []);

  const submit = async () => {
    if (!form.subject || form.description.length < 20) return;
    const res = await api.post<any>('/tickets/', form);
    setMsg(`Ticket #${res.ticket_id} raised successfully. We'll respond within 24 hours.`);
    setShowForm(false);
    setForm({ subject: '', description: '', priority: 'medium', category: 'general' });
    load();
    setTimeout(() => setMsg(''), 5000);
  };

  const categories = ['general', 'network_issue', 'billing', 'feature_request', 'bug_report', 'compliance'];

  return (
    <UserLayout>
      <div className="p-6 space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold text-slate-900">Support Tickets</h1>
          <button onClick={() => setShowForm(true)}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700">
            Raise a Ticket
          </button>
        </div>

        {msg && <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-2 text-sm">{msg}</div>}

        {/* Ticket List */}
        <div className="space-y-3">
          {tickets.map(t => (
            <div key={t.id} className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-4 flex justify-between items-center cursor-pointer hover:bg-slate-50"
                   onClick={() => setExpanded(expanded === t.id ? null : t.id)}>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs text-slate-400">{t.id}</span>
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium text-white"
                      style={{ background: priorityColor(t.priority) }}>{t.priority}</span>
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium text-white"
                      style={{ background: statusColor(t.status) }}>{t.status.replace('_', ' ')}</span>
                    <span className="px-2 py-0.5 rounded-full text-xs bg-slate-100 text-slate-600">{t.category.replace('_', ' ')}</span>
                  </div>
                  <p className="font-medium text-slate-900">{t.subject}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{new Date(t.created_at).toLocaleDateString()}</p>
                </div>
                <span className="text-slate-400">{expanded === t.id ? '▲' : '▼'}</span>
              </div>
              {expanded === t.id && (
                <div className="px-4 pb-4 border-t border-slate-100 pt-3">
                  <p className="text-sm text-slate-700">{t.description}</p>
                  {t.admin_response && (
                    <div className="mt-3 bg-blue-50 rounded-lg p-3 border border-blue-100">
                      <p className="text-xs font-semibold text-blue-700 mb-1">PathWise Support</p>
                      <p className="text-sm text-blue-900">{t.admin_response}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          {tickets.length === 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
              <p className="text-slate-400">No tickets yet. Click "Raise a Ticket" to get started.</p>
            </div>
          )}
        </div>

        {/* New Ticket Modal */}
        {showForm && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4">
              <h3 className="text-lg font-semibold text-slate-900">Raise a New Ticket</h3>
              <input value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })}
                placeholder="Subject" className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm" />
              <div className="grid grid-cols-2 gap-3">
                <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm capitalize">
                  {categories.map(c => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
                </select>
                <div className="flex gap-2">
                  {['low', 'medium', 'high'].map(p => (
                    <button key={p} onClick={() => setForm({ ...form, priority: p })}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium capitalize ${form.priority === p ? 'text-white' : 'bg-slate-100 text-slate-600'}`}
                      style={form.priority === p ? { background: priorityColor(p) } : {}}>{p}</button>
                  ))}
                </div>
              </div>
              <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                placeholder="Describe your issue in detail (min 20 characters)..."
                rows={4} className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm" />
              <div className="flex gap-2">
                <button onClick={submit} disabled={!form.subject || form.description.length < 20}
                  className="flex-1 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                  Submit Ticket
                </button>
                <button onClick={() => setShowForm(false)}
                  className="px-4 py-2 rounded-lg bg-slate-100 text-slate-600 text-sm">Cancel</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </UserLayout>
  );
}
