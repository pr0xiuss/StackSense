/**
 * Password Hashing & Verification Service.
 *
 * Implements strict bcrypt password policy:
 * - Length: 8-128 characters.
 * - UTF-8 byte ceiling: max 72 bytes with explicit rejection (no silent truncation).
 * - Constant-time dummy verification against user enumeration.
 */

const bcrypt = require('bcryptjs');
const authConfig = require('../../config/authConfig');
const { PasswordPolicyError } = require('../../errors/authErrors');

const MIN_PASSWORD_LENGTH = 8;
const MAX_PASSWORD_LENGTH = 128;
const MAX_PASSWORD_BYTES = 72;

// Precomputed dummy hashes for constant-time comparison on nonexistent users
const DUMMY_HASH_PROD = '$2b$12$7kQeGj9P.3uW/W0oD0k9ve8yqCj0Z7WzB2H5tJ1aL3mN6oP9qRsTu';
const DUMMY_HASH_TEST = '$2b$04$8N74NNsEP2zYNWyYRNBcAeeL/G3yscTOqKyolFNRchBf357a1eRKC';

class PasswordService {
  constructor(defaultRounds = authConfig.bcryptRounds) {
    this.defaultRounds = defaultRounds;
  }

  /**
   * Validate password string against character length and UTF-8 byte limits.
   * Throws PasswordPolicyError on violation. Never silently truncates.
   *
   * @param {string} password Plaintext password to validate
   */
  validate(password) {
    if (!password || typeof password !== 'string') {
      throw new PasswordPolicyError(
        `Password must be between ${MIN_PASSWORD_LENGTH} and ${MAX_PASSWORD_LENGTH} characters long.`
      );
    }

    if (password.length < MIN_PASSWORD_LENGTH || password.length > MAX_PASSWORD_LENGTH) {
      throw new PasswordPolicyError(
        `Password must be between ${MIN_PASSWORD_LENGTH} and ${MAX_PASSWORD_LENGTH} characters long.`
      );
    }

    const byteLength = Buffer.byteLength(password, 'utf8');
    if (byteLength > MAX_PASSWORD_BYTES) {
      throw new PasswordPolicyError(
        `Password exceeds maximum length of ${MAX_PASSWORD_BYTES} UTF-8 bytes.`
      );
    }
  }

  /**
   * Hash a plaintext password with bcrypt after policy validation.
   *
   * @param {string} password Plaintext password
   * @param {number} [rounds] Optional bcrypt cost factor override
   * @returns {Promise<string>} Generated bcrypt hash
   */
  async hash(password, rounds = this.defaultRounds) {
    this.validate(password);
    const salt = await bcrypt.genSalt(rounds);
    return bcrypt.hash(password, salt);
  }

  /**
   * Verify a plaintext password against a stored bcrypt hash.
   *
   * @param {string} password Plaintext password
   * @param {string} passwordHash Stored bcrypt hash
   * @returns {Promise<boolean>} True if matching, false otherwise
   */
  async verify(password, passwordHash) {
    if (!password || !passwordHash || typeof password !== 'string' || typeof passwordHash !== 'string') {
      return false;
    }
    // Reject immediately if password exceeds 72 UTF-8 bytes to avoid truncation matching
    if (Buffer.byteLength(password, 'utf8') > MAX_PASSWORD_BYTES) {
      return false;
    }
    try {
      return await bcrypt.compare(password, passwordHash);
    } catch (_) {
      return false;
    }
  }

  /**
   * Perform constant-time dummy verification to mitigate timing attacks on nonexistent users.
   *
   * @param {string} [password='dummy-password'] Password to test against dummy hash
   * @returns {Promise<void>}
   */
  async dummyVerify(password = 'dummy-password') {
    const dummyHash = process.env.NODE_ENV === 'test' ? DUMMY_HASH_TEST : DUMMY_HASH_PROD;
    try {
      await bcrypt.compare(password || 'dummy-password', dummyHash);
    } catch (_) {
      // Intentionally swallowed
    }
  }
}

const passwordService = new PasswordService();

module.exports = passwordService;
module.exports.PasswordService = PasswordService;
module.exports.MIN_PASSWORD_LENGTH = MIN_PASSWORD_LENGTH;
module.exports.MAX_PASSWORD_LENGTH = MAX_PASSWORD_LENGTH;
module.exports.MAX_PASSWORD_BYTES = MAX_PASSWORD_BYTES;
module.exports.DUMMY_HASH_PROD = DUMMY_HASH_PROD;
module.exports.DUMMY_HASH_TEST = DUMMY_HASH_TEST;
