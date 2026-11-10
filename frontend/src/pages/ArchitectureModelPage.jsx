import React, { useState, useEffect, useCallback } from 'react';
import DashboardHeader from '../components/dashboard/DashboardHeader.jsx';
import ArchitectureCanvas from '../components/architecture/ArchitectureCanvas.jsx';
import ArchitectureInspector from '../components/architecture/ArchitectureInspector.jsx';
import ArchitectureCollectionTable from '../components/architecture/ArchitectureCollectionTable.jsx';
import { analysisService } from '../services/analysisService.js';
import { architectureService } from '../services/architectureService.js';
import { projectService } from '../services/projectService.js';
import { repositoryService } from '../services/repositoryService.js';

const OVERVIEW_ENTITY_LIMIT = 100;
const OVERVIEW_RELATIONSHIP_LIMIT = 500;

async function loadOverviewRelationships(versionId, projectId) {
  const items = [];
  let offset = 0;
  let total = 0;
  do {
    const page = await architectureService.listRelationships(versionId, {
      projectId,
      limit: 100,
      offset,
    });
    const pageItems = Array.isArray(page?.items) ? page.items : [];
    total = typeof page?.total === 'number' ? page.total : pageItems.length;
    items.push(...pageItems);
    offset += pageItems.length;
    if (pageItems.length === 0) break;
  } while (offset < total && items.length < OVERVIEW_RELATIONSHIP_LIMIT);
  return items.slice(0, OVERVIEW_RELATIONSHIP_LIMIT);
}

