import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  MapPin,
  Activity,
  CreditCard,
  LifeBuoy,
  UserCircle,
  LogOut,
  Wifi,
  Network,
  FlaskConical,
  Terminal,
  Radio,
  ScrollText,
  FileBarChart,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const NAV_ITEMS = [
  { to: '/user/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/user/sites', icon: MapPin, label: 'My Sites & Analytics' },
  { to: '/user/traffic', icon: Activity, label: 'Traffic Overview' },
  { to: '/user/billing', icon: CreditCard, label: 'Billing & Subscription' },
  { to: '/user/tickets', icon: LifeBuoy, label: 'Support Tickets' },
  { to: '/user/profile', icon: UserCircle, label: 'My Profile' },
];

const TOOLS_NAV = [
  { to: '/user/apps', icon: Radio, label: 'App Priority Switch' },
  { to: '/user/telemetry', icon: Network, label: 'Network Simulation' },
  { to: '/user/sandbox', icon: FlaskConical, label: 'Digital Twin Sandbox' },
  { to: '/user/ibn', icon: Terminal, label: 'Intent Policy (IBN)' },
  { to: '/user/audit', icon: ScrollText, label: 'Audit Log' },
  { to: '/user/reports', icon: FileBarChart, label: 'Reports' },
];

const UserLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, logout } = useAuth();

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside
        style={{
          width: 260,
          flexShrink: 0,
          backgroundColor: '#0f172a',
          display: 'flex',
          flexDirection: 'column',
          borderRight: '1px solid #1e293b',
        }}
      >
        {/* Brand */}
        <div
          style={{
            padding: '24px 20px',
            borderBottom: '1px solid #1e293b',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: 'linear-gradient(135deg, #2563eb, #06b6d4)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Wifi style={{ width: 20, height: 20, color: '#fff' }} />
            </div>
            <div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  color: '#f1f5f9',
                  letterSpacing: '-0.025em',
                }}
              >
                PathWise AI
              </div>
              <div
                style={{
                  fontSize: 10,
                  textTransform: 'uppercase',
                  letterSpacing: '0.15em',
                  color: '#60a5fa',
                }}
              >
                SD-WAN Management
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '16px 12px', overflowY: 'auto' }}>
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 12px',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 500,
                textDecoration: 'none',
                marginBottom: 2,
                color: isActive ? '#ffffff' : '#94a3b8',
                backgroundColor: isActive ? '#1e293b' : 'transparent',
                transition: 'all 0.15s',
              })}
            >
              <Icon style={{ width: 16, height: 16 }} />
              {label}
            </NavLink>
          ))}

          {/* Separator + Network Tools */}
          <div style={{
            margin: '12px 0 8px',
            padding: '0 12px',
            fontSize: 10,
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            color: '#475569',
            borderTop: '1px solid #1e293b',
            paddingTop: 12,
          }}>
            Network Tools
          </div>
          {TOOLS_NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 12px',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 500,
                textDecoration: 'none',
                marginBottom: 2,
                color: isActive ? '#ffffff' : '#94a3b8',
                backgroundColor: isActive ? '#1e293b' : 'transparent',
                transition: 'all 0.15s',
              })}
            >
              <Icon style={{ width: 16, height: 16 }} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer / Sign Out */}
        <div
          style={{
            padding: '16px 12px',
            borderTop: '1px solid #1e293b',
          }}
        >
          <button
            onClick={logout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 12px',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 500,
              color: '#94a3b8',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              width: '100%',
              textAlign: 'left',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#f87171';
              e.currentTarget.style.backgroundColor = 'rgba(248,113,113,0.1)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#94a3b8';
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            <LogOut style={{ width: 16, height: 16 }} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Topbar */}
        <header
          style={{
            height: 56,
            backgroundColor: '#ffffff',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            padding: '0 24px',
            gap: 12,
            flexShrink: 0,
          }}
        >
          {user?.company && (
            <span
              style={{
                fontSize: 13,
                color: '#64748b',
                marginRight: 'auto',
                fontWeight: 500,
              }}
            >
              {user.company}
            </span>
          )}
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              backgroundColor: '#2563eb',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            {user?.avatar_initials || 'U'}
          </div>
          <span style={{ fontSize: 13, fontWeight: 500, color: '#0f172a' }}>
            {user?.name || 'User'}
          </span>
        </header>

        {/* Content */}
        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            backgroundColor: '#f8fafc',
            padding: 24,
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
};

export default UserLayout;
