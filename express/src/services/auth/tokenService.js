/**
 * JWT and Refresh Token Infrastructure Service.
 *
 * Implements:
 * - Access token generation (HS256 JWT, claims: sub, email, iat, exp, jti, token_type: "access")
 * - Access token verification with sub UUID v4 validation and standard error mapping
 * - Refresh token generation (crypto.randomBytes(32).toString('base64url'))
 * - HMAC-SHA256 refresh token hashing with isolated key
 */

const crypto = require('crypto');
const jwt = require('jsonwebtoken');
const authConfig = require('../../config/authConfig');
const { InvalidTokenError, TokenExpiredError } = require('../../errors/authErrors');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

class TokenService {
  constructor(options = {}) {
    this.jwtSecret = options.jwtSecret || authConfig.jwtSecret;
    this.jwtAlgorithm = options.jwtAlgorithm || authConfig.jwtAlgorithm || 'HS256';
    this.refreshTokenHmacKey = options.refreshTokenHmacKey || authConfig.refreshTokenHmacKey;
    this.expirationMinutes = options.expirationMinutes || authConfig.accessTokenExpireMinutes || 60;
    this.refreshTokenExpireDays = options.refreshTokenExpireDays || authConfig.refreshTokenExpireDays || 30;
  }

  get expirationSeconds() {
    return this.expirationMinutes * 60;
  }

  get refreshExpirationSeconds() {
    return this.refreshTokenExpireDays * 86400;
  }

  /**
   * Create a signed JWT access token for a user.
   *
   * @param {object} user User object containing id and email
   * @returns {string} Signed JWT access token
   */
  createAccessToken(user) {
    const userId = user.id || user._id;
    if (!userId) {
      throw new Error('User id is required to create access token.');
    }

    const now = Math.floor(Date.now() / 1000);
    const expiresAt = now + this.expirationSeconds;
    const tokenId = crypto.randomUUID();

    const payload = {
      sub: String(userId),
      email: user.email,
      iat: now,
      exp: expiresAt,
      jti: tokenId,
      token_type: 'access',
    };

    return jwt.sign(payload, this.jwtSecret, {
      algorithm: this.jwtAlgorithm,
    });
  }

  /**
   * Decode and validate a JWT access token.
   *
   * @param {string} token JWT token string
   * @returns {object} Decoded and validated token payload
   */
  verifyToken(token) {
    if (!token || typeof token !== 'string') {
      throw new InvalidTokenError('Authentication token is missing or invalid.');
    }

    let payload;
    try {
      payload = jwt.verify(token, this.jwtSecret, {
        algorithms: [this.jwtAlgorithm],
      });
    } catch (err) {
      if (err.name === 'TokenExpiredError') {
        throw new TokenExpiredError('Authentication token has expired.');
      }
      throw new InvalidTokenError('Authentication token is invalid.');
    }

    // Required claims check
    if (!payload.sub || !payload.email || !payload.iat || !payload.exp || !payload.jti) {
      throw new InvalidTokenError('Token is missing required claims.');
    }

    if (payload.token_type !== 'access') {
      throw new InvalidTokenError('Token is not an access token.');
    }

    if (!UUID_V4_REGEX.test(payload.sub)) {
      throw new InvalidTokenError('Token subject is not a valid UUID.');
    }

    const issuedAt = new Date(payload.iat * 1000);
    const expiresAt = new Date(payload.exp * 1000);

    return {
      sub: payload.sub,
      userId: payload.sub,
      user_id: payload.sub,
      email: payload.email,
      tokenId: payload.jti,
      token_id: payload.jti,
      tokenType: payload.token_type,
      token_type: payload.token_type,
      issuedAt,
      issued_at: issuedAt,
      expiresAt,
      expires_at: expiresAt,
    };
  }

  /**
   * Generate a cryptographically secure random refresh token.
   *
   * @param {object} [user] Optional user reference
   * @returns {{ rawToken: string, tokenHash: string, expiresAt: Date }}
   */
  createRefreshToken(user = null) {
    const rawToken = crypto.randomBytes(32).toString('base64url');
    const tokenHash = this.hashRefreshToken(rawToken);
    const expiresAt = new Date(Date.now() + this.refreshExpirationSeconds * 1000);

    return {
      rawToken,
      tokenHash,
      expiresAt,
      raw_token: rawToken,
      token_hash: tokenHash,
      expires_at: expiresAt,
      [Symbol.iterator]: function* () {
        yield rawToken;
        yield tokenHash;
        yield expiresAt;
      },
    };
  }

  /**
   * Compute deterministic HMAC-SHA256 keyed hash of a raw refresh token.
   *
   * @param {string} rawToken Raw refresh token string
   * @returns {string} Hex-encoded HMAC-SHA256 hash
   */
  hashRefreshToken(rawToken) {
    if (!rawToken || typeof rawToken !== 'string') {
      throw new Error('rawToken is required to hash refresh token.');
    }
    return crypto
      .createHmac('sha256', this.refreshTokenHmacKey)
      .update(rawToken, 'utf8')
      .digest('hex');
  }

  /**
   * Compute unkeyed SHA-256 hash for backward compatibility.
   *
   * @param {string} rawToken Raw refresh token string
   * @returns {string} Hex-encoded SHA-256 hash
   */
  legacyHashRefreshToken(rawToken) {
    if (!rawToken || typeof rawToken !== 'string') {
      throw new Error('rawToken is required to compute legacy hash.');
    }
    return crypto.createHash('sha256').update(rawToken, 'utf8').digest('hex');
  }
}

const tokenService = new TokenService();

module.exports = tokenService;
module.exports.TokenService = TokenService;