export default function ArchitectureModelPage({ projectId, repositoryId, analysisId }) {
  const [version, setVersion] = useState(null);
  const [project, setProject] = useState(null);
  const [repository, setRepository] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [errorCode, setErrorCode] = useState(null);

  // Tab navigation state: 'overview' | 'entities' | 'relationships' | 'evidence' | 'unresolved' | 'conflicts'
  const [activeTab, setActiveTab] = useState('overview');

  // Overview canvas data (at most 100 loaded for bounded window)
  const [overviewEntities, setOverviewEntities] = useState([]);
  const [overviewRelationships, setOverviewRelationships] = useState([]);
  const [overviewLoading, setOverviewLoading] = useState(false);

  // Selection states
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [selectedEntityForEvidence, setSelectedEntityForEvidence] = useState(null);

  // Load Architecture Version & breadcrumb metadata
  const loadVersion = useCallback(async () => {
    setLoading(true);
    setError(null);
    setErrorCode(null);

    try {
      const [verData, projData, repoData] = await Promise.all([
        analysisService.getAnalysisArchitecture(analysisId, { projectId }),
        projectService.getProject(projectId).catch(() => null),
        repositoryService.getRepository(projectId, repositoryId).catch(() => null),
      ]);

      setVersion(verData);
      setProject(projData);
      setRepository(repoData);

      // Load overview canvas data
      if (verData?.id) {
        setOverviewLoading(true);
        Promise.all([
          architectureService.listEntities(verData.id, {
            projectId,
            limit: OVERVIEW_ENTITY_LIMIT,
            offset: 0,
          }),
          loadOverviewRelationships(verData.id, projectId),
        ])
          .then(([entRes, relRes]) => {
            const entList = Array.isArray(entRes?.items) ? entRes.items : [];
            const relList = Array.isArray(relRes) ? relRes : [];
            setOverviewEntities(entList);
            setOverviewRelationships(relList);
            if (entList.length > 0) {
              setSelectedEntity(entList[0]);
            }
          })
          .catch(() => {
            // Keep empty overview if secondary reads fail
          })
          .finally(() => {
            setOverviewLoading(false);
          });
      }
    } catch (err) {
      setError(err.message || 'Failed to load architecture version.');
      setErrorCode(err.status || err.code || null);
    } finally {
      setLoading(false);
    }
  }, [projectId, repositoryId, analysisId]);

  useEffect(() => {
    loadVersion();
  }, [loadVersion]);

  return (
    <div className="repository-page-wrapper">
      <DashboardHeader />

      <main className="repository-content container">
        {loading && (
          <div className="repo-loading-screen">
            <span className="btn-spinner" aria-hidden="true" />
            <p>Loading architecture model...</p>
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
                ? 'Architecture Version Not Found'
                : errorCode === 403
                  ? 'Access Denied'
                  : 'Unable to Load Model'}
            </h2>
            <p>{error}</p>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
              <button type="button" className="btn-table-view" onClick={loadVersion}>
                Retry
              </button>
              <a
                href={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}`}
                className="btn-gradient-primary"
              >
                Return to Analysis Run
              </a>
            </div>
          </div>
        )}

        {!loading && !error && version && (
          <>
            {/* Header & Summary */}
            <div className="arch-header-card">
              <nav className="repo-breadcrumb" aria-label="Architecture Breadcrumb">
                <a href="#/projects" className="breadcrumb-link">
                  Projects
                </a>
                <span className="breadcrumb-separator">/</span>
                <a
                  href={`#/projects/${projectId}/repositories/${repositoryId}`}
                  className="breadcrumb-link"
                >
                  {repository?.name || 'Repository'}
                </a>
                <span className="breadcrumb-separator">/</span>
                <a
                  href={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}`}
                  className="breadcrumb-link"
                >
                  Analysis Run {analysisId.slice(0, 8)}
                </a>
                <span className="breadcrumb-separator">/</span>
                <span className="breadcrumb-current">Architecture Model</span>
              </nav>

              <div className="arch-banner-main">
                <div className="arch-banner-info">
                  <div className="analysis-cube-badge">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="3" y="3" width="7" height="7" />
                      <rect x="14" y="3" width="7" height="7" />
                      <rect x="14" y="14" width="7" height="7" />
                      <rect x="3" y="14" width="7" height="7" />
                    </svg>
                  </div>

                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                      <h1 className="arch-model-title">
                        Architecture Model v{version.sequence_number || 1}
                      </h1>
                      <span className="badge-status badge-status-completed">
                        <span className="badge-status-dot" />
                        <span>Published</span>
                      </span>
                    </div>

                    <div className="arch-model-subtitle">
                      <span title={version.content_digest} className="mono-cell">
                        Digest: {version.content_digest ? version.content_digest.slice(0, 14) + '...' : '—'}
                      </span>
                      <span>Schema: v{version.architecture_schema_version || '1.0'}</span>
                      <span>
                        Published: {version.published_at ? new Date(version.published_at).toLocaleString() : '—'}
                      </span>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.6rem' }}>
                  <a
                    href={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}`}
                    className="btn-secondary"
                    style={{ textDecoration: 'none' }}
                  >
                    &larr; Back to Run
                  </a>
                </div>
              </div>

              {/* Counts Bar */}
              <div className="arch-counts-bar">
                <div className="arch-count-pill">
                  <span>Entities:</span>
                  <span className="arch-count-num">{version.entity_count ?? 0}</span>
                </div>
                <div className="arch-count-pill">
                  <span>Relationships:</span>
                  <span className="arch-count-num">{version.relationship_count ?? 0}</span>
                </div>
                <div className="arch-count-pill">
                  <span>Evidence:</span>
                  <span className="arch-count-num">{version.evidence_count ?? 0}</span>
                </div>
                <div className="arch-count-pill">
                  <span>Unresolved:</span>
                  <span className="arch-count-num">{version.unresolved_relationship_count ?? 0}</span>
                </div>
                <div className="arch-count-pill">
                  <span>Conflicts:</span>
                  <span className="arch-count-num">{version.conflict_count ?? 0}</span>
                </div>
              </div>
            </div>

            {/* Navigation Tabs */}
            <nav className="repo-tabs-nav" aria-label="Architecture Model Tabs">
              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
                onClick={() => setActiveTab('overview')}
                aria-selected={activeTab === 'overview'}
                role="tab"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="12 2 2 7 12 12 22 7 12 2" />
                  <polyline points="2 17 12 22 22 17" />
                  <polyline points="2 12 12 17 22 12" />
                </svg>
                <span>Overview Map</span>
              </button>

              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'entities' ? 'active' : ''}`}
                onClick={() => setActiveTab('entities')}
                aria-selected={activeTab === 'entities'}
                role="tab"
              >
                <span>Entities ({version.entity_count ?? 0})</span>
              </button>

              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'relationships' ? 'active' : ''}`}
                onClick={() => setActiveTab('relationships')}
                aria-selected={activeTab === 'relationships'}
                role="tab"
              >
                <span>Relationships ({version.relationship_count ?? 0})</span>
              </button>

              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'evidence' ? 'active' : ''}`}
                onClick={() => setActiveTab('evidence')}
                aria-selected={activeTab === 'evidence'}
                role="tab"
              >
                <span>Evidence ({version.evidence_count ?? 0})</span>
              </button>

              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'unresolved' ? 'active' : ''}`}
                onClick={() => setActiveTab('unresolved')}
                aria-selected={activeTab === 'unresolved'}
                role="tab"
              >
                <span>Unresolved ({version.unresolved_relationship_count ?? 0})</span>
              </button>

              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'conflicts' ? 'active' : ''}`}
                onClick={() => setActiveTab('conflicts')}
                aria-selected={activeTab === 'conflicts'}
                role="tab"
              >
                <span>Conflicts ({version.conflict_count ?? 0})</span>
              </button>
            </nav>

            {/* Tab Viewport */}
            <div className="repo-tab-viewport" style={{ marginTop: '1.25rem' }}>
              {activeTab === 'overview' && (
                <div className="arch-overview-split">
                  {overviewLoading ? (
                    <div className="table-loading-wrap" style={{ padding: '4rem 0' }}>
                      <span className="btn-spinner" aria-hidden="true" />
                      <span>Loading map view...</span>
                    </div>
                  ) : (
                    <ArchitectureCanvas
                      entities={overviewEntities}
                      relationships={overviewRelationships}
                      totalEntities={version.entity_count}
                      totalRelationships={version.relationship_count}
                      selectedEntity={selectedEntity}
                      onSelectEntity={setSelectedEntity}
                    />
                  )}

                  <ArchitectureInspector
                    entity={selectedEntity}
                    onViewEvidence={(ent) => {
                      setSelectedEntityForEvidence(ent);
                      setActiveTab('evidence');
                    }}
                  />
                </div>
              )}

              {activeTab !== 'overview' && (
                <ArchitectureCollectionTable
                  type={activeTab}
                  versionId={version.id}
                  projectId={projectId}
                  selectedEntityForEvidence={selectedEntityForEvidence}
                  onSelectEntity={(ent) => {
                    setSelectedEntity(ent);
                    setActiveTab('overview');
                  }}
                  onClearEntityFilter={() => setSelectedEntityForEvidence(null)}
                />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

