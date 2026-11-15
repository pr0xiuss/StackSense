import React, { useState } from 'react';
import '../../styles/graph.css';

const PAGE_SIZE = 20;

/** Pagination covers the loaded, bounded exploration window, not the whole model. */
export function GraphListView({
  nodes = {}, edges = {}, selectedNodeId, onSelectNode,
  onExpandNeighborhood, onViewOnMap, isOperationInFlight = false, layoutError,
}) {
  const [activeTab, setActiveTab] = useState('entities');
  const [filterText, setFilterText] = useState('');
  const [pages, setPages] = useState({ entities: 1, relationships: 1 });
  const nodeList = Object.values(nodes);
  const edgeList = Object.values(edges);
  const term = filterText.trim().toLowerCase();
  const records = (activeTab === 'entities' ? nodeList : edgeList).filter((record) =>
    [record.name, record.canonical_kind, record.logical_id, record.namespace,
      nodes[record.source_entity_id]?.name, nodes[record.target_entity_id]?.name]
      .some((value) => value?.toLowerCase().includes(term))
  );
  const pageCount = Math.max(1, Math.ceil(records.length / PAGE_SIZE));
  const page = Math.min(pages[activeTab], pageCount);
  const start = (page - 1) * PAGE_SIZE;
  const visibleRecords = records.slice(start, start + PAGE_SIZE);
  const changePage = (next) => setPages((previous) => ({ ...previous, [activeTab]: next }));

  return (
    <section className="graph-list-view" data-testid="graph-list-view">
      {layoutError && <p className="graph-list-note">Canvas layout encountered an issue: {layoutError}. Structured list view is available below.</p>}
      <div className="graph-list-header">
        <div role="group" aria-label="Structured graph view categories">
          {['entities', 'relationships'].map((tab) => (
            <button key={tab} type="button" aria-pressed={activeTab === tab}
              className={`repo-tab-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}>
              {tab === 'entities' ? `Entities (${nodeList.length})` : `Relationships (${edgeList.length})`}
            </button>
          ))}
        </div>
        <input type="search" className="graph-select" aria-label={`Filter loaded ${activeTab}`}
          placeholder={`Filter ${activeTab}...`} value={filterText}
          onChange={(event) => { setFilterText(event.target.value); setPages({ entities: 1, relationships: 1 }); }} />
      </div>
      <p className="graph-list-note">Browsing loaded records only. Use Load more above to retrieve another server window.</p>
      <div className="graph-table-scroll" role="region" aria-label={`Loaded ${activeTab} list`} tabIndex={0}>
        {records.length === 0 ? (
          <p className="graph-list-empty">{(activeTab === 'entities' ? nodeList : edgeList).length === 0
            ? `No ${activeTab} loaded in the current exploration window.` : `No ${activeTab} match the current filter.`}</p>
        ) : activeTab === 'entities' ? (
          <table className="graph-entity-table" aria-label="Loaded Architecture Entities Table">
            <colgroup><col /><col /><col /><col /><col /><col /></colgroup>
            <thead><tr>{['Name', 'Kind', 'Status', 'Logical ID', 'Evidence', 'Actions'].map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead>
            <tbody>{visibleRecords.map((node) => {
              const id = node.architecture_entity_id;
              const selected = selectedNodeId === id;
              return <tr key={id} className={selected ? 'graph-row-selected' : ''}>
                <td><strong>{node.name}</strong><span className="graph-cell-secondary" title={node.namespace}>{node.namespace}</span></td>
                <td><span className="arch-node-kind-badge">{node.canonical_kind}</span></td>
                <td><span className="graph-cell-status" data-supported={['confirmed', 'supported'].includes(node.fact_status?.toLowerCase())}>{node.fact_status}</span></td>
                <td><details className="graph-id-details"><summary>Show identifier</summary><code>{node.logical_id}</code></details></td>
                <td>{node.evidence_logical_ids?.length || 0}</td>
                <td><div className="graph-row-actions">
                  <button type="button" className="graph-btn" aria-pressed={selected} aria-label={`Select ${node.name}`}
                    data-testid={`entity-select-${id}`} onClick={() => onSelectNode?.(id)}>{selected ? 'Selected' : 'Select'}</button>
                  {onViewOnMap && <button type="button" className="graph-btn" onClick={() => onViewOnMap(id)}>View on map</button>}
                  {onExpandNeighborhood && <button type="button" className="graph-btn graph-btn-secondary"
                    disabled={isOperationInFlight} aria-label={`Expand neighborhood of ${node.name}`}
                    onClick={() => onExpandNeighborhood(id)}>Neighbors</button>}
                </div></td>
              </tr>;
            })}</tbody>
          </table>
        ) : (
          <table className="graph-relationship-table" aria-label="Loaded Architecture Relationships Table">
            <colgroup><col /><col /><col /><col /></colgroup>
            <thead><tr>{['Source Element', 'Relationship Kind', 'Target Element', 'Logical ID'].map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead>
            <tbody>{visibleRecords.map((edge) => <tr key={edge.architecture_relationship_id}>
              <td>{nodes[edge.source_entity_id]?.name || edge.source_entity_id}</td>
              <td><span className="arch-node-kind-badge">{edge.canonical_kind}</span></td>
              <td>{nodes[edge.target_entity_id]?.name || edge.target_entity_id}</td>
              <td><details className="graph-id-details"><summary>Show identifier</summary><code>{edge.logical_id}</code></details></td>
            </tr>)}</tbody>
          </table>
        )}
      </div>
      <nav className="graph-pagination" aria-label={`${activeTab} pagination`}>
        <span aria-live="polite">{records.length ? `${start + 1}–${Math.min(start + PAGE_SIZE, records.length)}` : '0'} of {records.length} {activeTab}</span>
        <div className="graph-row-actions">
          <button type="button" className="graph-btn" disabled={page === 1} onClick={() => changePage(page - 1)}>Previous</button>
          <span>Page {page} of {pageCount}</span>
          <button type="button" className="graph-btn" disabled={page === pageCount} onClick={() => changePage(page + 1)}>Next</button>
        </div>
      </nav>
    </section>
  );
}

export default GraphListView;
