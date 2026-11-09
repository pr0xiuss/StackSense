import React from 'react';
import {
  getStatusLabel,
  getStatusBadgeClass,
  formatDuration,
} from '../../contracts/analysisContracts.js';

export default function AnalysisHeader({
  project,
  repository,
  analysis,
  isLive,
  canCancel,
  onOpenCancelModal,
  refreshing,
  onRefresh,
}) {
  const shortId = analysis?.id ? analysis.id.slice(0, 8) : '—';
  const status = analysis?.status?.toLowerCase();
  const isCancellable = ['queued', 'running'].includes(status);
  const isCancelRequested = status === 'cancel_requested';
  const hasPublishedModel = Boolean(analysis?.published_version_id);
  const isCompletedWithoutModel = status === 'completed' && !hasPublishedModel;

  return (
    <div className="analysis-header-card">
      {/* Breadcrumb Navigation */}
      <nav className="repo-breadcrumb" aria-label="Analysis Breadcrumb">
        <a href="#/projects" className="breadcrumb-link">
          Projects
        </a>
        <span className="breadcrumb-separator">/</span>
        <a
          href={`#/projects/${analysis?.project_id}/repositories/${analysis?.repository_id}`}
          className="breadcrumb-link"
        >
          {repository?.name || 'Repository'}
        </a>
        <span className="breadcrumb-separator">/</span>
        <span className="breadcrumb-current">Analysis {shortId}</span>
      </nav>

      {/* Main Banner Title & Actions */}
      <div className="analysis-banner-main">
        <div className="analysis-banner-info">
          <div className="analysis-cube-badge">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="12 2 2 7 12 12 22 7 12 2" />
              <polyline points="2 17 12 22 22 17" />
              <polyline points="2 12 12 17 22 12" />
            </svg>
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              <h1 className="analysis-banner-title">Analysis Run {shortId}</h1>
              <span className={`badge-status ${getStatusBadgeClass(status)}`}>
                <span className="badge-status-dot" />
                <span>{getStatusLabel(status)}</span>
              </span>

              {/* Streaming Indicator */}
              {isLive ? (
                <span className="live-indicator-pill live" title="Real-time SSE event stream connected">
                  <span className="pulse-dot" /> Live
                </span>
              ) : isCancellable ? (
                <span className="live-indicator-pill polling" title="Polling for updates">
                  Polling
                </span>
              ) : null}
            </div>

            <p className="analysis-banner-subtitle mono-cell" title={analysis?.id}>
              UUID: {analysis?.id}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="analysis-banner-actions">
          {/* Manual Refresh Button */}
          <button
            type="button"
            className="btn-refresh-icon"
            onClick={onRefresh}
            disabled={refreshing}
            title="Refresh analysis state"
            aria-label="Refresh analysis details"
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className={refreshing ? 'spinning' : ''}
            >
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          </button>

          {/* Cancellation Control */}
          {canCancel && isCancellable && (
            <button
              type="button"
              className="btn-cancel-analysis"
              onClick={onOpenCancelModal}
            >
              Cancel Analysis
            </button>
          )}

          {isCancelRequested && (
            <button type="button" className="btn-cancel-analysis" disabled>
              <span className="btn-spinner" aria-hidden="true" />
              Cancellation Requested…
            </button>
          )}

          {/* Architecture CTA */}
          {hasPublishedModel && (
            <a
              href={`#/projects/${analysis.project_id}/repositories/${analysis.repository_id}/analyses/${analysis.id}/architecture`}
              className="btn-view-architecture"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="7" height="7" />
                <rect x="14" y="3" width="7" height="7" />
                <rect x="14" y="14" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" />
              </svg>
              <span>View Architecture &rarr;</span>
            </a>
          )}

          {isCompletedWithoutModel && (
            <span className="badge-severity-warning" title="Integrity error: completed run has no published model version">
              Model Not Published
            </span>
          )}
        </div>
      </div>

      {/* Metadata Strip */}
      <div className="analysis-meta-strip">
        <div className="analysis-meta-item">
          <span className="analysis-meta-label">Snapshot / Revision</span>
          <span className="analysis-meta-value mono-cell" title={analysis?.snapshot_id}>
            {analysis?.snapshot_id ? analysis.snapshot_id.slice(0, 10) + '...' : '—'}
          </span>
        </div>

        <div className="analysis-meta-item">
          <span className="analysis-meta-label">Created At</span>
          <span className="analysis-meta-value">
            {analysis?.created_at ? new Date(analysis.created_at).toLocaleString() : '—'}
          </span>
        </div>

        <div className="analysis-meta-item">
          <span className="analysis-meta-label">Elapsed Duration</span>
          <span className="analysis-meta-value">
            {formatDuration(analysis?.started_at, analysis?.completed_at)}
          </span>
        </div>

        {analysis?.active_job && (
          <div className="analysis-meta-item">
            <span className="analysis-meta-label">Execution Attempt</span>
            <span className="analysis-meta-value">
              Attempt {analysis.active_job.attempt} of {analysis.active_job.max_attempts}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

