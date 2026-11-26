import React, { useState, useEffect } from 'react';
import { useRepositoryIntelligence } from '../hooks/useRepositoryIntelligence.js';
import { useProjectRole } from '../hooks/useProjectRole.js';
import { useIntelligenceDelivery } from '../hooks/useIntelligenceDelivery.js';
import { useIntelligenceQuery } from '../hooks/useIntelligenceQuery.js';
import { IntelligenceHeader } from '../components/intelligence/IntelligenceHeader.jsx';
import { IntelligenceErrorBoundary } from '../components/intelligence/IntelligenceErrorBoundary.jsx';
import { DeliveryStatus } from '../components/intelligence/DeliveryStatus.jsx';
import { DiagramPanel } from '../components/intelligence/DiagramPanel.jsx';
import { SearchPanel } from '../components/intelligence/SearchPanel.jsx';
import { KnowledgePanel } from '../components/intelligence/KnowledgePanel.jsx';
import { EvidencePanel } from '../components/intelligence/EvidencePanel.jsx';
import { ReportPanel } from '../components/intelligence/ReportPanel.jsx';
import '../styles/intelligence.css';

/**
 * Repository Intelligence Page (M6 Unified Workspace)
 *
 * Provides a unified intelligence workspace spanning Diagrams, Search, Knowledge, and Reports
 * with a shared bounded evidence drawer and compact delivery strip.
 */
