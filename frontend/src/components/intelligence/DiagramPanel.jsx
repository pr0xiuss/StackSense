import React, { useCallback, useEffect, useRef, useState } from 'react';
import { DiagramView } from '../diagrams/DiagramView.jsx';
import { DiagramCanvas } from '../diagrams/DiagramCanvas.jsx';
import { diagramService } from '../../services/diagramService.js';
import { useIntelligenceDiagram, DIAGRAM_TEMPLATES } from '../../hooks/useIntelligenceDiagram.js';

const TEMPLATE_LABELS = {
  system_overview: 'System Overview',
  component_architecture: 'Component Architecture',
  dependency_map: 'Dependency Map',
  data_flow: 'Data Flow',
};

function LocalDiagram({ versionId, projectId, template, cache }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [selected, setSelected] = useState(null);
  const [collapsed, setCollapsed] = useState([]);
  const [focus, setFocus] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    const key = JSON.stringify([projectId, versionId, template]);
    setData(null); setError(null); setSelected(null); setCollapsed([]); setFocus(null);
    const cached = cache.current.get(key);
    if (cached) {
      setData(cached);
      return () => controller.abort();
    }
    diagramService.getLocalPreview(versionId, template, { projectId, signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) { cache.current.set(key, result); setData(result); } })
      .catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [versionId, projectId, template, attempt, cache]);
  const node = data?.spec.nodes.find(item => item.entity.id === selected?.id);
  const toggleGroup = useCallback(id => setCollapsed(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]), []);
  const focusItem = useCallback(id => {
    const groups = new Map(data.spec.groups.map(group => [group.id, group]));
    const ancestors = new Set();
    let parent = groups.get(id)?.parent_group_id || data.spec.nodes.find(item => item.id === id)?.group_id;
    while (parent && !ancestors.has(parent)) { ancestors.add(parent); parent = groups.get(parent)?.parent_group_id; }
    setCollapsed(current => current.filter(item => !ancestors.has(item)));
    setFocus({ id, sequence: Date.now() });
  }, [data]);
  const downloadJson = () => {
    const revokeUrl = URL.revokeObjectURL.bind(URL);
    const url = URL.createObjectURL(new Blob([JSON.stringify({ mode: data.mode, spec: data.spec, layout: data.layout }, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url; link.download = `local-${template}.json`; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => revokeUrl(url), 1000);
  };
  return <section className="ss-diagram" aria-label="Local diagram">
    <p>Local interactive diagram · Cached while this page is open; not a published artifact.</p>
    {!data && !error && <p role="status">Generating diagram…</p>}
    {error && <div role="alert"><p>Local generation failed: {error}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Retry diagram</button></div>}
    {data && <>
      <p><a download={`local-${template}.svg`} href={`data:image/svg+xml;base64,${data.svg_base64}`}>Download SVG</a>{' · '}<button type="button" onClick={downloadJson}>Download JSON</button></p>
      <p>{data.spec.nodes.length} elements · {data.spec.edges.length} relationships · {data.spec.coverage.view_state.replaceAll('_', ' ')}</p>
      {data.spec.coverage.reasons.length > 0 && <p>Coverage limitations: {data.spec.coverage.reasons.join(', ')}</p>}
      <label>Jump to element: <select className="local-diagram-jump" defaultValue="" onChange={event => { if (event.target.value) focusItem(event.target.value); }}><option value="">Select an element</option>{data.spec.groups.map(group => <option key={group.id} value={group.id}>{group.label}</option>)}{data.spec.nodes.map(item => <option key={item.id} value={item.id}>{item.name} ({item.kind})</option>)}</select></label>
      <div className="ss-diagram-map-layout">
        <DiagramCanvas spec={data.spec} layout={data.layout} viewState={{ base_generation_id: 'local', base_digest: data.spec.semantic_digest, selected_ref: selected, collapsed_groups: collapsed, focus_visual_id: focus }} onSelect={setSelected} onFocus={focusItem} onToggleGroup={toggleGroup} />
        <aside className="ss-diagram-inspector" aria-label="Selected element">
          {node ? <><h3>{node.name}</h3><p>{node.kind} · {node.status}</p><p>{node.namespace.join(' / ')}</p><details><summary>Canonical identifier</summary><code>{node.entity.logical_id}</code></details><p>{node.evidence.length} evidence references</p></> : <><h3>Architecture details</h3><p>Select an element to inspect it. Pan and zoom to explore.</p></>}
        </aside>
      </div>
      <p>Local mode supports pan, zoom, selection and group collapse. Published-generation history and derived views are unavailable.</p>
    </>}
  </section>;
}

export function DiagramPanel({
  versionId,
  projectId,
  onSelectSubject,
  architectureModelUrl,
}) {
  const localCache = useRef(new Map());
  const {
    template,
    templates,
    collection,
    summary,
    selectedGenerationId,
    prepared,
    loading,
    error,
    statusUnavailable,
    exportLoading,
    requestView,
    requestMembers,
    exportDiagram,
    switchTemplate,
    switchGeneration,
    refresh,
  } = useIntelligenceDiagram(versionId, { projectId });

  const showLocal = !loading && error && (
    statusUnavailable || ['NOT_SCHEDULED', 'WAITING', 'BUILDING'].includes(summary?.availability) ||
    (summary?.availability === 'UNAVAILABLE' && summary?.reason === 'diagram_store_unavailable')
  );

  return (
    <div className="intelligence-diagram-panel" role="region" aria-label="Architecture Diagrams">
      {/* Template Navigation Bar */}
      <div className="diagram-template-tabs" role="tablist" aria-label="Diagram Templates">
        {templates.map((tpl) => {
          const isSelected = tpl === template;
          const tplSummary = collection?.items?.find((item) => item.template === tpl);
          const isReady = tplSummary?.availability === 'READY';

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
          {!showLocal && <>
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
          </>}
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

        {!loading && error && !showLocal && (
          <div className="diagram-error-card" role="alert">
            <h3>Diagram Unavailable</h3>
            <p>{error}</p>
            {architectureModelUrl && <p>The existing architecture overview is still available in the <a href={architectureModelUrl}>canonical model</a>.</p>}
            <button type="button" className="btn-retry" onClick={refresh}>
              Retry Loading
            </button>
          </div>
        )}

        {showLocal && (
          <LocalDiagram versionId={versionId} projectId={projectId} template={template} cache={localCache} />
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
