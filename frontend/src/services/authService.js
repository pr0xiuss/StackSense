import { apiClient, tokenStorage } from './apiClient.js';

export function isDefinitiveSessionFailure(error) {
  if (error?.status === 401) return true;
  return error?.status === 403 && error?.code === 'user_inactive';
}

export const authService = {
  async login(identifier, password) {
    const payload = {
      identifier: identifier.trim().toLowerCase(),
      password,
    };

    const data = await apiClient.post('/auth/login', payload, { skipAuth: true });
    if (data?.access_token) {
      tokenStorage.setTokens(data.access_token, data.refresh_token);
    }
    return data;
  },

  async register(email, username, password) {
    const payload = {
      email: email.trim().toLowerCase(),
      username: username.trim().toLowerCase(),
      password,
    };

    const data = await apiClient.post('/auth/register', payload, { skipAuth: true });
    if (data?.access_token) {
      tokenStorage.setTokens(data.access_token, data.refresh_token);
    }
    return data;
  },

  async refreshToken(refreshToken) {
    const token = refreshToken || tokenStorage.getRefreshToken();
    if (!token) {
      throw new Error('No active refresh token found.');
    }

    const data = await apiClient.post(
      '/auth/refresh',
      { refresh_token: token.trim() },
      { skipAuth: true }
    );
    if (data?.access_token) {
      tokenStorage.setTokens(data.access_token, data.refresh_token);
    }
    return data;
  },

  async logout(refreshToken) {
    const token = refreshToken || tokenStorage.getRefreshToken();
    try {
      if (token) {
        await apiClient.post(
          '/auth/logout',
          { refresh_token: token.trim() },
          { skipAuth: true }
        );
      }
    } finally {
      tokenStorage.clearTokens();
    }
  },

  async getCurrentUser() {
    return apiClient.get('/auth/me');
  },

  getAccessToken() {
    return tokenStorage.getAccessToken();
  },

  getRefreshToken() {
    return tokenStorage.getRefreshToken();
  },

  clearTokens() {
    tokenStorage.clearTokens();
  },
};
