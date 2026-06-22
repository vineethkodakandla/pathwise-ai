import { useEffect, useRef, useCallback } from "react";
import { createWebSocket } from "../services/api";
import { useNetworkStore } from "../store/networkStore";
import type { ScoreboardUpdate } from "../types";

export function useScoreboardWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const {
    setWsConnected,
    updateScoreboard,
    setSteeringEvents,
    updateComparison,
    setLstmEnabled,
    setActiveRoutingRules,
  } = useNetworkStore();

  const connect = useCallback(() => {
    try {
      const ws = createWebSocket();
      wsRef.current = ws;

      ws.onopen = () => setWsConnected(true);

      ws.onmessage = (event) => {
        try {
          const msg: ScoreboardUpdate = JSON.parse(event.data);
          if (msg.type === "scoreboard_update") {
            updateScoreboard(msg.links);
            setSteeringEvents(msg.steering_events || []);
            updateComparison(msg.comparison);
            setLstmEnabled(msg.lstm_enabled);
            setActiveRoutingRules(msg.active_routing_rules || []);
          }
        } catch { /* ignore parse errors */ }
      };

      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimer.current = setTimeout(connect, 2000);
      };

      ws.onerror = () => ws.close();
    } catch {
      reconnectTimer.current = setTimeout(connect, 2000);
    }
  }, [setWsConnected, updateScoreboard, setSteeringEvents, updateComparison, setLstmEnabled, setActiveRoutingRules]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);
}
