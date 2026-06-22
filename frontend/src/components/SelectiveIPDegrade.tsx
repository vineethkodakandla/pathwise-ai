import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../utils/apiClient';

/**
 * Selective IP Degrade panel.
 *
 * Narrow-scope sibling to the App Priority Switch: instead of blocking an
 * entire application domain-set on the host, this lets the operator pick
 * specific remote IPs, choose "block" or "throttle <kbps>", and set a
 * duration. When the timer expires the backend auto-restores connectivity.
 *
 * Uses:
 *   GET  /api/v1/apps/selective/candidates/{app_id}
 *   GET  /api/v1/apps/selective
 *   POST /api/v1/apps/selective
 *   DELETE /api/v1/apps/selective/{rule_id}
 */

type Mode = 'block' | 'throttle';

interface AppOption {
  app_id: string;
  name: string;
  icon: string;
  color: string;
}

interface Candidates {
  app_id: string;
  display_name: string;
  ips: string[];
  cidrs: string[];
}

interface SelectiveRule {
  id: string;
  app_id: string | null;
  ips: string[];
  mode: Mode;
  throttle_kbps: number | null;
  started_at: number;
  duration_s: number;
  expires_at: number;
  reason: string;
  active: boolean;
  remaining_s: number;
}

interface Props {
  apps: AppOption[];
}

const PRESET_DURATIONS = [
  { label: '30s', value: 30 },
  { label: '1 min', value: 60 },
  { label: '2 min', value: 120 },
  { label: '5 min', value: 300 },
  { label: '15 min', value: 900 },
];

const PRESET_KBPS = [128, 256, 500, 1000, 2000];

