const crypto = require('crypto');
const ProjectAccess = require('../../src/models/ProjectAccess');
const projectAccessService = require('../../src/services/projectAccessService');
const projectAuthorization = require('../../src/services/projectAuthorization');
const { PROJECT_ROLES } = require('../../src/constants/projectRoles');
const { ProjectAccessDeniedError } = require('../../src/errors/accessErrors');

describe('ProjectAuthorization Unit Tests (Batch 1)', () => {
  beforeEach(async () => {
    await ProjectAccess.init();
  });

  const projectId = crypto.randomUUID();
  const ownerId = crypto.randomUUID();
  const adminId = crypto.randomUUID();
  const developerId = crypto.randomUUID();
  const viewerId = crypto.randomUUID();
  const outsiderId = crypto.randomUUID();

  beforeEach(async () => {
    await projectAccessService.grantAccess({ projectId, userId: ownerId, role: PROJECT_ROLES.OWNER });
    await projectAccessService.grantAccess({ projectId, userId: adminId, role: PROJECT_ROLES.ADMIN });
    await projectAccessService.grantAccess({ projectId, userId: developerId, role: PROJECT_ROLES.DEVELOPER });
    await projectAccessService.grantAccess({ projectId, userId: viewerId, role: PROJECT_ROLES.VIEWER });
  });

  describe('requireAccess (Read capability)', () => {
    it('allows OWNER, ADMIN, DEVELOPER, VIEWER to access project', async () => {
      await expect(projectAuthorization.requireAccess(projectId, ownerId)).resolves.toBeDefined();
      await expect(projectAuthorization.requireAccess(projectId, adminId)).resolves.toBeDefined();
      await expect(projectAuthorization.requireAccess(projectId, developerId)).resolves.toBeDefined();
      await expect(projectAuthorization.requireAccess(projectId, viewerId)).resolves.toBeDefined();
    });

    it('denies outsider with ProjectAccessDeniedError (code: project_access_denied, status: 403)', async () => {
      try {
        await projectAuthorization.requireAccess(projectId, outsiderId);
        throw new Error('Should have thrown');
      } catch (err) {
        expect(err).toBeInstanceOf(ProjectAccessDeniedError);
        expect(err.code).toBe('project_access_denied');
        expect(err.status).toBe(403);
      }
    });
  });

  describe('requireCreateAccess (Create resources capability)', () => {
    it('allows OWNER, ADMIN, DEVELOPER to create resources', async () => {
      await expect(projectAuthorization.requireCreateAccess(projectId, ownerId)).resolves.toBeDefined();
      await expect(projectAuthorization.requireCreateAccess(projectId, adminId)).resolves.toBeDefined();
      await expect(projectAuthorization.requireCreateAccess(projectId, developerId)).resolves.toBeDefined();
    });

    it('denies VIEWER and outsider from creating resources', async () => {
      await expect(projectAuthorization.requireCreateAccess(projectId, viewerId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
      await expect(projectAuthorization.requireCreateAccess(projectId, outsiderId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
    });
  });

  describe('requireUpdateAccess (Update resources capability)', () => {
    it('allows OWNER, ADMIN, DEVELOPER to update resources', async () => {
      await expect(projectAuthorization.requireUpdateAccess(projectId, ownerId)).resolves.toBeDefined();
      await expect(projectAuthorization.requireUpdateAccess(projectId, adminId)).resolves.toBeDefined();
      await expect(projectAuthorization.requireUpdateAccess(projectId, developerId)).resolves.toBeDefined();
    });

    it('denies VIEWER and outsider from updating resources', async () => {
      await expect(projectAuthorization.requireUpdateAccess(projectId, viewerId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
      await expect(projectAuthorization.requireUpdateAccess(projectId, outsiderId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
    });
  });

  describe('requireDeleteAccess (Delete project / resources capability)', () => {
    it('allows OWNER and ADMIN to delete project resources', async () => {
      await expect(projectAuthorization.requireDeleteAccess(projectId, ownerId)).resolves.toBeDefined();
      await expect(projectAuthorization.requireDeleteAccess(projectId, adminId)).resolves.toBeDefined();
    });

    it('denies DEVELOPER, VIEWER, and outsider from deleting project resources', async () => {
      await expect(projectAuthorization.requireDeleteAccess(projectId, developerId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
      await expect(projectAuthorization.requireDeleteAccess(projectId, viewerId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
      await expect(projectAuthorization.requireDeleteAccess(projectId, outsiderId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
    });
  });

  describe('requireManageAccess (Membership management capability)', () => {
    it('allows OWNER and ADMIN to manage access', async () => {
      await expect(projectAuthorization.requireManageAccess(projectId, ownerId)).resolves.toBeDefined();
      await expect(projectAuthorization.requireManageAccess(projectId, adminId)).resolves.toBeDefined();
    });

    it('denies DEVELOPER, VIEWER, and outsider from managing access', async () => {
      await expect(projectAuthorization.requireManageAccess(projectId, developerId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
      await expect(projectAuthorization.requireManageAccess(projectId, viewerId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
      await expect(projectAuthorization.requireManageAccess(projectId, outsiderId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
    });
  });

  describe('requireManageOtherUserAccess (Target-aware membership management)', () => {
    it('allows OWNER and ADMIN to manage another member', async () => {
      await expect(
        projectAuthorization.requireManageOtherUserAccess(projectId, ownerId, viewerId)
      ).resolves.toBeDefined();
      await expect(
        projectAuthorization.requireManageOtherUserAccess(projectId, adminId, developerId)
      ).resolves.toBeDefined();
    });

    it('denies OWNER and ADMIN from changing their own access', async () => {
      await expect(
        projectAuthorization.requireManageOtherUserAccess(projectId, ownerId, ownerId)
      ).rejects.toMatchObject({ code: 'project_access_denied', status: 403 });
      await expect(
        projectAuthorization.requireManageOtherUserAccess(projectId, adminId, adminId)
      ).rejects.toMatchObject({ code: 'project_access_denied', status: 403 });
    });
  });

  describe('Cross-Project Isolation', () => {
    it('does not grant access to project B if user only has access to project A', async () => {
      const projectB = crypto.randomUUID();
      await projectAccessService.grantAccess({ projectId: projectB, userId: outsiderId, role: PROJECT_ROLES.OWNER });

      // Owner of Project A cannot manage or delete Project B
      await expect(projectAuthorization.requireAccess(projectB, ownerId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
      await expect(projectAuthorization.requireManageAccess(projectB, ownerId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
      await expect(projectAuthorization.requireDeleteAccess(projectB, ownerId)).rejects.toThrow(
        ProjectAccessDeniedError
      );
    });
  });
});
