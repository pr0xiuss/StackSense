import React, { useEffect, useState } from 'react';
import '../../styles/graph.css';

function EvidenceReferences({ references }) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 5;
  const pageCount = Math.max(1, Math.ceil(references.length / pageSize));
  return <section className="graph-evidence">
    <button type="button" className="graph-btn graph-btn-ghost" aria-expanded={open}
      onClick={() => setOpen(!open)}>Attached Evidence ({references.length}): {open ? 'Hide' : 'Show'}</button>
    {open && <div>
      {!references.length && <p>No direct evidence records attached.</p>}
      <ol start={(page - 1) * pageSize + 1}>
        {references.slice((page - 1) * pageSize, page * pageSize).map((id) =>
          <li key={id}><details><summary>Evidence reference</summary><code>{id}</code></details></li>)}
      </ol>
      {references.length > pageSize && <nav className="graph-pagination" aria-label="Evidence pagination">
        <button className="graph-btn" type="button" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous evidence</button>
        <span aria-live="polite">Page {page} of {pageCount}</span>
        <button className="graph-btn" type="button" disabled={page === pageCount} onClick={() => setPage(page + 1)}>Next evidence</button>
      </nav>}
    </div>}
  </section>;
}

export function GraphInspector({
  selectedNode, selectedEdge, version, nodes = {}, onDeselect,
  onExpandNeighborhood, onExpandDependencies, onExpandDependents, onExpandContainment,
  isOperationInFlight = false,
}) {
  useEffect(() => {
    if (!selectedNode && !selectedEdge) return;
    const close = (event) => { if (event.key === 'Escape') { event.preventDefault(); onDeselect?.(); } };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [selectedNode, selectedEdge, onDeselect]);

  const selected = selectedNode || selectedEdge;
  if (!selected) return <aside className="graph-inspector-panel" data-testid="graph-inspector">
    <h3>Architecture Summary</h3>
    {version ? <dl className="graph-properties">
      <dt>Version ID:</dt><dd className="mono-cell">{version.id}</dd>
      <dt>Schema:</dt><dd>v{version.architecture_schema_version || '1.0.0'}</dd>
      <dt>Entities:</dt><dd>{version.entity_count ?? 0}</dd>
      <dt>Relationships:</dt><dd>{version.relationship_count ?? 0}</dd>
      <dt>Evidence:</dt><dd>{version.evidence_count ?? 0}</dd>
      <dt>Unresolved:</dt><dd>{version.unresolved_relationship_count ?? 0}</dd>
      <dt>Conflicts:</dt><dd>{version.conflict_count ?? 0}</dd>
    </dl> : <p>No architecture version loaded.</p>}
    <p className="graph-list-note">Select a node to highlight its direct connections and explore one neighborhood at a time.</p>
  </aside>;

  const actions = [
    [onExpandNeighborhood, 'Expand Neighborhood (1 hop)', `Expand Neighborhood of ${selected.name}`],
    [onExpandDependencies, 'Explore Dependencies (Outgoing)', `Explore Dependencies of ${selected.name}`],
    [onExpandDependents, 'Explore Dependents (Incoming)', `Explore Dependents of ${selected.name}`],
    [onExpandContainment, 'Explore Containment (Hierarchy)', `Explore Containment of ${selected.name}`],
  ];
  return <aside className="graph-inspector-panel" data-testid="graph-inspector">
    <header className="graph-inspector-heading">
      <div><span className="arch-node-kind-badge">{selectedNode ? selected.canonical_kind : 'Relationship'}</span>
        <h3>{selectedNode ? selected.name : selected.canonical_kind}</h3></div>
      {onDeselect && <button type="button" className="graph-btn graph-btn-ghost" onClick={onDeselect} aria-label="Close inspector">×</button>}
    </header>
    {selectedNode && <section className="graph-inspector-actions" aria-label="Explore Relationships">
      {actions.filter(([callback]) => callback).map(([callback, label, accessibleLabel]) =>
        <button type="button" key={label} className="graph-btn" disabled={isOperationInFlight}
          aria-label={accessibleLabel} onClick={() => callback(selected.architecture_entity_id)}>{label}</button>)}
    </section>}
    <dl className="graph-properties">
      {selectedNode ? <>
        <dt>Status:</dt><dd className="graph-cell-status" data-supported={['confirmed', 'supported'].includes(selected.fact_status?.toLowerCase())}>{selected.fact_status || 'UNKNOWN'}</dd>
        <dt>Namespace:</dt><dd>{selected.namespace || '—'}</dd>
      </> : <>
        <dt>Source:</dt><dd>{nodes[selected.source_entity_id]?.name || selected.source_entity_id}</dd>
        <dt>Target:</dt><dd>{nodes[selected.target_entity_id]?.name || selected.target_entity_id}</dd>
      </>}
    </dl>
    <details className="graph-id-details"><summary>Canonical identifiers</summary>
      <dl className="graph-properties"><dt>Logical ID:</dt><dd><code>{selected.logical_id}</code></dd>
        <dt>{selectedNode ? 'Entity ID:' : 'Relationship ID:'}</dt>
        <dd><code>{selected.architecture_entity_id || selected.architecture_relationship_id}</code></dd></dl>
    </details>
    <EvidenceReferences key={selected.architecture_entity_id || selected.architecture_relationship_id}
      references={Array.isArray(selected.evidence_logical_ids) ? selected.evidence_logical_ids : []} />
  </aside>;
}

export default GraphInspector;
