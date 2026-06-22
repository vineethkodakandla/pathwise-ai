import React from 'react';
import UserLayout from '../../components/layout/UserLayout';
import IBNConsole from '../IBNConsole';
import { useScoreboardWebSocket } from '../../hooks/useWebSocket';

export default function UserIBN() {
  useScoreboardWebSocket();
  return (
    <UserLayout>
      <div style={{ margin: -24, height: 'calc(100% + 48px)', overflow: 'auto' }}>
        <IBNConsole />
      </div>
    </UserLayout>
  );
}
