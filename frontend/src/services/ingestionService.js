/**
 * Ingestion Service
 * Interacts with ingestion, revision, and artifact endpoints via centralized apiClient.
 */
import { apiClient } from './apiClient.js';

export const ingestionService = {
  /**
   * List ingestion jobs for a repository.
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {number} [limit=50]
   * @param {number} [offset=0]
   */
  async listIngestions(projectId, repositoryId, limit = 50, offset = 0) {
    return apiClient.get(
      `/projects/${projectId}/repositories/${repositoryId}/ingestions?limit=${limit}&offset=${offset}`
    );
  },

  /**
   * Retrieve details of a specific ingestion job.
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {string} ingestionId
   */
  async getIngestion(projectId, repositoryId, ingestionId) {
    return apiClient.get(
      `/projects/${projectId}/repositories/${repositoryId}/ingestions/${ingestionId}`
    );
  },

  /**
   * Trigger ingestion via a public GitHub URL, server path, or staged archive.
   * Supports: 'github', 'archive', and 'server_path'.
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {{ source_type?: string, repository_url?: string, ref?: string, source_reference?: string, revision_identifier?: string }} payload
   */
  async triggerIngestion(projectId, repositoryId, payload) {
    const body = {
      repository_id: repositoryId,
      source_type: payload.source_type || 'archive',
    };

    if (payload.repository_url && typeof payload.repository_url === 'string') {
      body.repository_url = payload.repository_url.trim();
    }
    if (payload.ref && typeof payload.ref === 'string') {
      body.ref = payload.ref.trim();
    }
    if (payload.source_reference && typeof payload.source_reference === 'string') {
      body.source_reference = payload.source_reference.trim();
    }
    if (payload.revision_identifier && typeof payload.revision_identifier === 'string') {
      const cleanRev = payload.revision_identifier.trim();
      if (cleanRev) {
        body.revision_identifier = cleanRev;
      }
    }

    return apiClient.post(
      `/projects/${projectId}/repositories/${repositoryId}/ingestions`,
      body
    );
  },

  /**
   * Upload a zip archive and trigger repository ingestion.
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {File} file
   * @param {string} [revisionIdentifier]
   */
  async uploadAndIngest(projectId, repositoryId, file, revisionIdentifier = null) {
    const formData = new FormData();
    formData.append('file', file);
    if (revisionIdentifier) {
      formData.append('revision_identifier', revisionIdentifier.trim());
    }

    return apiClient.post(
      `/projects/${projectId}/repositories/${repositoryId}/ingestions/upload`,
      formData
    );
  },

  /**
   * List revisions captured for a repository.
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {number} [limit=50]
   * @param {number} [offset=0]
   */
  async listRevisions(projectId, repositoryId, limit = 50, offset = 0) {
    return apiClient.get(
      `/projects/${projectId}/repositories/${repositoryId}/revisions?limit=${limit}&offset=${offset}`
    );
  },

  /**
   * Retrieve a specific revision.
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {string} revisionId
   */
  async getRevision(projectId, repositoryId, revisionId) {
    return apiClient.get(
      `/projects/${projectId}/repositories/${repositoryId}/revisions/${revisionId}`
    );
  },

  /**
   * List artifacts discovered for a specific revision.
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {string} revisionId
   * @param {number} [limit=50]
   * @param {number} [offset=0]
   */
  async listArtifacts(projectId, repositoryId, revisionId, limit = 50, offset = 0) {
    return apiClient.get(
      `/projects/${projectId}/repositories/${repositoryId}/revisions/${revisionId}/artifacts?limit=${limit}&offset=${offset}`
    );
  },
};
