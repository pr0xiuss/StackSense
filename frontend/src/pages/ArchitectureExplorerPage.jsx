import React, { useState, useEffect, useCallback, useMemo } from 'react';
import DashboardHeader from '../components/dashboard/DashboardHeader.jsx';
import { useArchitectureGraph } from '../hooks/useArchitectureGraph.js';
import { useGraphLayout } from '../hooks/useGraphLayout.js';
import { useProjectRole } from '../hooks/useProjectRole.js';
import { GraphStatusBanner } from '../components/graph/GraphStatusBanner.jsx';
import { GraphControls, EXPLORER_MODES } from '../components/graph/GraphControls.jsx';
import { GraphCanvas } from '../components/graph/GraphCanvas.jsx';
import { GraphInspector } from '../components/graph/GraphInspector.jsx';
import { GraphListView } from '../components/graph/GraphListView.jsx';
import { projectService } from '../services/projectService.js';
import { repositoryService } from '../services/repositoryService.js';
import '../styles/graph.css';

export default function ArchitectureExplorerPage({
  projectId,
  repositoryId,
  analysisId,
  versionId,
}) {
  const [project, setProject] = useState(null);
  const [repository, setRepository] = useState(null);
  const [metaLoading, setMetaLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('map');
  const [activeMode, setActiveMode] = useState(EXPLORER_MODES.WINDOW);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [fitViewTrigger, setFitViewTrigger] = useState(0);

  // User project role for mutation authorization (OWNER / ADMIN)
  const { canManageAccess } = useProjectRole(projectId);

  // Orchestrated graph state and operations
  const {
    state: graphState,
    refreshStatus,
    requestRebuild,
    loadMore,
    expandNeighborhood,
    expandDependencies,
    expandDependents,
    expandContainment,
    findPaths,
    selectNode,
    clearExploration,
    reloadVersion,
  } = useArchitectureGraph({
    projectId,
    repositoryId,
    analysisId,
    versionId,
  });

  // Off-thread ELK layout computation
  const {
    positions: layoutPositions,
    isLayoutRunning,
    layoutError,
  } = useGraphLayout({
    nodes: graphState.nodes,
    edges: graphState.edges,
    graphRevision: graphState.graphRevision,
    contextKey: `${projectId}:${versionId}`,
    generationId: graphState.activeGenerationId,
  });

  // Load project & repository metadata for breadcrumb display
  useEffect(() => {
    let active = true;
    setMetaLoading(true);

    Promise.all([
      projectService.getProject(projectId).catch(() => null),
      repositoryService.getRepository(projectId, repositoryId).catch(() => null),
    ]).then(([projData, repoData]) => {
      if (active) {
        setProject(projData);
        setRepository(repoData);
        setMetaLoading(false);
      }
    });

    return () => {
      active = false;
    };
  }, [projectId, repositoryId]);

  const handleRebuild = useCallback(async () => {
    setIsRebuilding(true);
    try {
      await requestRebuild();
    } catch {
      // Handled in reducer
    } finally {
      setIsRebuilding(false);
    }
  }, [requestRebuild]);

  const handleFitView = useCallback(() => {
    setFitViewTrigger((prev) => prev + 1);
  }, []);

  const handleDeselect = useCallback(() => {
    const prevId = graphState.selectedNodeId;
    selectNode(null);
    if (prevId && typeof document !== 'undefined') {
      requestAnimationFrame(() => {
        const nodeEl = document.querySelector(`[data-testid="arch-node-${prevId}"]`);
        if (nodeEl) {
          nodeEl.focus({ preventScroll: true });
          return;
        }
        const listEl = document.querySelector(`[data-testid="entity-select-${prevId}"]`);
        if (listEl) {
          listEl.focus({ preventScroll: true });
        }
      });
    }
  }, [graphState.selectedNodeId, selectNode]);

  const handleExecuteQuery = useCallback(
    (query) => {
      if (query.mode === EXPLORER_MODES.NEIGHBORHOOD) {
        expandNeighborhood(query.entityId, query);
      } else if (query.mode === EXPLORER_MODES.DEPENDENCIES) {
        expandDependencies(query.entityId, query);
      } else if (query.mode === EXPLORER_MODES.DEPENDENTS) {
        expandDependents(query.entityId, query);
      } else if (query.mode === EXPLORER_MODES.CONTAINMENT) {
        expandContainment(query.entityId, query);
      } else if (query.mode === EXPLORER_MODES.PATHS) {
        findPaths(query.sourceEntityId, query.targetEntityId, query);
      }
    },
    [expandNeighborhood, expandDependencies, expandDependents, expandContainment, findPaths]
  );

  const selectedNode = useMemo(() => {
    if (!graphState.selectedNodeId) return null;
    return graphState.nodes[graphState.selectedNodeId] || null;
  }, [graphState.selectedNodeId, graphState.nodes]);

  const loadedNodesList = useMemo(() => {
    return Object.values(graphState.nodes);
  }, [graphState.nodes]);

  const version = graphState.version;

  return (
    <div className="graph-explorer-page">
      <DashboardHeader />

      <main className="container" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Context Error Screen */}
        {graphState.contextError && (
          <div className="repo-error-screen" role="alert">
            <div className="error-icon-box">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h2>Unable to Load Explorer</h2>
            <p>{graphState.contextError}</p>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
              <a
                href={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}`}
                className="btn-gradient-primary"
              >
                Return to Architecture Model
              </a>
            </div>
          </div>
        )}

        {/* Loading Screen */}
        {!graphState.contextError && (!graphState.contextValidated || metaLoading) && (
          <div className="repo-loading-screen" role="status">
            <span className="btn-spinner" aria-hidden="true" />
            <p>Loading architecture graph explorer...</p>
          </div>
        )}

        {/* Validated Explorer View */}
        {!graphState.contextError && graphState.contextValidated && version && (
          <>
            {/* Header & Breadcrumb */}
            <div className="graph-header-card">
              <nav className="repo-breadcrumb" aria-label="Architecture Explorer Breadcrumb">
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
                <a
                  href={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}`}
                  className="breadcrumb-link"
                >
                  Architecture Model v{version.sequence_number || 1}
                </a>
                <span className="breadcrumb-separator">/</span>
                <span className="breadcrumb-current">Graph Explorer</span>
              </nav>

              <div className="graph-banner-main">
                <div className="graph-banner-info">
                  <div className="graph-cube-badge">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="6" cy="6" r="3" />
                      <circle cx="18" cy="18" r="3" />
                      <line x1="8.5" y1="8.5" x2="15.5" y2="15.5" />
                    </svg>
                  </div>

                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                      <h1 className="graph-title">
                        Architecture Graph Explorer — v{version.sequence_number || 1}
                      </h1>
                    </div>

                    <div className="graph-subtitle">
                      <span className="mono-cell">ID: {version.id.slice(0, 8)}...</span>
                      <span>Total Entities: {version.entity_count ?? 0}</span>
                      <span>Total Relationships: {version.relationship_count ?? 0}</span>
                      <span className="badge-status" style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8' }} aria-live="polite">
                        Loaded: {graphState.loadedNodeCount} nodes / {graphState.loadedEdgeCount} edges
                      </span>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.6rem' }}>
                  <a
                    href={`#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}`}
                    className="btn-secondary"
                    style={{ textDecoration: 'none' }}
                  >
                    &larr; Back to Exact Model
                  </a>
                </div>
              </div>
            </div>

            {/* Projection Lifecycle & Status Banner */}
            <GraphStatusBanner
              status={graphState.status}
              isOutOfDate={graphState.isOutOfDate}
              generationChangeMessage={graphState.generationChangeMessage}
              isCapReached={graphState.isCapReached}
              capMessage={graphState.capMessage}
              error={graphState.error}
              canManage={Boolean(canManageAccess)}
              onRetry={refreshStatus}
              onRebuild={handleRebuild}
              onReload={reloadVersion}
              isRebuilding={isRebuilding}
            />

            {/* View Tabs */}
            <div className="graph-toolbar">
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  type="button"
                  className={`repo-tab-btn ${activeTab === 'map' ? 'active' : ''}`}
                  onClick={() => setActiveTab('map')}
                  style={{ borderRadius: '6px' }}
                >
                  Graph Map
                </button>
                <button
                  type="button"
                  className={`repo-tab-btn ${activeTab === 'list' ? 'active' : ''}`}
                  onClick={() => setActiveTab('list')}
                  style={{ borderRadius: '6px' }}
                >
                  Structured List ({graphState.loadedNodeCount})
                </button>
              </div>
            </div>

            {/* Interactive Graph Controls Toolbar */}
            <GraphControls
              mode={activeMode}
              onModeChange={setActiveMode}
              selectedNode={selectedNode}
              loadedNodes={loadedNodesList}
              activeOperation={graphState.operations[activeMode] || graphState.operations.window}
              isCapReached={graphState.isCapReached}
              onLoadMore={() => loadMore(activeMode)}
              onExecuteQuery={handleExecuteQuery}
              onClear={clearExploration}
              onFit={handleFitView}
            />

            {/* Main Content Area */}
            <div className="graph-main-layout">
              {/* Canvas or Structured List Tab View */}
              {activeTab === 'map' ? (
                <div className="graph-canvas-container">
                  <GraphCanvas
                    nodes={graphState.nodes}
                    edges={graphState.edges}
                    positions={layoutPositions}
                    selectedNodeId={graphState.selectedNodeId}
                    onSelectNode={selectNode}
                    fitViewTrigger={fitViewTrigger}
                    isLayoutRunning={isLayoutRunning}
                    layoutError={layoutError}
                  />
                </div>
              ) : (
                <GraphListView
                  nodes={graphState.nodes}
                  edges={graphState.edges}
                  selectedNodeId={graphState.selectedNodeId}
                  onSelectNode={selectNode}
                  onExpandNeighborhood={(id) => expandNeighborhood(id, { mode: EXPLORER_MODES.NEIGHBORHOOD, depth: 1 })}
                  onExpandDependencies={(id) => expandDependencies(id, { mode: EXPLORER_MODES.DEPENDENCIES, depth: 1 })}
                  onExpandDependents={(id) => expandDependents(id, { mode: EXPLORER_MODES.DEPENDENTS, depth: 1 })}
                  layoutError={layoutError}
                />
              )}

              {/* Inspector Panel */}
              <GraphInspector
                selectedNode={selectedNode}
                version={version}
                nodes={graphState.nodes}
                onDeselect={handleDeselect}
                onExpandNeighborhood={(id) => expandNeighborhood(id, { mode: EXPLORER_MODES.NEIGHBORHOOD, depth: 1 })}
                onExpandDependencies={(id) => expandDependencies(id, { mode: EXPLORER_MODES.DEPENDENCIES, depth: 1 })}
                onExpandDependents={(id) => expandDependents(id, { mode: EXPLORER_MODES.DEPENDENTS, depth: 1 })}
                onExpandContainment={(id) => expandContainment(id, { mode: EXPLORER_MODES.CONTAINMENT, depth: 1, direction: 'children' })}
                isOperationInFlight={Boolean(graphState.operations[activeMode]?.inFlight)}
              />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
