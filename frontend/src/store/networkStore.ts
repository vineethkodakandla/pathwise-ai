import { create } from "zustand";
import type {
  LinkHealth,
  SteeringEvent,
  ComparisonMetrics,
  PredictionResponse,
  ActiveRoutingRule,
} from "../types";

interface NetworkState {
  activeLinks: string[];
  setActiveLinks: (links: string[]) => void;

  lstmEnabled: boolean;
  setLstmEnabled: (enabled: boolean) => void;

  scoreboard: Record<string, LinkHealth>;
  updateScoreboard: (data: Record<string, LinkHealth>) => void;

  predictions: Record<string, PredictionResponse>;
  updatePredictions: (preds: Record<string, PredictionResponse>) => void;

  steeringEvents: SteeringEvent[];
  setSteeringEvents: (events: SteeringEvent[]) => void;

  activeRoutingRules: ActiveRoutingRule[];
  setActiveRoutingRules: (rules: ActiveRoutingRule[]) => void;

  comparison: {
    lstm_on: ComparisonMetrics;
    lstm_off: ComparisonMetrics;
  };
  updateComparison: (data: NetworkState["comparison"]) => void;

  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;

  tickCount: number;
  setTickCount: (n: number) => void;

  // Auth state
  isAuthenticated: boolean;
  userRole: string | null;
  userEmail: string | null;
  setAuth: (token: string, role: string, email: string) => void;
  logout: () => void;
}

export const useNetworkStore = create<NetworkState>((set) => ({
  activeLinks: [],
  setActiveLinks: (links) => set({ activeLinks: links }),

  lstmEnabled: false,
  setLstmEnabled: (enabled) => set({ lstmEnabled: enabled }),

  scoreboard: {},
  updateScoreboard: (data) => set({ scoreboard: data }),

  predictions: {},
  updatePredictions: (preds) =>
    set((s) => ({ predictions: { ...s.predictions, ...preds } })),

  steeringEvents: [],
  setSteeringEvents: (events) => set({ steeringEvents: events }),

  activeRoutingRules: [],
  setActiveRoutingRules: (rules) => set({ activeRoutingRules: rules }),

  comparison: {
    lstm_on: { avg_latency: 0, avg_jitter: 0, avg_packet_loss: 0 },
    lstm_off: { avg_latency: 0, avg_jitter: 0, avg_packet_loss: 0 },
  },
  updateComparison: (data) => set({ comparison: data }),

  wsConnected: false,
  setWsConnected: (connected) => set({ wsConnected: connected }),

  tickCount: 0,
  setTickCount: (n) => set({ tickCount: n }),

  isAuthenticated: !!localStorage.getItem("pathwise_token"),
  userRole: localStorage.getItem("pathwise_role"),
  userEmail: localStorage.getItem("pathwise_email"),
  setAuth: (token, role, email) => {
    localStorage.setItem("pathwise_token", token);
    localStorage.setItem("pathwise_role", role);
    localStorage.setItem("pathwise_email", email);
    set({ isAuthenticated: true, userRole: role, userEmail: email });
  },
  logout: () => {
    localStorage.removeItem("pathwise_token");
    localStorage.removeItem("pathwise_role");
    localStorage.removeItem("pathwise_email");
    set({ isAuthenticated: false, userRole: null, userEmail: null });
  },
}));
