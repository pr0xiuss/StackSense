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
        </div>
      </div>
    </section>
  );
}
