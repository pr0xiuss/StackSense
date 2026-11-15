/**
 * Architecture Graph Contracts, Vocabulary, and Guard Functions (Frontend)
 *
 * Defines frozen P4-Q1 / P4-D1 / P4-H1 wire schema contracts, consumer guards,
 * query bounds, dependency allowlists, and P4-U1 local layout protocol constants.
 */
import {
  ARCHITECTURE_ENTITY_KIND,
  ARCHITECTURE_ENTITY_KIND_LABELS,
  ARCHITECTURE_RELATIONSHIP_KIND,
  ARCHITECTURE_RELATIONSHIP_KIND_LABELS,
} from './architectureContracts.js';

// Re-export canonical architecture kinds and labels
export {
  ARCHITECTURE_ENTITY_KIND,
  ARCHITECTURE_ENTITY_KIND_LABELS,
  ARCHITECTURE_RELATIONSHIP_KIND,
  ARCHITECTURE_RELATIONSHIP_KIND_LABELS,
};

/**
 * Public Contract Versions
 */
export const PROJECTION_CONTRACT_VERSION = '1.0.0';
export const GRAPH_SCHEMA_VERSION = '1.0.0';
export const PROJECTOR_VERSION = '1.0.0';

/**
 * Public Projection Lifecycle States (frozen M1/M2/M3)
 */
export const PROJECTION_PUBLIC_STATUS = Object.freeze({
  PENDING: 'PENDING',
  RUNNING: 'RUNNING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  STALE: 'STALE',
});

/**
 * Internal Attempt States (frozen M1)
 */
export const PROJECTION_ATTEMPT_STATUS = Object.freeze({
  QUEUED: 'QUEUED',
  RUNNING: 'RUNNING',
  RETRYING: 'RETRYING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  SUPERSEDED: 'SUPERSEDED',
});

/**
 * Graph Query Health Status (frozen M3/P4-H1)
 */
export const GRAPH_QUERY_HEALTH_STATUS = Object.freeze({
  READY: 'ready',
  DEGRADED: 'degraded',
  UNAVAILABLE: 'unavailable',
});

/**
 * Frozen Backend Maxima (hard limits enforced by FastAPI / Neo4j)
 */
export const BACKEND_MAX_DEPTH = 5;
export const BACKEND_MAX_NODES = 500;
export const BACKEND_MAX_EDGES = 1000;
export const BACKEND_MAX_PATHS = 25;
export const BACKEND_MAX_TIMEOUT_SECONDS = 5;
export const BACKEND_MAX_PAGE_SIZE = 100;
export const BACKEND_MAX_CURSOR_LENGTH = 2048;

/**
 * Client Query Defaults (conservative bounds for initial and paginated queries)
 */
export const DEFAULT_NODE_LIMIT = 50;
export const DEFAULT_EDGE_LIMIT = 100;
export const DEFAULT_PAGE_SIZE = 50;
export const DEFAULT_DEPTH = 1;
export const DEFAULT_TIMEOUT_SECONDS = 2;
export const DEFAULT_PATH_MAX_DEPTH = 3;
export const DEFAULT_PATH_LIMIT = 5;

/**
 * Local Canvas & Retained Data Caps (P4-U1 invariant)
 */
export const CANVAS_MAX_NODES = 300;
export const CANVAS_MAX_EDGES = 600;

/**
 * Approved Non-Containment Dependency Relationship Kinds (12 approved kinds)
 * Note: 'contains' is strictly forbidden in dependency/dependent/path operations.
 */
export const DEPENDENCY_RELATIONSHIP_KINDS = Object.freeze([
  'depends_on',
  'imports',
  'calls',
  'exposes',
  'consumes',
  'produces',
  'connects_to',
  'persists_to',
  'uses',
  'extends',
  'implements',
  'routes_to',
]);

/**
 * Containment relationship kind (hierarchy only)
 */
export const CONTAINMENT_RELATIONSHIP_KIND = 'contains';

/**
 * Traversal directions
 */
export const NEIGHBORHOOD_DIRECTIONS = Object.freeze(['incoming', 'outgoing', 'both']);
export const CONTAINMENT_DIRECTIONS = Object.freeze(['parents', 'children', 'both']);

/**
 * P4-U1 Local Layout Protocol Constants
 */
export const LAYOUT_PROTOCOL_VERSION = 1;
export const DEFAULT_NODE_WIDTH = 220;
export const DEFAULT_NODE_HEIGHT = 80;
export const LAYOUT_WATCHDOG_TIMEOUT_MS = 10000;

/**
 * UUID v4 / standard hex pattern
 */
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Validate whether a string is a well-formed UUID.
 * @param {any} val
 * @returns {boolean}
 */
export function isValidUuid(val) {
  return typeof val === 'string' && UUID_REGEX.test(val.trim());
}

/**
 * Validate ProjectionCounts structure.
 * @param {any} counts
 * @returns {boolean}
 */
