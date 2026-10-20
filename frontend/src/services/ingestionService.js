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
    const sourceType = typeof payload.source_type === 'string'
      ? payload.source_type.trim()
      : payload.source_type;
    let sourceReference = typeof payload.source_reference === 'string'
      ? payload.source_reference.trim()
      : payload.source_reference;

    // Express's GitHub acquisition contract encodes an optional ref in
    // source_reference as "https://github.com/owner/repo@ref".
    if (sourceType === 'github' && typeof payload.repository_url === 'string') {
      const repositoryUrl = payload.repository_url.trim();
      const ref = typeof payload.ref === 'string' ? payload.ref.trim() : '';
      sourceReference = ref ? `${repositoryUrl}@${ref}` : repositoryUrl;
    }

    const body = {
      source_type: sourceType,
      source_reference: sourceReference,
    };

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