export default function RepositoryIntelligencePage({
  projectId,
  repositoryId,
  analysisId,
  versionId,
}) {
  const getTabFromLocation = () => {
    const hash = window.location.hash || '';
    const qIndex = hash.indexOf('?');
    if (qIndex !== -1) {
      const sp = new URLSearchParams(hash.slice(qIndex));
      const t = sp.get('tab');
      if (['diagrams', 'search', 'knowledge', 'reports'].includes(t)) return t;
    }
    const sp = new URLSearchParams(window.location.search);
    const t = sp.get('tab');
    if (['diagrams', 'search', 'knowledge', 'reports'].includes(t)) return t;
    return 'diagrams';
  };

  const [activeTab, setActiveTab] = useState(getTabFromLocation);

  useEffect(() => {
    const onHashChange = () => {
      setActiveTab(getTabFromLocation());
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    const hash = window.location.hash || '';
    const baseHash = hash.split('?')[0];
    if (tab === 'diagrams') {
      window.location.hash = baseHash;
    } else {
      window.location.hash = `${baseHash}?tab=${tab}`;
    }
  };

  const {
    project,
    repository,
    analysis,
    version,
    loading,
    error,
    reload,
  } = useRepositoryIntelligence({
    projectId,
    repositoryId,
    analysisId,
    versionId,
  });

  const { role } = useProjectRole(projectId);

  // Delivery status & retry hook
  const deliveryHook = useIntelligenceDelivery(versionId, { projectId });

  // Query, search, and evidence hook
  const queryHook = useIntelligenceQuery(versionId, { projectId });

  if (loading) {
    return (
      <div className="intelligence-page" aria-busy="true">
        <div className="intelligence-loading">
          <p>Loading repository intelligence context...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="intelligence-page">
        <div className="intelligence-error-card" role="alert">
          <h2 className="intelligence-error-title">Failed to load intelligence workspace</h2>
          <p className="intelligence-error-message">{error.message}</p>
          <div className="intelligence-error-actions">
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={reload}
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="intelligence-page">
      <IntelligenceHeader
        project={project}
        repository={repository}
        analysis={analysis}
        version={version}
        activeTab={activeTab}
        onTabChange={handleTabChange}
      />

      {/* Projection Delivery Strip */}
      <DeliveryStatus
        delivery={deliveryHook.delivery}
        loading={deliveryHook.loading}
        error={deliveryHook.error}
        retrying={deliveryHook.retrying}
        retryError={deliveryHook.retryError}
        onRetry={deliveryHook.retryWorkItem}
        userRole={role}
      />

      <main className="intelligence-workspace">
        <IntelligenceErrorBoundary key={activeTab}>
          <div className="intelligence-panel-container">
            {activeTab === 'diagrams' && (
              <section
                id="panel-diagrams"
                role="tabpanel"
                aria-labelledby="tab-diagrams"
                className="intelligence-panel"
              >
                <DiagramPanel
                  versionId={versionId}
                  projectId={projectId}
                  architectureModelUrl={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}`}
                  onSelectSubject={(ref) => queryHook.openEvidence({
                    entity_id: ref.id,
                    name: ref.name || ref.id,
                  })}
                />
              </section>
            )}

            {activeTab === 'search' && (
              <section
                id="panel-search"
                role="tabpanel"
                aria-labelledby="tab-search"
                className="intelligence-panel"
              >
                <SearchPanel
                  searchQuery={queryHook.searchQuery}
                  setSearchQuery={queryHook.setSearchQuery}
                  searchFilters={queryHook.searchFilters}
                  setSearchFilters={queryHook.setSearchFilters}
                  searchStatus={queryHook.searchStatus}
                  searchPage={queryHook.searchPage}
                  searchLoading={queryHook.searchLoading}
                  searchError={queryHook.searchError}
                  searchCursorIndex={queryHook.searchCursorIndex}
                  hasMoreSearch={queryHook.hasMoreSearch}
                  onSearch={queryHook.executeSearch}
                  onNextPage={queryHook.nextSearchPage}
                  onPrevPage={queryHook.prevSearchPage}
                  onInspectSubject={(subj) => {
                    handleTabChange('knowledge');
                    queryHook.setSelectorType('logical_id');
                    queryHook.setSelectorValue(subj.logical_id);
                    queryHook.executeKnowledgeQuery({ type: 'logical_id', value: subj.logical_id });
                  }}
                  onOpenEvidence={(subj) => queryHook.openEvidence(subj)}
                />
              </section>
            )}

            {activeTab === 'knowledge' && (
              <section
                id="panel-knowledge"
                role="tabpanel"
                aria-labelledby="tab-knowledge"
                className="intelligence-panel"
              >
                <KnowledgePanel
                  selectorType={queryHook.selectorType}
                  setSelectorType={queryHook.setSelectorType}
                  selectorValue={queryHook.selectorValue}
                  setSelectorValue={queryHook.setSelectorValue}
                  operation={queryHook.operation}
                  setOperation={queryHook.setOperation}
                  knowledgeResponse={queryHook.knowledgeResponse}
                  knowledgeLoading={queryHook.knowledgeLoading}
                  knowledgeError={queryHook.knowledgeError}
                  onExecuteQuery={queryHook.executeKnowledgeQuery}
                  contextBundle={queryHook.contextBundle}
                  contextLoading={queryHook.contextLoading}
                  contextError={queryHook.contextError}
                  onAssembleContext={queryHook.assembleContext}
                  onOpenEvidence={(subj) => queryHook.openEvidence(subj)}
                />
              </section>
            )}

            {activeTab === 'reports' && (
              <section
                id="panel-reports"
                role="tabpanel"
                aria-labelledby="tab-reports"
                className="intelligence-panel"
              >
                <ReportPanel
                  versionId={versionId}
                  projectId={projectId}
                />
              </section>
            )}
          </div>
        </IntelligenceErrorBoundary>
      </main>

      {/* Shared Bounded Evidence Drawer */}
      <EvidencePanel
        evidenceSubject={queryHook.evidenceSubject}
        evidencePage={queryHook.evidencePage}
        evidenceLoading={queryHook.evidenceLoading}
        evidenceError={queryHook.evidenceError}
        evidenceCursorIndex={queryHook.evidenceCursorIndex}
        hasMoreEvidence={queryHook.hasMoreEvidence}
        onNextPage={queryHook.nextEvidencePage}
        onPrevPage={queryHook.prevEvidencePage}
        onClose={queryHook.closeEvidence}
      />
    </div>
  );
}
