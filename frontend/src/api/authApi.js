/**
 * StackSense Authentication API Client
 * Interacts directly with the backend FastAPI /api/v1/auth endpoints.
 */

const API_BASE = '/api/v1/auth';
const TOKEN_KEY = 'stacksense_auth_token';

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
    // Non-JSON response
  }

  if (!response.ok) {
    const errorPayload = data?.error;
    const message = errorPayload?.message || (data?.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : null) || 'An authentication error occurred.';
    const code = errorPayload?.code || 'auth_error';
    const details = errorPayload?.details || null;
    throw new AuthApiError(message, code, response.status, details);
  }

  return data;
}

export const authApi = {
  /**
   * Log in user with email and password.
   * @param {string} email
   * @param {string} password
   * @returns {Promise<{ access_token: string, token_type: string, expires_in: number }>}
   */
  async login(email, password) {
    try {
      const response = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });
      const data = await parseResponse(response);
      if (data?.access_token) {
        this.setStoredToken(data.access_token);
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
   * Register a new user with email and password.
   * @param {string} email
   * @param {string} password
   * @returns {Promise<{ id: string, email: string, is_active: boolean }>}
   */
  async register(email, password) {
    try {
      const response = await fetch(`${API_BASE}/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });
      return await parseResponse(response);
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
   * Get currently authenticated user profile.
   * @param {string} [token]
   * @returns {Promise<{ id: string, email: string, is_active: boolean }>}
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
   */
  getStoredToken() {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },

  /**
   * Store access token in localStorage.
   */
  setStoredToken(token) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      // Storage unavailable or disabled
    }
  },

  /**
   * Clear access token from localStorage.
   */
  clearStoredToken() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      // Ignore
    }
  },
};
