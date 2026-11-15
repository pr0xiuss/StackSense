/**
 * Architecture Graph API Service (Frontend)
 *
 * Provides typed operations for retrieving projection status, bounded graph windows,
 * node details, neighborhood, dependencies, dependents, containment, bounded paths,
 * rebuild mutations, and diagnostic query health.
 *
 * All requests route through the central apiClient to the authorized Express backend.
 */
import { apiClient } from './apiClient.js';

function buildQueryString(queryObj = {}) {
  const params = new URLSearchParams();
  for (const [key, val] of Object.entries(queryObj)) {
    if (val === undefined || val === null) continue;
    if (Array.isArray(val)) {
      for (const item of val) {
        if (item !== undefined && item !== null) {
          params.append(key, String(item));
        }
      }
    } else {
      params.append(key, String(val));
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export const graphService = {
  /**
   * Get projection lifecycle status and attempt summary for an architecture version.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @param {AbortSignal} [options.signal]
   * @returns {Promise<object>} ProjectionStatusResponse
   */
  async getStatus(versionId, { projectId, signal } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const qs = buildQueryString({ project_id: projectId });
    return apiClient.get(`/architecture-versions/${encodeURIComponent(versionId)}/graph/status${qs}`, {
      signal,
    });
  },

  /**
   * Request a durable rebuild of the graph projection.
   * Requires OWNER or ADMIN role.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @param {AbortSignal} [options.signal]
   * @returns {Promise<object>} ProjectionRebuildAcceptedResponse (HTTP 202)
   */
  async requestRebuild(versionId, { projectId, signal } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const qs = buildQueryString({ project_id: projectId });
    return apiClient.post(
      `/architecture-versions/${encodeURIComponent(versionId)}/graph/rebuild${qs}`,
      {},
      { signal }
    );
  },

  /**
   * Get bounded initial graph window overview for an architecture version.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @param {number} [options.nodeLimit=50]
   * @param {number} [options.edgeLimit=100]
   * @param {number} [options.pageSize=50]
   * @param {string[]} [options.canonicalKinds]
   * @param {string} [options.cursor]
   * @param {number} [options.timeoutSeconds=2]
   * @param {AbortSignal} [options.signal]
   * @returns {Promise<object>} GraphSubgraph
   */
  async getWindow(
    versionId,
    {
      projectId,
      nodeLimit,
      edgeLimit,
      pageSize,
      canonicalKinds,
      cursor,
      timeoutSeconds,
      signal,
    } = {}
  ) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const qs = buildQueryString({
      project_id: projectId,
      node_limit: nodeLimit,
      edge_limit: edgeLimit,
      page_size: pageSize,
      canonical_kinds: canonicalKinds,
      cursor,
      timeout_seconds: timeoutSeconds,
    });

    return apiClient.get(`/architecture-versions/${encodeURIComponent(versionId)}/graph/window${qs}`, {
      signal,
    });
  },

  /**
   * Retrieve single entity inspector detail.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {string} entityId - Architecture Entity UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @param {number} [options.timeoutSeconds]
   * @param {AbortSignal} [options.signal]
   * @returns {Promise<object>} GraphNode
   */
  async getNodeDetail(versionId, entityId, { projectId, timeoutSeconds, signal } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!entityId) throw new Error('entityId is required');
    if (!projectId) throw new Error('projectId is required');

    const qs = buildQueryString({
      project_id: projectId,
      timeout_seconds: timeoutSeconds,
    });

    return apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/graph/nodes/${encodeURIComponent(entityId)}${qs}`,
      { signal }
    );
  },

  /**
   * Retrieve structural expansion neighborhood around an anchor node.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {string} entityId - Architecture Entity UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @param {string} [options.direction='both'] - 'incoming' | 'outgoing' | 'both'
   * @param {number} [options.depth=1]
   * @param {number} [options.nodeLimit=50]
   * @param {number} [options.edgeLimit=100]
   * @param {string[]} [options.relationshipKinds]
   * @param {string} [options.cursor]
   * @param {number} [options.timeoutSeconds=2]
   * @param {AbortSignal} [options.signal]
   * @returns {Promise<object>} GraphSubgraph
   */
  async getNeighborhood(
    versionId,
    entityId,
    {
      projectId,
      direction,
      depth,
      nodeLimit,
      edgeLimit,
      relationshipKinds,
      cursor,
      timeoutSeconds,
      signal,
    } = {}
  ) {
    if (!versionId) throw new Error('versionId is required');
    if (!entityId) throw new Error('entityId is required');
    if (!projectId) throw new Error('projectId is required');

    const qs = buildQueryString({
      project_id: projectId,
      direction,
      depth,
      node_limit: nodeLimit,
      edge_limit: edgeLimit,
      relationship_kinds: relationshipKinds,
      cursor,
      timeout_seconds: timeoutSeconds,
    });

    return apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/graph/nodes/${encodeURIComponent(entityId)}/neighborhood${qs}`,
      { signal }
    );
  },

  /**
   * Retrieve outgoing dependencies from an anchor node.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {string} entityId - Architecture Entity UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @param {number} [options.depth=1]
   * @param {number} [options.nodeLimit=50]
   * @param {number} [options.edgeLimit=100]
   * @param {string[]} [options.relationshipKinds]
   * @param {string} [options.cursor]
   * @param {number} [options.timeoutSeconds=2]
   * @param {AbortSignal} [options.signal]
   * @returns {Promise<object>} GraphSubgraph
   */
  async getDependencies(
    versionId,
    entityId,
    {
      projectId,
      depth,
      nodeLimit,
      edgeLimit,
      relationshipKinds,
      cursor,
      timeoutSeconds,
      signal,
    } = {}
  ) {
    if (!versionId) throw new Error('versionId is required');
    if (!entityId) throw new Error('entityId is required');
    if (!projectId) throw new Error('projectId is required');

    const qs = buildQueryString({
      project_id: projectId,
      depth,
      node_limit: nodeLimit,
      edge_limit: edgeLimit,
      relationship_kinds: relationshipKinds,
      cursor,
      timeout_seconds: timeoutSeconds,
    });

    return apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/graph/nodes/${encodeURIComponent(entityId)}/dependencies${qs}`,
      { signal }
    );
  },

  /**
   * Retrieve incoming dependents to an anchor node.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {string} entityId - Architecture Entity UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @param {number} [options.depth=1]
   * @param {number} [options.nodeLimit=50]
   * @param {number} [options.edgeLimit=100]
   * @param {string[]} [options.relationshipKinds]
   * @param {string} [options.cursor]
   * @param {number} [options.timeoutSeconds=2]
   * @param {AbortSignal} [options.signal]
   * @returns {Promise<object>} GraphSubgraph
   */
  async getDependents(
    versionId,
    entityId,
    {
      projectId,
      depth,
      nodeLimit,
      edgeLimit,
      relationshipKinds,
      cursor,
      timeoutSeconds,
      signal,
    } = {}
  ) {
    if (!versionId) throw new Error('versionId is required');
    if (!entityId) throw new Error('entityId is required');
    if (!projectId) throw new Error('projectId is required');

    const qs = buildQueryString({
      project_id: projectId,
      depth,
      node_limit: nodeLimit,
      edge_limit: edgeLimit,
      relationship_kinds: relationshipKinds,
      cursor,
      timeout_seconds: timeoutSeconds,
    });

    return apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/graph/nodes/${encodeURIComponent(entityId)}/dependents${qs}`,
      { signal }
    );
  },

  /**
   * Retrieve hierarchy navigation for contains relationships.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {string} entityId - Architecture Entity UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @param {string} [options.direction='children'] - 'parents' | 'children' | 'both'
   * @param {number} [options.depth=1]
   * @param {number} [options.nodeLimit=50]
   * @param {number} [options.edgeLimit=100]
   * @param {string} [options.cursor]
   * @param {number} [options.timeoutSeconds=2]
   * @param {AbortSignal} [options.signal]
   * @returns {Promise<object>} GraphSubgraph
   */
  async getContainment(
    versionId,
    entityId,
    {
      projectId,
      direction,
      depth,
      nodeLimit,
      edgeLimit,
      cursor,
      timeoutSeconds,
      signal,
    } = {}
  ) {
    if (!versionId) throw new Error('versionId is required');
    if (!entityId) throw new Error('entityId is required');
    if (!projectId) throw new Error('projectId is required');

    const qs = buildQueryString({
      project_id: projectId,
      direction,
      depth,
      node_limit: nodeLimit,
      edge_limit: edgeLimit,
      cursor,
      timeout_seconds: timeoutSeconds,
    });

    return apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/graph/nodes/${encodeURIComponent(entityId)}/containment${qs}`,
      { signal }
    );
  },

  /**
   * Retrieve bounded simple paths between two entities.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @param {string} options.sourceEntityId - Source Entity UUID
   * @param {string} options.targetEntityId - Target Entity UUID
   * @param {number} [options.maxDepth=3]
   * @param {number} [options.pathLimit=5]
   * @param {string[]} [options.relationshipKinds]
   * @param {number} [options.timeoutSeconds=2]
   * @param {AbortSignal} [options.signal]
   * @returns {Promise<object>} GraphPathResult
   */
  async getBoundedPaths(
    versionId,
    {
      projectId,
      sourceEntityId,
      targetEntityId,
      maxDepth,
      pathLimit,
      relationshipKinds,
      timeoutSeconds,
      signal,
    } = {}
  ) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');
    if (!sourceEntityId) throw new Error('sourceEntityId is required');
    if (!targetEntityId) throw new Error('targetEntityId is required');

    const qs = buildQueryString({
      project_id: projectId,
      source_entity_id: sourceEntityId,
      target_entity_id: targetEntityId,
      max_depth: maxDepth,
      path_limit: pathLimit,
      relationship_kinds: relationshipKinds,
      timeout_seconds: timeoutSeconds,
    });

    return apiClient.get(`/architecture-versions/${encodeURIComponent(versionId)}/graph/paths${qs}`, {
      signal,
    });
  },

  /**
   * Diagnostic health probe relay for the graph query engine.
   *
   * @param {object} [options]
   * @param {AbortSignal} [options.signal]
   * @returns {Promise<object>} GraphQueryHealthResponse
   */
  async getQueryHealth({ signal } = {}) {
    return apiClient.get('/health/graph/query', { signal });
  },
};

