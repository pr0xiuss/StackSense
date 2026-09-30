/**
 * Authentication Service
 * Interacts with /api/v1/auth endpoints via centralized apiClient.
 */
import { apiClient, tokenStorage } from './apiClient.js';

export const authService = {
  /**
   * Authenticate user with identifier (username or email) and password.
   */
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

  /**
   * Register a new user account with email, username, and password.
   */
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

  /**
   * Explicitly rotate refresh token.
   */
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

  /**
   * Log out current user and revoke session.
   */
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

  /**
   * Retrieve profile of currently authenticated user.
   */
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
