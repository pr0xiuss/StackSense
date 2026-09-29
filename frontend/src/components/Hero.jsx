import React from 'react';
import ArchitecturePreview from './ArchitecturePreview.jsx';

export default function Hero() {
  return (
    <section className="hero-section" id="overview" aria-labelledby="hero-title">
      <div className="container hero-grid">
        <div className="hero-content">
          <div className="eyebrow-badge">
            <span className="eyebrow-dot" aria-hidden="true" />
            <span>Turn Code into Clarity</span>
          </div>

          <h1 className="hero-title" id="hero-title">
            Understand any codebase{' '}
            <span className="text-gradient">with confidence.</span>
          </h1>

          <p className="hero-subtitle">
            StackSense helps you see how your software is structured, connected,
            and organized — without tracing everything manually.
          </p>

          <div className="hero-cta-group">
            <a href="#cta" className="btn-primary">
              Get Started
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </a>
            <a href="#how-it-works" className="btn-secondary">
              See How It Works
            </a>
          </div>
        </div>

        <div className="hero-visual">
          <ArchitecturePreview />
        </div>
      </div>
    </section>
  );
}
