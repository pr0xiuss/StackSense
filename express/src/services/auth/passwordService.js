const bcrypt = require('bcryptjs');
const authConfig = require('../../config/authConfig');
const { PasswordPolicyError } = require('../../errors/authErrors');

const MIN_PASSWORD_LENGTH = 8;
const MAX_PASSWORD_LENGTH = 128;
const MAX_PASSWORD_BYTES = 72;

const DUMMY_HASH_PROD = '$2b$12$7kQeGj9P.3uW/W0oD0k9ve8yqCj0Z7WzB2H5tJ1aL3mN6oP9qRsTu';
const DUMMY_HASH_TEST = '$2b$04$8N74NNsEP2zYNWyYRNBcAeeL/G3yscTOqKyolFNRchBf357a1eRKC';

class PasswordService {
  constructor(defaultRounds = authConfig.bcryptRounds) {
    this.defaultRounds = defaultRounds;
  }

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

  async hash(password, rounds = this.defaultRounds) {
    this.validate(password);
    const salt = await bcrypt.genSalt(rounds);
    return bcrypt.hash(password, salt);
  }

  async verify(password, passwordHash) {
    if (!password || !passwordHash || typeof password !== 'string' || typeof passwordHash !== 'string') {
      return false;
    }
    if (Buffer.byteLength(password, 'utf8') > MAX_PASSWORD_BYTES) {
      return false;
    }
    try {
      return await bcrypt.compare(password, passwordHash);
    } catch (_) {
      return false;
    }
  }

  async dummyVerify(password = 'dummy-password') {
    const dummyHash = process.env.NODE_ENV === 'test' ? DUMMY_HASH_TEST : DUMMY_HASH_PROD;
    try {
      await bcrypt.compare(password || 'dummy-password', dummyHash);
    } catch (_) {
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
