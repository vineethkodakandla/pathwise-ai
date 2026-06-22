import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const authUser = await login(email, password);
      navigate(authUser.redirect_to, { replace: true });
    } catch (err: any) {
      // Generic error message -- no username enumeration (Req-Func-Sw-16 / UC-6)
      setError('Invalid credentials. Please check your email and password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#0f172a',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 420,
          padding: '0 24px',
        }}
      >
        {/* Logo / Wordmark */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 16,
              background: 'linear-gradient(135deg, #2563eb, #06b6d4)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
            }}
          >
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#ffffff"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>
          <h1
            style={{
              fontSize: 28,
              fontWeight: 800,
              color: '#f1f5f9',
              margin: '0 0 6px',
              letterSpacing: '-0.025em',
            }}
          >
            PathWise AI
          </h1>
          <p
            style={{
              fontSize: 13,
              color: '#64748b',
              margin: 0,
              letterSpacing: '0.02em',
            }}
          >
            Intelligent SD-WAN Management
          </p>
        </div>

        {/* Login Card */}
        <div
          style={{
            backgroundColor: '#1e293b',
            borderRadius: 12,
            padding: 32,
            border: '1px solid #334155',
          }}
        >
          <h2
            style={{
              fontSize: 18,
              fontWeight: 600,
              color: '#f1f5f9',
              margin: '0 0 24px',
            }}
          >
            Sign in to your account
          </h2>

          {/* Error */}
          {error && (
            <div
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: 8,
                padding: '10px 14px',
                marginBottom: 20,
                fontSize: 13,
                color: '#fca5a5',
              }}
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Email */}
            <div style={{ marginBottom: 16 }}>
              <label
                htmlFor="email"
                style={{
                  display: 'block',
                  fontSize: 12,
                  fontWeight: 500,
                  color: '#94a3b8',
                  marginBottom: 6,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                autoComplete="email"
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: 8,
                  color: '#f1f5f9',
                  fontSize: 14,
                  outline: 'none',
                  boxSizing: 'border-box',
                  transition: 'border-color 0.15s',
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = '#2563eb')}
                onBlur={(e) => (e.currentTarget.style.borderColor = '#334155')}
              />
            </div>

            {/* Password */}
            <div style={{ marginBottom: 24 }}>
              <label
                htmlFor="password"
                style={{
                  display: 'block',
                  fontSize: 12,
                  fontWeight: 500,
                  color: '#94a3b8',
                  marginBottom: 6,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: 8,
                  color: '#f1f5f9',
                  fontSize: 14,
                  outline: 'none',
                  boxSizing: 'border-box',
                  transition: 'border-color 0.15s',
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = '#2563eb')}
                onBlur={(e) => (e.currentTarget.style.borderColor = '#334155')}
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '12px 0',
                backgroundColor: loading ? '#1d4ed8' : '#2563eb',
                color: '#ffffff',
                border: 'none',
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.15s',
                opacity: loading ? 0.8 : 1,
              }}
              onMouseEnter={(e) => {
                if (!loading) e.currentTarget.style.backgroundColor = '#1d4ed8';
              }}
              onMouseLeave={(e) => {
                if (!loading) e.currentTarget.style.backgroundColor = '#2563eb';
              }}
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          {/* Security badges */}
          <div
            style={{
              marginTop: 24,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                backgroundColor: 'rgba(22, 163, 74, 0.1)',
                border: '1px solid rgba(22, 163, 74, 0.3)',
                borderRadius: 6,
                padding: '5px 12px',
                fontSize: 11,
                fontWeight: 500,
                color: '#4ade80',
              }}
            >
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              TLS 1.3 Encrypted Connection
            </div>
            <p
              style={{
                fontSize: 11,
                color: '#475569',
                margin: 0,
              }}
            >
              Account locked after 5 failed attempts
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
