const crypto = require('crypto');
const ProjectAccess = require('../../src/models/ProjectAccess');
const { PROJECT_ROLES } = require('../../src/constants/projectRoles');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe('ProjectAccess Model Unit Tests (Batch 1)', () => {
  const validProjectId = crypto.randomUUID();
  const validUserId = crypto.randomUUID();

  describe('Schema & Validation', () => {
    it('creates a valid ProjectAccess document with default UUID _id and timestamps', async () => {
      const access = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
        role: PROJECT_ROLES.OWNER,
      });

      await access.save();

      expect(access._id).toMatch(UUID_V4_REGEX);
      expect(access.project_id).toBe(validProjectId);
      expect(access.user_id).toBe(validUserId);
      expect(access.role).toBe('owner');
      expect(access.created_at).toBeInstanceOf(Date);
      expect(access.updated_at).toBeInstanceOf(Date);
    });

    it('rejects creation when project_id is missing', async () => {
      const access = new ProjectAccess({
        user_id: validUserId,
        role: PROJECT_ROLES.DEVELOPER,
      });

      await expect(access.save()).rejects.toThrow(/project_id is required/);
    });

    it('rejects creation when user_id is missing', async () => {
      const access = new ProjectAccess({
        project_id: validProjectId,
        role: PROJECT_ROLES.DEVELOPER,
      });

      await expect(access.save()).rejects.toThrow(/user_id is required/);
    });

    it('rejects creation when role is missing', async () => {
      const access = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
      });

      await expect(access.save()).rejects.toThrow(/role is required/);
    });

    it('rejects invalid project_id UUID format', async () => {
      const access = new ProjectAccess({
        project_id: 'not-a-uuid',
        user_id: validUserId,
        role: PROJECT_ROLES.VIEWER,
      });

      await expect(access.save()).rejects.toThrow(/valid UUID v4/);
    });

    it('rejects invalid user_id UUID format', async () => {
      const access = new ProjectAccess({
        project_id: validProjectId,
        user_id: '123-invalid-uuid',
        role: PROJECT_ROLES.VIEWER,
      });

      await expect(access.save()).rejects.toThrow(/valid UUID v4/);
    });

    it('rejects invalid role string', async () => {
      const access = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
        role: 'superadmin',
      });

      await expect(access.save()).rejects.toThrow(/Invalid project role/);
    });

    it('serializes to JSON with { project_id, user_id, role } matching API contract', async () => {
      const access = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
        role: PROJECT_ROLES.ADMIN,
      });

      await access.save();

      const json = access.toJSON();
      expect(json).toEqual({
        project_id: validProjectId,
        user_id: validUserId,
        role: 'admin',
      });
      expect(json._id).toBeUndefined();
      expect(json.id).toBeUndefined();
      expect(json.__v).toBeUndefined();
    });

    it('enforces compound uniqueness on (project_id, user_id)', async () => {
      // Ensure indexes are built
      await ProjectAccess.init();

      const access1 = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
        role: PROJECT_ROLES.DEVELOPER,
      });
      await access1.save();

      const access2 = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
        role: PROJECT_ROLES.VIEWER,
      });

      await expect(access2.save()).rejects.toThrow(/duplicate key/i);
    });

    it('permits the same user to have access across different projects', async () => {
      await ProjectAccess.init();

      const otherProjectId = crypto.randomUUID();

      const access1 = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
        role: PROJECT_ROLES.OWNER,
      });
      const access2 = new ProjectAccess({
        project_id: otherProjectId,
        user_id: validUserId,
        role: PROJECT_ROLES.VIEWER,
      });

      await access1.save();
      await expect(access2.save()).resolves.toBeDefined();
    });

    it('permits different users to have access within the same project', async () => {
      await ProjectAccess.init();

      const otherUserId = crypto.randomUUID();

      const access1 = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
        role: PROJECT_ROLES.OWNER,
      });
      const access2 = new ProjectAccess({
        project_id: validProjectId,
        user_id: otherUserId,
        role: PROJECT_ROLES.DEVELOPER,
      });

      await access1.save();
      await expect(access2.save()).resolves.toBeDefined();
    });
  });

  describe('Domain Capability Methods', () => {
    it('OWNER role has full capabilities', () => {
      const access = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
        role: PROJECT_ROLES.OWNER,
      });

      expect(access.canRead()).toBe(true);
      expect(access.canCreate()).toBe(true);
      expect(access.canUpdate()).toBe(true);
      expect(access.canDelete()).toBe(true);
    });

    it('ADMIN role has full capabilities', () => {
      const access = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
        role: PROJECT_ROLES.ADMIN,
      });

      expect(access.canRead()).toBe(true);
      expect(access.canCreate()).toBe(true);
      expect(access.canUpdate()).toBe(true);
      expect(access.canDelete()).toBe(true);
    });

    it('DEVELOPER role can read, create, and update, but cannot delete', () => {
      const access = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
        role: PROJECT_ROLES.DEVELOPER,
      });

      expect(access.canRead()).toBe(true);
      expect(access.canCreate()).toBe(true);
      expect(access.canUpdate()).toBe(true);
      expect(access.canDelete()).toBe(false);
    });

    it('VIEWER role can only read', () => {
      const access = new ProjectAccess({
        project_id: validProjectId,
        user_id: validUserId,
        role: PROJECT_ROLES.VIEWER,
      });

      expect(access.canRead()).toBe(true);
      expect(access.canCreate()).toBe(false);
      expect(access.canUpdate()).toBe(false);
      expect(access.canDelete()).toBe(false);
    });
  });
});
