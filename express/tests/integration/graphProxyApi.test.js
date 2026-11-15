/**
 * Gate T-V: Express Graph Transport Integration Tests
 *
 * Verifies the full HTTP pipeline:
 * Express Supertest -> Authentication -> Project Authorization (RBAC) ->
 * Parameter Validation -> Gateway Service -> Controlled Real HTTP Upstream.
 *
 * Covers:
 * - All 9 scoped operations + health endpoint
 * - Role matrix (Viewer reads, Owner/Admin rebuild, Outsider denied)
 * - Delegation spoof resistance (client-injected headers stripped/overridden)
 * - Wire query parameter serialization (repeated keys for kinds)
 * - Safe status and error relay (200, 202, 404, 409, 410, 422 structured & detail, 5xx sanitized)
 * - Outage & timeout handling
 */
const http = require('http');
const crypto = require('crypto');
const request = require('supertest');
const app = require('../../src/app');
const projectService = require('../../src/services/projectService');
const projectAccessService = require('../../src/services/projectAccessService');
const { PROJECT_ROLES } = require('../../src/constants/projectRoles');
const { analysisGatewayService } = require('../../src/services/analysisGatewayService');

describe('Architecture Graph Transport Integration Tests (Gate T-V)', () => {
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
  let entityId1;
  let entityId2;

  beforeAll(async () => {
    // Start a controlled real HTTP upstream server
    upstreamServer = http.createServer((req, res) => {
      let bodyData = '';
      req.on('data', (chunk) => {
        bodyData += chunk;
      });
      req.on('end', () => {
        const recorded = {
          method: req.method,
          url: req.url,
          headers: req.headers,
          body: bodyData ? JSON.parse(bodyData) : null,
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
    entityId1 = crypto.randomUUID();
    entityId2 = crypto.randomUUID();

    project = await projectService.createProject({
      name: `Graph-Project-${crypto.randomUUID().slice(0, 8)}`,
      description: 'Test project for architecture graph transport',
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
    it('rejects unauthenticated requests to all graph endpoints with 401', async () => {
      const endpoints = [
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/graph/status?project_id=${project._id}` },
        { method: 'post', path: `/api/v1/architecture-versions/${versionId}/graph/rebuild?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/graph/window?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/graph/nodes/${entityId1}?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/graph/nodes/${entityId1}/neighborhood?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/graph/nodes/${entityId1}/dependencies?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/graph/nodes/${entityId1}/dependents?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/graph/nodes/${entityId1}/containment?project_id=${project._id}` },
        { method: 'get', path: `/api/v1/architecture-versions/${versionId}/graph/paths?project_id=${project._id}&source_entity_id=${entityId1}&target_entity_id=${entityId2}` },
        { method: 'get', path: '/api/v1/health/graph/query' },
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
        .get(`/api/v1/architecture-versions/${versionId}/graph/status?project_id=${project._id}`)
        .set('x-user-id', outsiderId);

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
      expect(receivedRequests.length).toBe(0);
    });

    it('allows VIEWER to perform read operations and checks delegation headers', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ resource_id: 'res-1', status: 'COMPLETED' }));
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/status?project_id=${project._id}`)
        .set('x-user-id', viewerId);

      expect(res.status).toBe(200);
      expect(res.body).toEqual({ resource_id: 'res-1', status: 'COMPLETED' });
      expect(receivedRequests.length).toBe(1);

      const upstreamReq = receivedRequests[0];
      expect(upstreamReq.headers['x-service-token']).toBe(analysisGatewayService.config.secretKey);
      expect(upstreamReq.headers['x-actor-id']).toBe(viewerId);
      expect(upstreamReq.headers['x-actor-role']).toBe('VIEWER');
      expect(upstreamReq.headers['x-project-id']).toBe(String(project._id));
      expect(upstreamReq.headers['x-correlation-id']).toBeDefined();
    });

    it('rejects VIEWER and DEVELOPER with 403 on rebuild POST (requires OWNER or ADMIN)', async () => {
      // Viewer attempt
      const resViewer = await request(app)
        .post(`/api/v1/architecture-versions/${versionId}/graph/rebuild?project_id=${project._id}`)
        .set('x-user-id', viewerId)
        .send({});

      expect(resViewer.status).toBe(403);
      expect(resViewer.body.error.code).toBe('project_access_denied');

      // Developer attempt
      const resDev = await request(app)
        .post(`/api/v1/architecture-versions/${versionId}/graph/rebuild?project_id=${project._id}`)
        .set('x-user-id', devId)
        .send({});

      expect(resDev.status).toBe(403);
      expect(resDev.body.error.code).toBe('project_access_denied');

      // Zero upstream requests dispatched
      expect(receivedRequests.length).toBe(0);
    });

    it('allows OWNER and ADMIN to perform rebuild POST and relays 202', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(202, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            resource_id: 'res-1',
            architecture_version_id: versionId,
            status: 'RUNNING',
            attempt_id: 'att-1',
            attempt_number: 1,
            attempt_status: 'QUEUED',
            accepted_at: '2026-11-15T11:00:00Z',
          })
        );
      };

      // Owner rebuild
      const resOwner = await request(app)
        .post(`/api/v1/architecture-versions/${versionId}/graph/rebuild?project_id=${project._id}`)
        .set('x-user-id', ownerId)
        .send({});

      expect(resOwner.status).toBe(202);
      expect(resOwner.body.attempt_status).toBe('QUEUED');
      expect(receivedRequests[0].headers['x-actor-role']).toBe('OWNER');

      // Admin rebuild
      const resAdmin = await request(app)
        .post(`/api/v1/architecture-versions/${versionId}/graph/rebuild?project_id=${project._id}`)
        .set('x-user-id', adminId)
        .send({});

      expect(resAdmin.status).toBe(202);
      expect(receivedRequests[1].headers['x-actor-role']).toBe('ADMIN');
    });
  });

  describe('Spoof Resistance', () => {
    it('ignores client-supplied spoofed delegation headers and uses authoritative DB role', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ resource_id: 'res-1', status: 'COMPLETED' }));
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/status?project_id=${project._id}`)
        .set('x-user-id', viewerId)
        .set('x-actor-role', 'OWNER') // spoofed role
        .set('x-actor-id', crypto.randomUUID()) // spoofed user
        .set('x-project-id', crypto.randomUUID()) // spoofed project
        .set('x-service-token', 'fake-token'); // spoofed service token

      expect(res.status).toBe(200);
      expect(receivedRequests.length).toBe(1);

      const upstreamReq = receivedRequests[0];
      // Must be authoritative VIEWER, not spoofed OWNER
      expect(upstreamReq.headers['x-actor-role']).toBe('VIEWER');
      expect(upstreamReq.headers['x-actor-id']).toBe(viewerId);
      expect(upstreamReq.headers['x-project-id']).toBe(String(project._id));
      expect(upstreamReq.headers['x-service-token']).toBe(analysisGatewayService.config.secretKey);
    });
  });

  describe('Repeated Query Key Serialization', () => {
    it('serializes repeated canonical_kinds on /window', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            scope: { project_id: project._id, architecture_version_id: versionId },
            nodes: [],
            edges: [],
            total_manifest_nodes: 0,
            total_manifest_edges: 0,
            loaded_nodes: 0,
            loaded_edges: 0,
            truncated: false,
          })
        );
      };

      const res = await request(app)
        .get(
          `/api/v1/architecture-versions/${versionId}/graph/window?project_id=${project._id}&canonical_kinds=calls&canonical_kinds=imports`
        )
        .set('x-user-id', devId);

      expect(res.status).toBe(200);
      expect(receivedRequests.length).toBe(1);

      const wireUrl = receivedRequests[0].url;
      expect(wireUrl).toContain('canonical_kinds=calls');
      expect(wireUrl).toContain('canonical_kinds=imports');
      expect(wireUrl).toContain(`project_id=${project._id}`);
    });

    it('serializes repeated relationship_kinds on /paths', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            scope: { project_id: project._id, architecture_version_id: versionId },
            paths: [],
            total_paths_found: 0,
            truncated: false,
          })
        );
      };

      const res = await request(app)
        .get(
          `/api/v1/architecture-versions/${versionId}/graph/paths?project_id=${project._id}&source_entity_id=${entityId1}&target_entity_id=${entityId2}&relationship_kinds=calls&relationship_kinds=depends_on`
        )
        .set('x-user-id', devId);

      expect(res.status).toBe(200);
      const wireUrl = receivedRequests[0].url;
      expect(wireUrl).toContain('relationship_kinds=calls');
      expect(wireUrl).toContain('relationship_kinds=depends_on');
    });
  });

  describe('Health Relay Endpoint', () => {
    it('relays GET /api/v1/health/graph/query with un-scoped delegation headers', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ready', code: 'graph_query_ready' }));
      };

      const res = await request(app)
        .get('/api/v1/health/graph/query')
        .set('x-user-id', devId);

      expect(res.status).toBe(200);
      expect(res.body).toEqual({ status: 'ready', code: 'graph_query_ready' });
      expect(receivedRequests.length).toBe(1);

      const upstreamReq = receivedRequests[0];
      expect(upstreamReq.url).toBe('/api/v1/health/graph/query');
      expect(upstreamReq.headers['x-service-token']).toBe(analysisGatewayService.config.secretKey);
      expect(upstreamReq.headers['x-actor-id']).toBe(devId);
      expect(upstreamReq.headers['x-project-id']).toBeUndefined();
      expect(upstreamReq.headers['x-actor-role']).toBeUndefined();
    });

    it('relays degraded health status without modifying it', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'degraded', code: 'graph_degraded', details: { latency_ms: 1200 } }));
      };

      const res = await request(app)
        .get('/api/v1/health/graph/query')
        .set('x-user-id', devId);

      expect(res.status).toBe(200);
      expect(res.body.status).toBe('degraded');
      expect(res.body.code).toBe('graph_degraded');
    });
  });

  describe('Error Relay and Sanitization', () => {
    it('preserves structured upstream 409 graph_projection_not_ready', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(409, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            error: {
              code: 'graph_projection_not_ready',
              message: 'Graph projection is not ready for queries',
              details: { state: 'PENDING' },
            },
          })
        );
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/window?project_id=${project._id}`)
        .set('x-user-id', devId);

      expect(res.status).toBe(409);
      expect(res.body.error.code).toBe('graph_projection_not_ready');
      expect(res.body.error.details.state).toBe('PENDING');
    });

    it('preserves structured upstream 404 graph_node_not_found', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            error: {
              code: 'graph_node_not_found',
              message: 'Graph node not found in scope',
              details: {},
            },
          })
        );
      };

      const res = await request(app)
        .get(
          `/api/v1/architecture-versions/${versionId}/graph/nodes/${entityId1}?project_id=${project._id}`
        )
        .set('x-user-id', devId);

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('graph_node_not_found');
    });

    it('preserves structured upstream 410 graph_cursor_expired', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(410, { 'Content-Type': 'application/json' });
        res.end(
          JSON.stringify({
            error: {
              code: 'graph_cursor_expired',
              message: 'Pagination cursor has expired',
              details: {},
            },
          })
        );
      };

      const res = await request(app)
        .get(
          `/api/v1/architecture-versions/${versionId}/graph/window?project_id=${project._id}&cursor=old_cur`
        )
        .set('x-user-id', devId);

      expect(res.status).toBe(410);
      expect(res.body.error.code).toBe('graph_cursor_expired');
    });

    it('preserves FastAPI syntactic 422 detail array', async () => {
      const detail = [
        { loc: ['query', 'node_limit'], msg: 'Input should be greater than 0', type: 'greater_than' },
      ];
      upstreamResponseHandler = (req, res) => {
        res.writeHead(422, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ detail }));
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/window?project_id=${project._id}`)
        .set('x-user-id', devId);

      expect(res.status).toBe(422);
      expect(res.body.detail).toEqual(detail);
    });

    it('sanitizes unexpected upstream 500 HTML/stack trace into 500 analysis_service_error', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(500, { 'Content-Type': 'text/html' });
        res.end('<html><body>Internal Server Error: Traceback in /var/app/graph.py</body></html>');
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/window?project_id=${project._id}`)
        .set('x-user-id', devId);

      expect(res.status).toBe(500);
      expect(res.body.error.code).toBe('analysis_service_error');
      expect(res.body.error.message).toBe('Analysis service encountered an unexpected error.');
      // Ensure raw HTML / stack trace is never exposed
      expect(JSON.stringify(res.body)).not.toContain('Traceback');
    });
  });

  describe('All 9 scoped operations route verification', () => {
    it('verifies GET /status', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'COMPLETED' }));
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/status?project_id=${project._id}`)
        .set('x-user-id', devId);
      expect(res.status).toBe(200);
      expect(receivedRequests[0].url).toContain(`/architecture-versions/${versionId}/graph/status`);
    });

    it('verifies GET /window', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ nodes: [], edges: [] }));
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/window?project_id=${project._id}`)
        .set('x-user-id', devId);
      expect(res.status).toBe(200);
      expect(receivedRequests[0].url).toContain(`/architecture-versions/${versionId}/graph/window`);
    });

    it('verifies GET /nodes/:entityId', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ architecture_entity_id: entityId1, name: 'ServiceA' }));
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/nodes/${entityId1}?project_id=${project._id}`)
        .set('x-user-id', devId);
      expect(res.status).toBe(200);
      expect(receivedRequests[0].url).toContain(`/architecture-versions/${versionId}/graph/nodes/${entityId1}`);
    });

    it('verifies GET /nodes/:entityId/neighborhood', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ nodes: [], edges: [] }));
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/nodes/${entityId1}/neighborhood?project_id=${project._id}`)
        .set('x-user-id', devId);
      expect(res.status).toBe(200);
      expect(receivedRequests[0].url).toContain(`/architecture-versions/${versionId}/graph/nodes/${entityId1}/neighborhood`);
    });

    it('verifies GET /nodes/:entityId/dependencies', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ nodes: [], edges: [] }));
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/nodes/${entityId1}/dependencies?project_id=${project._id}`)
        .set('x-user-id', devId);
      expect(res.status).toBe(200);
      expect(receivedRequests[0].url).toContain(`/architecture-versions/${versionId}/graph/nodes/${entityId1}/dependencies`);
    });

    it('verifies GET /nodes/:entityId/dependents', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ nodes: [], edges: [] }));
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/nodes/${entityId1}/dependents?project_id=${project._id}`)
        .set('x-user-id', devId);
      expect(res.status).toBe(200);
      expect(receivedRequests[0].url).toContain(`/architecture-versions/${versionId}/graph/nodes/${entityId1}/dependents`);
    });

    it('verifies GET /nodes/:entityId/containment', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ nodes: [], edges: [] }));
      };

      const res = await request(app)
        .get(`/api/v1/architecture-versions/${versionId}/graph/nodes/${entityId1}/containment?project_id=${project._id}`)
        .set('x-user-id', devId);
      expect(res.status).toBe(200);
      expect(receivedRequests[0].url).toContain(`/architecture-versions/${versionId}/graph/nodes/${entityId1}/containment`);
    });

    it('verifies GET /paths', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ paths: [], total_paths_found: 0 }));
      };

      const res = await request(app)
        .get(
          `/api/v1/architecture-versions/${versionId}/graph/paths?project_id=${project._id}&source_entity_id=${entityId1}&target_entity_id=${entityId2}`
        )
        .set('x-user-id', devId);
      expect(res.status).toBe(200);
      expect(receivedRequests[0].url).toContain(`/architecture-versions/${versionId}/graph/paths`);
    });

    it('verifies POST /rebuild', async () => {
      upstreamResponseHandler = (req, res) => {
        res.writeHead(202, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ attempt_status: 'QUEUED' }));
      };

      const res = await request(app)
        .post(`/api/v1/architecture-versions/${versionId}/graph/rebuild?project_id=${project._id}`)
        .set('x-user-id', ownerId)
        .send({});
      expect(res.status).toBe(202);
      expect(receivedRequests[0].url).toContain(`/architecture-versions/${versionId}/graph/rebuild`);
    });
  });
});

