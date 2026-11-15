const { EventEmitter, Readable } = require('stream');
const { AnalysisGatewayService } = require('../../src/services/analysisGatewayService');
const {
  AnalysisGatewayError,
  AnalysisServiceError,
  AnalysisServiceUnavailableError,
  AnalysisServiceTimeoutError,
} = require('../../src/errors/analysisErrors');

describe('AnalysisGatewayService Unit Tests', () => {
  const mockConfig = {
    baseUrl: 'http://localhost:8000/api/v1',
    secretKey: 'mock-secret-key-at-least-16-chars',
    jsonTimeoutMs: 2000,
    sseTimeoutMs: 5000,
  };

  const sampleUser = { id: '11111111-1111-4111-8111-111111111111', email: 'test@example.com' };
  const sampleProjectId = '22222222-2222-4222-8222-222222222222';

  describe('buildDelegatedHeaders', () => {
    it('constructs expected headers with uppercase role and secret', () => {
      const gateway = new AnalysisGatewayService(mockConfig);
      const headers = gateway.buildDelegatedHeaders({
        user: sampleUser,
        role: 'developer',
        projectId: sampleProjectId,
        correlationId: 'test-corr-id',
      });

      expect(headers).toEqual({
        'X-Service-Token': 'mock-secret-key-at-least-16-chars',
        'X-Actor-Id': sampleUser.id,
        'X-Actor-Role': 'DEVELOPER',
        'X-Project-Id': sampleProjectId,
        'X-Correlation-Id': 'test-corr-id',
      });
    });

    it('generates a random correlation ID if none provided', () => {
      const gateway = new AnalysisGatewayService(mockConfig);
      const headers = gateway.buildDelegatedHeaders({
        user: sampleUser,
        role: 'owner',
        projectId: sampleProjectId,
      });

      expect(headers['X-Correlation-Id']).toBeDefined();
      expect(typeof headers['X-Correlation-Id']).toBe('string');
    });

    it('throws when required fields are missing', () => {
      const gateway = new AnalysisGatewayService(mockConfig);
      expect(() => gateway.buildDelegatedHeaders({ role: 'owner', projectId: sampleProjectId })).toThrow();
      expect(() => gateway.buildDelegatedHeaders({ user: sampleUser, projectId: sampleProjectId })).toThrow();
      expect(() => gateway.buildDelegatedHeaders({ user: sampleUser, role: 'owner' })).toThrow();
    });
  });

  describe('request execution and error handling', () => {
    it('successfully executes GET and parses JSON response', async () => {
      const mockResponseData = { items: [{ id: 'a1' }], total: 1 };
      const mockFetch = jest.fn().mockResolvedValue({
        status: 200,
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockResponseData,
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'GET',
        path: '/analyses',
        query: { project_id: sampleProjectId, limit: 10 },
        user: sampleUser,
        role: 'developer',
        projectId: sampleProjectId,
      });

      expect(result).toEqual(mockResponseData);
      expect(mockFetch).toHaveBeenCalledWith(
        `http://localhost:8000/api/v1/analyses?project_id=${sampleProjectId}&limit=10`,
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'X-Service-Token': mockConfig.secretKey,
            'X-Actor-Id': sampleUser.id,
            'X-Actor-Role': 'DEVELOPER',
            'X-Project-Id': sampleProjectId,
          }),
        })
      );
    });

    it('returns null on 204 No Content', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        status: 204,
        ok: true,
        headers: new Map(),
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'DELETE',
        path: '/some-resource',
        user: sampleUser,
        role: 'admin',
        projectId: sampleProjectId,
      });

      expect(result).toBeNull();
    });

    it('passes through structured 4xx errors from upstream', async () => {
      const upstreamError = {
        error: {
          code: 'analysis_not_found',
          message: 'Analysis record was not found.',
          details: { id: 'bad-id' },
        },
      };
      const mockFetch = jest.fn().mockResolvedValue({
        status: 404,
        ok: false,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => upstreamError,
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      await expect(
        gateway.request({
          method: 'GET',
          path: '/analyses/bad-id',
          user: sampleUser,
          role: 'developer',
          projectId: sampleProjectId,
        })
      ).rejects.toMatchObject({
        status: 404,
        code: 'analysis_not_found',
        message: 'Analysis record was not found.',
        details: { id: 'bad-id' },
      });
    });

    it('sanitizes 5xx upstream errors into 502 analysis_service_error without secret or trace', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        status: 500,
        ok: false,
        headers: new Map([['content-type', 'text/html']]),
        text: async () => '<html><body>Traceback: Internal Server Error with token mock-secret-key</body></html>',
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      await expect(
        gateway.request({
          method: 'GET',
          path: '/analyses',
          user: sampleUser,
          role: 'developer',
          projectId: sampleProjectId,
        })
      ).rejects.toThrow(AnalysisServiceError);

      try {
        await gateway.request({
          method: 'GET',
          path: '/analyses',
          user: sampleUser,
          role: 'developer',
          projectId: sampleProjectId,
        });
      } catch (err) {
        expect(err.status).toBe(502);
        expect(err.code).toBe('analysis_service_error');
        expect(err.message).not.toContain('mock-secret-key');
        expect(err.message).not.toContain('Traceback');
      }
    });

    it('maps AbortError to 504 analysis_service_timeout', async () => {
      const abortError = new Error('The operation was aborted');
      abortError.name = 'AbortError';
      const mockFetch = jest.fn().mockRejectedValue(abortError);

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      await expect(
        gateway.request({
          method: 'GET',
          path: '/analyses',
          user: sampleUser,
          role: 'developer',
          projectId: sampleProjectId,
        })
      ).rejects.toThrow(AnalysisServiceTimeoutError);
    });

    it('maps network connection failure to 503 analysis_service_unavailable', async () => {
      const connError = new Error('fetch failed');
      connError.code = 'ECONNREFUSED';
      const mockFetch = jest.fn().mockRejectedValue(connError);

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      await expect(
        gateway.request({
          method: 'GET',
          path: '/analyses',
          user: sampleUser,
          role: 'developer',
          projectId: sampleProjectId,
        })
      ).rejects.toThrow(AnalysisServiceUnavailableError);
    });
  });

  describe('streamEvents relay', () => {
    it('sets SSE headers and pipes stream to client response', async () => {
      const mockStream = new Readable({
        read() {
          this.push('event: analysis.queued\ndata: {}\n\n');
          this.push(null);
        },
      });

      const mockFetch = jest.fn().mockResolvedValue({
        status: 200,
        ok: true,
        headers: new Map([['content-type', 'text/event-stream']]),
        body: Readable.toWeb(mockStream),
      });

      const clientReq = new EventEmitter();
      const clientRes = new EventEmitter();
      clientRes.writeHead = jest.fn();
      clientRes.write = jest.fn();
      clientRes.end = jest.fn();

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      await gateway.streamEvents({
        analysisId: '33333333-3333-4333-8333-333333333333',
        projectId: sampleProjectId,
        user: sampleUser,
        role: 'developer',
        clientReq,
        clientRes,
      });

      expect(clientRes.writeHead).toHaveBeenCalledWith(
        200,
        expect.objectContaining({
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          Connection: 'keep-alive',
        })
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/analyses/33333333-3333-4333-8333-333333333333/events'),
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-Service-Token': mockConfig.secretKey,
            Accept: 'text/event-stream',
          }),
        })
      );
    });

    it('throws structured error when upstream returns 404', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        status: 404,
        ok: false,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({
          error: { code: 'analysis_not_found', message: 'Not found', details: {} },
        }),
      });

      const clientReq = new EventEmitter();
      const clientRes = new EventEmitter();

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      await expect(
        gateway.streamEvents({
          analysisId: '33333333-3333-4333-8333-333333333333',
          projectId: sampleProjectId,
          user: sampleUser,
          role: 'developer',
          clientReq,
          clientRes,
        })
      ).rejects.toMatchObject({
        status: 404,
        code: 'analysis_not_found',
      });
    });
  });

  describe('graph responseMode and repeated query parameters', () => {
    it('serializes repeated array query parameters using identical repeated keys', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        status: 200,
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ nodes: [], edges: [] }),
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'GET',
        path: '/architecture-versions/123/graph/window',
        query: {
          project_id: sampleProjectId,
          canonical_kinds: ['calls', 'imports'],
        },
        user: sampleUser,
        role: 'developer',
        projectId: sampleProjectId,
        responseMode: 'graph',
      });

      expect(result).toEqual({
        status: 200,
        body: { nodes: [], edges: [] },
      });
      const calledUrl = mockFetch.mock.calls[0][0];
      expect(calledUrl).toContain('canonical_kinds=calls');
      expect(calledUrl).toContain('canonical_kinds=imports');
      expect(calledUrl).toContain(`project_id=${sampleProjectId}`);
    });

    it('returns { status: 202, body } for rebuild mutation in graph mode', async () => {
      const rebuildPayload = {
        resource_id: 'res-1',
        architecture_version_id: 'ver-1',
        status: 'RUNNING',
        attempt_id: 'att-1',
        attempt_number: 1,
        attempt_status: 'QUEUED',
        accepted_at: '2026-11-15T11:00:00Z',
      };
      const mockFetch = jest.fn().mockResolvedValue({
        status: 202,
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => rebuildPayload,
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'POST',
        path: '/architecture-versions/ver-1/graph/rebuild',
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'admin',
        projectId: sampleProjectId,
        responseMode: 'graph',
      });

      expect(result).toEqual({
        status: 202,
        body: rebuildPayload,
      });
    });

    it('returns { status: 204, body: null } for 204 No Content in graph mode', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        status: 204,
        ok: true,
        headers: new Map(),
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'GET',
        path: '/test-204',
        user: sampleUser,
        role: 'developer',
        projectId: sampleProjectId,
        responseMode: 'graph',
      });

      expect(result).toEqual({ status: 204, body: null });
    });

    it('preserves recognized structured 4xx error body in graph mode', async () => {
      const errorPayload = {
        error: {
          code: 'graph_projection_not_ready',
          message: 'Graph projection is not ready for queries',
          details: { state: 'PENDING' },
        },
      };
      const mockFetch = jest.fn().mockResolvedValue({
        status: 409,
        ok: false,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => errorPayload,
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'GET',
        path: '/architecture-versions/ver-1/graph/window',
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'developer',
        projectId: sampleProjectId,
        responseMode: 'graph',
      });

      expect(result).toEqual({
        status: 409,
        body: errorPayload,
      });
    });

    it('preserves syntactic FastAPI 422 detail array in graph mode', async () => {
      const fastapiDetail = [
        { loc: ['query', 'node_limit'], msg: 'Input should be greater than 0', type: 'greater_than' },
      ];
      const mockFetch = jest.fn().mockResolvedValue({
        status: 422,
        ok: false,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ detail: fastapiDetail }),
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'GET',
        path: '/architecture-versions/ver-1/graph/window',
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'developer',
        projectId: sampleProjectId,
        responseMode: 'graph',
      });

      expect(result).toEqual({
        status: 422,
        body: { detail: fastapiDetail },
      });
    });

    it('sanitizes unrecognized upstream errors into analysis_service_error envelope', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        status: 500,
        ok: false,
        headers: new Map([['content-type', 'text/html']]),
        json: async () => { throw new Error('not json'); },
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'GET',
        path: '/architecture-versions/ver-1/graph/window',
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'developer',
        projectId: sampleProjectId,
        responseMode: 'graph',
      });

      expect(result).toEqual({
        status: 500,
        body: {
          error: {
            code: 'analysis_service_error',
            message: 'Analysis service encountered an unexpected error.',
            details: {},
          },
        },
      });
    });

    it('rejects redirects with 502 analysis_service_error in graph mode', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        status: 302,
        ok: false,
        headers: new Map([['location', 'http://external-host.com']]),
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      await expect(
        gateway.request({
          method: 'GET',
          path: '/architecture-versions/ver-1/graph/window',
          query: { project_id: sampleProjectId },
          user: sampleUser,
          role: 'developer',
          projectId: sampleProjectId,
          responseMode: 'graph',
        })
      ).rejects.toThrow(AnalysisServiceError);
    });

    it('builds un-scoped delegation headers for GET /health/graph/query in graph mode', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        status: 200,
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => ({ status: 'ready', code: 'graph_query_ready' }),
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'GET',
        path: '/health/graph/query',
        user: sampleUser,
        correlationId: 'health-corr-id',
        responseMode: 'graph',
      });

      expect(result).toEqual({
        status: 200,
        body: { status: 'ready', code: 'graph_query_ready' },
      });

      const callHeaders = mockFetch.mock.calls[0][1].headers;
      expect(callHeaders['X-Service-Token']).toBe(mockConfig.secretKey);
      expect(callHeaders['X-Actor-Id']).toBe(sampleUser.id);
      expect(callHeaders['X-Correlation-Id']).toBe('health-corr-id');
      expect(callHeaders['X-Project-Id']).toBeUndefined();
      expect(callHeaders['X-Actor-Role']).toBeUndefined();
    });

    it('aborts upstream fetch when clientReq closes before response completes', async () => {
      const clientReq = new EventEmitter();
      let capturedSignal;
      const mockFetch = jest.fn().mockImplementation((_url, options) => {
        capturedSignal = options.signal;
        return new Promise((resolve) => {
          options.signal.addEventListener('abort', () => {
            const err = new Error('The operation was aborted');
            err.name = 'AbortError';
            resolve(Promise.reject(err));
          });
        });
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const requestPromise = gateway.request({
        method: 'GET',
        path: '/architecture-versions/ver-1/graph/window',
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'developer',
        projectId: sampleProjectId,
        responseMode: 'graph',
        clientReq,
      });

      // Emit client disconnect
      clientReq.emit('close');

      await expect(requestPromise).rejects.toThrow(AnalysisServiceTimeoutError);
      expect(capturedSignal.aborted).toBe(true);
    });
  });
});

