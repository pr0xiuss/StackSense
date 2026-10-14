const crypto = require('crypto');
const ProjectAccess = require('../../src/models/ProjectAccess');
const projectAccessService = require('../../src/services/projectAccessService');
const { PROJECT_ROLES } = require('../../src/constants/projectRoles');
const {
  ProjectAccessAlreadyExistsError,
  ProjectAccessNotFoundError,
} = require('../../src/errors/accessErrors');

describe('ProjectAccessService Unit Tests (Batch 1)', () => {
  beforeEach(async () => {
    await ProjectAccess.init();
  });

  const projectId = crypto.randomUUID();
  const userId = crypto.randomUUID();

  describe('grantAccess', () => {
    it('grants access to a user with the specified role', async () => {
      const access = await projectAccessService.grantAccess({
        projectId,
        userId,
        role: PROJECT_ROLES.DEVELOPER,
      });

      expect(access).toBeDefined();
      expect(access.project_id).toBe(projectId);
      expect(access.user_id).toBe(userId);
      expect(access.role).toBe('developer');

      const found = await ProjectAccess.findOne({ project_id: projectId, user_id: userId });
      expect(found).not.toBeNull();
      expect(found.role).toBe('developer');
    });

    it('throws ProjectAccessAlreadyExistsError on duplicate access grant attempt', async () => {
      await projectAccessService.grantAccess({
        projectId,
        userId,
        role: PROJECT_ROLES.DEVELOPER,
      });

      await expect(
        projectAccessService.grantAccess({
          projectId,
          userId,
          role: PROJECT_ROLES.VIEWER,
        })
      ).rejects.toThrow(ProjectAccessAlreadyExistsError);
    });

    it('attaches proper code (project_access_already_exists) and status (409) to conflict error', async () => {
      await projectAccessService.grantAccess({
        projectId,
        userId,
        role: PROJECT_ROLES.ADMIN,
      });

      try {
        await projectAccessService.grantAccess({
          projectId,
          userId,
          role: PROJECT_ROLES.DEVELOPER,
        });
        throw new Error('Should have failed');
      } catch (err) {
        expect(err).toBeInstanceOf(ProjectAccessAlreadyExistsError);
        expect(err.code).toBe('project_access_already_exists');
        expect(err.status).toBe(409);
      }
    });
  });

  describe('getAccess', () => {
    it('returns the access document when it exists', async () => {
      await projectAccessService.grantAccess({
        projectId,
        userId,
        role: PROJECT_ROLES.OWNER,
      });

      const access = await projectAccessService.getAccess(projectId, userId);
      expect(access).not.toBeNull();
      expect(access.role).toBe('owner');
    });

    it('returns null when access record does not exist', async () => {
      const access = await projectAccessService.getAccess(projectId, crypto.randomUUID());
      expect(access).toBeNull();
    });
  });

  describe('listProjectAccess', () => {
    it('returns all access records for the project sorted by user_id', async () => {
      const u1 = '00000000-0000-4000-8000-000000000001';
      const u2 = '00000000-0000-4000-8000-000000000002';
      const otherProj = crypto.randomUUID();

      await projectAccessService.grantAccess({ projectId, userId: u2, role: PROJECT_ROLES.VIEWER });
      await projectAccessService.grantAccess({ projectId, userId: u1, role: PROJECT_ROLES.OWNER });
      await projectAccessService.grantAccess({ projectId: otherProj, userId: u1, role: PROJECT_ROLES.ADMIN });

      const members = await projectAccessService.listProjectAccess(projectId);
      expect(members).toHaveLength(2);
      expect(members[0].user_id).toBe(u1);
      expect(members[1].user_id).toBe(u2);
    });
  });

  describe('listUserAccess', () => {
    it('returns user access records with pagination', async () => {
      const p1 = '10000000-0000-4000-8000-000000000001';
      const p2 = '20000000-0000-4000-8000-000000000002';
      const p3 = '30000000-0000-4000-8000-000000000003';

      await projectAccessService.grantAccess({ projectId: p1, userId, role: PROJECT_ROLES.DEVELOPER });
      await projectAccessService.grantAccess({ projectId: p2, userId, role: PROJECT_ROLES.ADMIN });
      await projectAccessService.grantAccess({ projectId: p3, userId, role: PROJECT_ROLES.VIEWER });

      // Page 1
      const page1 = await projectAccessService.listUserAccess(userId, { limit: 2, offset: 0 });
      expect(page1).toHaveLength(2);
      expect(page1[0].project_id).toBe(p1);
      expect(page1[1].project_id).toBe(p2);

      // Page 2
      const page2 = await projectAccessService.listUserAccess(userId, { limit: 2, offset: 2 });
      expect(page2).toHaveLength(1);
      expect(page2[0].project_id).toBe(p3);
    });
  });

  describe('changeRole', () => {
    it('updates role of an existing member', async () => {
      await projectAccessService.grantAccess({
        projectId,
        userId,
        role: PROJECT_ROLES.VIEWER,
      });

      const updated = await projectAccessService.changeRole({
        projectId,
        userId,
        role: PROJECT_ROLES.DEVELOPER,
      });

      expect(updated.role).toBe('developer');

      const found = await projectAccessService.getAccess(projectId, userId);
      expect(found.role).toBe('developer');
    });

    it('throws ProjectAccessNotFoundError if member does not exist', async () => {
      try {
        await projectAccessService.changeRole({
          projectId,
          userId: crypto.randomUUID(),
          role: PROJECT_ROLES.ADMIN,
        });
        throw new Error('Should have failed');
      } catch (err) {
        expect(err).toBeInstanceOf(ProjectAccessNotFoundError);
        expect(err.code).toBe('project_access_not_found');
        expect(err.status).toBe(404);
      }
    });
  });

  describe('revokeAccess', () => {
    it('revokes access of an existing member', async () => {
      await projectAccessService.grantAccess({
        projectId,
        userId,
        role: PROJECT_ROLES.DEVELOPER,
      });

      await projectAccessService.revokeAccess({ projectId, userId });

      const found = await projectAccessService.getAccess(projectId, userId);
      expect(found).toBeNull();
    });

    it('throws ProjectAccessNotFoundError if member does not exist', async () => {
      try {
        await projectAccessService.revokeAccess({
          projectId,
          userId: crypto.randomUUID(),
        });
        throw new Error('Should have failed');
      } catch (err) {
        expect(err).toBeInstanceOf(ProjectAccessNotFoundError);
        expect(err.code).toBe('project_access_not_found');
        expect(err.status).toBe(404);
      }
    });
  });
});
