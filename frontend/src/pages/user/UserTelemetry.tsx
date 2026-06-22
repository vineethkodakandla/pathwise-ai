import React from 'react';
import UserLayout from '../../components/layout/UserLayout';
import NetworkSimulation from '../NetworkSimulation';
import { useScoreboardWebSocket } from '../../hooks/useWebSocket';

export default function UserTelemetry() {
  useScoreboardWebSocket();
  return (
    <UserLayout>
      <div style={{ margin: -24, height: 'calc(100% + 48px)', overflow: 'auto' }}>
        <NetworkSimulation />
      </div>
    </UserLayout>
  );
}
