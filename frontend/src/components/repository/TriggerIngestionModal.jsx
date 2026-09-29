import React, { useState } from 'react';
import { ingestionService } from '../../services/ingestionService.js';

export default function TriggerIngestionModal({
  isOpen,
  projectId,
  repositoryId,
  onClose,
  onIngestionTriggered,
}) {
  const [sourceReference, setSourceReference] = useState('');
  const [sourceType, setSourceType] = useState('archive');
  const [revisionIdentifier, setRevisionIdentifier] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!sourceReference.trim()) {
      setError('Source reference path or URI is required.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const ingestion = await ingestionService.triggerIngestion(projectId, repositoryId, {
        source_type: sourceType,
        source_reference: sourceReference.trim(),
        revision_identifier: revisionIdentifier.trim() || undefined,
      });
      onIngestionTriggered(ingestion);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to trigger ingestion.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="trigger-title">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-icon blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </div>
          <div>
            <h2 className="modal-title" id="trigger-title">Trigger Ingestion</h2>
            <p className="modal-subtitle">Start an ingestion run from a verified local reference or staging path.</p>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close modal">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="modal-alert-error" role="alert">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label htmlFor="source-type" className="form-label">
              Source Type
            </label>
            <select
              id="source-type"
              className="form-select"
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
              disabled={loading}
            >
              <option value="archive">Archive (.zip file)</option>
              <option value="directory">Local Directory Path</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="source-reference" className="form-label">
              Source Reference Path <span className="required-star">*</span>
            </label>
            <input
              id="source-reference"
              type="text"
              className="form-input"
              value={sourceReference}
              onChange={(e) => setSourceReference(e.target.value)}
              placeholder="e.g. /tmp/repo_source.zip or /var/staged/repo"
              required
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="trigger-revision" className="form-label">
              Revision Identifier <span className="optional-tag">(optional, e.g. v1.2.0)</span>
            </label>
            <input
              id="trigger-revision"
              type="text"
              className="form-input"
              value={revisionIdentifier}
              onChange={(e) => setRevisionIdentifier(e.target.value)}
              placeholder="e.g. main or v1.0.0"
              maxLength={255}
              disabled={loading}
            />
          </div>

          <div className="modal-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-gradient-primary"
              disabled={loading || !sourceReference.trim()}
            >
              {loading ? (
                <>
                  <span className="btn-spinner" aria-hidden="true" />
                  <span>Starting...</span>
                </>
              ) : (
                <span>Trigger Ingestion</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
