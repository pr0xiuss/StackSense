/** Pure mapping of validated C2. Absolute geometry is converted exactly once. */
export function toReactFlow(spec, layout, viewState = {}) {
  const boxes = new Map([...layout.nodes, ...layout.groups].map(row => [row.id, row.box]));
  const groups = new Map(spec.groups.map(g => [g.id, g]));
  const collapsed = new Set(viewState.collapsed_groups ?? spec.groups.filter(g => g.collapsed_default).map(g => g.id));
  const hidden = id => {
    let group = groups.get(id)?.parent_group_id ?? spec.nodes.find(n => n.id === id)?.group_id;
    while (group) { if (collapsed.has(group)) return true; group = groups.get(group)?.parent_group_id; }
    return false;
  };
  const labels = new Map();
  for (const label of layout.labels) labels.set(label.owner_id, [...(labels.get(label.owner_id) || []), label]);
  const glyphs = new Map(layout.glyphs.map(g => [g.id, g]));
  const output = [];
  const added = new Set();
  function add(item, group) {
    if (added.has(item.id)) return;
    const parent = group ? item.parent_group_id : item.group_id;
    if (parent) add(groups.get(parent), true);
    const box = boxes.get(item.id), origin = parent ? boxes.get(parent) : { x: 0, y: 0 };
    const selected = !!viewState.selected_ref && viewState.selected_ref.id === item.entity?.id;
    output.push({
      id: item.id, type: group ? 'diagramGroup' : 'diagramNode',
      position: { x: (box.x - origin.x) / 1000, y: (box.y - origin.y) / 1000 },
      ...(parent ? { parentId: parent } : {}),
      width: box.width / 1000, height: box.height / 1000,
      style: { width: box.width / 1000, height: box.height / 1000 },
      draggable: false, connectable: false, selected: !!selected,
      hidden: hidden(item.id),
      data: { item, box, labels: labels.get(item.id) || [], glyphs, collapsed: collapsed.has(item.id), group },
    });
    added.add(item.id);
  }
  spec.groups.forEach(g => add(g, true)); spec.nodes.forEach(n => add(n, false));
  const routes = new Map(layout.routes.map(r => [r.edge_id, r]));
  return { nodes: output, edges: spec.edges.map(edge => ({
    id: edge.id, source: edge.source_visual_id, target: edge.target_visual_id,
    type: 'diagramEdge', hidden: hidden(edge.source_visual_id) || hidden(edge.target_visual_id),
    data: { item: edge, route: routes.get(edge.id), labels: labels.get(edge.id) || [], glyphs },
  })) };
}
