import React from 'react';

export default function ArchitectureSection() {
  return (
    <section className="arch-section" id="architecture" aria-labelledby="arch-heading">
      <div className="container">
        <div className="section-header">
          <div className="section-label">Architecture Model</div>
          <h2 className="section-title" id="arch-heading">
            See how your code fits together.
          </h2>
          <p className="section-subtitle">
            Explore components, dependencies, APIs, and data stores through an
            architecture model built from the repository.
          </p>
        </div>

        <div className="arch-showcase-box" aria-label="System Architecture Flow">
          <div className="arch-showcase-grid">
            {/* Column 1: Client Interfaces */}
            <div className="arch-col">
              <div className="arch-col-header">Clients</div>
              <div className="arch-box">
                <div className="arch-box-title">Web Client</div>
                <div className="arch-box-meta">React / SPA</div>
              </div>
              <div className="arch-box">
                <div className="arch-box-title">Developer CLI</div>
                <div className="arch-box-meta">Terminal Client</div>
              </div>
            </div>

            {/* Transition Arrow */}
            <div className="arch-arrow-col" aria-hidden="true">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </div>

            {/* Column 2: Gateway & Ingestion */}
            <div className="arch-col">
              <div className="arch-col-header">Routing & Services</div>
              <div className="arch-box">
                <div className="arch-box-title">API Gateway</div>
                <div className="arch-box-meta">FastAPI / /api/v1</div>
              </div>
              <div className="arch-box">
                <div className="arch-box-title">Project Boundary</div>
                <div className="arch-box-meta">Domain Isolation & RBAC</div>
              </div>
              <div className="arch-box">
                <div className="arch-box-title">Ingestion Engine</div>
                <div className="arch-box-meta">Repository Parser & IR</div>
              </div>
            </div>

            {/* Transition Arrow */}
            <div className="arch-arrow-col" aria-hidden="true">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </div>

            {/* Column 3: Storage & External */}
            <div className="arch-col">
              <div className="arch-col-header">Persistence & Ext</div>
              <div className="arch-box">
                <div className="arch-box-title">PostgreSQL</div>
                <div className="arch-box-meta">Verified Metadata & Models</div>
              </div>
              <div className="arch-box">
                <div className="arch-box-title">Redis Store</div>
                <div className="arch-box-meta">State & Job Coordination</div>
              </div>
              <div className="arch-box">
                <div className="arch-box-title">External Systems</div>
                <div className="arch-box-meta">Git Providers & Artifacts</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
