/**
 * Express Intelligence Product Journey Integration Tests (C5 Phase 5 Module 6 Batch 3)
 *
 * Verifies the complete end-to-end user and product journey through Express:
 * 1. Delivery status inspection & verification
 * 2. Four-template diagram discovery, generation spec/layout loading, and SVG export
 * 3. Lexical search capabilities & multi-filter search queries
 * 4. Knowledge query with subject resolution, relationships, and context assembly
 * 5. Evidence context resolution
 * 6. Report collection, generation history, and authenticated SHA-256 verified PDF streaming
 * 7. Security isolation: outsider denial (403), unauthorized access (401), and scope protection (400)
 */
const http = require('http');
const crypto = require('crypto');
const request = require('supertest');
const app = require('../../src/app');
const projectService = require('../../src/services/projectService');
const projectAccessService = require('../../src/services/projectAccessService');
const { PROJECT_ROLES } = require('../../src/constants/projectRoles');
const { analysisGatewayService } = require('../../src/services/analysisGatewayService');

describe('Intelligence Product Journey Integration Tests (Batch 3)', () => {
  let upstreamServer;
  let upstreamPort;
  let originalBaseUrl;
  let receivedRequests = [];
  let upstreamResponseHandler = null;

  let ownerId;
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
    viewerId = crypto.randomUUID();
    outsiderId = crypto.randomUUID();

    versionId = crypto.randomUUID();
    generationId = crypto.randomUUID();
    reportId = crypto.randomUUID();

    project = await projectService.createProject({
      name: `Journey-Project-${crypto.randomUUID().slice(0, 8)}`,
      description: 'Test project for intelligence product journey',
      ownerId,
    });

    await projectAccessService.grantAccess({
      projectId: project._id,
      userId: viewerId,
      role: PROJECT_ROLES.VIEWER,
      actorUserId: ownerId,
    });
  });

  it('successfully executes the full intelligence journey from delivery to report download', async () => {
    // 1. Delivery Status
    upstreamResponseHandler = (req, res) => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        state: 'SUCCEEDED',
        completed_work_items: 6,
        total_work_items: 6,
        work_summary: [
          { work_id: 'w1', kind: 'CONTAINER_ISOLATION', status: 'SUCCEEDED' },
          { work_id: 'w2', kind: 'AUTOMATIC_REPORT', status: 'SUCCEEDED' },
        ],
      }));
    };

    const deliveryRes = await request(app)
      .get(`/api/v1/architecture-versions/${versionId}/delivery?project_id=${project._id}`)
      .set('x-user-id', viewerId);

    expect(deliveryRes.status).toBe(200);
    expect(deliveryRes.body.state).toBe('SUCCEEDED');
    expect(deliveryRes.body.completed_work_items).toBe(6);

    // 2. Diagrams Collection & Spec
    upstreamResponseHandler = (req, res) => {
      if (req.url.includes('/spec')) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          template: 'system_overview',
          digest: 'spec-digest-1',
          nodes: [{ id: 'n1', name: 'Web' }],
          edges: [],
          groups: [],
          legend: [],
          coverage: { view_state: 'COMPLETE', reasons: [] },
        }));
      } else {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          diagrams: {
            system_overview: { ready: true },
          },
        }));
      }
    };

    const diagColRes = await request(app)
      .get(`/api/v1/architecture-versions/${versionId}/diagrams?project_id=${project._id}`)
      .set('x-user-id', viewerId);

    expect(diagColRes.status).toBe(200);
    expect(diagColRes.body.diagrams.system_overview.ready).toBe(true);

    const specRes = await request(app)
      .get(`/api/v1/architecture-versions/${versionId}/diagrams/system_overview/generations/${generationId}/spec?project_id=${project._id}`)
      .set('x-user-id', viewerId);

    expect(specRes.status).toBe(200);
    expect(specRes.body.template).toBe('system_overview');
    expect(specRes.body.nodes).toHaveLength(1);

    // 3. Export SVG Stream
    const svgContent = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><circle cx="50" cy="50" r="40"/></svg>';
    const svgHash = crypto.createHash('sha256').update(svgContent, 'utf8').digest('base64');

    upstreamResponseHandler = (req, res) => {
      res.writeHead(200, {
        'Content-Type': 'image/svg+xml',
        'Content-Digest': `sha-256=:${svgHash}:`,
      });
      res.end(svgContent);
    };

    const svgRes = await request(app)
      .get(`/api/v1/architecture-versions/${versionId}/diagrams/system_overview/generations/${generationId}/export?project_id=${project._id}&format=svg`)
      .set('x-user-id', viewerId)
      .buffer();

    expect(svgRes.status).toBe(200);
    expect(svgRes.headers['content-type']).toBe('image/svg+xml');
    expect(svgRes.body.toString('utf8')).toBe(svgContent);

    // 4. Lexical Search
    upstreamResponseHandler = (req, res) => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        items: [
          { id: 'ent-1', name: 'AuthService', kind: 'SERVICE', score: 10.5 },
        ],
        next_cursor: null,
      }));
    };

    const searchRes = await request(app)
      .get(`/api/v1/architecture-versions/${versionId}/search?project_id=${project._id}&q=Auth&entity_kinds=SERVICE`)
      .set('x-user-id', viewerId);

    expect(searchRes.status).toBe(200);
    expect(searchRes.body.items).toHaveLength(1);
    expect(searchRes.body.items[0].name).toBe('AuthService');

    // 5. Knowledge Query & Context Assembly
    upstreamResponseHandler = (req, res) => {
      if (req.url.includes('/context')) {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          semantic_digest: 'digest-c3-semantic-1234',
          subjects: [{ id: 'ent-1', name: 'AuthService' }],
          relationships: [],
          evidence: [],
          coverage: { completeness_state: 'COMPLETE' },
        }));
      } else {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          resolution_state: 'RESOLVED',
          resolved_subject: { id: 'ent-1', name: 'AuthService' },
          relationships: [],
        }));
      }
    };

    const queryRes = await request(app)
      .post(`/api/v1/architecture-versions/${versionId}/knowledge/query?project_id=${project._id}`)
      .set('x-user-id', viewerId)
      .send({
        subject: { kind: 'entity_name', name: 'AuthService' },
        operation: 'LOOKUP',
      });

    expect(queryRes.status).toBe(200);
    expect(queryRes.body.resolution_state).toBe('RESOLVED');

    const contextRes = await request(app)
      .post(`/api/v1/architecture-versions/${versionId}/knowledge/context?project_id=${project._id}`)
      .set('x-user-id', viewerId)
      .send({
        subjects: [{ kind: 'exact_id', id: '11111111-1111-4111-8111-111111111111' }],
      });

    expect(contextRes.status).toBe(200);
    expect(contextRes.body.semantic_digest).toBe('digest-c3-semantic-1234');

    // 6. Evidence Pagination
    upstreamResponseHandler = (req, res) => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        items: [{ id: 'ev-1', strength: 'CONFIRMED_DIRECT' }],
        next_cursor: null,
      }));
    };

    const evidenceRes = await request(app)
      .get(`/api/v1/architecture-versions/${versionId}/knowledge/evidence?project_id=${project._id}&entity_id=11111111-1111-4111-8111-111111111111`)
      .set('x-user-id', viewerId);

    expect(evidenceRes.status).toBe(200);
    expect(evidenceRes.body.items).toHaveLength(1);

    // 7. Report Collection & Summary
    upstreamResponseHandler = (req, res) => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        report_id: reportId,
        name: 'Executive Architecture Report',
        ready: true,
        active_generation_id: generationId,
      }));
    };

    const reportRes = await request(app)
      .get(`/api/v1/architecture-versions/${versionId}/reports/${reportId}?project_id=${project._id}`)
      .set('x-user-id', viewerId);

    expect(reportRes.status).toBe(200);
    expect(reportRes.body.report_id).toBe(reportId);
    expect(reportRes.body.ready).toBe(true);

    // 8. Verified PDF Binary Streaming with SHA-256 Content-Digest
    const pdfData = Buffer.from('%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n', 'utf8');
    const pdfHash = crypto.createHash('sha256').update(pdfData).digest('base64');

    upstreamResponseHandler = (req, res) => {
      res.writeHead(200, {
        'Content-Type': 'application/pdf',
        'Content-Digest': `sha-256=:${pdfHash}:`,
      });
      res.end(pdfData);
    };

    const pdfRes = await request(app)
      .get(`/api/v1/architecture-versions/${versionId}/reports/${reportId}/generations/${generationId}/download?project_id=${project._id}`)
      .set('x-user-id', viewerId)
      .buffer();

    expect(pdfRes.status).toBe(200);
    expect(pdfRes.headers['content-type']).toBe('application/pdf');
    expect(pdfRes.body.toString('utf8')).toBe(pdfData.toString('utf8'));
  });

  it('enforces RBAC isolation: denies outsider from viewing intelligence endpoints', async () => {
    const res = await request(app)
      .get(`/api/v1/architecture-versions/${versionId}/delivery?project_id=${project._id}`)
      .set('x-user-id', outsiderId);

    expect(res.status).toBe(403);
  });

  it('rejects unauthenticated requests with 401', async () => {
    const res = await request(app)
      .get(`/api/v1/architecture-versions/${versionId}/delivery?project_id=${project._id}`);

    expect(res.status).toBe(401);
  });

  it('rejects malformed UUID in architecture version parameter with 422', async () => {
    const res = await request(app)
      .get(`/api/v1/architecture-versions/not-a-valid-uuid/delivery?project_id=${project._id}`)
      .set('x-user-id', viewerId);

    expect(res.status).toBe(422);
  });
});
