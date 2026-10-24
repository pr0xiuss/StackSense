const crypto = require('crypto');
const request = require('supertest');
const app = require('../../src/app');
const projectService = require('../../src/services/projectService');
const projectAccessService = require('../../src/services/projectAccessService');
const { PROJECT_ROLES } = require('../../src/constants/projectRoles');

const NON_EXISTENT_UUID_V4 = '00000000-0000-4000-8000-000000000000';

describe('Repository API Integration Tests (M3 Batch 1)', () => {
  let ownerId;
  let devId;
  let viewerId;
  let outsiderId;
  let project;

  beforeEach(async () => {
    ownerId = crypto.randomUUID();
    devId = crypto.randomUUID();
    viewerId = crypto.randomUUID();
    outsiderId = crypto.randomUUID();

    project = await projectService.createProject({
      name: `Project-${crypto.randomUUID().slice(0, 8)}`,
      description: 'Test project for repository API',
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
  });

  describe('Authentication & Route Validation', () => {
    it('rejects unauthenticated request with 401 authentication_required', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .send({ name: 'my-repo' });

      expect(res.status).toBe(401);
      expect(res.body.error.code).toBe('authentication_required');
    });

    it('rejects invalid projectId format with 422 invalid_project_id', async () => {
      const res = await request(app)
        .post('/api/v1/projects/not-a-uuid/repositories')
        .set('x-user-id', ownerId)
        .send({ name: 'my-repo' });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_project_id');
    });

    it('rejects invalid repositoryId format with 422 invalid_repository_id', async () => {
      const res = await request(app)
        .get(`/api/v1/projects/${project._id}/repositories/not-a-uuid`)
        .set('x-user-id', ownerId);

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_repository_id');
    });

    it('rejects registration with missing or empty name with 422 validation_error', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: '   ' });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });
  });

  describe('Repository Registration (POST)', () => {
    it('registers a new repository successfully (201 Created)', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({
          name: 'backend-core',
          description: 'Core backend service',
        });

      expect(res.status).toBe(201);
      expect(res.body.id).toBeDefined();
      expect(res.body.name).toBe('backend-core');
      expect(res.body.description).toBe('Core backend service');
      expect(res.body.project_id).toBe(project._id);
      expect(res.body.status).toBe('registered');
    });

    it('rejects duplicate repository name within the same project with 409 repository_already_exists', async () => {
      await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'service-x' });

      const res = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', devId)
        .send({ name: 'service-x' });

      expect(res.status).toBe(409);
      expect(res.body.error.code).toBe('repository_already_exists');
    });

    it('allows identical repository name in another project', async () => {
      const project2 = await projectService.createProject({
        name: 'Second-Project',
        ownerId,
      });

      const res1 = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'shared-lib' });
      expect(res1.status).toBe(201);

      const res2 = await request(app)
        .post(`/api/v1/projects/${project2._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'shared-lib' });
      expect(res2.status).toBe(201);
      expect(res2.body.project_id).toBe(project2._id);
    });
  });

  describe('Repository Retrieval & Listing (GET)', () => {
    it('retrieves single repository by ID (200 OK)', async () => {
      const createRes = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'api-service' });

      const repoId = createRes.body.id;

      const res = await request(app)
        .get(`/api/v1/projects/${project._id}/repositories/${repoId}`)
        .set('x-user-id', viewerId);

      expect(res.status).toBe(200);
      expect(res.body.id).toBe(repoId);
      expect(res.body.name).toBe('api-service');
    });

    it('returns 404 repository_not_found for non-existent repository', async () => {
      const res = await request(app)
        .get(`/api/v1/projects/${project._id}/repositories/${NON_EXISTENT_UUID_V4}`)
        .set('x-user-id', ownerId);

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('repository_not_found');
    });

    it('returns 404 repository_not_found when repository belongs to a different project', async () => {
      const project2 = await projectService.createProject({
        name: 'Project 2',
        ownerId,
      });

      const createRes = await request(app)
        .post(`/api/v1/projects/${project2._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'other-repo' });

      const repoId = createRes.body.id;

      // Accessing via Project 1 URL path
      const res = await request(app)
        .get(`/api/v1/projects/${project._id}/repositories/${repoId}`)
        .set('x-user-id', ownerId);

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('repository_not_found');
    });

    it('lists repositories with pagination (200 OK)', async () => {
      await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'repo-alpha' });

      await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'repo-beta' });

      const res = await request(app)
        .get(`/api/v1/projects/${project._id}/repositories?limit=1&offset=0`)
        .set('x-user-id', viewerId);

      expect(res.status).toBe(200);
      expect(res.body).toHaveLength(1);
      expect(res.body[0].name).toBe('repo-alpha');
    });
  });

  describe('Repository Update (PATCH)', () => {
    it('updates repository name and description (200 OK)', async () => {
      const createRes = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'initial-name', description: 'initial desc' });

      const repoId = createRes.body.id;

      const res = await request(app)
        .patch(`/api/v1/projects/${project._id}/repositories/${repoId}`)
        .set('x-user-id', devId)
        .send({ name: 'updated-name', description: 'updated desc' });

      expect(res.status).toBe(200);
      expect(res.body.name).toBe('updated-name');
      expect(res.body.description).toBe('updated desc');
    });

    it('rejects update if new name conflicts with an existing repo (409)', async () => {
      await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'repo-1' });

      const repo2 = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'repo-2' });

      const res = await request(app)
        .patch(`/api/v1/projects/${project._id}/repositories/${repo2.body.id}`)
        .set('x-user-id', ownerId)
        .send({ name: 'repo-1' });

      expect(res.status).toBe(409);
      expect(res.body.error.code).toBe('repository_already_exists');
    });
  });

  describe('Repository Deletion (DELETE)', () => {
    it('deletes repository successfully (204 No Content)', async () => {
      const createRes = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'temporary-repo' });

      const repoId = createRes.body.id;

      const deleteRes = await request(app)
        .delete(`/api/v1/projects/${project._id}/repositories/${repoId}`)
        .set('x-user-id', ownerId);

      expect(deleteRes.status).toBe(204);

      // Verify it is gone
      const getRes = await request(app)
        .get(`/api/v1/projects/${project._id}/repositories/${repoId}`)
        .set('x-user-id', ownerId);

      expect(getRes.status).toBe(404);
    });

    it('rejects cross-project repository deletion with 404', async () => {
      const project2 = await projectService.createProject({
        name: 'Project-Two',
        ownerId,
      });

      const repoRes = await request(app)
        .post(`/api/v1/projects/${project2._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'isolated-repo' });

      const repoId = repoRes.body.id;

      // Attempt to delete through project 1 URL
      const deleteRes = await request(app)
        .delete(`/api/v1/projects/${project._id}/repositories/${repoId}`)
        .set('x-user-id', ownerId);

      expect(deleteRes.status).toBe(404);
      expect(deleteRes.body.error.code).toBe('repository_not_found');
    });

    it('rejects unauthenticated deletion with 401', async () => {
      const repoRes = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'auth-check-repo' });

      const repoId = repoRes.body.id;

      const deleteRes = await request(app)
        .delete(`/api/v1/projects/${project._id}/repositories/${repoId}`);

      expect(deleteRes.status).toBe(401);
      expect(deleteRes.body.error.code).toBe('authentication_required');
    });
  });

  describe('Role-Based Access Control (RBAC)', () => {
    it('prevents VIEWER from creating, updating, or deleting repositories (403)', async () => {
      // Create attempt
      const createRes = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', viewerId)
        .send({ name: 'viewer-create' });
      expect(createRes.status).toBe(403);
      expect(createRes.body.error.code).toBe('project_access_denied');

      // Create valid repo with Owner
      const validRepo = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'valid-repo-rbac' });

      const repoId = validRepo.body.id;

      // Update attempt by VIEWER
      const updateRes = await request(app)
        .patch(`/api/v1/projects/${project._id}/repositories/${repoId}`)
        .set('x-user-id', viewerId)
        .send({ name: 'viewer-renamed' });
      expect(updateRes.status).toBe(403);
      expect(updateRes.body.error.code).toBe('project_access_denied');

      // Delete attempt by VIEWER
      const deleteRes = await request(app)
        .delete(`/api/v1/projects/${project._id}/repositories/${repoId}`)
        .set('x-user-id', viewerId);
      expect(deleteRes.status).toBe(403);
      expect(deleteRes.body.error.code).toBe('project_access_denied');
    });

    it('prevents DEVELOPER from deleting repositories (403)', async () => {
      const validRepo = await request(app)
        .post(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', ownerId)
        .send({ name: 'dev-delete-forbidden' });

      const repoId = validRepo.body.id;

      const deleteRes = await request(app)
        .delete(`/api/v1/projects/${project._id}/repositories/${repoId}`)
        .set('x-user-id', devId);

      expect(deleteRes.status).toBe(403);
      expect(deleteRes.body.error.code).toBe('project_access_denied');
    });

    it('rejects access from outsider with 403 project_access_denied', async () => {
      const res = await request(app)
        .get(`/api/v1/projects/${project._id}/repositories`)
        .set('x-user-id', outsiderId);

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });
  });
});
