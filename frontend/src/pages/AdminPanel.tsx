import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BrainCircuit,
  Power,
  Activity,
  TrendingUp,
  ShieldAlert,
  Zap,
  Clock,
  ChevronRight,
} from "lucide-react";
import { useNetworkStore } from "../store/networkStore";
import { api } from "../services/api";

const AdminPanel: React.FC = () => {
  const lstmEnabled = useNetworkStore((s) => s.lstmEnabled);
  const comparison = useNetworkStore((s) => s.comparison);
  const steeringEvents = useNetworkStore((s) => s.steeringEvents);
  const wsConnected = useNetworkStore((s) => s.wsConnected);
  const [toggling, setToggling] = useState(false);

  const handleToggle = useCallback(async () => {
    setToggling(true);
    try {
      await api.toggleLSTM(!lstmEnabled);
    } catch (err) {
      console.error("Toggle failed:", err);
    } finally {
      setTimeout(() => setToggling(false), 500);
    }
  }, [lstmEnabled]);

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Admin Control Panel</h1>
        <p className="text-pw-muted text-sm mt-1">
          Manage LSTM predictive engine and monitor system performance
        </p>
      </div>

      {/* LSTM Toggle — Hero Section */}
      <motion.div
        layout
        className={`glass-card p-8 relative overflow-hidden transition-all duration-700 ${
          lstmEnabled ? "glow-border" : ""
        }`}
      >
        {/* Animated background gradient */}
        <div
          className={`absolute inset-0 transition-opacity duration-1000 ${
            lstmEnabled ? "opacity-100" : "opacity-0"
          }`}
          style={{
            background:
              "radial-gradient(ellipse at 30% 50%, rgba(99,102,241,0.08) 0%, transparent 70%)",
          }}
        />

        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-6">
            {/* Icon with glow */}
            <motion.div
              animate={{
                boxShadow: lstmEnabled
                  ? "0 0 40px rgba(99,102,241,0.4)"
                  : "0 0 0px rgba(99,102,241,0)",
              }}
              transition={{ duration: 0.7 }}
              className={`w-20 h-20 rounded-2xl flex items-center justify-center transition-colors duration-700 ${
                lstmEnabled
                  ? "bg-gradient-to-br from-pw-accent to-pw-cyan"
                  : "bg-pw-border"
              }`}
            >
              <BrainCircuit className="w-10 h-10 text-white" />
            </motion.div>

            <div>
              <h2 className="text-xl font-bold text-white">
                LSTM Prediction Engine
              </h2>
              <p className="text-pw-muted text-sm mt-1 max-w-md">
                When enabled, the LSTM neural network predicts network
                degradation 30 seconds ahead, enabling proactive traffic
                steering before brownouts occur.
              </p>
              <div className="flex items-center gap-4 mt-3">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={lstmEnabled ? "on" : "off"}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    className={`flex items-center gap-2 text-sm font-medium ${
                      lstmEnabled ? "text-pw-emerald" : "text-pw-muted"
                    }`}
                  >
                    <div
                      className={`w-2 h-2 rounded-full ${
                        lstmEnabled
                          ? "bg-pw-emerald animate-pulse"
                          : "bg-pw-muted"
                      }`}
                    />
                    {lstmEnabled
                      ? "Active — Proactive Steering Enabled"
                      : "Inactive — Reactive Mode Only"}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </div>

          {/* Toggle Switch */}
          <button
            onClick={handleToggle}
            disabled={toggling || !wsConnected}
            className="relative flex-shrink-0 group"
          >
            <div
              className={`w-24 h-12 rounded-full transition-all duration-500 flex items-center px-1 cursor-pointer ${
                lstmEnabled
                  ? "bg-gradient-to-r from-pw-accent to-pw-cyan shadow-lg shadow-pw-accent/30"
                  : "bg-pw-border"
              } ${!wsConnected ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <motion.div
                layout
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
                className={`w-10 h-10 rounded-full bg-white shadow-lg flex items-center justify-center ${
                  lstmEnabled ? "ml-auto" : ""
                }`}
              >
                <Power
                  className={`w-5 h-5 transition-colors duration-300 ${
                    lstmEnabled ? "text-pw-accent" : "text-gray-400"
                  }`}
                />
              </motion.div>
            </div>
          </button>
        </div>
      </motion.div>

      {/* Comparison Metrics */}
      <div className="grid grid-cols-2 gap-6">
        {/* LSTM ON metrics */}
        <motion.div
          layout
          className={`glass-card p-6 transition-all duration-500 ${
            lstmEnabled
              ? "border-pw-emerald/30 shadow-lg shadow-pw-emerald/5"
              : ""
          }`}
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-8 h-8 rounded-lg bg-pw-emerald/20 flex items-center justify-center">
              <Zap className="w-4 h-4 text-pw-emerald" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">
                With LSTM (AI-Optimized)
              </h3>
              <p className="text-xs text-pw-muted">
                Proactive prediction & steering
              </p>
            </div>
            {lstmEnabled && (
              <span className="ml-auto text-xs px-2 py-1 rounded-full bg-pw-emerald/20 text-pw-emerald font-medium">
                ACTIVE
              </span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-4">
            <MetricCard
              label="Avg Latency"
              value={comparison.lstm_on.avg_latency}
              unit="ms"
              color="emerald"
            />
            <MetricCard
              label="Avg Jitter"
              value={comparison.lstm_on.avg_jitter}
              unit="ms"
              color="emerald"
            />
            <MetricCard
              label="Packet Loss"
              value={comparison.lstm_on.avg_packet_loss}
              unit="%"
              color="emerald"
              decimals={3}
            />
          </div>
          <div className="mt-4 pt-4 border-t border-pw-border flex items-center justify-between text-xs text-pw-muted">
            <span>
              Proactive steerings:{" "}
              <span className="text-pw-emerald font-semibold">
                {comparison.lstm_on.proactive_steerings || 0}
              </span>
            </span>
            <span>
              Brownouts avoided:{" "}
              <span className="text-pw-emerald font-semibold">
                {comparison.lstm_on.brownouts_avoided || 0}
              </span>
            </span>
          </div>
        </motion.div>

        {/* LSTM OFF metrics */}
        <motion.div
          layout
          className={`glass-card p-6 transition-all duration-500 ${
            !lstmEnabled
              ? "border-pw-rose/30 shadow-lg shadow-pw-rose/5"
              : ""
          }`}
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-8 h-8 rounded-lg bg-pw-rose/20 flex items-center justify-center">
              <ShieldAlert className="w-4 h-4 text-pw-rose" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">
                Without LSTM (Reactive)
              </h3>
              <p className="text-xs text-pw-muted">
                Threshold-based failover only
              </p>
            </div>
            {!lstmEnabled && (
              <span className="ml-auto text-xs px-2 py-1 rounded-full bg-pw-rose/20 text-pw-rose font-medium">
                ACTIVE
              </span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-4">
            <MetricCard
              label="Avg Latency"
              value={comparison.lstm_off.avg_latency}
              unit="ms"
              color="rose"
            />
            <MetricCard
              label="Avg Jitter"
              value={comparison.lstm_off.avg_jitter}
              unit="ms"
              color="rose"
            />
            <MetricCard
              label="Packet Loss"
              value={comparison.lstm_off.avg_packet_loss}
              unit="%"
              color="rose"
              decimals={3}
            />
          </div>
          <div className="mt-4 pt-4 border-t border-pw-border flex items-center justify-between text-xs text-pw-muted">
            <span>
              Reactive steerings:{" "}
              <span className="text-pw-rose font-semibold">
                {comparison.lstm_off.reactive_steerings || 0}
              </span>
            </span>
            <span>
              Brownouts hit:{" "}
              <span className="text-pw-rose font-semibold">
                {comparison.lstm_off.brownouts_hit || 0}
              </span>
            </span>
          </div>
        </motion.div>
      </div>

      {/* Steering Event Log */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-3 mb-4">
          <Clock className="w-4 h-4 text-pw-accent-light" />
          <h3 className="text-sm font-semibold text-white">
            Recent Steering Decisions
          </h3>
        </div>
        <div className="space-y-2">
          {steeringEvents.length === 0 ? (
            <p className="text-pw-muted text-sm py-4 text-center">
              No steering events yet — waiting for network activity…
            </p>
          ) : (
            steeringEvents.map((evt) => (
              <motion.div
                key={evt.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex items-center gap-4 py-3 px-4 rounded-xl bg-pw-bg/50"
              >
                <div
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wide ${
                    evt.action === "PREEMPTIVE_SHIFT"
                      ? "bg-pw-emerald/20 text-pw-emerald"
                      : "bg-pw-rose/20 text-pw-rose"
                  }`}
                >
                  {evt.action.replace("_", " ")}
                </div>
                <div className="flex items-center gap-2 text-sm text-pw-muted">
                  <span className="text-pw-text">{evt.source_link}</span>
                  <ChevronRight className="w-3 h-3" />
                  <span className="text-pw-text">{evt.target_link}</span>
                </div>
                <p className="flex-1 text-xs text-pw-muted truncate">
                  {evt.reason}
                </p>
                <span className="text-xs text-pw-muted/60">
                  {evt.confidence > 0
                    ? `${(evt.confidence * 100).toFixed(0)}% conf`
                    : ""}
                </span>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

function MetricCard({
  label,
  value,
  unit,
  color,
  decimals = 1,
}: {
  label: string;
  value: number;
  unit: string;
  color: "emerald" | "rose" | "cyan" | "accent";
  decimals?: number;
}) {
  const colorMap = {
    emerald: "text-pw-emerald",
    rose: "text-pw-rose",
    cyan: "text-pw-cyan",
    accent: "text-pw-accent-light",
  };

  return (
    <div className="text-center">
      <p className="metric-label mb-1">{label}</p>
      <p className={`text-2xl font-bold ${colorMap[color]}`}>
        {value.toFixed(decimals)}
        <span className="text-sm font-normal text-pw-muted ml-0.5">
          {unit}
        </span>
      </p>
    </div>
  );
}

export default AdminPanel;
