import React, { useState } from 'react';
import AuthInput from './AuthInput.jsx';

/**
 * Login Form Component
 */
export default function LoginForm({
  onSwitchToSignup,
  onSubmit,
  loading = false,
  error = null,
  successMessage = null,
  active = true,
}) {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [infoMessage, setInfoMessage] = useState('');

  const validate = () => {
    const errors = {};
    if (!identifier.trim()) {
      errors.identifier = 'Username or email is required.';
    }

    if (!password) {
      errors.password = 'Password is required.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setInfoMessage('');
    if (!validate()) return;
    if (onSubmit) {
      onSubmit({ identifier: identifier.trim(), password });
    }
  };

  const handleForgotPassword = (e) => {
    e.preventDefault();
    setInfoMessage('If an account exists for this identifier, password reset instructions will be sent.');
  };

  const handleGitHubAuth = () => {
    setInfoMessage('GitHub authentication preview: please use standard credentials to log in.');
  };

  return (
    <div className="auth-form-card" inert={active ? undefined : ''} aria-hidden={!active}>
      <div className="auth-card-header">
        <h2 className="auth-card-title">Log in to StackSense</h2>
        <p className="auth-card-subtitle">
          Enter your credentials to access your projects and repositories.
        </p>
      </div>

      {successMessage && (
        <div className="auth-alert auth-alert-success" role="status">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>{successMessage}</span>
        </div>
      )}

      {error && (
        <div className="auth-alert auth-alert-error" role="alert">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>{error}</span>
        </div>
      )}

      {infoMessage && (
        <div className="auth-alert auth-alert-info" role="status">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <span>{infoMessage}</span>
        </div>
      )}

      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <AuthInput
          id="login-identifier"
          name="identifier"
          label="Username or email"
          type="text"
          value={identifier}
          onChange={(e) => {
            setIdentifier(e.target.value);
            if (fieldErrors.identifier) setFieldErrors({ ...fieldErrors, identifier: null });
          }}
          placeholder="Enter your username or email"
          required
          autoComplete="username"
          disabled={loading || !active}
          error={fieldErrors.identifier}
          icon={
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          }
        />

        <div className="password-field-group">
          <AuthInput
            id="login-password"
            name="password"
            label="Password"
            type="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (fieldErrors.password) setFieldErrors({ ...fieldErrors, password: null });
            }}
            placeholder="Enter your password"
            required
            autoComplete="current-password"
            disabled={loading || !active}
            error={fieldErrors.password}
            icon={
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            }
          />
          <div className="forgot-password-row">
            <button
              type="button"
              className="forgot-link"
              onClick={handleForgotPassword}
              tabIndex={!active ? -1 : 0}
            >
              Forgot password?
            </button>
          </div>
        </div>

        <button
          type="submit"
          className="btn-auth-submit"
          disabled={loading || !active}
          tabIndex={!active ? -1 : 0}
        >
          {loading ? (
            <>
              <span className="btn-spinner" aria-hidden="true" />
              <span>Logging in...</span>
            </>
          ) : (
            <>
              <span>Log in</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </>
          )}
        </button>

        <div className="auth-divider">
          <span>OR</span>
        </div>

        <button
          type="button"
          className="btn-github-auth"
          onClick={handleGitHubAuth}
          disabled={loading || !active}
          tabIndex={!active ? -1 : 0}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
          </svg>
          <span>Continue with GitHub</span>
        </button>

        <div className="auth-footer-prompt">
          <span>Don't have an account? </span>
          <button
            type="button"
            className="auth-switch-btn"
            onClick={onSwitchToSignup}
            tabIndex={!active ? -1 : 0}
          >
            Sign up
          </button>
        </div>
      </form>
    </div>
  );
}
