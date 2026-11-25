import React from 'react';
import { DiagramView } from '../diagrams/DiagramView.jsx';
import { useIntelligenceDiagram, DIAGRAM_TEMPLATES } from '../../hooks/useIntelligenceDiagram.js';

const TEMPLATE_LABELS = {
  system_overview: 'System Overview',
  component_architecture: 'Component Architecture',
  dependency_map: 'Dependency Map',
  data_flow: 'Data Flow',
};

export function DiagramPanel({
  versionId,
  projectId,
  onSelectSubject,
}) {
  const {
    template,
    templates,
    collection,
    summary,
    selectedGenerationId,
    prepared,
    loading,
    error,
    exportLoading,
    requestView,
    requestMembers,
    exportDiagram,
    switchTemplate,
    switchGeneration,
    refresh,
  } = useIntelligenceDiagram(versionId, { projectId });

  return (
    <div className="intelligence-diagram-panel" role="region" aria-label="Architecture Diagrams">
      {/* Template Navigation Bar */}
      <div className="diagram-template-tabs" role="tablist" aria-label="Diagram Templates">
        {templates.map((tpl) => {
          const isSelected = tpl === template;
          const tplSummary = collection?.diagrams?.[tpl];
          const isReady = tplSummary?.ready ?? (summary?.template === tpl ? summary?.ready : true);

          return (
            <button
              key={tpl}
              type="button"
              role="tab"
              aria-selected={isSelected}
              className={`template-tab-btn ${isSelected ? 'active' : ''}`}
              onClick={() => switchTemplate(tpl)}
            >
              <span className="template-tab-title">{TEMPLATE_LABELS[tpl] || tpl}</span>
              {tplSummary && (
                <span className={`template-indicator ${isReady ? 'ready' : 'pending'}`} />
              )}
            </button>
          );
        })}
      </div>

      {/* Generation & Actions Bar */}
      <div className="diagram-control-toolbar">
        <div className="diagram-meta-group">
          <span className="diagram-active-label">
            Active: <strong>{TEMPLATE_LABELS[template]}</strong>
          </span>

          {summary?.generations && summary.generations.length > 1 && (
            <label className="generation-select-label">
              <span>Generation:</span>
              <select
                value={selectedGenerationId || ''}
                onChange={(e) => switchGeneration(e.target.value)}
                className="generation-dropdown"
              >
                {summary.generations.map((g) => (
                  <option key={g.generation_id} value={g.generation_id}>
                    {g.generation_id.slice(0, 8)}… ({new Date(g.created_at).toLocaleTimeString()})
                  </option>
                ))}
              </select>
            </label>
          )}

          {selectedGenerationId && (
            <span className="generation-pill" title={`Generation ID: ${selectedGenerationId}`}>
              Gen {selectedGenerationId.slice(0, 8)}
            </span>
          )}
        </div>

        <div className="diagram-action-group">
          <button
            type="button"
            className="btn-diagram-action"
            disabled={exportLoading || !prepared}
            onClick={() => exportDiagram('svg')}
          >
            {exportLoading ? 'Exporting…' : 'Export SVG'}
          </button>
          <button
            type="button"
            className="btn-diagram-action"
            disabled={exportLoading || !prepared}
            onClick={() => exportDiagram('json')}
          >
            Export JSON
          </button>
          <button
            type="button"
            className="btn-diagram-action btn-refresh"
            onClick={refresh}
            title="Refresh diagram view"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Main Diagram Viewport */}
      <div className="diagram-viewport-container">
        {loading && (
          <div className="diagram-status-placeholder" role="status">
            <span className="spinner-dot" />
            <span>Loading {TEMPLATE_LABELS[template]} diagram…</span>
          </div>
        )}

        {!loading && error && (
          <div className="diagram-error-card" role="alert">
            <h3>Diagram Unavailable</h3>
            <p>{error}</p>
            <button type="button" className="btn-retry" onClick={refresh}>
              Retry Loading
            </button>
          </div>
        )}

        {!loading && !error && prepared && (
          <DiagramView
            prepared={prepared}
            requestView={requestView}
            requestMembers={requestMembers}
            onSelect={(ref) => onSelectSubject?.(ref)}
            onExport={exportDiagram}
            onError={(err) => console.error('Diagram render error:', err)}
          />
        )}
      </div>
    </div>
  );
}
export default DiagramPanel;
