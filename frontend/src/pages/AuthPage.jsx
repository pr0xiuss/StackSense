import React, { useState, useEffect, useCallback } from 'react';
import AuthLayout from '../components/auth/AuthLayout.jsx';
import AuthBranding from '../components/auth/AuthBranding.jsx';
import AuthPanel from '../components/auth/AuthPanel.jsx';
import { useAuth } from '../auth/AuthContext.jsx';


export default function AuthPage({
  initialMode = 'login',
  onNavigateHome,
}) {
  const { user: authenticatedUser, login, register, logout } = useAuth();
  const [authMode, setAuthMode] = useState(initialMode);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [authSuccessMessage, setAuthSuccessMessage] = useState('');

  useEffect(() => {
    setAuthMode(initialMode === 'signup' ? 'signup' : 'login');
    setError(null);
  }, [initialMode]);

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
