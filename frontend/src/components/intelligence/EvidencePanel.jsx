import React from 'react';

const STRENGTH_LABELS = {
  CONFIRMED_DIRECT: 'Confirmed (Direct)',
  CONFIRMED_INFERRED: 'Confirmed (Inferred)',
  PLAUSIBLE_INFERRED: 'Plausible (Inferred)',
  HEURISTIC: 'Heuristic',
};

export function EvidencePanel({
  evidenceSubject,
  evidencePage,
  evidenceLoading,
  evidenceError,
  evidenceCursorIndex = 0,
  hasMoreEvidence = false,
  onNextPage,
  onPrevPage,
  onClose,
}) {
  if (!evidenceSubject) return null;

  return (
    <aside className="evidence-drawer-overlay" role="dialog" aria-modal="true" aria-label="Evidence Drawer">
      <div className="evidence-drawer-card">
        {/* Drawer Header */}
        <div className="evidence-drawer-header">
          <div>
            <span className="drawer-eyebrow">Evidence Context</span>
            <h3 className="drawer-title">{evidenceSubject.name || 'Subject Evidence'}</h3>
            <span className="drawer-subtitle mono-cell">
              {evidenceSubject.entity_id || evidenceSubject.relationship_id}
            </span>
          </div>
          <button
            type="button"
            className="btn-close-drawer"
            onClick={onClose}
            aria-label="Close evidence drawer"
          >
            &times;
          </button>
        </div>

        {/* Error Notification */}
        {evidenceError && (
          <div className="evidence-error-banner" role="alert">
            {evidenceError}
          </div>
        )}

        {/* Drawer Content */}
        <div className="evidence-drawer-body">
          {evidenceLoading && !evidencePage && (
            <div className="evidence-loading-state" role="status">
              <span className="spinner-dot" />
              <span>Fetching verified coordinate evidence…</span>
            </div>
          )}

          {!evidenceLoading && evidencePage && evidencePage.items?.length === 0 && (
            <div className="evidence-empty-state">
              <p>No verified evidence records located for this subject.</p>
            </div>
          )}

          {evidencePage && evidencePage.items?.length > 0 && (
            <div className="evidence-records-list">
              {evidencePage.items.map((item, idx) => {
                const strengthKey = item.strength || item.confidence_tier || 'HEURISTIC';
                const isOpposing = Boolean(item.is_opposing || item.opposing);

                return (
                  <div
                    key={item.id || idx}
                    className={`evidence-record-card ${isOpposing ? 'opposing-evidence' : ''}`}
                  >
                    <div className="evidence-card-header">
                      <span className={`strength-badge strength-${strengthKey.toLowerCase()}`}>
                        {STRENGTH_LABELS[strengthKey] || strengthKey}
                      </span>

                      {isOpposing && (
                        <span className="opposing-badge" title="Opposing evidence contradicting current model">
                          Opposing Evidence
                        </span>
                      )}

                      {item.extractor_name && (
                        <span className="extractor-tag">{item.extractor_name}</span>
                      )}
                    </div>

                    {item.coordinates && (
                      <div className="evidence-coordinates">
                        <code>{item.coordinates.file_path || item.coordinates.path}</code>
                        {item.coordinates.line_start && (
                          <span> L{item.coordinates.line_start}–L{item.coordinates.line_end || item.coordinates.line_start}</span>
                        )}
                      </div>
                    )}

                    {item.snippet && (
                      <pre className="evidence-snippet">
                        <code>{item.snippet}</code>
                      </pre>
                    )}

                    {item.description && !item.snippet && (
                      <p className="evidence-description">{item.description}</p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Drawer Footer & Pagination */}
        {evidencePage && evidencePage.items?.length > 0 && (
          <div className="evidence-drawer-footer">
            <button
              type="button"
              className="btn-pagination"
              disabled={evidenceCursorIndex === 0 || evidenceLoading}
              onClick={onPrevPage}
            >
              &larr; Prev
            </button>
            <span className="pagination-label">
              Page {evidenceCursorIndex + 1}
            </span>
            <button
              type="button"
              className="btn-pagination"
              disabled={!hasMoreEvidence || evidenceLoading}
              onClick={onNextPage}
            >
              Next &rarr;
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
export default EvidencePanel;
