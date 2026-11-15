/**
 * ELK Layout Web Worker (Frontend)
 *
 * Runs deterministic directed-graph layout calculations completely off the main UI thread.
 * Uses bundled ELK without nested worker spawning.
 */
import ELK from 'elkjs/lib/elk.bundled.js';

const elk = new ELK();

const DEFAULT_NODE_WIDTH = 220;
const DEFAULT_NODE_HEIGHT = 80;

self.addEventListener('message', async (event) => {
  const data = event.data;
  if (!data || data.type !== 'layout') {
    return;
  }

  const {
    protocolVersion = 1,
    requestId,
    contextKey,
    generationId,
    graphRevision,
    nodes = [],
    edges = [],
    options = {},
  } = data;

  try {
    // Sort nodes and edges lexically by stable UUID to ensure deterministic calculation
    const sortedNodes = [...nodes].sort((a, b) => String(a.id).localeCompare(String(b.id)));
    const sortedEdges = [...edges].sort((a, b) => String(a.id).localeCompare(String(b.id)));

    // Construct ELK graph definition
    const elkGraph = {
      id: 'root',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': options.direction || 'DOWN',
        'elk.edgeRouting': 'ORTHOGONAL',
        'elk.layered.deterministicModelOrder': 'true',
        'elk.randomSeed': '42',
        'elk.spacing.nodeNode': '40',
        'elk.layered.spacing.nodeNodeBetweenLayers': '60',
      },
      children: sortedNodes.map((n) => ({
        id: String(n.id),
        width: typeof n.width === 'number' ? n.width : DEFAULT_NODE_WIDTH,
        height: typeof n.height === 'number' ? n.height : DEFAULT_NODE_HEIGHT,
      })),
      edges: sortedEdges.map((e) => ({
        id: String(e.id),
        sources: [String(e.source || e.source_entity_id)],
        targets: [String(e.target || e.target_entity_id)],
      })),
    };

    const layoutResult = await elk.layout(elkGraph);

    // Extract positioned node coordinates
    const positions = {};
    if (Array.isArray(layoutResult.children)) {
      for (const child of layoutResult.children) {
        positions[child.id] = {
          x: child.x || 0,
          y: child.y || 0,
          width: child.width || DEFAULT_NODE_WIDTH,
          height: child.height || DEFAULT_NODE_HEIGHT,
        };
      }
    }

    // Extract edge routing points if calculated
    const edgeRoutes = {};
    if (Array.isArray(layoutResult.edges)) {
      for (const edge of layoutResult.edges) {
        edgeRoutes[edge.id] = edge.sections || [];
      }
    }

    self.postMessage({
      type: 'layout-success',
      protocolVersion,
      requestId,
      contextKey,
      generationId,
      graphRevision,
      positions,
      edgeRoutes,
    });
  } catch (err) {
    self.postMessage({
      type: 'layout-error',
      protocolVersion,
      requestId,
      contextKey,
      generationId,
      graphRevision,
      code: 'layout_failed',
      message: err?.message || 'ELK layout computation failed in worker',
    });
  }
});

