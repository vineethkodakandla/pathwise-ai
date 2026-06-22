import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FlaskConical,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  ChevronRight,
  Layers,
  Shield,
  Route,
  Gauge,
  Network,
  RotateCcw,
  History,
  Loader2,
  Rocket,
  ArrowRight,
} from "lucide-react";
import { api } from "../services/api";
import { useNetworkStore } from "../store/networkStore";
import type { SandboxReport, SandboxCheck } from "../types";
import { useNavigate } from "react-router-dom";

const LINKS = [
  { id: "fiber-primary", label: "Fiber Primary", color: "#6366f1" },
  { id: "broadband-secondary", label: "Broadband Secondary", color: "#22d3ee" },
  { id: "satellite-backup", label: "Satellite Backup", color: "#fbbf24" },
  { id: "5g-mobile", label: "5G Mobile", color: "#34d399" },
];

const TRAFFIC_CLASSES = [
  { id: "voip", label: "VoIP", desc: "Real-time voice — low latency required" },
  { id: "video", label: "Video", desc: "Streaming/conferencing — moderate latency" },
  { id: "critical", label: "Critical", desc: "Business-critical data — high reliability" },
  { id: "bulk", label: "Bulk", desc: "File transfers — latency tolerant" },
];

const SandboxViewer: React.FC = () => {
  const [sourceLink, setSourceLink] = useState("fiber-primary");
  const [targetLink, setTargetLink] = useState("broadband-secondary");
  const [selectedClasses, setSelectedClasses] = useState<string[]>(["voip", "video"]);
  const [loading, setLoading] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [deployed, setDeployed] = useState(false);
  const [deployedRuleId, setDeployedRuleId] = useState<string | null>(null);
  const [activeReport, setActiveReport] = useState<SandboxReport | null>(null);
  const [history, setHistory] = useState<SandboxReport[]>([]);
  const [animatingCheck, setAnimatingCheck] = useState(-1);

  const scoreboard = useNetworkStore((s) => s.scoreboard);
  const navigate = useNavigate();

  useEffect(() => {
    api.sandboxHistory(10).then((data) => setHistory(data.reports || [])).catch(() => {});
  }, []);

  const toggleClass = (id: string) => {
    setSelectedClasses((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  };

  const handleDeploy = useCallback(async () => {
    if (!activeReport || activeReport.result !== "pass") return;
    setDeploying(true);
    try {
      const res = await api.applyRoutingRule(
        activeReport.id,
        activeReport.source_link,
        activeReport.target_link,
        activeReport.traffic_classes,
      );
      if (res.rule_id) {
        setDeployed(true);
        setDeployedRuleId(res.rule_id);
      }
    } catch (err) {
      console.error("Deploy failed:", err);
    } finally {
      setDeploying(false);
    }
  }, [activeReport]);

  const runValidation = useCallback(async () => {
    if (sourceLink === targetLink || selectedClasses.length === 0) return;
    setLoading(true);
    setActiveReport(null);
    setAnimatingCheck(-1);
    setDeployed(false);
    setDeployedRuleId(null);

    try {
      const report: SandboxReport = await api.sandboxValidate(
        sourceLink, targetLink, selectedClasses
      );
      setActiveReport(report);

      // Animate checks one by one
      for (let i = 0; i < report.checks.length; i++) {
        await new Promise((r) => setTimeout(r, 300));
        setAnimatingCheck(i);
      }

      // Refresh history
      const hist = await api.sandboxHistory(10);
      setHistory(hist.reports || []);
    } catch (err) {
      console.error("Sandbox validation failed:", err);
    } finally {
      setLoading(false);
    }
  }, [sourceLink, targetLink, selectedClasses]);

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <FlaskConical className="w-6 h-6 text-pw-accent-light" />
          Digital Twin Sandbox
        </h1>
        <p className="text-pw-muted text-sm mt-1">
          Test routing changes in a virtual network before applying to production.
          Validates loop-free routing, policy compliance, reachability, and performance impact.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left: Configuration Panel */}
        <div className="col-span-1 space-y-4">
          {/* Source Link */}
          <div className="glass-card p-5">
            <label className="text-xs uppercase tracking-wider text-pw-muted font-medium mb-3 block">
              Source Link (move traffic from)
            </label>
            <div className="space-y-2">
              {LINKS.map((link) => {
                const health = scoreboard[link.id];
                return (
                  <button
                    key={link.id}
                    onClick={() => setSourceLink(link.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                      sourceLink === link.id
                        ? "bg-pw-accent/15 border border-pw-accent/30 text-white"
                        : "bg-pw-bg/50 border border-transparent text-pw-muted hover:text-pw-text hover:bg-pw-bg"
                    }`}
                  >
                    <div
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: link.color }}
                    />
                    <span className="flex-1 text-left">{link.label}</span>
                    {health && (
                      <span className={`text-[10px] font-semibold ${
                        health.health_score >= 70 ? "text-pw-emerald" :
                        health.health_score >= 40 ? "text-pw-amber" : "text-pw-rose"
                      }`}>
                        {health.health_score.toFixed(0)}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Target Link */}
          <div className="glass-card p-5">
            <label className="text-xs uppercase tracking-wider text-pw-muted font-medium mb-3 block">
              Target Link (move traffic to)
            </label>
            <div className="space-y-2">
              {LINKS.filter((l) => l.id !== sourceLink).map((link) => {
                const health = scoreboard[link.id];
                return (
                  <button
                    key={link.id}
                    onClick={() => setTargetLink(link.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                      targetLink === link.id
                        ? "bg-pw-cyan/15 border border-pw-cyan/30 text-white"
                        : "bg-pw-bg/50 border border-transparent text-pw-muted hover:text-pw-text hover:bg-pw-bg"
                    }`}
                  >
                    <div
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: link.color }}
                    />
                    <span className="flex-1 text-left">{link.label}</span>
                    {health && (
                      <span className={`text-[10px] font-semibold ${
                        health.health_score >= 70 ? "text-pw-emerald" :
                        health.health_score >= 40 ? "text-pw-amber" : "text-pw-rose"
                      }`}>
                        {health.health_score.toFixed(0)}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Traffic Classes */}
          <div className="glass-card p-5">
            <label className="text-xs uppercase tracking-wider text-pw-muted font-medium mb-3 block">
              Traffic Classes
            </label>
            <div className="space-y-2">
              {TRAFFIC_CLASSES.map((tc) => (
                <button
                  key={tc.id}
                  onClick={() => toggleClass(tc.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                    selectedClasses.includes(tc.id)
                      ? "bg-pw-emerald/15 border border-pw-emerald/30 text-white"
                      : "bg-pw-bg/50 border border-transparent text-pw-muted hover:text-pw-text hover:bg-pw-bg"
                  }`}
                >
                  <div className={`w-4 h-4 rounded border-2 flex items-center justify-center text-[10px] ${
                    selectedClasses.includes(tc.id)
                      ? "border-pw-emerald bg-pw-emerald text-white"
                      : "border-pw-border"
                  }`}>
                    {selectedClasses.includes(tc.id) && "✓"}
                  </div>
                  <div className="text-left">
                    <span className="block">{tc.label}</span>
                    <span className="text-[10px] text-pw-muted">{tc.desc}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Run Button */}
          <button
            onClick={runValidation}
            disabled={loading || sourceLink === targetLink || selectedClasses.length === 0}
            className={`w-full flex items-center justify-center gap-2 py-3.5 rounded-xl text-sm font-semibold transition-all ${
              loading || sourceLink === targetLink || selectedClasses.length === 0
                ? "bg-pw-border text-pw-muted cursor-not-allowed"
                : "bg-gradient-to-r from-pw-accent to-pw-cyan text-white hover:shadow-lg hover:shadow-pw-accent/20"
            }`}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Validating…
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Run Sandbox Validation
              </>
            )}
          </button>
        </div>

        {/* Right: Results Panel */}
        <div className="col-span-2 space-y-4">
          {/* Active Report */}
          <AnimatePresence mode="wait">
            {activeReport ? (
              <motion.div
                key={activeReport.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-4"
              >
                {/* Result Banner */}
                <div
                  className={`glass-card p-6 border-l-4 ${
                    activeReport.result === "pass"
                      ? "border-l-pw-emerald"
                      : activeReport.result.startsWith("fail")
                      ? "border-l-pw-rose"
                      : "border-l-pw-amber"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <ResultIcon result={activeReport.result} size="lg" />
                      <div>
                        <h2 className="text-lg font-bold text-white">
                          {activeReport.result === "pass"
                            ? "Validation Passed"
                            : `Validation Failed — ${activeReport.result.replace("fail_", "").replace("_", " ").toUpperCase()}`}
                        </h2>
                        <p className="text-sm text-pw-muted mt-0.5">
                          {activeReport.source_link}
                          <ChevronRight className="w-3 h-3 inline mx-1" />
                          {activeReport.target_link}
                          <span className="ml-2 text-pw-muted/60">
                            [{activeReport.traffic_classes.join(", ")}]
                          </span>
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-2xl font-bold text-pw-text">
                        {activeReport.execution_time_ms.toFixed(0)}
                        <span className="text-sm text-pw-muted ml-0.5">ms</span>
                      </p>
                      <p className="text-[10px] uppercase tracking-wider text-pw-muted">
                        Total Time
                      </p>
                    </div>
                  </div>

                  {/* Summary badges */}
                  <div className="flex items-center gap-3 mt-4">
                    <StatusBadge label="Loop-Free" ok={activeReport.loop_free} />
                    <StatusBadge label="Policy OK" ok={activeReport.policy_compliant} />
                    <StatusBadge label="Reachable" ok={activeReport.reachability_verified} />
                    <StatusBadge label="Performance" ok={activeReport.performance_acceptable} />
                  </div>

                  {/* Deploy to Production */}
                  {activeReport.result === "pass" && (
                    <div className="mt-5 pt-5 border-t border-pw-border">
                      <AnimatePresence mode="wait">
                        {deployed ? (
                          <motion.div
                            key="deployed"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="flex items-center justify-between"
                          >
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-xl bg-pw-emerald/20 flex items-center justify-center">
                                <Rocket className="w-5 h-5 text-pw-emerald" />
                              </div>
                              <div>
                                <p className="text-sm font-semibold text-pw-emerald">
                                  Deployed to Production
                                </p>
                                <p className="text-xs text-pw-muted">
                                  Rule {deployedRuleId} is now active — traffic is being rerouted in real-time
                                </p>
                              </div>
                            </div>
                            <button
                              onClick={() => navigate("/simulation")}
                              className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-pw-accent/15 text-pw-accent-light border border-pw-accent/30 hover:bg-pw-accent/25 transition-colors"
                            >
                              View in Simulation
                              <ArrowRight className="w-3 h-3" />
                            </button>
                          </motion.div>
                        ) : (
                          <motion.div
                            key="deploy-btn"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="flex items-center justify-between"
                          >
                            <div>
                              <p className="text-sm font-medium text-white">
                                Ready to deploy
                              </p>
                              <p className="text-xs text-pw-muted">
                                Apply this validated routing change to the live network simulation
                              </p>
                            </div>
                            <button
                              onClick={handleDeploy}
                              disabled={deploying}
                              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-pw-emerald to-emerald-500 text-white hover:shadow-lg hover:shadow-pw-emerald/20 transition-all disabled:opacity-50"
                            >
                              {deploying ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Rocket className="w-4 h-4" />
                              )}
                              {deploying ? "Deploying…" : "Apply to Production"}
                            </button>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}
                </div>

                {/* Validation Pipeline */}
                <div className="glass-card p-6">
                  <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                    <Layers className="w-4 h-4 text-pw-accent-light" />
                    Validation Pipeline
                  </h3>
                  <div className="space-y-3">
                    {activeReport.checks.map((check, i) => (
                      <AnimatePresence key={check.name}>
                        {i <= animatingCheck && (
                          <motion.div
                            initial={{ opacity: 0, x: -20, height: 0 }}
                            animate={{ opacity: 1, x: 0, height: "auto" }}
                            transition={{ duration: 0.3, delay: 0.05 }}
                          >
                            <CheckRow check={check} index={i} />
                          </motion.div>
                        )}
                      </AnimatePresence>
                    ))}
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="glass-card p-12 flex flex-col items-center justify-center text-center"
              >
                <div className="w-16 h-16 rounded-2xl bg-pw-accent/10 flex items-center justify-center mb-4">
                  <FlaskConical className="w-8 h-8 text-pw-accent-light" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  No Validation Running
                </h3>
                <p className="text-sm text-pw-muted max-w-sm">
                  Select a source link, target link, and traffic classes, then
                  click "Run Sandbox Validation" to test a routing change in the
                  virtual network.
                </p>
                <div className="flex items-center gap-6 mt-6 text-xs text-pw-muted/60">
                  <span className="flex items-center gap-1.5">
                    <Shield className="w-3 h-3" /> Loop Detection
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Route className="w-3 h-3" /> Policy Check
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Network className="w-3 h-3" /> Reachability
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Gauge className="w-3 h-3" /> Performance
                  </span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* History */}
          {history.length > 0 && (
            <div className="glass-card p-6">
              <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                <History className="w-4 h-4 text-pw-accent-light" />
                Validation History
              </h3>
              <div className="space-y-2">
                {history.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => {
                      setActiveReport(r);
                      setAnimatingCheck(r.checks.length - 1);
                    }}
                    className="w-full flex items-center gap-3 py-2.5 px-4 rounded-xl bg-pw-bg/50 hover:bg-pw-bg transition-colors text-left"
                  >
                    <ResultIcon result={r.result} size="sm" />
                    <span className="text-xs text-pw-text font-medium">
                      {r.source_link}
                    </span>
                    <ChevronRight className="w-3 h-3 text-pw-muted" />
                    <span className="text-xs text-pw-text font-medium">
                      {r.target_link}
                    </span>
                    <span className="flex-1 text-[10px] text-pw-muted truncate">
                      [{r.traffic_classes.join(", ")}]
                    </span>
                    <span className="text-[10px] text-pw-muted">
                      {r.execution_time_ms.toFixed(0)}ms
                    </span>
                    <span className={`text-[10px] font-semibold uppercase ${
                      r.result === "pass" ? "text-pw-emerald" : "text-pw-rose"
                    }`}>
                      {r.result === "pass" ? "PASS" : "FAIL"}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};


/* ── Check Row ──────────────────────────────────────────── */

const CHECK_ICONS: Record<string, React.ElementType> = {
  topology_snapshot: Layers,
  loop_detection: RotateCcw,
  policy_compliance: Shield,
  reachability_test: Route,
  performance_impact: Gauge,
};

function CheckRow({ check, index }: { check: SandboxCheck; index: number }) {
  const Icon = CHECK_ICONS[check.name] || Layers;
  const statusColor =
    check.status === "pass"
      ? "text-pw-emerald"
      : check.status === "fail"
      ? "text-pw-rose"
      : "text-pw-amber";
  const statusBg =
    check.status === "pass"
      ? "bg-pw-emerald/10"
      : check.status === "fail"
      ? "bg-pw-rose/10"
      : "bg-pw-amber/10";

  return (
    <div className="flex items-start gap-4 py-3 px-4 rounded-xl bg-pw-bg/40">
      {/* Step number & icon */}
      <div className="flex-shrink-0 flex items-center gap-3">
        <span className="text-[10px] font-bold text-pw-muted w-4 text-right">
          {index + 1}
        </span>
        <div className={`w-8 h-8 rounded-lg ${statusBg} flex items-center justify-center`}>
          <Icon className={`w-4 h-4 ${statusColor}`} />
        </div>
      </div>

      {/* Details */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-white capitalize">
            {check.name.replace(/_/g, " ")}
          </span>
          <span className={`text-[10px] font-bold uppercase ${statusColor}`}>
            {check.status}
          </span>
        </div>
        <p className="text-[11px] text-pw-muted mt-0.5 leading-relaxed">
          {check.detail}
        </p>
      </div>

      {/* Duration */}
      <div className="flex-shrink-0 text-right">
        <span className="text-xs font-medium text-pw-muted">
          {check.duration_ms.toFixed(0)}ms
        </span>
      </div>
    </div>
  );
}


/* ── Result Icon ────────────────────────────────────────── */

function ResultIcon({ result, size = "sm" }: { result: string; size?: "sm" | "lg" }) {
  const cls = size === "lg" ? "w-10 h-10" : "w-5 h-5";
  if (result === "pass") {
    return <CheckCircle2 className={`${cls} text-pw-emerald`} />;
  }
  if (result.startsWith("fail")) {
    return <XCircle className={`${cls} text-pw-rose`} />;
  }
  return <AlertTriangle className={`${cls} text-pw-amber`} />;
}


/* ── Status Badge ───────────────────────────────────────── */

function StatusBadge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-semibold ${
        ok
          ? "bg-pw-emerald/10 text-pw-emerald"
          : "bg-pw-rose/10 text-pw-rose"
      }`}
    >
      {ok ? (
        <CheckCircle2 className="w-3 h-3" />
      ) : (
        <XCircle className="w-3 h-3" />
      )}
      {label}
    </span>
  );
}


export default SandboxViewer;
