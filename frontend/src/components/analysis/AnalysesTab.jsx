import React, { useState, useEffect, useCallback } from 'react';
import { analysisService } from '../../services/analysisService.js';
import { useProjectRole } from '../../hooks/useProjectRole.js';
import {
  ANALYSIS_STATUS,
  getStatusLabel,
  getStatusBadgeClass,
  formatDuration,
} from '../../contracts/analysisContracts.js';
import StartAnalysisModal from './StartAnalysisModal.jsx';

export default function AnalysesTab({ projectId, repositoryId }) {
  const { role, canCreateOrUpdate, loading: roleLoading } = useProjectRole(projectId);

  const [analyses, setAnalyses] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const [isStartModalOpen, setIsStartModalOpen] = useState(false);

  const limit = 20;

  const loadAnalyses = useCallback(
    async (nextOffset = 0, isManualRefresh = false) => {
      if (isManualRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      try {
        const data = await analysisService.listAnalyses({
          projectId,
          repositoryId,
          limit,
          offset: nextOffset,
          status: statusFilter || undefined,
        });

        const items = Array.isArray(data?.items) ? data.items : [];
        setAnalyses(items);
        setTotal(typeof data?.total === 'number' ? data.total : items.length);
        setOffset(nextOffset);
      } catch (err) {
        setError(err.message || 'Failed to load analysis runs.');
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [projectId, repositoryId, limit, statusFilter]
  );

  useEffect(() => {
    setOffset(0);
    loadAnalyses(0, false);
  }, [loadAnalyses]);

  const handleStatusFilterChange = (e) => {
    setStatusFilter(e.target.value);
  };

  const handleAnalysisCreated = (newAnalysis) => {
    if (!newAnalysis) return;
    // Prepend newly created run if on the first page
    if (offset === 0) {
      setAnalyses((prev) => [newAnalysis, ...prev.filter((a) => a.id !== newAnalysis.id)].slice(0, limit));
      setTotal((t) => t + 1);
    } else {
      // Return to first page
      loadAnalyses(0, false);
    }
  };

  const hasNextPage = offset + limit < total;
  const hasPrevPage = offset > 0;

  return (
    <div className="analyses-tab-content">
      <div className="analyses-card">
        {/* Header with Title and Start/Role Controls */}
        <div className="analyses-tab-header">
          <div className="analyses-tab-titles">
            <h3 className="analyses-card-title">Codebase Analysis Runs</h3>
            <p className="analyses-card-subtitle">
              Syntax parsing, intermediate representation (IR), and architecture model derivation.
            </p>
          </div>

          <div className="analyses-header-actions">
            {roleLoading ? (
              <span className="btn-spinner" aria-hidden="true" />
            ) : canCreateOrUpdate ? (
              <button
                type="button"
                className="btn-start-analysis"
                onClick={() => setIsStartModalOpen(true)}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                <span>Start Analysis</span>
              </button>
            ) : role === 'VIEWER' ? (
              <span className="role-readonly-pill" title="Viewers have read-only access">
                Read-only (Viewer)
              </span>
            ) : null}
          </div>
        </div>

        {/* Filter and Refresh Bar */}
        <div className="analyses-controls-bar">
          <div className="analyses-filters-group">
            <label htmlFor="analyses-status-filter" className="analyses-filter-label">
              Status:
            </label>
            <select
              id="analyses-status-filter"
              className="analyses-select-filter"
              value={statusFilter}
              onChange={handleStatusFilterChange}
            >
              <option value="">All Statuses</option>
              <option value={ANALYSIS_STATUS.COMPLETED}>Completed</option>
              <option value={ANALYSIS_STATUS.RUNNING}>Running</option>
              <option value={ANALYSIS_STATUS.QUEUED}>Queued</option>
              <option value={ANALYSIS_STATUS.FAILED}>Failed</option>
              <option value={ANALYSIS_STATUS.COMPLETED_WITH_WARNINGS}>Completed with Warnings</option>
              <option value={ANALYSIS_STATUS.PARTIAL}>Partial</option>
              <option value={ANALYSIS_STATUS.CANCELLED}>Cancelled</option>
            </select>
          </div>

          <button
            type="button"
            className="btn-refresh-icon"
            onClick={() => loadAnalyses(offset, true)}
            disabled={loading || refreshing}
            title="Refresh runs"
            aria-label="Refresh analysis runs"
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
        </div>

        {/* Loading State */}
        {loading && (
          <div className="table-loading-wrap" style={{ padding: '2.5rem 0' }}>
            <span className="btn-spinner" aria-hidden="true" />
            <span>Loading analysis runs...</span>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="table-error-wrap" role="alert" style={{ margin: '1rem 0' }}>
            <p>{error}</p>
            <button
              type="button"
              className="btn-table-view"
              onClick={() => loadAnalyses(offset, false)}
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty States */}
        {!loading && !error && analyses.length === 0 && (
          <div className="analyses-empty-box">
            <svg
              width="36"
              height="36"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="analyses-empty-icon"
            >
              <polygon points="12 2 2 7 12 12 22 7 12 2" />
              <polyline points="2 17 12 22 22 17" />
              <polyline points="2 12 12 17 22 12" />
            </svg>
            {statusFilter ? (
              <>
                <p className="analyses-empty-title">No matching runs found</p>
                <p className="analyses-empty-desc">
                  No analysis runs match the status filter "{statusFilter}".
                </p>
                <button
                  type="button"
                  className="btn-table-view"
                  onClick={() => setStatusFilter('')}
                >
                  Clear Status Filter
                </button>
              </>
            ) : (
              <>
                <p className="analyses-empty-title">No analysis runs yet</p>
                <p className="analyses-empty-desc">
                  Run an analysis on an immutable repository revision to discover services, dependencies, and architecture.
                </p>
                {canCreateOrUpdate && (
                  <button
                    type="button"
                    className="btn-start-analysis"
                    onClick={() => setIsStartModalOpen(true)}
                  >
                    Start Your First Analysis
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {/* Analysis Runs Table */}
        {!loading && !error && analyses.length > 0 && (
          <div className="analyses-table-container">
            <table className="analyses-table">
              <thead>
                <tr>
                  <th scope="col">Status</th>
                  <th scope="col">Snapshot / Revision</th>
                  <th scope="col">Created</th>
                  <th scope="col">Duration</th>
                  <th scope="col">Architecture Model</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {analyses.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <span className={`badge-status ${getStatusBadgeClass(item.status)}`}>
                        <span className="badge-status-dot" />
                        <span>{getStatusLabel(item.status)}</span>
                      </span>
                    </td>
                    <td className="mono-cell">
                      <span title={item.snapshot_id || item.repository_id}>
                        {(item.snapshot_id || item.id).slice(0, 10)}...
                      </span>
                    </td>
                    <td>
                      {item.created_at ? new Date(item.created_at).toLocaleString() : '—'}
                    </td>
                    <td>{formatDuration(item.started_at, item.completed_at)}</td>
                    <td>
                      {item.published_version_id ? (
                        <a
                          href={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${item.id}/architecture`}
                          className="model-link-badge"
                          title="View published architecture version"
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect x="3" y="3" width="7" height="7" />
                            <rect x="14" y="3" width="7" height="7" />
                            <rect x="14" y="14" width="7" height="7" />
                            <rect x="3" y="14" width="7" height="7" />
                          </svg>
                          <span>Model v{item.published_version_id.slice(0, 8)} &rarr;</span>
                        </a>
                      ) : (
                        <span style={{ color: '#64748B' }}>—</span>
                      )}
                    </td>
                    <td>
                      <a
                        href={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${item.id}`}
                        className="btn-table-view"
                      >
                        View Details &rarr;
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {!loading && !error && analyses.length > 0 && (
          <div className="history-footer" style={{ marginTop: '1rem' }}>
            <span className="footer-count">
              Showing {offset + 1}&ndash;{offset + analyses.length} of {total} runs
            </span>
            <div className="repo-pagination-controls" aria-label="Analyses pagination">
              <button
                type="button"
                className="repo-pagination-btn"
                onClick={() => loadAnalyses(Math.max(0, offset - limit), false)}
                disabled={!hasPrevPage || loading}
              >
                Previous
              </button>
              <button
                type="button"
                className="repo-pagination-btn"
                onClick={() => loadAnalyses(offset + limit, false)}
                disabled={!hasNextPage || loading}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Start Analysis Modal */}
      <StartAnalysisModal
        isOpen={isStartModalOpen}
        onClose={() => setIsStartModalOpen(false)}
        projectId={projectId}
        repositoryId={repositoryId}
        onAnalysisCreated={handleAnalysisCreated}
      />
    </div>
  );
}

