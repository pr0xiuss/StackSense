import React, { memo, useEffect, useMemo, useRef, useState } from 'react';
import { ReactFlow, ReactFlowProvider, Controls, Handle, Position, useReactFlow } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { toReactFlow } from '../../services/diagramAdapter.js';

function Labels({ labels, glyphs, origin = { x: 0, y: 0 } }) {
  return labels.map(label => <g key={label.id}><title>{label.original_text}</title>{label.glyphs.map((place, i) => {
    const glyph = glyphs.get(place.glyph_id);
    const d = glyph.commands.map(command => command.command + ' ' + command.operands.join(' ')).join(' ');
    return <path key={i} d={d} transform={`translate(${place.origin.x - origin.x} ${place.origin.y - origin.y})`} fill="currentColor" />;
  })}</g>);
}
export const DiagramNode = memo(function DiagramNode({ data, selected }) {
  const item = data.item;
  return <div className={`ss-diagram-node ${selected ? 'is-selected' : ''}`} style={{ width: data.box.width / 1000, height: data.box.height / 1000 }} role="button" tabIndex={0}
    aria-label={`${item.kind}: ${item.name}; ${item.status}`} onClick={e => { e.stopPropagation(); data.onSelect?.(item.entity); }} onDoubleClick={e => { e.stopPropagation(); data.onFocus?.(item.id); }}
    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); data.onSelect?.(item.entity); } if (e.key === 'Escape') data.onSelect?.(null); }}>
    <Handle type="target" position={Position.Top} isConnectable={false} /><Handle type="source" position={Position.Bottom} isConnectable={false} />
    <svg width="100%" height="100%" viewBox={`0 0 ${data.box.width} ${data.box.height}`} aria-hidden="true"><Labels labels={data.labels} glyphs={data.glyphs} origin={data.box} /></svg>
    <span className="ss-diagram-sr">{item.status}</span>
  </div>;
});
export const DiagramGroup = memo(function DiagramGroup({ data }) {
  return <div className="ss-diagram-group" style={{ width: data.box.width / 1000, height: data.box.height / 1000 }}>
    <svg width="100%" height="100%" viewBox={`0 0 ${data.box.width} ${data.box.height}`} aria-hidden="true"><Labels labels={data.labels} glyphs={data.glyphs} origin={data.box} /></svg>
    <button className="ss-diagram-group-toggle nodrag nopan" aria-label={`${data.collapsed ? 'Expand' : 'Collapse'} ${data.item.label}`} onClick={e => { e.stopPropagation(); data.onToggleGroup?.(data.item.id); }}>{data.collapsed ? '+' : '−'}</button>
    <Handle type="target" position={Position.Top} isConnectable={false} /><Handle type="source" position={Position.Bottom} isConnectable={false} />
  </div>;
});
export const DiagramEdge = memo(function DiagramEdge({ id, data }) {
  return <g aria-label={data.item.label}>
    <defs><marker id={`arrow-${id}`} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M 0 0 L 8 4 L 0 8" fill="#38bdf8" /></marker></defs>
    {data.route.sections.map((s, i) => <path key={i} d={'M ' + [s.start, ...s.bends, s.end].map(p => `${p.x / 1000} ${p.y / 1000}`).join(' L ')} fill="none" stroke="#38bdf8" strokeWidth="1.2" markerEnd={`url(#arrow-${id})`} />)}
    <g transform="scale(0.001)"><Labels labels={data.labels} glyphs={data.glyphs} /></g>
  </g>;
});
const nodeTypes = { diagramNode: DiagramNode, diagramGroup: DiagramGroup }, edgeTypes = { diagramEdge: DiagramEdge };
function Canvas({ spec, layout, viewState, onSelect, onFocus, onToggleGroup }) {
  const api = useReactFlow(), fitted = useRef(null), focused = useRef(null);
  const [initialized, setInitialized] = useState(false);
  const geometry = useMemo(() => {
    const result = toReactFlow(spec, layout, { collapsed_groups: viewState.collapsed_groups });
    result.nodes.forEach(n => { n.data = { ...n.data, onSelect, onFocus, onToggleGroup }; });
    return result;
  }, [spec, layout, viewState.collapsed_groups, onSelect, onFocus, onToggleGroup]);
  // Selection changes only the two affected node shells. Keep routes, prepared
  // glyph data and all other node data stable; never rebuild geometry on click.
  const mapped = useMemo(() => ({
    edges: geometry.edges,
    nodes: geometry.nodes.map(node => viewState.selected_ref?.id === node.data.item.entity?.id
      ? { ...node, selected: true } : node),
  }), [geometry, viewState.selected_ref]);
  const baseKey = `${viewState.base_generation_id}:${viewState.base_digest}`;
  useEffect(() => {
    if (!initialized) return;
    const focus = viewState.focus_visual_id;
    if (focus && focused.current !== focus) {
      const row = [...layout.nodes, ...layout.groups].find(n => n.id === focus.id);
      if (!row) return;
      focused.current = focus;
      api.setCenter((row.box.x + row.box.width / 2) / 1000, (row.box.y + row.box.height / 2) / 1000, { zoom: 1, duration: globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 0 : 200 });
      fitted.current = baseKey; return;
    }
    if (fitted.current !== baseKey) {
      fitted.current = baseKey;
      // A user selection before canvas initialization must not trigger a late fit.
      if (!viewState.selected_ref) api.fitView({ padding: 0.12, minZoom: 0.35, maxZoom: 1 });
    }
  }, [initialized, baseKey, layout, viewState.focus_visual_id, api]);
  return <ReactFlow nodes={mapped.nodes} edges={mapped.edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} nodesDraggable={false} nodesConnectable={false} nodesFocusable={false} edgesFocusable={false} elementsSelectable={false} minZoom={0.1} maxZoom={2} onInit={() => setInitialized(true)} onPaneClick={() => onSelect(null)}><Controls showInteractive={false} /></ReactFlow>;
}
export function DiagramCanvas(props) { return <div className="ss-diagram-canvas" aria-label="Architecture diagram"><ReactFlowProvider><Canvas {...props} /></ReactFlowProvider></div>; }
