const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
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
    this.activeArtifactRelays = 0;
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
    clientRes,
    maxBytes,
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
    if (responseMode === 'intelligence') {
      if (clientRes && typeof clientRes.on === 'function') {
        clientCloseHandler = () => {
          if (!responseCompleted && !clientRes.writableFinished) {
            controller.abort();
          }
        };
        clientRes.on('close', clientCloseHandler);
      } else if (clientReq && typeof clientReq.on === 'function') {
        clientCloseHandler = () => {
          if (!responseCompleted && (clientReq.aborted || clientReq.destroyed)) {
            controller.abort();
          }
        };
        clientReq.on('close', clientCloseHandler);
      }
    } else if (clientReq && typeof clientReq.on === 'function') {
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

    if (responseMode === 'graph' || responseMode === 'intelligence') {
      fetchOptions.redirect = 'manual';
    }

    if (body !== undefined && body !== null) {
      fetchOptions.headers['Content-Type'] = 'application/json';
      fetchOptions.body = JSON.stringify(body);
    }

    try {
      const response = await this.fetch(url, fetchOptions);

      if (
        (responseMode === 'graph' || responseMode === 'intelligence') &&
        response.status >= 300 &&
        response.status < 400
      ) {
        if (responseMode === 'intelligence') {
          throw new AnalysisGatewayError(
            'Upstream redirected unexpectedly.',
            'intelligence_upstream_invalid',
            502
          );
        }
        throw new AnalysisServiceError('Upstream redirected unexpectedly.');
      }

      if (response.status === 204) {
        return responseMode === 'graph' || responseMode === 'intelligence'
          ? { status: 204, body: null }
          : null;
      }

      let data;
      const contentType = response.headers.get('content-type') || '';
      if (responseMode === 'intelligence') {
        const effectiveMaxBytes =
          maxBytes || this.config.intelligenceJsonResponseMaxBytes || 4194304;
        if (contentType.includes('application/json')) {
          if (response.body && typeof response.body.getReader === 'function') {
            const reader = response.body.getReader();
            let totalBytes = 0;
            const chunks = [];
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              totalBytes += value.length;
              if (totalBytes > effectiveMaxBytes) {
                await reader.cancel();
                throw new AnalysisGatewayError(
                  `Upstream response body exceeded limit of ${effectiveMaxBytes} bytes.`,
                  'intelligence_upstream_invalid',
                  502,
                  { max_bytes: effectiveMaxBytes, actual_bytes: totalBytes }
                );
              }
              chunks.push(value);
            }
            const fullBuf = Buffer.concat(chunks.map((c) => Buffer.from(c)));
            if (fullBuf.length > 0) {
              try {
                data = JSON.parse(fullBuf.toString('utf8'));
              } catch (_) {
                data = null;
              }
            } else {
              data = null;
            }
          } else if (typeof response.json === 'function') {
            try {
              data = await response.json();
            } catch (_) {
              data = null;
            }
          }
        }
      } else if (contentType.includes('application/json')) {
        try {
          data = await response.json();
        } catch (_) {
          data = null;
        }
      }

      if (responseMode === 'intelligence') {
        if (response.ok) {
          if (data === null || data === undefined) {
            throw new AnalysisGatewayError(
              'Analysis service returned an invalid response format.',
              'intelligence_upstream_invalid',
              502
            );
          }
          return { status: response.status, body: data };
        }

        // Upstream error in intelligence mode: preserve recognized shapes and status
        if (response.status >= 400) {
          if (data && data.error && typeof data.error.code === 'string') {
            const sanitizedError = {
              code: data.error.code,
              message:
                typeof data.error.message === 'string'
                  ? data.error.message
                  : 'Upstream error.',
              details:
                typeof data.error.details === 'object' && data.error.details !== null
                  ? data.error.details
                  : {},
            };
            if (typeof data.error.cause === 'string') {
              sanitizedError.cause = data.error.cause;
            }
            return {
              status: response.status,
              body: { error: sanitizedError },
            };
          }
          if (response.status === 422 && data && Array.isArray(data.detail)) {
            return {
              status: 422,
              body: {
                detail: data.detail.map((item) => ({
                  loc: item.loc,
                  msg: item.msg,
                  type: item.type,
                })),
              },
            };
          }
          return {
            status: response.status,
            body: {
              error: {
                code:
                  response.status >= 500
                    ? 'intelligence_upstream_unavailable'
                    : 'intelligence_upstream_invalid',
                message:
                  response.status >= 500
                    ? 'Analysis service encountered an unexpected error.'
                    : 'Upstream request failed.',
                details: {},
              },
            },
          };
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
      if (responseMode === 'intelligence') {
        if (err.name === 'AbortError') {
          throw new AnalysisGatewayError(
            'Upstream request timed out.',
            'intelligence_upstream_timeout',
            504
          );
        }
        if (
          err.code === 'ECONNREFUSED' ||
          err.code === 'ENOTFOUND' ||
          (err.message && err.message.toLowerCase().includes('fetch failed'))
        ) {
          throw new AnalysisGatewayError(
            'Analysis service is currently unavailable.',
            'intelligence_upstream_unavailable',
            503
          );
        }
        throw new AnalysisGatewayError(
          'Analysis service encountered an unexpected error.',
          'intelligence_upstream_invalid',
          502
        );
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
      if (clientRes && clientCloseHandler && typeof clientRes.off === 'function') {
        clientRes.off('close', clientCloseHandler);
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

  /**
   * Clean old spool directories from previous crashes.
   */
  async cleanOldSpools(spoolBase) {
    try {
      if (!fs.existsSync(spoolBase)) return;
      const entries = await fs.promises.readdir(spoolBase, { withFileTypes: true });
      const now = Date.now();
      const maxAgeMs = 3600000; // 1 hour
      for (const entry of entries) {
        if (entry.isDirectory() && entry.name.startsWith('relay-')) {
          const dirPath = path.join(spoolBase, entry.name);
          const stat = await fs.promises.stat(dirPath);
          if (now - stat.mtimeMs > maxAgeMs) {
            await fs.promises.rm(dirPath, { recursive: true, force: true }).catch(() => {});
          }
        }
      }
    } catch (_) {}
  }

  /**
   * Stream a binary intelligence artifact (PDF/SVG) via private disk spooling with digest verification.
   */
  async streamArtifact({
    method = 'GET',
    path: reqPath,
    query = {},
    user,
    role,
    projectId,
    correlationId,
    clientReq,
    clientRes,
    expectedMediaType,
    maxBytes,
    timeoutMs,
    attachmentFilename,
  }) {
    if (clientReq && clientReq.headers && clientReq.headers['range']) {
      return clientRes.status(416).json({
        error: {
          code: 'intelligence_transport_range_not_supported',
          message: 'Byte range requests are not supported for intelligence artifacts.',
          details: {},
        },
      });
    }

    const maxRelays = this.config.intelligenceMaxConcurrentArtifactRelays || 2;
    if (this.activeArtifactRelays >= maxRelays) {
      return clientRes.status(503).json({
        error: {
          code: 'intelligence_transport_busy',
          message: 'Too many concurrent artifact downloads. Please try again shortly.',
          details: {},
        },
      });
    }
    this.activeArtifactRelays++;

    const effectiveMaxBytes =
      maxBytes ||
      (expectedMediaType === 'image/svg+xml'
        ? this.config.intelligenceDiagramSvgMaxBytes
        : this.config.intelligencePdfMaxBytes) ||
      67108864;
    const effectiveTimeout =
      timeoutMs || this.config.intelligenceArtifactCombinedTimeoutMs || 150000;

    const spoolBase =
      this.config.intelligenceArtifactSpoolDir ||
      path.join(os.tmpdir(), 'stacksense-intelligence-spool');
    let tempDir = null;
    let tempFilePath = null;
    const controller = new AbortController();
    const timeoutHandle = setTimeout(() => controller.abort(), effectiveTimeout);

    const cleanPath = reqPath.startsWith('/') ? reqPath : `/${reqPath}`;
    const headers = this.buildDelegatedHeaders({
      user,
      role,
      projectId,
      correlationId,
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

    const clientCloseHandler = () => {
      if (!clientRes.writableFinished) {
        controller.abort();
      }
    };
    if (clientRes && typeof clientRes.on === 'function') {
      clientRes.on('close', clientCloseHandler);
    }

    try {
      await fs.promises.mkdir(spoolBase, { recursive: true, mode: 0o700 });
      this.cleanOldSpools(spoolBase);
      tempDir = await fs.promises.mkdtemp(path.join(spoolBase, 'relay-'));
      tempFilePath = path.join(tempDir, 'artifact.bin');

      const upstreamHeaders = {
        ...headers,
        Accept: expectedMediaType,
        'Accept-Encoding': 'identity',
      };

      const response = await this.fetch(url, {
        method,
        headers: upstreamHeaders,
        redirect: 'manual',
        signal: controller.signal,
      });

      if (response.status >= 300 && response.status < 400) {
        return clientRes.status(502).json({
          error: {
            code: 'intelligence_upstream_invalid',
            message: 'Upstream redirected unexpectedly.',
            details: {},
          },
        });
      }

      if (!response.ok) {
        let errorData = null;
        try {
          errorData = await response.json();
        } catch (_) {}

        if (errorData && errorData.error && typeof errorData.error.code === 'string') {
          const sanitized = {
            code: errorData.error.code,
            message:
              typeof errorData.error.message === 'string'
                ? errorData.error.message
                : 'Upstream error.',
            details:
              typeof errorData.error.details === 'object' && errorData.error.details !== null
                ? errorData.error.details
                : {},
          };
          if (typeof errorData.error.cause === 'string') {
            sanitized.cause = errorData.error.cause;
          }
          return clientRes.status(response.status).json({ error: sanitized });
        }

        return clientRes.status(response.status).json({
          error: {
            code:
              response.status >= 500
                ? 'intelligence_upstream_unavailable'
                : 'intelligence_upstream_invalid',
            message:
              response.status >= 500
                ? 'Analysis service encountered an unexpected error.'
                : 'Upstream request failed.',
            details: {},
          },
        });
      }

      const contentType = (response.headers.get('content-type') || '')
        .split(';')[0]
        .trim()
        .toLowerCase();
      if (contentType !== expectedMediaType) {
        return clientRes.status(502).json({
          error: {
            code: 'intelligence_upstream_invalid',
            message: `Expected ${expectedMediaType} but received ${contentType || 'unknown'}.`,
            details: {},
          },
        });
      }
      const contentEncoding = response.headers.get('content-encoding');
      if (contentEncoding && contentEncoding.toLowerCase() !== 'identity') {
        return clientRes.status(502).json({ error: { code: 'intelligence_upstream_invalid', message: 'Encoded artifact responses are not supported.', details: {} } });
      }

      const hash = crypto.createHash('sha256');
      let totalBytes = 0;
      const writeStream = fs.createWriteStream(tempFilePath, { mode: 0o600 });

      if (response.body && typeof response.body.getReader === 'function') {
        const reader = response.body.getReader();
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            totalBytes += value.length;
            if (totalBytes > effectiveMaxBytes) {
              await reader.cancel();
              writeStream.destroy();
              return clientRes.status(413).json({
                error: {
                  code: 'intelligence_transport_limit',
                  message: `Artifact size exceeded maximum allowed limit of ${effectiveMaxBytes} bytes.`,
                  details: { max_bytes: effectiveMaxBytes, actual_bytes: totalBytes },
                },
              });
            }
            hash.update(value);
            if (!writeStream.write(value)) {
              await new Promise((resolve) => writeStream.once('drain', resolve));
            }
          }
        } finally {
          await new Promise((resolve, reject) => {
            writeStream.end((err) => (err ? reject(err) : resolve()));
          });
        }
      } else if (response.body && typeof response.body.on === 'function') {
        await new Promise((resolve, reject) => {
          response.body.on('data', (chunk) => {
            totalBytes += chunk.length;
            if (totalBytes > effectiveMaxBytes) {
              response.body.destroy();
              writeStream.destroy();
              reject(
                new AnalysisGatewayError(
                  `Artifact size exceeded maximum allowed limit of ${effectiveMaxBytes} bytes.`,
                  'intelligence_transport_limit',
                  413,
                  { max_bytes: effectiveMaxBytes, actual_bytes: totalBytes }
                )
              );
              return;
            }
            hash.update(chunk);
            if (!writeStream.write(chunk)) {
              response.body.pause();
              writeStream.once('drain', () => response.body.resume());
            }
          });
          response.body.on('end', () => {
            writeStream.end(resolve);
          });
          response.body.on('error', reject);
          writeStream.on('error', reject);
        });
      } else {
        writeStream.destroy();
        return clientRes.status(502).json({
          error: {
            code: 'intelligence_upstream_invalid',
            message: 'Upstream artifact response contained no body.',
            details: {},
          },
        });
      }

      const sha256Buffer = hash.digest();
      const computedSha256Hex = sha256Buffer.toString('hex');
      const computedSha256B64 = sha256Buffer.toString('base64');

      const upstreamDigest = response.headers.get('content-digest');
      const digestMatch = upstreamDigest?.match(/^sha-256=:([A-Za-z0-9+/]{43}=):$/i);
      if (!digestMatch) {
        return clientRes.status(502).json({ error: { code: 'intelligence_upstream_invalid', message: 'Missing or malformed artifact Content-Digest.', details: {} } });
      }
      if (digestMatch[1] !== computedSha256B64) {
        return clientRes.status(502).json({
          error: {
            code: 'intelligence_upstream_invalid',
            message: 'Artifact Content-Digest mismatch.',
            details: {},
          },
        });
      }

      const upstreamLength = response.headers.get('content-length');
      if (!upstreamLength || !/^\d+$/.test(upstreamLength)) {
        return clientRes.status(502).json({ error: { code: 'intelligence_upstream_invalid', message: 'Missing or malformed artifact Content-Length.', details: {} } });
      }
      if (upstreamLength) {
        const expectedLen = parseInt(upstreamLength, 10);
        if (!isNaN(expectedLen) && expectedLen !== totalBytes) {
          return clientRes.status(502).json({
            error: {
              code: 'intelligence_upstream_invalid',
              message: 'Artifact Content-Length mismatch.',
              details: { expected_bytes: expectedLen, actual_bytes: totalBytes },
            },
          });
        }
      }

      const upstreamETag = response.headers.get('etag');
      if (upstreamETag) {
        const cleanETag = upstreamETag.replace(/^W\//, '').replace(/"/g, '');
        if (cleanETag.toLowerCase() !== computedSha256Hex.toLowerCase()) {
          return clientRes.status(502).json({
            error: {
              code: 'intelligence_upstream_invalid',
              message: 'Artifact ETag mismatch.',
              details: {},
            },
          });
        }
      }

      const safeFilename = attachmentFilename
        ? attachmentFilename.replace(/[^a-zA-Z0-9._-]/g, '_')
        : `artifact-${computedSha256Hex.slice(0, 12)}.${
            expectedMediaType === 'image/svg+xml' ? 'svg' : 'pdf'
          }`;

      const outHeaders = {
        'Content-Type': expectedMediaType,
        'Content-Length': String(totalBytes),
        'Content-Digest': `sha-256=:${computedSha256B64}:`,
        ETag: `"${computedSha256Hex}"`,
        'Cache-Control': 'private, no-store',
        'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': `attachment; filename="${safeFilename}"`,
      };

      clientRes.writeHead(200, outHeaders);

      const readStream = fs.createReadStream(tempFilePath);
      await new Promise((resolve, reject) => {
        const abortRelay = () => {
          readStream.destroy();
          clientRes.destroy();
          resolve();
        };
        controller.signal.addEventListener('abort', abortRelay, { once: true });
        if (controller.signal.aborted) return abortRelay();
        readStream.pipe(clientRes);
        readStream.on('error', (err) => {
          clientRes.destroy();
          reject(err);
        });
        const finish = () => {
          controller.signal.removeEventListener('abort', abortRelay);
          readStream.destroy();
          resolve();
        };
        clientRes.on('finish', finish);
        clientRes.on('close', finish);
      });
    } catch (err) {
      if (clientRes.headersSent) {
        clientRes.destroy();
        return;
      }
      if (err instanceof AnalysisGatewayError) {
        return clientRes.status(err.status || 502).json({
          error: {
            code: err.code || 'intelligence_upstream_invalid',
            message: err.message,
            details: err.details || {},
          },
        });
      }
      if (err.name === 'AbortError') {
        return clientRes.status(504).json({
          error: {
            code: 'intelligence_upstream_timeout',
            message: 'Artifact relay timed out.',
            details: {},
          },
        });
      }
      if (
        err.code === 'ECONNREFUSED' ||
        err.code === 'ENOTFOUND' ||
        (err.message && err.message.toLowerCase().includes('fetch failed'))
      ) {
        return clientRes.status(503).json({
          error: {
            code: 'intelligence_upstream_unavailable',
            message: 'Analysis service is currently unavailable.',
            details: {},
          },
        });
      }
      return clientRes.status(502).json({
        error: {
          code: 'intelligence_upstream_invalid',
          message: 'Failed to relay artifact from analysis service.',
          details: {},
        },
      });
    } finally {
      this.activeArtifactRelays--;
      clearTimeout(timeoutHandle);
      if (clientReq && typeof clientReq.off === 'function') {
        clientReq.off('close', clientCloseHandler);
      }
      if (clientRes && typeof clientRes.off === 'function') {
        clientRes.off('close', clientCloseHandler);
      }
      if (tempDir) {
        try {
          await fs.promises.rm(tempDir, { recursive: true, force: true });
        } catch (_) {}
      }
    }
  }
}

const analysisGatewayService = new AnalysisGatewayService();

module.exports = {
  AnalysisGatewayService,
  analysisGatewayService,
};

