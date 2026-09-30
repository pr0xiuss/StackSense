import React from 'react';

/**
 * Auth Layout Component
 * Houses the top branding bar, background lighting orbs, and centered grid container.
 */
export default function AuthLayout({ children, onNavigateHome }) {
  return (
    <div className="auth-page">
      {/* Background Ambient Lighting Effects */}
      <div className="auth-bg-ambient" aria-hidden="true">
        <div className="auth-glow-top" />
        <div className="auth-glow-corner" />
      </div>

      {/* Top Header with StackSense Logo & GitHub link */}
      <header className="auth-header">
        <div className="container auth-header-container">
          <a
            href="#/"
            className="brand-link"
            onClick={(e) => {
              if (onNavigateHome) {
                e.preventDefault();
                onNavigateHome();
              }
            }}
            aria-label="StackSense Home"
          >
            <svg className="brand-icon" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M16 4L26 9.5V14.5L16 20L6 14.5V9.5L16 4Z" fill="#38BDF8" fillOpacity="0.9" />
              <path d="M6 17.5L16 23L26 17.5V21L16 26.5L6 21V17.5Z" fill="#6366F1" />
              <path d="M6 13.5L16 19L26 13.5V16.5L16 22L6 16.5V13.5Z" fill="#8B5CF6" fillOpacity="0.8" />
            </svg>
            <span className="brand-title">StackSense</span>
          </a>
        </div>
      </header>

      {/* Main Authentication Grid */}
      <main className="auth-main-wrapper">
        <div className="container auth-content-container">
          {children}
        </div>
      </main>
    </div>
  );
}
