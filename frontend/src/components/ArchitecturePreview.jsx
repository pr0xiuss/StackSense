import React from 'react';

export default function ArchitecturePreview() {
  return (
    <div className="arch-preview-wrapper" aria-label="Visual Architecture Model Diagram">
      <div className="arch-preview-glow" aria-hidden="true" />
      
      <div className="arch-window">
        {/* Window Chrome Header */}
        <div className="window-header">
          <div className="window-controls" aria-hidden="true">
            <span className="window-dot red" />
            <span className="window-dot yellow" />
            <span className="window-dot green" />
          </div>
          <div className="window-title">
            <span className="window-status" aria-hidden="true" />
            <span>architecture_model.ir — verified</span>
          </div>
          <div style={{ width: '40px' }} aria-hidden="true" />
        </div>

        {/* Visual Architecture Canvas */}
        <div className="window-canvas">
          {/* Tier 1: Client Layer */}
          <div className="arch-tier">
            <div className="arch-node node-client">
              <span className="arch-node-name">Client App</span>
              <span className="arch-node-tech">React / Web</span>
            </div>
          </div>

          {/* Connector Down */}
          <div className="arch-connector-v" aria-hidden="true" />

          {/* Tier 2: API Gateway Layer */}
          <div className="arch-tier">
            <div className="arch-node node-gateway">
              <span className="arch-node-name">API Gateway</span>
              <span className="arch-node-tech">FastAPI / REST</span>
            </div>
          </div>

          {/* Branching Bus to Services */}
          <div className="arch-connector-bus" aria-hidden="true">
            <div className="arch-bus-stem" />
          </div>

          {/* Tier 3: Core Domain Services */}
          <div className="arch-tier">
            <div className="arch-node node-service">
              <span className="arch-node-name">Auth Service</span>
              <span className="arch-node-tech">JWT / Roles</span>
            </div>
            <div className="arch-node node-service">
              <span className="arch-node-name">User Service</span>
              <span className="arch-node-tech">Identity Domain</span>
            </div>
            <div className="arch-node node-service">
              <span className="arch-node-name">Product Service</span>
              <span className="arch-node-tech">Catalog Domain</span>
            </div>
          </div>

          {/* Converging Bus to Data Tier */}
          <div className="arch-connector-bus inverted" aria-hidden="true">
            <div className="arch-bus-stem down" />
          </div>

          {/* Tier 4: Data & External Infrastructure */}
          <div className="arch-tier">
            <div className="arch-node node-db">
              <span className="arch-node-name">PostgreSQL</span>
              <span className="arch-node-tech">Relational DB</span>
            </div>
            <div className="arch-node node-cache">
              <span className="arch-node-name">Redis</span>
              <span className="arch-node-tech">Key-Value Cache</span>
            </div>
            <div className="arch-node node-ext">
              <span className="arch-node-name">External API</span>
              <span className="arch-node-tech">Third-Party Gateway</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
