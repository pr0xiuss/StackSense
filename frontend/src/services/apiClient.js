/**
 * StackSense Centralized API Client
 *
 * Enforces:
 * - Single source of truth for backend communication
 * - Automatic Authorization: Bearer <access_token> attachment
 * - Automatic 401 interceptor with token refresh
 * - Shared refresh promise to prevent concurrent refresh storms
 * - Single-retry loop protection
 * - Event dispatching on unrecoverable auth failure
 */

export const ACCESS_TOKEN_KEY = 'stacksense_access_token';
export const REFRESH_TOKEN_KEY = 'stacksense_refresh_token';
export const LEGACY_TOKEN_KEY = 'stacksense_auth_token';

export class ApiError extends Error {
  constructor(message, status = 500, code = 'api_error', details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let isRefreshing = false;
let refreshPromise = null;

export const tokenStorage = {
  getAccessToken() {
    try {
      return localStorage.getItem(ACCESS_TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY);
    } catch {
      return null;
    }
  },

  getRefreshToken() {
    try {
      return localStorage.getItem(REFRESH_TOKEN_KEY);
    } catch {
      return null;
    }
  },

  setTokens(accessToken, refreshToken) {
    try {
      if (accessToken) localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
      if (refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    } catch {
      // Storage unavailable
    }
  },

  clearTokens() {
    try {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      localStorage.removeItem(LEGACY_TOKEN_KEY);
    } catch {
      // Storage unavailable
    }
  },
};

/**
 * Perform token rotation with concurrency and loop protection.
 * Returns the fresh access token, or throws an ApiError if refresh fails.
 */
async function refreshAccessToken() {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }

  const currentRefreshToken = tokenStorage.getRefreshToken();
  if (!currentRefreshToken) {
    tokenStorage.clearTokens();
    window.dispatchEvent(new CustomEvent('auth:expired'));
    throw new ApiError('Session expired. Please log in again.', 401, 'session_expired');
  }

  isRefreshing = true;
  refreshPromise = (async () => {
    let response;
    try {
      response = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: currentRefreshToken.trim() }),
      });
    } catch (networkErr) {
      // Network failure (offline, timeout, connection drop):
      // Do NOT clear tokens or dispatch auth:expired!
      throw new ApiError(
        'Network error while refreshing session. Please check your connection.',
        0,
        'network_error'
      );
    }

    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }

    // Definitive authentication failure: invalid, expired, or revoked refresh token
    if (response.status === 401 || response.status === 403) {
      tokenStorage.clearTokens();
      window.dispatchEvent(new CustomEvent('auth:expired'));
      const errorCode = data?.error?.code || 'refresh_failed';
      const errorMessage =
        data?.error?.message ||
        data?.detail ||
        'Session expired. Please log in again.';
      throw new ApiError(errorMessage, response.status, errorCode);
    }

    if (!response.ok) {
      // Transient server/gateway error (5xx, etc.): do NOT clear tokens
      const errorCode = data?.error?.code || 'server_error';
      const errorMessage =
        data?.error?.message ||
        data?.detail ||
        `Failed to refresh session (${response.status}).`;
      throw new ApiError(errorMessage, response.status, errorCode);
    }

    if (data?.access_token) {
      tokenStorage.setTokens(data.access_token, data.refresh_token);
      return data.access_token;
    }

    // Response succeeded but had unexpected structure: do not evict user session
    throw new ApiError('Invalid refresh response from server.', 500, 'invalid_response');
  })().finally(() => {
    isRefreshing = false;
    refreshPromise = null;
  });

  return refreshPromise;
}

/**
 * Centralized fetch wrapper
 *
 * @param {string} endpoint - API path, e.g. '/api/v1/projects' or 'projects'
 * @param {RequestInit & { _retry?: boolean, skipAuth?: boolean }} options
 */
export async function apiRequest(endpoint, options = {}) {
  const url = endpoint.startsWith('http')
    ? endpoint
    : endpoint.startsWith('/api/')
      ? endpoint
      : endpoint.startsWith('/')
        ? `/api/v1${endpoint}`
        : `/api/v1/${endpoint}`;

  const isAuthEndpoint =
    url.includes('/auth/login') ||
    url.includes('/auth/register') ||
    url.includes('/auth/refresh');

  const headers = new Headers(options.headers || {});

  // Automatically attach access token if not an unauthenticated/auth endpoint
  if (!options.skipAuth && !isAuthEndpoint) {
    const token = tokenStorage.getAccessToken();
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  // Set Content-Type: application/json if sending an object payload that is not FormData
  if (
    options.body &&
    !(options.body instanceof FormData) &&
    typeof options.body === 'object' &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json');
    options.body = JSON.stringify(options.body);
  }

  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (netErr) {
    throw new ApiError(
      'Network connection error. Please verify the server is running.',
      0,
      'network_error'
    );
  }

  // Handle 401 Unauthorized for authenticated requests (with single retry and loop protection)
  if (response.status === 401 && !options._retry && !isAuthEndpoint && !options.skipAuth) {
    try {
      const newAccessToken = await refreshAccessToken();
      const retryHeaders = new Headers(headers);
      retryHeaders.set('Authorization', `Bearer ${newAccessToken}`);

      return apiRequest(endpoint, {
        ...options,
        headers: retryHeaders,
        _retry: true,
      });
    } catch (refreshErr) {
      throw refreshErr;
    }
  }

  // 204 No Content
  if (response.status === 204) {
    return null;
  }

  let data = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    try {
      data = await response.text();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const errorPayload = data?.error;
    const message =
      errorPayload?.message ||
      (data?.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : null) ||
      `Request failed with status ${response.status}`;
    const code = errorPayload?.code || (response.status === 403 ? 'forbidden' : response.status === 404 ? 'not_found' : 'api_error');
    const details = errorPayload?.details || data?.detail || null;

    throw new ApiError(message, response.status, code, details);
  }

  return data;
}

export const apiClient = {
  get(endpoint, options = {}) {
    return apiRequest(endpoint, { ...options, method: 'GET' });
  },

  post(endpoint, body, options = {}) {
    return apiRequest(endpoint, { ...options, method: 'POST', body });
  },

  patch(endpoint, body, options = {}) {
    return apiRequest(endpoint, { ...options, method: 'PATCH', body });
  },

  put(endpoint, body, options = {}) {
    return apiRequest(endpoint, { ...options, method: 'PUT', body });
  },

  delete(endpoint, options = {}) {
    return apiRequest(endpoint, { ...options, method: 'DELETE' });
  },
};
