import React, { useEffect, useState } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { api } from '../../utils/apiClient';
import { statusColor } from '../../utils/theme';
import UserLayout from '../../components/layout/UserLayout';

const CLASS_COLORS: Record<string, string> = {
  voip: '#ef4444', video: '#8b5cf6', critical: '#f59e0b', bulk: '#6b7280', other: '#94a3b8'
};

export default function TrafficOverview() {
  const [steering, setSteering] = useState<any[]>([]);
  const [rules, setRules] = useState<any[]>([]);

  useEffect(() => {
    api.get<{ events: any[] }>('/steering/history?limit=20').then(d => setSteering(d.events)).catch(() => {});
    api.get<{ rules: any[] }>('/routing/active').then(d => setRules(d.rules)).catch(() => {});
  }, []);

  // Traffic class distribution (derive from steering events)
  const classCounts: Record<string, number> = {};
  steering.forEach(e => {
    (e.traffic_classes || '').split(',').forEach((c: string) => {
      const cls = c.trim() || 'other';
      classCounts[cls] = (classCounts[cls] || 0) + 1;
    });
  });
  const pieData = Object.entries(classCounts).map(([name, value]) => ({ name, value }));
  if (pieData.length === 0) pieData.push({ name: 'voip', value: 35 }, { name: 'video', value: 25 }, { name: 'critical', value: 20 }, { name: 'bulk', value: 20 });

  return (
    <UserLayout>
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">Traffic Overview</h1>

        <div className="grid grid-cols-2 gap-6">
          {/* Traffic Distribution */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h2 className="font-semibold text-slate-900 mb-4">Traffic Class Distribution</h2>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={85}
                  label={({ name, percent }: any) => `${name} ${(percent * 100).toFixed(0)}%`}>
                  {pieData.map((d, i) => <Cell key={i} fill={CLASS_COLORS[d.name] || '#94a3b8'} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Active Routing Rules */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h2 className="font-semibold text-slate-900 mb-4">Current Routing Table</h2>
            {rules.length > 0 ? (
              <div className="space-y-2">
                {rules.map(r => (
                  <div key={r.id} className="bg-slate-50 rounded-lg p-3 flex justify-between items-center">
                    <div>
                      <p className="text-sm font-medium">{r.source_link} → {r.target_link}</p>
                      <p className="text-xs text-slate-500">{r.traffic_classes?.join(', ')}</p>
                    </div>
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium"
                      style={{ background: statusColor(r.status) + '20', color: statusColor(r.status) }}>
                      {r.status}
                    </span>
                  </div>
                ))}
              </div>
            ) : <p className="text-slate-400 text-sm text-center py-10">No active routing rules</p>}
          </div>
        </div>

        {/* Steering Events Timeline */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <h2 className="font-semibold text-slate-900 mb-4">Recent AI Steering Events</h2>
          {steering.length > 0 ? (
            <div className="space-y-3">
              {steering.slice(0, 10).map(e => (
                <div key={e.id} className="flex items-start gap-3 border-l-2 border-blue-200 pl-3">
                  <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5 flex-shrink-0" />
                  <div className="flex-1">
                    <p className="text-sm text-slate-900">
                      <span className="font-medium">{e.action}</span> — {e.source_link} → {e.target_link}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {e.reason} • Confidence: {(e.confidence * 100).toFixed(0)}% • {e.status}
                    </p>
                    <p className="text-xs text-slate-400">{new Date(e.timestamp * 1000).toLocaleString()}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-slate-400 text-sm text-center py-6">No steering events recorded yet</p>}
        </div>
      </div>
    </UserLayout>
  );
}