export function validateProjectionCounts(counts) {
  if (!counts || typeof counts !== 'object') return false;
  const requiredKeys = ['entities', 'relationships', 'evidence', 'unresolved', 'conflicts'];
  return requiredKeys.every(
    (k) => typeof counts[k] === 'number' && Number.isInteger(counts[k]) && counts[k] >= 0
  );
}

/**
 * Validate ProjectionStatusResponse structure.
 * @param {any} status
 * @returns {boolean}
 */
export function validateProjectionStatus(status) {
  if (!status || typeof status !== 'object') return false;
  if (!isValidUuid(status.project_id)) return false;
  if (!isValidUuid(status.architecture_version_id)) return false;
  if (status.resource_id && !isValidUuid(status.resource_id)) return false;
  if (!Object.values(PROJECTION_PUBLIC_STATUS).includes(status.status)) return false;
  if (status.active_generation_id && !isValidUuid(status.active_generation_id)) return false;
  if (status.counts && !validateProjectionCounts(status.counts)) return false;
  return true;
}

/**
 * Validate GraphReadScope structure.
 * @param {any} scope
 * @returns {boolean}
 */
export function validateGraphReadScope(scope) {
  if (!scope || typeof scope !== 'object') return false;
  if (!isValidUuid(scope.project_id)) return false;
  if (!isValidUuid(scope.architecture_version_id)) return false;
  if (!isValidUuid(scope.generation_id)) return false;
  if (!Object.values(PROJECTION_PUBLIC_STATUS).includes(scope.resource_state)) return false;
  if (scope.counts && !validateProjectionCounts(scope.counts)) return false;
  return true;
}

/**
 * Validate GraphNode wire record.
 * @param {any} node
 * @returns {boolean}
 */
export function validateGraphNode(node) {
  if (!node || typeof node !== 'object') return false;
  if (!isValidUuid(node.architecture_entity_id)) return false;
  if (typeof node.logical_id !== 'string' || !node.logical_id) return false;
  if (typeof node.canonical_kind !== 'string' || !node.canonical_kind) return false;
  if (typeof node.name !== 'string') return false;
  if (!Array.isArray(node.evidence_logical_ids)) return false;
  return true;
}

/**
 * Validate GraphEdge wire record.
 * @param {any} edge
 * @returns {boolean}
 */
export function validateGraphEdge(edge) {
  if (!edge || typeof edge !== 'object') return false;
  if (!isValidUuid(edge.architecture_relationship_id)) return false;
  if (typeof edge.logical_id !== 'string' || !edge.logical_id) return false;
  if (typeof edge.canonical_kind !== 'string' || !edge.canonical_kind) return false;
  if (!isValidUuid(edge.source_entity_id)) return false;
  if (!isValidUuid(edge.target_entity_id)) return false;
  if (!Array.isArray(edge.evidence_logical_ids)) return false;
  return true;
}

/**
 * Validate GraphSubgraph response envelope.
 * @param {any} subgraph
 * @returns {boolean}
 */
export function validateGraphSubgraph(subgraph) {
  if (!subgraph || typeof subgraph !== 'object') return false;
  if (!validateGraphReadScope(subgraph.scope)) return false;
  if (!Array.isArray(subgraph.nodes)) return false;
  if (!Array.isArray(subgraph.edges)) return false;
  if (!subgraph.nodes.every(validateGraphNode)) return false;
  if (!subgraph.edges.every(validateGraphEdge)) return false;
  if (typeof subgraph.truncated !== 'boolean') return false;
  if (subgraph.next_cursor !== undefined && subgraph.next_cursor !== null) {
    if (typeof subgraph.next_cursor !== 'string' || subgraph.next_cursor.length > BACKEND_MAX_CURSOR_LENGTH) {
      return false;
    }
  }
  return true;
}

/**
 * Validate GraphPathResult response envelope.
 * @param {any} pathResult
 * @returns {boolean}
 */
export function validateGraphPathResult(pathResult) {
  if (!pathResult || typeof pathResult !== 'object') return false;
  if (!validateGraphReadScope(pathResult.scope)) return false;
  if (!Array.isArray(pathResult.paths)) return false;
  for (const p of pathResult.paths) {
    if (!p || typeof p !== 'object') return false;
    if (!Array.isArray(p.nodes) || !p.nodes.every(validateGraphNode)) return false;
    if (!Array.isArray(p.edges) || !p.edges.every(validateGraphEdge)) return false;
    if (typeof p.hop_count !== 'number') return false;
  }
  if (typeof pathResult.truncated !== 'boolean') return false;
  return true;
}

/**
 * Validate GraphQueryHealthResponse.
 * @param {any} health
 * @returns {boolean}
 */
export function validateGraphQueryHealth(health) {
  if (!health || typeof health !== 'object') return false;
  return Object.values(GRAPH_QUERY_HEALTH_STATUS).includes(health.status);
}

