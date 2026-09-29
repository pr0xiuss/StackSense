import React, { useEffect } from 'react';
import { useAuth } from '../auth/AuthContext.jsx';

/**
 * ProtectedRoute component
 *
 * Ensures:
 * 1. Shows a sleek loading skeleton while auth state is resolving on startup
 * 2. If unauthenticated, immediately redirects to /#/login using history replacement
 * 3. Enforces fresh auth check whenever navigated or restored via browser Back/Forward
 */
export default function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      if (window.history.replaceState) {
        window.history.replaceState(null, '', '#/login');
      } else {
        window.location.hash = '#/login';
      }
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    }
  }, [isAuthenticated, loading]);

  if (loading) {
    return (
      <div
        className="auth-loading-screen"
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg-primary, #080C14)',
          color: 'var(--text-secondary, #94A3B8)',
          fontFamily: 'var(--font-sans, Inter, sans-serif)',
          gap: '1rem',
        }}
      >
        <div
          style={{
            width: '40px',
            height: '40px',
            borderRadius: '50%',
            border: '3px solid rgba(99, 102, 241, 0.2)',
            borderTopColor: '#6366F1',
            animation: 'spin 0.8s linear infinite',
          }}
        />
        <p style={{ fontSize: '0.9rem', color: '#94a3b8' }}>Verifying authentication session...</p>
        <style>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return children;
}
