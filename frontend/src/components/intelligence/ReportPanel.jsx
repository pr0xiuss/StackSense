import React from 'react';
import { useReportHistory } from '../../hooks/useReportHistory.js';

export function ReportPanel({
  versionId,
  projectId,
}) {
  const {
    collection,
    reportId,
    setReportId,
    summary,
    generationsPage,
    selectedGenerationId,
    selectGeneration,
    loading,
    error,
    cursorIndex,
    hasMoreGenerations,
    nextGenerationsPage,
    prevGenerationsPage,
    downloading,
    downloadError,
    downloadPdf,
    cancelDownload,
    refresh,
  } = useReportHistory(versionId, { projectId });

  if (loading && !summary) {
    return (
      <div className="report-panel-loading" role="status">
        <span className="spinner-dot" />
        <span>Loading architecture report metadata…</span>
      </div>
    );
  }

  if (error && !summary) {
    return (
      <div className="report-panel-error" role="alert">
        <h3>Report Unavailable</h3>
        <p>{error}</p>
        <button type="button" className="btn-retry" onClick={refresh}>
          Retry Loading
        </button>
      </div>
    );
  }

  const isReady = summary?.ready ?? false;
  const activeGenId = summary?.active_generation_id;

  return (
    <div className="intelligence-report-panel" role="region" aria-label="Architecture Reports">
      {/* Report Summary Card */}
      <div className="report-summary-card">
        <div className="report-summary-header">
          <div>
            <span className="report-eyebrow">Executive Architecture Deliverable</span>
            <h3 className="report-title">{summary?.name || 'Automated Architecture Report'}</h3>
            <p className="report-desc">
              Deterministic, comprehensive PDF compilation of system architecture, container boundaries,
              component communication, data flows, cross-boundary integrations, and lexical entity catalog.
            </p>
          </div>

          <div className="report-status-badge-group">
            <span className={`status-pill status-${isReady ? 'succeeded' : 'pending'}`}>
              {isReady ? 'READY FOR EXPORT' : 'PREPARING'}
            </span>
          </div>
        </div>

        {/* Report Metadata */}
        <div className="report-meta-grid">
          <div className="report-meta-item">
            <span className="meta-label">Active Generation:</span>
            <span className="meta-value mono-cell">
              {activeGenId ? activeGenId.slice(0, 10) + '…' : 'None'}
            </span>
          </div>
          {summary?.active_digest && (
            <div className="report-meta-item">
              <span className="meta-label">SHA-256 Digest:</span>
              <span className="meta-value mono-cell" title={summary.active_digest}>
                {summary.active_digest.slice(0, 16)}…
              </span>
            </div>
          )}
          {summary?.page_count && (
            <div className="report-meta-item">
              <span className="meta-label">Pages:</span>
              <span className="meta-value">{summary.page_count}</span>
            </div>
          )}
        </div>

        {/* Primary Download CTA */}
        <div className="report-download-cta-row">
          <button
            type="button"
            className="btn-download-pdf-primary"
            disabled={!isReady || downloading}
            onClick={() => downloadPdf(activeGenId)}
          >
            {downloading ? (
              <>
                <span className="spinner-dot" />
                <span>Downloading & Verifying SHA-256…</span>
              </>
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                <span>Download Verified PDF Report</span>
              </>
            )}
          </button>

          {downloading && (
            <button
              type="button"
              className="btn-cancel-download"
              onClick={cancelDownload}
            >
              Cancel
            </button>
          )}
        </div>

        {downloadError && (
          <div className="report-download-error" role="alert">
            <strong>Download Notice:</strong> {downloadError}
          </div>
        )}
      </div>

      {/* Historical Generations Section */}
      <div className="report-history-section">
        <div className="history-header-row">
          <h4>Generation Publication History</h4>
          <span className="history-count-badge">
            {generationsPage?.items?.length ?? 0} generations recorded
          </span>
        </div>

        {generationsPage && generationsPage.items?.length === 0 && (
          <div className="history-empty-state">
            <p>No historical publication generations recorded for this report.</p>
          </div>
        )}

        {generationsPage && generationsPage.items?.length > 0 && (
          <>
            <div className="history-table-wrapper">
              <table className="report-history-table">
                <thead>
                  <tr>
                    <th>Generation</th>
                    <th>Created At</th>
                    <th>Status</th>
                    <th>Content Digest</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {generationsPage.items.map((gen) => {
                    const isActive = gen.generation_id === activeGenId;
                    const isSelected = gen.generation_id === selectedGenerationId;

                    return (
                      <tr key={gen.generation_id} className={isSelected ? 'selected-row' : ''}>
                        <td>
                          <div className="generation-cell">
                            <span className="mono-cell">{gen.generation_id.slice(0, 10)}…</span>
                            {isActive && <span className="active-pill">ACTIVE</span>}
                          </div>
                        </td>
                        <td>
                          {gen.created_at ? new Date(gen.created_at).toLocaleString() : '—'}
                        </td>
                        <td>
                          <span className={`status-badge status-${(gen.status || 'READY').toLowerCase()}`}>
                            {gen.status || 'READY'}
                          </span>
                        </td>
                        <td>
                          <span className="mono-cell" title={gen.digest}>
                            {gen.digest ? gen.digest.slice(0, 12) + '…' : '—'}
                          </span>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn-table-download"
                            disabled={downloading}
                            onClick={() => downloadPdf(gen.generation_id)}
                            title="Download exact generation PDF"
                          >
                            Download
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="history-pagination-row">
              <button
                type="button"
                className="btn-pagination"
                disabled={cursorIndex === 0 || loading}
                onClick={prevGenerationsPage}
              >
                &larr; Prev Page
              </button>
              <span className="pagination-current-label">
                Page {cursorIndex + 1}
              </span>
              <button
                type="button"
                className="btn-pagination"
                disabled={!hasMoreGenerations || loading}
                onClick={nextGenerationsPage}
              >
                Next Page &rarr;
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
export default ReportPanel;
