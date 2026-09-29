import React, { useState } from 'react';

/**
 * Format relative time
 */
function formatRelativeTime(dateString) {
  if (!dateString) return '—';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

function formatFullDateTime(dateString) {
  if (!dateString) return '—';
  return new Date(dateString).toLocaleString();
}

export default function IngestionTab({
  ingestions,
  loading,
  error,
  onOpenUpload,
  onOpenTrigger,
  onSelectIngestion,
  selectedIngestion,
}) {
  const [filterActive, setFilterActive] = useState(false);
  const [selectedStatusFilter, setSelectedStatusFilter] = useState('ALL');
  const [copiedId, setCopiedId] = useState(false);

  // Latest ingestion is the first in the list if available
  const latestIngestion = ingestions && ingestions.length > 0 ? ingestions[0] : null;
  const activeDetail = selectedIngestion || latestIngestion;

  const currentStatus = (latestIngestion?.status || 'IDLE').toUpperCase();
  const isCompleted = currentStatus === 'COMPLETED';
  const isProcessing = currentStatus === 'PROCESSING';
  const isFailed = currentStatus === 'FAILED';

  const statusClass = isCompleted
    ? 'status-completed'
    : isProcessing
      ? 'status-processing'
      : isFailed
        ? 'status-failed'
        : 'status-active';

  const statusTitle = isCompleted
    ? 'Completed'
    : isProcessing
      ? 'Processing'
      : isFailed
        ? 'Failed'
        : 'Idle / Ready';

  const statusSubtitle = isCompleted
    ? 'Ingestion finished successfully.'
    : isProcessing
      ? 'Ingestion pipeline in progress...'
      : isFailed
        ? (latestIngestion?.error_message || 'Ingestion encountered an error.')
        : 'No ingestion job run yet.';

  const filteredIngestions = ingestions.filter((item) => {
    if (selectedStatusFilter === 'ALL') return true;
    return (item.status || '').toUpperCase() === selectedStatusFilter;
  });

  const handleCopyId = (id) => {
    if (!id) return;
    navigator.clipboard?.writeText(id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  return (
    <div className="ingestion-tab-content">
      {/* 1. Current Ingestion Status Card */}
      <div className={`current-status-card ${statusClass}`}>
        <div className="status-main-col">
          <div className="status-avatar-wrap">
            {isCompleted && (
              <div className="status-large-icon completed" aria-label="Completed">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
            )}
            {isProcessing && (
              <div className="status-large-icon processing" aria-label="Processing">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="spin-icon">
                  <line x1="12" y1="2" x2="12" y2="6" />
                  <line x1="12" y1="18" x2="12" y2="22" />
                  <line x1="4.93" y1="4.93" x2="7.76" y2="7.76" />
                  <line x1="16.24" y1="16.24" x2="19.07" y2="19.07" />
                  <line x1="2" y1="12" x2="6" y2="12" />
                  <line x1="18" y1="12" x2="22" y2="12" />
                  <line x1="4.93" y1="19.07" x2="7.76" y2="16.24" />
                  <line x1="16.24" y1="7.76" x2="19.07" y2="4.93" />
                </svg>
              </div>
            )}
            {isFailed && (
              <div className="status-large-icon failed" aria-label="Failed">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </div>
            )}
            {!isCompleted && !isProcessing && !isFailed && (
              <div className="status-large-icon idle" aria-label="Idle">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
            )}
          </div>

          <div className="status-text-content">
            <span className="status-eyebrow">Current Ingestion Status</span>
            <h2 className="status-title">{statusTitle}</h2>
            <p className="status-subtitle">{statusSubtitle}</p>

            {/* Metadata strip */}
            {latestIngestion && (
              <div className="status-metadata-strip">
                <div className="meta-item">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                    <line x1="16" y1="2" x2="16" y2="6" />
                    <line x1="8" y1="2" x2="8" y2="6" />
                    <line x1="3" y1="10" x2="21" y2="10" />
                  </svg>
                  <span className="meta-label">Started:</span>
                  <span className="meta-value">
                    {formatRelativeTime(latestIngestion.started_at || latestIngestion.created_at)}
                  </span>
                </div>

                <div className="meta-item">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                  <span className="meta-label">Completed:</span>
                  <span className="meta-value">
                    {latestIngestion.completed_at ? formatRelativeTime(latestIngestion.completed_at) : '—'}
                  </span>
                </div>

                <div className="meta-item">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                  <span className="meta-label">Source:</span>
                  <span className="meta-value">
                    {latestIngestion.source_type === 'archive' ? 'Archive Upload' : latestIngestion.source_type}
                  </span>
                </div>

                <div className="meta-item">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
                    <line x1="7" y1="7" x2="7.01" y2="7" />
                  </svg>
                  <span className="meta-label">Revision:</span>
                  <span className="meta-value">
                    {latestIngestion.revision_identifier || '—'}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Action Trigger Buttons */}
        <div className="status-actions-col">
          <button
            type="button"
            className="btn-trigger-primary"
            onClick={onOpenTrigger}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            <span>Trigger New Ingestion</span>
          </button>

          <button
            type="button"
            className="btn-upload-secondary"
            onClick={onOpenUpload}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <span>Upload Archive</span>
          </button>
        </div>
      </div>

      {/* 2. Ingestion History Table Card */}
      <div className="ingestion-history-card">
        <div className="history-header">
          <h3 className="history-title">Ingestion History</h3>
          <div className="history-controls">
            <button
              type="button"
              className={`btn-filter ${filterActive ? 'active' : ''}`}
              onClick={() => setFilterActive(!filterActive)}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
              </svg>
              <span>Filter</span>
            </button>

            {filterActive && (
              <select
                className="filter-select"
                value={selectedStatusFilter}
                onChange={(e) => setSelectedStatusFilter(e.target.value)}
              >
                <option value="ALL">All Statuses</option>
                <option value="COMPLETED">Completed</option>
                <option value="PROCESSING">Processing</option>
                <option value="FAILED">Failed</option>
              </select>
            )}
          </div>
        </div>

        {loading && (
          <div className="table-loading-wrap">
            <span className="btn-spinner" aria-hidden="true" />
            <span>Loading ingestion records...</span>
          </div>
        )}

        {error && (
          <div className="table-error-wrap">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && filteredIngestions.length === 0 && (
          <div className="table-empty-wrap">
            <p>No ingestion jobs recorded yet.</p>
            <button type="button" className="btn-link-action" onClick={onOpenUpload}>
              + Upload an archive to run first ingestion
            </button>
          </div>
        )}

        {!loading && !error && filteredIngestions.length > 0 && (
          <div className="history-table-wrapper">
            <table className="history-table">
              <thead>
                <tr>
                  <th scope="col">ID</th>
                  <th scope="col">Status</th>
                  <th scope="col">Started</th>
                  <th scope="col">Completed</th>
                  <th scope="col">Source</th>
                  <th scope="col">Revision</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredIngestions.map((item) => {
                  const itemStatus = (item.status || 'Active').toLowerCase();
                  const rowStatusClass =
                    itemStatus === 'completed'
                      ? 'status-completed'
                      : itemStatus === 'processing'
                        ? 'status-processing'
                        : itemStatus === 'failed'
                          ? 'status-failed'
                          : 'status-active';

                  const itemStatusText =
                    itemStatus.charAt(0).toUpperCase() + itemStatus.slice(1);

                  const isSelected = activeDetail?.id === item.id;

                  return (
                    <tr key={item.id} className={`history-row ${isSelected ? 'row-selected' : ''}`}>
                      <td className="cell-id">
                        <span className="mono-text" title={item.id}>
                          {item.id.slice(0, 8)}
                        </span>
                      </td>
                      <td className="cell-status">
                        <div className="status-indicator">
                          <span className={`status-dot ${rowStatusClass}`} aria-hidden="true" />
                          <span className="status-text">{itemStatusText}</span>
                        </div>
                      </td>
                      <td className="cell-time">
                        <span>{formatRelativeTime(item.started_at || item.created_at)}</span>
                      </td>
                      <td className="cell-time">
                        <span>{item.completed_at ? formatRelativeTime(item.completed_at) : '—'}</span>
                      </td>
                      <td className="cell-source">
                        <span>{item.source_type === 'archive' ? 'Archive Upload' : item.source_type}</span>
                      </td>
                      <td className="cell-revision">
                        <span className="mono-text">{item.revision_identifier || '—'}</span>
                      </td>
                      <td className="cell-actions">
                        <button
                          type="button"
                          className={`btn-table-view ${isSelected ? 'active' : ''}`}
                          onClick={() => onSelectIngestion(item)}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="history-footer">
          <span className="footer-count">
            Showing {filteredIngestions.length} {filteredIngestions.length === 1 ? 'ingestion' : 'ingestions'}
          </span>
        </div>
      </div>

      {/* 3. Bottom 2-Column Grid: Ingestion Logs & Ingestion Details */}
      <div className="bottom-detail-grid">
        {/* Left Column: Recent Ingestion Logs */}
        <div className="detail-panel-card logs-panel">
          <div className="panel-header">
            <h3 className="panel-title">Recent Ingestion Logs</h3>
          </div>
          <div className="logs-terminal-viewport">
            <div className="logs-empty-message">
              <p>No execution logs streamed for this ingestion job.</p>
              <span className="logs-notice-sub">
                Ingestion status: {activeDetail ? (activeDetail.status || '').toUpperCase() : 'NO JOB SELECTED'}
              </span>
            </div>
          </div>
        </div>

        {/* Right Column: Ingestion Details */}
        <div className="detail-panel-card details-panel">
          <div className="panel-header">
            <h3 className="panel-title">Ingestion Details</h3>
            {activeDetail && (
              <button
                type="button"
                className="btn-copy-id"
                onClick={() => handleCopyId(activeDetail.id)}
                title="Copy full Ingestion UUID"
              >
                {copiedId ? 'Copied' : 'Copy ID'}
              </button>
            )}
          </div>

          {activeDetail ? (
            <div className="details-list">
              <div className="detail-row">
                <span className="detail-label">Ingestion ID</span>
                <span className="detail-value mono" title={activeDetail.id}>
                  {activeDetail.id}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Status</span>
                <div className="detail-value status-val">
                  <span
                    className={`status-dot ${(activeDetail.status || '').toLowerCase() === 'completed' ? 'status-completed' : (activeDetail.status || '').toLowerCase() === 'failed' ? 'status-failed' : 'status-processing'}`}
                  />
                  <span>
                    {(activeDetail.status || '').charAt(0).toUpperCase() +
                      (activeDetail.status || '').slice(1).toLowerCase()}
                  </span>
                </div>
              </div>
              <div className="detail-row">
                <span className="detail-label">Started At</span>
                <span className="detail-value">
                  {formatFullDateTime(activeDetail.started_at || activeDetail.created_at)}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Completed At</span>
                <span className="detail-value">
                  {activeDetail.completed_at ? formatFullDateTime(activeDetail.completed_at) : '—'}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Source</span>
                <span className="detail-value">
                  {activeDetail.source_type === 'archive'
                    ? 'Archive Upload'
                    : activeDetail.source_type}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Revision Identifier</span>
                <span className="detail-value mono">
                  {activeDetail.revision_identifier || '—'}
                </span>
              </div>
              {activeDetail.error_message && (
                <div className="detail-row error-row">
                  <span className="detail-label">Error Details</span>
                  <span className="detail-value error-text">
                    {activeDetail.error_code ? `[${activeDetail.error_code}] ` : ''}
                    {activeDetail.error_message}
                  </span>
                </div>
              )}
            </div>
          ) : (
            <div className="details-empty">
              <p>No ingestion selected.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
