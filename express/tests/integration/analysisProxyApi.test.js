const crypto = require('crypto');
const request = require('supertest');
const app = require('../../src/app');
const projectService = require('../../src/services/projectService');
const projectAccessService = require('../../src/services/projectAccessService');
const Repository = require('../../src/models/Repository');
const RepositoryRevision = require('../../src/models/RepositoryRevision');
const { PROJECT_ROLES } = require('../../src/constants/projectRoles');
const { analysisGatewayService } = require('../../src/services/analysisGatewayService');
const {
  AnalysisGatewayError,
  AnalysisServiceUnavailableError,
} = require('../../src/errors/analysisErrors');

describe('Analysis & Architecture Proxy API Integration Tests (M5 Batch 1)', () => {
  let ownerId;
  let devId;
  let viewerId;
  let outsiderId;
  let project;
  let repository;
  let revision;

  beforeEach(async () => {
    ownerId = crypto.randomUUID();
    devId = crypto.randomUUID();
    viewerId = crypto.randomUUID();
    outsiderId = crypto.randomUUID();

    project = await projectService.createProject({
      name: `Project-${crypto.randomUUID().slice(0, 8)}`,
      description: 'Test project for analysis proxy API',
      ownerId,
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

    repository = await Repository.create({
      _id: crypto.randomUUID(),
      project_id: project._id,
      name: 'sample-repo',
      status: 'registered',
    });

    revision = await RepositoryRevision.create({
      _id: crypto.randomUUID(),
      project_id: project._id,
      repository_id: repository._id,
      revision_identifier: 'v1.0.0',
      source_hash: 'a'.repeat(64),
      total_files: 10,
      total_bytes: 1024,
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Authentication Enforcement', () => {
    it('rejects unauthenticated POST /api/v1/analyses with 401', async () => {
      const res = await request(app)
        .post('/api/v1/analyses')
        .send({
          project_id: project._id,
          repository_id: repository._id,
          revision_id: revision._id,
        });

      expect(res.status).toBe(401);
      expect(res.body.error.code).toBe('authentication_required');
    });

    it('rejects unauthenticated GET /api/v1/analyses with 401', async () => {
      const res = await request(app).get(`/api/v1/analyses?project_id=${project._id}`);

      expect(res.status).toBe(401);
      expect(res.body.error.code).toBe('authentication_required');
    });

    it('rejects unauthenticated GET /api/v1/architecture-versions/:id with 401', async () => {
      const versionId = crypto.randomUUID();
      const res = await request(app).get(
        `/api/v1/architecture-versions/${versionId}?project_id=${project._id}`
      );

      expect(res.status).toBe(401);
      expect(res.body.error.code).toBe('authentication_required');
    });
  });

  describe('Role-Based Access Control (RBAC) & Project Isolation', () => {
    it('rejects outsider with 403 project_access_denied on create', async () => {
      const res = await request(app)
        .post('/api/v1/analyses')
        .set('x-user-id', outsiderId)
        .send({
          project_id: project._id,
          repository_id: repository._id,
          revision_id: revision._id,
        });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('authorizes before resource lookup so outsiders cannot probe repository IDs', async () => {
      const repositoryLookup = jest.spyOn(Repository, 'findOne');

      const res = await request(app)
        .post('/api/v1/analyses')
        .set('x-user-id', outsiderId)
        .send({
          project_id: project._id,
          repository_id: crypto.randomUUID(),
          revision_id: crypto.randomUUID(),
        });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
      expect(repositoryLookup).not.toHaveBeenCalled();
    });

    it('rejects VIEWER with 403 on create', async () => {
      const res = await request(app)
        .post('/api/v1/analyses')
        .set('x-user-id', viewerId)
        .send({
          project_id: project._id,
          repository_id: repository._id,
          revision_id: revision._id,
        });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('rejects VIEWER with 403 on cancel', async () => {
      const analysisId = crypto.randomUUID();
      const res = await request(app)
        .post(`/api/v1/analyses/${analysisId}/cancel?project_id=${project._id}`)
        .set('x-user-id', viewerId)
        .send({ reason: 'cancel attempt' });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('allows VIEWER to perform read operations', async () => {
      const mockResult = { items: [], total: 0, limit: 20, offset: 0 };
      const spy = jest
        .spyOn(analysisGatewayService, 'request')
        .mockResolvedValueOnce(mockResult);

      const res = await request(app)
        .get(`/api/v1/analyses?project_id=${project._id}`)
        .set('x-user-id', viewerId);

      expect(res.status).toBe(200);
      expect(res.body).toEqual(mockResult);
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({
          role: 'VIEWER',
          projectId: project._id,
        })
      );
      spy.mockRestore();
    });

    it('allows DEVELOPER to create and cancel analyses', async () => {
      const mockAnalysis = {
        id: crypto.randomUUID(),
        status: 'queued',
        project_id: project._id,
      };
      const spy = jest
        .spyOn(analysisGatewayService, 'request')
        .mockResolvedValueOnce(mockAnalysis);

      const res = await request(app)
        .post('/api/v1/analyses')
        .set('x-user-id', devId)
        .send({
          project_id: project._id,
          repository_id: repository._id,
          revision_id: revision._id,
        });

      expect(res.status).toBe(202);
      expect(res.body).toEqual(mockAnalysis);
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({
          role: 'DEVELOPER',
          projectId: project._id,
          method: 'POST',
          path: '/analyses',
        })
      );
      spy.mockRestore();
    });
  });

  describe('Project/Repository/Revision Chain Validation', () => {
    it('returns 404 repository_not_found when repository belongs to a different project', async () => {
      const otherProject = await projectService.createProject({
        name: 'Other-Proj',
        ownerId,
      });

      const res = await request(app)
        .post('/api/v1/analyses')
        .set('x-user-id', ownerId)
        .send({
          project_id: otherProject._id,
          repository_id: repository._id, // repository belongs to project, not otherProject
          revision_id: revision._id,
        });

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('repository_not_found');
    });

    it('returns 404 revision_not_found when revision belongs to a different repository', async () => {
      const otherRepo = await Repository.create({
        _id: crypto.randomUUID(),
        project_id: project._id,
        name: 'other-repo',
        status: 'registered',
      });

      const res = await request(app)
        .post('/api/v1/analyses')
        .set('x-user-id', ownerId)
        .send({
          project_id: project._id,
          repository_id: otherRepo._id,
          revision_id: revision._id, // revision belongs to repository, not otherRepo
        });

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('revision_not_found');
    });

    it('returns 422 when required fields are missing or not UUIDs', async () => {
      const res = await request(app)
        .post('/api/v1/analyses')
        .set('x-user-id', ownerId)
        .send({
          project_id: 'invalid-uuid',
          repository_id: repository._id,
          revision_id: revision._id,
        });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });
  });

  describe('Upstream Proxy Delegation & Endpoints', () => {
    it('GET /api/v1/analyses filters by repository_id and status', async () => {
      const mockResult = { items: [], total: 0, limit: 10, offset: 0 };
      const spy = jest
        .spyOn(analysisGatewayService, 'request')
        .mockResolvedValueOnce(mockResult);

      const res = await request(app)
        .get(
          `/api/v1/analyses?project_id=${project._id}&repository_id=${repository._id}&status=completed&limit=10&offset=0`
        )
        .set('x-user-id', ownerId);

      expect(res.status).toBe(200);
      expect(res.body).toEqual(mockResult);
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({
          path: '/analyses',
          query: expect.objectContaining({
            project_id: project._id,
            repository_id: repository._id,
            status: 'completed',
            limit: '10',
            offset: '0',
          }),
        })
      );
      spy.mockRestore();
    });

    it('GET /api/v1/analyses/:analysisId/diagnostics proxies diagnostics query', async () => {
      const analysisId = crypto.randomUUID();
      const mockDiagResult = { items: [], total: 0, limit: 20, offset: 0 };
      const spy = jest
        .spyOn(analysisGatewayService, 'request')
        .mockResolvedValueOnce(mockDiagResult);

      const res = await request(app)
        .get(
          `/api/v1/analyses/${analysisId}/diagnostics?project_id=${project._id}&severity=warning&stage=syntax_extraction`
        )
        .set('x-user-id', ownerId);

      expect(res.status).toBe(200);
      expect(res.body).toEqual(mockDiagResult);
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({
          path: `/analyses/${analysisId}/diagnostics`,
          query: expect.objectContaining({
            severity: 'warning',
            stage: 'syntax_extraction',
          }),
        })
      );
      spy.mockRestore();
    });

    it('GET /api/v1/analyses/:analysisId/architecture proxies architecture summary', async () => {
      const analysisId = crypto.randomUUID();
      const mockArch = { id: crypto.randomUUID(), sequence_number: 1, entity_count: 5 };
      const spy = jest
        .spyOn(analysisGatewayService, 'request')
        .mockResolvedValueOnce(mockArch);

      const res = await request(app)
        .get(`/api/v1/analyses/${analysisId}/architecture?project_id=${project._id}`)
        .set('x-user-id', ownerId);

      expect(res.status).toBe(200);
      expect(res.body).toEqual(mockArch);
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({
          path: `/analyses/${analysisId}/architecture`,
        })
      );
      spy.mockRestore();
    });

    it('GET /api/v1/architecture-versions/:versionId/evidence supports entity_id filter', async () => {
      const versionId = crypto.randomUUID();
      const entityId = crypto.randomUUID();
      const mockEvidence = { items: [], total: 0, limit: 20, offset: 0 };
      const spy = jest
        .spyOn(analysisGatewayService, 'request')
        .mockResolvedValueOnce(mockEvidence);

      const res = await request(app)
        .get(
          `/api/v1/architecture-versions/${versionId}/evidence?project_id=${project._id}&entity_id=${entityId}`
        )
        .set('x-user-id', ownerId);

      expect(res.status).toBe(200);
      expect(res.body).toEqual(mockEvidence);
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({
          path: `/architecture-versions/${versionId}/evidence`,
          query: expect.objectContaining({
            entity_id: entityId,
          }),
        })
      );
      spy.mockRestore();
    });

    it('GET /api/v1/analyses/:analysisId/events establishes SSE relay', async () => {
      const analysisId = crypto.randomUUID();
      const spy = jest
        .spyOn(analysisGatewayService, 'streamEvents')
        .mockImplementationOnce(async ({ clientRes }) => {
          clientRes.writeHead(200, { 'Content-Type': 'text/event-stream' });
          clientRes.write('event: analysis.queued\ndata: {}\n\n');
          clientRes.end();
        });

      const res = await request(app)
        .get(`/api/v1/analyses/${analysisId}/events?project_id=${project._id}`)
        .set('x-user-id', ownerId);

      expect(res.status).toBe(200);
      expect(res.headers['content-type']).toContain('text/event-stream');
      expect(res.text).toContain('event: analysis.queued');
      spy.mockRestore();
    });

    it('relays upstream 409 conflict cleanly without exposing secrets', async () => {
      const analysisId = crypto.randomUUID();
      const spy = jest
        .spyOn(analysisGatewayService, 'request')
        .mockRejectedValueOnce(
          new AnalysisGatewayError(
            'Cannot cancel already completed analysis.',
            'analysis_cancel_not_allowed',
            409,
            { status: 'completed' }
          )
        );

      const res = await request(app)
        .post(`/api/v1/analyses/${analysisId}/cancel?project_id=${project._id}`)
        .set('x-user-id', ownerId)
        .send({ reason: 'cancel' });

      expect(res.status).toBe(409);
      expect(res.body.error.code).toBe('analysis_cancel_not_allowed');
      expect(res.body.error.message).toBe('Cannot cancel already completed analysis.');
      expect(res.body.error.details.status).toBe('completed');
      spy.mockRestore();
    });

    it('returns 503 analysis_service_unavailable when backend service is down', async () => {
      const spy = jest
        .spyOn(analysisGatewayService, 'request')
        .mockRejectedValueOnce(
          new AnalysisServiceUnavailableError('Analysis service is currently unavailable.')
        );

      const res = await request(app)
        .get(`/api/v1/analyses?project_id=${project._id}`)
        .set('x-user-id', ownerId);

      expect(res.status).toBe(503);
      expect(res.body.error.code).toBe('analysis_service_unavailable');
      spy.mockRestore();
    });
  });
});
