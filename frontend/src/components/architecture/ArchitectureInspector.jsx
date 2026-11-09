import React from 'react';
import {
  getEntityKindLabel,
} from '../../contracts/architectureContracts.js';

export default function ArchitectureInspector({ entity, onViewEvidence }) {
  if (!entity) {
    return (
      <div className="arch-inspector-panel">
        <h3 className="tab-card-title" style={{ fontSize: '1rem' }}>
          Entity Inspector
        </h3>
        <div className="analyses-empty-box" style={{ padding: '2rem 1rem' }}>
          <svg
            width="32"
            height="32"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            style={{ color: '#64748B', margin: '0 auto 0.75rem' }}
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <p className="analyses-empty-title" style={{ fontSize: '0.9rem' }}>
            No Entity Selected
          </p>
          <p className="analyses-empty-desc" style={{ fontSize: '0.8rem', margin: 0 }}>
            Click an entity node on the canvas or select a row from the Entities tab to inspect its properties.
          </p>
        </div>
      </div>
    );
  }

  const metadata = entity.metadata && typeof entity.metadata === 'object' ? entity.metadata : {};
  const metaKeys = Object.keys(metadata);
  const evidenceCount = Array.isArray(entity.evidence_ids) ? entity.evidence_ids.length : 0;
  const sourceIrCount = Array.isArray(entity.source_ir_keys) ? entity.source_ir_keys.length : 0;

  // Format namespace
  const namespaceStr = Array.isArray(entity.namespace)
    ? entity.namespace.join(' / ')
    : typeof entity.namespace === 'string'
      ? entity.namespace
      : 'Root';

  return (
    <div className="arch-inspector-panel" aria-live="polite">
      {/* Header */}
      <div className="arch-inspector-header">
        <span className="arch-inspector-section-label">Selected Entity</span>
        <h3 className="arch-inspector-title">{entity.name || entity.logical_id}</h3>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.35rem' }}>
          <span className="badge-status badge-status-default">
            {getEntityKindLabel(entity.kind)}
          </span>
          <span className="badge-status badge-status-completed">
            {entity.status || 'Active'}
          </span>
        </div>
      </div>

      {/* Logical ID & Namespace */}
      <div className="arch-inspector-section">
        <span className="arch-inspector-section-label">Logical Identifier</span>
        <span className="mono-cell" style={{ wordBreak: 'break-all', fontSize: '0.8rem' }} title={entity.logical_id}>
          {entity.logical_id}
        </span>
      </div>

      <div className="arch-inspector-section">
        <span className="arch-inspector-section-label">Namespace</span>
        <span style={{ fontSize: '0.85rem', color: '#F8FAFC' }}>{namespaceStr}</span>
      </div>

      {/* Evidence Section */}
      <div className="arch-inspector-section">
        <span className="arch-inspector-section-label">Supporting Evidence</span>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.85rem', color: '#F8FAFC' }}>
            {evidenceCount} source records
          </span>
          {evidenceCount > 0 && onViewEvidence && (
            <button
              type="button"
              className="btn-table-view"
              style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
              onClick={() => onViewEvidence(entity)}
            >
              View Evidence &rarr;
            </button>
          )}
        </div>
      </div>

      {/* Source IR Keys */}
      <div className="arch-inspector-section">
        <span className="arch-inspector-section-label">Source IR Nodes</span>
        <span style={{ fontSize: '0.85rem', color: '#94A3B8' }}>
          {sourceIrCount > 0 ? `${sourceIrCount} parsed IR elements` : 'Directly derived'}
        </span>
      </div>

      {/* Safe Metadata Key-Value List */}
      <div className="arch-inspector-section">
        <span className="arch-inspector-section-label">Metadata Attributes</span>
        {metaKeys.length === 0 ? (
          <span style={{ fontSize: '0.8rem', color: '#64748B' }}>No extra attributes</span>
        ) : (
          <div className="arch-metadata-box">
            {metaKeys.map((key) => {
              const val = metadata[key];
              const displayVal =
                val === null || val === undefined
                  ? 'null'
                  : typeof val === 'object'
                    ? JSON.stringify(val)
                    : String(val);

              return (
                <div key={key} className="arch-metadata-row">
                  <span className="arch-metadata-key">{key}</span>
                  <span className="arch-metadata-value" title={displayVal}>
                    {displayVal}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

