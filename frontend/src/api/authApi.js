/**
 * StackSense Authentication API Client
 * Interacts directly with the backend FastAPI /api/v1/auth endpoints.
 */

const API_BASE = '/api/v1/auth';
const ACCESS_TOKEN_KEY = 'stacksense_access_token';
const REFRESH_TOKEN_KEY = 'stacksense_refresh_token';
const LEGACY_TOKEN_KEY = 'stacksense_auth_token';

/**
 * Custom error wrapper to expose structured backend errors.
 */
export class AuthApiError extends Error {
  constructor(message, code = 'unknown_error', status = 500, details = null) {
    super(message);
    this.name = 'AuthApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

/**
 * Safely parse JSON or return generic error.
 */
async function parseResponse(response) {
  let data = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON response (e.g. 204 No Content)
  }

  if (!response.ok) {
    const errorPayload = data?.error;
    const message =
      errorPayload?.message ||
      (data?.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : null) ||
      'An authentication error occurred.';
    const code = errorPayload?.code || 'auth_error';
    const details = errorPayload?.details || null;
    throw new AuthApiError(message, code, response.status, details);
  }

  return data;
}

export const authApi = {
  /**
   * Log in user with identifier (username or email) and password.
   * @param {string|{identifier?: string, email?: string, username?: string, password?: string}} identifierOrPayload
   * @param {string} [maybePassword]
   * @returns {Promise<{ access_token: string, refresh_token: string, token_type: string, expires_in: number, refresh_expires_in: number }>}
   */
  async login(identifierOrPayload, maybePassword) {
    let identifier;
    let password;
    if (typeof identifierOrPayload === 'object' && identifierOrPayload !== null) {
      identifier = identifierOrPayload.identifier || identifierOrPayload.username || identifierOrPayload.email;
      password = identifierOrPayload.password;
    } else {
      identifier = identifierOrPayload;
      password = maybePassword;
    }

    try {
      const response = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          identifier: (identifier || '').trim().toLowerCase(),
          password,
        }),
      });
      const data = await parseResponse(response);
      if (data?.access_token) {
        this.setStoredToken(data.access_token);
      }
      if (data?.refresh_token) {
        this.setStoredRefreshToken(data.refresh_token);
      }
      return data;
    } catch (err) {
      if (err instanceof AuthApiError) throw err;
      throw new AuthApiError(
        'Unable to connect to the authentication server. Please verify the backend is running.',
        'connection_error',
        0
      );
    }
  },

  /**
   * Register a new user with email, username, and password.
   * @param {string|{email?: string, username?: string, password?: string}} emailOrPayload
   * @param {string} [maybeUsername]
   * @param {string} [maybePassword]
   * @returns {Promise<{ id: string, email: string, username: string, is_active: boolean, access_token?: string, refresh_token?: string }>}
   */
  async register(emailOrPayload, maybeUsername, maybePassword) {
    let email;
    let username;
    let password;
    if (typeof emailOrPayload === 'object' && emailOrPayload !== null) {
      email = emailOrPayload.email;
      username = emailOrPayload.username;
      password = emailOrPayload.password;
    } else {
      email = emailOrPayload;
      username = maybeUsername;
      password = maybePassword;
    }

    try {
      const response = await fetch(`${API_BASE}/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: (email || '').trim().toLowerCase(),
          username: (username || '').trim().toLowerCase(),
          password,
        }),
      });
      const data = await parseResponse(response);
      if (data?.access_token) {
        this.setStoredToken(data.access_token);
      }
      if (data?.refresh_token) {
        this.setStoredRefreshToken(data.refresh_token);
      }
      return data;
    } catch (err) {
      if (err instanceof AuthApiError) throw err;
      throw new AuthApiError(
        'Unable to connect to the authentication server. Please verify the backend is running.',
        'connection_error',
        0
      );
    }
  },

  /**
   * Rotate active refresh token and store new token pair.
   * @param {string} [refreshToken]
   * @returns {Promise<{ access_token: string, refresh_token: string, token_type: string, expires_in: number, refresh_expires_in: number }>}
   */
  async refreshToken(refreshToken) {
    const token = refreshToken || this.getStoredRefreshToken();
    if (!token) {
      throw new AuthApiError('No active refresh token found', 'unauthorized', 401);
    }

    try {
      const response = await fetch(`${API_BASE}/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: token.trim() }),
      });
      const data = await parseResponse(response);
      if (data?.access_token) {
        this.setStoredToken(data.access_token);
      }
      if (data?.refresh_token) {
        this.setStoredRefreshToken(data.refresh_token);
      }
      return data;
    } catch (err) {
      if (err instanceof AuthApiError) throw err;
      throw new AuthApiError(
        'Unable to connect to the authentication server.',
        'connection_error',
        0
      );
    }
  },

  /**
   * Revoke refresh token and clear tokens locally.
   * @param {string} [refreshToken]
   * @returns {Promise<void>}
   */
  async logout(refreshToken) {
    const token = refreshToken || this.getStoredRefreshToken();
    try {
      if (token) {
        const response = await fetch(`${API_BASE}/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ refresh_token: token.trim() }),
        });
        await parseResponse(response);
      }
    } catch (err) {
      if (err instanceof AuthApiError) throw err;
      throw new AuthApiError(
        'Unable to connect to the authentication server.',
        'connection_error',
        0
      );
    } finally {
      this.clearTokens();
    }
  },

  /**
   * Get currently authenticated user profile.
   * @param {string} [token]
   * @returns {Promise<{ id: string, email: string, username: string, is_active: boolean }>}
   */
  async getCurrentUser(token) {
    const bearer = token || this.getStoredToken();
    if (!bearer) {
      throw new AuthApiError('No active token found', 'unauthorized', 401);
    }

    try {
      const response = await fetch(`${API_BASE}/me`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${bearer}`,
        },
      });
      return await parseResponse(response);
    } catch (err) {
      if (err instanceof AuthApiError) throw err;
      throw new AuthApiError(
        'Unable to connect to the authentication server.',
        'connection_error',
        0
      );
    }
  },

  /**
   * Retrieve saved access token from localStorage.
   * @returns {string|null}
   */
  getStoredToken() {
    try {
      return localStorage.getItem(ACCESS_TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY);
    } catch {
      return null;
    }
  },

  /**
   * Store access token in localStorage.
   * @param {string} token
   */
  setStoredToken(token) {
    try {
      localStorage.setItem(ACCESS_TOKEN_KEY, token);
    } catch {
      // Storage unavailable or disabled
    }
  },

  /**
   * Retrieve saved refresh token from localStorage.
   * @returns {string|null}
   */
  getStoredRefreshToken() {
    try {
      return localStorage.getItem(REFRESH_TOKEN_KEY);
    } catch {
      return null;
    }
  },

  /**
   * Store refresh token in localStorage.
   * @param {string} token
   */
  setStoredRefreshToken(token) {
    try {
      localStorage.setItem(REFRESH_TOKEN_KEY, token);
    } catch {
      // Storage unavailable or disabled
    }
  },

  /**
   * Clear both access and refresh tokens from localStorage.
   */
  clearTokens() {
    try {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      localStorage.removeItem(LEGACY_TOKEN_KEY);
    } catch {
      // Ignore
    }
  },

  /**
   * Backward-compatible alias to clear tokens.
   */
  clearStoredToken() {
    this.clearTokens();
  },
};
