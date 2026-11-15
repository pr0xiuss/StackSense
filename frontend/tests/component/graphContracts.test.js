import { describe, it, expect } from 'vitest';
import {
  PROJECTION_CONTRACT_VERSION,
  GRAPH_SCHEMA_VERSION,
  PROJECTOR_VERSION,
  PROJECTION_PUBLIC_STATUS,
  PROJECTION_ATTEMPT_STATUS,
  GRAPH_QUERY_HEALTH_STATUS,
  BACKEND_MAX_DEPTH,
  BACKEND_MAX_NODES,
  BACKEND_MAX_EDGES,
  BACKEND_MAX_PATHS,
  BACKEND_MAX_TIMEOUT_SECONDS,
  BACKEND_MAX_PAGE_SIZE,
  BACKEND_MAX_CURSOR_LENGTH,
  DEFAULT_NODE_LIMIT,
  DEFAULT_EDGE_LIMIT,
  DEFAULT_PAGE_SIZE,
  DEFAULT_DEPTH,
  DEFAULT_TIMEOUT_SECONDS,
  DEFAULT_PATH_MAX_DEPTH,
  DEFAULT_PATH_LIMIT,
  CANVAS_MAX_NODES,
  CANVAS_MAX_EDGES,
  DEPENDENCY_RELATIONSHIP_KINDS,
  CONTAINMENT_RELATIONSHIP_KIND,
  NEIGHBORHOOD_DIRECTIONS,
  CONTAINMENT_DIRECTIONS,
  LAYOUT_PROTOCOL_VERSION,
  DEFAULT_NODE_WIDTH,
  DEFAULT_NODE_HEIGHT,
  LAYOUT_WATCHDOG_TIMEOUT_MS,
  isValidUuid,
  validateProjectionCounts,
  validateProjectionStatus,
  validateGraphReadScope,
  validateGraphNode,
  validateGraphEdge,
  validateGraphSubgraph,
  validateGraphPathResult,
  validateGraphQueryHealth,
} from '../../src/contracts/graphContracts.js';

