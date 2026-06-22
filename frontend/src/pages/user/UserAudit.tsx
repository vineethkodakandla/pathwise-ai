import React from 'react';
import UserLayout from '../../components/layout/UserLayout';
import AuditLog from '../AuditLog';
import { useScoreboardWebSocket } from '../../hooks/useWebSocket';

export default function UserAudit() {
  useScoreboardWebSocket();
  return (
    <UserLayout>
      <div style={{ margin: -24, height: 'calc(100% + 48px)', overflow: 'auto' }}>
        <AuditLog />
      </div>
    </UserLayout>
  );
}
