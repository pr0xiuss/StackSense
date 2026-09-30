import React, { useState, useEffect, useCallback } from 'react';
import AuthLayout from '../components/auth/AuthLayout.jsx';
import AuthBranding from '../components/auth/AuthBranding.jsx';
import AuthPanel from '../components/auth/AuthPanel.jsx';
import { useAuth } from '../auth/AuthContext.jsx';

/**
 * Authentication Page Component
 * Manages mode switching (Login <-> Signup), backend auth submission,
 * error handling, and post-auth navigation.
 */
export default function AuthPage({
  initialMode = 'login',
  onNavigateHome,
}) {
  const { user: authenticatedUser, login, register, logout } = useAuth();
  const [authMode, setAuthMode] = useState(initialMode);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [authSuccessMessage, setAuthSuccessMessage] = useState('');

  // Synchronize initialMode changes or URL hash
  useEffect(() => {
    setAuthMode(initialMode === 'signup' ? 'signup' : 'login');
    setError(null);
  }, [initialMode]);

  // Redirect to projects dashboard if user is already authenticated
  useEffect(() => {
    if (authenticatedUser) {
      window.location.hash = '#/projects';
    }
  }, [authenticatedUser]);

  const handleSwitchMode = useCallback((mode, clearMessage = true) => {
    setAuthMode(mode);
    setError(null);
    if (clearMessage) {
      setAuthSuccessMessage('');
    }
    // Update hash gracefully without triggering full page reload
    if (window.history.pushState) {
      window.history.pushState(null, '', `#/${mode}`);
    } else {
      window.location.hash = `#/${mode}`;
    }
  }, []);

  const handleLogin = async ({ identifier, password }) => {
    setLoading(true);
    setError(null);
    setAuthSuccessMessage('');

    try {
      await login(identifier, password);
      // Immediately open projects dashboard
      window.location.hash = '#/projects';
    } catch (err) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async ({ username, email, password }) => {
    setLoading(true);
    setError(null);

    try {
      await register(email, username, password);
      // Inform user and redirect to sign-in page
      setAuthSuccessMessage('Account created successfully! Please sign in with your credentials.');
      handleSwitchMode('login', false);
    } catch (err) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout onNavigateHome={onNavigateHome}>
      <div className="auth-grid">
        <AuthBranding authMode={authMode} />
        <AuthPanel
          authMode={authMode}
          onSwitchMode={handleSwitchMode}
          onLoginSubmit={handleLogin}
          onSignupSubmit={handleSignup}
          loading={loading}
          error={error}
          successMessage={authSuccessMessage}
        />
      </div>
    </AuthLayout>
  );
}
