import React, { useEffect, useState } from 'react';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { api } from '../../utils/apiClient';
import AdminLayout from '../../components/layout/AdminLayout';

const PLAN_COLORS: Record<string, string> = {
  Starter: '#3b82f6', Professional: '#8b5cf6', Enterprise: '#f59e0b'
};

export default function RevenueDashboard() {
  const [revenue, setRevenue] = useState<any>(null);

  useEffect(() => {
    api.get<any>('/billing/admin/revenue').then(setRevenue).catch(() => {});
  }, []);

  const mrr = revenue?.total_mrr ?? 0;
  const arr = revenue?.arr ?? 0;
  const byPlan = revenue?.by_plan ?? [];
  const monthly = (revenue?.monthly_trend ?? []).slice(0, 12).reverse();
  const userCount = byPlan.reduce((s: number, p: any) => s + (p.count || 0), 0);
  const arpu = userCount > 0 ? mrr / userCount : 0;

  return (
    <AdminLayout>
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">Revenue Dashboard</h1>

        {/* KPI row */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Monthly Recurring Revenue', value: `$${mrr.toLocaleString()}`, color: '#8b5cf6' },
            { label: 'Annual Run Rate', value: `$${arr.toLocaleString()}`, color: '#3b82f6' },
            { label: 'Avg Revenue Per User', value: `$${arpu.toFixed(0)}`, color: '#0ea5e9' },
            { label: 'Active Paying Users', value: userCount, color: '#16a34a' },
          ].map(c => (
            <div key={c.label} className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
              <p className="text-sm text-slate-500">{c.label}</p>
              <p className="text-2xl font-bold mt-1" style={{ color: c.color }}>{c.value}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Revenue by Plan */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h2 className="font-semibold text-slate-900 mb-4">Revenue by Plan</h2>
            {byPlan.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={byPlan} dataKey="revenue" nameKey="plan_name"
                       cx="50%" cy="50%" outerRadius={90} label={({ plan_name, revenue }: any) => `${plan_name}: $${revenue}`}>
                    {byPlan.map((p: any, i: number) => (
                      <Cell key={i} fill={PLAN_COLORS[p.plan_name] || '#6b7280'} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : <p className="text-slate-400 text-center py-10">No data</p>}
          </div>

          {/* Monthly Trend */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h2 className="font-semibold text-slate-900 mb-4">Monthly Revenue Trend</h2>
            {monthly.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={monthly}>
                  <XAxis dataKey="month" tickFormatter={(v: string) => v?.slice(0, 7)} tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="revenue" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="text-slate-400 text-center py-10">No invoice data yet</p>}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
