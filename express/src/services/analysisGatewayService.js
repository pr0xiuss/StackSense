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
  buildDelegatedHeaders({ user, role, projectId, correlationId }) {
    if (!user || !user.id) {
      throw new AnalysisServiceError('Valid authenticated user is required for delegation.');
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
  }) {
    const headers = this.buildDelegatedHeaders({
      user,
      role,
      projectId,
      correlationId,
    });

    const queryString = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) {
        queryString.append(key, String(value));
      }
    }
    const qs = queryString.toString();
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    const url = `${this.config.baseUrl}${cleanPath}${qs ? `?${qs}` : ''}`;

    const controller = new AbortController();
    const effectiveTimeout = timeoutMs || this.config.jsonTimeoutMs;
    const timeoutHandle = setTimeout(() => controller.abort(), effectiveTimeout);

    const fetchOptions = {
      method,
      headers: {
        ...headers,
        Accept: 'application/json',
      },
      signal: controller.signal,
    };

    if (body !== undefined && body !== null) {
      fetchOptions.headers['Content-Type'] = 'application/json';
      fetchOptions.body = JSON.stringify(body);
    }

    try {
      const response = await this.fetch(url, fetchOptions);
      clearTimeout(timeoutHandle);

      if (response.status === 204) {
        return null;
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

      if (response.ok) {
        return data;
      }

      // Upstream returned an error status
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
      clearTimeout(timeoutHandle);
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

