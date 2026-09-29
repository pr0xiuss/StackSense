import React, { useState, useEffect, useCallback } from 'react';
import AuthLayout from '../components/auth/AuthLayout.jsx';
import AuthBranding from '../components/auth/AuthBranding.jsx';
import AuthPanel from '../components/auth/AuthPanel.jsx';
import { authApi } from '../api/authApi.js';

/**
 * Authentication Page Component
 * Manages mode switching (Login <-> Signup), backend auth submission,
 * error handling, and authenticated session state.
 */
export default function AuthPage({
  initialMode = 'login',
  onNavigateHome,
}) {
  const [authMode, setAuthMode] = useState(initialMode);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [authenticatedUser, setAuthenticatedUser] = useState(null);
  const [authSuccessMessage, setAuthSuccessMessage] = useState('');

  // Synchronize initialMode changes or URL hash
  useEffect(() => {
    setAuthMode(initialMode === 'signup' ? 'signup' : 'login');
    setError(null);
  }, [initialMode]);

  // Check if an active session exists on mount
  useEffect(() => {
    const token = authApi.getStoredToken();
    if (token) {
      authApi.getCurrentUser(token)
        .then((user) => setAuthenticatedUser(user))
        .catch(() => {
          authApi.clearStoredToken();
        });
    }
  }, []);

  const handleSwitchMode = useCallback((mode) => {
    setAuthMode(mode);
    setError(null);
    setAuthSuccessMessage('');
    // Update hash gracefully without triggering full page reload
    if (window.history.pushState) {
      window.history.pushState(null, '', `#/${mode}`);
    } else {
      window.location.hash = `#/${mode}`;
    }
  }, []);

  const handleLogin = async ({ email, password }) => {
    setLoading(true);
    setError(null);
    setAuthSuccessMessage('');

    try {
      const data = await authApi.login(email, password);
      // Retrieve user profile with token
      const user = await authApi.getCurrentUser(data.access_token);
      setAuthenticatedUser(user);
      setAuthSuccessMessage(`Welcome back, ${user.email}!`);
    } catch (err) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async ({ email, password }) => {
    setLoading(true);
    setError(null);
    setAuthSuccessMessage('');

    try {
      // 1. Register with backend
      await authApi.register(email, password);
      // 2. Automatically log in to issue token
      const data = await authApi.login(email, password);
      const user = await authApi.getCurrentUser(data.access_token);
      setAuthenticatedUser(user);
      setAuthSuccessMessage(`Account created successfully! Welcome, ${user.email}.`);
    } catch (err) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = () => {
    authApi.clearStoredToken();
    setAuthenticatedUser(null);
    setAuthSuccessMessage('');
    setError(null);
    handleSwitchMode('login');
  };

  return (
    <AuthLayout onNavigateHome={onNavigateHome}>
      {authenticatedUser ? (
        <div className="auth-authenticated-card">
          <div className="auth-card-header">
            <div className="auth-badge-success">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <h2 className="auth-card-title">Authenticated to StackSense</h2>
            <p className="auth-card-subtitle">
              {authSuccessMessage || `Signed in as ${authenticatedUser.email}`}
            </p>
          </div>

          <div className="auth-user-details">
            <div className="auth-user-row">
              <span className="user-label">User ID:</span>
              <span className="user-value">{authenticatedUser.id}</span>
            </div>
            <div className="auth-user-row">
              <span className="user-label">Email:</span>
              <span className="user-value">{authenticatedUser.email}</span>
            </div>
            <div className="auth-user-row">
              <span className="user-label">Status:</span>
              <span className="user-value status-active">Active</span>
            </div>
          </div>

          <div className="auth-session-actions">
            <button
              type="button"
              className="btn-auth-submit"
              onClick={onNavigateHome}
            >
              <span>Explore Architecture & Projects</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
            <button
              type="button"
              className="btn-auth-secondary"
              onClick={handleSignOut}
            >
              Sign out
            </button>
          </div>
        </div>
      ) : (
        <div className="auth-grid">
          <AuthBranding authMode={authMode} />
          <AuthPanel
            authMode={authMode}
            onSwitchMode={handleSwitchMode}
            onLoginSubmit={handleLogin}
            onSignupSubmit={handleSignup}
            loading={loading}
            error={error}
          />
        </div>
      )}
    </AuthLayout>
  );
}
