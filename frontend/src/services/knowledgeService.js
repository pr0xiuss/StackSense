/**
 * Knowledge & Search Service (Frontend)
 *
 * Interacts with C1 lexical search and C3 controlled retrieval / context endpoints.
 */
import { apiClient } from './apiClient.js';
import {
  validateSearchStatus,
  validateSearchPage,
  validateSearchReprojectionAccepted,
  validateKnowledgeQueryResponse,
  validateContextBundle,
  validateEvidencePage,
} from '../contracts/intelligenceContracts.js';

export const knowledgeService = {
  /**
   * Retrieve C1 search status and capabilities.
   */
  async getSearchStatus(versionId, { projectId, signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/search/status?project_id=${encodeURIComponent(projectId)}`,
      { signal, ...options }
    );
    return validateSearchStatus(data);
  },

  /**
   * Execute C1 lexical search.
   */
  async search(versionId, params = {}, { signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!params.projectId) throw new Error('projectId is required');

    const qs = new URLSearchParams();
    qs.set('project_id', params.projectId);
    if (params.q !== undefined && params.q !== null) qs.set('q', params.q);
    if (params.mode) qs.set('mode', params.mode);
    if (params.limit) qs.set('limit', String(params.limit));
    if (params.cursor) qs.set('cursor', params.cursor);
    if (params.timeout_seconds) qs.set('timeout_seconds', String(params.timeout_seconds));

    for (const key of ['document_kinds', 'entity_kinds', 'statuses']) {
      if (params[key]) {
        const arr = Array.isArray(params[key]) ? params[key] : [params[key]];
        for (const item of arr) {
          qs.append(key, item);
        }
      }
    }

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/search?${qs.toString()}`,
      { signal, ...options }
    );
    return validateSearchPage(data);
  },

  /**
   * Request rebuild of C1 search reprojection.
   */
  async rebuildSearch(versionId, payload, { projectId, signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.post(
      `/architecture-versions/${encodeURIComponent(versionId)}/search/rebuild?project_id=${encodeURIComponent(projectId)}`,
      payload,
      { signal, ...options }
    );
    return validateSearchReprojectionAccepted(data);
  },

  /**
   * Execute C3 Knowledge Query.
   */
  async queryKnowledge(versionId, body, { projectId, signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.post(
      `/architecture-versions/${encodeURIComponent(versionId)}/knowledge/query?project_id=${encodeURIComponent(projectId)}`,
      body,
      { signal, ...options }
    );
    return validateKnowledgeQueryResponse(data);
  },

  /**
   * Execute C3 Context Assembly.
   */
  async getContext(versionId, body, { projectId, signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.post(
      `/architecture-versions/${encodeURIComponent(versionId)}/knowledge/context?project_id=${encodeURIComponent(projectId)}`,
      body,
      { signal, ...options }
    );
    return validateContextBundle(data);
  },

  /**
   * Retrieve paginated evidence records for specified selector family.
   */
  async getEvidence(versionId, params = {}, { signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!params.projectId) throw new Error('projectId is required');

    const qs = new URLSearchParams();
    qs.set('project_id', params.projectId);
    if (params.limit) qs.set('limit', String(params.limit));
    if (params.cursor) qs.set('cursor', params.cursor);

    for (const key of ['entity_id', 'relationship_id', 'evidence_id']) {
      if (params[key]) {
        const arr = Array.isArray(params[key]) ? params[key] : [params[key]];
        for (const item of arr) {
          qs.append(key, item);
        }
      }
    }

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/knowledge/evidence?${qs.toString()}`,
      { signal, ...options }
    );
    return validateEvidencePage(data);
  },
};
