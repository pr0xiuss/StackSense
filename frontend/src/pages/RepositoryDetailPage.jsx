import React, { useState, useEffect, useCallback } from 'react';
import DashboardHeader from '../components/dashboard/DashboardHeader.jsx';
import RepositoryHeader from '../components/repository/RepositoryHeader.jsx';
import IngestionTab from '../components/repository/IngestionTab.jsx';
import RevisionsTab from '../components/repository/RevisionsTab.jsx';
import ArtifactsTab from '../components/repository/ArtifactsTab.jsx';
import NewIngestionModal from '../components/repository/NewIngestionModal.jsx';
import UploadArchiveModal from '../components/repository/UploadArchiveModal.jsx';
import TriggerIngestionModal from '../components/repository/TriggerIngestionModal.jsx';
import MetadataEditModal from '../components/common/MetadataEditModal.jsx';
import DeleteRepositoryModal from '../components/dashboard/DeleteRepositoryModal.jsx';
import { projectService } from '../services/projectService.js';
import { repositoryService } from '../services/repositoryService.js';
import { ingestionService } from '../services/ingestionService.js';
import { useProjectRole } from '../hooks/useProjectRole.js';

export default function RepositoryDetailPage({ projectId, repositoryId }) {
  const { canCreateOrUpdate, canDelete } = useProjectRole(projectId);
  const [project, setProject] = useState(null);
  const [repository, setRepository] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [errorCode, setErrorCode] = useState(null);

  // Tab navigation state: 'ingestion' | 'revisions' | 'artifacts'
  const [activeTab, setActiveTab] = useState('ingestion');

  // Ingestion data
  const [ingestions, setIngestions] = useState([]);
  const [loadingIngestions, setLoadingIngestions] = useState(false);
  const [ingestionError, setIngestionError] = useState(null);
  const [selectedIngestion, setSelectedIngestion] = useState(null);
  const [ingestionOffset, setIngestionOffset] = useState(0);
  const [ingestionsHasMore, setIngestionsHasMore] = useState(false);

  // Artifacts tab revision selection state
  const [selectedRevisionForArtifacts, setSelectedRevisionForArtifacts] = useState(null);

  // Modals state
  const [newIngestionModalOpen, setNewIngestionModalOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);
  const [editRepositoryOpen, setEditRepositoryOpen] = useState(false);
  const [deleteRepositoryOpen, setDeleteRepositoryOpen] = useState(false);
  const [mutationFeedback, setMutationFeedback] = useState(null);

  // Load project & repository metadata
  const loadMetadata = useCallback(async () => {
    setLoading(true);
    setError(null);
    setErrorCode(null);

    try {
      const [projData, repoData] = await Promise.all([
        projectService.getProject(projectId),
        repositoryService.getRepository(projectId, repositoryId),
      ]);
      setProject(projData);
      setRepository(repoData);
    } catch (err) {
      setError(err.message || 'Failed to load repository.');
      setErrorCode(err.status || err.code || null);
    } finally {
      setLoading(false);
    }
  }, [projectId, repositoryId]);

  const [refreshingIngestions, setRefreshingIngestions] = useState(false);

  // Manual refresh ingestion status handler (F-003)
  const handleManualRefreshIngestions = useCallback(async () => {
    setRefreshingIngestions(true);
    setIngestionError(null);
    try {
      const data = await ingestionService.listIngestions(projectId, repositoryId, 50, ingestionOffset);
      const list = Array.isArray(data) ? data : [];
      setIngestions(list);
      setIngestionsHasMore(list.length === 50);
      if (list.length > 0) {
        setSelectedIngestion((prev) => {
          if (!prev) return list[0];
          const updated = list.find((item) => item.id === prev.id);
          return updated || list[0];
        });
      }
    } catch (err) {
      setIngestionError(err.message || 'Failed to refresh ingestion records.');
    } finally {
      setRefreshingIngestions(false);
    }
  }, [projectId, repositoryId, ingestionOffset]);

  // Load ingestion history
  const loadIngestions = useCallback(async (nextOffset = 0) => {
    setLoadingIngestions(true);
    setIngestionError(null);
    try {
      const data = await ingestionService.listIngestions(projectId, repositoryId, 50, nextOffset);
      const list = Array.isArray(data) ? data : [];
      setIngestions(list);
      setIngestionOffset(nextOffset);
      setIngestionsHasMore(list.length === 50);
      if (list.length > 0) {
        setSelectedIngestion(list[0]);
      }
    } catch (err) {
      setIngestionError(err.message || 'Failed to load ingestion records.');
    } finally {
      setLoadingIngestions(false);
    }
  }, [projectId, repositoryId]);

  useEffect(() => {
    loadMetadata();
    loadIngestions();
  }, [loadMetadata, loadIngestions]);

  const activeIngestionId = ingestions[0]?.id;
  const activeIngestionStatus = ingestions[0]?.status?.toLowerCase();

  // Poll only the active ingestion record, without overlapping requests.
  useEffect(() => {
    if (!activeIngestionId || !['pending', 'processing'].includes(activeIngestionStatus)) return undefined;
    let cancelled = false;
    let pollCount = 0;
    let timeoutId;
    const poll = async () => {
      pollCount++;
      try {
        const current = await ingestionService.getIngestion(projectId, repositoryId, activeIngestionId);
        if (cancelled) return;
        setIngestions((items) => items.map((item) => item.id === current.id ? current : item));
        setSelectedIngestion((item) => item?.id === current.id ? current : item);
        if (['pending', 'processing'].includes(current.status?.toLowerCase()) && pollCount < 15) {
          timeoutId = window.setTimeout(poll, 3000);
        }
      } catch (err) {
        if (!cancelled) setIngestionError(err.message || 'Failed to refresh ingestion status.');
      }
    };
    timeoutId = window.setTimeout(poll, 3000);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [activeIngestionId, activeIngestionStatus, projectId, repositoryId]);

  const handleIngestionTriggered = (newIngestion) => {
    if (!newIngestion) return;
    setIngestionOffset(0);
    setIngestions((prev) => [newIngestion, ...(ingestionOffset === 0 ? prev : []).filter((i) => i.id !== newIngestion.id)].slice(0, 50));
    setSelectedIngestion(newIngestion);
  };

  const handleSelectRevisionForArtifacts = (rev) => {
    setSelectedRevisionForArtifacts(rev);
    setActiveTab('artifacts');
  };

  const latestStatus = ingestions && ingestions.length > 0 ? ingestions[0].status : repository?.status;

  const handleRepositorySave = async (payload) => {
    const updated = await repositoryService.updateRepository(projectId, repositoryId, payload);
    setRepository(updated);
    setMutationFeedback(`Repository "${updated.name}" updated successfully.`);
  };

  const handleRepositoryDeleted = () => {
    window.location.hash = '#/projects';
  };

  return (
    <div className="repository-page-wrapper">
      <DashboardHeader />

      <main className="repository-content container">
        {loading && (
          <div className="repo-loading-screen">
            <span className="btn-spinner" aria-hidden="true" />
            <p>Loading repository details...</p>
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
                ? 'Repository or Project Not Found'
                : errorCode === 403
                  ? 'Access Denied'
                  : 'Unable to Load Repository'}
            </h2>
            <p>{error}</p>
            <a href="#/projects" className="btn-gradient-primary" style={{ marginTop: '1rem' }}>
              Return to Projects
            </a>
          </div>
        )}

        {!loading && !error && repository && (
          <>
            {/* Repository Banner Header */}
            <RepositoryHeader
              project={project}
              repository={repository}
              latestIngestionStatus={latestStatus}
              canUpdate={canCreateOrUpdate}
              canDelete={canDelete}
              onEdit={() => setEditRepositoryOpen(true)}
              onDelete={() => setDeleteRepositoryOpen(true)}
            />
            {mutationFeedback && (
              <div className="repo-feedback-banner success" role="status">
                <span>{mutationFeedback}</span>
                <button type="button" className="repo-search-clear-btn" onClick={() => setMutationFeedback(null)} aria-label="Dismiss feedback">×</button>
              </div>
            )}

            {/* Horizontal Navigation Tabs */}
            <nav className="repo-tabs-nav" aria-label="Repository Sections">
              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'ingestion' ? 'active' : ''}`}
                onClick={() => setActiveTab('ingestion')}
                aria-selected={activeTab === 'ingestion'}
                role="tab"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <ellipse cx="12" cy="5" rx="9" ry="3" />
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                </svg>
                <span>Ingestion</span>
              </button>

              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'revisions' ? 'active' : ''}`}
                onClick={() => setActiveTab('revisions')}
                aria-selected={activeTab === 'revisions'}
                role="tab"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="6" y1="3" x2="6" y2="15" />
                  <circle cx="18" cy="6" r="3" />
                  <circle cx="6" cy="18" r="3" />
                  <path d="M18 9a9 9 0 0 1-9 9" />
                </svg>
                <span>Revisions</span>
              </button>

              <button
                type="button"
                className={`repo-tab-btn ${activeTab === 'artifacts' ? 'active' : ''}`}
                onClick={() => setActiveTab('artifacts')}
                aria-selected={activeTab === 'artifacts'}
                role="tab"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                  <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                  <line x1="12" y1="22.08" x2="12" y2="12" />
                </svg>
                <span>Artifacts</span>
              </button>
            </nav>

            {/* Tab Viewport */}
            <div className="repo-tab-viewport">
              {activeTab === 'ingestion' && (
                <IngestionTab
                  ingestions={ingestions}
                  loading={loadingIngestions}
                  refreshing={refreshingIngestions}
                  onRefreshIngestions={handleManualRefreshIngestions}
                  error={ingestionError}
                  onOpenNewIngestion={() => setNewIngestionModalOpen(true)}
                  onOpenUpload={() => setNewIngestionModalOpen(true)}
                  onOpenTrigger={() => setNewIngestionModalOpen(true)}
                  onSelectIngestion={setSelectedIngestion}
                  selectedIngestion={selectedIngestion}
                  canCreate={canCreateOrUpdate}
                  offset={ingestionOffset}
                  hasMore={ingestionsHasMore}
                  onPreviousPage={() => loadIngestions(Math.max(0, ingestionOffset - 50))}
                  onNextPage={() => loadIngestions(ingestionOffset + 50)}
                />
              )}

              {activeTab === 'revisions' && (
                <RevisionsTab
                  projectId={projectId}
                  repositoryId={repositoryId}
                  onSelectRevisionForArtifacts={handleSelectRevisionForArtifacts}
                />
              )}

              {activeTab === 'artifacts' && (
                <ArtifactsTab
                  projectId={projectId}
                  repositoryId={repositoryId}
                  selectedRevision={selectedRevisionForArtifacts}
                  onSelectRevision={setSelectedRevisionForArtifacts}
                />
              )}
            </div>
          </>
        )}
      </main>

      {/* Primary Unified Ingestion Modal (GitHub, Archive Upload, Server Path) */}
      <NewIngestionModal
        isOpen={newIngestionModalOpen && canCreateOrUpdate}
        projectId={projectId}
        repositoryId={repositoryId}
        onClose={() => setNewIngestionModalOpen(false)}
        onIngestionTriggered={handleIngestionTriggered}
      />

      {/* Backward-compatible legacy modal references */}
      <UploadArchiveModal
        isOpen={uploadModalOpen}
        projectId={projectId}
        repositoryId={repositoryId}
        onClose={() => setUploadModalOpen(false)}
        onIngestionTriggered={handleIngestionTriggered}
      />

      <TriggerIngestionModal
        isOpen={triggerModalOpen}
        projectId={projectId}
        repositoryId={repositoryId}
        onClose={() => setTriggerModalOpen(false)}
        onIngestionTriggered={handleIngestionTriggered}
      />
      <MetadataEditModal
        isOpen={editRepositoryOpen}
        entity={repository}
        entityLabel="Repository"
        onClose={() => setEditRepositoryOpen(false)}
        onSave={handleRepositorySave}
      />
      <DeleteRepositoryModal
        isOpen={deleteRepositoryOpen}
        projectId={projectId}
        repository={repository}
        onClose={() => setDeleteRepositoryOpen(false)}
        onDeleted={handleRepositoryDeleted}
      />
    </div>
  );
}
