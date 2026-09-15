import React from 'react';

// Shown to visitors signed in through the one-click demo (backend DEMO_MODE),
// where the server rejects every change.
const DemoBanner: React.FC = () => (
  <div
    role="status"
    style={{
      marginBottom: 16,
      padding: '10px 14px',
      borderRadius: 8,
      border: '1px solid #fcd34d',
      backgroundColor: '#fffbeb',
      color: '#92400e',
      fontSize: 13,
    }}
  >
    Read-only demo: you can browse everything, but changes are disabled on this shared instance.
  </div>
);

export default DemoBanner;
