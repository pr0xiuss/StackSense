const crypto = require('crypto');
const jwt = require('jsonwebtoken');
const authenticate = require('../../src/middleware/authenticate');
const tokenService = require('../../src/services/auth/tokenService');
const authConfig = require('../../src/config/authConfig');
const projectAuthorization = require('../../src/services/projectAuthorization');
const User = require('../../src/models/User');
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
    it('authenticates an active existing user and sources req.user from the user record', async () => {
      await User.create({
        _id: validUuid,
        email: 'current@stacksense.local',
        username: 'current_user',
        password_hash: 'test-password-hash',
      });
      const token = tokenService.createAccessToken({
        id: validUuid,
        email: 'stale-claim@stacksense.local',
      });

      const req = createMockReq({
        authorization: `Bearer ${token}`,
      });
      const res = createMockRes();
      const next = jest.fn();

      await authenticate(req, res, next);

      expect(next).toHaveBeenCalledTimes(1);
      expect(req.user).toBeDefined();
      expect(req.user.id).toBe(validUuid);
      expect(req.user.email).toBe('current@stacksense.local');
      expect(res.status).not.toHaveBeenCalled();
    });

    it('rejects a valid unexpired token when the user is inactive', async () => {
      await User.create({
        _id: validUuid,
        email: 'inactive@stacksense.local',
        username: 'inactive_user',
        password_hash: 'test-password-hash',
        is_active: false,
      });
      const token = tokenService.createAccessToken({ id: validUuid, email: 'inactive@stacksense.local' });
      const req = createMockReq({ authorization: `Bearer ${token}` });
      const res = createMockRes();
      const next = jest.fn();

      await authenticate(req, res, next);

      expect(next).not.toHaveBeenCalled();
      expect(res.status).toHaveBeenCalledWith(403);
      expect(res.json).toHaveBeenCalledWith({
        error: {
          code: 'user_inactive',
          message: 'User account is inactive.',
          details: {},
        },
      });
    });

    it('rejects a valid unexpired token when the user no longer exists', async () => {
      const token = tokenService.createAccessToken({ id: validUuid, email: 'deleted@stacksense.local' });
      const req = createMockReq({ authorization: `Bearer ${token}` });
      const res = createMockRes();
      const next = jest.fn();

      await authenticate(req, res, next);

      expect(next).not.toHaveBeenCalled();
      expect(res.status).toHaveBeenCalledWith(401);
      expect(res.json).toHaveBeenCalledWith({
        error: {
          code: 'invalid_token',
          message: 'User associated with token does not exist.',
          details: {},
        },
      });
    });

    it('returns 401 token_expired when Bearer token has expired', async () => {
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

      await authenticate(req, res, next);

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

    it('returns 401 invalid_token when Bearer token signature is tampered', async () => {
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

      await authenticate(req, res, next);

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

    it('returns 401 invalid_token when the signed token is not an access token', async () => {
      const now = Math.floor(Date.now() / 1000);
      const token = jwt.sign(
        {
          sub: validUuid,
          email: 'refresh@stacksense.local',
          iat: now,
          exp: now + 3600,
          jti: crypto.randomUUID(),
          token_type: 'refresh',
        },
        authConfig.jwtSecret,
        { algorithm: authConfig.jwtAlgorithm }
      );
      const req = createMockReq({ authorization: `Bearer ${token}` });
      const res = createMockRes();
      const next = jest.fn();

      await authenticate(req, res, next);

      expect(next).not.toHaveBeenCalled();
      expect(res.status).toHaveBeenCalledWith(401);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({ code: 'invalid_token' }),
        })
      );
    });

    it('returns 401 invalid_token when authorization header is malformed', async () => {
      const req = createMockReq({
        authorization: 'MalformedHeaderWithoutBearerPrefix',
      });
      const res = createMockRes();
      const next = jest.fn();

      await authenticate(req, res, next);

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
      await User.deleteMany({});

      ownerId = crypto.randomUUID();
      adminId = crypto.randomUUID();
      developerId = crypto.randomUUID();
      viewerId = crypto.randomUUID();
      outsiderId = crypto.randomUUID();

      await User.create([
        { _id: ownerId, email: 'owner@test.local', username: 'owner', password_hash: 'test-hash' },
        { _id: adminId, email: 'admin@test.local', username: 'admin', password_hash: 'test-hash' },
        { _id: developerId, email: 'dev@test.local', username: 'developer', password_hash: 'test-hash' },
        { _id: viewerId, email: 'viewer@test.local', username: 'viewer', password_hash: 'test-hash' },
        { _id: outsiderId, email: 'outsider@test.local', username: 'outsider', password_hash: 'test-hash' },
      ]);

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

      await authenticate(req, res, next);
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

      await authenticate(req, res, next);
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

      await authenticate(req, res, next);
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

      await authenticate(req, res, next);
      expect(next).toHaveBeenCalled();

      await expect(projectAuthorization.requireAccess(projectId, req.user.id)).rejects.toThrow(
        ProjectAccessDeniedError
      );
    });
  });
});
