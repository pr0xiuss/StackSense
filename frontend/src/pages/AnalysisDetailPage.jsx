import React, { useState, useEffect, useCallback } from 'react';
import DashboardHeader from '../components/dashboard/DashboardHeader.jsx';
import AnalysisHeader from '../components/analysis/AnalysisHeader.jsx';
import AnalysisProgress from '../components/analysis/AnalysisProgress.jsx';
import AnalysisFindings from '../components/analysis/AnalysisFindings.jsx';
import AnalysisExecution from '../components/analysis/AnalysisExecution.jsx';
import { useAnalysisLiveStatus } from '../hooks/useAnalysisLiveStatus.js';
import { useProjectRole } from '../hooks/useProjectRole.js';
import { projectService } from '../services/projectService.js';
import { repositoryService } from '../services/repositoryService.js';
import { analysisService } from '../services/analysisService.js';

export default function AnalysisDetailPage({ projectId, repositoryId, analysisId }) {
  const { canCreateOrUpdate } = useProjectRole(projectId);
  const {
    analysis,
    loading,
    refreshing,
    error,
    errorCode,
    isLive,
    refetch,
  } = useAnalysisLiveStatus(projectId, analysisId);

  const [project, setProject] = useState(null);
  const [repository, setRepository] = useState(null);
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'findings' | 'execution'

  // Cancel Modal state
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState(null);

  // Load project & repository metadata for breadcrumb context
  useEffect(() => {
    let active = true;
    Promise.all([
      projectService.getProject(projectId).catch(() => null),
      repositoryService.getRepository(projectId, repositoryId).catch(() => null),
    ]).then(([projData, repoData]) => {
      if (active) {
        setProject(projData);
        setRepository(repoData);
      }
    });

    return () => {
      active = false;
    };
  }, [projectId, repositoryId]);

  const handleCancelSubmit = async (e) => {
    e.preventDefault();
    if (cancelling) return;

    setCancelling(true);
    setCancelError(null);

    try {
      await analysisService.cancelAnalysis(analysisId, {
        projectId,
        reason: cancelReason || undefined,
      });
      setCancelModalOpen(false);
      setCancelReason('');
      refetch();
    } catch (err) {
      setCancelError(err.message || 'Failed to cancel analysis run.');
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="repository-page-wrapper">
      <DashboardHeader />

      <main className="repository-content container">
        {loading && (
          <div className="repo-loading-screen">
            <span className="btn-spinner" aria-hidden="true" />
            <p>Loading analysis details...</p>
          </div>
        )}

        {!loading && error && (
          <div className="repo-error-screen" role="alert">
            <div className="error-icon-box">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h2>
              {errorCode === 404
                ? 'Analysis Run Not Found'
                : errorCode === 403
                  ? 'Access Denied'
                  : 'Unable to Load Analysis'}
            </h2>
            <p>{error}</p>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
              <button type="button" className="btn-table-view" onClick={refetch}>
                Retry
              </button>
              <a
                href={`#/projects/${projectId}/repositories/${repositoryId}`}
                className="btn-gradient-primary"
              >
                Return to Repository
              </a>
            </div>
          </div>
        )}

        {!loading && !error && analysis && (
          <>
            {/* Header Card */}
            <AnalysisHeader
              project={project}
              repository={repository}
              analysis={analysis}
              isLive={isLive}
              canCancel={canCreateOrUpdate}
              onOpenCancelModal={() => setCancelModalOpen(true)}
              refreshing={refreshing}
              onRefresh={refetch}
            />

            {/* Error or Warning Banner */}
            {(analysis.error_code || analysis.error_message) && (
              <div className="analysis-error-banner" role="alert" style={{ marginBottom: '1.5rem' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, marginTop: '2px' }}>
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <div>
                  <strong>Analysis {analysis.status?.toUpperCase()}: {analysis.error_code || 'Failure'}</strong>
                  <p style={{ marginTop: '0.25rem' }}>{analysis.error_message}</p>
                </div>
              </div>
            )}

            {/* Pipeline Stage Rail & Metrics */}
            <AnalysisProgress analysis={analysis} />

            {/* Tab Navigation */}
            <nav className="repo-tabs-nav" style={{ marginTop: '2rem' }} aria-label="Analysis Details Tabs">
              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
                onClick={() => setActiveTab('overview')}
                aria-selected={activeTab === 'overview'}
                role="tab"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <line x1="3" y1="9" x2="21" y2="9" />
                  <line x1="9" y1="21" x2="9" y2="9" />
                </svg>
                <span>Overview & Config</span>
              </button>

              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'findings' ? 'active' : ''}`}
                onClick={() => setActiveTab('findings')}
                aria-selected={activeTab === 'findings'}
                role="tab"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                <span>Findings & Diagnostics</span>
              </button>

              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'execution' ? 'active' : ''}`}
                onClick={() => setActiveTab('execution')}
                aria-selected={activeTab === 'execution'}
                role="tab"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                </svg>
                <span>Execution Details</span>
              </button>
            </nav>

            {/* Tab Viewport */}
            <div className="repo-tab-viewport" style={{ marginTop: '1.25rem' }}>
              {activeTab === 'overview' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.5rem' }}>
                  {/* Configuration Card */}
                  <div className="analyses-card">
                    <h3 className="tab-card-title">Analysis Configuration</h3>
                    <p className="tab-card-subtitle" style={{ marginBottom: '1.25rem' }}>
                      Scope boundaries, resource limits, and path filters applied to this run.
                    </p>

                    <div className="revision-summary-card">
                      <div className="revision-summary-row">
                        <span className="revision-summary-label">Max File Size</span>
                        <span className="revision-summary-val">
                          {analysis.configuration?.max_file_size_bytes
                            ? `${Math.round(analysis.configuration.max_file_size_bytes / (1024 * 1024))} MiB`
                            : '5 MiB (Default)'}
                        </span>
                      </div>
                      <div className="revision-summary-row">
                        <span className="revision-summary-label">Timeout Limit</span>
                        <span className="revision-summary-val">
                          {analysis.configuration?.timeout_seconds
                            ? `${analysis.configuration.timeout_seconds} seconds`
                            : '1800 seconds (Default)'}
                        </span>
                      </div>
                      <div className="revision-summary-row">
                        <span className="revision-summary-label">Include Paths</span>
                        <span className="revision-summary-val mono-cell">
                          {Array.isArray(analysis.configuration?.include_paths) && analysis.configuration.include_paths.length > 0
                            ? analysis.configuration.include_paths.join(', ')
                            : 'All (Entire revision)'}
                        </span>
                      </div>
                      <div className="revision-summary-row">
                        <span className="revision-summary-label">Exclude Paths</span>
                        <span className="revision-summary-val mono-cell">
                          {Array.isArray(analysis.configuration?.exclude_paths) && analysis.configuration.exclude_paths.length > 0
                            ? analysis.configuration.exclude_paths.join(', ')
                            : 'Default excludes only'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Completeness Card */}
                  <div className="analyses-card">
                    <h3 className="tab-card-title">Inventory Completeness</h3>
                    <p className="tab-card-subtitle" style={{ marginBottom: '1.25rem' }}>
                      File classification and coverage breakdown.
                    </p>

                    <div className="revision-summary-card">
                      <div className="revision-summary-row">
                        <span className="revision-summary-label">Analyzed Files</span>
                        <span className="revision-summary-val">
                          {analysis.completeness?.analyzed_files_count?.toLocaleString() ?? 0}
                        </span>
                      </div>
                      <div className="revision-summary-row">
                        <span className="revision-summary-label">Unsupported Files</span>
                        <span className="revision-summary-val">
                          {analysis.completeness?.unsupported_files_count?.toLocaleString() ?? 0}
                        </span>
                      </div>
                      <div className="revision-summary-row">
                        <span className="revision-summary-label">Failed Files</span>
                        <span className="revision-summary-val">
                          {analysis.completeness?.failed_files_count?.toLocaleString() ?? 0}
                        </span>
                      </div>
                      <div className="revision-summary-row">
                        <span className="revision-summary-label">Excluded Files</span>
                        <span className="revision-summary-val">
                          {analysis.completeness?.excluded_files_count?.toLocaleString() ?? 0}
                        </span>
                      </div>
                      <div className="revision-summary-row">
                        <span className="revision-summary-label">Partial Completion</span>
                        <span className="revision-summary-val">
                          {analysis.completeness?.is_partial ? 'Yes (Partial Scope)' : 'No (Full Coverage)'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'findings' && (
                <AnalysisFindings
                  projectId={projectId}
                  analysisId={analysisId}
                  publishedVersionId={analysis.published_version_id}
                />
              )}

              {activeTab === 'execution' && (
                <AnalysisExecution analysis={analysis} />
              )}
            </div>
          </>
        )}
      </main>

      {/* Cancellation Confirmation Modal */}
      {cancelModalOpen && (
        <div className="analysis-modal-overlay" role="presentation" onClick={(e) => e.target === e.currentTarget && !cancelling && setCancelModalOpen(false)}>
          <div
            className="analysis-modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="cancel-modal-title"
            style={{ maxWidth: '480px' }}
          >
            <div className="analysis-modal-header">
              <h2 id="cancel-modal-title" className="analysis-modal-title">
                Cancel Analysis Run
              </h2>
              <button
                type="button"
                className="analysis-modal-close-btn"
                onClick={() => setCancelModalOpen(false)}
                disabled={cancelling}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleCancelSubmit} className="analysis-modal-body">
              {cancelError && (
                <div className="analysis-error-banner" role="alert">
                  <p>{cancelError}</p>
                </div>
              )}

              <p style={{ fontSize: '0.875rem', color: '#94A3B8' }}>
                Are you sure you want to cancel this analysis run? Any active worker tasks will be interrupted.
              </p>

              <div className="analysis-form-group">
                <label htmlFor="cancel-reason" className="analysis-form-label">
                  Reason for Cancellation (Optional)
                </label>
                <textarea
                  id="cancel-reason"
                  className="analysis-form-textarea"
                  placeholder="e.g. Configuration correction, revision replaced..."
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  disabled={cancelling}
                  maxLength={1000}
                />
              </div>

              <div className="analysis-modal-footer">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setCancelModalOpen(false)}
                  disabled={cancelling}
                >
                  Keep Running
                </button>
                <button
                  type="submit"
                  className="btn-cancel-analysis"
                  disabled={cancelling}
                >
                  {cancelling && <span className="btn-spinner" aria-hidden="true" />}
                  <span>{cancelling ? 'Cancelling...' : 'Confirm Cancellation'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

