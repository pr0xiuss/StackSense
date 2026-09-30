import React from 'react';

/**
 * Left branding column displaying the technical tagline, context badge,
 * and developer-focused isometric architecture illustration.
 */
export default function AuthBranding({ authMode = 'login' }) {
  const isLogin = authMode === 'login';

  return (
    <div className="auth-branding">
      <div className="auth-branding-content">
        <div className="auth-eyebrow" key={`eyebrow-${authMode}`}>
          <span className="eyebrow-dot" aria-hidden="true" />
          <span>{isLogin ? 'WELCOME BACK' : 'GET STARTED'}</span>
        </div>

        <h1 className="auth-heading" key={`heading-${authMode}`}>
          {isLogin ? (
            <>
              Turn code <br />
              into <span className="auth-highlight">clarity.</span>
            </>
          ) : (
            <>
              Build a deeper <br />
              understanding of <br />
              your <span className="auth-highlight">codebase.</span>
            </>
          )}
        </h1>

        <p className="auth-lead" key={`lead-${authMode}`}>
          {isLogin
            ? 'Understand your codebase, explore architecture and make better decisions with StackSense.'
            : 'Create your account and start exploring your architecture insights in minutes.'}
        </p>
      </div>

      {/* Decorative Technical Architecture Illustration matching the reference */}
      <div className="auth-illustration-wrapper" aria-hidden="true">
        <div className="auth-ambient-glow" />

        <div className="auth-tech-art">
          {/* Main IDE Window Plate */}
          <div className="art-window art-window-main">
            <div className="art-window-bar">
              <span className="art-dot art-dot-1" />
              <span className="art-dot art-dot-2" />
              <span className="art-dot art-dot-3" />
              <span className="art-tab">architecture.py</span>
            </div>
            <div className="art-code-lines">
              <div className="art-code-line line-indent-0 w-60 accent-blue" />
              <div className="art-code-line line-indent-1 w-80" />
              <div className="art-code-line line-indent-2 w-45 accent-purple" />
              <div className="art-code-line line-indent-2 w-70" />
              <div className="art-code-line line-indent-1 w-50" />
              <div className="art-code-line line-indent-1 w-75 accent-cyan" />
              <div className="art-code-line line-indent-2 w-40" />
            </div>
          </div>

          {/* Secondary Stacked Window Plate */}
          <div className="art-window art-window-back">
            <div className="art-window-bar">
              <span className="art-dot" />
              <span className="art-dot" />
              <span className="art-dot" />
            </div>
            <div className="art-code-lines">
              <div className="art-code-line line-indent-0 w-70" />
              <div className="art-code-line line-indent-1 w-50" />
            </div>
          </div>

          {/* Floating Architecture Node Graph Badge */}
          <div className="art-badge-graph">
            <svg viewBox="0 0 72 72" fill="none" className="graph-svg" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="netGrad" x1="0" y1="0" x2="72" y2="72" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#38BDF8" />
                  <stop offset="1" stopColor="#8B5CF6" />
                </linearGradient>
                <filter id="glowFilter" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="2" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* Connecting Lines */}
              <line x1="36" y1="20" x2="52" y2="30" stroke="rgba(99, 102, 241, 0.6)" strokeWidth="1.8" />
              <line x1="52" y1="30" x2="52" y2="48" stroke="rgba(56, 189, 248, 0.6)" strokeWidth="1.8" />
              <line x1="52" y1="48" x2="36" y2="58" stroke="rgba(139, 92, 246, 0.6)" strokeWidth="1.8" />
              <line x1="36" y1="58" x2="20" y2="48" stroke="rgba(99, 102, 241, 0.6)" strokeWidth="1.8" />
              <line x1="20" y1="48" x2="20" y2="30" stroke="rgba(56, 189, 248, 0.6)" strokeWidth="1.8" />
              <line x1="20" y1="30" x2="36" y2="20" stroke="rgba(139, 92, 246, 0.6)" strokeWidth="1.8" />

              {/* Central Hub Links */}
              <line x1="36" y1="38" x2="36" y2="20" stroke="url(#netGrad)" strokeWidth="2" />
              <line x1="36" y1="38" x2="52" y2="30" stroke="url(#netGrad)" strokeWidth="2" />
              <line x1="36" y1="38" x2="52" y2="48" stroke="url(#netGrad)" strokeWidth="2" />
              <line x1="36" y1="38" x2="36" y2="58" stroke="url(#netGrad)" strokeWidth="2" />
              <line x1="36" y1="38" x2="20" y2="48" stroke="url(#netGrad)" strokeWidth="2" />
              <line x1="36" y1="38" x2="20" y2="30" stroke="url(#netGrad)" strokeWidth="2" />

              {/* Outer Nodes */}
              <circle cx="36" cy="20" r="4" fill="#38BDF8" filter="url(#glowFilter)" />
              <circle cx="52" cy="30" r="4" fill="#6366F1" />
              <circle cx="52" cy="48" r="4" fill="#8B5CF6" filter="url(#glowFilter)" />
              <circle cx="36" cy="58" r="4" fill="#38BDF8" />
              <circle cx="20" cy="48" r="4" fill="#6366F1" />
              <circle cx="20" cy="30" r="4" fill="#8B5CF6" />

              {/* Center Core Node */}
              <circle cx="36" cy="38" r="6" fill="#FFFFFF" stroke="#6366F1" strokeWidth="2.5" filter="url(#glowFilter)" />
            </svg>
          </div>

          {/* Floating Code Tag Badge */}
          <div className="art-badge-code">
            <span className="code-tag">&lt;/&gt;</span>
          </div>
        </div>
      </div>
    </div>
  );
}
