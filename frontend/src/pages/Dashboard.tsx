import React from "react";
import { motion } from "framer-motion";
import {
  Activity,
  Heart,
  Gauge,
  Zap,
  TrendingUp,
  TrendingDown,
  BrainCircuit,
  Network,
  ArrowRight,
} from "lucide-react";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
} from "recharts";
import { useNetworkStore } from "../store/networkStore";
import { Link } from "react-router-dom";

const Dashboard: React.FC = () => {
  const scoreboard = useNetworkStore((s) => s.scoreboard);
  const lstmEnabled = useNetworkStore((s) => s.lstmEnabled);
  const comparison = useNetworkStore((s) => s.comparison);
  const steeringEvents = useNetworkStore((s) => s.steeringEvents);
  const wsConnected = useNetworkStore((s) => s.wsConnected);

  const links = Object.entries(scoreboard);

  const avgHealth =
    links.length > 0
      ? links.reduce((sum, [, h]) => sum + h.health_score, 0) / links.length
      : 0;

  const avgLatency =
    links.length > 0
      ? links.reduce((sum, [, h]) => sum + h.latency_current, 0) / links.length
      : 0;

  const totalBrownouts = links.filter(([, h]) => h.brownout_active).length;

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Network Overview
          </h1>
          <p className="text-pw-muted text-sm mt-1">
            Real-time SD-WAN health monitoring and AI-powered insights
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm ${
              wsConnected
                ? "bg-pw-emerald/10 text-pw-emerald border border-pw-emerald/20"
                : "bg-pw-rose/10 text-pw-rose border border-pw-rose/20"
            }`}
          >
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                wsConnected ? "bg-pw-emerald animate-pulse" : "bg-pw-rose"
              }`}
            />
            {wsConnected ? "Live" : "Disconnected"}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <KPICard
          icon={Heart}
          label="Avg Health Score"
          value={avgHealth.toFixed(0)}
          suffix="/100"
          color={avgHealth >= 70 ? "emerald" : avgHealth >= 40 ? "amber" : "rose"}
          trend={avgHealth >= 70 ? "up" : avgHealth >= 40 ? "stable" : "down"}
        />
        <KPICard
          icon={Gauge}
          label="Avg Latency"
          value={avgLatency.toFixed(1)}
          suffix="ms"
          color={avgLatency < 30 ? "emerald" : avgLatency < 60 ? "amber" : "rose"}
          trend={avgLatency < 30 ? "up" : "down"}
        />
        <KPICard
          icon={BrainCircuit}
          label="LSTM Engine"
          value={lstmEnabled ? "Active" : "Off"}
          suffix=""
          color={lstmEnabled ? "accent" : "muted"}
          trend={lstmEnabled ? "up" : "stable"}
        />
        <KPICard
          icon={Zap}
          label="Active Brownouts"
          value={String(totalBrownouts)}
          suffix={`/ ${links.length}`}
          color={totalBrownouts === 0 ? "emerald" : "rose"}
          trend={totalBrownouts === 0 ? "up" : "down"}
        />
      </div>

      {/* Health Scoreboard */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Activity className="w-4 h-4 text-pw-accent-light" />
            Link Health Scoreboard
          </h2>
          <Link
            to="/simulation"
            className="text-xs text-pw-accent-light hover:text-pw-accent flex items-center gap-1 transition-colors"
          >
            View Simulation <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {links.map(([linkId, health]) => (
            <HealthCard key={linkId} linkId={linkId} health={health} />
          ))}
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-2 gap-6">
        {/* Latency Forecast */}
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-white mb-4">
            Latency Forecast (30s ahead)
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart>
                {links.map(([linkId, health]) => {
                  const data = (health.latency_forecast || []).map(
                    (v, i) => ({ t: i, [linkId]: v })
                  );
                  const color =
                    linkId === "fiber-primary"
                      ? "#6366f1"
                      : linkId === "broadband-secondary"
                      ? "#22d3ee"
                      : linkId === "satellite-backup"
                      ? "#fbbf24"
                      : "#34d399";
                  return (
                    <Line
                      key={linkId}
                      data={data}
                      dataKey={linkId}
                      stroke={color}
                      strokeWidth={1.5}
                      dot={false}
                      type="monotone"
                    />
                  );
                })}
                <XAxis dataKey="t" hide />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fill: "#94a3b8", fontSize: 10 }}
                  width={40}
                />
                <Tooltip
                  contentStyle={{
                    background: "#1a2035",
                    border: "1px solid #1f2a40",
                    borderRadius: "8px",
                    fontSize: 11,
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center gap-4 mt-3 justify-center">
            {["fiber-primary", "broadband-secondary", "satellite-backup", "5g-mobile"].map((id) => {
              const color =
                id === "fiber-primary"
                  ? "#6366f1"
                  : id === "broadband-secondary"
                  ? "#22d3ee"
                  : id === "satellite-backup"
                  ? "#fbbf24"
                  : "#34d399";
              return (
                <span key={id} className="flex items-center gap-1.5 text-[10px] text-pw-muted">
                  <div className="w-2 h-2 rounded-full" style={{ background: color }} />
                  {id.split("-")[0]}
                </span>
              );
            })}
          </div>
        </div>

        {/* Comparison Summary */}
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-white mb-4">
            AI Impact Summary
          </h3>
          <div className="space-y-5">
            <ImpactRow
              label="Latency"
              aiVal={comparison.lstm_on.avg_latency}
              noAiVal={comparison.lstm_off.avg_latency}
              unit="ms"
            />
            <ImpactRow
              label="Jitter"
              aiVal={comparison.lstm_on.avg_jitter}
              noAiVal={comparison.lstm_off.avg_jitter}
              unit="ms"
            />
            <ImpactRow
              label="Packet Loss"
              aiVal={comparison.lstm_on.avg_packet_loss}
              noAiVal={comparison.lstm_off.avg_packet_loss}
              unit="%"
              decimals={3}
            />
          </div>
          <div className="mt-6 pt-4 border-t border-pw-border">
            <Link
              to="/admin"
              className="flex items-center gap-2 text-xs text-pw-accent-light hover:text-pw-accent transition-colors"
            >
              <BrainCircuit className="w-3.5 h-3.5" />
              Go to Admin Panel to toggle LSTM
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ── KPI Card ───────────────────────────────────────────── */

function KPICard({
  icon: Icon,
  label,
  value,
  suffix,
  color,
  trend,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  suffix: string;
  color: string;
  trend: "up" | "down" | "stable";
}) {
  const colorMap: Record<string, string> = {
    emerald: "text-pw-emerald",
    rose: "text-pw-rose",
    amber: "text-pw-amber",
    accent: "text-pw-accent-light",
    cyan: "text-pw-cyan",
    muted: "text-pw-muted",
  };
  const bgMap: Record<string, string> = {
    emerald: "bg-pw-emerald/10",
    rose: "bg-pw-rose/10",
    amber: "bg-pw-amber/10",
    accent: "bg-pw-accent/10",
    cyan: "bg-pw-cyan/10",
    muted: "bg-white/5",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5"
    >
      <div className="flex items-center justify-between mb-3">
        <div
          className={`w-9 h-9 rounded-xl ${bgMap[color]} flex items-center justify-center`}
        >
          <Icon className={`w-4 h-4 ${colorMap[color]}`} />
        </div>
        {trend === "up" ? (
          <TrendingUp className="w-4 h-4 text-pw-emerald" />
        ) : trend === "down" ? (
          <TrendingDown className="w-4 h-4 text-pw-rose" />
        ) : (
          <Activity className="w-4 h-4 text-pw-muted" />
        )}
      </div>
      <p className={`text-2xl font-bold ${colorMap[color]}`}>
        {value}
        <span className="text-sm font-normal text-pw-muted ml-1">
          {suffix}
        </span>
      </p>
      <p className="text-[10px] uppercase tracking-wider text-pw-muted mt-1">
        {label}
      </p>
    </motion.div>
  );
}

/* ── Health Card ────────────────────────────────────────── */

function HealthCard({
  linkId,
  health,
}: {
  linkId: string;
  health: {
    health_score: number;
    confidence: number;
    latency_current: number;
    jitter_current: number;
    packet_loss_current: number;
    trend: string;
    brownout_active: boolean;
    latency_forecast?: number[];
    reasoning?: string;
  };
}) {
  const score = health.health_score;
  const scoreColor =
    score >= 70 ? "text-pw-emerald" : score >= 40 ? "text-pw-amber" : "text-pw-rose";
  const ringColor =
    score >= 70 ? "#34d399" : score >= 40 ? "#fbbf24" : "#f43f5e";

  const sparkData = (health.latency_forecast || []).slice(0, 10).map((v, i) => ({
    t: i,
    v,
  }));

  return (
    <div
      className={`bg-pw-bg/60 rounded-xl p-4 border transition-all duration-300 ${
        health.brownout_active
          ? "border-pw-rose/40 shadow-lg shadow-pw-rose/5"
          : "border-pw-border/50 hover:border-pw-border"
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-xs font-semibold text-white">
            {linkId.replace("-", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </p>
          <p className="text-[10px] text-pw-muted capitalize">{health.trend}</p>
          {health.reasoning && (
            <p className="text-[9px] text-pw-muted/70 mt-0.5 max-w-[160px] truncate" title={health.reasoning}>
              {health.reasoning}
            </p>
          )}
        </div>
        {/* Circular score */}
        <div className="relative w-12 h-12">
          <svg className="w-12 h-12 -rotate-90" viewBox="0 0 48 48">
            <circle
              cx="24"
              cy="24"
              r="20"
              fill="none"
              stroke="#1f2a40"
              strokeWidth="3"
            />
            <circle
              cx="24"
              cy="24"
              r="20"
              fill="none"
              stroke={ringColor}
              strokeWidth="3"
              strokeDasharray={`${(score / 100) * 125.6} 125.6`}
              strokeLinecap="round"
            />
          </svg>
          <span
            className={`absolute inset-0 flex items-center justify-center text-xs font-bold ${scoreColor}`}
          >
            {score.toFixed(0)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
        <div>
          <p className="text-pw-muted">Latency</p>
          <p className="text-pw-text font-semibold">
            {health.latency_current.toFixed(0)}ms
          </p>
        </div>
        <div>
          <p className="text-pw-muted">Jitter</p>
          <p className="text-pw-text font-semibold">
            {health.jitter_current.toFixed(1)}ms
          </p>
        </div>
        <div>
          <p className="text-pw-muted">Loss</p>
          <p className="text-pw-text font-semibold">
            {health.packet_loss_current.toFixed(2)}%
          </p>
        </div>
      </div>

      {sparkData.length > 2 && (
        <div className="h-8 mt-2 -mx-1">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparkData}>
              <defs>
                <linearGradient id={`hs-${linkId}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={ringColor} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={ringColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="v"
                stroke={ringColor}
                strokeWidth={1}
                fill={`url(#hs-${linkId})`}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

/* ── Impact Row ─────────────────────────────────────────── */

function ImpactRow({
  label,
  aiVal,
  noAiVal,
  unit,
  decimals = 1,
}: {
  label: string;
  aiVal: number;
  noAiVal: number;
  unit: string;
  decimals?: number;
}) {
  const improvement =
    noAiVal > 0 ? (((noAiVal - aiVal) / noAiVal) * 100).toFixed(0) : "0";
  const improved = aiVal < noAiVal;

  return (
    <div className="flex items-center gap-4">
      <span className="text-xs text-pw-muted w-20">{label}</span>
      <div className="flex-1 flex items-center gap-3">
        <div className="flex-1">
          <div className="flex items-center justify-between text-[10px] mb-1">
            <span className="text-pw-emerald">AI: {aiVal.toFixed(decimals)}{unit}</span>
            <span className="text-pw-rose">No AI: {noAiVal.toFixed(decimals)}{unit}</span>
          </div>
          <div className="h-2 bg-pw-bg rounded-full overflow-hidden flex">
            <div
              className="h-full bg-pw-emerald/70 rounded-l-full transition-all duration-500"
              style={{
                width: `${Math.max(5, (aiVal / (Math.max(aiVal, noAiVal) * 1.2)) * 50)}%`,
              }}
            />
            <div className="w-px bg-pw-border" />
            <div
              className="h-full bg-pw-rose/70 rounded-r-full transition-all duration-500"
              style={{
                width: `${Math.max(5, (noAiVal / (Math.max(aiVal, noAiVal) * 1.2)) * 50)}%`,
              }}
            />
          </div>
        </div>
        {improved && Number(improvement) > 0 && (
          <span className="text-[10px] text-pw-emerald font-medium whitespace-nowrap">
            -{improvement}%
          </span>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
