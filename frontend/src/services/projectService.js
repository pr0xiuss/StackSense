/**
 * Project Service
 * Interacts with /api/v1/projects endpoints via centralized apiClient.
 */
import { apiClient } from './apiClient.js';

export const projectService = {
  /**
   * List projects accessible to the current user with pagination.
   * @param {number} [limit=50]
   * @param {number} [offset=0]
   * @returns {Promise<Array<{ id: string, name: string, description: string | null, created_at: string, updated_at: string, role?: string }>>}
   */
  async listProjects(limit = 50, offset = 0) {
    return apiClient.get(`/projects?limit=${limit}&offset=${offset}`);
  },

  /**
   * Retrieve a single project by ID.
   * @param {string} projectId
   */
  async getProject(projectId) {
    return apiClient.get(`/projects/${projectId}`);
  },

  /**
   * Create a new project.
   * @param {{ name: string, description?: string }} payload
   */
  async createProject(payloadOrName, maybeDescription) {
    let name;
    let description;
    if (typeof payloadOrName === 'object' && payloadOrName !== null) {
      name = payloadOrName.name;
      description = payloadOrName.description;
    } else {
      name = payloadOrName;
      description = maybeDescription;
    }

    return apiClient.post('/projects', {
      name: (name || '').trim(),
      description: description ? description.trim() : null,
    });
  },

  /**
   * Delete a project.
   * @param {string} projectId
   */
  async deleteProject(projectId) {
    return apiClient.delete(`/projects/${projectId}`);
  },
};
