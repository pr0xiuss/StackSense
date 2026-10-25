import { apiClient } from './apiClient.js';

export const PROJECT_ROLES = ['owner', 'admin', 'developer', 'viewer'];

export const projectAccessService = {
  async listAccess(projectId) {
    return apiClient.get(`/projects/${projectId}/access`);
  },

  async grantAccess(projectId, userId, role) {
    return apiClient.post(`/projects/${projectId}/access`, {
      user_id: userId.trim(),
      role: role.toLowerCase(),
    });
  },

  async changeRole(projectId, userId, role) {
    return apiClient.patch(`/projects/${projectId}/access/${userId}`, {
      role: role.toLowerCase(),
    });
  },

  async revokeAccess(projectId, userId) {
    return apiClient.delete(`/projects/${projectId}/access/${userId}`);
  },
};
