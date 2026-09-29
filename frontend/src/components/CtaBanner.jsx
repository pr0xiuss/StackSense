import React from 'react';

export default function CtaBanner() {
  return (
    <section className="cta-section" id="cta" aria-labelledby="cta-heading">
      <div className="container">
        <div className="cta-banner">
          <div className="cta-label">Ready to Explore</div>
          <h2 className="cta-title" id="cta-heading">
            Turn your codebase into clarity.
          </h2>
          <p className="cta-desc">
            Start understanding your software architecture with StackSense.
          </p>
          <a
            href="https://github.com/pr0xiuss/StackSense"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary"
            style={{ padding: '0.75rem 1.75rem', fontSize: '1rem' }}
          >
            Get Started
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </a>
        </div>
      </div>
    </section>
  );
}
