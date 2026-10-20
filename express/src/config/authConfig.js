/**
 * Authentication and Cryptographic Configuration.
 * 
 * Enforces strict secret length and separation in production environments.
 * Provides token lifetimes (access: 60m, refresh: 30d) and bcrypt rounds
 * with exact parity to Python reference platform config.
 */

const DEFAULT_DEV_JWT_SECRET = 'stacksense-dev-jwt-secret-key-at-least-32-chars-long';
const DEFAULT_DEV_REFRESH_HMAC_KEY = 'stacksense-dev-refresh-hmac-key-at-least-32-chars-long';

function validateAuthConfig(env = process.env) {
  const isProduction = env.NODE_ENV === 'production';
  const jwtSecret = env.JWT_SECRET || (isProduction ? '' : DEFAULT_DEV_JWT_SECRET);
  const refreshTokenHmacKey = env.REFRESH_TOKEN_HMAC_KEY || (isProduction ? '' : DEFAULT_DEV_REFRESH_HMAC_KEY);

  if (isProduction) {
    if (!jwtSecret || jwtSecret.length < 32) {
      throw new Error('JWT_SECRET must be set and at least 32 characters in production.');
    }
    if (!refreshTokenHmacKey || refreshTokenHmacKey.length < 32) {
      throw new Error('REFRESH_TOKEN_HMAC_KEY must be set and at least 32 characters in production.');
    }
    if (jwtSecret === refreshTokenHmacKey) {
      throw new Error('JWT_SECRET and REFRESH_TOKEN_HMAC_KEY must be distinct in production.');
    }
  } else {
    if (env.JWT_SECRET && env.JWT_SECRET.length < 32) {
      throw new Error('JWT_SECRET must be at least 32 characters.');
    }
    if (env.REFRESH_TOKEN_HMAC_KEY && env.REFRESH_TOKEN_HMAC_KEY.length < 32) {
      throw new Error('REFRESH_TOKEN_HMAC_KEY must be at least 32 characters.');
    }
    if (env.NODE_ENV !== 'test') {
      if (env.JWT_SECRET && !env.REFRESH_TOKEN_HMAC_KEY) {
        console.warn(
          '[AuthConfig] Warning: Custom JWT_SECRET is configured but REFRESH_TOKEN_HMAC_KEY is using default dev secret.'
        );
      } else if (!env.JWT_SECRET && env.REFRESH_TOKEN_HMAC_KEY) {
        console.warn(
          '[AuthConfig] Warning: Custom REFRESH_TOKEN_HMAC_KEY is configured but JWT_SECRET is using default dev secret.'
        );
      }
    }
  }

  const bcryptRounds = env.NODE_ENV === 'test' ? 4 : (parseInt(env.BCRYPT_ROUNDS, 10) || 12);
  const accessTokenExpireMinutes = parseInt(env.ACCESS_TOKEN_EXPIRE_MINUTES, 10) || 60;
  const refreshTokenExpireDays = parseInt(env.REFRESH_TOKEN_EXPIRE_DAYS, 10) || 30;

  return {
    jwtSecret,
    jwtAlgorithm: env.JWT_ALGORITHM || 'HS256',
    refreshTokenHmacKey,
    accessTokenExpireMinutes,
    accessTokenExpireSeconds: accessTokenExpireMinutes * 60,
    refreshTokenExpireDays,
    refreshTokenExpireSeconds: refreshTokenExpireDays * 86400,
    bcryptRounds,
    validateAuthConfig,
  };
}

const currentConfig = validateAuthConfig(process.env);

module.exports = currentConfig;
