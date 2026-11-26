const crypto = require('crypto');
const fs = require('fs');
const { Readable } = require('stream');
const { AnalysisGatewayService } = require('../../src/services/analysisGatewayService');
const {
  AnalysisGatewayError,
} = require('../../src/errors/analysisErrors');

describe('AnalysisGatewayService Intelligence Mode & streamArtifact Unit Tests', () => {
  const mockConfig = {
    baseUrl: 'http://localhost:8000/api/v1',
    secretKey: 'mock-secret-key-at-least-16-chars',
    jsonTimeoutMs: 2000,
    sseTimeoutMs: 5000,
    intelligenceQueryMaxBytes: 32768,
    intelligenceMaxFilterElements: 50,
    intelligenceJsonRequestMaxBytes: 131072,
    intelligenceJsonResponseMaxBytes: 4194304,
    intelligenceC3ResponseMaxBytes: 2097152,
    intelligenceDiagramSpecMaxBytes: 16777216,
    intelligenceDiagramLayoutMaxBytes: 33554432,
    intelligenceDiagramExportMaxBytes: 67108864,
    intelligenceDiagramSvgMaxBytes: 50331648,
    intelligencePdfMaxBytes: 67108864,
    intelligenceMetadataTimeoutMs: 30000,
    intelligenceLongTimeoutMs: 120000,
    intelligenceArtifactUpstreamTimeoutMs: 90000,
    intelligenceArtifactRelayTimeoutMs: 60000,
    intelligenceArtifactCombinedTimeoutMs: 150000,
    intelligenceMaxConcurrentArtifactRelays: 2,
    intelligenceArtifactSpoolDir: '/tmp/stacksense-test-intelligence-spool',
  };

  const sampleUser = { id: '11111111-1111-4111-8111-111111111111', email: 'test@example.com' };
  const sampleProjectId = '22222222-2222-4222-8222-222222222222';
  const sampleVersionId = '33333333-3333-4333-8333-333333333333';

  describe('request() in intelligence responseMode', () => {
    it('returns status and parsed JSON on 200 OK', async () => {
      const mockData = { items: [{ id: 'item-1' }], total: 1 };
      const mockFetch = vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockData,
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'GET',
        path: `/architecture-versions/${sampleVersionId}/delivery`,
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'VIEWER',
        projectId: sampleProjectId,
        responseMode: 'intelligence',
      });

      expect(result).toEqual({ status: 200, body: mockData });
    });

    it('returns status 202 for retry or rebuild mutations', async () => {
      const mockData = { accepted: true, work_id: 'work-123' };
      const mockFetch = vi.fn().mockResolvedValue({
        status: 202,
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockData,
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'POST',
        path: `/architecture-versions/${sampleVersionId}/delivery/retry`,
        query: { project_id: sampleProjectId },
        body: { resource_type: 'diagram', resource_id: sampleVersionId, idempotency_key: sampleVersionId },
        user: sampleUser,
        role: 'ADMIN',
        projectId: sampleProjectId,
        responseMode: 'intelligence',
      });

      expect(result).toEqual({ status: 202, body: mockData });
    });

    it('returns status 204 with body null', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        status: 204,
        ok: true,
        headers: new Map(),
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'GET',
        path: `/architecture-versions/${sampleVersionId}/delivery`,
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'VIEWER',
        projectId: sampleProjectId,
        responseMode: 'intelligence',
      });

      expect(result).toEqual({ status: 204, body: null });
    });

    it('preserves recognized 4xx error with cause', async () => {
      const errorPayload = {
        error: {
          code: 'retrieval_generation_drift',
          message: 'Active search index changed.',
          details: { drift: true },
          cause: 'index_swapped',
        },
      };
      const mockFetch = vi.fn().mockResolvedValue({
        status: 409,
        ok: false,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => errorPayload,
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'POST',
        path: `/architecture-versions/${sampleVersionId}/knowledge/query`,
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'VIEWER',
        projectId: sampleProjectId,
        responseMode: 'intelligence',
      });

      expect(result.status).toBe(409);
      expect(result.body.error.code).toBe('retrieval_generation_drift');
      expect(result.body.error.cause).toBe('index_swapped');
    });

    it('sanitizes FastAPI 422 detail array', async () => {
      const detailPayload = {
        detail: [
          { loc: ['body', 'q'], msg: 'field required', type: 'value_error.missing', input: 'secret_leak' },
        ],
      };
      const mockFetch = vi.fn().mockResolvedValue({
        status: 422,
        ok: false,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => detailPayload,
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const result = await gateway.request({
        method: 'POST',
        path: `/architecture-versions/${sampleVersionId}/knowledge/query`,
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'VIEWER',
        projectId: sampleProjectId,
        responseMode: 'intelligence',
      });

      expect(result.status).toBe(422);
      expect(result.body.detail[0]).toEqual({
        loc: ['body', 'q'],
        msg: 'field required',
        type: 'value_error.missing',
      });
      expect(result.body.detail[0].input).toBeUndefined();
    });

    it('rejects redirects with 502 intelligence_upstream_invalid', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        status: 302,
        ok: false,
        headers: new Map([['location', 'http://other.internal/leak']]),
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      await expect(
        gateway.request({
          method: 'GET',
          path: `/architecture-versions/${sampleVersionId}/delivery`,
          query: { project_id: sampleProjectId },
          user: sampleUser,
          role: 'VIEWER',
          projectId: sampleProjectId,
          responseMode: 'intelligence',
        })
      ).rejects.toThrow(
        expect.objectContaining({
          code: 'intelligence_upstream_invalid',
          status: 502,
        })
      );
    });

    it('enforces streaming body byte cap and throws 502 when exceeded', async () => {
      const largeChunk = new Uint8Array(2000);
      let readCount = 0;
      const mockStream = {
        getReader: () => ({
          read: async () => {
            readCount++;
            if (readCount > 5) return { done: true, value: undefined };
            return { done: false, value: largeChunk };
          },
          cancel: vi.fn(),
        }),
      };

      const mockFetch = vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        headers: new Map([['content-type', 'application/json']]),
        body: mockStream,
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      await expect(
        gateway.request({
          method: 'GET',
          path: `/architecture-versions/${sampleVersionId}/knowledge/context`,
          query: { project_id: sampleProjectId },
          user: sampleUser,
          role: 'VIEWER',
          projectId: sampleProjectId,
          responseMode: 'intelligence',
          maxBytes: 5000,
        })
      ).rejects.toThrow(
        expect.objectContaining({
          code: 'intelligence_upstream_invalid',
          status: 502,
        })
      );
    });
  });

  describe('streamArtifact()', () => {
    function mockClientRes() {
      const res = {
        statusCode: 200,
        headersSent: false,
        writableFinished: false,
        headers: {},
        status: vi.fn(function (code) {
          this.statusCode = code;
          return this;
        }),
        json: vi.fn(function (data) {
          this.body = data;
          this.writableFinished = true;
          return this;
        }),
        writeHead: vi.fn(function (code, headers) {
          this.statusCode = code;
          this.headers = headers;
          this.headersSent = true;
        }),
        write: vi.fn(),
        end: vi.fn(function () {
          this.writableFinished = true;
        }),
        on: vi.fn(),
        off: vi.fn(),
        destroy: vi.fn(),
      };
      return res;
    }

    it('rejects Range requests with 416', async () => {
      const gateway = new AnalysisGatewayService(mockConfig);
      const clientReq = { headers: { range: 'bytes=0-1024' }, on: vi.fn(), off: vi.fn() };
      const clientRes = mockClientRes();

      await gateway.streamArtifact({
        path: `/architecture-versions/${sampleVersionId}/reports/rep-1/generations/gen-1/download`,
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'VIEWER',
        projectId: sampleProjectId,
        clientReq,
        clientRes,
        expectedMediaType: 'application/pdf',
      });

      expect(clientRes.status).toHaveBeenCalledWith(416);
      expect(clientRes.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({ code: 'intelligence_transport_range_not_supported' }),
        })
      );
    });

    it('rejects when active relays exceed admission limit with 503 intelligence_transport_busy', async () => {
      const gateway = new AnalysisGatewayService(mockConfig);
      gateway.activeArtifactRelays = 2; // already at limit
      const clientReq = { headers: {}, on: vi.fn(), off: vi.fn() };
      const clientRes = mockClientRes();

      await gateway.streamArtifact({
        path: `/architecture-versions/${sampleVersionId}/reports/rep-1/generations/gen-1/download`,
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'VIEWER',
        projectId: sampleProjectId,
        clientReq,
        clientRes,
        expectedMediaType: 'application/pdf',
      });

      expect(clientRes.status).toHaveBeenCalledWith(503);
      expect(clientRes.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({ code: 'intelligence_transport_busy' }),
        })
      );
    });

    it('successfully streams artifact when Content-Digest matches SHA-256', async () => {
      const pdfBytes = Buffer.from('%PDF-1.4 Mock PDF Content For Tests');
      const sha256Hex = crypto.createHash('sha256').update(pdfBytes).digest('hex');
      const sha256B64 = crypto.createHash('sha256').update(pdfBytes).digest('base64');

      const mockFetch = vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        headers: new Map([
          ['content-type', 'application/pdf'],
          ['content-length', String(pdfBytes.length)],
          ['content-digest', `sha-256=:${sha256B64}:`],
          ['etag', `"${sha256Hex}"`],
        ]),
        body: Readable.from([pdfBytes]),
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const clientReq = { headers: {}, on: vi.fn(), off: vi.fn() };
      const clientRes = mockClientRes();

      await gateway.streamArtifact({
        path: `/architecture-versions/${sampleVersionId}/reports/rep-1/generations/gen-1/download`,
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'VIEWER',
        projectId: sampleProjectId,
        clientReq,
        clientRes,
        expectedMediaType: 'application/pdf',
        attachmentFilename: 'test-report.pdf',
      });

      expect(clientRes.writeHead).toHaveBeenCalledWith(
        200,
        expect.objectContaining({
          'Content-Type': 'application/pdf',
          'Content-Length': String(pdfBytes.length),
          'Content-Digest': `sha-256=:${sha256B64}:`,
          ETag: `"${sha256Hex}"`,
          'Cache-Control': 'private, no-store',
          'X-Content-Type-Options': 'nosniff',
          'Content-Disposition': 'attachment; filename="test-report.pdf"',
        })
      );
    });

    it('rejects with 502 when Content-Digest mismatches computed hash', async () => {
      const pdfBytes = Buffer.from('%PDF-1.4 Mock PDF Content');
      const wrongB64 = crypto.createHash('sha256').update('wrong').digest('base64');

      const mockFetch = vi.fn().mockResolvedValue({
        status: 200,
        ok: true,
        headers: new Map([
          ['content-type', 'application/pdf'],
          ['content-length', String(pdfBytes.length)],
          ['content-digest', `sha-256=:${wrongB64}:`],
        ]),
        body: Readable.from([pdfBytes]),
      });

      const gateway = new AnalysisGatewayService(mockConfig, mockFetch);
      const clientReq = { headers: {}, on: vi.fn(), off: vi.fn() };
      const clientRes = mockClientRes();

      await gateway.streamArtifact({
        path: `/architecture-versions/${sampleVersionId}/reports/rep-1/generations/gen-1/download`,
        query: { project_id: sampleProjectId },
        user: sampleUser,
        role: 'VIEWER',
        projectId: sampleProjectId,
        clientReq,
        clientRes,
        expectedMediaType: 'application/pdf',
      });

      expect(clientRes.status).toHaveBeenCalledWith(502);
      expect(clientRes.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({
            code: 'intelligence_upstream_invalid',
            message: 'Artifact Content-Digest mismatch.',
          }),
        })
      );
    });

    it('rejects missing digest rather than generating a trusted digest', async () => {
      const pdfBytes = Buffer.from('%PDF-1.4 example');
      const gateway = new AnalysisGatewayService(mockConfig, vi.fn().mockResolvedValue({
        status: 200, ok: true,
        headers: new Map([['content-type', 'application/pdf'], ['content-length', String(pdfBytes.length)]]),
        body: Readable.from([pdfBytes]),
      }));
      const clientRes = mockClientRes();
      await gateway.streamArtifact({
        path: '/reports/example', user: sampleUser, role: 'VIEWER',
        projectId: sampleProjectId, clientRes, expectedMediaType: 'application/pdf',
      });
      expect(clientRes.status).toHaveBeenCalledWith(502);
      expect(clientRes.writeHead).not.toHaveBeenCalled();
    });

    it('stops a stalled downstream at the relay deadline and releases admission', async () => {
      const { Writable } = require('stream');
      const pdfBytes = Buffer.from('%PDF-1.4 example');
      const digest = crypto.createHash('sha256').update(pdfBytes).digest('base64');
      const gateway = new AnalysisGatewayService(mockConfig, vi.fn().mockResolvedValue({
        status: 200, ok: true,
        headers: new Map([['content-type', 'application/pdf'], ['content-length', String(pdfBytes.length)], ['content-digest', `sha-256=:${digest}:`]]),
        body: Readable.from([pdfBytes]),
      }));
      const response = new Writable({ write(_chunk, _encoding, _callback) {} });
      response.writeHead = () => {};
      await gateway.streamArtifact({
        path: '/reports/example', user: sampleUser, role: 'VIEWER', projectId: sampleProjectId,
        clientRes: response, expectedMediaType: 'application/pdf', timeoutMs: 50,
      });
      expect(response.destroyed).toBe(true);
      expect(gateway.activeArtifactRelays).toBe(0);
    });
  });
});
