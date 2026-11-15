const crypto = require('crypto');
const { Readable } = require('stream');
const { analysisConfig } = require('../config/analysisConfig');
const {
  AnalysisGatewayError,
  AnalysisServiceError,
  AnalysisServiceUnavailableError,
  AnalysisServiceTimeoutError,
} = require('../errors/analysisErrors');

/**
 * Service managing secure communication between Express and FastAPI analysis platform.
 * Constructs delegated headers, enforces timeouts, sanitizes upstream responses,
 * and manages resilient SSE relay.
 */
class AnalysisGatewayService {
  constructor(config = analysisConfig, fetchImpl = globalThis.fetch) {
    this.config = config;
    this.fetch = fetchImpl;
  }

  /**
   * Construct trusted delegation headers required by FastAPI backend.
   */
  buildDelegatedHeaders({ user, role, projectId, correlationId, isHealth = false }) {
    if (!user || !user.id) {
      throw new AnalysisServiceError('Valid authenticated user is required for delegation.');
    }
    if (isHealth) {
      return {
        'X-Service-Token': this.config.secretKey,
        'X-Actor-Id': String(user.id),
        'X-Correlation-Id': String(correlationId || crypto.randomUUID()),
      };
    }
    if (!role) {
      throw new AnalysisServiceError('Authoritative project role is required for delegation.');
    }
    if (!projectId) {
      throw new AnalysisServiceError('Target project ID is required for delegation.');
    }

    return {
      'X-Service-Token': this.config.secretKey,
      'X-Actor-Id': String(user.id),
      'X-Actor-Role': String(role).toUpperCase(),
      'X-Project-Id': String(projectId),
      'X-Correlation-Id': String(correlationId || crypto.randomUUID()),
    };
  }

