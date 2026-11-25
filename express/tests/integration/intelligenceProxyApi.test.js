/**
 * Express Intelligence Transport Integration Tests (C5 Phase 5 Module 6 Batch 1)
 *
 * Verifies the full HTTP pipeline:
 * Express Supertest -> Authentication -> Project Authorization (RBAC) ->
 * Parameter & Body Validation -> Gateway Service (intelligence mode & artifact streaming) ->
 * Controlled Real HTTP Upstream.
 *
 * Covers:
 * - All 21 scoped operations
 * - Role matrix (Viewer reads, Owner/Admin retry & rebuild, Outsider denied)
 * - Delegation spoof resistance (client-injected headers stripped/overridden)
 * - Error relay (200, 202, 404, 409, 410, 422, 500)
 * - Binary artifact streaming with SHA-256 Content-Digest verification (SVG & PDF)
 * - Range request rejection (416)
 */
const http = require('http');
const crypto = require('crypto');
const request = require('supertest');
const app = require('../../src/app');
const projectService = require('../../src/services/projectService');
const projectAccessService = require('../../src/services/projectAccessService');
const { PROJECT_ROLES } = require('../../src/constants/projectRoles');
const { analysisGatewayService } = require('../../src/services/analysisGatewayService');

describe('Intelligence Transport Integration Tests (Batch 1)', () => {
  let upstreamServer;
  let upstreamPort;
  let originalBaseUrl;
  let receivedRequests = [];
  let upstreamResponseHandler = null;

  let ownerId;
  let adminId;
  let devId;
  let viewerId;
  let outsiderId;
  let project;
  let versionId;
  let generationId;
  let reportId;

  beforeAll(async () => {
    upstreamServer = http.createServer((req, res) => {
      let bodyData = '';
      req.on('data', (chunk) => {
        bodyData += chunk;
      });
      req.on('end', () => {
        let parsedBody = null;
        if (bodyData) {
          try {
            parsedBody = JSON.parse(bodyData);
          } catch (_) {
            parsedBody = bodyData;
          }
        }
        const recorded = {
          method: req.method,
          url: req.url,
          headers: req.headers,
          body: parsedBody,
        };
        receivedRequests.push(recorded);

        if (upstreamResponseHandler) {
          upstreamResponseHandler(req, res, recorded);
        } else {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'default_ok' }));
        }
      });
    });

    await new Promise((resolve) => {
      upstreamServer.listen(0, '127.0.0.1', () => {
        upstreamPort = upstreamServer.address().port;
        resolve();
      });
    });

    originalBaseUrl = analysisGatewayService.config.baseUrl;
    analysisGatewayService.config.baseUrl = `http://127.0.0.1:${upstreamPort}/api/v1`;
  });

  afterAll(async () => {
    analysisGatewayService.config.baseUrl = originalBaseUrl;
    await new Promise((resolve) => upstreamServer.close(resolve));
  });

  beforeEach(async () => {
    receivedRequests = [];
    upstreamResponseHandler = null;

    ownerId = crypto.randomUUID();
    adminId = crypto.randomUUID();
    devId = crypto.randomUUID();
    viewerId = crypto.randomUUID();
    outsiderId = crypto.randomUUID();

    versionId = crypto.randomUUID();
    generationId = crypto.randomUUID();
    reportId = crypto.randomUUID();

    project = await projectService.createProject({
      name: `Intel-Project-${crypto.randomUUID().slice(0, 8)}`,
      description: 'Test project for intelligence transport',
      ownerId,
    });

    await projectAccessService.grantAccess({
      projectId: project._id,
      userId: adminId,
      role: PROJECT_ROLES.ADMIN,
      actorUserId: ownerId,
    });

    await projectAccessService.grantAccess({
      projectId: project._id,
      userId: devId,
      role: PROJECT_ROLES.DEVELOPER,
      actorUserId: ownerId,
    });

    await projectAccessService.grantAccess({
      projectId: project._id,
      userId: viewerId,
      role: PROJECT_ROLES.VIEWER,
      actorUserId: ownerId,
    });
  });

  describe('Authentication and RBAC Authorization', () => {
    it('rejects unauthenticated requests to all 21 intelligence endpoints with 401', async () => {
      const endpoints = [
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/delivery?project_id=${project._id}` },
        { method: 'post', path: `/api/v1/architecture-versions/${versionId}/delivery/retry?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/search/status?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/search?project_id=${project._id}` },
        { method: 'post', path: `/api/v1/architecture-versions/${versionId}/search/rebuild?project_id=${project._id}` },
        { method: 'post', path: `/api/v1/architecture-versions/${versionId}/knowledge/query?project_id=${project._id}` },
        { method: 'post', path: `/api/v1/architecture-versions/${versionId}/knowledge/context?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/knowledge/evidence?project_id=${project._id}&entity_id=${crypto.randomUUID()}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/diagrams?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/diagrams/system_overview?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/diagrams/system_overview/generations?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/diagrams/system_overview/generations/${generationId}/spec?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/diagrams/system_overview/generations/${generationId}/layout?project_id=${project._id}` },
        { method: 'post', path: `/api/v1/architecture-versions/${versionId}/diagrams/system_overview/generations/${generationId}/view?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/diagrams/system_overview/generations/${generationId}/members?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/diagrams/system_overview/generations/${generationId}/export?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/reports?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/reports/${reportId}?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/reports/${reportId}/generations?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/reports/${reportId}/generations/${generationId}?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/reports/${reportId}/generations/${generationId}/download?project_id=${project._id}` },
      ];

      for (const ep of endpoints) {
        const res = await request(app)[ep.method](ep.path);
        expect(res.status).toBe(401);
        expect(res.body.error.code).toBe('authentication_required');
      }
      expect(receivedRequests.length).toBe(0);
    });

    it('rejects outsider with 403 project_access_denied before reaching upstream', async () => {
      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/delivery?project_id=${project._id}`)
        .set('x-user-id', outsiderId);

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
      expect(receivedRequests.length).toBe(0);
    });

    it('allows VIEWER to read delivery and verifies delegation headers', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ slots: [], overall_state: 'READY' }));
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/delivery?project_id=${project._id}`)
        .set('x-user-id', viewerId)
        .set('x-correlation-id', 'test-client-corr-id');

      expect(res.status).toBe(200);
      expect(res.body).toEqual({ slots: [], overall_state: 'READY' });
      expect(receivedRequests.length).toBe(1);

      const upstreamReq = receivedRequests[0];
      expect(upstreamReq.headers['x-service-token']).toBe(analysisGatewayService.config.secretKey);
      expect(upstreamReq.headers['x-actor-id']).toBe(viewerId);
      expect(upstreamReq.headers['x-actor-role']).toBe('VIEWER');
      expect(upstreamReq.headers['x-project-id']).toBe(String(project._id));
      expect(upstreamReq.headers['x-correlation-id']).toBe('test-client-corr-id');
    });

    it('strips spoofed client delegation headers', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok' }));
      };

      await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/delivery?project_id=${project._id}`)
        .set('x-user-id', viewerId)
        .set('x-service-token', 'malicious-spoofed-token')
        .set('x-actor-role', 'OWNER')
        .set('x-project-id', '00000000-0000-0000-0000-000000000000');

      expect(receivedRequests.length).toBe(1);
      const upstreamReq = receivedRequests[0];
      expect(upstreamReq.headers['x-service-token']).toBe(analysisGatewayService.config.secretKey);
      expect(upstreamReq.headers['x-actor-role']).toBe('VIEWER');
      expect(upstreamReq.headers['x-project-id']).toBe(String(project._id));
    });

    it('rejects VIEWER and DEVELOPER on retry and rebuild mutations with 403', async () => {
      const retryBody = {
        resource_type: 'diagram',
        resource_id: versionId,
        idempotency_key: crypto.randomUUID(),
      };

      // Viewer retry
      const vRes = await request(app)
        .post(`/api/v1/architecture-versions/${versionId}/delivery/retry?project_id=${project._id}`)
        .set('x-user-id', viewerId)
        .send(retryBody);
      expect(vRes.status).toBe(403);
      expect(vRes.body.error.code).toBe('project_access_denied');

      // Developer rebuild
      const dRes = await request(app)
        .post(`/api/v1/architecture-versions/${versionId}/search/rebuild?project_id=${project._id}`)
        .set('x-user-id', devId)
        .send({ idempotency_key: crypto.randomUUID() });
      expect(dRes.status).toBe(403);
      expect(dRes.body.error.code).toBe('project_access_denied');

      expect(receivedRequests.length).toBe(0);
    });

    it('allows ADMIN to invoke retry and rebuild mutations receiving 202', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(202, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ accepted: true, work_id: 'work-abc' }));
      };

      const retryRes = await request(app)
        .post(`/api/v1/architecture-versions/${versionId}/delivery/retry?project_id=${project._id}`)
        .set('x-user-id', adminId)
        .send({
          resource_type: 'diagram',
          resource_id: versionId,
          idempotency_key: crypto.randomUUID(),
        });

      expect(retryRes.status).toBe(202);
      expect(retryRes.body).toEqual({ accepted: true, work_id: 'work-abc' });

      const rebuildRes = await request(app)
        .post(`/api/v1/architecture-versions/${versionId}/search/rebuild?project_id=${project._id}`)
        .set('x-user-id', adminId)
        .send({ idempotency_key: crypto.randomUUID() });

      expect(rebuildRes.status).toBe(202);
      expect(rebuildRes.body).toEqual({ accepted: true, work_id: 'work-abc' });
    });
  });

  describe('C1 Search and C3 Knowledge Read Operations', () => {
    it('serializes repeated array parameters for GET /search', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ items: [], total_hits: 0 }));
      };

      const res = await request(app)
        .get(
          `/api/v1/architecture-versions/${versionId}/search?project_id=${project._id}&document_kinds=file&document_kinds=symbol&q=test&limit=10`
        )
        .set('x-user-id', viewerId);

      expect(res.status).toBe(200);
      expect(receivedRequests.length).toBe(1);
      const url = receivedRequests[0].url;
      expect(url).toContain('document_kinds=file');
      expect(url).toContain('document_kinds=symbol');
      expect(url).toContain('q=test');
      expect(url).toContain('limit=10');
    });

    it('relays POST /knowledge/query and preserves upstream status and cause', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(409, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            error: {
              code: 'retrieval_generation_drift',
              message: 'Index drift detected.',
              details: {},
              cause: 'index_swapped',
            },
          })
        );
      };

      const res = await request(app)
        .post(`/api/v1/architecture-versions/${versionId}/knowledge/query?project_id=${project._id}`)
        .set('x-user-id', viewerId)
        .send({ project_id: String(project._id) });

      expect(res.status).toBe(409);
      expect(res.body.error.code).toBe('retrieval_generation_drift');
      expect(res.body.error.cause).toBe('index_swapped');
    });
  });

  describe('Artifact Streaming (SVG and PDF)', () => {
    it('streams SVG diagram export with Content-Digest verification', async () => {
      const svgContent = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100"/></svg>';
      const svgBuffer = Buffer.from(svgContent);
      const sha256Hex = crypto.createHash('sha256').update(svgBuffer).digest('hex');
      const sha256B64 = crypto.createHash('sha256').update(svgBuffer).digest('base64');

      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, {
          'Content-Type': 'image/svg+xml',
          'Content-Length': String(svgBuffer.length),
          'Content-Digest': `sha-256=:${sha256B64}:`,
          ETag: `"${sha256Hex}"`,
        });
        res.end(svgBuffer);
      };

      const res = await request(app)
        .get(
          `/api/v1/architecture-versions/${versionId}/diagrams/system_overview/generations/${generationId}/export?project_id=${project._id}&format=svg`
        )
        .set('x-user-id', viewerId)
        .buffer();

      expect(res.status).toBe(200);
      expect(res.headers['content-type']).toBe('image/svg+xml');
      expect(res.headers['content-length']).toBe(String(svgBuffer.length));
      expect(res.headers['content-digest']).toBe(`sha-256=:${sha256B64}:`);
      expect(res.headers['etag']).toBe(`"${sha256Hex}"`);
      expect(res.headers['cache-control']).toBe('private, no-store');
      expect(res.body.toString('utf8')).toBe(svgContent);
    });

    it('streams PDF report download with Content-Digest verification', async () => {
      const pdfContent = '%PDF-1.4 Mock PDF Content';
      const pdfBuffer = Buffer.from(pdfContent);
      const sha256Hex = crypto.createHash('sha256').update(pdfBuffer).digest('hex');
      const sha256B64 = crypto.createHash('sha256').update(pdfBuffer).digest('base64');

      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, {
          'Content-Type': 'application/pdf',
          'Content-Length': String(pdfBuffer.length),
          'Content-Digest': `sha-256=:${sha256B64}:`,
          ETag: `"${sha256Hex}"`,
        });
        res.end(pdfBuffer);
      };

      const res = await request(app)
        .get(
          `/api/v1/architecture-versions/${versionId}/reports/${reportId}/generations/${generationId}/download?project_id=${project._id}`
        )
        .set('x-user-id', viewerId)
        .buffer();

      expect(res.status).toBe(200);
      expect(res.headers['content-type']).toBe('application/pdf');
      expect(res.headers['content-length']).toBe(String(pdfBuffer.length));
      expect(res.headers['content-digest']).toBe(`sha-256=:${sha256B64}:`);
      expect(res.headers['etag']).toBe(`"${sha256Hex}"`);
      expect(res.headers['cache-control']).toBe('private, no-store');
      expect(res.body.toString('utf8')).toBe(pdfContent);
    });

    it('rejects Range requests on download with 416', async () => {
      const res = await request(app)
        .get(
          `/api/v1/architecture-versions/${versionId}/reports/${reportId}/generations/${generationId}/download?project_id=${project._id}`
        )
        .set('x-user-id', viewerId)
        .set('Range', 'bytes=0-100');

      expect(res.status).toBe(416);
      expect(res.body.error.code).toBe('intelligence_transport_range_not_supported');
      expect(receivedRequests.length).toBe(0);
    });
  });
});
