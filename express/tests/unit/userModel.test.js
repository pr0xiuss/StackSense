const User = require('../../src/models/User');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe('User Model Unit Tests (M5 Batch 1)', () => {
  beforeEach(async () => {
    await User.deleteMany({});
  });

  describe('Schema Validation and Defaults', () => {
    it('creates a user with valid fields and generates UUID v4 id', async () => {
      const user = new User({
        email: 'developer@stacksense.local',
        username: 'dev_user',
        password_hash: '$2b$12$somevalidhashstringforbcryptpassword',
      });

      await user.save();

      expect(user._id).toBeDefined();
      expect(user._id).toMatch(UUID_V4_REGEX);
      expect(user.email).toBe('developer@stacksense.local');
      expect(user.username).toBe('dev_user');
      expect(user.is_active).toBe(true);
      expect(user.created_at).toBeInstanceOf(Date);
      expect(user.updated_at).toBeInstanceOf(Date);
    });

    it('normalizes email and username to lowercase and trims whitespace', async () => {
      const user = new User({
        email: '  ALICE.SMITH@EXAMPLE.COM  ',
        username: '  Alice_99  ',
        password_hash: '$2b$12$dummyhash',
      });

      await user.save();

      expect(user.email).toBe('alice.smith@example.com');
      expect(user.username).toBe('alice_99');
    });

    it('rejects creation when email is missing or empty', async () => {
      const userMissing = new User({
        username: 'valid_user',
        password_hash: '$2b$12$dummyhash',
      });
      await expect(userMissing.save()).rejects.toThrow();

      const userEmpty = new User({
        email: '   ',
        username: 'valid_user',
        password_hash: '$2b$12$dummyhash',
      });
      await expect(userEmpty.save()).rejects.toThrow();
    });

    it('rejects creation when username is missing', async () => {
      const user = new User({
        email: 'user@example.com',
        password_hash: '$2b$12$dummyhash',
      });
      await expect(user.save()).rejects.toThrow();
    });

    it('rejects username shorter than 3 characters', async () => {
      const user = new User({
        email: 'user@example.com',
        username: 'ab',
        password_hash: '$2b$12$dummyhash',
      });
      await expect(user.save()).rejects.toThrow(/between 3 and 30 characters/);
    });

    it('rejects username longer than 30 characters', async () => {
      const user = new User({
        email: 'user@example.com',
        username: 'a'.repeat(31),
        password_hash: '$2b$12$dummyhash',
      });
      await expect(user.save()).rejects.toThrow(/between 3 and 30 characters/);
    });

    it('rejects username with invalid characters (e.g. hyphen or spaces)', async () => {
      const userHyphen = new User({
        email: 'user1@example.com',
        username: 'bad-username',
        password_hash: '$2b$12$dummyhash',
      });
      await expect(userHyphen.save()).rejects.toThrow();

      const userSpecial = new User({
        email: 'user2@example.com',
        username: 'bad@user',
        password_hash: '$2b$12$dummyhash',
      });
      await expect(userSpecial.save()).rejects.toThrow();
    });

    it('rejects creation when password_hash is missing', async () => {
      const user = new User({
        email: 'user@example.com',
        username: 'valid_user',
      });
      await expect(user.save()).rejects.toThrow();
    });
  });

  describe('Security and JSON Serialization', () => {
    it('does not include password_hash in default queries', async () => {
      const user = await User.create({
        email: 'hidden@example.com',
        username: 'hidden_user',
        password_hash: '$2b$12$secretpasswordhash',
      });

      const queried = await User.findById(user._id);
      expect(queried.password_hash).toBeUndefined();

      // Explicit selection includes it
      const queriedWithPassword = await User.findById(user._id).select('+password_hash');
      expect(queriedWithPassword.password_hash).toBe('$2b$12$secretpasswordhash');
    });

    it('serializes to JSON exposing id and stripping _id and password_hash', async () => {
      const user = await User.create({
        email: 'serialize@example.com',
        username: 'serialize_user',
        password_hash: '$2b$12$secretpasswordhash',
      });

      const userWithHash = await User.findById(user._id).select('+password_hash');
      const json = userWithHash.toJSON();

      expect(json.id).toBe(user._id);
      expect(json._id).toBeUndefined();
      expect(json.password_hash).toBeUndefined();
      expect(json.email).toBe('serialize@example.com');
      expect(json.username).toBe('serialize_user');
      expect(json.is_active).toBe(true);
    });
  });

  describe('Unique Indexes', () => {
    it('enforces uniqueness on email', async () => {
      await User.syncIndexes();

      await User.create({
        email: 'unique@example.com',
        username: 'user_one',
        password_hash: '$2b$12$hash1',
      });

      await expect(
        User.create({
          email: 'unique@example.com',
          username: 'user_two',
          password_hash: '$2b$12$hash2',
        })
      ).rejects.toThrow();
    });

    it('enforces uniqueness on username', async () => {
      await User.syncIndexes();

      await User.create({
        email: 'first@example.com',
        username: 'same_username',
        password_hash: '$2b$12$hash1',
      });

      await expect(
        User.create({
          email: 'second@example.com',
          username: 'same_username',
          password_hash: '$2b$12$hash2',
        })
      ).rejects.toThrow();
    });
  });
});
