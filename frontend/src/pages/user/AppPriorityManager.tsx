import React, { useState, useEffect, useCallback, useRef } from 'react';
import UserLayout from '../../components/layout/UserLayout';
import SelectiveIPDegrade from '../../components/SelectiveIPDegrade';
import { api } from '../../utils/apiClient';
import { useAuth } from '../../context/AuthContext';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface AppSignature {
  app_id: string;
  name: string;
  icon: string;
  color: string;
  category: string;
  quality_tiers: string[];
}

interface ActiveApp {
  app_id: string;
  name: string;
  connections: number;
  est_kbps: number;
}

interface PriorityEntry {
  app_id: string;
  priority: Priority;
}

interface AppliedApp {
  app_id: string;
  name: string;
  priority: Priority;
  guaranteed_kbps: number;
  ceil_kbps: number;
  estimated_quality: string;
}

type Priority = 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW' | 'BLOCKED';

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const PRIORITY_OPTIONS: Priority[] = ['CRITICAL', 'HIGH', 'NORMAL', 'LOW', 'BLOCKED'];

const PRIORITY_COLORS: Record<Priority, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  NORMAL: '#3b82f6',
  LOW: '#64748b',
  BLOCKED: '#6b7280',
};

const CATEGORIES = ['Video Calls', 'Streaming', 'Voice & Audio', 'Gaming', 'Productivity'];

const CATEGORY_MAP: Record<string, string> = {
  video_conferencing: 'Video Calls',
  video_call: 'Video Calls',
  streaming: 'Streaming',
  audio_streaming: 'Streaming',
  voip: 'Voice & Audio',
  communication: 'Voice & Audio',
  gaming: 'Gaming',
  productivity: 'Productivity',
  browser: 'Productivity',
  cloud_storage: 'Productivity',
  other: 'Productivity',
};

const QUALITY_BADGE_COLORS: Record<string, string> = {
  '144p': '#ef4444',
  '360p': '#f97316',
  '480p': '#f59e0b',
  '720p': '#f59e0b',
  '1080p': '#3b82f6',
  '1440p': '#22c55e',
  '2160p': '#22c55e',
  'HD Voice': '#22c55e',
  'SD Voice': '#f59e0b',
  'Excellent': '#22c55e',
  'Good': '#3b82f6',
  'Fair': '#f59e0b',
  'Poor': '#ef4444',
};

/* ------------------------------------------------------------------ */
/*  Queue item used in state                                           */
/* ------------------------------------------------------------------ */

interface QueueItem {
  app_id: string;
  name: string;
  icon: string;
  color: string;
  priority: Priority;
  // set after apply
  guaranteed_kbps?: number;
  ceil_kbps?: number;
  estimated_quality?: string;
}

/* ------------------------------------------------------------------ */
/*  QualityCascade -- animated countdown that cycles through quality   */
/*  tiers from high → target so the audience literally watches the     */
/*  drop happen over ~1.8 seconds.                                     */
/* ------------------------------------------------------------------ */

const STREAMING_TIERS_HIGH_TO_LOW = [
  '4K', '1440p', '1080p', '720p', '480p', '360p', '240p', '144p',
];
const VIDEO_CONF_TIERS_HIGH_TO_LOW = [
  'Excellent', 'HD (1080p)', 'Medium (720p)', 'Low (360p)', 'Audio Only',
];

function pickTierChain(target: string): string[] {
  const t = (target || '').toLowerCase();
  // streaming label match
  for (let i = 0; i < STREAMING_TIERS_HIGH_TO_LOW.length; i++) {
    if (t.includes(STREAMING_TIERS_HIGH_TO_LOW[i].toLowerCase())) {
      return STREAMING_TIERS_HIGH_TO_LOW.slice(0, i + 1);
    }
  }
  // video-conf label match
  for (let i = 0; i < VIDEO_CONF_TIERS_HIGH_TO_LOW.length; i++) {
    if (t.includes(VIDEO_CONF_TIERS_HIGH_TO_LOW[i].toLowerCase())) {
      return VIDEO_CONF_TIERS_HIGH_TO_LOW.slice(0, i + 1);
    }
  }
  return [target];
}

