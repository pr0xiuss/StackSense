import React, { useState, useEffect, useCallback } from 'react';
import DashboardHeader from '../components/dashboard/DashboardHeader.jsx';
import RepositoryHeader from '../components/repository/RepositoryHeader.jsx';
import IngestionTab from '../components/repository/IngestionTab.jsx';
import RevisionsTab from '../components/repository/RevisionsTab.jsx';
import ArtifactsTab from '../components/repository/ArtifactsTab.jsx';
import NewIngestionModal from '../components/repository/NewIngestionModal.jsx';
import UploadArchiveModal from '../components/repository/UploadArchiveModal.jsx';
import TriggerIngestionModal from '../components/repository/TriggerIngestionModal.jsx';
import { projectService } from '../services/projectService.js';
import { repositoryService } from '../services/repositoryService.js';
import { ingestionService } from '../services/ingestionService.js';

export default function RepositoryDetailPage({ projectId, repositoryId }) {
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

  // Artifacts tab revision selection state
  const [selectedRevisionForArtifacts, setSelectedRevisionForArtifacts] = useState(null);

  // Modals state
  const [newIngestionModalOpen, setNewIngestionModalOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [triggerModalOpen, setTriggerModalOpen] = useState(false);

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

  // Load ingestion history
  const loadIngestions = useCallback(async () => {
    setLoadingIngestions(true);
    setIngestionError(null);
    try {
      const data = await ingestionService.listIngestions(projectId, repositoryId, 50, 0);
      const list = Array.isArray(data) ? data : [];
      setIngestions(list);
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

  // Bounded polling when latest ingestion is in PROCESSING state
  useEffect(() => {
    const latest = ingestions && ingestions.length > 0 ? ingestions[0] : null;
    const isProcessing = latest?.status?.toLowerCase() === 'processing';

    if (!isProcessing) return;

    let pollCount = 0;
    const maxPolls = 15; // Max 45 seconds bounded polling
    const intervalId = setInterval(async () => {
      pollCount++;
      try {
        const data = await ingestionService.listIngestions(projectId, repositoryId, 50, 0);
        const list = Array.isArray(data) ? data : [];
        if (list.length > 0) {
          setIngestions(list);
          setSelectedIngestion((prev) => {
            if (!prev) return list[0];
            const updated = list.find((item) => item.id === prev.id);
            return updated || list[0];
          });
          const currentLatest = list[0];
          if (currentLatest.status?.toLowerCase() !== 'processing' || pollCount >= maxPolls) {
            clearInterval(intervalId);
          }
        }
      } catch {
        clearInterval(intervalId);
      }
    }, 3000);

    return () => clearInterval(intervalId);
  }, [ingestions, projectId, repositoryId]);

  const handleIngestionTriggered = (newIngestion) => {
    if (!newIngestion) return;
    setIngestions((prev) => [newIngestion, ...prev.filter((i) => i.id !== newIngestion.id)]);
    setSelectedIngestion(newIngestion);
  };

  const handleSelectRevisionForArtifacts = (rev) => {
    setSelectedRevisionForArtifacts(rev);
    setActiveTab('artifacts');
  };

  const latestStatus = ingestions && ingestions.length > 0 ? ingestions[0].status : repository?.status;

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
            />

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
                  error={ingestionError}
                  onOpenNewIngestion={() => setNewIngestionModalOpen(true)}
                  onOpenUpload={() => setNewIngestionModalOpen(true)}
                  onOpenTrigger={() => setNewIngestionModalOpen(true)}
                  onSelectIngestion={setSelectedIngestion}
                  selectedIngestion={selectedIngestion}
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
        isOpen={newIngestionModalOpen}
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
    </div>
  );
}
