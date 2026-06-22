import React, { useEffect, useState } from 'react';
import { api } from '../../utils/apiClient';
import { statusColor } from '../../utils/theme';
import UserLayout from '../../components/layout/UserLayout';

interface Plan { id: string; name: string; price: number; sites: number; links: number; }

export default function BillingDashboard() {
  const [tab, setTab] = useState<'current' | 'plans' | 'invoices'>('current');
  const [sub, setSub] = useState<any>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    api.get<any>('/billing/subscription').then(setSub).catch(() => {});
    api.get<{ plans: Plan[] }>('/billing/plans').then(d => setPlans(d.plans)).catch(() => {});
    api.get<{ invoices: any[] }>('/billing/invoices').then(d => setInvoices(d.invoices)).catch(() => {});
  }, []);

  const upgrade = async (planId: string) => {
    await api.post('/billing/subscription/upgrade', { plan_id: planId });
    setMsg('Plan upgraded successfully!');
    api.get<any>('/billing/subscription').then(setSub);
    setTimeout(() => setMsg(''), 3000);
  };

  const cancel = async () => {
    if (!window.confirm('Are you sure you want to cancel your subscription?')) return;
    await api.post('/billing/subscription/cancel', {});
    setMsg('Subscription cancelled.');
    api.get<any>('/billing/subscription').then(setSub);
    setTimeout(() => setMsg(''), 3000);
  };

  const PLAN_FEATURES: Record<string, string[]> = {
    starter: ['Basic Dashboard', 'Email Alerts', 'CSV Export', '2 Sites', '2 Links/Site'],
    professional: ['Full Dashboard', 'LSTM Forecasting', 'IBN Interface', 'Sandbox Validation', 'PDF Export', 'Priority Support', '5 Sites', '4 Links/Site'],
    enterprise: ['Full Dashboard', 'LSTM Forecasting', 'IBN + Sandbox', 'PDF Export', 'Dedicated Support', 'HIPAA Audit Log', 'Multi-Site Analytics', '20 Sites', '6 Links/Site'],
  };

  return (
    <UserLayout>
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">Billing & Subscription</h1>
        {msg && <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-2 text-sm">{msg}</div>}

        <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit">
          {[
            { id: 'current' as const, label: 'Current Plan' },
            { id: 'plans' as const, label: 'Change Plan' },
            { id: 'invoices' as const, label: 'Invoice History' },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-4 py-2 rounded-md text-sm font-medium ${tab === t.id ? 'bg-white shadow-sm text-slate-900' : 'text-slate-600'}`}>
              {t.label}
            </button>
          ))}
        </div>

        {/* Current Plan */}
        {tab === 'current' && sub && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 max-w-lg">
            <div className="flex items-center gap-3 mb-4">
              <span className="px-3 py-1 rounded-full text-sm font-bold bg-blue-100 text-blue-700">{sub.plan_name}</span>
              <span className="px-2 py-0.5 rounded-full text-xs" style={{ background: statusColor(sub.status) + '20', color: statusColor(sub.status) }}>
                {sub.status}
              </span>
            </div>
            <p className="text-3xl font-bold text-slate-900">${sub.monthly_price}<span className="text-sm font-normal text-slate-500">/month</span></p>
            <p className="text-sm text-slate-500 mt-2">Next billing: {sub.next_billing_date}</p>
            <p className="text-sm text-slate-500">Payment: Visa ending in {sub.card_last4 || '4242'}</p>
            <div className="mt-4 space-y-1">
              {PLAN_FEATURES[sub.plan_id]?.map(f => (
                <p key={f} className="text-sm text-slate-600 flex items-center gap-2">
                  <span className="text-green-500">&#10003;</span> {f}
                </p>
              ))}
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setTab('plans')} className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700">Upgrade Plan</button>
              <button onClick={cancel} className="px-4 py-2 rounded-lg bg-red-50 text-red-600 text-sm font-medium hover:bg-red-100">Cancel Subscription</button>
            </div>
          </div>
        )}

        {/* Plan Comparison */}
        {tab === 'plans' && (
          <div className="grid grid-cols-3 gap-4">
            {plans.map(p => {
              const isCurrent = sub?.plan_id === p.id;
              return (
                <div key={p.id} className={`bg-white rounded-xl border-2 shadow-sm p-5 ${isCurrent ? 'border-blue-500' : 'border-slate-200'}`}>
                  {isCurrent && <span className="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700 font-medium mb-2 inline-block">Current Plan</span>}
                  <h3 className="text-lg font-bold text-slate-900">{p.name}</h3>
                  <p className="text-2xl font-bold mt-2">${p.price}<span className="text-sm font-normal text-slate-500">/mo</span></p>
                  <p className="text-sm text-slate-500 mt-1">{p.sites} sites, {p.links} links/site</p>
                  <div className="mt-3 space-y-1">
                    {PLAN_FEATURES[p.id]?.map(f => (
                      <p key={f} className="text-xs text-slate-600">&#10003; {f}</p>
                    ))}
                  </div>
                  {!isCurrent && (
                    <button onClick={() => upgrade(p.id)}
                      className="w-full mt-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700">Select Plan</button>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Invoices */}
        {tab === 'invoices' && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="text-left p-3">Invoice</th>
                  <th className="text-left p-3">Period</th>
                  <th className="text-right p-3">Amount</th>
                  <th className="text-center p-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map(inv => (
                  <tr key={inv.id} className="border-t border-slate-100">
                    <td className="p-3 font-mono text-xs">{inv.id}</td>
                    <td className="p-3 text-slate-600">{inv.period_start} — {inv.period_end}</td>
                    <td className="p-3 text-right font-medium">${inv.amount}</td>
                    <td className="p-3 text-center">
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium"
                        style={{ background: statusColor(inv.status) + '20', color: statusColor(inv.status) }}>
                        {inv.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {invoices.length === 0 && <p className="p-6 text-center text-slate-400">No invoices yet</p>}
          </div>
        )}
      </div>
    </UserLayout>
  );
}