interface QualityCascadeProps {
  target: string;
  color: string;
  run: boolean;            // start the cascade
  stepMs?: number;
  onDone?: () => void;
}

const QualityCascade: React.FC<QualityCascadeProps> = ({ target, color, run, stepMs = 220, onDone }) => {
  const [idx, setIdx] = useState(0);
  const chain = pickTierChain(target);

  useEffect(() => {
    if (!run) { setIdx(chain.length - 1); return; }
    setIdx(0);
    let i = 0;
    const tick = () => {
      i += 1;
      if (i < chain.length) {
        setIdx(i);
        t = setTimeout(tick, stepMs);
      } else {
        onDone && onDone();
      }
    };
    let t = setTimeout(tick, stepMs);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, target]);

  const label = chain[Math.min(idx, chain.length - 1)];
  const isFinal = idx >= chain.length - 1;
  return (
    <span style={{
      padding: '4px 12px', borderRadius: 20,
      fontSize: 12, fontWeight: 700,
      backgroundColor: `${color}15`, color: color,
      border: `1.5px solid ${color}50`,
      display: 'inline-block',
      transition: 'all 120ms ease-out',
      transform: isFinal ? 'none' : 'scale(1.05)',
      boxShadow: isFinal ? 'none' : `0 0 10px ${color}80`,
    }}>
      {label}
    </span>
  );
};


/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

