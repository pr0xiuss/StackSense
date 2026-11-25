import React from 'react';

/**
 * Intelligence Header component.
 * Displays breadcrumbs, version and snapshot metadata, exact technical links,
 * and accessible primary workspace tabs.
 */
export function IntelligenceHeader({
  project,
  repository,
  analysis,
  version,
  activeTab,
  onTabChange,
}) {
  const projectId = project?.id || project?._id;
  const repositoryId = repository?.id || repository?._id;
  const analysisId = analysis?.id || analysis?._id;
  const versionId = version?.id || version?._id;

  const sequenceNumber = version?.sequence_number || 1;
  const snapshotId = version?.snapshot_id || analysis?.snapshot_id || 'Unavailable';

  const tabs = [
    { id: 'diagrams', label: 'Diagrams' },
    { id: 'search', label: 'Search' },
    { id: 'knowledge', label: 'Knowledge' },
    { id: 'reports', label: 'Reports' },
  ];

  return (
    <header className="intelligence-header">
      <nav aria-label="Breadcrumbs" className="intelligence-breadcrumbs">
        <a href="#/projects">Projects</a>
        <span className="breadcrumb-separator">/</span>
        <a href={`#/projects/${projectId}`}>{project?.name || 'Project'}</a>
        <span className="breadcrumb-separator">/</span>
        <a href={`#/projects/${projectId}/repositories/${repositoryId}`}>
          {repository?.name || 'Repository'}
        </a>
        <span className="breadcrumb-separator">/</span>
        <a
          href={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}`}
        >
          Analysis
        </a>
        <span className="breadcrumb-separator">/</span>
        <span className="breadcrumb-current">
          Architecture v{sequenceNumber}
        </span>
      </nav>

      <div className="intelligence-header-main">
        <div className="intelligence-title-section">
          <h1 className="intelligence-title">
            Repository Intelligence
            <span className="intelligence-badge">v{sequenceNumber}</span>
          </h1>
          <div className="intelligence-meta-strip">
            <span className="meta-item">
              <strong className="meta-label">Version ID:</strong>{' '}
              <span className="meta-value font-mono">{versionId}</span>
            </span>
            <span className="meta-separator">•</span>
            <span className="meta-item">
              <strong className="meta-label">Snapshot:</strong>{' '}
              <span className="meta-value font-mono">{snapshotId}</span>
            </span>
          </div>
        </div>

        <div className="intelligence-technical-links">
          <a
            href={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}`}
            className="btn btn-secondary btn-sm"
            title="View Canonical Architecture Model"
          >
            Canonical Model
          </a>
          <a
            href={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/graph`}
            className="btn btn-secondary btn-sm"
            title="Open Graph Explorer"
          >
            Graph Explorer
          </a>
        </div>
      </div>

      <nav
        className="intelligence-tabs-nav"
        role="tablist"
        aria-label="Intelligence workspace panels"
      >
        {tabs.map((tab) => {
          const isSelected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              role="tab"
              id={`tab-${tab.id}`}
              aria-controls={`panel-${tab.id}`}
              aria-selected={isSelected}
              tabIndex={isSelected ? 0 : -1}
              className={`intelligence-tab-btn ${isSelected ? 'active' : ''}`}
              onClick={() => onTabChange(tab.id)}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>
    </header>
  );
}

