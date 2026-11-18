/**
 * Architecture Graph Reducer and State Management (Frontend)
 *
 * Implements pure P4-U1 state, atomic scope-aware merge, 300-node/600-edge cap checks,
 * referential integrity enforcement, and generation change invalidation.
 */
import {
  CANVAS_MAX_NODES,
  CANVAS_MAX_EDGES,
  PROJECTION_PUBLIC_STATUS,
  validateGraphSubgraph,
  validateGraphPathResult,
} from '../contracts/graphContracts.js';

export const GRAPH_ACTION_TYPES = Object.freeze({
  INITIALIZE_CONTEXT: 'INITIALIZE_CONTEXT',
  SET_VERSION_VALIDATED: 'SET_VERSION_VALIDATED',
  SET_CONTEXT_ERROR: 'SET_CONTEXT_ERROR',
  UPDATE_PROJECTION_STATUS: 'UPDATE_PROJECTION_STATUS',
  MERGE_SUBGRAPH: 'MERGE_SUBGRAPH',
  MERGE_PATHS: 'MERGE_PATHS',
  SET_NODE_DETAIL: 'SET_NODE_DETAIL',
  SELECT_NODE: 'SELECT_NODE',
  SELECT_EDGE: 'SELECT_EDGE',
  SET_PATH_ENDPOINTS: 'SET_PATH_ENDPOINTS',
  START_OPERATION: 'START_OPERATION',
  FAIL_OPERATION: 'FAIL_OPERATION',
  CLEAR_EXPLORATION: 'CLEAR_EXPLORATION',
  RELOAD_VERSION: 'RELOAD_VERSION',
});

/**
 * Create initial P4-U1 graph state.
 * @param {object} [context]
 * @returns {object}
 */
export function createInitialGraphState(context = {}) {
  return {
    context: {
      projectId: context.projectId || null,
      repositoryId: context.repositoryId || null,
      analysisId: context.analysisId || null,
      versionId: context.versionId || null,
    },
    contextValidated: false,
    version: null,
    contextError: null,

    // Public lifecycle status & accepted generation
    status: null,
    activeGenerationId: null,

    // Graph maps keyed by stable UUID
    nodes: {}, // architecture_entity_id -> GraphNode
    edges: {}, // architecture_relationship_id -> GraphEdge

    // Retained counts and cap state
    loadedNodeCount: 0,
    loadedEdgeCount: 0,
    isCapReached: false,
    capMessage: null,

    // Operation tracking by operation key
    operations: {}, // opKey -> { mode, inFlight, cursor, error, fingerprint }

    // Selection state
    selectedNodeId: null,
    selectedEdgeId: null,
    selectedNodeDetail: null,

    // Paths state
    pathSourceEntityId: null,
    pathTargetEntityId: null,
    pathResult: null,

    // Out-of-date banner when generation changes on rebuild
    isOutOfDate: false,
    generationChangeMessage: null,

    // Local request epoch & revision
    requestEpoch: 0,
    graphRevision: 0,
    error: null,
  };
}

/**
 * Pure reducer for Architecture Explorer state.
 * @param {object} state
 * @param {object} action
 * @returns {object}
 */