const SelectiveIPDegrade: React.FC<Props> = ({ apps }) => {
  const [selectedApp, setSelectedApp] = useState<string>('');
  const [candidates, setCandidates] = useState<Candidates | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [manualIp, setManualIp] = useState('');
  const [mode, setMode] = useState<Mode>('throttle');
  const [kbps, setKbps] = useState<number>(500);
  const [durationS, setDurationS] = useState<number>(60);
  const [rules, setRules] = useState<SelectiveRule[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ text: string; type: 'ok' | 'err' } | null>(null);

  const fetchRules = useCallback(async () => {
    try {
      const data = await api.get<{ rules: SelectiveRule[] }>('/apps/selective');
      setRules(data.rules || []);
    } catch {
      /* silent */
    }
  }, []);

  useEffect(() => {
    fetchRules();
    const t = setInterval(fetchRules, 1000); // live countdown
    return () => clearInterval(t);
  }, [fetchRules]);

  const loadCandidates = useCallback(async (appId: string) => {
    if (!appId) { setCandidates(null); setPicked(new Set()); return; }
    try {
      const data = await api.get<Candidates>(`/apps/selective/candidates/${appId}`);
      setCandidates(data);
      setPicked(new Set()); // reset picks on app change
    } catch (err: any) {
      setMsg({ text: err.message || 'Failed to load candidate IPs', type: 'err' });
    }
  }, []);

  useEffect(() => { loadCandidates(selectedApp); }, [selectedApp, loadCandidates]);

  const togglePick = (ip: string) => {
    setPicked(prev => {
      const next = new Set(prev);
      if (next.has(ip)) next.delete(ip); else next.add(ip);
      return next;
    });
  };

  const addManualIp = () => {
    const v = manualIp.trim();
    if (!v) return;
    setPicked(prev => new Set(prev).add(v));
    setManualIp('');
  };

  const pickedList = useMemo(() => Array.from(picked), [picked]);

  const submit = async () => {
    if (pickedList.length === 0) {
      setMsg({ text: 'Pick at least one IP or CIDR first.', type: 'err' });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const body = {
        app_id: selectedApp || null,
        ips: pickedList,
        mode,
        duration_s: durationS,
        throttle_kbps: mode === 'throttle' ? kbps : null,
        reason: 'Selective IP degrade from UI',
      };
      const res = await api.post<{ rule: SelectiveRule; message: string }>(
        '/apps/selective', body,
      );
      setMsg({ text: res.message, type: 'ok' });
      setPicked(new Set());
      fetchRules();
    } catch (err: any) {
      setMsg({ text: err.message || 'Failed to apply selective rule', type: 'err' });
    } finally {
      setBusy(false);
    }
  };

  const stopRule = async (ruleId: string) => {
    try {
      await api.delete(`/apps/selective/${ruleId}`);
      fetchRules();
    } catch (err: any) {
      setMsg({ text: err.message || 'Failed to stop rule', type: 'err' });
    }
  };

  const stopAll = async () => {
    try {
      await api.post('/apps/selective/stop-all', {});
      fetchRules();
    } catch (err: any) {
      setMsg({ text: err.message || 'Failed to stop rules', type: 'err' });
    }
  };

  return (
    <div style={{
      backgroundColor: '#ffffff',
      borderRadius: 12,
      border: '1px solid #e2e8f0',
      padding: 20,
      marginBottom: 20,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <h2 style={{ fontSize: 15, fontWeight: 700, color: '#0f172a', margin: 0 }}>
          Selective IP Degrade
        </h2>
        {rules.length > 0 && (
          <button
            onClick={stopAll}
            style={{
              fontSize: 11, padding: '4px 10px', borderRadius: 6,
              background: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca',
              cursor: 'pointer', fontWeight: 600,
            }}
          >
            Stop All ({rules.length})
          </button>
        )}
      </div>
      <p style={{ fontSize: 12, color: '#64748b', marginTop: 0, marginBottom: 14 }}>
        Degrade or block <b>specific IPs</b> (not the whole app) for a chosen duration.
        The host stays fully online; only the selected IPs are affected, and they
        auto-restore when the timer expires.
      </p>

      {msg && (
        <div style={{
          padding: '8px 12px', borderRadius: 8, marginBottom: 12,
          fontSize: 12, fontWeight: 500,
          background: msg.type === 'ok' ? '#f0fdf4' : '#fef2f2',
          color:      msg.type === 'ok' ? '#16a34a' : '#dc2626',
          border: `1px solid ${msg.type === 'ok' ? '#bbf7d0' : '#fecaca'}`,
        }}>{msg.text}</div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* -------- left: picker -------- */}
        <div>
          <label style={labelCss}>App</label>
          <select
            value={selectedApp}
            onChange={e => setSelectedApp(e.target.value)}
            style={inputCss}
          >
            <option value="">— Select app —</option>
            {apps.map(a => (
              <option key={a.app_id} value={a.app_id}>
                {a.name}
              </option>
            ))}
          </select>

          {candidates && (
            <div style={{ marginTop: 12 }}>
              <label style={labelCss}>
                Candidate IPs for {candidates.display_name}
              </label>
              <div style={{
                maxHeight: 180, overflowY: 'auto',
                border: '1px solid #e2e8f0', borderRadius: 8, padding: 6,
                background: '#f8fafc',
              }}>
                {candidates.ips.length === 0 && (
                  <div style={{ fontSize: 12, color: '#94a3b8', padding: 6 }}>
                    No candidate IPs resolved. Add one manually below.
                  </div>
                )}
                {candidates.ips.map(ip => (
                  <label key={ip} style={ipRowCss}>
                    <input
                      type="checkbox"
                      checked={picked.has(ip)}
                      onChange={() => togglePick(ip)}
                    />
                    <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{ip}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div style={{ marginTop: 12 }}>
            <label style={labelCss}>Or enter an IP / CIDR manually</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={manualIp}
                onChange={e => setManualIp(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') addManualIp(); }}
                placeholder="e.g. 172.217.14.110 or 142.250.0.0/16"
                style={{ ...inputCss, flex: 1 }}
              />
              <button onClick={addManualIp} style={btnSecondaryCss}>Add</button>
            </div>
          </div>

          {pickedList.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <label style={labelCss}>Selected ({pickedList.length})</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {pickedList.map(ip => (
                  <span key={ip} onClick={() => togglePick(ip)} style={chipCss}>
                    {ip} ×
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* -------- right: config + submit -------- */}
        <div>
          <label style={labelCss}>Mode</label>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <button
              onClick={() => setMode('throttle')}
              style={pillCss(mode === 'throttle', '#f59e0b')}
            >
              Throttle
            </button>
            <button
              onClick={() => setMode('block')}
              style={pillCss(mode === 'block', '#ef4444')}
            >
              Block
            </button>
          </div>

          {mode === 'throttle' && (
            <>
              <label style={labelCss}>Throttle to (kbps)</label>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                {PRESET_KBPS.map(v => (
                  <button
                    key={v}
                    onClick={() => setKbps(v)}
                    style={pillCss(kbps === v, '#f59e0b')}
                  >
                    {v < 1000 ? `${v} kbps` : `${v / 1000} Mbps`}
                  </button>
                ))}
              </div>
              <input
                type="number"
                min={32}
                value={kbps}
                onChange={e => setKbps(Math.max(32, Number(e.target.value)))}
                style={inputCss}
              />
            </>
          )}

          <label style={{ ...labelCss, marginTop: 12 }}>Duration</label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
            {PRESET_DURATIONS.map(d => (
              <button
                key={d.value}
                onClick={() => setDurationS(d.value)}
                style={pillCss(durationS === d.value, '#3b82f6')}
              >
                {d.label}
              </button>
            ))}
          </div>
          <input
            type="number"
            min={5}
            max={3600}
            value={durationS}
            onChange={e => setDurationS(Math.max(5, Math.min(3600, Number(e.target.value))))}
            style={inputCss}
          />
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
            Auto-restore when timer expires (5s – 1h).
          </div>

          <button
            onClick={submit}
            disabled={busy || pickedList.length === 0}
            style={{
              marginTop: 16, width: '100%',
              padding: '10px 14px', borderRadius: 8, border: 'none',
              background: pickedList.length === 0 || busy ? '#cbd5e1' : '#0f172a',
              color: '#fff', fontWeight: 700, fontSize: 13,
              cursor: pickedList.length === 0 || busy ? 'not-allowed' : 'pointer',
            }}
          >
            {busy ? 'Applying…' :
              mode === 'block'
                ? `Block ${pickedList.length} IP(s) for ${durationS}s`
                : `Throttle ${pickedList.length} IP(s) to ${kbps} kbps for ${durationS}s`
            }
          </button>
        </div>
      </div>

      {/* -------- active rules -------- */}
      {rules.length > 0 && (
        <div style={{ marginTop: 20, borderTop: '1px solid #e2e8f0', paddingTop: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#0f172a', marginBottom: 8 }}>
            Active rules
          </div>
          {rules.map(r => {
            const pct = Math.max(0, Math.min(100,
              (r.remaining_s / Math.max(1, r.duration_s)) * 100,
            ));
            return (
              <div key={r.id} style={{
                padding: 10, marginBottom: 8,
                border: '1px solid #e2e8f0', borderRadius: 8, background: '#f8fafc',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#0f172a' }}>
                    {r.mode.toUpperCase()}
                    {r.mode === 'throttle' && r.throttle_kbps ? ` ${r.throttle_kbps} kbps` : ''}
                    {r.app_id ? ` · ${r.app_id}` : ''}
                    {' · '}
                    <span style={{ fontFamily: 'monospace', color: '#475569' }}>
                      {r.ips.length} IP{r.ips.length === 1 ? '' : 's'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span style={{
                      fontSize: 11, fontWeight: 700,
                      color: r.remaining_s > 5 ? '#0f172a' : '#dc2626',
                    }}>
                      {r.remaining_s}s left
                    </span>
                    <button
                      onClick={() => stopRule(r.id)}
                      style={{
                        fontSize: 11, padding: '2px 8px', borderRadius: 6,
                        background: '#fff', color: '#dc2626',
                        border: '1px solid #fecaca', cursor: 'pointer', fontWeight: 600,
                      }}
                    >
                      Stop
                    </button>
                  </div>
                </div>
                <div style={{
                  height: 4, background: '#e2e8f0', borderRadius: 2, overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%', width: `${pct}%`,
                    background: r.mode === 'block' ? '#ef4444' : '#f59e0b',
                    transition: 'width 1s linear',
                  }} />
                </div>
                <div style={{
                  marginTop: 6, fontFamily: 'monospace', fontSize: 11, color: '#64748b',
                  wordBreak: 'break-all',
                }}>
                  {r.ips.slice(0, 4).join(', ')}
                  {r.ips.length > 4 ? ` +${r.ips.length - 4} more` : ''}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

const labelCss: React.CSSProperties = {
  display: 'block', fontSize: 11, fontWeight: 600,
  textTransform: 'uppercase', letterSpacing: '0.05em',
  color: '#64748b', marginBottom: 6,
};

const inputCss: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: 8,
  border: '1px solid #cbd5e1', fontSize: 13, boxSizing: 'border-box',
};

const btnSecondaryCss: React.CSSProperties = {
  padding: '8px 14px', borderRadius: 8, border: '1px solid #cbd5e1',
  background: '#fff', color: '#0f172a', cursor: 'pointer', fontWeight: 600, fontSize: 12,
};

const ipRowCss: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8,
  padding: '4px 6px', borderRadius: 4, cursor: 'pointer',
};

const chipCss: React.CSSProperties = {
  fontFamily: 'monospace', fontSize: 11,
  padding: '4px 8px', borderRadius: 12,
  background: '#e0f2fe', color: '#075985', cursor: 'pointer',
};

const pillCss = (active: boolean, accent: string): React.CSSProperties => ({
  padding: '6px 12px', borderRadius: 999, fontSize: 12, fontWeight: 600,
  cursor: 'pointer', border: `1px solid ${active ? accent : '#cbd5e1'}`,
  background: active ? `${accent}15` : '#fff',
  color: active ? accent : '#475569',
});

export default SelectiveIPDegrade;
