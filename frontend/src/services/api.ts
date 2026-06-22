import axios from "axios";

const API_BASE =
  (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_URL) ||
  (typeof process !== "undefined" && (process as any).env?.REACT_APP_API_URL) ||
  "http://localhost:8000";

const client = axios.create({
  baseURL: API_BASE,
  timeout: 10_000,
});

// ── Auth Token Management ─────────────────────────────────────

export function setAuthToken(token: string) {
  localStorage.setItem("pathwise_token", token);
}

export function clearAuthToken() {
  localStorage.removeItem("pathwise_token");
  localStorage.removeItem("pathwise_role");
  localStorage.removeItem("pathwise_email");
}

export function getAuthToken(): string | null {
  return localStorage.getItem("pathwise_token");
}

// Axios interceptor: attach token to every request
client.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Axios interceptor: redirect to login on 401
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && window.location.pathname !== "/login") {
      clearAuthToken();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ── API Methods ───────────────────────────────────────────────

export const api = {
  // Auth
  login: (email: string, password: string) =>
    client.post("/api/v1/auth/login", { email, password }).then((r) => r.data),

  getMe: () =>
    client.get("/api/v1/auth/me").then((r) => r.data),

  getUsers: () =>
    client.get("/api/v1/auth/users").then((r) => r.data),

  // Status
  getStatus: () => client.get("/api/v1/status").then((r) => r.data),

  // Admin
  toggleLSTM: (enabled: boolean) =>
    client.post("/api/v1/admin/lstm-toggle", { enabled }).then((r) => r.data),

  getLSTMStatus: () =>
    client.get("/api/v1/admin/lstm-status").then((r) => r.data),

  // Telemetry
  getLinks: () =>
    client.get("/api/v1/telemetry/links").then((r) => r.data),

  getTelemetry: (linkId: string, window = 60) =>
    client.get(`/api/v1/telemetry/${linkId}`, { params: { window } }).then((r) => r.data),

  getRawTelemetry: (linkId: string, window = 60) =>
    client.get(`/api/v1/telemetry/${linkId}/raw`, { params: { window } }).then((r) => r.data),

  // Predictions
  getAllPredictions: () =>
    client.get("/api/v1/predictions/all").then((r) => r.data),

  // Steering
  getSteeringHistory: (limit = 50) =>
    client.get("/api/v1/steering/history", { params: { limit } }).then((r) => r.data),

  getComparisonMetrics: () =>
    client.get("/api/v1/metrics/comparison").then((r) => r.data),

  // Sandbox
  sandboxValidate: (source_link: string, target_link: string, traffic_classes: string[]) =>
    client.post("/api/v1/sandbox/validate", { source_link, target_link, traffic_classes }).then((r) => r.data),

  sandboxHistory: (limit = 20) =>
    client.get("/api/v1/sandbox/history", { params: { limit } }).then((r) => r.data),

  sandboxTopology: () =>
    client.get("/api/v1/sandbox/topology").then((r) => r.data),

  // Routing
  applyRoutingRule: (sandbox_report_id: string, source_link: string, target_link: string, traffic_classes: string[]) =>
    client.post("/api/v1/routing/apply", { sandbox_report_id, source_link, target_link, traffic_classes }).then((r) => r.data),

  getActiveRules: () =>
    client.get("/api/v1/routing/active").then((r) => r.data),

  getAllRules: () =>
    client.get("/api/v1/routing/all").then((r) => r.data),

  rollbackRule: (ruleId: string) =>
    client.delete(`/api/v1/routing/${ruleId}`).then((r) => r.data),

  // IBN
  ibnCreateIntent: (text: string) =>
    client.post("/api/v1/ibn/intents", { text }).then((r) => r.data),

  ibnListIntents: () =>
    client.get("/api/v1/ibn/intents").then((r) => r.data),

  ibnDeleteIntent: (intentId: string) =>
    client.delete(`/api/v1/ibn/intents/${intentId}`).then((r) => r.data),

  ibnPauseIntent: (intentId: string) =>
    client.post(`/api/v1/ibn/intents/${intentId}/pause`).then((r) => r.data),

  ibnResumeIntent: (intentId: string) =>
    client.post(`/api/v1/ibn/intents/${intentId}/resume`).then((r) => r.data),

  ibnParseIntent: (text: string) =>
    client.post("/api/v1/ibn/parse", { text }).then((r) => r.data),

  // Traffic Shaping
  getAppList: () =>
    client.get("/api/v1/traffic/apps").then((r) => r.data),

  getTrafficPolicies: () =>
    client.get("/api/v1/traffic/policies").then((r) => r.data),

  throttleApp: (app_name: string, bandwidth_kbps = 500) =>
    client.post("/api/v1/traffic/throttle", { app_name, bandwidth_kbps }).then((r) => r.data),

  prioritizeApp: (app_name: string) =>
    client.post("/api/v1/traffic/prioritize", { app_name }).then((r) => r.data),

  prioritizeOver: (high_app: string, low_app: string, throttle_kbps = 500) =>
    client.post("/api/v1/traffic/prioritize-over", { high_app, low_app, throttle_kbps }).then((r) => r.data),

  removeTrafficPolicy: (policyId: string) =>
    client.delete(`/api/v1/traffic/policies/${policyId}`).then((r) => r.data),

  resetTrafficPolicies: () =>
    client.post("/api/v1/traffic/reset").then((r) => r.data),

  // Audit Log
  getAuditLog: (params: Record<string, any> = {}) =>
    client.get("/api/v1/audit", { params }).then((r) => r.data),

  verifyAuditIntegrity: () =>
    client.get("/api/v1/audit/verify").then((r) => r.data),

  // Alerts
  getAlertHistory: (limit = 50) =>
    client.get("/api/v1/alerts/history", { params: { limit } }).then((r) => r.data),

  updateAlertConfig: (threshold?: number, suppression_window_s?: number) =>
    client.put("/api/v1/alerts/config", { threshold, suppression_window_s }).then((r) => r.data),

  // Reports (returns blob for download)
  exportReport: (reportType: string, format: string) =>
    client.get(`/api/v1/reports/${reportType}`, {
      params: { format },
      responseType: "arraybuffer",
    }).then((r) => r.data),
};

export function createWebSocket(): WebSocket {
  const token = getAuthToken();
  const wsUrl = API_BASE.replace(/^http/, "ws") + "/ws/scoreboard" + (token ? `?token=${token}` : "");
  return new WebSocket(wsUrl);
}