export function architectureGraphReducer(state, action) {
  switch (action.type) {
    case GRAPH_ACTION_TYPES.INITIALIZE_CONTEXT: {
      const nextContext = {
        projectId: action.payload.projectId,
        repositoryId: action.payload.repositoryId,
        analysisId: action.payload.analysisId,
        versionId: action.payload.versionId,
      };
      return {
        ...createInitialGraphState(nextContext),
        requestEpoch: state.requestEpoch + 1,
      };
    }

    case GRAPH_ACTION_TYPES.SET_VERSION_VALIDATED: {
      return {
        ...state,
        version: action.payload.version,
        contextValidated: true,
        contextError: null,
      };
    }

    case GRAPH_ACTION_TYPES.SET_CONTEXT_ERROR: {
      return {
        ...state,
        contextError: action.payload.error,
        contextValidated: false,
      };
    }

    case GRAPH_ACTION_TYPES.UPDATE_PROJECTION_STATUS: {
      const nextStatus = action.payload.status;
      const nextActiveGen = nextStatus?.active_generation_id || null;

      // Detect if generation changed while we were displaying an older generation
      let isOutOfDate = state.isOutOfDate;
      let generationChangeMessage = state.generationChangeMessage;

      if (
        state.activeGenerationId &&
        nextActiveGen &&
        state.activeGenerationId !== nextActiveGen &&
        (state.loadedNodeCount > 0 || state.loadedEdgeCount > 0)
      ) {
        isOutOfDate = true;
        generationChangeMessage =
          'A newly published projection generation is available for this architecture version. Existing view is frozen.';
      }

      return {
        ...state,
        status: nextStatus,
        activeGenerationId: isOutOfDate ? state.activeGenerationId : (nextActiveGen || state.activeGenerationId),
        isOutOfDate,
        generationChangeMessage,
      };
    }

    case GRAPH_ACTION_TYPES.START_OPERATION: {
      const { opKey, mode, fingerprint } = action.payload;
      return {
        ...state,
        operations: {
          ...state.operations,
          [opKey]: {
            ...(state.operations[opKey] || {}),
            mode,
            fingerprint,
            inFlight: true,
            error: null,
          },
        },
      };
    }

    case GRAPH_ACTION_TYPES.FAIL_OPERATION: {
      const { opKey, error } = action.payload;
      const errorMsg = typeof error === 'string' ? error : (error?.message || 'Operation failed');
      const isCursorExpired =
        errorMsg.toLowerCase().includes('cursor') || error?.status === 410;

      return {
        ...state,
        error: errorMsg,
        operations: {
          ...state.operations,
          [opKey]: {
            ...(state.operations[opKey] || {}),
            inFlight: false,
            error: errorMsg,
            ...(isCursorExpired ? { cursor: null } : {}),
          },
        },
      };
    }

    case GRAPH_ACTION_TYPES.MERGE_SUBGRAPH: {
      const { subgraph, opKey } = action.payload;
      if (!validateGraphSubgraph(subgraph)) {
        return {
          ...state,
          error: 'Received invalid graph subgraph payload from server.',
        };
      }

      // 1. Assert exact scope match
      const scope = subgraph.scope;
      if (
        scope.project_id !== state.context.projectId ||
        scope.architecture_version_id !== state.context.versionId
      ) {
        return {
          ...state,
          error: 'Scope mismatch: subgraph belongs to a different project or version.',
        };
      }

      // If we have an accepted active generation, assert it matches
      if (state.activeGenerationId && scope.generation_id !== state.activeGenerationId) {
        return {
          ...state,
          isOutOfDate: true,
          generationChangeMessage: 'Received subgraph for a different generation. View frozen.',
        };
      }

      const activeGen = state.activeGenerationId || scope.generation_id;

      // 2. Compute candidate union of nodes
      const candidateNodes = { ...state.nodes };
      for (const node of subgraph.nodes) {
        const id = node.architecture_entity_id;
        if (candidateNodes[id]) {
          // Verify identical or safe dedup
          const existing = candidateNodes[id];
          if (existing.canonical_kind !== node.canonical_kind || existing.logical_id !== node.logical_id) {
            return {
              ...state,
              error: `Conflict detected for entity ${id}: divergent metadata for same UUID.`,
            };
          }
        } else {
          candidateNodes[id] = node;
        }
      }

      // 3. Compute candidate union of edges
      const candidateEdges = { ...state.edges };
      for (const edge of subgraph.edges) {
        const id = edge.architecture_relationship_id;
        if (candidateEdges[id]) {
          const existing = candidateEdges[id];
          if (existing.canonical_kind !== edge.canonical_kind || existing.logical_id !== edge.logical_id) {
            return {
              ...state,
              error: `Conflict detected for relationship ${id}: divergent metadata for same UUID.`,
            };
          }
        } else {
          candidateEdges[id] = edge;
        }
      }

      const candidateNodeCount = Object.keys(candidateNodes).length;
      const candidateEdgeCount = Object.keys(candidateEdges).length;

      // 4. Enforce 300 nodes / 600 edges cap atomically
      if (candidateNodeCount > CANVAS_MAX_NODES || candidateEdgeCount > CANVAS_MAX_EDGES) {
        return {
          ...state,
          isCapReached: true,
          capMessage: `Canvas cap reached (${CANVAS_MAX_NODES} nodes, ${CANVAS_MAX_EDGES} edges). Additional elements were withheld to protect browser performance.`,
          operations: opKey
            ? {
              ...state.operations,
              [opKey]: {
                ...(state.operations[opKey] || {}),
                inFlight: false,
                // Retain previous cursor so user can retry or clear
              },
            }
            : state.operations,
        };
      }

      // 5. Enforce referential integrity: every edge endpoint must be in candidateNodes
      for (const edge of Object.values(candidateEdges)) {
        if (!candidateNodes[edge.source_entity_id] || !candidateNodes[edge.target_entity_id]) {
          return {
            ...state,
            error: `Referential integrity violation: edge ${edge.architecture_relationship_id} references endpoints not present in the graph.`,
          };
        }
      }

      // 6. Successful atomic merge!
      const nextOperations = { ...state.operations };
      if (opKey) {
        nextOperations[opKey] = {
          ...(nextOperations[opKey] || {}),
          inFlight: false,
          cursor: subgraph.next_cursor || null,
          error: null,
        };
      }

      const hasTopologyChange =
        candidateNodeCount !== state.loadedNodeCount || candidateEdgeCount !== state.loadedEdgeCount;

      return {
        ...state,
        activeGenerationId: activeGen,
        nodes: candidateNodes,
        edges: candidateEdges,
        loadedNodeCount: candidateNodeCount,
        loadedEdgeCount: candidateEdgeCount,
        operations: nextOperations,
        graphRevision: hasTopologyChange ? state.graphRevision + 1 : state.graphRevision,
        error: null,
      };
    }

    case GRAPH_ACTION_TYPES.MERGE_PATHS: {
      const { pathResult } = action.payload;
      if (!validateGraphPathResult(pathResult)) {
        return {
          ...state,
          error: 'Received invalid path result payload from server.',
        };
      }

      const candidateNodes = { ...state.nodes };
      const candidateEdges = { ...state.edges };

      for (const p of pathResult.paths) {
        for (const n of p.nodes) {
          candidateNodes[n.architecture_entity_id] = n;
        }
        for (const e of p.edges) {
          candidateEdges[e.architecture_relationship_id] = e;
        }
      }

      const candidateNodeCount = Object.keys(candidateNodes).length;
      const candidateEdgeCount = Object.keys(candidateEdges).length;

      if (candidateNodeCount > CANVAS_MAX_NODES || candidateEdgeCount > CANVAS_MAX_EDGES) {
        return {
          ...state,
          isCapReached: true,
          capMessage: `Canvas cap reached (${CANVAS_MAX_NODES} nodes, ${CANVAS_MAX_EDGES} edges). Path results could not be merged.`,
        };
      }

      return {
        ...state,
        nodes: candidateNodes,
        edges: candidateEdges,
        loadedNodeCount: candidateNodeCount,
        loadedEdgeCount: candidateEdgeCount,
        pathResult,
        graphRevision: state.graphRevision + 1,
        error: null,
      };
    }

    case GRAPH_ACTION_TYPES.SET_NODE_DETAIL: {
      return {
        ...state,
        selectedNodeDetail: action.payload.detail,
      };
    }

    case GRAPH_ACTION_TYPES.SELECT_NODE: {
      const nodeId = action.payload.nodeId;
      return {
        ...state,
        selectedNodeId: nodeId,
        selectedEdgeId: null,
        selectedNodeDetail: state.nodes[nodeId] || null,
      };
    }

    case GRAPH_ACTION_TYPES.SELECT_EDGE: {
      const edgeId = action.payload.edgeId;
      return {
        ...state,
        selectedEdgeId: edgeId,
        selectedNodeId: null,
        selectedNodeDetail: null,
      };
    }

    case GRAPH_ACTION_TYPES.SET_PATH_ENDPOINTS: {
      return {
        ...state,
        pathSourceEntityId: action.payload.sourceEntityId,
        pathTargetEntityId: action.payload.targetEntityId,
      };
    }

    case GRAPH_ACTION_TYPES.CLEAR_EXPLORATION: {
      return {
        ...state,
        nodes: {},
        edges: {},
        loadedNodeCount: 0,
        loadedEdgeCount: 0,
        isCapReached: false,
        capMessage: null,
        operations: {},
        selectedNodeId: null,
        selectedEdgeId: null,
        selectedNodeDetail: null,
        pathResult: null,
        graphRevision: state.graphRevision + 1,
        error: null,
      };
    }

    case GRAPH_ACTION_TYPES.RELOAD_VERSION: {
      // Clear data and accept new active generation
      const newActiveGen = state.status?.active_generation_id || null;
      return {
        ...createInitialGraphState(state.context),
        version: state.version,
        contextValidated: true,
        status: state.status,
        activeGenerationId: newActiveGen,
        requestEpoch: state.requestEpoch + 1,
        graphRevision: state.graphRevision + 1,
      };
    }

    default:
      return state;
  }
}

