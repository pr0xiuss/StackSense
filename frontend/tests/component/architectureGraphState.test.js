import { describe, it, expect } from 'vitest';
import {
  createInitialGraphState,
  architectureGraphReducer,
  GRAPH_ACTION_TYPES,
} from '../../src/hooks/architectureGraphState.js';
import { CANVAS_MAX_NODES, CANVAS_MAX_EDGES } from '../../src/contracts/graphContracts.js';

describe('Architecture Graph State & Reducer', () => {
  const testContext = {
    projectId: '11111111-1111-1111-1111-111111111111',
    repositoryId: '22222222-2222-2222-2222-222222222222',
    analysisId: '33333333-3333-3333-3333-333333333333',
    versionId: '44444444-4444-4444-4444-444444444444',
  };

  const genId1 = '55555555-5555-5555-5555-555555555555';
  const genId2 = '66666666-6666-6666-6666-666666666666';

  it('creates initial graph state with zero loaded counts and clean context', () => {
    const state = createInitialGraphState(testContext);
    expect(state.context).toEqual(testContext);
    expect(state.contextValidated).toBe(false);
    expect(state.loadedNodeCount).toBe(0);
    expect(state.loadedEdgeCount).toBe(0);
    expect(state.isCapReached).toBe(false);
    expect(state.isOutOfDate).toBe(false);
    expect(state.requestEpoch).toBe(0);
  });

  it('initializes context, resets data, and increments request epoch', () => {
    let state = createInitialGraphState(testContext);
    state = { ...state, loadedNodeCount: 5, nodes: { a: {} } };

    const newContext = { ...testContext, versionId: '99999999-9999-9999-9999-999999999999' };
    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.INITIALIZE_CONTEXT,
      payload: newContext,
    });

    expect(state.context.versionId).toBe('99999999-9999-9999-9999-999999999999');
    expect(state.loadedNodeCount).toBe(0);
    expect(state.nodes).toEqual({});
    expect(state.requestEpoch).toBe(1);
  });

  it('sets version validated and context error correctly', () => {
    let state = createInitialGraphState(testContext);
    const mockVer = { id: testContext.versionId, sequence_number: 1 };

    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.SET_VERSION_VALIDATED,
      payload: { version: mockVer },
    });
    expect(state.contextValidated).toBe(true);
    expect(state.version).toEqual(mockVer);

    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.SET_CONTEXT_ERROR,
      payload: { error: 'Context chain mismatch' },
    });
    expect(state.contextValidated).toBe(false);
    expect(state.contextError).toBe('Context chain mismatch');
  });

  it('detects when projection active generation changes and marks view out of date', () => {
    let state = createInitialGraphState(testContext);
    state = {
      ...state,
      activeGenerationId: genId1,
      loadedNodeCount: 1,
      nodes: { 'n-1': {} },
    };

    // Update with same generation
    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.UPDATE_PROJECTION_STATUS,
      payload: { status: { active_generation_id: genId1, status: 'COMPLETED' } },
    });
    expect(state.isOutOfDate).toBe(false);

    // Update with new generation while older data is on screen
    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.UPDATE_PROJECTION_STATUS,
      payload: { status: { active_generation_id: genId2, status: 'COMPLETED' } },
    });
    expect(state.isOutOfDate).toBe(true);
    expect(state.generationChangeMessage).toContain('newly published projection generation is available');
    expect(state.activeGenerationId).toBe(genId1); // Retained previous generation view
  });

  it('rejects subgraph merge with scope mismatch', () => {
    let state = createInitialGraphState(testContext);
    const badSubgraph = {
      scope: {
        project_id: '99999999-9999-9999-9999-999999999999', // wrong project
        architecture_version_id: testContext.versionId,
        generation_id: genId1,
        resource_state: 'COMPLETED',
      },
      nodes: [],
      edges: [],
      truncated: false,
    };

    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
      payload: { subgraph: badSubgraph },
    });
    expect(state.error).toContain('Scope mismatch');
  });

  it('merges valid subgraph atomically and increments graphRevision', () => {
    let state = createInitialGraphState(testContext);

    const nodeA = {
      architecture_entity_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      logical_id: 'ent:a',
      canonical_kind: 'service',
      name: 'A',
      evidence_logical_ids: [],
    };
    const nodeB = {
      architecture_entity_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      logical_id: 'ent:b',
      canonical_kind: 'database',
      name: 'B',
      evidence_logical_ids: [],
    };
    const edgeAB = {
      architecture_relationship_id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
      logical_id: 'rel:a-b',
      canonical_kind: 'persists_to',
      source_entity_id: nodeA.architecture_entity_id,
      target_entity_id: nodeB.architecture_entity_id,
      evidence_logical_ids: [],
    };

    const subgraph = {
      scope: {
        project_id: testContext.projectId,
        architecture_version_id: testContext.versionId,
        generation_id: genId1,
        resource_state: 'COMPLETED',
      },
      nodes: [nodeA, nodeB],
      edges: [edgeAB],
      truncated: false,
      next_cursor: 'cur-1',
    };

    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
      payload: { subgraph, opKey: 'window-op' },
    });

    expect(state.error).toBeNull();
    expect(state.loadedNodeCount).toBe(2);
    expect(state.loadedEdgeCount).toBe(1);
    expect(state.nodes[nodeA.architecture_entity_id]).toEqual(nodeA);
    expect(state.edges[edgeAB.architecture_relationship_id]).toEqual(edgeAB);
    expect(state.operations['window-op'].cursor).toBe('cur-1');
    expect(state.graphRevision).toBe(1);

    // Dedup identical nodes and edges
    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
      payload: { subgraph, opKey: 'window-op' },
    });
    expect(state.loadedNodeCount).toBe(2);
    expect(state.loadedEdgeCount).toBe(1);
  });

  it('rejects conflicting metadata for same UUID without modifying state', () => {
    let state = createInitialGraphState(testContext);

    const nodeA = {
      architecture_entity_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      logical_id: 'ent:a',
      canonical_kind: 'service',
      name: 'A',
      evidence_logical_ids: [],
    };

    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
      payload: {
        subgraph: {
          scope: {
            project_id: testContext.projectId,
            architecture_version_id: testContext.versionId,
            generation_id: genId1,
            resource_state: 'COMPLETED',
          },
          nodes: [nodeA],
          edges: [],
          truncated: false,
        },
      },
    });

    // Same UUID but different canonical_kind
    const conflictingNode = {
      ...nodeA,
      canonical_kind: 'database',
    };

    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
      payload: {
        subgraph: {
          scope: {
            project_id: testContext.projectId,
            architecture_version_id: testContext.versionId,
            generation_id: genId1,
            resource_state: 'COMPLETED',
          },
          nodes: [conflictingNode],
          edges: [],
          truncated: false,
        },
      },
    });

    expect(state.error).toContain('Conflict detected for entity');
    expect(state.nodes[nodeA.architecture_entity_id].canonical_kind).toBe('service'); // Untouched
  });

  it('rejects dangling edge failing referential integrity', () => {
    let state = createInitialGraphState(testContext);

    const nodeA = {
      architecture_entity_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      logical_id: 'ent:a',
      canonical_kind: 'service',
      name: 'A',
      evidence_logical_ids: [],
    };
    const danglingEdge = {
      architecture_relationship_id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
      logical_id: 'rel:a-missing',
      canonical_kind: 'calls',
      source_entity_id: nodeA.architecture_entity_id,
      target_entity_id: '99999999-9999-9999-9999-999999999999', // Missing target!
      evidence_logical_ids: [],
    };

    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
      payload: {
        subgraph: {
          scope: {
            project_id: testContext.projectId,
            architecture_version_id: testContext.versionId,
            generation_id: genId1,
            resource_state: 'COMPLETED',
          },
          nodes: [nodeA],
          edges: [danglingEdge],
          truncated: false,
        },
      },
    });

    expect(state.error).toContain('Referential integrity violation');
    expect(state.loadedNodeCount).toBe(0);
    expect(state.loadedEdgeCount).toBe(0);
  });

  it('enforces 300-node / 600-edge canvas cap atomically', () => {
    let state = createInitialGraphState(testContext);

    // Create 301 nodes
    const excessiveNodes = [];
    for (let i = 0; i <= CANVAS_MAX_NODES; i++) {
      const hex = i.toString(16).padStart(12, '0');
      excessiveNodes.push({
        architecture_entity_id: `00000000-0000-0000-0000-${hex}`,
        logical_id: `ent:${i}`,
        canonical_kind: 'module',
        name: `Node ${i}`,
        evidence_logical_ids: [],
      });
    }

    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
      payload: {
        subgraph: {
          scope: {
            project_id: testContext.projectId,
            architecture_version_id: testContext.versionId,
            generation_id: genId1,
            resource_state: 'COMPLETED',
          },
          nodes: excessiveNodes,
          edges: [],
          truncated: true,
        },
        opKey: 'huge-op',
      },
    });

    expect(state.isCapReached).toBe(true);
    expect(state.capMessage).toContain('Canvas cap reached');
    expect(state.loadedNodeCount).toBe(0); // Atomic rejection: none merged
  });

  it('handles selections, clearing, and version reload', () => {
    let state = createInitialGraphState(testContext);
    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.SELECT_NODE,
      payload: { nodeId: 'node-1' },
    });
    expect(state.selectedNodeId).toBe('node-1');
    expect(state.selectedEdgeId).toBeNull();

    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.SELECT_EDGE,
      payload: { edgeId: 'edge-1' },
    });
    expect(state.selectedEdgeId).toBe('edge-1');
    expect(state.selectedNodeId).toBeNull();

    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.CLEAR_EXPLORATION,
    });
    expect(state.selectedNodeId).toBeNull();
    expect(state.selectedEdgeId).toBeNull();
    expect(state.loadedNodeCount).toBe(0);

    state = architectureGraphReducer(state, {
      type: GRAPH_ACTION_TYPES.RELOAD_VERSION,
    });
    expect(state.requestEpoch).toBe(1);
    expect(state.isOutOfDate).toBe(false);
  });
});

