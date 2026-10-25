const crypto = require('crypto');
const request = require('supertest');
const app = require('../../src/app');
const projectService = require('../../src/services/projectService');
const projectAccessService = require('../../src/services/projectAccessService');
const { PROJECT_ROLES } = require('../../src/constants/projectRoles');
const User = require('../../src/models/User');

const NON_EXISTENT_UUID_V4 = '00000000-0000-4000-8000-000000000000';
const INVALID_UUID = 'not-a-valid-uuid';

describe('Project Access API Integration Tests (Batch 2)', () => {
  let projectA;
  let projectB;
  let ownerUser;
  let adminUser;
  let developerUser;
  let viewerUser;
  let outsiderUser;
  let targetUser;

  beforeEach(async () => {
    // Generate isolated user identities
    ownerUser = crypto.randomUUID();
    adminUser = crypto.randomUUID();
    developerUser = crypto.randomUUID();
    viewerUser = crypto.randomUUID();
    outsiderUser = crypto.randomUUID();
    targetUser = crypto.randomUUID();

    // Create projects
    projectA = await projectService.createProject({
      name: 'Project Alpha',
      description: 'Alpha workspace',
    });

    projectB = await projectService.createProject({
      name: 'Project Beta',
      description: 'Beta workspace',
    });

    // Seed roles in projectA
    await projectAccessService.grantAccess({
      projectId: projectA._id,
      userId: ownerUser,
      role: PROJECT_ROLES.OWNER,
    });

    await projectAccessService.grantAccess({
      projectId: projectA._id,
      userId: adminUser,
      role: PROJECT_ROLES.ADMIN,
    });

    await projectAccessService.grantAccess({
      projectId: projectA._id,
      userId: developerUser,
      role: PROJECT_ROLES.DEVELOPER,
    });

    await projectAccessService.grantAccess({
      projectId: projectA._id,
      userId: viewerUser,
      role: PROJECT_ROLES.VIEWER,
    });
  });

  // =========================================================================
  // 1. Authentication Seam Verification
  // =========================================================================
  describe('Authentication Enforcement', () => {
    it('returns 401 authentication_required when no credentials or header provided', async () => {
      const res = await request(app).get(`/api/v1/projects/${projectA._id}/access`);

      expect(res.status).toBe(401);
      expect(res.body.error).toBeDefined();
      expect(res.body.error.code).toBe('authentication_required');
    });

    it('returns 422 invalid_user_id when x-user-id header is not a valid UUID v4', async () => {
      const res = await request(app)
        .get(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', 'invalid-uuid');

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_user_id');
    });
  });

  // =========================================================================
  // 2. Grant Access: POST /api/v1/projects/:projectId/access
  // =========================================================================
  describe('POST /api/v1/projects/:projectId/access', () => {
    it('allows OWNER to grant access and returns 201 with access representation', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', ownerUser)
        .send({
          user_id: targetUser,
          role: 'developer',
        });

      expect(res.status).toBe(201);
      expect(res.body).toEqual({
        project_id: projectA._id,
        user_id: targetUser,
        role: 'developer',
      });

      // Verify persistence
      const saved = await projectAccessService.getAccess(projectA._id, targetUser);
      expect(saved).not.toBeNull();
      expect(saved.role).toBe('developer');
    });

    it('allows ADMIN to grant access and returns 201', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', adminUser)
        .send({
          user_id: targetUser,
          role: 'viewer',
        });

      expect(res.status).toBe(201);
      expect(res.body.role).toBe('viewer');
    });

    it('denies DEVELOPER from granting access with 403 project_access_denied', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', developerUser)
        .send({
          user_id: targetUser,
          role: 'viewer',
        });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('denies VIEWER from granting access with 403 project_access_denied', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', viewerUser)
        .send({
          user_id: targetUser,
          role: 'viewer',
        });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('denies outsider from granting access with 403 project_access_denied', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', outsiderUser)
        .send({
          user_id: targetUser,
          role: 'viewer',
        });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('returns 409 project_access_already_exists when granting access to existing member', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', ownerUser)
        .send({
          user_id: developerUser, // already member
          role: 'developer',
        });

      expect(res.status).toBe(409);
      expect(res.body.error.code).toBe('project_access_already_exists');
    });

    it('returns 422 when request body is missing or empty', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', ownerUser)
        .send({});

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    it('returns 422 when user_id is missing', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', ownerUser)
        .send({ role: 'viewer' });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    it('returns 422 when user_id is not a valid UUID v4', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', ownerUser)
        .send({ user_id: 'bad-uuid', role: 'viewer' });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_user_id');
    });

    it('returns 422 when role is missing', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', ownerUser)
        .send({ user_id: targetUser });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    it('returns 422 when role is invalid', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', ownerUser)
        .send({ user_id: targetUser, role: 'superuser' });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    it('returns 422 when projectId param is invalid UUID', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${INVALID_UUID}/access`)
        .set('x-user-id', ownerUser)
        .send({ user_id: targetUser, role: 'viewer' });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_project_id');
    });
  });

  // =========================================================================
  // 3. List Members: GET /api/v1/projects/:projectId/access
  // =========================================================================
  describe('GET /api/v1/projects/:projectId/access', () => {
    it('allows OWNER to list project access records', async () => {
      const res = await request(app)
        .get(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', ownerUser);

      expect(res.status).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
      expect(res.body).toHaveLength(4);
      expect(res.body.map((m) => m.role).sort()).toEqual(
        ['admin', 'developer', 'owner', 'viewer'].sort()
      );
    });

    it('includes the minimal username for persisted users without exposing email', async () => {
      await User.create({
        _id: ownerUser,
        email: 'owner@example.com',
        username: 'project_owner',
        password_hash: 'hash',
      });

      const res = await request(app)
        .get(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', ownerUser)
        .expect(200);

      const owner = res.body.find((member) => member.user_id === ownerUser);
      expect(owner.username).toBe('project_owner');
      expect(owner.email).toBeUndefined();
    });

    it('allows ADMIN, DEVELOPER, and VIEWER to list project access records', async () => {
      for (const user of [adminUser, developerUser, viewerUser]) {
        const res = await request(app)
          .get(`/api/v1/projects/${projectA._id}/access`)
          .set('x-user-id', user);

        expect(res.status).toBe(200);
        expect(res.body).toHaveLength(4);
      }
    });

    it('denies outsider with 403 project_access_denied', async () => {
      const res = await request(app)
        .get(`/api/v1/projects/${projectA._id}/access`)
        .set('x-user-id', outsiderUser);

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('returns 422 when projectId param is malformed', async () => {
      const res = await request(app)
        .get(`/api/v1/projects/${INVALID_UUID}/access`)
        .set('x-user-id', ownerUser);

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_project_id');
    });
  });

  // =========================================================================
  // 4. Update Role: PATCH /api/v1/projects/:projectId/access/:userId
  // =========================================================================
  describe('PATCH /api/v1/projects/:projectId/access/:userId', () => {
    it('allows OWNER to change member role and returns 200 with updated document', async () => {
      const res = await request(app)
        .patch(`/api/v1/projects/${projectA._id}/access/${viewerUser}`)
        .set('x-user-id', ownerUser)
        .send({ role: 'developer' });

      expect(res.status).toBe(200);
      expect(res.body.role).toBe('developer');

      const updated = await projectAccessService.getAccess(projectA._id, viewerUser);
      expect(updated.role).toBe('developer');
    });

    it('allows ADMIN to change member role', async () => {
      const res = await request(app)
        .patch(`/api/v1/projects/${projectA._id}/access/${developerUser}`)
        .set('x-user-id', adminUser)
        .send({ role: 'viewer' });

      expect(res.status).toBe(200);
      expect(res.body.role).toBe('viewer');
    });

    it('denies changing your own role and preserves the access record', async () => {
      const res = await request(app)
        .patch(`/api/v1/projects/${projectA._id}/access/${ownerUser}`)
        .set('x-user-id', ownerUser)
        .send({ role: 'viewer' });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');

      const unchanged = await projectAccessService.getAccess(projectA._id, ownerUser);
      expect(unchanged.role).toBe(PROJECT_ROLES.OWNER);
    });

    it('denies DEVELOPER from changing role with 403', async () => {
      const res = await request(app)
        .patch(`/api/v1/projects/${projectA._id}/access/${viewerUser}`)
        .set('x-user-id', developerUser)
        .send({ role: 'developer' });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('denies VIEWER from changing role with 403', async () => {
      const res = await request(app)
        .patch(`/api/v1/projects/${projectA._id}/access/${developerUser}`)
        .set('x-user-id', viewerUser)
        .send({ role: 'viewer' });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('returns 404 project_access_not_found when changing role of non-member', async () => {
      const res = await request(app)
        .patch(`/api/v1/projects/${projectA._id}/access/${NON_EXISTENT_UUID_V4}`)
        .set('x-user-id', ownerUser)
        .send({ role: 'developer' });

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('project_access_not_found');
    });

    it('returns 422 when role is missing or invalid', async () => {
      const resInvalid = await request(app)
        .patch(`/api/v1/projects/${projectA._id}/access/${viewerUser}`)
        .set('x-user-id', ownerUser)
        .send({ role: 'invalid_role' });

      expect(resInvalid.status).toBe(422);
      expect(resInvalid.body.error.code).toBe('validation_error');
    });

    it('returns 422 when target userId param is invalid UUID', async () => {
      const res = await request(app)
        .patch(`/api/v1/projects/${projectA._id}/access/${INVALID_UUID}`)
        .set('x-user-id', ownerUser)
        .send({ role: 'developer' });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_user_id');
    });
  });

  // =========================================================================
  // 5. Revoke Access: DELETE /api/v1/projects/:projectId/access/:userId
  // =========================================================================
  describe('DELETE /api/v1/projects/:projectId/access/:userId', () => {
    it('allows OWNER to revoke member access and returns 204 No Content', async () => {
      const res = await request(app)
        .delete(`/api/v1/projects/${projectA._id}/access/${viewerUser}`)
        .set('x-user-id', ownerUser);

      expect(res.status).toBe(204);
      expect(res.text).toBe('');

      const check = await projectAccessService.getAccess(projectA._id, viewerUser);
      expect(check).toBeNull();
    });

    it('allows ADMIN to revoke member access and returns 204 No Content', async () => {
      const res = await request(app)
        .delete(`/api/v1/projects/${projectA._id}/access/${developerUser}`)
        .set('x-user-id', adminUser);

      expect(res.status).toBe(204);

      const check = await projectAccessService.getAccess(projectA._id, developerUser);
      expect(check).toBeNull();
    });

    it('denies revoking your own access and preserves the access record', async () => {
      const res = await request(app)
        .delete(`/api/v1/projects/${projectA._id}/access/${adminUser}`)
        .set('x-user-id', adminUser);

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');

      const unchanged = await projectAccessService.getAccess(projectA._id, adminUser);
      expect(unchanged).not.toBeNull();
      expect(unchanged.role).toBe(PROJECT_ROLES.ADMIN);
    });

    it('denies DEVELOPER from revoking access with 403', async () => {
      const res = await request(app)
        .delete(`/api/v1/projects/${projectA._id}/access/${viewerUser}`)
        .set('x-user-id', developerUser);

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('denies VIEWER from revoking access with 403', async () => {
      const res = await request(app)
        .delete(`/api/v1/projects/${projectA._id}/access/${developerUser}`)
        .set('x-user-id', viewerUser);

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    it('returns 404 project_access_not_found when revoking non-member', async () => {
      const res = await request(app)
        .delete(`/api/v1/projects/${projectA._id}/access/${NON_EXISTENT_UUID_V4}`)
        .set('x-user-id', ownerUser);

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('project_access_not_found');
    });

    it('returns 422 when target userId param is invalid UUID', async () => {
      const res = await request(app)
        .delete(`/api/v1/projects/${projectA._id}/access/${INVALID_UUID}`)
        .set('x-user-id', ownerUser);

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_user_id');
    });
  });

  // =========================================================================
  // 6. Cross-Project Isolation
  // =========================================================================
  describe('Cross-Project Isolation', () => {
    it('denies user with access to Project A from managing or reading Project B', async () => {
      // User is OWNER on Project A, but has zero access to Project B
      const listRes = await request(app)
        .get(`/api/v1/projects/${projectB._id}/access`)
        .set('x-user-id', ownerUser);

      expect(listRes.status).toBe(403);
      expect(listRes.body.error.code).toBe('project_access_denied');

      const grantRes = await request(app)
        .post(`/api/v1/projects/${projectB._id}/access`)
        .set('x-user-id', ownerUser)
        .send({
          user_id: targetUser,
          role: 'developer',
        });

      expect(grantRes.status).toBe(403);
      expect(grantRes.body.error.code).toBe('project_access_denied');
    });
  });
});