  /**
   * Execute a bounded, delegated JSON request to FastAPI.
   */
  async request({
    method = 'GET',
    path,
    query = {},
    body,
    user,
    role,
    projectId,
    correlationId,
    timeoutMs,
    responseMode = 'default',
    clientReq,
  }) {
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    const isHealth = responseMode === 'graph' && cleanPath === '/health/graph/query';

    const headers = this.buildDelegatedHeaders({
      user,
      role,
      projectId,
      correlationId,
      isHealth,
    });

    const queryString = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) {
        if (Array.isArray(value)) {
          for (const item of value) {
            if (item !== undefined && item !== null) {
              queryString.append(key, String(item));
            }
          }
        } else {
          queryString.append(key, String(value));
        }
      }
    }
    const qs = queryString.toString();
    const url = `${this.config.baseUrl}${cleanPath}${qs ? `?${qs}` : ''}`;

    const controller = new AbortController();
    const effectiveTimeout = timeoutMs || this.config.jsonTimeoutMs;
    const timeoutHandle = setTimeout(() => controller.abort(), effectiveTimeout);
    let responseCompleted = false;

    let clientCloseHandler = null;
    if (clientReq && typeof clientReq.on === 'function') {
      clientCloseHandler = () => {
        if (!responseCompleted) {
          controller.abort();
        }
      };
      clientReq.on('close', clientCloseHandler);
    }

    const fetchOptions = {
      method,
      headers: {
        ...headers,
        Accept: 'application/json',
      },
      signal: controller.signal,
    };

    if (responseMode === 'graph') {
      fetchOptions.redirect = 'manual';
    }

    if (body !== undefined && body !== null) {
      fetchOptions.headers['Content-Type'] = 'application/json';
      fetchOptions.body = JSON.stringify(body);
    }

    try {
      const response = await this.fetch(url, fetchOptions);

      if (responseMode === 'graph' && response.status >= 300 && response.status < 400) {
        throw new AnalysisServiceError('Upstream redirected unexpectedly.');
      }

      if (response.status === 204) {
        return responseMode === 'graph' ? { status: 204, body: null } : null;
      }

      let data;
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        try {
          data = await response.json();
        } catch (_) {
          data = null;
        }
      }

      if (responseMode === 'graph') {
        if (response.ok) {
          if (data === null || data === undefined) {
            throw new AnalysisServiceError('Analysis service returned an invalid response format.');
          }
          return { status: response.status, body: data };
        }

        // Upstream error in graph mode: preserve recognized shapes
        if (response.status >= 400) {
          if (data && data.error && typeof data.error.code === 'string') {
            return {
              status: response.status,
              body: {
                error: {
                  code: data.error.code,
                  message: typeof data.error.message === 'string' ? data.error.message : 'Upstream error.',
                  details: data.error.details || {},
                },
              },
            };
          }
          if (response.status === 422 && data && Array.isArray(data.detail)) {
            return {
              status: 422,
              body: {
                detail: data.detail,
              },
            };
          }
          // Unrecognized upstream 4xx/5xx error: sanitize into standard error envelope with the HTTP status
          return {
            status: response.status,
            body: {
              error: {
                code: 'analysis_service_error',
                message: 'Analysis service encountered an unexpected error.',
                details: {},
              },
            },
          };
        }
      }

      if (response.ok) {
        return data;
      }

      // Upstream returned an error status (default mode)
      if (response.status >= 400 && response.status < 500) {
        if (data && data.error) {
          throw new AnalysisGatewayError(
            data.error.message || 'Upstream request failed.',
            data.error.code || 'upstream_validation_error',
            response.status,
            data.error.details || {}
          );
        }
        if (data && data.detail) {
          const message = typeof data.detail === 'string' ? data.detail : 'Validation error';
          throw new AnalysisGatewayError(
            message,
            'upstream_client_error',
            response.status,
            Array.isArray(data.detail) ? { issues: data.detail } : {}
          );
        }
        throw new AnalysisGatewayError(
          'Upstream request failed with a client error.',
          'upstream_client_error',
          response.status,
          {}
        );
      }

      // 5xx error from upstream: do not relay internal detail or stack trace
      throw new AnalysisServiceError('Analysis service encountered an unexpected error.');
    } catch (err) {
      if (err instanceof AnalysisGatewayError) {
        throw err;
      }
      if (err.name === 'AbortError') {
        throw new AnalysisServiceTimeoutError('Analysis service request timed out.');
      }
      if (
        err.code === 'ECONNREFUSED' ||
        err.code === 'ENOTFOUND' ||
        (err.message && err.message.toLowerCase().includes('fetch failed'))
      ) {
        throw new AnalysisServiceUnavailableError('Analysis service is currently unavailable.');
      }
      throw new AnalysisServiceError('Analysis service encountered an unexpected error.');
    } finally {
      responseCompleted = true;
      clearTimeout(timeoutHandle);
      if (clientReq && clientCloseHandler && typeof clientReq.off === 'function') {
        clientReq.off('close', clientCloseHandler);
      }
    }
  }

  /**
   * Stream Server-Sent Events from FastAPI to client response.
   */
  async streamEvents({
    analysisId,
    projectId,
    afterSequence = 0,
    lastEventId,
    user,
    role,
    correlationId,
    clientReq,
    clientRes,
  }) {
    const headers = this.buildDelegatedHeaders({
      user,
      role,
      projectId,
      correlationId,
    });

    const queryString = new URLSearchParams({
      project_id: String(projectId),
      after_sequence: String(afterSequence),
    });
    const url = `${this.config.baseUrl}/analyses/${encodeURIComponent(analysisId)}/events?${queryString}`;

    const controller = new AbortController();
    const timeoutHandle = setTimeout(() => controller.abort(), this.config.sseTimeoutMs);

    const abortHandler = () => {
      controller.abort();
    };
    clientReq.on('close', abortHandler);

    const upstreamHeaders = {
      ...headers,
      Accept: 'text/event-stream',
    };
    if (lastEventId) {
      upstreamHeaders['Last-Event-ID'] = String(lastEventId);
    }

    try {
      const response = await this.fetch(url, {
        method: 'GET',
        headers: upstreamHeaders,
        signal: controller.signal,
      });

      if (!response.ok) {
        clearTimeout(timeoutHandle);
        clientReq.off('close', abortHandler);
        let errorData;
        try {
          errorData = await response.json();
        } catch (_) {
          errorData = null;
        }

        if (response.status >= 400 && response.status < 500 && errorData && errorData.error) {
          throw new AnalysisGatewayError(
            errorData.error.message,
            errorData.error.code,
            response.status,
            errorData.error.details || {}
          );
        }
        if (response.status === 404) {
          throw new AnalysisGatewayError('Analysis not found.', 'analysis_not_found', 404);
        }
        throw new AnalysisServiceError('Failed to establish event stream from analysis service.');
      }

      clientRes.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
      });
      if (typeof clientRes.flushHeaders === 'function') {
        clientRes.flushHeaders();
      }

      if (!response.body) {
        clearTimeout(timeoutHandle);
        clientReq.off('close', abortHandler);
        clientRes.end();
        return;
      }

      const stream = Readable.fromWeb(response.body);
      stream.on('error', () => {
        clearTimeout(timeoutHandle);
        controller.abort();
        clientRes.end();
      });

      stream.on('end', () => {
        clearTimeout(timeoutHandle);
        clientReq.off('close', abortHandler);
        clientRes.end();
      });

      stream.pipe(clientRes);
    } catch (err) {
      clearTimeout(timeoutHandle);
      clientReq.off('close', abortHandler);
      if (clientRes.headersSent) {
        clientRes.end();
        return;
      }
      if (err instanceof AnalysisGatewayError) {
        throw err;
      }
      if (err.name === 'AbortError') {
        throw new AnalysisServiceTimeoutError('Event stream connection timed out.');
      }
      if (
        err.code === 'ECONNREFUSED' ||
        err.code === 'ENOTFOUND' ||
        (err.message && err.message.toLowerCase().includes('fetch failed'))
      ) {
        throw new AnalysisServiceUnavailableError('Analysis service is currently unavailable.');
      }
      throw new AnalysisServiceError('Failed to establish event stream.');
    }
  }
}

const analysisGatewayService = new AnalysisGatewayService();

module.exports = {
  AnalysisGatewayService,
  analysisGatewayService,
};

