import React, { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Terminal,
  Send,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Pause,
  Play,
  Trash2,
  Code2,
  ChevronDown,
  ChevronRight,
  Zap,
  Shield,
  Lightbulb,
  Clock,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { api } from "../services/api";
import type { IBNIntent, IBNParseResult } from "../types";

const EXAMPLE_INTENTS = [
  // App-level traffic shaping (real OS QoS)
  "Prioritize Zoom over YouTube",
  "Prioritize Teams over Netflix",
  "Throttle YouTube to 500 Kbps",
  "Throttle Netflix to 1000 Kbps",
  "Block Twitch",
  "Give Zoom maximum bandwidth",
  "Limit Spotify to 200 Kbps",
  "Remove YouTube restriction",
  // Link-level policies
  "Prioritize VoIP traffic on fiber",
  "Ensure video latency stays below 100ms",
  "Redirect critical traffic from satellite to fiber",
  "Keep packet loss below 0.5% for critical applications",
];

const STATUS_CONFIG: Record<string, { color: string; bg: string; border: string; icon: React.ElementType; label: string }> = {
  compliant:     { color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30", icon: CheckCircle2,  label: "Compliant" },
  active:        { color: "text-blue-400",    bg: "bg-blue-500/10",    border: "border-blue-500/30",    icon: RefreshCw,     label: "Monitoring" },
  violated:      { color: "text-red-400",     bg: "bg-red-500/10",     border: "border-red-500/30",     icon: XCircle,       label: "Violated" },
  auto_steering: { color: "text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/30",   icon: Zap,           label: "Auto-Steering" },
  paused:        { color: "text-gray-400",    bg: "bg-gray-500/10",    border: "border-gray-500/30",    icon: Pause,         label: "Paused" },
};

const IBNConsole: React.FC = () => {
  const [inputText, setInputText] = useState("");
  const [preview, setPreview] = useState<IBNParseResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [intents, setIntents] = useState<IBNIntent[]>([]);
  const [expandedYang, setExpandedYang] = useState<string | null>(null);
  const [showExamples, setShowExamples] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const fetchIntents = useCallback(async () => {
    try {
      const res = await api.ibnListIntents();
      setIntents(res.intents || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchIntents();
    const interval = setInterval(fetchIntents, 2000);
    return () => clearInterval(interval);
  }, [fetchIntents]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (inputText.trim().length < 5) {
      setPreview(null);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setPreviewLoading(true);
      try {
        const res = await api.ibnParseIntent(inputText);
        setPreview(res);
      } catch { setPreview(null); }
      finally { setPreviewLoading(false); }
    }, 400);
  }, [inputText]);

  const handleSubmit = useCallback(async () => {
    if (!inputText.trim() || submitting) return;
    setSubmitting(true);
    try {
      await api.ibnCreateIntent(inputText.trim());
      setInputText("");
      setPreview(null);
      await fetchIntents();
    } catch (err) {
      console.error("Failed to create intent:", err);
    } finally {
      setSubmitting(false);
    }
  }, [inputText, submitting, fetchIntents]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleAction = useCallback(async (id: string, action: "delete" | "pause" | "resume") => {
    try {
      if (action === "delete") await api.ibnDeleteIntent(id);
      else if (action === "pause") await api.ibnPauseIntent(id);
      else await api.ibnResumeIntent(id);
      await fetchIntents();
    } catch { /* ignore */ }
  }, [fetchIntents]);

  const activeCount = intents.filter((i) => i.status !== "paused").length;
  const violatedCount = intents.filter((i) => i.status === "violated" || i.status === "auto_steering").length;
  const compliantCount = intents.filter((i) => i.status === "compliant").length;

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center">
            <Terminal className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Intent-Based Network Management</h1>
            <p className="text-xs text-pw-muted">
              Describe your network goals in plain English — the system translates them into YANG/NETCONF policies and enforces them automatically
            </p>
          </div>
        </div>
      </motion.div>

      {/* KPI Row */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Active Policies", value: activeCount, color: "text-blue-400", icon: Shield },
          { label: "Compliant", value: compliantCount, color: "text-emerald-400", icon: CheckCircle2 },
          { label: "Violations", value: violatedCount, color: "text-red-400", icon: AlertTriangle },
        ].map(({ label, value, color, icon: Icon }) => (
          <div key={label} className="glass-card p-4 flex items-center gap-3">
            <div className={`w-9 h-9 rounded-lg ${color === "text-blue-400" ? "bg-blue-500/15" : color === "text-emerald-400" ? "bg-emerald-500/15" : "bg-red-500/15"} flex items-center justify-center`}>
              <Icon className={`w-4 h-4 ${color}`} />
            </div>
            <div>
              <p className={`text-2xl font-bold ${color}`}>{value}</p>
              <p className="text-xs text-pw-muted">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Intent Input Console */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-fuchsia-400" />
            New Intent
          </h3>
          <button
            onClick={() => setShowExamples(!showExamples)}
            className="flex items-center gap-1 text-xs text-pw-accent-light hover:text-white transition-colors"
          >
            <Lightbulb className="w-3 h-3" />
            {showExamples ? "Hide" : "Show"} Examples
          </button>
        </div>

        <AnimatePresence>
          {showExamples && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden mb-3"
            >
              <div className="flex flex-wrap gap-2 p-3 rounded-xl bg-pw-surface/60 border border-pw-border">
                {EXAMPLE_INTENTS.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => { setInputText(ex); inputRef.current?.focus(); }}
                    className="px-3 py-1.5 rounded-lg text-xs bg-pw-accent/10 text-pw-accent-light border border-pw-accent/20 hover:bg-pw-accent/20 transition-colors"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="relative">
          <textarea
            ref={inputRef}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder='Type a network intent... e.g. "Ensure VoIP latency stays below 50ms on fiber"'
            rows={2}
            className="w-full bg-pw-bg/80 border border-pw-border rounded-xl px-4 py-3 pr-14 text-sm text-white placeholder:text-pw-muted/50 focus:outline-none focus:border-pw-accent/50 resize-none font-mono"
          />
          <button
            onClick={handleSubmit}
            disabled={!inputText.trim() || submitting}
            className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-lg bg-gradient-to-r from-violet-500 to-fuchsia-600 flex items-center justify-center text-white hover:shadow-lg hover:shadow-fuchsia-500/20 transition-all disabled:opacity-30"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        {/* Live Parse Preview */}
        <AnimatePresence>
          {preview && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mt-3 p-3 rounded-xl bg-pw-surface/60 border border-pw-border"
            >
              <p className="text-[10px] text-pw-muted uppercase tracking-wider mb-2">Live Parse Preview</p>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="px-2 py-0.5 rounded-md bg-violet-500/15 text-violet-300 border border-violet-500/20">
                  {preview.action}
                </span>
                {preview.traffic_classes.map((tc) => (
                  <span key={tc} className="px-2 py-0.5 rounded-md bg-blue-500/15 text-blue-300 border border-blue-500/20">
                    {tc}
                  </span>
                ))}
                {preview.metric && (
                  <span className="px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-300 border border-amber-500/20">
                    {preview.metric} {preview.threshold != null ? `≤ ${preview.threshold}${preview.threshold_unit || ""}` : ""}
                  </span>
                )}
                {preview.preferred_link && (
                  <span className="px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-300 border border-emerald-500/20">
                    on {preview.preferred_link}
                  </span>
                )}
                {preview.avoid_link && (
                  <span className="px-2 py-0.5 rounded-md bg-red-500/15 text-red-300 border border-red-500/20">
                    avoid {preview.avoid_link}
                  </span>
                )}
                {preview.source_link && preview.target_link && (
                  <span className="px-2 py-0.5 rounded-md bg-cyan-500/15 text-cyan-300 border border-cyan-500/20">
                    {preview.source_link} → {preview.target_link}
                  </span>
                )}
                {preview.high_app && (
                  <span className="px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-300 border border-emerald-500/20">
                    boost {preview.high_app}
                  </span>
                )}
                {preview.low_app && (
                  <span className="px-2 py-0.5 rounded-md bg-red-500/15 text-red-300 border border-red-500/20">
                    throttle {preview.low_app}{preview.throttle_kbps ? ` @ ${preview.throttle_kbps} Kbps` : ""}
                  </span>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Active Intents */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Shield className="w-4 h-4 text-pw-accent-light" />
          Active Policies ({intents.length})
        </h3>

        {intents.length === 0 && (
          <div className="glass-card p-8 text-center">
            <Terminal className="w-10 h-10 text-pw-muted/30 mx-auto mb-3" />
            <p className="text-sm text-pw-muted">No intents defined yet</p>
            <p className="text-xs text-pw-muted/60 mt-1">Type a network goal above to create your first policy</p>
          </div>
        )}

        <AnimatePresence>
          {intents.map((intent) => {
            const cfg = STATUS_CONFIG[intent.status] || STATUS_CONFIG.active;
            const StatusIcon = cfg.icon;
            const isExpanded = expandedYang === intent.id;

            return (
              <motion.div
                key={intent.id}
                layout
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className={`glass-card p-4 border-l-4 ${cfg.border}`}
              >
                {/* Top Row */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <div className={`w-7 h-7 rounded-lg ${cfg.bg} flex items-center justify-center`}>
                        <StatusIcon className={`w-3.5 h-3.5 ${cfg.color}`} />
                      </div>
                      <p className="text-sm font-medium text-white truncate font-mono">
                        "{intent.raw_text}"
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-1.5 ml-9">
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold ${cfg.bg} ${cfg.color} border ${cfg.border}`}>
                        {cfg.label}
                      </span>
                      <span className="px-2 py-0.5 rounded-md text-[10px] bg-violet-500/10 text-violet-300 border border-violet-500/20">
                        {intent.action}
                      </span>
                      {intent.traffic_classes.map((tc) => (
                        <span key={tc} className="px-2 py-0.5 rounded-md text-[10px] bg-blue-500/10 text-blue-300 border border-blue-500/20">
                          {tc}
                        </span>
                      ))}
                      {intent.threshold != null && (
                        <span className="px-2 py-0.5 rounded-md text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/20">
                          {intent.metric} ≤ {intent.threshold}{intent.threshold_unit || ""}
                        </span>
                      )}
                      {intent.high_app && (
                        <span className="px-2 py-0.5 rounded-md text-[10px] bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                          boost {intent.high_app}
                        </span>
                      )}
                      {intent.low_app && (
                        <span className="px-2 py-0.5 rounded-md text-[10px] bg-red-500/10 text-red-300 border border-red-500/20">
                          throttle {intent.low_app}{intent.throttle_kbps ? ` @ ${intent.throttle_kbps} Kbps` : ""}
                        </span>
                      )}
                    </div>

                    {/* Violation Detail */}
                    {intent.last_violation && intent.status !== "compliant" && (
                      <p className="text-xs text-red-400/80 mt-2 ml-9">
                        ⚠ {intent.last_violation}
                      </p>
                    )}
                  </div>

                  {/* Stats & Actions */}
                  <div className="flex flex-col items-end gap-2 flex-shrink-0">
                    <div className="flex items-center gap-3 text-[10px] text-pw-muted">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {intent.age_seconds < 60
                          ? `${Math.round(intent.age_seconds)}s`
                          : intent.age_seconds < 3600
                          ? `${Math.round(intent.age_seconds / 60)}m`
                          : `${Math.round(intent.age_seconds / 3600)}h`}
                      </span>
                      {intent.violation_count > 0 && (
                        <span className="text-red-400">
                          {intent.violation_count} violations
                        </span>
                      )}
                      {intent.auto_steer_count > 0 && (
                        <span className="text-amber-400">
                          {intent.auto_steer_count} auto-steers
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setExpandedYang(isExpanded ? null : intent.id)}
                        className="p-1.5 rounded-md text-pw-muted hover:text-violet-400 hover:bg-violet-500/10 transition-colors"
                        title="View YANG Config"
                      >
                        <Code2 className="w-3.5 h-3.5" />
                      </button>
                      {intent.status === "paused" ? (
                        <button
                          onClick={() => handleAction(intent.id, "resume")}
                          className="p-1.5 rounded-md text-pw-muted hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                          title="Resume"
                        >
                          <Play className="w-3.5 h-3.5" />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleAction(intent.id, "pause")}
                          className="p-1.5 rounded-md text-pw-muted hover:text-amber-400 hover:bg-amber-500/10 transition-colors"
                          title="Pause"
                        >
                          <Pause className="w-3.5 h-3.5" />
                        </button>
                      )}
                      <button
                        onClick={() => handleAction(intent.id, "delete")}
                        className="p-1.5 rounded-md text-pw-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* YANG/NETCONF Config (expandable) */}
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="mt-3 ml-9 p-3 rounded-xl bg-[#0a0e1a] border border-pw-border font-mono text-[11px] text-emerald-300/80 whitespace-pre overflow-x-auto">
                        {intent.yang_config}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default IBNConsole;
