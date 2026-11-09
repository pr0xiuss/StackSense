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
    baseUrl: 'http://localhost:8000',
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
        `http://localhost:8000/analyses?project_id=${sampleProjectId}&limit=10`,
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
});

