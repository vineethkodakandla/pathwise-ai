import React from 'react';
import UserLayout from '../../components/layout/UserLayout';
import Reports from '../Reports';
import { useScoreboardWebSocket } from '../../hooks/useWebSocket';

export default function UserReports() {
  useScoreboardWebSocket();
  return (
    <UserLayout>
      <div style={{ margin: -24, height: 'calc(100% + 48px)', overflow: 'auto' }}>
        <Reports />
      </div>
    </UserLayout>
  );
}
