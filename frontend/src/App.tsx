import React from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";

import { AuthProvider, useAuth } from "./context/AuthContext";

// Auth
import LoginPage from "./pages/auth/LoginPage";

// Admin pages
import AdminDashboard from "./pages/admin/AdminDashboard";
import UserManagement from "./pages/admin/UserManagement";
import SiteAnalytics from "./pages/admin/SiteAnalytics";
import RevenueDashboard from "./pages/admin/RevenueDashboard";
import LSTMControlCenter from "./pages/admin/LSTMControlCenter";
import TicketDashboard from "./pages/admin/TicketDashboard";

// User pages
import UserDashboard from "./pages/user/UserDashboard";
import MySitesAnalytics from "./pages/user/MySitesAnalytics";
import TrafficOverview from "./pages/user/TrafficOverview";
import BillingDashboard from "./pages/user/BillingDashboard";
import SupportTickets from "./pages/user/SupportTickets";
import UserProfile from "./pages/user/UserProfile";
import UserTelemetry from "./pages/user/UserTelemetry";
import UserSandbox from "./pages/user/UserSandbox";
import UserIBN from "./pages/user/UserIBN";
import UserAudit from "./pages/user/UserAudit";
import UserReports from "./pages/user/UserReports";
import AppPriorityManager from "./pages/user/AppPriorityManager";
import AppQoSOverview from "./pages/admin/AppQoSOverview";

// Legacy pages (existing system)
import Dashboard from "./pages/Dashboard";
import NetworkSimulation from "./pages/NetworkSimulation";
import SandboxViewer from "./pages/SandboxViewer";
import IBNConsole from "./pages/IBNConsole";
import AuditLog from "./pages/AuditLog";
import Reports from "./pages/Reports";
import AdminPanel from "./pages/AdminPanel";

// Guards
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, isAdmin, isLoading } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" />;
  if (!isAdmin) return <Navigate to="/user/dashboard" />;
  return <>{children}</>;
}

function UserRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" />;
  return <>{children}</>;
}

function LoadingScreen() {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: '#0f172a', color: '#94a3b8', fontFamily: 'Inter, system-ui, sans-serif'
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10, margin: '0 auto 12px',
          background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'white', fontWeight: 700, fontSize: 18
        }}>P</div>
        <p>Loading PathWise AI...</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Auth */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/login" />} />

          {/* Admin Portal */}
          <Route path="/admin/dashboard" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
          <Route path="/admin/users" element={<AdminRoute><UserManagement /></AdminRoute>} />
          <Route path="/admin/analytics" element={<AdminRoute><SiteAnalytics /></AdminRoute>} />
          <Route path="/admin/revenue" element={<AdminRoute><RevenueDashboard /></AdminRoute>} />
          <Route path="/admin/lstm" element={<AdminRoute><LSTMControlCenter /></AdminRoute>} />
          <Route path="/admin/tickets" element={<AdminRoute><TicketDashboard /></AdminRoute>} />
          <Route path="/admin/app-qos" element={<AdminRoute><AppQoSOverview /></AdminRoute>} />

          {/* User Portal */}
          <Route path="/user/dashboard" element={<UserRoute><UserDashboard /></UserRoute>} />
          <Route path="/user/sites" element={<UserRoute><MySitesAnalytics /></UserRoute>} />
          <Route path="/user/traffic" element={<UserRoute><TrafficOverview /></UserRoute>} />
          <Route path="/user/billing" element={<UserRoute><BillingDashboard /></UserRoute>} />
          <Route path="/user/tickets" element={<UserRoute><SupportTickets /></UserRoute>} />
          <Route path="/user/profile" element={<UserRoute><UserProfile /></UserRoute>} />

          {/* Network Tools (legacy features in user portal) */}
          <Route path="/user/telemetry" element={<UserRoute><UserTelemetry /></UserRoute>} />
          <Route path="/user/sandbox" element={<UserRoute><UserSandbox /></UserRoute>} />
          <Route path="/user/ibn" element={<UserRoute><UserIBN /></UserRoute>} />
          <Route path="/user/audit" element={<UserRoute><UserAudit /></UserRoute>} />
          <Route path="/user/reports" element={<UserRoute><UserReports /></UserRoute>} />
          <Route path="/user/apps" element={<UserRoute><AppPriorityManager /></UserRoute>} />

          {/* Legacy system pages (still accessible) */}
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/simulation" element={<NetworkSimulation />} />
          <Route path="/sandbox" element={<SandboxViewer />} />
          <Route path="/ibn" element={<IBNConsole />} />
          <Route path="/audit" element={<AuditLog />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/admin-legacy" element={<AdminPanel />} />

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}
