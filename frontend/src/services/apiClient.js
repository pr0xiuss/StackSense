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
    if (netErr.name === 'AbortError' || options.signal?.aborted) {
      throw netErr;
    }
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
    if (options.maxBytes && response.body && typeof response.body.getReader === 'function') {
      const reader = response.body.getReader();
      let totalBytes = 0;
      const chunks = [];
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        totalBytes += value.length;
        if (totalBytes > options.maxBytes) {
          await reader.cancel();
          throw new ApiError(
            `Response exceeded maximum allowed size of ${options.maxBytes} bytes.`,
            502,
            'response_limit_exceeded',
            { max_bytes: options.maxBytes, actual_bytes: totalBytes }
          );
        }
        chunks.push(value);
      }
      const fullBuffer = new Uint8Array(totalBytes);
      let offset = 0;
      for (const chunk of chunks) {
        fullBuffer.set(chunk, offset);
        offset += chunk.length;
      }
      const text = new TextDecoder('utf-8').decode(fullBuffer);
      try {
        data = JSON.parse(text);
      } catch {
        data = null;
      }
    } else {
      try {
        data = await response.json();
      } catch {
        data = null;
      }
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

/**
 * Stream SSE events using authenticated fetch + ReadableStream.
 *
 * @param {string} endpoint - API path, e.g. '/analyses/:id/events?project_id=...'
 * @param {object} options
 * @param {AbortSignal} [options.signal]
 * @param {HeadersInit} [options.headers]
 * @param {boolean} [options.skipAuth]
 * @param {function(Response): void} [options.onOpen]
 * @param {function({ event: string, id: string|null, data: any }): void} [options.onMessage]
 * @param {function(Error): void} [options.onError]
 * @param {function(): void} [options.onClose]
 * @returns {{ abort: (reason?: any) => void }}
 */
export function apiStream(endpoint, options = {}) {
  const url = endpoint.startsWith('http')
    ? endpoint
    : endpoint.startsWith('/api/')
      ? endpoint
      : endpoint.startsWith('/')
        ? `/api/v1${endpoint}`
        : `/api/v1/${endpoint}`;

  const controller = new AbortController();

  if (options.signal) {
    if (options.signal.aborted) {
      controller.abort(options.signal.reason);
    } else {
      options.signal.addEventListener('abort', () => controller.abort(options.signal.reason), { once: true });
    }
  }

  const run = async (retry = false) => {
    if (controller.signal.aborted) return;

    const headers = new Headers(options.headers || {});
    if (!options.skipAuth) {
      const token = tokenStorage.getAccessToken();
      if (token && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`);
      }
    }
    if (!headers.has('Accept')) {
      headers.set('Accept', 'text/event-stream');
    }

    let response;
    try {
      response = await fetch(url, {
        method: 'GET',
        headers,
        signal: controller.signal,
      });
    } catch (netErr) {
      if (controller.signal.aborted) return;
      const error = new ApiError(
        'Network error connecting to event stream.',
        0,
        'network_error'
      );
      options.onError?.(error);
      return;
    }

    // 401 retry with token rotation
    if (response.status === 401 && !retry && !options.skipAuth) {
      try {
        await refreshAccessToken();
        return run(true);
      } catch (refreshErr) {
        if (!controller.signal.aborted) {
          options.onError?.(refreshErr);
        }
        return;
      }
    }

    if (!response.ok) {
      let data = null;
      try {
        data = await response.json();
      } catch {
        try {
          data = await response.text();
        } catch {
          data = null;
        }
      }
      const errorPayload = data?.error;
      const message =
        errorPayload?.message ||
        data?.detail ||
        `Stream failed with status ${response.status}`;
      const code =
        errorPayload?.code ||
        (response.status === 403 ? 'forbidden' : response.status === 404 ? 'not_found' : 'api_error');
      const details = errorPayload?.details || data?.detail || null;
      const apiErr = new ApiError(message, response.status, code, details);
      if (!controller.signal.aborted) {
        options.onError?.(apiErr);
      }
      return;
    }

    options.onOpen?.(response);

    if (!response.body) {
      options.onClose?.();
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    const processBlock = (block) => {
      if (!block.trim()) return;
      const lines = block.split(/\r?\n/);
      let event = 'message';
      let id = null;
      const dataLines = [];

      for (const line of lines) {
        if (line.startsWith(':')) {
          // SSE comment/heartbeat
          continue;
        }
        if (line.startsWith('event:')) {
          event = line.slice(6).trim();
        } else if (line.startsWith('id:')) {
          id = line.slice(3).trim();
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trimStart());
        }
      }

      if (dataLines.length > 0) {
        const rawData = dataLines.join('\n');
        let parsed = rawData;
        try {
          parsed = JSON.parse(rawData);
        } catch {
          // Keep raw string
        }
        options.onMessage?.({ event, id, data: parsed });
      }
    };

    try {
      while (!controller.signal.aborted) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split(/\r?\n\r?\n/);
        buffer = parts.pop() || '';

        for (const block of parts) {
          processBlock(block);
        }
      }

      // Flush remainder if any
      if (buffer.trim()) {
        processBlock(buffer);
      }

      options.onClose?.();
    } catch (readErr) {
      if (!controller.signal.aborted) {
        options.onError?.(readErr);
      }
    } finally {
      try {
        reader.releaseLock();
      } catch {
        // Ignored
      }
    }
  };

  run().catch((err) => {
    if (!controller.signal.aborted) {
      options.onError?.(err);
    }
  });

  return {
    abort: (reason) => {
      try {
        controller.abort(reason);
      } catch {
        // Ignored
      }
    },
  };
}

/**
 * Bounded binary download with SHA-256 verification and blob revocation.
 *
 * @param {string} endpoint
 * @param {object} options
 * @param {string} [options.expectedMediaType='application/pdf']
 * @param {string} [options.expectedDigest] - expected SHA-256 hex or base64
 * @param {number} [options.maxBytes=67108864] - 64 MiB limit
 * @param {string} [options.filename]
 * @param {AbortSignal} [options.signal]
 * @param {boolean} [options.triggerBrowserDownload=true]
 */
export async function apiDownload(endpoint, options = {}) {
  const url = endpoint.startsWith('http')
    ? endpoint
    : endpoint.startsWith('/api/')
      ? endpoint
      : endpoint.startsWith('/')
        ? `/api/v1${endpoint}`
        : `/api/v1/${endpoint}`;

  const expectedMediaType = options.expectedMediaType || 'application/pdf';
  const maxBytes = options.maxBytes || 67108864; // 64 MiB

  const headers = new Headers(options.headers || {});
  const token = tokenStorage.getAccessToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('Accept')) {
    headers.set('Accept', expectedMediaType);
  }

  let response;
  try {
    response = await fetch(url, {
      method: 'GET',
      headers,
      signal: options.signal,
    });
  } catch (netErr) {
    if (netErr.name === 'AbortError' || options.signal?.aborted) {
      throw netErr;
    }
    throw new ApiError(
      'Network connection error. Please verify the server is running.',
      0,
      'network_error'
    );
  }

  // 401 retry
  if (response.status === 401 && !options._retry) {
    try {
      await refreshAccessToken();
      return apiDownload(endpoint, { ...options, _retry: true });
    } catch (refreshErr) {
      throw refreshErr;
    }
  }

  if (!response.ok) {
    let errData = null;
    try {
      errData = await response.json();
    } catch {
      try {
        errData = await response.text();
      } catch {
        errData = null;
      }
    }
    const errorPayload = errData?.error;
    const message =
      errorPayload?.message ||
      (typeof errData?.detail === 'string' ? errData.detail : null) ||
      `Download failed with status ${response.status}`;
    const code =
      errorPayload?.code ||
      (response.status === 403
        ? 'forbidden'
        : response.status === 404
          ? 'not_found'
          : 'api_error');
    throw new ApiError(message, response.status, code, errorPayload?.details || null);
  }

  const contentType = (response.headers.get('content-type') || '')
    .split(';')[0]
    .trim()
    .toLowerCase();
  if (contentType !== expectedMediaType) {
    throw new ApiError(
      `Expected ${expectedMediaType} but received ${contentType || 'unknown'}.`,
      502,
      'invalid_content_type'
    );
  }

  let totalBytes = 0;
  const chunks = [];
  if (response.body && typeof response.body.getReader === 'function') {
    const reader = response.body.getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      totalBytes += value.length;
      if (totalBytes > maxBytes) {
        await reader.cancel();
        throw new ApiError(
          `Artifact download exceeded limit of ${maxBytes} bytes.`,
          413,
          'download_limit_exceeded',
          { max_bytes: maxBytes, actual_bytes: totalBytes }
        );
      }
      chunks.push(value);
    }
  } else if (typeof response.arrayBuffer === 'function') {
    const buf = await response.arrayBuffer();
    const arr = new Uint8Array(buf);
    totalBytes = arr.length;
    if (totalBytes > maxBytes) {
      throw new ApiError(
        `Artifact download exceeded limit of ${maxBytes} bytes.`,
        413,
        'download_limit_exceeded',
        { max_bytes: maxBytes, actual_bytes: totalBytes }
      );
    }
    chunks.push(arr);
  }

  const fullBuffer = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    fullBuffer.set(chunk, offset);
    offset += chunk.length;
  }

  // Digest verification
  let computedSha256Hex = '';
  let computedSha256B64 = '';
  if (
    typeof crypto !== 'undefined' &&
    crypto.subtle &&
    typeof crypto.subtle.digest === 'function'
  ) {
    const hashBuf = await crypto.subtle.digest('SHA-256', fullBuffer);
    const hashArr = Array.from(new Uint8Array(hashBuf));
    computedSha256Hex = hashArr.map((b) => b.toString(16).padStart(2, '0')).join('');
    computedSha256B64 = btoa(String.fromCharCode(...hashArr));
  }

  // Verify against expected digest if provided
  if (options.expectedDigest && computedSha256Hex) {
    const cleanExpected = options.expectedDigest.replace(/"/g, '').toLowerCase();
    if (cleanExpected !== computedSha256Hex && cleanExpected !== computedSha256B64) {
      throw new ApiError(
        'Downloaded artifact digest does not match expected generation digest.',
        502,
        'digest_mismatch'
      );
    }
  }

  // Verify against Content-Digest header if present
  const contentDigestHeader = response.headers.get('content-digest');
  if (contentDigestHeader && computedSha256Hex) {
    const match =
      contentDigestHeader.match(/sha-256=:(.*?):/i) ||
      contentDigestHeader.match(/sha-256=([a-f0-9]+)/i);
    if (match) {
      const digestVal = match[1];
      if (digestVal !== computedSha256B64 && digestVal.toLowerCase() !== computedSha256Hex) {
        throw new ApiError(
          'Downloaded artifact Content-Digest header mismatch.',
          502,
          'digest_mismatch'
        );
      }
    }
  }

  // Safe filename resolution
  let filename = options.filename;
  if (!filename) {
    const disp = response.headers.get('content-disposition');
    if (disp) {
      const match = disp.match(/filename="?([^";]+)"?/i);
      if (match) filename = match[1];
    }
  }
  if (!filename) {
    filename = `artifact-${computedSha256Hex.slice(0, 12) || 'download'}.${
      expectedMediaType === 'image/svg+xml' ? 'svg' : 'pdf'
    }`;
  }
  filename = filename.replace(/[^a-zA-Z0-9._-]/g, '_');

  const blob = new Blob([fullBuffer], { type: expectedMediaType });
  let blobUrl = null;
  if (typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function') {
    blobUrl = URL.createObjectURL(blob);
  }

  if (
    options.triggerBrowserDownload !== false &&
    blobUrl &&
    typeof document !== 'undefined'
  ) {
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => {
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    }, 2000);
  }

  return {
    filename,
    size: totalBytes,
    sha256: computedSha256Hex,
    blob,
    blobUrl,
    revoke: () => {
      if (blobUrl && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(blobUrl);
      }
    },
  };
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

  stream(endpoint, options = {}) {
    return apiStream(endpoint, options);
  },

  download(endpoint, options = {}) {
    return apiDownload(endpoint, options);
  },
};
