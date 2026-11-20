import React, { useCallback, useEffect, useRef, useState } from 'react';
import { DiagramCanvas } from './DiagramCanvas.jsx';
import { DiagramInspector } from './DiagramInspector.jsx';
import { useDiagramView } from '../../hooks/useDiagramView.js';
import { validateMemberPage } from '../../contracts/diagramContracts.js';
import '../../styles/diagrams.css';

export function DiagramView({ prepared, requestView, requestMembers, onSelect, onExport, onError }) {
  const view = useDiagramView(prepared, requestView, onError), { state } = view;
  const [tab, setTab] = useState('map'), [list, setList] = useState('entities'), [page, setPage] = useState(0), [query, setQuery] = useState('');
  const [members, setMembers] = useState(null), [membersBusy, setMembersBusy] = useState(false);
  const selectedKey = `${state.base_generation_id}:${state.selected_ref?.id ?? ''}`;
  const current = useRef(selectedKey); current.current = selectedKey;
  useEffect(() => { view.membersPending.current?.abort(); setMembers(null); setMembersBusy(false); }, [selectedKey]);
  useEffect(() => { setPage(0); }, [list, query, state.spec]);
  const select = useCallback(ref => { view.select(ref); onSelect?.(ref); }, [view.select, onSelect]);
  const focus = id => { setTab('map'); view.focus(id); };
  async function loadMembers(cursor = null) {
    if (!state.selected_ref) return;
    view.membersPending.current?.abort();
    const controller = new AbortController(); view.membersPending.current = controller;
    const expected = current.current;
    setMembersBusy(true);
    try {
      const result = await requestMembers({ generation_id: state.base_generation_id, group_id: null, entity_id: state.selected_ref.id, limit: 20, cursor }, controller.signal);
      if (controller.signal.aborted || expected !== current.current) return;
      setMembers(validateMemberPage(result, state.base_generation_id, state.base_digest, 20));
    } catch (error) {
      if (!controller.signal.aborted && expected === current.current) onError?.({ error: { code: 'diagram_internal_error', message: 'Evidence could not be loaded.', details: { dimension: null, actual: null, limit: null, request_id: null } } });
    } finally { if (!controller.signal.aborted && expected === current.current) setMembersBusy(false); }
  }
  if (state.error && !state.ready) return <section className="ss-diagram" role="alert">Diagram data could not be validated.</section>;
  if (!state.ready) return <section className="ss-diagram" role="status">Preparing diagram…</section>;
  const { spec, layout } = state;
  const records = list === 'entities' ? spec.nodes : spec.edges;
  const filtered = records.filter(row => (row.name || row.label).toLowerCase().includes(query.toLowerCase()));
  const rows = filtered.slice(page * 20, (page + 1) * 20);
  function expand() {
    if (!state.selected_ref) return;
    view.derive({ root_ids: [state.selected_ref.id], entity_kinds: [], statuses: [], relationship_kinds: [], include_contains: false, depth: 1, direction: 'outgoing', collapsed_group_ids: [], selected_entity_ids: [] });
  }
  return <section className="ss-diagram" aria-label="Diagram viewer" onKeyDown={e => { if (e.key === 'Escape') select(null); }}>
    <header className="ss-diagram-toolbar"><div><h2>{spec.template.replaceAll('_', ' ')}</h2><p>{spec.nodes.length} elements · {spec.edges.length} connectors · {spec.coverage.view_state.replaceAll('_', ' ')}</p></div>
      <div className="ss-diagram-actions"><button onClick={() => onExport?.('json')}>Export JSON</button><button onClick={() => onExport?.('svg')}>Export SVG</button></div>
    </header>
    <p className="ss-diagram-muted">{spec.legend.map(l => l.label).join(' · ')}{spec.coverage.reasons.length > 0 && ` · Omissions: ${spec.coverage.reasons.join(', ')}`}</p>
    <div role="tablist" aria-label="Diagram presentation" className="ss-diagram-tabs"><button role="tab" aria-selected={tab === 'map'} onClick={() => setTab('map')}>Diagram map</button><button role="tab" aria-selected={tab === 'list'} onClick={() => setTab('list')}>Structured list</button></div>
    {state.error && <p role="alert">The requested view could not be prepared. The previous view is retained.</p>}
    {state.busy && <p role="status">Preparing view…</p>}
    <div className="ss-diagram-map-layout" hidden={tab !== 'map'}><div>
      <div className="ss-diagram-actions"><button disabled={!state.selected_ref || state.busy} onClick={expand}>Focus neighborhood</button></div>
      {spec.nodes.length || spec.groups.length ? <DiagramCanvas spec={spec} layout={layout} viewState={state} onSelect={select} onFocus={view.focus} onToggleGroup={view.toggleGroup} /> : <div className="ss-diagram-empty">{spec.template === 'data_flow' ? 'No established static data flow in this view.' : 'No elements match this view.'}</div>}
    </div><DiagramInspector key={selectedKey} selection={state.selected_ref} spec={spec} members={members} busy={membersBusy} onClose={() => select(null)} onFocus={view.focus} onRequestMembers={loadMembers} /></div>
    {tab === 'list' && <div className="ss-diagram-list">
      <div className="ss-diagram-toolbar"><div className="ss-diagram-tabs"><button aria-pressed={list === 'entities'} onClick={() => setList('entities')}>Entities ({spec.nodes.length})</button><button aria-pressed={list === 'relationships'} onClick={() => setList('relationships')}>Relationships ({spec.edges.length})</button></div><label>Filter <input value={query} onChange={e => setQuery(e.target.value)} /></label></div>
      <p className="ss-diagram-muted">Browsing this bounded diagram, not the full repository.</p>
      <div className="ss-diagram-table-scroll"><table><thead><tr><th>Name / relationship</th><th>Kind / status</th><th>Canonical reference</th><th>Actions</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td>{row.name || row.label}</td><td>{row.kind || row.members[0]?.kind}<br />{row.status || row.members[0]?.status}</td><td><details><summary>Show identifier</summary><code>{row.entity?.logical_id || row.members.map(m => m.relationship.logical_id).join('\n')}</code></details></td><td><div className="ss-diagram-actions">{row.entity && <button onClick={() => select(row.entity)}>Select</button>}<button onClick={() => { if (row.entity) select(row.entity); focus(row.entity ? row.id : row.source_visual_id); }}>View on map</button></div></td></tr>)}</tbody></table></div>
      {filtered.length === 0 && <p>No matching records.</p>}
      <nav aria-label="Diagram list pagination" className="ss-diagram-actions"><button disabled={page === 0} onClick={() => setPage(p => p - 1)}>Previous</button><span>Page {page + 1} of {Math.max(1, Math.ceil(filtered.length / 20))}</span><button disabled={(page + 1) * 20 >= filtered.length} onClick={() => setPage(p => p + 1)}>Next</button></nav>
    </div>}
    <details className="ss-diagram-notice"><summary>Layout and font notices</summary><p>{layout.font_notice}</p>{layout.limitations.map(text => <p key={text}>{text}</p>)}</details>
  </section>;
}
