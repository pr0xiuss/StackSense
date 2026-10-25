import { apiClient } from './apiClient.js';

export const repositoryService = {
  async listRepositories(projectId, limit = 50, offset = 0) {
    return apiClient.get(`/projects/${projectId}/repositories?limit=${limit}&offset=${offset}`);
  },

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

  async updateRepository(projectId, repositoryId, payload) {
    return apiClient.patch(`/projects/${projectId}/repositories/${repositoryId}`, payload);
  },

  async deleteRepository(projectId, repositoryId) {
    return apiClient.delete(`/projects/${projectId}/repositories/${repositoryId}`);
  },
};
