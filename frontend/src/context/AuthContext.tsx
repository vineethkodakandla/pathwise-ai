import React, { createContext, useContext, useState, useEffect } from 'react';

export interface AuthUser {
  user_id: string;
  name: string;
  email: string;
  role: string;
  company?: string;
  avatar_initials: string;
  access_token: string;
  redirect_to: string;
  // True for one-click demo sessions, where the backend rejects every change.
  demo?: boolean;
}

export type DemoPersona = 'admin' | 'owner';

// Error message demoLogin throws when the backend is not running in DEMO_MODE.
export const DEMO_DISABLED = 'DEMO_DISABLED';

interface AuthCtx {
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<AuthUser>;
  demoLogin: (persona: DemoPersona) => Promise<AuthUser>;
  logout: () => void;
  isAdmin: boolean;
  isLoading: boolean;
}

// Local dev: VITE_API_URL unset → '' → relative '/api/v1' via the Vite proxy.
// Cloud: set VITE_API_URL to the backend origin so login reaches the hosted API.
const API_ROOT =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_URL) || '';

const AuthContext = createContext<AuthCtx>(null!);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('pathwise_user');
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {
        // Corrupted storage, ignore
      }
    }
    setIsLoading(false);
  }, []);

  const storeSession = (data: any): AuthUser => {
    const authUser: AuthUser = {
      user_id: data.user_id || data.id || '',
      name: data.name || data.email || '',
      email: data.email || '',
      role: data.role || 'BUSINESS_OWNER',
      company: data.company || '',
      avatar_initials:
        data.avatar_initials || data.name?.slice(0, 2).toUpperCase() || 'U',
      access_token: data.access_token || data.token || '',
      redirect_to:
        data.redirect_to ||
        (data.role === 'SUPER_ADMIN' ? '/admin/dashboard' : '/user/dashboard'),
      demo: data.demo === true,
    };
    localStorage.setItem('pathwise_user', JSON.stringify(authUser));
    setUser(authUser);
    return authUser;
  };

  const login = async (email: string, password: string): Promise<AuthUser> => {
    // Try v2 (DB-backed) first, fall back to v1 (in-memory)
    let res = await fetch(`${API_ROOT}/api/v1/auth/login/v2`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (res.status === 404) {
      res = await fetch(`${API_ROOT}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || 'Login failed');
    }
    return storeSession(await res.json());
  };

  const demoLogin = async (persona: DemoPersona): Promise<AuthUser> => {
    // Password-free sign-in to a read-only demo persona (backend DEMO_MODE only).
    const res = await fetch(`${API_ROOT}/api/v1/auth/demo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ persona }),
    });
    if (res.status === 404) {
      throw new Error(DEMO_DISABLED);
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Demo sign-in failed' }));
      throw new Error(err.detail || 'Demo sign-in failed');
    }
    return storeSession(await res.json());
  };

  const logout = () => {
    localStorage.removeItem('pathwise_user');
    localStorage.removeItem('pathwise_token');
    localStorage.removeItem('pathwise_role');
    localStorage.removeItem('pathwise_email');
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        demoLogin,
        logout,
        isAdmin: user?.role === 'SUPER_ADMIN',
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
