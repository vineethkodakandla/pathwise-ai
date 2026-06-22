import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../../utils/apiClient';
import AdminLayout from '../../components/layout/AdminLayout';

interface LSTMModel {
  id: string; name: string; description: string; sequence_length: number;
  hidden_units: number; num_layers: number; dropout: number;
  learning_rate: number; batch_size: number; epochs: number;
  is_active: boolean; accuracy: number | null; mae_latency: number | null;
  created_at: string;
}

export default function LSTMControlCenter() {
  const [models, setModels] = useState<LSTMModel[]>([]);
  const [tab, setTab] = useState<'active' | 'library' | 'perf'>('active');
  const [params, setParams] = useState({ prediction_window_s: 60, health_threshold: 70, confidence_threshold: 0.85, brownout_sensitivity: 0.7 });
  const [newModel, setNewModel] = useState({ name: '', description: '', sequence_length: 60, hidden_units: 128, num_layers: 2, dropout: 0.2, learning_rate: 0.001, batch_size: 32, epochs: 100 });
  const [msg, setMsg] = useState('');

  const load = () => api.get<{ models: LSTMModel[] }>('/lstm/models').then(d => setModels(d.models)).catch(() => {});
  useEffect(() => { load(); }, []);

  const active = models.find(m => m.is_active);

  const activate = async (id: string) => {
    await api.post(`/lstm/models/${id}/activate`, {});
    load();
  };

  const applyParams = async () => {
    await api.put('/lstm/hyperparams', params);
    setMsg('Parameters applied successfully.');
    setTimeout(() => setMsg(''), 3000);
  };

  const createModel = async () => {
    if (!newModel.name) return;
    await api.post('/lstm/models', newModel);
    setNewModel({ name: '', description: '', sequence_length: 60, hidden_units: 128, num_layers: 2, dropout: 0.2, learning_rate: 0.001, batch_size: 32, epochs: 100 });
    load();
  };

  const retrain = async (id: string) => {
    await api.post(`/lstm/retrain?model_id=${id}`, {});
    setMsg('Retrain job queued. Check logs for progress.');
    setTimeout(() => setMsg(''), 5000);
  };

  const tabs = [
    { id: 'active' as const, label: 'Active Model' },
    { id: 'library' as const, label: 'Model Library' },
    { id: 'perf' as const, label: 'Performance' },
  ];

  return (
    <AdminLayout>
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">LSTM Control Center</h1>

        {msg && (
          <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-2 text-sm">{msg}</div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit">
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                tab === t.id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}>{t.label}</button>
          ))}
        </div>

        {/* Active Model Tab */}
        {tab === 'active' && active && (
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">{active.name}</h2>
                  <p className="text-sm text-slate-500 mt-1">{active.description}</p>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-green-50 text-green-700">ACTIVE</span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-sm">
                {[
                  { label: 'Accuracy', value: active.accuracy ? `${active.accuracy}%` : 'N/A' },
                  { label: 'Latency MAE', value: active.mae_latency ? `${active.mae_latency} ms` : 'N/A' },
                  { label: 'Seq Length', value: active.sequence_length },
                  { label: 'Hidden Units', value: active.hidden_units },
                  { label: 'Layers', value: active.num_layers },
                  { label: 'Dropout', value: active.dropout },
                ].map(s => (
                  <div key={s.label} className="bg-slate-50 rounded-lg p-2">
                    <p className="text-xs text-slate-500">{s.label}</p>
                    <p className="font-semibold text-slate-900">{s.value}</p>
                  </div>
                ))}
              </div>
              <button onClick={() => retrain(active.id)}
                className="w-full py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors">
                Retrain with Current Config
              </button>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
              <h2 className="text-lg font-semibold text-slate-900">Inference Parameters</h2>
              {[
                { key: 'prediction_window_s', label: 'Prediction Window', min: 30, max: 120, step: 5, unit: 's' },
                { key: 'health_threshold', label: 'Health Threshold', min: 50, max: 90, step: 1, unit: '' },
                { key: 'confidence_threshold', label: 'Confidence Threshold', min: 0.5, max: 0.99, step: 0.01, unit: '' },
                { key: 'brownout_sensitivity', label: 'Brownout Sensitivity', min: 0.3, max: 1.0, step: 0.05, unit: '' },
              ].map(s => (
                <div key={s.key}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-slate-600">{s.label}</span>
                    <span className="font-mono text-slate-900">{(params as any)[s.key]}{s.unit}</span>
                  </div>
                  <input type="range" min={s.min} max={s.max} step={s.step}
                    value={(params as any)[s.key]}
                    onChange={e => setParams({ ...params, [s.key]: parseFloat(e.target.value) })}
                    className="w-full accent-blue-600" />
                </div>
              ))}
              <button onClick={applyParams}
                className="w-full py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors">
                Apply Changes
              </button>
            </div>
          </div>
        )}

        {/* Model Library Tab */}
        {tab === 'library' && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="text-left p-3">Name</th>
                    <th className="text-center p-3">Arch</th>
                    <th className="text-center p-3">Accuracy</th>
                    <th className="text-center p-3">MAE</th>
                    <th className="text-center p-3">Status</th>
                    <th className="text-center p-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map(m => (
                    <tr key={m.id} className="border-t border-slate-100">
                      <td className="p-3">
                        <p className="font-medium">{m.name}</p>
                        <p className="text-xs text-slate-500">{m.description}</p>
                      </td>
                      <td className="p-3 text-center text-xs font-mono">{m.sequence_length}/{m.hidden_units}/{m.num_layers}L</td>
                      <td className="p-3 text-center">{m.accuracy ? `${m.accuracy}%` : '—'}</td>
                      <td className="p-3 text-center">{m.mae_latency ? `${m.mae_latency}ms` : '—'}</td>
                      <td className="p-3 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${m.is_active ? 'bg-green-50 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                          {m.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="p-3 text-center">
                        {!m.is_active && (
                          <button onClick={() => activate(m.id)}
                            className="px-3 py-1 rounded-lg text-xs bg-blue-50 text-blue-600 hover:bg-blue-100">Set Active</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Create form */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <h3 className="font-semibold text-slate-900 mb-3">Create New Model Config</h3>
              <div className="grid grid-cols-3 gap-3">
                <input placeholder="Name" value={newModel.name} onChange={e => setNewModel({...newModel, name: e.target.value})}
                  className="px-3 py-2 rounded-lg border border-slate-300 text-sm" />
                <input placeholder="Description" value={newModel.description} onChange={e => setNewModel({...newModel, description: e.target.value})}
                  className="col-span-2 px-3 py-2 rounded-lg border border-slate-300 text-sm" />
                {[
                  { k: 'sequence_length', l: 'Seq Length', t: 'number' },
                  { k: 'hidden_units', l: 'Hidden Units', t: 'number' },
                  { k: 'num_layers', l: 'Layers', t: 'number' },
                  { k: 'dropout', l: 'Dropout', t: 'number' },
                  { k: 'learning_rate', l: 'LR', t: 'number' },
                  { k: 'epochs', l: 'Epochs', t: 'number' },
                ].map(f => (
                  <div key={f.k}>
                    <label className="text-xs text-slate-500">{f.l}</label>
                    <input type={f.t} value={(newModel as any)[f.k]}
                      onChange={e => setNewModel({...newModel, [f.k]: parseFloat(e.target.value) || 0})}
                      className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm" />
                  </div>
                ))}
              </div>
              <button onClick={createModel} className="mt-3 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700">
                Create Model
              </button>
            </div>
          </div>
        )}

        {/* Performance Tab */}
        {tab === 'perf' && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h2 className="font-semibold text-slate-900 mb-4">Model Accuracy Comparison</h2>
            {models.filter(m => m.accuracy).length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={models.filter(m => m.accuracy)}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis domain={[80, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="accuracy" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="text-slate-400 text-center py-10">No models with accuracy data yet</p>}
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
