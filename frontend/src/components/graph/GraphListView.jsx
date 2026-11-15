import React, { useState, useMemo } from 'react';
import '../../styles/graph.css';

/**
 * Graph List View (Frontend)
 *
 * Provides a fully accessible structured table alternative to the visual canvas,
 * allowing element selection and relationship traversals via standard keyboard and screen reader elements.
 */
export function GraphListView({
  nodes = {},
  edges = {},
  selectedNodeId,
  onSelectNode,
  onExpandNeighborhood,
  onExpandDependencies,
  onExpandDependents,
  layoutError,
}) {
  const [activeTab, setActiveTab] = useState('entities');
  const [filterText, setFilterText] = useState('');

  const nodeList = useMemo(() => Object.values(nodes), [nodes]);
  const edgeList = useMemo(() => Object.values(edges), [edges]);

  // Filter nodes
  const filteredNodes = useMemo(() => {
    if (!filterText.trim()) return nodeList;
    const term = filterText.toLowerCase();
    return nodeList.filter(
      (n) =>
        (n.name && n.name.toLowerCase().includes(term)) ||
        (n.canonical_kind && n.canonical_kind.toLowerCase().includes(term)) ||
        (n.logical_id && n.logical_id.toLowerCase().includes(term)) ||
        (n.namespace && n.namespace.toLowerCase().includes(term))
    );
  }, [nodeList, filterText]);

  // Filter edges
  const filteredEdges = useMemo(() => {
    if (!filterText.trim()) return edgeList;
    const term = filterText.toLowerCase();
    return edgeList.filter(
      (e) =>
        (e.canonical_kind && e.canonical_kind.toLowerCase().includes(term)) ||
        (e.logical_id && e.logical_id.toLowerCase().includes(term))
    );
  }, [edgeList, filterText]);

  return (
    <div
      className="graph-list-view"
      data-testid="graph-list-view"
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#070d19',
        border: '1px solid #1e293b',
        borderRadius: '0.75rem',
        overflow: 'hidden',
        padding: '1.25rem',
        boxSizing: 'border-box',
      }}
    >
      {layoutError && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: 6,
            padding: '8px 12px',
            marginBottom: '1rem',
            fontSize: '0.82rem',
            color: '#fca5a5',
          }}
        >
          ℹ️ Canvas layout encountered an issue: {layoutError}. Structured list view is available below.
        </div>
      )}

      {/* Header with Sub-tabs and Search Filter */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap',
          marginBottom: '1rem',
        }}
      >
        <div style={{ display: 'flex', gap: '0.5rem' }} role="group" aria-label="Structured graph view categories">
          <button
            type="button"
            id="graph-tab-entities"
            aria-pressed={activeTab === 'entities'}
            aria-controls="graph-list-entities-panel"
            className={`repo-tab-btn ${activeTab === 'entities' ? 'active' : ''}`}
            onClick={() => setActiveTab('entities')}
            style={{ borderRadius: 6, fontSize: '0.85rem' }}
          >
            Entities ({nodeList.length})
          </button>
          <button
            type="button"
            id="graph-tab-relationships"
            aria-pressed={activeTab === 'relationships'}
            aria-controls="graph-list-relationships-panel"
            className={`repo-tab-btn ${activeTab === 'relationships' ? 'active' : ''}`}
            onClick={() => setActiveTab('relationships')}
            style={{ borderRadius: 6, fontSize: '0.85rem' }}
          >
            Relationships ({edgeList.length})
          </button>
        </div>

        <div>
          <label htmlFor="graph-list-filter" className="sr-only">
            Filter loaded {activeTab}
          </label>
          <input
            id="graph-list-filter"
            type="text"
            className="graph-select"
            placeholder={`Filter ${activeTab}...`}
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            style={{ width: '220px', padding: '6px 10px', fontSize: '0.82rem' }}
            aria-label={`Filter loaded ${activeTab}`}
          />
          <div className="sr-only" aria-live="polite">
            {filterText.trim()
              ? activeTab === 'entities'
                ? `Showing ${filteredNodes.length} of ${nodeList.length} entities`
                : `Showing ${filteredEdges.length} of ${edgeList.length} relationships`
              : ''}
          </div>
        </div>
      </div>

      {/* Main Content Table Area */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {activeTab === 'entities' && (
          <div id="graph-list-entities-panel" role="region" aria-label="Loaded entities list">
            {filteredNodes.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748b' }}>
                <p style={{ margin: 0, fontSize: '0.9rem' }}>
                  {nodeList.length === 0
                    ? 'No entities loaded in the current exploration window.'
                    : 'No entities match the current filter.'}
                </p>
              </div>
            ) : (
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: '0.82rem',
                  textAlign: 'left',
                }}
                aria-label="Loaded Architecture Entities Table"
              >
                <thead>
                  <tr style={{ borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                    <th scope="col" style={{ padding: '8px 12px' }}>Name</th>
                    <th scope="col" style={{ padding: '8px 12px' }}>Kind</th>
                    <th scope="col" style={{ padding: '8px 12px' }}>Status</th>
                    <th scope="col" style={{ padding: '8px 12px' }}>Logical ID</th>
                    <th scope="col" style={{ padding: '8px 12px' }}>Evidence</th>
                    <th scope="col" style={{ padding: '8px 12px', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredNodes.map((n) => {
                    const isSelected = selectedNodeId === n.architecture_entity_id;
                    const isConfirmed = n.fact_status === 'CONFIRMED';
                    return (
                      <tr
                        key={n.architecture_entity_id}
                        style={{
                          borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                          background: isSelected ? 'rgba(99, 102, 241, 0.12)' : 'transparent',
                        }}
                      >
                        <td style={{ padding: '8px 12px', fontWeight: 600, color: '#f8fafc', wordBreak: 'break-word' }}>
                          {n.name}
                        </td>
                        <td style={{ padding: '8px 12px' }}>
                          <span className="arch-node-kind-badge">{n.canonical_kind}</span>
                        </td>
                        <td style={{ padding: '8px 12px', color: isConfirmed ? '#10b981' : '#f59e0b' }}>
                          {n.fact_status}
                        </td>
                        <td style={{ padding: '8px 12px' }}>
                          <span className="mono-cell" style={{ fontSize: '0.75rem' }}>{n.logical_id}</span>
                        </td>
                        <td style={{ padding: '8px 12px', color: '#94a3b8' }}>
                          {Array.isArray(n.evidence_logical_ids) ? n.evidence_logical_ids.length : 0}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                          <div style={{ display: 'flex', gap: '4px', justifyContent: 'flex-end' }}>
                            <button
                              type="button"
                              className={`graph-btn ${isSelected ? 'graph-btn-primary' : 'graph-btn-secondary'}`}
                              style={{ padding: '2px 8px', fontSize: '0.72rem' }}
                              onClick={() => onSelectNode && onSelectNode(n.architecture_entity_id)}
                              aria-label={`Select ${n.name}`}
                              data-testid={`entity-select-${n.architecture_entity_id}`}
                            >
                              {isSelected ? 'Selected' : 'Select'}
                            </button>
                            {onExpandNeighborhood && (
                              <button
                                type="button"
                                className="graph-btn graph-btn-ghost"
                                style={{ padding: '2px 6px', fontSize: '0.72rem' }}
                                onClick={() => onExpandNeighborhood(n.architecture_entity_id)}
                                title="Expand neighborhood"
                                aria-label={`Expand neighborhood of ${n.name}`}
                              >
                                Neighbors
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}

        {activeTab === 'relationships' && (
          <div id="graph-list-relationships-panel" role="region" aria-label="Loaded relationships list">
            {filteredEdges.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748b' }}>
                <p style={{ margin: 0, fontSize: '0.9rem' }}>
                  {edgeList.length === 0
                    ? 'No relationships loaded in the current exploration window.'
                    : 'No relationships match the current filter.'}
                </p>
              </div>
            ) : (
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: '0.82rem',
                  textAlign: 'left',
                }}
                aria-label="Loaded Architecture Relationships Table"
              >
                <thead>
                  <tr style={{ borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                    <th scope="col" style={{ padding: '8px 12px' }}>Source Element</th>
                    <th scope="col" style={{ padding: '8px 12px' }}>Relationship Kind</th>
                    <th scope="col" style={{ padding: '8px 12px' }}>Target Element</th>
                    <th scope="col" style={{ padding: '8px 12px' }}>Logical ID</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEdges.map((e) => {
                    const src = nodes[e.source_entity_id];
                    const tgt = nodes[e.target_entity_id];
                    return (
                      <tr
                        key={e.architecture_relationship_id}
                        style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}
                      >
                        <td style={{ padding: '8px 12px', color: '#f8fafc', wordBreak: 'break-word' }}>
                          {src?.name || e.source_entity_id.slice(0, 8)}
                        </td>
                        <td style={{ padding: '8px 12px' }}>
                          <span
                            className="arch-node-kind-badge"
                            style={{
                              background: e.canonical_kind === 'contains' ? '#3b0764' : '#1e1b4b',
                              borderColor: e.canonical_kind === 'contains' ? '#7e22ce' : '#4338ca',
                              color: e.canonical_kind === 'contains' ? '#d8b4fe' : '#a5b4fc',
                            }}
                          >
                            {e.canonical_kind}
                          </span>
                        </td>
                        <td style={{ padding: '8px 12px', color: '#f8fafc', wordBreak: 'break-word' }}>
                          {tgt?.name || e.target_entity_id.slice(0, 8)}
                        </td>
                        <td style={{ padding: '8px 12px' }}>
                          <span className="mono-cell" style={{ fontSize: '0.75rem' }}>{e.logical_id}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default GraphListView;

