import React, { useState } from 'react';
import AuthInput from './AuthInput.jsx';

/**
 * Signup Form Component
 */
export default function SignupForm({
  onSwitchToLogin,
  onSubmit,
  loading = false,
  error = null,
  active = false,
}) {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [infoMessage, setInfoMessage] = useState('');

  const validate = () => {
    const errors = {};
    if (!fullName.trim()) {
      errors.fullName = 'Full name is required.';
    }

    if (!email.trim()) {
      errors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      errors.password = 'Password is required.';
    } else if (password.length < 8) {
      errors.password = 'Password must be at least 8 characters long.';
    }

    if (!agreeTerms) {
      errors.terms = 'Please accept the Terms of Service to continue.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setInfoMessage('');
    if (!validate()) return;
    if (onSubmit) {
      onSubmit({ fullName, email, password });
    }
  };

  const handleGitHubAuth = () => {
    setInfoMessage('GitHub authentication preview: please use standard email & password registration.');
  };

  return (
    <div className="auth-form-card" inert={active ? undefined : ''} aria-hidden={!active}>
      <div className="auth-card-header">
        <h2 className="auth-card-title">Create your account</h2>
        <p className="auth-card-subtitle">
          Get started with StackSense
        </p>
      </div>

      {error && (
        <div className="auth-alert auth-alert-error" role="alert">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="16" />
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
          id="signup-name"
          name="fullName"
          label="Full name"
          type="text"
          value={fullName}
          onChange={(e) => {
            setFullName(e.target.value);
            if (fieldErrors.fullName) setFieldErrors({ ...fieldErrors, fullName: null });
          }}
          placeholder="John Doe"
          required
          autoComplete="name"
          disabled={loading || !active}
          error={fieldErrors.fullName}
          icon={
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          }
        />

        <AuthInput
          id="signup-email"
          name="email"
          label="Email address"
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (fieldErrors.email) setFieldErrors({ ...fieldErrors, email: null });
          }}
          placeholder="you@company.com"
          required
          autoComplete="email"
          disabled={loading || !active}
          error={fieldErrors.email}
          icon={
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
              <polyline points="22,6 12,13 2,6" />
            </svg>
          }
        />

        <AuthInput
          id="signup-password"
          name="password"
          label="Password"
          type="password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            if (fieldErrors.password) setFieldErrors({ ...fieldErrors, password: null });
          }}
          placeholder="Create a password"
          required
          autoComplete="new-password"
          disabled={loading || !active}
          error={fieldErrors.password}
          helperText="Must be at least 8 characters with a number and a letter."
          icon={
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          }
        />

        <div className="terms-checkbox-group">
          <label className="checkbox-label" htmlFor="agree-terms">
            <input
              id="agree-terms"
              type="checkbox"
              checked={agreeTerms}
              onChange={(e) => {
                setAgreeTerms(e.target.checked);
                if (fieldErrors.terms) setFieldErrors({ ...fieldErrors, terms: null });
              }}
              disabled={loading || !active}
              tabIndex={!active ? -1 : 0}
              className="auth-checkbox"
            />
            <span className="checkbox-custom" aria-hidden="true">
              <svg viewBox="0 0 12 10" fill="none">
                <polyline points="1.5 5 4.5 8 10.5 2" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span className="terms-text">
              I agree to the <a href="#terms" className="legal-link" tabIndex={!active ? -1 : 0}>Terms of Service</a> and <a href="#privacy" className="legal-link" tabIndex={!active ? -1 : 0}>Privacy Policy</a>.
            </span>
          </label>
          {fieldErrors.terms && (
            <p className="form-error-text terms-error" role="alert">
              {fieldErrors.terms}
            </p>
          )}
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
              <span>Creating account...</span>
            </>
          ) : (
            <>
              <span>Create account</span>
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
          <span>Already have an account? </span>
          <button
            type="button"
            className="auth-switch-btn"
            onClick={onSwitchToLogin}
            tabIndex={!active ? -1 : 0}
          >
            Sign in
          </button>
        </div>
      </form>
    </div>
  );
}
