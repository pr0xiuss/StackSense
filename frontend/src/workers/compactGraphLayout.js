/**
 * Fold wide ELK layers into bounded rows. This changes presentation coordinates
 * only: every canonical node and directed edge remains unchanged. Keep ELK's
 * layer and within-layer order so dependent layers follow their predecessors.
 */
export function compactGraphLayers(children, columns = 4) {
  const ordered = [...children].sort((a, b) =>
    (a.y || 0) - (b.y || 0) || (a.x || 0) - (b.x || 0) ||
    (String(a.id) < String(b.id) ? -1 : String(a.id) > String(b.id) ? 1 : 0)
  );
  const layers = [];
  for (const node of ordered) {
    const last = layers[layers.length - 1];
    if (!last || Math.abs((last[0].y || 0) - (node.y || 0)) > 1) layers.push([node]);
    else last.push(node);
  }
  const positions = {};
  const width = Math.max(220, ...ordered.map((node) => node.width || 220));
  const height = Math.max(80, ...ordered.map((node) => node.height || 80));
  const usedColumns = Math.min(columns, ordered.length);
  let y = 24;
  for (const layer of layers) {
    for (let offset = 0; offset < layer.length; offset += columns) {
      const row = layer.slice(offset, offset + columns);
      const inset = (usedColumns - row.length) * (width + 40) / 2;
      row.forEach((node, column) => {
        positions[node.id] = { x: 24 + inset + column * (width + 40), y,
          width: node.width || 220, height: node.height || 80 };
      });
      y += height + 64;
    }
    y += 32;
  }
  return positions;
}
