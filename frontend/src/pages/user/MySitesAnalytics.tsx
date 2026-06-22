import React, { useEffect, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { api } from '../../utils/apiClient';
import UserLayout from '../../components/layout/UserLayout';

export default function MySitesAnalytics() {
  const [profile, setProfile] = useState<any>(null);
  const [selectedSite, setSelectedSite] = useState('');
  const [siteData, setSiteData] = useState<any>(null);

  useEffect(() => {
    api.get<any>('/profile/').then(d => {
      setProfile(d);
      if (d.sites?.length > 0) setSelectedSite(d.sites[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedSite) return;
    const idx = selectedSite.split('-').pop() || '1';
    api.get<any>(`/telemetry/site/${idx}`).then(setSiteData).catch(() => {});
  }, [selectedSite]);

  const sites = profile?.sites ?? [];
  const links = siteData?.links ?? [];

  // Build chart data from link metrics
  const chartData = links.map((l: any, i: number) => ({
    name: l.link_id,
    latency: l.latency_ms,
    jitter: l.jitter_ms,
    loss: l.packet_loss_pct,
    health: l.health_score,
  }));

  return (
    <UserLayout>
      <div className="p-6 space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold text-slate-900">My Sites & Analytics</h1>
          <select value={selectedSite} onChange={e => setSelectedSite(e.target.value)}
            className="px-4 py-2 rounded-lg border border-slate-300 text-sm">
            {sites.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>

        {/* 2x2 metric grid */}
        <div className="grid grid-cols-2 gap-4">
          {[
            { title: 'Latency (ms)', dataKey: 'latency', color: '#3b82f6' },
            { title: 'Jitter (ms)', dataKey: 'jitter', color: '#8b5cf6' },
            { title: 'Packet Loss (%)', dataKey: 'loss', color: '#ef4444' },
            { title: 'Health Score', dataKey: 'health', color: '#16a34a' },
          ].map(chart => (
            <div key={chart.dataKey} className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">{chart.title}</h3>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Area type="monotone" dataKey={chart.dataKey} stroke={chart.color}
                      fill={chart.color} fillOpacity={0.1} strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : <p className="text-slate-400 text-sm text-center py-10">Waiting for data...</p>}
            </div>
          ))}
        </div>

        {/* Stats summary */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <h3 className="font-semibold text-slate-900 mb-3">Link Statistics</h3>
          <div className="grid grid-cols-6 gap-4 text-center text-sm">
            <div><p className="text-slate-400">Links</p><p className="font-bold text-lg">{links.length}</p></div>
            <div><p className="text-slate-400">Avg Health</p><p className="font-bold text-lg">{siteData?.health_score?.toFixed(0) ?? '—'}</p></div>
            <div><p className="text-slate-400">Status</p><p className="font-bold text-lg capitalize">{siteData?.status ?? '—'}</p></div>
            <div><p className="text-slate-400">Site ID</p><p className="font-bold text-lg">{siteData?.site_id ?? '—'}</p></div>
            <div><p className="text-slate-400">Plan Sites</p><p className="font-bold text-lg">{profile?.subscription?.plan_name ?? '—'}</p></div>
            <div><p className="text-slate-400">Data Points</p><p className="font-bold text-lg">{links.length * 60}</p></div>
          </div>
        </div>
      </div>
    </UserLayout>
  );
}
