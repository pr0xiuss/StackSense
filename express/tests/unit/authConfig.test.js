const authConfig = require('../../src/config/authConfig');

describe('AuthConfig Unit Tests (M5 Batch 1)', () => {
  const { validateAuthConfig } = authConfig;

  describe('Default and Test Mode Configuration', () => {
    it('provides standard token lifetimes and algorithm defaults', () => {
      expect(authConfig.jwtAlgorithm).toBe('HS256');
      expect(authConfig.accessTokenExpireMinutes).toBe(60);
      expect(authConfig.accessTokenExpireSeconds).toBe(3600);
      expect(authConfig.refreshTokenExpireDays).toBe(30);
      expect(authConfig.refreshTokenExpireSeconds).toBe(30 * 86400);
      expect(authConfig.jwtSecret).toBeDefined();
      expect(authConfig.jwtSecret.length).toBeGreaterThanOrEqual(32);
      expect(authConfig.refreshTokenHmacKey).toBeDefined();
      expect(authConfig.refreshTokenHmacKey.length).toBeGreaterThanOrEqual(32);
    });

    it('sets bcrypt rounds to 4 in test environment', () => {
      const config = validateAuthConfig({ NODE_ENV: 'test' });
      expect(config.bcryptRounds).toBe(4);
    });

    it('sets bcrypt rounds to 12 in development/production by default', () => {
      const config = validateAuthConfig({
        NODE_ENV: 'development',
      });
      expect(config.bcryptRounds).toBe(12);
    });

    it('allows custom bcrypt rounds when configured', () => {
      const config = validateAuthConfig({
        NODE_ENV: 'development',
        BCRYPT_ROUNDS: '10',
      });
      expect(config.bcryptRounds).toBe(10);
    });

    it('allows custom token lifetimes when configured', () => {
      const config = validateAuthConfig({
        NODE_ENV: 'development',
        ACCESS_TOKEN_EXPIRE_MINUTES: '15',
        REFRESH_TOKEN_EXPIRE_DAYS: '7',
      });
      expect(config.accessTokenExpireMinutes).toBe(15);
      expect(config.accessTokenExpireSeconds).toBe(900);
      expect(config.refreshTokenExpireDays).toBe(7);
      expect(config.refreshTokenExpireSeconds).toBe(604800);
    });

    it('emits a warning in non-production when exactly one secret is customized', () => {
      const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
      try {
        validateAuthConfig({
          NODE_ENV: 'development',
          JWT_SECRET: '12345678901234567890123456789012_jwt',
        });
        expect(warnSpy).toHaveBeenCalledWith(
          expect.stringContaining('Custom JWT_SECRET is configured but REFRESH_TOKEN_HMAC_KEY is using default dev secret')
        );

        warnSpy.mockClear();
        validateAuthConfig({
          NODE_ENV: 'development',
          REFRESH_TOKEN_HMAC_KEY: '12345678901234567890123456789012_refresh',
        });
        expect(warnSpy).toHaveBeenCalledWith(
          expect.stringContaining('Custom REFRESH_TOKEN_HMAC_KEY is configured but JWT_SECRET is using default dev secret')
        );
      } finally {
        warnSpy.mockRestore();
      }
    });
  });

  describe('Production Runtime Secret Validation', () => {
    const validSecret1 = '12345678901234567890123456789012_jwt';
    const validSecret2 = '12345678901234567890123456789012_refresh';

    it('succeeds in production when valid distinct 32+ char secrets are provided', () => {
      const config = validateAuthConfig({
        NODE_ENV: 'production',
        JWT_SECRET: validSecret1,
        REFRESH_TOKEN_HMAC_KEY: validSecret2,
      });

      expect(config.jwtSecret).toBe(validSecret1);
      expect(config.refreshTokenHmacKey).toBe(validSecret2);
      expect(config.bcryptRounds).toBe(12);
    });

    it('fails in production when JWT_SECRET is missing', () => {
      expect(() => {
        validateAuthConfig({
          NODE_ENV: 'production',
          REFRESH_TOKEN_HMAC_KEY: validSecret2,
        });
      }).toThrow(/JWT_SECRET must be set and at least 32 characters in production/);
    });

    it('fails in production when JWT_SECRET is shorter than 32 characters', () => {
      expect(() => {
        validateAuthConfig({
          NODE_ENV: 'production',
          JWT_SECRET: 'too-short',
          REFRESH_TOKEN_HMAC_KEY: validSecret2,
        });
      }).toThrow(/JWT_SECRET must be set and at least 32 characters in production/);
    });

    it('fails in production when REFRESH_TOKEN_HMAC_KEY is missing', () => {
      expect(() => {
        validateAuthConfig({
          NODE_ENV: 'production',
          JWT_SECRET: validSecret1,
        });
      }).toThrow(/REFRESH_TOKEN_HMAC_KEY must be set and at least 32 characters in production/);
    });

    it('fails in production when REFRESH_TOKEN_HMAC_KEY is shorter than 32 characters', () => {
      expect(() => {
        validateAuthConfig({
          NODE_ENV: 'production',
          JWT_SECRET: validSecret1,
          REFRESH_TOKEN_HMAC_KEY: 'short-hmac-key',
        });
      }).toThrow(/REFRESH_TOKEN_HMAC_KEY must be set and at least 32 characters in production/);
    });

    it('fails in production when JWT_SECRET and REFRESH_TOKEN_HMAC_KEY are identical', () => {
      expect(() => {
        validateAuthConfig({
          NODE_ENV: 'production',
          JWT_SECRET: validSecret1,
          REFRESH_TOKEN_HMAC_KEY: validSecret1,
        });
      }).toThrow(/JWT_SECRET and REFRESH_TOKEN_HMAC_KEY must be distinct in production/);
    });
  });
});
