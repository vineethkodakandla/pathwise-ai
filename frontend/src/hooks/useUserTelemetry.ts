import { useEffect, useState, useRef } from 'react';

export interface UserTelemetryPoint {
  site_id: string;
  link_type: string;
  latency_ms: number;
  jitter_ms: number;
  packet_loss_pct: number;
  health_score: number;
  bandwidth_mbps: number;
  timestamp: string;
}

export function useUserTelemetry(userId: string) {
  const [data, setData] = useState<UserTelemetryPoint[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!userId) return;
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(
      `${proto}://${window.location.host}/ws/user/${userId}/telemetry`
    );
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'telemetry') setData(msg.data);
      } catch {
        // Ignore malformed messages
      }
    };
    return () => ws.close();
  }, [userId]);

  return { data, connected };
}
