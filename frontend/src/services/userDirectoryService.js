import { apiClient } from './apiClient.js';

export const userDirectoryService = {
  async searchByUsername(username, limit = 8) {
    const query = new URLSearchParams({
      username: username.trim(),
      limit: String(limit),
    });
    return apiClient.get(`/users/lookup?${query.toString()}`);
  },
};
