const crypto = require('crypto');
const request = require('supertest');
const app = require('../../src/app');
const projectAccessService = require('../../src/services/projectAccessService');
const ProjectAccess = require('../../src/models/ProjectAccess');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const NON_EXISTENT_UUID_V4 = '00000000-0000-4000-8000-000000000000';
const INVALID_UUID_V1 = '216fff40-98d9-11ef-b864-0242ac120002'; // Version 1, not 4

describe('Project API Integration Tests (Batch 3 — M1 Integration & Full Authorization)', () => {
  let defaultUser;
  let otherUser;

  beforeEach(() => {
    defaultUser = crypto.randomUUID();
    otherUser = crypto.randomUUID();
  });

  // =========================================================================
  // 1. Authentication Enforcement on Project Endpoints
  // =========================================================================
  describe('Authentication Enforcement', () => {
    it('rejects unauthenticated project creation with 401 authentication_required', async () => {
      const res = await request(app)
        .post('/api/v1/projects')
        .send({ name: 'Unauthenticated Project' });

      expect(res.status).toBe(401);
      expect(res.body.error.code).toBe('authentication_required');
    });

    it('rejects unauthenticated project retrieval with 401 authentication_required', async () => {
      const res = await request(app).get(`/api/v1/projects/${NON_EXISTENT_UUID_V4}`);

      expect(res.status).toBe(401);
      expect(res.body.error.code).toBe('authentication_required');
    });

    it('rejects unauthenticated project listing with 401 authentication_required', async () => {
      const res = await request(app).get('/api/v1/projects');

      expect(res.status).toBe(401);
      expect(res.body.error.code).toBe('authentication_required');
    });

    it('rejects unauthenticated project update with 401 authentication_required', async () => {
      const res = await request(app)
        .patch(`/api/v1/projects/${NON_EXISTENT_UUID_V4}`)
        .send({ name: 'Update Attempt' });

      expect(res.status).toBe(401);
      expect(res.body.error.code).toBe('authentication_required');
    });

    it('rejects unauthenticated project deletion with 401 authentication_required', async () => {
      const res = await request(app).delete(`/api/v1/projects/${NON_EXISTENT_UUID_V4}`);

      expect(res.status).toBe(401);
      expect(res.body.error.code).toBe('authentication_required');
    });

    it('rejects malformed x-user-id header with 422 invalid_user_id', async () => {
      const res = await request(app)
        .get('/api/v1/projects')
        .set('x-user-id', 'not-a-uuid');

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_user_id');
    });
  });

  // =========================================================================
  // 2. Project Creation & Automatic OWNER Grant
  // =========================================================================
  describe('POST /api/v1/projects', () => {
    it('creates a project, returns 201, and automatically grants OWNER access to creator', async () => {
      const res = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({
          name: 'StackSense Core',
          description: 'Core architectural understanding platform',
        });

      expect(res.status).toBe(201);
      expect(res.body).toHaveProperty('id');
      expect(res.body.id).toMatch(UUID_V4_REGEX);
      expect(res.body._id).toBeUndefined();
      expect(res.body.__v).toBeUndefined();
      expect(res.body.name).toBe('StackSense Core');
      expect(res.body.description).toBe('Core architectural understanding platform');
      expect(res.body).toHaveProperty('created_at');
      expect(res.body).toHaveProperty('updated_at');

      // Verify automatic OWNER access grant in database
      const access = await projectAccessService.getAccess(res.body.id, defaultUser);
      expect(access).not.toBeNull();
      expect(access.role).toBe('owner');
      expect(access.project_id).toBe(res.body.id);
      expect(access.user_id).toBe(defaultUser);
    });

    it('rejects creation when name is missing or empty with 422', async () => {
      const resMissing = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({});

      expect(resMissing.status).toBe(422);
      expect(resMissing.body.error.code).toBe('validation_error');
      expect(resMissing.body.error.message).toContain('name is required');

      const resEmpty = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: '   ' });

      expect(resEmpty.status).toBe(422);
      expect(resEmpty.body.error.code).toBe('validation_error');
    });

    it('rejects name exceeding 255 characters with 422', async () => {
      const res = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'x'.repeat(256) });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
      expect(res.body.error.message).toContain('255');
    });

    it('rejects description exceeding 2000 characters with 422', async () => {
      const res = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({
          name: 'Valid Project',
          description: 'd'.repeat(2001),
        });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    it('rejects non-string description with 422', async () => {
      const res = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({
          name: 'Valid Project',
          description: 12345,
        });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    it('permits duplicate project names in accordance with architecture', async () => {
      const res1 = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Duplicate Name' });

      const res2 = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Duplicate Name' });

      expect(res1.status).toBe(201);
      expect(res2.status).toBe(201);
      expect(res1.body.id).not.toBe(res2.body.id);
    });
  });

  // =========================================================================
  // 3. User-Scoped Project Listing
  // =========================================================================
  describe('GET /api/v1/projects (User-Scoped Listing)', () => {
    it('returns only projects accessible to the authenticated user', async () => {
      // User A creates 2 projects
      const pA1 = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'User A - Project 1' });

      const pA2 = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'User A - Project 2' });

      // User B creates 1 project
      const pB = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', otherUser)
        .send({ name: 'User B - Project 1' });

      // Listing as User A
      const listA = await request(app)
        .get('/api/v1/projects')
        .set('x-user-id', defaultUser);

      expect(listA.status).toBe(200);
      expect(listA.body).toHaveLength(2);
      const idsA = listA.body.map((p) => p.id);
      expect(idsA).toContain(pA1.body.id);
      expect(idsA).toContain(pA2.body.id);
      expect(idsA).not.toContain(pB.body.id);

      // Listing as User B
      const listB = await request(app)
        .get('/api/v1/projects')
        .set('x-user-id', otherUser);

      expect(listB.status).toBe(200);
      expect(listB.body).toHaveLength(1);
      expect(listB.body[0].id).toBe(pB.body.id);
    });

    it('respects limit and offset query parameters', async () => {
      for (let i = 1; i <= 3; i++) {
        await request(app)
          .post('/api/v1/projects')
          .set('x-user-id', defaultUser)
          .send({ name: `Paged Project ${i}` });
      }

      const paged = await request(app)
        .get('/api/v1/projects?limit=2&offset=1')
        .set('x-user-id', defaultUser);

      expect(paged.status).toBe(200);
      expect(paged.body.length).toBe(2);
    });

    it('rejects invalid limit parameter with 422', async () => {
      const res = await request(app)
        .get('/api/v1/projects?limit=invalid')
        .set('x-user-id', defaultUser);

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    it('rejects negative offset parameter with 422', async () => {
      const res = await request(app)
        .get('/api/v1/projects?offset=-5')
        .set('x-user-id', defaultUser);

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });
  });

  // =========================================================================
  // 4. Project Retrieval & Anti-Enumeration Isolation
  // =========================================================================
  describe('GET /api/v1/projects/:projectId', () => {
    it('retrieves an existing project for member with 200', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Retrievable Project' });

      const res = await request(app)
        .get(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', defaultUser);

      expect(res.status).toBe(200);
      expect(res.body.id).toBe(created.body.id);
      expect(res.body.name).toBe('Retrievable Project');
    });

    it('returns 404 project_not_found for outsider to prevent enumeration', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Protected Project' });

      // otherUser is an outsider
      const res = await request(app)
        .get(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', otherUser);

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('project_not_found');
    });

    it('returns 404 for non-existent UUID v4', async () => {
      const res = await request(app)
        .get(`/api/v1/projects/${NON_EXISTENT_UUID_V4}`)
        .set('x-user-id', defaultUser);

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('project_not_found');
    });

    it('returns 422 for malformed UUID string', async () => {
      const res = await request(app)
        .get('/api/v1/projects/not-a-uuid')
        .set('x-user-id', defaultUser);

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_project_id');
    });

    it('returns 422 for non-v4 UUID (UUID v1 rejected)', async () => {
      const res = await request(app)
        .get(`/api/v1/projects/${INVALID_UUID_V1}`)
        .set('x-user-id', defaultUser);

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_project_id');
    });
  });

  // =========================================================================
  // 5. Project Update & RBAC Authorization
  // =========================================================================
  describe('PATCH /api/v1/projects/:projectId', () => {
    it('allows OWNER to update project metadata and returns 200', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Original Name', description: 'Original Description' });

      const res = await request(app)
        .patch(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', defaultUser)
        .send({
          name: 'Updated Name',
          description: 'Updated Description',
        });

      expect(res.status).toBe(200);
      expect(res.body.id).toBe(created.body.id);
      expect(res.body.name).toBe('Updated Name');
      expect(res.body.description).toBe('Updated Description');
    });

    it('allows DEVELOPER to update project metadata', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Dev Update Project' });

      // Grant DEVELOPER to otherUser
      await projectAccessService.grantAccess({
        projectId: created.body.id,
        userId: otherUser,
        role: 'developer',
      });

      const res = await request(app)
        .patch(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', otherUser)
        .send({ name: 'Updated by Developer' });

      expect(res.status).toBe(200);
      expect(res.body.name).toBe('Updated by Developer');
    });

    it('denies VIEWER from updating project with 403 project_access_denied', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Viewer Update Project' });

      // Grant VIEWER to otherUser
      await projectAccessService.grantAccess({
        projectId: created.body.id,
        userId: otherUser,
        role: 'viewer',
      });

      const res = await request(app)
        .patch(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', otherUser)
        .send({ name: 'Attempted Update' });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('denies outsider from updating project with 403 project_access_denied', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Outsider Update Project' });

      const res = await request(app)
        .patch(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', otherUser)
        .send({ name: 'Attempted Update' });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('returns 404 when updating non-existent project', async () => {
      const res = await request(app)
        .patch(`/api/v1/projects/${NON_EXISTENT_UUID_V4}`)
        .set('x-user-id', defaultUser)
        .send({ name: 'New Name' });

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('project_not_found');
    });

    it('returns 422 when update body has no valid fields', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Target Project' });

      const res = await request(app)
        .patch(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', defaultUser)
        .send({});

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });
  });

  // =========================================================================
  // 6. Project Deletion, RBAC & Cascade Deletion
  // =========================================================================
  describe('DELETE /api/v1/projects/:projectId', () => {
    it('allows OWNER to delete project and cascade deletes all ProjectAccess records', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Delete Target' });

      // Grant additional member access
      await projectAccessService.grantAccess({
        projectId: created.body.id,
        userId: otherUser,
        role: 'developer',
      });

      const accessBefore = await ProjectAccess.find({ project_id: created.body.id });
      expect(accessBefore).toHaveLength(2); // owner + developer

      const delRes = await request(app)
        .delete(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', defaultUser);

      expect(delRes.status).toBe(204);
      expect(delRes.text).toBe('');

      // Verify project is deleted
      const getRes = await request(app)
        .get(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', defaultUser);
      expect(getRes.status).toBe(404);

      // Verify all access records are cascade-deleted
      const accessAfter = await ProjectAccess.find({ project_id: created.body.id });
      expect(accessAfter).toHaveLength(0);
    });

    it('allows ADMIN to delete project with 204 No Content', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Admin Delete Target' });

      await projectAccessService.grantAccess({
        projectId: created.body.id,
        userId: otherUser,
        role: 'admin',
      });

      const res = await request(app)
        .delete(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', otherUser);

      expect(res.status).toBe(204);
    });

    it('denies DEVELOPER from deleting project with 403 project_access_denied', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Dev Delete Attempt' });

      await projectAccessService.grantAccess({
        projectId: created.body.id,
        userId: otherUser,
        role: 'developer',
      });

      const res = await request(app)
        .delete(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', otherUser);

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('denies VIEWER from deleting project with 403 project_access_denied', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .set('x-user-id', defaultUser)
        .send({ name: 'Viewer Delete Attempt' });

      await projectAccessService.grantAccess({
        projectId: created.body.id,
        userId: otherUser,
        role: 'viewer',
      });

      const res = await request(app)
        .delete(`/api/v1/projects/${created.body.id}`)
        .set('x-user-id', otherUser);

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('returns 404 when deleting a non-existent project', async () => {
      const res = await request(app)
        .delete(`/api/v1/projects/${NON_EXISTENT_UUID_V4}`)
        .set('x-user-id', defaultUser);

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('project_not_found');
    });

    it('returns 422 for invalid UUID v4 param on delete', async () => {
      const res = await request(app)
        .delete('/api/v1/projects/not-a-valid-uuid')
        .set('x-user-id', defaultUser);

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_project_id');
    });
  });
});
