const crypto = require('crypto');
const request = require('supertest');
const express = require('express');
const mongoose = require('mongoose');
const authRoutes = require('../../src/routes/authRoutes');
const errorHandler = require('../../src/middleware/errorHandler');
const authenticate = require('../../src/middleware/authenticate');
const User = require('../../src/models/User');
const RefreshToken = require('../../src/models/RefreshToken');
const passwordService = require('../../src/services/auth/passwordService');
const tokenService = require('../../src/services/auth/tokenService');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

// Create test app with auth routes
function createTestApp() {
  const app = express();
  app.use(express.json());
  app.use('/api/v1/auth', authRoutes);
  app.use(errorHandler);
  return app;
}

describe('Auth API Integration Tests (M5 Batch 2)', () => {
  let app;
  let testUser;

  beforeAll(() => {
    app = createTestApp();
  });

  beforeEach(async () => {
    await User.deleteMany({});
    await RefreshToken.deleteMany({});

    // Create a test user for login tests
    const passwordHash = await passwordService.hash('ValidPass123');
    testUser = await User.create({
      email: 'testuser@example.com',
      username: 'testuser',
      password_hash: passwordHash,
      is_active: true,
    });
  });

  describe('POST /api/v1/auth/register', () => {
    it('registers a new user successfully and returns 201', async () => {
      const response = await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'newuser@example.com',
          username: 'newuser',
          password: 'ValidPass123',
        })
        .expect(201);

      expect(response.body.user).toBeDefined();
      expect(response.body.user.id).toMatch(UUID_V4_REGEX);
      expect(response.body.user.email).toBe('newuser@example.com');
      expect(response.body.user.username).toBe('newuser');
      expect(response.body.user.password_hash).toBeUndefined();
      expect(response.body.message).toBe('User registered successfully.');
    });

    it('normalizes email and username to lowercase and trims whitespace', async () => {
      const response = await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: '  NEWUSER@EXAMPLE.COM  ',
          username: '  New_User  ',
          password: 'ValidPass123',
        })
        .expect(201);

      expect(response.body.user.email).toBe('newuser@example.com');
      expect(response.body.user.username).toBe('new_user');
    });

    it('returns 409 user_already_exists for duplicate email', async () => {
      await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'duplicate@example.com',
          username: 'userone',
          password: 'ValidPass123',
        })
        .expect(201);

      const response = await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'duplicate@example.com',
          username: 'usertwo',
          password: 'ValidPass123',
        })
        .expect(409);

      expect(response.body.error.code).toBe('user_already_exists');
    });

    it('returns 409 username_already_exists for duplicate username', async () => {
      await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'userone@example.com',
          username: 'duplicateuser',
          password: 'ValidPass123',
        })
        .expect(201);

      const response = await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'usertwo@example.com',
          username: 'duplicateuser',
          password: 'ValidPass123',
        })
        .expect(409);

      expect(response.body.error.code).toBe('username_already_exists');
    });

    it('CONCURRENT REGISTRATION: handles simultaneous duplicate email registrations (exactly one 201, one 409)', async () => {
      await User.syncIndexes();
      const payload1 = {
        email: 'race_email@example.com',
        username: 'race_user_1',
        password: 'ValidPassword123',
      };
      const payload2 = {
        email: 'race_email@example.com',
        username: 'race_user_2',
        password: 'ValidPassword123',
      };

      const [res1, res2] = await Promise.all([
        request(app).post('/api/v1/auth/register').send(payload1),
        request(app).post('/api/v1/auth/register').send(payload2),
      ]);

      const statuses = [res1.status, res2.status].sort();
      expect(statuses).toEqual([201, 409]);

      const conflictRes = res1.status === 409 ? res1 : res2;
      expect(conflictRes.body.error.code).toBe('user_already_exists');
    });

    it('CONCURRENT REGISTRATION: handles simultaneous duplicate username registrations (exactly one 201, one 409)', async () => {
      await User.syncIndexes();
      const payload1 = {
        email: 'race_user1@example.com',
        username: 'race_username',
        password: 'ValidPassword123',
      };
      const payload2 = {
        email: 'race_user2@example.com',
        username: 'race_username',
        password: 'ValidPassword123',
      };

      const [res1, res2] = await Promise.all([
        request(app).post('/api/v1/auth/register').send(payload1),
        request(app).post('/api/v1/auth/register').send(payload2),
      ]);

      const statuses = [res1.status, res2.status].sort();
      expect(statuses).toEqual([201, 409]);

      const conflictRes = res1.status === 409 ? res1 : res2;
      expect(conflictRes.body.error.code).toBe('username_already_exists');
    });

    it('returns 422 when email is missing', async () => {
      const response = await request(app)
        .post('/api/v1/auth/register')
        .send({
          username: 'newuser',
          password: 'ValidPass123',
        })
        .expect(422);

      expect(response.body.error.code).toBe('validation_error');
      expect(response.body.error.details.field).toBe('email');
    });

    it('returns 422 when username is missing', async () => {
      const response = await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'newuser@example.com',
          password: 'ValidPass123',
        })
        .expect(422);

      expect(response.body.error.code).toBe('validation_error');
      expect(response.body.error.details.field).toBe('username');
    });

    it('returns 422 when password is missing', async () => {
      const response = await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'newuser@example.com',
          username: 'newuser',
        })
        .expect(422);

      expect(response.body.error.code).toBe('validation_error');
      expect(response.body.error.details.field).toBe('password');
    });

    it('returns 422 when password is shorter than 8 characters', async () => {
      const response = await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'newuser@example.com',
          username: 'newuser',
          password: 'Short1',
        })
        .expect(422);

      expect(response.body.error.code).toBe('validation_error');
      expect(response.body.error.details.field).toBe('password');
    });

    it('returns 422 when password exceeds 128 characters', async () => {
      const response = await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'newuser@example.com',
          username: 'newuser',
          password: 'A'.repeat(129),
        })
        .expect(422);

      expect(response.body.error.code).toBe('validation_error');
      expect(response.body.error.details.field).toBe('password');
    });

    it('returns 422 when username has invalid characters', async () => {
      const response = await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'newuser@example.com',
          username: 'invalid-user',
          password: 'ValidPass123',
        })
        .expect(422);

      expect(response.body.error.code).toBe('validation_error');
      expect(response.body.error.details.field).toBe('username');
    });

    it('returns 422 when email format is invalid', async () => {
      const response = await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'not-an-email',
          username: 'newuser',
          password: 'ValidPass123',
        })
        .expect(422);

      expect(response.body.error.code).toBe('validation_error');
      expect(response.body.error.details.field).toBe('email');
    });
  });

  describe('POST /api/v1/auth/login', () => {
    it('authenticates with email and returns tokens', async () => {
      const response = await request(app)
        .post('/api/v1/auth/login')
        .send({
          identifier: 'testuser@example.com',
          password: 'ValidPass123',
        })
        .expect(200);

      expect(response.body.access_token).toBeDefined();
      expect(response.body.refresh_token).toBeDefined();
      expect(response.body.token_type).toBe('Bearer');
      expect(response.body.expires_in).toBe(3600);
      expect(response.body.refresh_expires_in).toBe(2592000);
      expect(response.body.user.id).toBe(testUser.id);
      expect(response.body.user.email).toBe('testuser@example.com');
      expect(response.body.user.username).toBe('testuser');
    });

    it('authenticates with username and returns tokens', async () => {
      const response = await request(app)
        .post('/api/v1/auth/login')
        .send({
          identifier: 'testuser',
          password: 'ValidPass123',
        })
        .expect(200);

      expect(response.body.access_token).toBeDefined();
      expect(response.body.refresh_token).toBeDefined();
      expect(response.body.user.username).toBe('testuser');
    });

    it('returns 401 invalid_credentials for wrong password', async () => {
      const response = await request(app)
        .post('/api/v1/auth/login')
        .send({
          identifier: 'testuser@example.com',
          password: 'WrongPassword123',
        })
        .expect(401);

      expect(response.body.error.code).toBe('invalid_credentials');
    });

    it('returns 401 invalid_credentials for nonexistent user (timing-safe)', async () => {
      const response = await request(app)
        .post('/api/v1/auth/login')
        .send({
          identifier: 'nonexistent@example.com',
          password: 'ValidPass123',
        })
        .expect(401);

      expect(response.body.error.code).toBe('invalid_credentials');
    });

    it('returns 403 user_inactive for inactive account', async () => {
      await User.findByIdAndUpdate(testUser.id, { is_active: false });

      const response = await request(app)
        .post('/api/v1/auth/login')
        .send({
          identifier: 'testuser@example.com',
          password: 'ValidPass123',
        })
        .expect(403);

      expect(response.body.error.code).toBe('user_inactive');
    });

    it('returns 422 when identifier is missing', async () => {
      const response = await request(app)
        .post('/api/v1/auth/login')
        .send({
          password: 'ValidPass123',
        })
        .expect(422);

      expect(response.body.error.code).toBe('validation_error');
      expect(response.body.error.details.field).toBe('identifier');
    });

    it('returns 422 when password is missing', async () => {
      const response = await request(app)
        .post('/api/v1/auth/login')
        .send({
          identifier: 'testuser@example.com',
        })
        .expect(422);

      expect(response.body.error.code).toBe('validation_error');
      expect(response.body.error.details.field).toBe('password');
    });
  });

  describe('POST /api/v1/auth/refresh', () => {
    let refreshToken;

    beforeEach(async () => {
      // Login to get a refresh token
      const loginResponse = await request(app)
        .post('/api/v1/auth/login')
        .send({
          identifier: 'testuser@example.com',
          password: 'ValidPass123',
        });
      refreshToken = loginResponse.body.refresh_token;
    });

    it('refreshes tokens successfully and returns new token pair', async () => {
      const response = await request(app)
        .post('/api/v1/auth/refresh')
        .send({ refresh_token: refreshToken })
        .expect(200);

      expect(response.body.access_token).toBeDefined();
      expect(response.body.refresh_token).toBeDefined();
      expect(response.body.refresh_token).not.toBe(refreshToken); // Token rotated
      expect(response.body.token_type).toBe('Bearer');
      expect(response.body.expires_in).toBe(3600);
      expect(response.body.refresh_expires_in).toBe(2592000);
      expect(response.body.user.id).toBe(testUser.id);
    });

    it('returns 401 invalid_refresh_token for nonexistent token', async () => {
      const fakeToken = crypto.randomBytes(32).toString('base64url');

      const response = await request(app)
        .post('/api/v1/auth/refresh')
        .send({ refresh_token: fakeToken })
        .expect(401);

      expect(response.body.error.code).toBe('invalid_refresh_token');
    });

    it('returns 401 refresh_token_revoked for already used token (replay attack)', async () => {
      // First refresh - should succeed
      await request(app)
        .post('/api/v1/auth/refresh')
        .send({ refresh_token: refreshToken })
        .expect(200);

      // Second refresh with same token - should fail with revoked
      const response = await request(app)
        .post('/api/v1/auth/refresh')
        .send({ refresh_token: refreshToken })
        .expect(401);

      expect(response.body.error.code).toBe('refresh_token_revoked');
    });

    it('returns 401 refresh_token_expired for expired token', async () => {
      // Create an expired refresh token directly in DB
      const expiredTokenHash = tokenService.hashRefreshToken('expired-token-raw');
      await RefreshToken.create({
        user_id: testUser.id,
        token_hash: expiredTokenHash,
        expires_at: new Date(Date.now() - 1000), // Expired 1 second ago
        revoked_at: null,
      });

      const response = await request(app)
        .post('/api/v1/auth/refresh')
        .send({ refresh_token: 'expired-token-raw' })
        .expect(401);

      expect(response.body.error.code).toBe('refresh_token_expired');
    });

    it('returns 422 when refresh_token is missing', async () => {
      const response = await request(app)
        .post('/api/v1/auth/refresh')
        .send({})
        .expect(422);

      expect(response.body.error.code).toBe('validation_error');
      expect(response.body.error.details.field).toBe('refresh_token');
    });

    it('CONCURRENT ROTATION: exactly ONE succeeds when two simultaneous requests use same token', async () => {
      // Fire two simultaneous refresh requests against the same refresh token
      const [result1, result2] = await Promise.all([
        request(app).post('/api/v1/auth/refresh').send({ refresh_token: refreshToken }),
        request(app).post('/api/v1/auth/refresh').send({ refresh_token: refreshToken }),
      ]);

      const statuses = [result1.status, result2.status].sort();
      expect(statuses).toEqual([200, 401]);

      // Find which one succeeded and which failed
      const success = statuses[0] === 200 ? result1 : result2;
      const failure = statuses[0] === 200 ? result2 : result1;

      expect(success.status).toBe(200);
      expect(success.body.access_token).toBeDefined();
      expect(success.body.refresh_token).toBeDefined();

      expect(failure.status).toBe(401);
      expect(failure.body.error.code).toBe('refresh_token_revoked');
    });
  });

  describe('POST /api/v1/auth/logout', () => {
    it('revokes refresh token and returns 204', async () => {
      const loginResponse = await request(app)
        .post('/api/v1/auth/login')
        .send({
          identifier: 'testuser@example.com',
          password: 'ValidPass123',
        });
      const refreshToken = loginResponse.body.refresh_token;

      await request(app)
        .post('/api/v1/auth/logout')
        .send({ refresh_token: refreshToken })
        .expect(204);

      // Verify token is revoked - attempting to use it should fail
      const response = await request(app)
        .post('/api/v1/auth/refresh')
        .send({ refresh_token: refreshToken })
        .expect(401);

      expect(response.body.error.code).toBe('refresh_token_revoked');
    });

    it('returns 204 even without refresh_token (idempotent)', async () => {
      await request(app)
        .post('/api/v1/auth/logout')
        .send({})
        .expect(204);
    });

    it('returns 204 even with invalid refresh_token (no error)', async () => {
      await request(app)
        .post('/api/v1/auth/logout')
        .send({ refresh_token: 'invalid-token' })
        .expect(204);
    });
  });

  describe('GET /api/v1/auth/me', () => {
    let accessToken;

    beforeEach(async () => {
      const loginResponse = await request(app)
        .post('/api/v1/auth/login')
        .send({
          identifier: 'testuser@example.com',
          password: 'ValidPass123',
        });
      accessToken = loginResponse.body.access_token;
    });

    it('returns current user profile with valid Bearer token', async () => {
      const response = await request(app)
        .get('/api/v1/auth/me')
        .set('Authorization', `Bearer ${accessToken}`)
        .expect(200);

      expect(response.body.id).toBe(testUser.id);
      expect(response.body.email).toBe('testuser@example.com');
      expect(response.body.username).toBe('testuser');
      expect(response.body.password_hash).toBeUndefined();
    });

    it('returns 401 authentication_required without token', async () => {
      const response = await request(app)
        .get('/api/v1/auth/me')
        .expect(401);

      expect(response.body.error.code).toBe('authentication_required');
    });

    it('returns 401 invalid_token for malformed token', async () => {
      const response = await request(app)
        .get('/api/v1/auth/me')
        .set('Authorization', 'Bearer not-a-valid-jwt')
        .expect(401);

      expect(response.body.error.code).toBe('invalid_token');
    });

    it('returns 401 token_expired for expired access token', async () => {
      // Create an expired access token
      const expiredToken = tokenService.createAccessToken({
        id: testUser.id,
        email: testUser.email,
      });
      // Manually create an expired token by using a past timestamp
      const jwt = require('jsonwebtoken');
      const authConfig = require('../../src/config/authConfig');
      const pastPayload = {
        sub: testUser.id,
        email: testUser.email,
        iat: Math.floor(Date.now() / 1000) - 7200,
        exp: Math.floor(Date.now() / 1000) - 3600,
        jti: crypto.randomUUID(),
        token_type: 'access',
      };
      const expiredAccessToken = jwt.sign(pastPayload, authConfig.jwtSecret, {
        algorithm: 'HS256',
      });

      const response = await request(app)
        .get('/api/v1/auth/me')
        .set('Authorization', `Bearer ${expiredAccessToken}`)
        .expect(401);

      expect(response.body.error.code).toBe('token_expired');
    });
  });

  describe('Full authentication flow', () => {
    it('completes register -> login -> refresh -> me -> logout', async () => {
      // 1. Register
      const registerResponse = await request(app)
        .post('/api/v1/auth/register')
        .send({
          email: 'flowuser@example.com',
          username: 'flowuser',
          password: 'ValidPass123',
        })
        .expect(201);

      const userId = registerResponse.body.user.id;

      // 2. Login
      const loginResponse = await request(app)
        .post('/api/v1/auth/login')
        .send({
          identifier: 'flowuser@example.com',
          password: 'ValidPass123',
        })
        .expect(200);

      const { access_token, refresh_token } = loginResponse.body;

      // 3. Access /me with access token
      const meResponse = await request(app)
        .get('/api/v1/auth/me')
        .set('Authorization', `Bearer ${access_token}`)
        .expect(200);

      expect(meResponse.body.id).toBe(userId);

      // 4. Refresh tokens
      const refreshResponse = await request(app)
        .post('/api/v1/auth/refresh')
        .send({ refresh_token })
        .expect(200);

      const newAccessToken = refreshResponse.body.access_token;
      const newRefreshToken = refreshResponse.body.refresh_token;

      // 5. Access /me with new access token
      await request(app)
        .get('/api/v1/auth/me')
        .set('Authorization', `Bearer ${newAccessToken}`)
        .expect(200);

      // 6. Logout with new refresh token
      await request(app)
        .post('/api/v1/auth/logout')
        .send({ refresh_token: newRefreshToken })
        .expect(204);

      // 7. Verify old refresh token is revoked
      await request(app)
        .post('/api/v1/auth/refresh')
        .send({ refresh_token: newRefreshToken })
        .expect(401);
    });
  });
});