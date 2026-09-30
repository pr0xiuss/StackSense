import React, { useRef, useEffect } from 'react';
import LoginForm from './LoginForm.jsx';
import SignupForm from './SignupForm.jsx';

/**
 * Sliding Auth Panel Component
 * Wraps LoginForm and SignupForm in a zero-overflow viewport and executes
 * the horizontal slide transition between Login and Signup modes.
 */
export default function AuthPanel({
  authMode = 'login',
  onSwitchMode,
  onLoginSubmit,
  onSignupSubmit,
  loading = false,
  error = null,
  successMessage = null,
}) {
  const isLogin = authMode === 'login';
  const viewportRef = useRef(null);

  // Focus the first input of the newly activated form after transition
  useEffect(() => {
    const timer = setTimeout(() => {
      const activeInput = isLogin
        ? document.getElementById('login-identifier')
        : document.getElementById('signup-username');
      if (activeInput && document.activeElement && document.activeElement.tagName !== 'INPUT') {
        // Only autofocus if user is not already actively focused elsewhere
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [authMode, isLogin]);

  return (
    <div className="auth-card" aria-live="polite">
      <div className="auth-card-viewport" ref={viewportRef}>
        <div
          className={`auth-slider-track ${isLogin ? 'slide-login' : 'slide-signup'}`}
          style={{
            transform: isLogin ? 'translateX(0%)' : 'translateX(-50%)',
          }}
        >
          {/* Login Slide */}
          <div className="auth-slide-pane" aria-hidden={!isLogin}>
            <LoginForm
              active={isLogin}
              onSwitchToSignup={() => onSwitchMode('signup')}
              onSubmit={onLoginSubmit}
              loading={loading && isLogin}
              error={isLogin ? error : null}
              successMessage={isLogin ? successMessage : null}
            />
          </div>

          {/* Signup Slide */}
          <div className="auth-slide-pane" aria-hidden={isLogin}>
            <SignupForm
              active={!isLogin}
              onSwitchToLogin={() => onSwitchMode('login')}
              onSubmit={onSignupSubmit}
              loading={loading && !isLogin}
              error={!isLogin ? error : null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
