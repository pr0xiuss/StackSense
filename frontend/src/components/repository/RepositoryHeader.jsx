import React from 'react';

export default function RepositoryHeader({
  project,
  repository,
  latestIngestionStatus,
}) {
  const status = (latestIngestionStatus || repository?.status || 'Active').toLowerCase();

  const statusClass =
    status === 'completed'
      ? 'status-completed'
      : status === 'processing'
        ? 'status-processing'
        : status === 'failed'
          ? 'status-failed'
          : 'status-active';

  const statusLabel =
    status === 'completed'
      ? 'Completed'
      : status === 'processing'
        ? 'Processing'
        : status === 'failed'
          ? 'Failed'
          : 'Active';

  return (
    <div className="repository-header-card">
      {/* Breadcrumb Navigation */}
      <nav className="repo-breadcrumb" aria-label="Breadcrumb">
        <a href="#/projects" className="breadcrumb-link">Projects</a>
        <span className="breadcrumb-separator" aria-hidden="true">&gt;</span>
        <a href="#/projects" className="breadcrumb-link">
          {project?.name || 'Project'}
        </a>
        <span className="breadcrumb-separator" aria-hidden="true">&gt;</span>
        <span className="breadcrumb-current" aria-current="page">
          {repository?.name || 'Repository'}
        </span>
      </nav>

      {/* Main Repository Info Banner */}
      <div className="repo-banner-main">
        <div className="repo-banner-info">
          <div className="repo-cube-badge blue" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
              <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
              <line x1="12" y1="22.08" x2="12" y2="12" />
            </svg>
          </div>
          <div className="repo-banner-titles">
            <div className="repo-title-row">
              <h1 className="repo-page-title">{repository?.name || 'Repository'}</h1>
              <div className={`repo-status-pill ${statusClass}`}>
                <span className="status-dot" aria-hidden="true" />
                <span>{statusLabel}</span>
              </div>
            </div>
            <p className="repo-page-description">
              {repository?.description || 'Repository registered in StackSense.'}
            </p>
          </div>
        </div>

        {/* Back to Project Button */}
        <div className="repo-banner-actions">
          <a href="#/projects" className="btn-back-project">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            <span>Back to Project</span>
          </a>
        </div>
      </div>
    </div>
  );
}
