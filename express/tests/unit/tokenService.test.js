const crypto = require('crypto');
const jwt = require('jsonwebtoken');
const tokenService = require('../../src/services/auth/tokenService');
const { TokenService } = require('../../src/services/auth/tokenService');
const { InvalidTokenError, TokenExpiredError } = require('../../src/errors/authErrors');

const TEST_SECRET = 'stacksense-test-secret-key-that-is-at-least-32-bytes-long-for-jwt-signing';
const TEST_HMAC_KEY = 'stacksense-test-refresh-hmac-key-at-least-32-bytes-long-for-hashing';

describe('TokenService Unit Tests (M5 Batch 1)', () => {
  let customService;

  beforeEach(() => {
    customService = new TokenService({
      jwtSecret: TEST_SECRET,
      refreshTokenHmacKey: TEST_HMAC_KEY,
      expirationMinutes: 60,
      refreshTokenExpireDays: 30,
    });
  });

  describe('Access Token Issuance & Verification', () => {
    it('creates and verifies access token with canonical sub claim and 3600s lifetime', () => {
      const userId = crypto.randomUUID();
      const user = {
        id: userId,
        email: 'tokenservice@stacksense.local',
      };

      const token = customService.createAccessToken(user);
      expect(typeof token).toBe('string');
      expect(token.split('.').length).toBe(3);

      const payload = customService.verifyToken(token);
      expect(payload.sub).toBe(userId);
      expect(payload.userId).toBe(userId);
      expect(payload.user_id).toBe(userId);
      expect(payload.email).toBe('tokenservice@stacksense.local');
      expect(payload.tokenId).toBeDefined();
      expect(payload.tokenType).toBe('access');
      expect(payload.issuedAt).toBeInstanceOf(Date);
      expect(payload.expiresAt).toBeInstanceOf(Date);

      // Verify expiration is ~3600 seconds after issued
      const diffSeconds = Math.round((payload.expiresAt.getTime() - payload.issuedAt.getTime()) / 1000);
      expect(diffSeconds).toBe(3600);
    });

    it('rejects expired access token with TokenExpiredError', () => {
      const expiredService = new TokenService({
        jwtSecret: TEST_SECRET,
        refreshTokenHmacKey: TEST_HMAC_KEY,
        expirationMinutes: -5, // Negative expiration creates already-expired token
      });

      const user = { id: crypto.randomUUID(), email: 'expired@stacksense.local' };
      const token = expiredService.createAccessToken(user);

      expect(() => customService.verifyToken(token)).toThrow(TokenExpiredError);
    });

    it('rejects tampered token signature with InvalidTokenError', () => {
      const user = { id: crypto.randomUUID(), email: 'tampered@stacksense.local' };
      const token = customService.createAccessToken(user);

      const parts = token.split('.');
      const tamperedSig = parts[2][0] === 'X' ? 'Y' + parts[2].slice(1) : 'X' + parts[2].slice(1);
      const tamperedToken = `${parts[0]}.${parts[1]}.${tamperedSig}`;

      expect(() => customService.verifyToken(tamperedToken)).toThrow(InvalidTokenError);
    });

    it('rejects token signed with different secret with InvalidTokenError', () => {
      const otherService = new TokenService({
        jwtSecret: 'completely-different-secret-key-at-least-32-chars-long',
        refreshTokenHmacKey: TEST_HMAC_KEY,
      });

      const user = { id: crypto.randomUUID(), email: 'different@stacksense.local' };
      const token = otherService.createAccessToken(user);

      expect(() => customService.verifyToken(token)).toThrow(InvalidTokenError);
    });

    it('rejects malformed token string with InvalidTokenError', () => {
      expect(() => customService.verifyToken('not.a.valid.jwt')).toThrow(InvalidTokenError);
      expect(() => customService.verifyToken('')).toThrow(InvalidTokenError);
      expect(() => customService.verifyToken(null)).toThrow(InvalidTokenError);
    });

    it('rejects token with non-UUID sub claim with InvalidTokenError', () => {
      const payload = {
        sub: 'not-a-valid-uuid',
        email: 'invalidsub@stacksense.local',
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 3600,
        jti: crypto.randomUUID(),
        token_type: 'access',
      };
      const token = jwt.sign(payload, TEST_SECRET, { algorithm: 'HS256' });

      expect(() => customService.verifyToken(token)).toThrow(InvalidTokenError);
      try {
        customService.verifyToken(token);
      } catch (err) {
        expect(err.message).toMatch(/not a valid UUID/);
      }
    });

    it('rejects token with token_type other than access', () => {
      const payload = {
        sub: crypto.randomUUID(),
        email: 'test@stacksense.local',
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 3600,
        jti: crypto.randomUUID(),
        token_type: 'refresh',
      };
      const token = jwt.sign(payload, TEST_SECRET, { algorithm: 'HS256' });

      expect(() => customService.verifyToken(token)).toThrow(InvalidTokenError);
    });
  });

  describe('Refresh Token Generation & HMAC Hashing', () => {
    it('generates cryptographically secure refresh token and deterministic hash', () => {
      const user = { id: crypto.randomUUID(), email: 'refresh@stacksense.local' };
      const { rawToken, tokenHash, expiresAt } = customService.createRefreshToken(user);

      expect(typeof rawToken).toBe('string');
      expect(rawToken.length).toBeGreaterThan(20);
      expect(tokenHash).toBe(customService.hashRefreshToken(rawToken));
      expect(expiresAt).toBeInstanceOf(Date);
      expect(expiresAt.getTime()).toBeGreaterThan(Date.now());

      // Supports array destructuring as well
      const [token1, hash1, exp1] = customService.createRefreshToken(user);
      expect(typeof token1).toBe('string');
      expect(hash1).toBe(customService.hashRefreshToken(token1));
      expect(exp1).toBeInstanceOf(Date);
    });

    it('enforces that HMAC-SHA256 is keyed and distinct from unkeyed SHA-256', () => {
      const rawToken = 'test-refresh-token-value-string';
      const tokenHash = customService.hashRefreshToken(rawToken);
      const legacyHash = customService.legacyHashRefreshToken(rawToken);

      expect(tokenHash).not.toBe(legacyHash);
    });

    it('produces different hashes for different secret keys and identical legacy hashes', () => {
      const rawToken = 'test-refresh-token-value-string';
      const altService = new TokenService({
        jwtSecret: TEST_SECRET,
        refreshTokenHmacKey: 'an-alternative-refresh-hmac-key-at-least-32-bytes',
      });

      expect(altService.hashRefreshToken(rawToken)).not.toBe(customService.hashRefreshToken(rawToken));
      expect(altService.legacyHashRefreshToken(rawToken)).toBe(customService.legacyHashRefreshToken(rawToken));
    });
  });
});
