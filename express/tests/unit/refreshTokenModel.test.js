const crypto = require('crypto');
const RefreshToken = require('../../src/models/RefreshToken');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe('RefreshToken Model Unit Tests (M5 Batch 1)', () => {
  beforeEach(async () => {
    await RefreshToken.deleteMany({});
  });

  describe('Schema Validation and Defaults', () => {
    it('creates a refresh token with valid fields and defaults', async () => {
      const userId = crypto.randomUUID();
      const expiresAt = new Date(Date.now() + 30 * 86400 * 1000);

      const token = new RefreshToken({
        user_id: userId,
        token_hash: 'a'.repeat(64),
        expires_at: expiresAt,
      });

      await token.save();

      expect(token._id).toBeDefined();
      expect(token._id).toMatch(UUID_V4_REGEX);
      expect(token.user_id).toBe(userId);
      expect(token.token_hash).toBe('a'.repeat(64));
      expect(token.expires_at).toEqual(expiresAt);
      expect(token.revoked_at).toBeNull();
      expect(token.replaced_by_token_id).toBeNull();
      expect(token.created_at).toBeInstanceOf(Date);
      expect(token.updated_at).toBeInstanceOf(Date);
    });

    it('rejects invalid UUID v4 for user_id', async () => {
      const token = new RefreshToken({
        user_id: 'invalid-uuid',
        token_hash: 'hash123',
        expires_at: new Date(Date.now() + 10000),
      });

      await expect(token.save()).rejects.toThrow();
    });

    it('rejects missing token_hash', async () => {
      const token = new RefreshToken({
        user_id: crypto.randomUUID(),
        expires_at: new Date(Date.now() + 10000),
      });

      await expect(token.save()).rejects.toThrow();
    });

    it('rejects invalid replaced_by_token_id', async () => {
      const token = new RefreshToken({
        user_id: crypto.randomUUID(),
        token_hash: 'hash123',
        expires_at: new Date(Date.now() + 10000),
        replaced_by_token_id: 'non-uuid-string',
      });

      await expect(token.save()).rejects.toThrow(/replaced_by_token_id must be a valid UUID v4/);
    });

    it('accepts valid UUID v4 replaced_by_token_id', async () => {
      const replacementId = crypto.randomUUID();
      const token = new RefreshToken({
        user_id: crypto.randomUUID(),
        token_hash: 'hash123',
        expires_at: new Date(Date.now() + 10000),
        replaced_by_token_id: replacementId,
      });

      await token.save();
      expect(token.replaced_by_token_id).toBe(replacementId);
    });
  });

  describe('Status Helper Properties (Virtuals)', () => {
    it('evaluates active state correctly for unexpired, unrevoked token', () => {
      const token = new RefreshToken({
        user_id: crypto.randomUUID(),
        token_hash: 'active_hash',
        expires_at: new Date(Date.now() + 3600 * 1000),
        revoked_at: null,
      });

      expect(token.isActive).toBe(true);
      expect(token.is_active).toBe(true);
      expect(token.isExpired).toBe(false);
      expect(token.is_expired).toBe(false);
      expect(token.isRevoked).toBe(false);
      expect(token.is_revoked).toBe(false);
    });

    it('evaluates expired state correctly when expires_at is in the past', () => {
      const token = new RefreshToken({
        user_id: crypto.randomUUID(),
        token_hash: 'expired_hash',
        expires_at: new Date(Date.now() - 3600 * 1000),
        revoked_at: null,
      });

      expect(token.isActive).toBe(false);
      expect(token.is_active).toBe(false);
      expect(token.isExpired).toBe(true);
      expect(token.is_expired).toBe(true);
      expect(token.isRevoked).toBe(false);
      expect(token.is_revoked).toBe(false);
    });

    it('evaluates revoked state correctly when revoked_at is set', () => {
      const token = new RefreshToken({
        user_id: crypto.randomUUID(),
        token_hash: 'revoked_hash',
        expires_at: new Date(Date.now() + 3600 * 1000),
        revoked_at: new Date(),
      });

      expect(token.isActive).toBe(false);
      expect(token.is_active).toBe(false);
      expect(token.isExpired).toBe(false);
      expect(token.is_expired).toBe(false);
      expect(token.isRevoked).toBe(true);
      expect(token.is_revoked).toBe(true);
    });
  });

  describe('JSON Serialization and Indexing', () => {
    it('serializes to JSON with id instead of _id', async () => {
      const token = await RefreshToken.create({
        user_id: crypto.randomUUID(),
        token_hash: 'serialize_hash',
        expires_at: new Date(Date.now() + 10000),
      });

      const json = token.toJSON();
      expect(json.id).toBe(token._id);
      expect(json._id).toBeUndefined();
    });

    it('enforces uniqueness on token_hash', async () => {
      await RefreshToken.syncIndexes();

      await RefreshToken.create({
        user_id: crypto.randomUUID(),
        token_hash: 'unique_hash_123',
        expires_at: new Date(Date.now() + 10000),
      });

      await expect(
        RefreshToken.create({
          user_id: crypto.randomUUID(),
          token_hash: 'unique_hash_123',
          expires_at: new Date(Date.now() + 10000),
        })
      ).rejects.toThrow();
    });
  });
});
