/**
 * Architecture Model API Service (Frontend)
 *
 * Provides typed operations for retrieving published Architecture Versions,
 * Entities, Relationships, Evidence, Unresolved items, and Conflicts.
 */
import { apiClient } from './apiClient.js';

export const architectureService = {
  /**
   * Retrieve an Architecture Version summary by ID.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @returns {Promise<object>} ArchitectureVersionResponse
   */
  async getVersion(versionId, { projectId } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');
    return apiClient.get(`/architecture-versions/${versionId}?project_id=${encodeURIComponent(projectId)}`);
  },

  /**
   * List entities belonging to an Architecture Version.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {object} params
   * @param {string} params.projectId - Project UUID
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   * @param {string} [params.kind] - Optional entity kind filter
   * @param {string} [params.status] - Optional entity status filter
   * @returns {Promise<{ items: object[], total: number, limit: number, offset: number }>}
   */
  async listEntities(versionId, { projectId, limit = 50, offset = 0, kind, status } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (kind) params.set('kind', kind);
    if (status) params.set('status', status);

    return apiClient.get(`/architecture-versions/${versionId}/entities?${params.toString()}`);
  },

  /**
   * Retrieve a specific entity by logical ID or UUID.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {string} entityId - Entity UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @returns {Promise<object>} ArchitectureEntityResponse
   */
  async getEntity(versionId, entityId, { projectId } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!entityId) throw new Error('entityId is required');
    if (!projectId) throw new Error('projectId is required');

    return apiClient.get(
      `/architecture-versions/${versionId}/entities/${entityId}?project_id=${encodeURIComponent(projectId)}`
    );
  },

  /**
   * List relationships belonging to an Architecture Version.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {object} params
   * @param {string} params.projectId - Project UUID
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   * @param {string} [params.kind] - Optional relationship kind filter
   * @param {string} [params.status] - Optional relationship status filter
   * @returns {Promise<{ items: object[], total: number, limit: number, offset: number }>}
   */
  async listRelationships(versionId, { projectId, limit = 50, offset = 0, kind, status } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (kind) params.set('kind', kind);
    if (status) params.set('status', status);

    return apiClient.get(`/architecture-versions/${versionId}/relationships?${params.toString()}`);
  },

  /**
   * List evidence records for an Architecture Version, optionally filtered by entity.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {object} params
   * @param {string} params.projectId - Project UUID
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   * @param {string} [params.entityId] - Optional entity UUID filter
   * @returns {Promise<{ items: object[], total: number, limit: number, offset: number }>}
   */
  async listEvidence(versionId, { projectId, limit = 50, offset = 0, entityId } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (entityId) params.set('entity_id', entityId);

    return apiClient.get(`/architecture-versions/${versionId}/evidence?${params.toString()}`);
  },

  /**
   * List unresolved relationships in an Architecture Version.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {object} params
   * @param {string} params.projectId - Project UUID
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   * @returns {Promise<{ items: object[], total: number, limit: number, offset: number }>}
   */
  async listUnresolved(versionId, { projectId, limit = 50, offset = 0 } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));

    return apiClient.get(`/architecture-versions/${versionId}/unresolved?${params.toString()}`);
  },

  /**
   * List architecture conflicts identified in an Architecture Version.
   *
   * @param {string} versionId - Architecture Version UUID
   * @param {object} params
   * @param {string} params.projectId - Project UUID
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   * @returns {Promise<{ items: object[], total: number, limit: number, offset: number }>}
   */
  async listConflicts(versionId, { projectId, limit = 50, offset = 0 } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));

    return apiClient.get(`/architecture-versions/${versionId}/conflicts?${params.toString()}`);
  },
};

