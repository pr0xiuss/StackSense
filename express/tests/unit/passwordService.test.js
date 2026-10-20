const passwordService = require('../../src/services/auth/passwordService');
const { PasswordPolicyError } = require('../../src/errors/authErrors');

describe('PasswordService Unit Tests (M5 Batch 1)', () => {
  describe('Password Policy Validation', () => {
    it('accepts valid passwords between 8 and 72 ASCII characters', () => {
      expect(() => passwordService.validate('ValidPass123')).not.toThrow();
      expect(() => passwordService.validate('12345678')).not.toThrow();
      expect(() => passwordService.validate('a'.repeat(72))).not.toThrow();
    });

    it('rejects passwords shorter than 8 characters with PasswordPolicyError', () => {
      expect(() => passwordService.validate('short')).toThrow(PasswordPolicyError);
      expect(() => passwordService.validate('')).toThrow(PasswordPolicyError);
      expect(() => passwordService.validate('1234567')).toThrow(PasswordPolicyError);
      try {
        passwordService.validate('short');
      } catch (err) {
        expect(err.code).toBe('password_policy_violation');
        expect(err.status).toBe(422);
      }
    });

    it('rejects null, undefined, or non-string passwords with PasswordPolicyError', () => {
      expect(() => passwordService.validate(null)).toThrow(PasswordPolicyError);
      expect(() => passwordService.validate(undefined)).toThrow(PasswordPolicyError);
      expect(() => passwordService.validate(12345678)).toThrow(PasswordPolicyError);
    });

    it('rejects ASCII passwords exceeding 72 bytes without silent truncation', () => {
      const password73 = 'a'.repeat(73);
      expect(password73.length).toBe(73);
      expect(Buffer.byteLength(password73, 'utf8')).toBe(73);

      expect(() => passwordService.validate(password73)).toThrow(PasswordPolicyError);
      try {
        passwordService.validate(password73);
      } catch (err) {
        expect(err.code).toBe('password_policy_violation');
        expect(err.status).toBe(422);
        expect(err.message).toMatch(/exceeds maximum length of 72 UTF-8 bytes/i);
      }
    });

    it('rejects multibyte Unicode passwords exceeding 72 UTF-8 bytes despite character count <= 128', () => {
      // 25 characters of '語' (each 3 bytes in UTF-8 -> 75 bytes total)
      const multibyteOver = '語'.repeat(25);
      expect(multibyteOver.length).toBe(25); // Well within 128 chars!
      expect(Buffer.byteLength(multibyteOver, 'utf8')).toBe(75); // Exceeds 72 bytes!

      expect(() => passwordService.validate(multibyteOver)).toThrow(PasswordPolicyError);
      try {
        passwordService.validate(multibyteOver);
      } catch (err) {
        expect(err.code).toBe('password_policy_violation');
        expect(err.status).toBe(422);
      }
    });

    it('accepts multibyte Unicode passwords within 72 bytes and >= 8 chars', () => {
      // 10 characters of '語' (10 chars, 30 bytes)
      const multibyteValid = '語'.repeat(10);
      expect(multibyteValid.length).toBe(10);
      expect(Buffer.byteLength(multibyteValid, 'utf8')).toBe(30);

      expect(() => passwordService.validate(multibyteValid)).not.toThrow();
    });
  });

  describe('Bcrypt Hashing and Verification', () => {
    it('hashes a valid password using configured bcrypt rounds', async () => {
      const password = 'StrongPassword123';
      const hash = await passwordService.hash(password);

      expect(typeof hash).toBe('string');
      expect(hash.startsWith('$2')).toBe(true);
      expect(hash).not.toBe(password);
    });

    it('generates unique salts and distinct hashes for identical passwords', async () => {
      const password = 'IdenticalPassword123';
      const hash1 = await passwordService.hash(password);
      const hash2 = await passwordService.hash(password);

      expect(hash1).not.toBe(hash2);
      expect(await passwordService.verify(password, hash1)).toBe(true);
      expect(await passwordService.verify(password, hash2)).toBe(true);
    });

    it('verifies correct password returns true and wrong password returns false', async () => {
      const password = 'CorrectPassword123';
      const hash = await passwordService.hash(password);

      expect(await passwordService.verify(password, hash)).toBe(true);
      expect(await passwordService.verify('WrongPassword123', hash)).toBe(false);
      expect(await passwordService.verify('', hash)).toBe(false);
      expect(await passwordService.verify(null, hash)).toBe(false);
      expect(await passwordService.verify(password, null)).toBe(false);
    });

    it('rejects passwords exceeding 72 bytes during verification without truncation match', async () => {
      const base72 = 'a'.repeat(72);
      const hash = await passwordService.hash(base72);

      // 73 chars starting with same 72 chars
      const over72 = base72 + 'b';
      expect(await passwordService.verify(over72, hash)).toBe(false);
    });
  });

  describe('Constant-Time Dummy Verification', () => {
    it('defines syntactically and cryptographically valid bcrypt dummy hashes', async () => {
      const bcrypt = require('bcryptjs');
      const { DUMMY_HASH_PROD, DUMMY_HASH_TEST } = passwordService;

      // Verify format and rounds
      expect(DUMMY_HASH_PROD).toMatch(/^\$2[ab]\$12\$[./A-Za-z0-9]{53}$/);
      expect(DUMMY_HASH_TEST).toMatch(/^\$2[ab]\$04\$[./A-Za-z0-9]{53}$/);

      // Verify bcrypt can parse and compare against both hashes returning false without error
      const prodResult = await bcrypt.compare('any-password', DUMMY_HASH_PROD);
      expect(prodResult).toBe(false);

      const testResult = await bcrypt.compare('any-password', DUMMY_HASH_TEST);
      expect(testResult).toBe(false);
    });

    it('executes dummy verification without throwing in test and simulated production', async () => {
      await expect(passwordService.dummyVerify('nonexistent-attempt')).resolves.not.toThrow();
      await expect(passwordService.dummyVerify()).resolves.not.toThrow();

      // Test with NODE_ENV = 'production'
      const prevEnv = process.env.NODE_ENV;
      try {
        process.env.NODE_ENV = 'production';
        await expect(passwordService.dummyVerify('nonexistent-attempt')).resolves.not.toThrow();
      } finally {
        process.env.NODE_ENV = prevEnv;
      }
    });
  });
});
