import React, { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  ScrollText, ShieldCheck, Filter, ChevronLeft, ChevronRight,
  ArrowRightLeft, Shield, Terminal, LogIn, AlertTriangle, Server,
} from "lucide-react";
import { api } from "../services/api";

interface AuditEntry {
  id: string;
  event_time: number;
  event_type: string;
  actor: string;
  link_id: string | null;
  health_score: number | null;
  confidence: number | null;
  validation_result: string | null;
  details: string | null;
  checksum: string;
}

const EVENT_ICONS: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  STEERING:      { icon: ArrowRightLeft, color: "text-blue-400",    bg: "bg-blue-500/15" },
  VALIDATION:    { icon: Shield,         color: "text-emerald-400", bg: "bg-emerald-500/15" },
  POLICY_CHANGE: { icon: Terminal,       color: "text-violet-400",  bg: "bg-violet-500/15" },
  AUTH:          { icon: LogIn,          color: "text-cyan-400",    bg: "bg-cyan-500/15" },
  ALERT:         { icon: AlertTriangle,  color: "text-amber-400",   bg: "bg-amber-500/15" },
  SYSTEM:        { icon: Server,         color: "text-gray-400",    bg: "bg-gray-500/15" },
};

const AuditLog: React.FC = () => {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const perPage = 25;

  const fetchLog = useCallback(async () => {
    try {
      const params: Record<string, any> = { page, per_page: perPage };
      if (eventTypeFilter) params.event_type = eventTypeFilter;
      if (actorFilter) params.actor = actorFilter;
      const res = await api.getAuditLog(params);
      setEntries(res.entries || []);
      setTotal(res.total || 0);
    } catch { /* ignore */ }
  }, [page, eventTypeFilter, actorFilter]);

  useEffect(() => { fetchLog(); }, [fetchLog]);
  useEffect(() => {
    const interval = setInterval(fetchLog, 5000);
    return () => clearInterval(interval);
  }, [fetchLog]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <ScrollText className="w-6 h-6 text-pw-accent-light" />
            Audit Log
          </h1>
          <p className="text-pw-muted text-sm mt-1">
            Tamper-evident record of all system events with SHA-256 chain verification
          </p>
        </div>
        <div className="text-xs text-pw-muted">
          {total} total entries
        </div>
      </div>

      {/* Filters */}
      <div className="glass-card p-4 flex items-center gap-4">
        <Filter className="w-4 h-4 text-pw-muted" />
        <select
          value={eventTypeFilter}
          onChange={(e) => { setEventTypeFilter(e.target.value); setPage(1); }}
          className="bg-pw-bg border border-pw-border rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-pw-accent/50"
        >
          <option value="">All Event Types</option>
          <option value="STEERING">Steering</option>
          <option value="VALIDATION">Validation</option>
          <option value="POLICY_CHANGE">Policy Change</option>
          <option value="AUTH">Authentication</option>
          <option value="ALERT">Alert</option>
          <option value="SYSTEM">System</option>
        </select>
        <input
          value={actorFilter}
          onChange={(e) => { setActorFilter(e.target.value); setPage(1); }}
          placeholder="Filter by actor..."
          className="bg-pw-bg border border-pw-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-pw-muted/40 focus:outline-none focus:border-pw-accent/50 w-48"
        />
      </div>

      {/* Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-pw-border">
                {["Time", "Type", "Actor", "Link", "Details", "Checksum"].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-xs uppercase tracking-wider text-pw-muted font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, i) => {
                const cfg = EVENT_ICONS[entry.event_type] || EVENT_ICONS.SYSTEM;
                const Icon = cfg.icon;
                return (
                  <motion.tr
                    key={entry.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.02 }}
                    className="border-b border-pw-border/50 hover:bg-pw-surface/30"
                  >
                    <td className="px-4 py-3 text-pw-muted whitespace-nowrap">
                      {new Date(entry.event_time * 1000).toLocaleTimeString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className={`w-6 h-6 rounded-md ${cfg.bg} flex items-center justify-center`}>
                          <Icon className={`w-3 h-3 ${cfg.color}`} />
                        </div>
                        <span className={`text-xs font-semibold ${cfg.color}`}>
                          {entry.event_type}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-pw-text font-mono text-xs">
                      {entry.actor}
                    </td>
                    <td className="px-4 py-3 text-pw-muted text-xs">
                      {entry.link_id || "-"}
                    </td>
                    <td className="px-4 py-3 text-pw-text text-xs max-w-xs truncate">
                      {entry.details || "-"}
                    </td>
                    <td className="px-4 py-3 text-pw-muted/60 font-mono text-[10px]">
                      {entry.checksum.slice(0, 12)}...
                    </td>
                  </motion.tr>
                );
              })}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-pw-muted">
                    No audit entries found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-pw-border">
          <span className="text-xs text-pw-muted">
            Page {page} of {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 rounded-lg text-pw-muted hover:text-white hover:bg-pw-surface transition-colors disabled:opacity-30"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1.5 rounded-lg text-pw-muted hover:text-white hover:bg-pw-surface transition-colors disabled:opacity-30"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuditLog;
