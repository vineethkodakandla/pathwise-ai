import React from 'react';
import UserLayout from '../../components/layout/UserLayout';
import SandboxViewer from '../SandboxViewer';
import { useScoreboardWebSocket } from '../../hooks/useWebSocket';

export default function UserSandbox() {
  useScoreboardWebSocket();
  return (
    <UserLayout>
      <div style={{ margin: -24, height: 'calc(100% + 48px)', overflow: 'auto' }}>
        <SandboxViewer />
      </div>
    </UserLayout>
  );
}
