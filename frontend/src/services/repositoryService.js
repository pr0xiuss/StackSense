/**
 * Repository Service
 * Interacts with /api/v1/projects/{project_id}/repositories endpoints via centralized apiClient.
 */
import { apiClient } from './apiClient.js';

export const repositoryService = {
  /**
   * List repositories belonging to a project.
   * @param {string} projectId
   * @param {number} [limit=50]
   * @param {number} [offset=0]
   */
  async listRepositories(projectId, limit = 50, offset = 0) {
    return apiClient.get(`/projects/${projectId}/repositories?limit=${limit}&offset=${offset}`);
  },

  /**
   * Retrieve a specific repository within a project.
   * @param {string} projectId
   * @param {string} repositoryId
   */
  async getRepository(projectId, repositoryId) {
    return apiClient.get(`/projects/${projectId}/repositories/${repositoryId}`);
  },

  /**
   * Register a new repository under a project.
   * @param {string} projectId
   * @param {{ name: string, description?: string }} payload
   */
  async createRepository(projectId, payloadOrName, maybeDescription) {
    let name;
    let description;
    if (typeof payloadOrName === 'object' && payloadOrName !== null) {
      name = payloadOrName.name;
      description = payloadOrName.description;
    } else {
      name = payloadOrName;
      description = maybeDescription;
    }

    return apiClient.post(`/projects/${projectId}/repositories`, {
      name: (name || '').trim(),
      description: description ? description.trim() : null,
    });
  },

  /**
   * Update repository metadata.
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {{ name?: string, description?: string }} payload
   */
  async updateRepository(projectId, repositoryId, payload) {
    return apiClient.patch(`/projects/${projectId}/repositories/${repositoryId}`, payload);
  },

  /**
   * Delete a repository from a project.
   * @param {string} projectId
   * @param {string} repositoryId
   */
  async deleteRepository(projectId, repositoryId) {
    return apiClient.delete(`/projects/${projectId}/repositories/${repositoryId}`);
  },
};
