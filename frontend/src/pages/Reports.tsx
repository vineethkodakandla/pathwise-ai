import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  FileBarChart, Download, Heart, ArrowRightLeft, ScrollText, Loader2,
} from "lucide-react";
import { api } from "../services/api";

const REPORT_TYPES = [
  {
    id: "health-scores",
    label: "Health Scores",
    description: "Current health scores, LSTM predictions, and confidence levels for all WAN links",
    icon: Heart,
    color: "from-emerald-500 to-emerald-600",
    iconColor: "text-emerald-400",
    bgColor: "bg-emerald-500/15",
  },
  {
    id: "steering-events",
    label: "Steering Events",
    description: "Historical log of all traffic steering decisions — proactive (LSTM) and reactive (threshold)",
    icon: ArrowRightLeft,
    color: "from-blue-500 to-blue-600",
    iconColor: "text-blue-400",
    bgColor: "bg-blue-500/15",
  },
  {
    id: "audit-log",
    label: "Audit Log",
    description: "Tamper-evident record of all system events with SHA-256 checksums for compliance",
    icon: ScrollText,
    color: "from-violet-500 to-violet-600",
    iconColor: "text-violet-400",
    bgColor: "bg-violet-500/15",
  },
];

const Reports: React.FC = () => {
  const [downloading, setDownloading] = useState<string | null>(null);

  const handleDownload = async (reportId: string, format: "csv" | "pdf") => {
    const key = `${reportId}-${format}`;
    setDownloading(key);
    try {
      const response = await api.exportReport(reportId, format);
      const blob = new Blob([response], {
        type: format === "pdf" ? "application/pdf" : "text/csv",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pathwise_${reportId.replace("-", "_")}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Download failed:", err);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <FileBarChart className="w-6 h-6 text-pw-accent-light" />
          Reports
        </h1>
        <p className="text-pw-muted text-sm mt-1">
          Export health scores, steering events, and audit logs as PDF or CSV
        </p>
      </div>

      {/* Report Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {REPORT_TYPES.map((report) => {
          const Icon = report.icon;
          return (
            <motion.div
              key={report.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-6 flex flex-col"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className={`w-10 h-10 rounded-xl ${report.bgColor} flex items-center justify-center`}>
                  <Icon className={`w-5 h-5 ${report.iconColor}`} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">{report.label}</h3>
                </div>
              </div>

              <p className="text-xs text-pw-muted leading-relaxed flex-1 mb-6">
                {report.description}
              </p>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => handleDownload(report.id, "csv")}
                  disabled={downloading === `${report.id}-csv`}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-semibold bg-pw-surface border border-pw-border text-pw-text hover:border-pw-accent/30 hover:bg-pw-accent/5 transition-all disabled:opacity-50"
                >
                  {downloading === `${report.id}-csv` ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Download className="w-3.5 h-3.5" />
                  )}
                  CSV
                </button>
                <button
                  onClick={() => handleDownload(report.id, "pdf")}
                  disabled={downloading === `${report.id}-pdf`}
                  className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-semibold bg-gradient-to-r ${report.color} text-white hover:shadow-lg transition-all disabled:opacity-50`}
                >
                  {downloading === `${report.id}-pdf` ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Download className="w-3.5 h-3.5" />
                  )}
                  PDF
                </button>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};

export default Reports;
