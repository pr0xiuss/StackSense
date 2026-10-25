import { apiClient } from './apiClient.js';

export const projectService = {
  async listProjects(limit = 50, offset = 0) {
    return apiClient.get(`/projects?limit=${limit}&offset=${offset}`);
  },

  async updateProject(projectId, payload) {
    return apiClient.patch(`/projects/${projectId}`, payload);
  },

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

  async deleteProject(projectId) {
    return apiClient.delete(`/projects/${projectId}`);
  },
};