describe('Graph Contracts & Vocabulary', () => {
  it('exposes frozen public contract versions', () => {
    expect(PROJECTION_CONTRACT_VERSION).toBe('1.0.0');
    expect(GRAPH_SCHEMA_VERSION).toBe('1.0.0');
    expect(PROJECTOR_VERSION).toBe('1.0.0');
  });

  it('exposes exactly the frozen public and internal statuses', () => {
    expect(PROJECTION_PUBLIC_STATUS).toEqual({
      PENDING: 'PENDING',
      RUNNING: 'RUNNING',
      COMPLETED: 'COMPLETED',
      FAILED: 'FAILED',
      STALE: 'STALE',
    });

    expect(PROJECTION_ATTEMPT_STATUS).toEqual({
      QUEUED: 'QUEUED',
      RUNNING: 'RUNNING',
      RETRYING: 'RETRYING',
      COMPLETED: 'COMPLETED',
      FAILED: 'FAILED',
      SUPERSEDED: 'SUPERSEDED',
    });

    expect(GRAPH_QUERY_HEALTH_STATUS).toEqual({
      READY: 'ready',
      DEGRADED: 'degraded',
      UNAVAILABLE: 'unavailable',
    });
  });

  it('enforces backend maxima and client defaults', () => {
    expect(BACKEND_MAX_DEPTH).toBe(5);
    expect(BACKEND_MAX_NODES).toBe(500);
    expect(BACKEND_MAX_EDGES).toBe(1000);
    expect(BACKEND_MAX_PATHS).toBe(25);
    expect(BACKEND_MAX_TIMEOUT_SECONDS).toBe(5);
    expect(BACKEND_MAX_PAGE_SIZE).toBe(100);
    expect(BACKEND_MAX_CURSOR_LENGTH).toBe(2048);

    expect(DEFAULT_NODE_LIMIT).toBe(50);
    expect(DEFAULT_EDGE_LIMIT).toBe(100);
    expect(DEFAULT_PAGE_SIZE).toBe(50);
    expect(DEFAULT_DEPTH).toBe(1);
    expect(DEFAULT_TIMEOUT_SECONDS).toBe(2);
    expect(DEFAULT_PATH_MAX_DEPTH).toBe(3);
    expect(DEFAULT_PATH_LIMIT).toBe(5);

    expect(CANVAS_MAX_NODES).toBe(300);
    expect(CANVAS_MAX_EDGES).toBe(600);
  });

  it('strictly isolates dependency relationship kinds from containment', () => {
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toHaveLength(12);
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('depends_on');
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('imports');
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('calls');
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('exposes');
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('consumes');
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('produces');
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('connects_to');
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('persists_to');
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('uses');
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('extends');
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('implements');
    expect(DEPENDENCY_RELATIONSHIP_KINDS).toContain('routes_to');

    // Contains is strictly separate
    expect(DEPENDENCY_RELATIONSHIP_KINDS).not.toContain('contains');
    expect(CONTAINMENT_RELATIONSHIP_KIND).toBe('contains');
  });

  it('defines valid directions and layout constants', () => {
    expect(NEIGHBORHOOD_DIRECTIONS).toEqual(['incoming', 'outgoing', 'both']);
    expect(CONTAINMENT_DIRECTIONS).toEqual(['parents', 'children', 'both']);

    expect(LAYOUT_PROTOCOL_VERSION).toBe(1);
    expect(DEFAULT_NODE_WIDTH).toBe(220);
    expect(DEFAULT_NODE_HEIGHT).toBe(80);
    expect(LAYOUT_WATCHDOG_TIMEOUT_MS).toBe(10000);
  });

  it('validates UUIDs correctly', () => {
    expect(isValidUuid('a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c8d')).toBe(true);
    expect(isValidUuid('A1B2C3D4-E5F6-4A1B-8C2D-3E4F5A6B7C8D')).toBe(true);
    expect(isValidUuid('invalid-uuid')).toBe(false);
    expect(isValidUuid('')).toBe(false);
    expect(isValidUuid(null)).toBe(false);
    expect(isValidUuid(12345)).toBe(false);
  });

  it('validates ProjectionCounts', () => {
    const valid = { entities: 10, relationships: 20, evidence: 5, unresolved: 2, conflicts: 1 };
    expect(validateProjectionCounts(valid)).toBe(true);
    expect(validateProjectionCounts({ ...valid, entities: -1 })).toBe(false);
    expect(validateProjectionCounts({ ...valid, entities: 1.5 })).toBe(false);
    expect(validateProjectionCounts({ entities: 10 })).toBe(false);
    expect(validateProjectionCounts(null)).toBe(false);
  });

  it('validates ProjectionStatusResponse', () => {
    const valid = {
      project_id: '11111111-1111-1111-1111-111111111111',
      architecture_version_id: '22222222-2222-2222-2222-222222222222',
      status: 'COMPLETED',
      active_generation_id: '33333333-3333-3333-3333-333333333333',
      counts: { entities: 5, relationships: 4, evidence: 3, unresolved: 0, conflicts: 0 },
    };
    expect(validateProjectionStatus(valid)).toBe(true);
    expect(validateProjectionStatus({ ...valid, status: 'INVALID_STATUS' })).toBe(false);
    expect(validateProjectionStatus({ ...valid, project_id: 'bad-id' })).toBe(false);
  });

  it('validates GraphReadScope', () => {
    const valid = {
      project_id: '11111111-1111-1111-1111-111111111111',
      architecture_version_id: '22222222-2222-2222-2222-222222222222',
      generation_id: '33333333-3333-3333-3333-333333333333',
      resource_state: 'COMPLETED',
      counts: { entities: 5, relationships: 4, evidence: 3, unresolved: 0, conflicts: 0 },
    };
    expect(validateGraphReadScope(valid)).toBe(true);
    expect(validateGraphReadScope({ ...valid, resource_state: 'UNKNOWN' })).toBe(false);
  });

  it('validates GraphNode and GraphEdge records', () => {
    const validNode = {
      architecture_entity_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      logical_id: 'entity:order-service',
      canonical_kind: 'service',
      name: 'Order Service',
      evidence_logical_ids: ['ev:1'],
    };
    expect(validateGraphNode(validNode)).toBe(true);
    expect(validateGraphNode({ ...validNode, architecture_entity_id: 'bad' })).toBe(false);
    expect(validateGraphNode({ ...validNode, logical_id: '' })).toBe(false);

    const validEdge = {
      architecture_relationship_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      logical_id: 'rel:order-to-db',
      canonical_kind: 'persists_to',
      source_entity_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      target_entity_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
      evidence_logical_ids: [],
    };
    expect(validateGraphEdge(validEdge)).toBe(true);
    expect(validateGraphEdge({ ...validEdge, source_entity_id: 'bad' })).toBe(false);
  });

  it('validates GraphSubgraph envelope', () => {
    const validSubgraph = {
      scope: {
        project_id: '11111111-1111-1111-1111-111111111111',
        architecture_version_id: '22222222-2222-2222-2222-222222222222',
        generation_id: '33333333-3333-3333-3333-333333333333',
        resource_state: 'COMPLETED',
      },
      nodes: [
        {
          architecture_entity_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
          logical_id: 'entity:order',
          canonical_kind: 'service',
          name: 'Order',
          evidence_logical_ids: [],
        },
      ],
      edges: [],
      truncated: false,
      next_cursor: 'opaque-token-123',
    };
    expect(validateGraphSubgraph(validSubgraph)).toBe(true);
    expect(validateGraphSubgraph({ ...validSubgraph, truncated: 'not-bool' })).toBe(false);
    expect(validateGraphSubgraph({ ...validSubgraph, next_cursor: 'a'.repeat(3000) })).toBe(false);
  });

  it('validates GraphQueryHealth', () => {
    expect(validateGraphQueryHealth({ status: 'ready' })).toBe(true);
    expect(validateGraphQueryHealth({ status: 'degraded' })).toBe(true);
    expect(validateGraphQueryHealth({ status: 'unavailable' })).toBe(true);
    expect(validateGraphQueryHealth({ status: 'healthy' })).toBe(false);
    expect(validateGraphQueryHealth(null)).toBe(false);
  });
});

