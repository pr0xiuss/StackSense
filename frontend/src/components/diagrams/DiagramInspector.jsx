import React, { useState } from 'react';

export function DiagramInspector({ selection, spec, members, busy, onClose, onFocus, onRequestMembers }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const node = spec.nodes.find(n => n.entity.id === selection?.id);
  if (!node) return <aside className="ss-diagram-inspector"><h3>Architecture details</h3><p>Select an element to inspect its canonical status and evidence.</p></aside>;
  return <aside className="ss-diagram-inspector" aria-label="Selected element">
    <div className="ss-diagram-heading"><h3>{node.name}</h3><button onClick={onClose} aria-label="Close inspector">×</button></div>
    <p>{node.kind} · <strong>{node.status}</strong></p>
    <div className="ss-diagram-actions"><button onClick={() => onFocus(node.id)}>Focus on map</button><button disabled={busy} onClick={() => { setShowEvidence(true); onRequestMembers(); }}>Load evidence ({node.evidence.length})</button></div>
    <p className="ss-diagram-muted">Static evidence, not a runtime assertion.</p>
    <details><summary>Canonical identifier</summary><code>{node.entity.logical_id}</code></details>
    <p>{node.namespace.join(' / ')}</p>
    {showEvidence && <section aria-label="Evidence"><h4>Evidence</h4>{busy && <p role="status">Loading evidence…</p>}
      {members?.items.map(item => <details key={item.record.id}><summary>{item.record.record_type} · {item.record.id.slice(0, 8)}</summary><code>{item.record.logical_id}</code>{item.reason && <p>{item.reason}</p>}</details>)}
      {members && <p>{members.items.length} of {members.total} records in this page</p>}
      {members?.next_cursor && <button disabled={busy} onClick={() => onRequestMembers(members.next_cursor)}>Next evidence page</button>}
      {members && members.total === 0 && <p>No attached evidence.</p>}
    </section>}
  </aside>;
}
