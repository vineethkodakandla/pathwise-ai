import React, { useState } from "react";
import { motion } from "framer-motion";
import { Activity, LogIn, AlertCircle, Lock } from "lucide-react";
import { api, setAuthToken } from "../services/api";
import { useNetworkStore } from "../store/networkStore";
import { useNavigate } from "react-router-dom";

const LoginPage: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const setAuth = useNetworkStore((s) => s.setAuth);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.login(email, password);
      setAuthToken(res.access_token);
      setAuth(res.access_token, res.role, res.email);
      navigate("/dashboard");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Invalid credentials";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-pw-bg flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-pw-accent to-pw-cyan flex items-center justify-center mx-auto mb-4">
            <Activity className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">PathWise AI</h1>
          <p className="text-pw-muted text-sm mt-1">AI-Powered SD-WAN Management</p>
        </div>

        {/* Login Card */}
        <div className="glass-card p-8">
          <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
            <LogIn className="w-5 h-5 text-pw-accent-light" />
            Sign In
          </h2>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm mb-4 ${
                error.includes("locked")
                  ? "bg-pw-amber/10 text-pw-amber border border-pw-amber/20"
                  : "bg-pw-rose/10 text-pw-rose border border-pw-rose/20"
              }`}
            >
              {error.includes("locked") ? (
                <Lock className="w-4 h-4 flex-shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
              )}
              {error}
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs uppercase tracking-wider text-pw-muted font-medium mb-1.5 block">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@pathwise.local"
                className="w-full bg-pw-bg/80 border border-pw-border rounded-xl px-4 py-3 text-sm text-white placeholder:text-pw-muted/40 focus:outline-none focus:border-pw-accent/50"
                required
              />
            </div>
            <div>
              <label className="text-xs uppercase tracking-wider text-pw-muted font-medium mb-1.5 block">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                className="w-full bg-pw-bg/80 border border-pw-border rounded-xl px-4 py-3 text-sm text-white placeholder:text-pw-muted/40 focus:outline-none focus:border-pw-accent/50"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-pw-accent to-pw-cyan text-white hover:shadow-lg hover:shadow-pw-accent/20 transition-all disabled:opacity-50"
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-pw-border">
            <p className="text-[10px] text-pw-muted/60 text-center">
              Default: admin@pathwise.local / admin
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default LoginPage;
