const crypto = require('crypto');
const authenticate = require('../../src/middleware/authenticate');
const tokenService = require('../../src/services/auth/tokenService');
const projectAuthorization = require('../../src/services/projectAuthorization');
const Project = require('../../src/models/Project');
const ProjectAccess = require('../../src/models/ProjectAccess');
const { PROJECT_ROLES } = require('../../src/constants/projectRoles');
const { ProjectAccessDeniedError } = require('../../src/errors/accessErrors');

describe('Authenticate Middleware Unit Tests (M5 Batch 3)', () => {
  const validUuid = '11111111-1111-4111-8111-111111111111';
  const invalidUuid = 'not-a-valid-uuid';

  function createMockReq(headers = {}, overrides = {}) {
    return {
      headers,
      header: jest.fn((name) => {
        const lower = name.toLowerCase();
        return headers[lower] || headers[name];
      }),
      ...overrides,
    };
  }

  function createMockRes() {
    const json = jest.fn();
    const status = jest.fn().mockReturnValue({ json });
    return { status, json };
  }

  describe('Bearer JWT Token Verification', () => {
    it('authenticates valid Bearer token and sets req.user.id from payload.sub', () => {
      const user = {
        id: validUuid,
        email: 'jwtuser@stacksense.local',
      };
      const token = tokenService.createAccessToken(user);

      const req = createMockReq({
        authorization: `Bearer ${token}`,
      });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);

      expect(next).toHaveBeenCalledTimes(1);
      expect(req.user).toBeDefined();
      expect(req.user.id).toBe(validUuid);
      expect(req.user.email).toBe('jwtuser@stacksense.local');
      expect(res.status).not.toHaveBeenCalled();
    });

    it('returns 401 token_expired when Bearer token has expired', () => {
      const { TokenService } = require('../../src/services/auth/tokenService');
      const expiredService = new TokenService({
        expirationMinutes: -10, // Creates pre-expired token
      });
      const user = { id: validUuid, email: 'expired@stacksense.local' };
      const expiredToken = expiredService.createAccessToken(user);

      const req = createMockReq({
        authorization: `Bearer ${expiredToken}`,
      });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);

      expect(next).not.toHaveBeenCalled();
      expect(res.status).toHaveBeenCalledWith(401);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({
            code: 'token_expired',
          }),
        })
      );
    });

    it('returns 401 invalid_token when Bearer token signature is tampered', () => {
      const user = { id: validUuid, email: 'tampered@stacksense.local' };
      const token = tokenService.createAccessToken(user);
      const parts = token.split('.');
      const tamperedSig = parts[2][0] === 'a' ? 'b' + parts[2].slice(1) : 'a' + parts[2].slice(1);
      const tamperedToken = `${parts[0]}.${parts[1]}.${tamperedSig}`;

      const req = createMockReq({
        authorization: `Bearer ${tamperedToken}`,
      });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);

      expect(next).not.toHaveBeenCalled();
      expect(res.status).toHaveBeenCalledWith(401);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({
            code: 'invalid_token',
          }),
        })
      );
    });

    it('returns 401 invalid_token when authorization header is malformed', () => {
      const req = createMockReq({
        authorization: 'MalformedHeaderWithoutBearerPrefix',
      });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);

      expect(next).not.toHaveBeenCalled();
      expect(res.status).toHaveBeenCalledWith(401);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({
            code: 'invalid_token',
          }),
        })
      );
    });
  });

  describe('Production Security Guard for x-user-id Seam', () => {
    let originalEnv;

    beforeEach(() => {
      originalEnv = process.env.NODE_ENV;
    });

    afterEach(() => {
      process.env.NODE_ENV = originalEnv;
    });

    it('STRICT REJECTION: returns 401 authentication_required when x-user-id is presented in production', () => {
      process.env.NODE_ENV = 'production';

      const req = createMockReq({
        'x-user-id': validUuid,
      });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);

      expect(next).not.toHaveBeenCalled();
      expect(res.status).toHaveBeenCalledWith(401);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({
            code: 'authentication_required',
          }),
        })
      );
      expect(req.user).toBeUndefined();
    });

    it('TEST FALLBACK: allows x-user-id header when NODE_ENV is test', () => {
      process.env.NODE_ENV = 'test';

      const req = createMockReq({
        'x-user-id': validUuid,
      });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);

      expect(next).toHaveBeenCalledTimes(1);
      expect(req.user).toEqual({ id: validUuid });
      expect(res.status).not.toHaveBeenCalled();
    });

    it('TEST FALLBACK: returns 422 when x-user-id is not a valid UUID in test environment', () => {
      process.env.NODE_ENV = 'test';

      const req = createMockReq({
        'x-user-id': invalidUuid,
      });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);

      expect(next).not.toHaveBeenCalled();
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({
            code: 'invalid_user_id',
          }),
        })
      );
    });
  });

  describe('Upstream req.user and Missing Credentials', () => {
    it('calls next() when req.user.id is already a valid UUID v4', () => {
      const req = createMockReq({}, { user: { id: validUuid } });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);
      expect(next).toHaveBeenCalledTimes(1);
      expect(req.user.id).toBe(validUuid);
    });

    it('normalizes req.user.id and calls next() when req.user._id is provided', () => {
      const req = createMockReq({}, { user: { _id: validUuid } });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);
      expect(next).toHaveBeenCalledTimes(1);
      expect(req.user.id).toBe(validUuid);
    });

    it('returns 422 when req.user contains an invalid UUID', () => {
      const req = createMockReq({}, { user: { id: invalidUuid } });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({
            code: 'invalid_user_id',
          }),
        })
      );
      expect(next).not.toHaveBeenCalled();
    });

    it('returns 401 authentication_required when no credentials are provided', () => {
      const req = createMockReq({});
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);
      expect(res.status).toHaveBeenCalledWith(401);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({
            code: 'authentication_required',
          }),
        })
      );
      expect(next).not.toHaveBeenCalled();
    });
  });

  describe('M2 RBAC Integration Verification via Authenticated Bearer Token', () => {
    let projectId;
    let ownerId;
    let adminId;
    let developerId;
    let viewerId;
    let outsiderId;

    beforeEach(async () => {
      await Project.deleteMany({});
      await ProjectAccess.deleteMany({});

      ownerId = crypto.randomUUID();
      adminId = crypto.randomUUID();
      developerId = crypto.randomUUID();
      viewerId = crypto.randomUUID();
      outsiderId = crypto.randomUUID();

      const project = await Project.create({
        name: 'RBAC Test Project',
        description: 'Testing M2 RBAC with Bearer token authentication',
      });
      projectId = project._id;

      await ProjectAccess.create([
        { project_id: projectId, user_id: ownerId, role: PROJECT_ROLES.OWNER },
        { project_id: projectId, user_id: adminId, role: PROJECT_ROLES.ADMIN },
        { project_id: projectId, user_id: developerId, role: PROJECT_ROLES.DEVELOPER },
        { project_id: projectId, user_id: viewerId, role: PROJECT_ROLES.VIEWER },
      ]);
    });

    it('authenticates Bearer token for OWNER and grants full project capabilities', async () => {
      const token = tokenService.createAccessToken({ id: ownerId, email: 'owner@test.local' });
      const req = createMockReq({ authorization: `Bearer ${token}` });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);
      expect(next).toHaveBeenCalled();

      // Flow into M2 projectAuthorization
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);
      expect(access.canRead()).toBe(true);
      expect(access.canCreate()).toBe(true);
      expect(access.canUpdate()).toBe(true);
      expect(access.canDelete()).toBe(true);
    });

    it('authenticates Bearer token for DEVELOPER: allows read/create/update but rejects delete', async () => {
      const token = tokenService.createAccessToken({ id: developerId, email: 'dev@test.local' });
      const req = createMockReq({ authorization: `Bearer ${token}` });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);
      expect(next).toHaveBeenCalled();

      // Developer can read, create, update
      await expect(projectAuthorization.requireCreateAccess(projectId, req.user.id)).resolves.toBeDefined();
      await expect(projectAuthorization.requireUpdateAccess(projectId, req.user.id)).resolves.toBeDefined();

      // Developer cannot delete
      await expect(projectAuthorization.requireDeleteAccess(projectId, req.user.id)).rejects.toThrow(
        ProjectAccessDeniedError
      );
    });

    it('authenticates Bearer token for VIEWER: allows read but rejects create, update, delete', async () => {
      const token = tokenService.createAccessToken({ id: viewerId, email: 'viewer@test.local' });
      const req = createMockReq({ authorization: `Bearer ${token}` });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);
      expect(next).toHaveBeenCalled();

      // Viewer can read
      await expect(projectAuthorization.requireAccess(projectId, req.user.id)).resolves.toBeDefined();

      // Viewer cannot create, update, or delete
      await expect(projectAuthorization.requireCreateAccess(projectId, req.user.id)).rejects.toThrow(
        ProjectAccessDeniedError
      );
      await expect(projectAuthorization.requireUpdateAccess(projectId, req.user.id)).rejects.toThrow(
        ProjectAccessDeniedError
      );
      await expect(projectAuthorization.requireDeleteAccess(projectId, req.user.id)).rejects.toThrow(
        ProjectAccessDeniedError
      );
    });

    it('authenticates Bearer token for OUTSIDER: denies all project access with 403', async () => {
      const token = tokenService.createAccessToken({ id: outsiderId, email: 'outsider@test.local' });
      const req = createMockReq({ authorization: `Bearer ${token}` });
      const res = createMockRes();
      const next = jest.fn();

      authenticate(req, res, next);
      expect(next).toHaveBeenCalled();

      await expect(projectAuthorization.requireAccess(projectId, req.user.id)).rejects.toThrow(
        ProjectAccessDeniedError
      );
    });
  });
});