const AppPriorityManager: React.FC = () => {
  const { user } = useAuth();

  // Catalog data
  const [catalog, setCatalog] = useState<AppSignature[]>([]);
  const [activeApps, setActiveApps] = useState<ActiveApp[]>([]);

  // Priority queue
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [appliedResults, setAppliedResults] = useState<AppliedApp[]>([]);
  const [applying, setApplying] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  // Track which apps are mid-drop animation so the UI stays flashy
  const [dropSet, setDropSet] = useState<Set<string>>(new Set());

  // Drag state
  const dragItem = useRef<number | null>(null);
  const dragOverItem = useRef<number | null>(null);

  /* ---- data fetching ---- */

  const fetchCatalog = useCallback(async () => {
    try {
      const data = await api.get<{ apps: AppSignature[] }>('/apps/signatures');
      setCatalog(data.apps || []);
    } catch {
      // silent — catalog may not be available yet
    }
  }, []);

  const fetchActive = useCallback(async () => {
    try {
      const data = await api.get<{ apps: ActiveApp[] }>('/apps/active');
      setActiveApps(data.apps || []);
    } catch {
      // silent
    }
  }, []);

  const fetchPriorities = useCallback(async () => {
    try {
      const data = await api.get<{ priorities: any }>('/apps/priorities');
      // Backend may return dict {app_id: priority} or array [{app_id, priority}]
      let entries: PriorityEntry[] = [];
      if (Array.isArray(data.priorities)) {
        entries = data.priorities;
      } else if (data.priorities && typeof data.priorities === 'object') {
        entries = Object.entries(data.priorities).map(([app_id, priority]) => ({
          app_id,
          priority: priority as Priority,
        }));
      }
      if (entries.length && catalog.length) {
        const items: QueueItem[] = entries.map((p) => {
          const sig = catalog.find((c) => c.app_id === p.app_id);
          return {
            app_id: p.app_id,
            name: sig?.name || p.app_id,
            icon: sig?.icon || '',
            color: sig?.color || '#64748b',
            priority: p.priority,
          };
        });
        setQueue(items);
      }
    } catch {
      // silent
    }
  }, [catalog]);

  useEffect(() => {
    fetchCatalog();
    fetchActive();
  }, [fetchCatalog, fetchActive]);

  useEffect(() => {
    if (catalog.length) fetchPriorities();
  }, [catalog, fetchPriorities]);

  /* ---- actions ---- */

  const addToQueue = (app: AppSignature) => {
    if (queue.find((q) => q.app_id === app.app_id)) return;
    setQueue((prev) => [
      ...prev,
      {
        app_id: app.app_id,
        name: app.name,
        icon: app.icon,
        color: app.color,
        priority: 'NORMAL' as Priority,
      },
    ]);
  };

  const removeFromQueue = (app_id: string) => {
    setQueue((prev) => prev.filter((q) => q.app_id !== app_id));
    setAppliedResults((prev) => prev.filter((a) => a.app_id !== app_id));
  };

  const setPriority = (app_id: string, priority: Priority) => {
    setQueue((prev) => prev.map((q) => (q.app_id === app_id ? { ...q, priority } : q)));
  };

  const handleApply = async () => {
    setApplying(true);
    setMessage(null);
    try {
      const payload = queue.map((q) => ({ app_id: q.app_id, priority: q.priority }));
      const data = await api.post<{ apps: any[] }>('/apps/priorities', { priorities: payload });
      // Normalize estimated_quality — backend may return string or {label: string}
      const normalized = (data.apps || []).map((a: any) => ({
        ...a,
        estimated_quality: typeof a.estimated_quality === 'object' && a.estimated_quality
          ? a.estimated_quality.label || 'Unknown'
          : a.estimated_quality || 'Unknown',
      }));
      setAppliedResults(normalized);
      // Flag every LOW/BLOCKED app so its card runs the cascade + flash
      const droppedApps = normalized.filter(
        (a: any) => a.priority === 'LOW' || a.priority === 'BLOCKED'
      );
      const dropping = new Set<string>(droppedApps.map((a: any) => a.app_id));
      setDropSet(dropping);
      // Clear drop flags after 2.5s so the flash/shake CSS stops
      setTimeout(() => setDropSet(new Set()), 2500);
      // Actionable call-to-action banner so the audience sees the effect
      if (droppedApps.length) {
        const names = droppedApps.map((a: any) => a.name).join(', ');
        setMessage({
          text:
            `Priorities applied. Now switch to your ${names} browser tab and press F5 — ` +
            `the stream will stall within ~15 seconds as PathWise resets active connections.`,
          type: 'success',
        });
      } else {
        setMessage({ text: 'Priorities applied successfully', type: 'success' });
      }
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to apply priorities', type: 'error' });
    } finally {
      setApplying(false);
    }
  };

  const handleReset = async () => {
    setMessage(null);
    try {
      await api.post<{ success: boolean }>('/apps/reset', {});
      setQueue([]);
      setAppliedResults([]);
      setMessage({ text: 'Priorities reset to defaults', type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Failed to reset', type: 'error' });
    }
  };

  /* ---- drag handlers ---- */

  const handleDragStart = (index: number) => {
    dragItem.current = index;
  };

  const handleDragEnter = (index: number) => {
    dragOverItem.current = index;
  };

  const handleDragEnd = () => {
    if (dragItem.current === null || dragOverItem.current === null) return;
    const copy = [...queue];
    const draggedItem = copy[dragItem.current];
    copy.splice(dragItem.current, 1);
    copy.splice(dragOverItem.current, 0, draggedItem);
    dragItem.current = null;
    dragOverItem.current = null;
    setQueue(copy);
  };

  /* ---- derived ---- */

  const groupedCatalog: Record<string, AppSignature[]> = {};
  CATEGORIES.forEach((cat) => { groupedCatalog[cat] = []; });
  catalog.forEach((a) => {
    const mapped = CATEGORY_MAP[a.category] || a.category;
    if (!groupedCatalog[mapped]) groupedCatalog[mapped] = [];
    groupedCatalog[mapped].push(a);
  });

  const hasZoomAndYouTube =
    queue.some((q) => q.name.toLowerCase().includes('zoom')) &&
    queue.some((q) => q.name.toLowerCase().includes('youtube'));

  const maxKbps = Math.max(...appliedResults.map((a) => a.ceil_kbps || 0), 1);

  /* ---- helpers ---- */

  const getQualityColor = (quality: string) => {
    for (const [key, color] of Object.entries(QUALITY_BADGE_COLORS)) {
      if (quality.toLowerCase().includes(key.toLowerCase())) return color;
    }
    return '#64748b';
  };

  /* ---- render ---- */

  return (
    <UserLayout>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#0f172a', margin: 0 }}>
          App Priority Switch
        </h1>
        <p style={{ fontSize: 13, color: '#64748b', marginTop: 4 }}>
          Assign bandwidth priorities to your applications. Drag to reorder, set priority levels,
          and see live quality impact.
        </p>
      </div>

      {message && (
        <div
          style={{
            padding: '10px 16px',
            borderRadius: 8,
            marginBottom: 16,
            fontSize: 13,
            fontWeight: 500,
            backgroundColor: message.type === 'success' ? '#f0fdf4' : '#fef2f2',
            color: message.type === 'success' ? '#16a34a' : '#dc2626',
            border: `1px solid ${message.type === 'success' ? '#bbf7d0' : '#fecaca'}`,
          }}
        >
          {message.text}
        </div>
      )}

      <SelectiveIPDegrade
        apps={catalog.map(c => ({
          app_id: c.app_id, name: c.name, icon: c.icon, color: c.color,
        }))}
      />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, alignItems: 'start' }}>
        {/* ============ COLUMN 1: App Catalog ============ */}
        <div
          style={{
            backgroundColor: '#ffffff',
            borderRadius: 12,
            border: '1px solid #e2e8f0',
            padding: 20,
            maxHeight: 'calc(100vh - 200px)',
            overflowY: 'auto',
          }}
        >
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0f172a', marginTop: 0, marginBottom: 16 }}>
            Available Apps
          </h2>

          {Object.entries(groupedCatalog).map(([category, apps]) =>
            apps.length === 0 ? null : (
              <div key={category} style={{ marginBottom: 16 }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: '#64748b',
                    marginBottom: 8,
                  }}
                >
                  {category}
                </div>
                {apps.map((app) => {
                  const inQueue = queue.some((q) => q.app_id === app.app_id);
                  return (
                    <button
                      key={app.app_id}
                      onClick={() => addToQueue(app)}
                      disabled={inQueue}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        width: '100%',
                        padding: '8px 12px',
                        marginBottom: 4,
                        borderRadius: 8,
                        border: '1px solid #e2e8f0',
                        backgroundColor: inQueue ? '#f1f5f9' : '#ffffff',
                        cursor: inQueue ? 'default' : 'pointer',
                        opacity: inQueue ? 0.5 : 1,
                        textAlign: 'left',
                        fontSize: 13,
                        fontWeight: 500,
                        color: '#0f172a',
                        transition: 'all 0.15s',
                      }}
                    >
                      <span
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: 6,
                          backgroundColor: app.color || '#3b82f6',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 14,
                          flexShrink: 0,
                        }}
                      >
                        {app.icon || app.name.charAt(0)}
                      </span>
                      <span style={{ flex: 1 }}>{app.name}</span>
                      {inQueue && (
                        <span style={{ fontSize: 10, color: '#94a3b8', fontWeight: 400 }}>Added</span>
                      )}
                    </button>
                  );
                })}
              </div>
            ),
          )}

          {catalog.length === 0 && (
            <p style={{ fontSize: 13, color: '#94a3b8', textAlign: 'center', padding: '20px 0' }}>
              No app signatures loaded. The backend may not be running.
            </p>
          )}
        </div>

        {/* ============ COLUMN 2: Priority Queue ============ */}
        <div
          style={{
            backgroundColor: '#ffffff',
            borderRadius: 12,
            border: '1px solid #e2e8f0',
            padding: 20,
            maxHeight: 'calc(100vh - 200px)',
            overflowY: 'auto',
          }}
        >
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0f172a', marginTop: 0, marginBottom: 16 }}>
            Priority Queue
          </h2>

          {hasZoomAndYouTube && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 8,
                marginBottom: 14,
                fontSize: 12,
                fontWeight: 500,
                backgroundColor: '#eff6ff',
                color: '#1d4ed8',
                border: '1px solid #bfdbfe',
              }}
            >
              Zoom + YouTube detected &mdash; Zoom will get bandwidth priority to maintain call quality.
            </div>
          )}

          {queue.length === 0 ? (
            <p style={{ fontSize: 13, color: '#94a3b8', textAlign: 'center', padding: '30px 0' }}>
              Click apps from the catalog to add them here.
            </p>
          ) : (
            <div>
              {queue.map((item, index) => (
                <div
                  key={item.app_id}
                  draggable
                  onDragStart={() => handleDragStart(index)}
                  onDragEnter={() => handleDragEnter(index)}
                  onDragEnd={handleDragEnd}
                  onDragOver={(e) => e.preventDefault()}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '10px 12px',
                    marginBottom: 6,
                    borderRadius: 8,
                    border: `1px solid ${PRIORITY_COLORS[item.priority]}33`,
                    backgroundColor: `${PRIORITY_COLORS[item.priority]}08`,
                    cursor: 'grab',
                    transition: 'all 0.15s',
                  }}
                >
                  {/* Drag handle */}
                  <span style={{ color: '#94a3b8', fontSize: 16, cursor: 'grab', userSelect: 'none' }}>
                    &#x2630;
                  </span>

                  {/* Rank */}
                  <span
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: '50%',
                      backgroundColor: '#f1f5f9',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 11,
                      fontWeight: 700,
                      color: '#475569',
                      flexShrink: 0,
                    }}
                  >
                    {index + 1}
                  </span>

                  {/* Icon */}
                  <span
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 6,
                      backgroundColor: item.color || '#3b82f6',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 14,
                      flexShrink: 0,
                    }}
                  >
                    {item.icon || item.name.charAt(0)}
                  </span>

                  {/* Name */}
                  <span style={{ flex: 1, fontSize: 13, fontWeight: 500, color: '#0f172a' }}>
                    {item.name}
                  </span>

                  {/* Priority dropdown */}
                  <select
                    value={item.priority}
                    onChange={(e) => setPriority(item.app_id, e.target.value as Priority)}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 6,
                      border: `1px solid ${PRIORITY_COLORS[item.priority]}`,
                      backgroundColor: `${PRIORITY_COLORS[item.priority]}18`,
                      color: PRIORITY_COLORS[item.priority],
                      fontSize: 11,
                      fontWeight: 600,
                      cursor: 'pointer',
                      outline: 'none',
                    }}
                  >
                    {PRIORITY_OPTIONS.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>

                  {/* Remove */}
                  <button
                    onClick={() => removeFromQueue(item.app_id)}
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: 6,
                      border: 'none',
                      backgroundColor: 'transparent',
                      color: '#94a3b8',
                      cursor: 'pointer',
                      fontSize: 16,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                    title="Remove"
                  >
                    &times;
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Buttons */}
          <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
            <button
              onClick={handleApply}
              disabled={queue.length === 0 || applying}
              style={{
                flex: 1,
                padding: '10px 16px',
                borderRadius: 8,
                border: 'none',
                backgroundColor: queue.length === 0 || applying ? '#94a3b8' : '#2563eb',
                color: '#ffffff',
                fontSize: 13,
                fontWeight: 600,
                cursor: queue.length === 0 || applying ? 'default' : 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {applying ? 'Applying...' : 'Apply Priorities'}
            </button>
            <button
              onClick={handleReset}
              disabled={applying}
              style={{
                padding: '10px 16px',
                borderRadius: 8,
                border: '1px solid #e2e8f0',
                backgroundColor: '#ffffff',
                color: '#475569',
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              Reset
            </button>
          </div>
        </div>

        {/* ============ COLUMN 3: Live Quality Impact (Enhanced) ============ */}
        <div
          style={{
            backgroundColor: '#ffffff',
            borderRadius: 12,
            border: '1px solid #e2e8f0',
            padding: 20,
            maxHeight: 'calc(100vh - 200px)',
            overflowY: 'auto',
          }}
        >
          {/* Header with enforcement status */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0f172a', margin: 0 }}>
              Live Quality Impact
            </h2>
            {appliedResults.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%', backgroundColor: '#16a34a',
                  animation: 'pulse 2s infinite',
                }} />
                <span style={{ fontSize: 11, color: '#16a34a', fontWeight: 600 }}>ENFORCING</span>
              </div>
            )}
          </div>

          {appliedResults.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px 0' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>📊</div>
              <p style={{ fontSize: 13, color: '#94a3b8', margin: 0 }}>
                Apply priorities to see estimated quality impact.
              </p>
              <p style={{ fontSize: 11, color: '#cbd5e1', marginTop: 4 }}>
                Add apps from the catalog, set their priority levels, then click Apply.
              </p>
            </div>
          ) : (
            <div>
              {/* Zoom vs YouTube banner */}
              {hasZoomAndYouTube && (() => {
                const zm = appliedResults.find(a => a.app_id === 'zoom');
                const yt = appliedResults.find(a => a.app_id === 'youtube');
                return (
                  <div style={{
                    background: 'linear-gradient(135deg, #0f2d0f 0%, #052e16 100%)',
                    border: '1px solid #16a34a', borderRadius: 10,
                    padding: 14, marginBottom: 14,
                  }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#86efac', marginBottom: 8 }}>
                      ACTIVE ENFORCEMENT: Zoom prioritized over YouTube
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 8, alignItems: 'center' }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 24 }}>🎥</div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9' }}>Zoom</div>
                        <div style={{
                          fontSize: 20, fontWeight: 700, color: '#4ade80',
                          fontFamily: 'monospace',
                        }}>
                          {zm ? `${(zm.ceil_kbps / 1000).toFixed(0)} Mbps` : '—'}
                        </div>
                        <div style={{
                          display: 'inline-block', marginTop: 4,
                          padding: '2px 8px', borderRadius: 6,
                          background: '#16a34a20', border: '1px solid #16a34a',
                          color: '#86efac', fontSize: 12, fontWeight: 600,
                        }}>
                          {zm?.estimated_quality || 'Excellent'}
                        </div>
                      </div>
                      <div style={{ color: '#475569', fontSize: 20 }}>⚡</div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: 24 }}>▶️</div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9' }}>YouTube</div>
                        <div style={{
                          fontSize: 20, fontWeight: 700, color: '#f87171',
                          fontFamily: 'monospace',
                        }}>
                          {yt ? (yt.ceil_kbps >= 1000 ? `${(yt.ceil_kbps / 1000).toFixed(1)} Mbps` : `${yt.ceil_kbps} Kbps`) : '—'}
                        </div>
                        <div style={{
                          display: 'inline-block', marginTop: 4,
                          padding: '2px 8px', borderRadius: 6,
                          background: '#ef444420', border: '1px solid #ef4444',
                          color: '#fca5a5', fontSize: 12, fontWeight: 600,
                        }}>
                          {yt?.estimated_quality || '144p'}
                        </div>
                      </div>
                    </div>
                    {yt && (
                      <div style={{ marginTop: 10, fontSize: 11, color: '#6ee7b7', textAlign: 'center' }}>
                        YouTube forced from 4K → {yt.estimated_quality} by DASH adaptive engine
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Per-app quality cards */}
              {appliedResults.map((app) => {
                const totalKbps = 100000; // 100 Mbps link
                const barPct = Math.min(100, (app.ceil_kbps / totalKbps) * 100);
                const qualityColor = getQualityColor(app.estimated_quality || '');
                const queueItem = queue.find((q) => q.app_id === app.app_id);
                const priorityColor = queueItem ? PRIORITY_COLORS[queueItem.priority] : '#64748b';
                const sig = catalog.find(c => c.app_id === app.app_id);

                const dropping = dropSet.has(app.app_id);

                return (
                  <div
                    key={app.app_id}
                    className={dropping ? 'pw-quality-drop' : ''}
                    style={{
                      padding: 14, marginBottom: 10, borderRadius: 10,
                      border: `1px solid ${dropping ? '#ef4444' : priorityColor + '30'}`,
                      background: `linear-gradient(135deg, ${priorityColor}08, #ffffff)`,
                    }}
                  >
                    {/* App header */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{
                          width: 28, height: 28, borderRadius: 6,
                          backgroundColor: sig?.color || '#3b82f6',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 14,
                        }}>
                          {sig?.icon || app.name.charAt(0)}
                        </span>
                        <div>
                          <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>{app.name}</span>
                          <div style={{ fontSize: 10, fontWeight: 600, color: priorityColor, textTransform: 'uppercase' }}>
                            {app.priority}
                            {dropping && (
                              <span style={{ marginLeft: 8, color: '#ef4444', fontWeight: 700 }}>
                                ▼ quality dropping…
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <QualityCascade
                        target={app.estimated_quality || 'N/A'}
                        color={qualityColor}
                        run={dropping}
                      />
                    </div>

                    {/* Animated bandwidth bar */}
                    <div style={{ marginBottom: 6 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#94a3b8', marginBottom: 3 }}>
                        <span>Bandwidth allocation</span>
                        <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#0f172a' }}>
                          {app.ceil_kbps >= 1000 ? `${(app.ceil_kbps / 1000).toFixed(1)} Mbps` : `${app.ceil_kbps} Kbps`}
                        </span>
                      </div>
                      <div style={{ height: 10, borderRadius: 5, backgroundColor: '#f1f5f9', overflow: 'hidden', position: 'relative' }}>
                        <div style={{
                          height: '100%', borderRadius: 5,
                          width: `${barPct}%`,
                          background: `linear-gradient(90deg, ${priorityColor}, ${priorityColor}aa)`,
                          transition: 'width 450ms cubic-bezier(0.4, 0, 0.2, 1)',
                          boxShadow: `0 0 8px ${priorityColor}40`,
                        }} />
                      </div>
                    </div>

                    {/* Detail row */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#94a3b8' }}>
                      <span>Floor: {(app.guaranteed_kbps / 1000).toFixed(1)} Mbps</span>
                      <span>Ceiling: {(app.ceil_kbps / 1000).toFixed(1)} Mbps</span>
                      <span>{barPct.toFixed(1)}% of link</span>
                    </div>
                  </div>
                );
              })}

              {/* Quality cascade explanation */}
              {appliedResults.some(a => a.priority === 'LOW' || a.priority === 'BLOCKED') && (
                <div style={{
                  marginTop: 14, padding: 12, borderRadius: 8,
                  background: '#0f172a', border: '1px solid #334155',
                }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#e2e8f0', marginBottom: 6 }}>
                    How Quality Drop Works
                  </div>
                  <div style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.5 }}>
                    YouTube uses <strong style={{ color: '#e2e8f0' }}>DASH adaptive streaming</strong>. It constantly probes available bandwidth.
                    When PathWise enforces a ceiling (via Linux tc or Windows QoS), the DASH engine detects the throughput drop
                    within <strong style={{ color: '#f59e0b' }}>2–3 seconds</strong> and automatically switches to a lower quality tier.
                  </div>
                  <div style={{ display: 'flex', gap: 4, marginTop: 8, flexWrap: 'wrap' }}>
                    {['4K', '1440p', '1080p', '720p', '480p', '360p', '144p'].map((q, i) => (
                      <span key={q} style={{
                        fontSize: 10, padding: '2px 6px', borderRadius: 4,
                        background: i <= 1 ? '#16a34a20' : i <= 3 ? '#3b82f620' : '#ef444420',
                        color: i <= 1 ? '#4ade80' : i <= 3 ? '#60a5fa' : '#f87171',
                        border: `1px solid ${i <= 1 ? '#16a34a40' : i <= 3 ? '#3b82f640' : '#ef444440'}`,
                      }}>{q}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* CSS animations */}
        <style>{`
          @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.3); }
          }
          @keyframes pwFlashRed {
            0%   { background-color: rgba(239,68,68,0.18); box-shadow: 0 0 0 2px rgba(239,68,68,0.5); }
            50%  { background-color: rgba(239,68,68,0.05); box-shadow: 0 0 0 4px rgba(239,68,68,0.25); }
            100% { background-color: transparent; box-shadow: 0 0 0 0 rgba(239,68,68,0); }
          }
          @keyframes pwShake {
            0%,100% { transform: translateX(0); }
            20%     { transform: translateX(-4px); }
            40%     { transform: translateX(4px); }
            60%     { transform: translateX(-3px); }
            80%     { transform: translateX(3px); }
          }
          .pw-quality-drop {
            animation: pwFlashRed 2.2s ease-out 1, pwShake 0.45s ease-in-out 2;
          }
        `}</style>
      </div>
    </UserLayout>
  );
};

export default AppPriorityManager;
