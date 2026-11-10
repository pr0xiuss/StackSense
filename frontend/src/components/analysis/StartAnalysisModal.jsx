import React, { useState, useEffect, useCallback } from 'react';
import { ingestionService } from '../../services/ingestionService.js';
import { analysisService } from '../../services/analysisService.js';

function generateIdempotencyKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'ss-analysis-' + Math.random().toString(36).substring(2, 15) + '-' + Date.now().toString(36);
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  if (!bytes) return '—';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export default function StartAnalysisModal({
  isOpen,
  onClose,
  projectId,
  repositoryId,
  onAnalysisCreated,
}) {
  const [revisions, setRevisions] = useState([]);
  const [loadingRevisions, setLoadingRevisions] = useState(false);
  const [revisionsError, setRevisionsError] = useState(null);

  const [selectedRevisionId, setSelectedRevisionId] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [includePaths, setIncludePaths] = useState('');
  const [excludePaths, setExcludePaths] = useState('');
  const [maxFileSizeMiB, setMaxFileSizeMiB] = useState(5);
  const [timeoutSeconds, setTimeoutSeconds] = useState(1800);
  const [idempotencyKey, setIdempotencyKey] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // Initialize form state when opened
  useEffect(() => {
    if (!isOpen) return;

    setIdempotencyKey(generateIdempotencyKey());
    setSubmitError(null);
    setSubmitting(false);
    setLoadingRevisions(true);
    setRevisionsError(null);

    let active = true;
    ingestionService
      .listRevisions(projectId, repositoryId, 100, 0)
      .then((data) => {
        if (!active) return;
        const list = Array.isArray(data) ? data : [];
        setRevisions(list);
        if (list.length > 0) {
          setSelectedRevisionId(list[0].id);
        } else {
          setSelectedRevisionId('');
        }
      })
      .catch((err) => {
        if (!active) return;
        setRevisionsError(err.message || 'Failed to load repository revisions.');
      })
      .finally(() => {
        if (active) setLoadingRevisions(false);
      });

    return () => {
      active = false;
    };
  }, [isOpen, projectId, repositoryId]);

  // Handle ESC key to dismiss
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !submitting) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, submitting, onClose]);

  const selectedRevision = revisions.find((r) => r.id === selectedRevisionId);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedRevisionId || submitting) return;

    setSubmitting(true);
    setSubmitError(null);

    // Parse path filters
    const parseList = (str) =>
      str
        .split(/[\r\n,]+/)
        .map((s) => s.trim())
        .filter(Boolean);

    const parsedIncludes = parseList(includePaths);
    const parsedExcludes = parseList(excludePaths);

    const miB = Math.min(50, Math.max(1, Number(maxFileSizeMiB) || 5));
    const maxBytes = miB * 1024 * 1024;
    const timeout = Math.min(1800, Math.max(1, Number(timeoutSeconds) || 1800));

    try {
      const result = await analysisService.createAnalysis({
        project_id: projectId,
        repository_id: repositoryId,
        revision_id: selectedRevisionId,
        include_paths: parsedIncludes.length > 0 ? parsedIncludes : undefined,
        exclude_paths: parsedExcludes.length > 0 ? parsedExcludes : undefined,
        max_file_size_bytes: maxBytes,
        timeout_seconds: timeout,
        idempotency_key: idempotencyKey,
      });

      if (onAnalysisCreated) {
        onAnalysisCreated(result);
      }
      onClose();
    } catch (err) {
      // Retain the idempotency key for transport retries
      setSubmitError(err.message || 'Failed to start analysis run.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="analysis-modal-overlay" role="presentation" onClick={(e) => e.target === e.currentTarget && !submitting && onClose()}>
      <div
        className="analysis-modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="start-analysis-title"
      >
        <div className="analysis-modal-header">
          <h2 id="start-analysis-title" className="analysis-modal-title">
            Start Codebase Analysis
          </h2>
          <button
            type="button"
            className="analysis-modal-close-btn"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close modal"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="analysis-modal-body">
          {submitError && (
            <div className="analysis-error-banner" role="alert">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, marginTop: '2px' }}>
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <div>
                <strong>Submission Error:</strong>
                <p style={{ marginTop: '0.2rem' }}>{submitError}</p>
              </div>
            </div>
          )}

          {revisionsError && (
            <div className="analysis-error-banner" role="alert">
              <p>{revisionsError}</p>
            </div>
          )}

          {/* Revision Selection */}
          <div className="analysis-form-group">
            <label htmlFor="select-revision" className="analysis-form-label">
              Source Revision Snapshot *
            </label>
            <p className="analysis-form-hint">
              Select the captured source snapshot to analyze.
            </p>

            {loadingRevisions ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0', color: '#94A3B8' }}>
                <span className="btn-spinner" aria-hidden="true" />
                <span>Loading available revisions...</span>
              </div>
            ) : revisions.length === 0 ? (
              <div className="analyses-empty-box" style={{ padding: '1.5rem', marginTop: '0.5rem' }}>
                <p className="analyses-empty-title">No Captured Revisions Found</p>
                <p className="analyses-empty-desc">
                  You must trigger or upload an ingestion run before an analysis can be launched.
                </p>
              </div>
            ) : (
              <select
                id="select-revision"
                className="analysis-form-select"
                value={selectedRevisionId}
                onChange={(e) => setSelectedRevisionId(e.target.value)}
                disabled={submitting}
                required
              >
                {revisions.map((rev) => (
                  <option key={rev.id} value={rev.id}>
                    {rev.revision_identifier || rev.id.slice(0, 8)} ({rev.total_files} files, {formatBytes(rev.total_bytes)}) — {new Date(rev.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Selected Revision Details Card */}
          {selectedRevision && (
            <div className="revision-summary-card">
              <div className="revision-summary-row">
                <span className="revision-summary-label">Revision Identifier</span>
                <span className="revision-summary-val mono-cell">{selectedRevision.revision_identifier || 'unspecified'}</span>
              </div>
              <div className="revision-summary-row">
                <span className="revision-summary-label">Files & Size</span>
                <span className="revision-summary-val">
                  {selectedRevision.total_files.toLocaleString()} files ({formatBytes(selectedRevision.total_bytes)})
                </span>
              </div>
              <div className="revision-summary-row">
                <span className="revision-summary-label">Source Hash</span>
                <span className="revision-summary-val mono-cell" title={selectedRevision.source_hash}>
                  {selectedRevision.source_hash ? selectedRevision.source_hash.slice(0, 14) + '...' : '—'}
                </span>
              </div>
            </div>
          )}

          {/* Advanced Pipeline Configuration Collapsible */}
          <div style={{ marginTop: '0.5rem' }}>
            <button
              type="button"
              className="collapsible-header-btn"
              onClick={() => setShowAdvanced((prev) => !prev)}
              aria-expanded={showAdvanced}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                style={{
                  transform: showAdvanced ? 'rotate(90deg)' : 'rotate(0deg)',
                  transition: 'transform 150ms ease',
                }}
              >
                <polyline points="9 18 15 12 9 6" />
              </svg>
              <span>{showAdvanced ? 'Hide Advanced Options' : 'Show Advanced Options'}</span>
            </button>

            {showAdvanced && (
              <div className="collapsible-advanced-panel" style={{ marginTop: '0.75rem' }}>
                <div className="analysis-form-group">
                  <label htmlFor="include-paths" className="analysis-form-label">
                    Include Paths (Optional)
                  </label>
                  <p className="analysis-form-hint">
                    Specific subdirectories or glob patterns to analyze (comma or newline separated).
                  </p>
                  <textarea
                    id="include-paths"
                    className="analysis-form-textarea"
                    placeholder="e.g. src/, backend/, packages/core/"
                    value={includePaths}
                    onChange={(e) => setIncludePaths(e.target.value)}
                    disabled={submitting}
                  />
                </div>

                <div className="analysis-form-group">
                  <label htmlFor="exclude-paths" className="analysis-form-label">
                    Exclude Paths (Optional)
                  </label>
                  <p className="analysis-form-hint">
                    Subdirectories or paths to skip (comma or newline separated).
                  </p>
                  <textarea
                    id="exclude-paths"
                    className="analysis-form-textarea"
                    placeholder="e.g. tests/, docs/, vendor/, static/"
                    value={excludePaths}
                    onChange={(e) => setExcludePaths(e.target.value)}
                    disabled={submitting}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div className="analysis-form-group">
                    <label htmlFor="max-file-size" className="analysis-form-label">
                      Max File Size (MiB)
                    </label>
                    <input
                      id="max-file-size"
                      type="number"
                      min="1"
                      max="50"
                      className="analysis-form-input"
                      value={maxFileSizeMiB}
                      onChange={(e) => setMaxFileSizeMiB(e.target.value)}
                      disabled={submitting}
                    />
                    <span className="analysis-form-hint">Between 1 and 50 MiB (default: 5)</span>
                  </div>

                  <div className="analysis-form-group">
                    <label htmlFor="timeout-seconds" className="analysis-form-label">
                      Timeout (seconds)
                    </label>
                    <input
                      id="timeout-seconds"
                      type="number"
                      min="30"
                      max="1800"
                      className="analysis-form-input"
                      value={timeoutSeconds}
                      onChange={(e) => setTimeoutSeconds(e.target.value)}
                      disabled={submitting}
                    />
                    <span className="analysis-form-hint">Max 1800s / 30m (default: 1800)</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="analysis-modal-footer">
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-start-analysis"
              disabled={submitting || !selectedRevisionId || revisions.length === 0}
            >
              {submitting && <span className="btn-spinner" aria-hidden="true" />}
              <span>{submitting ? 'Starting Analysis...' : 'Start Analysis'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

