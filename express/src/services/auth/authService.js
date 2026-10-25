const crypto = require('crypto');
const mongoose = require('mongoose');
const User = require('../../models/User');
const RefreshToken = require('../../models/RefreshToken');
const passwordService = require('./passwordService');
const tokenService = require('./tokenService');
const {
  InvalidCredentialsError,
  UserAlreadyExistsError,
  UsernameAlreadyExistsError,
  UserInactiveError,
  InvalidRefreshTokenError,
  RefreshTokenExpiredError,
  RefreshTokenRevokedError,
  PasswordPolicyError,
} = require('../../errors/authErrors');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

class AuthService {
  constructor(options = {}) {
    this.passwordService = options.passwordService || passwordService;
    this.tokenService = options.tokenService || tokenService;
    this.User = options.User || User;
    this.RefreshToken = options.RefreshToken || RefreshToken;
  }


  async register({ email, username, password }) {
    this.passwordService.validate(password);

    const normalizedEmail = String(email || '').trim().toLowerCase();
    const normalizedUsername = String(username || '').trim().toLowerCase();

    const passwordHash = await this.passwordService.hash(password);

    const user = new this.User({
      email: normalizedEmail,
      username: normalizedUsername,
      password_hash: passwordHash,
    });

    try {
      await user.save();
    } catch (err) {
      if (err.code === 11000) {
        const keyPattern = err.keyPattern || {};
        const keyValue = err.keyValue || {};

        if (keyPattern.email) {
          throw new UserAlreadyExistsError(
            'A user with this email address already exists.',
            { field: 'email', value: keyValue.email }
          );
        }
        if (keyPattern.username) {
          throw new UsernameAlreadyExistsError(
            'A user with this username already exists.',
            { field: 'username', value: keyValue.username }
          );
        }
        throw new UserAlreadyExistsError('A user with these credentials already exists.');
      }
      throw err;
    }

    return user.toJSON();
  }

  async login({ identifier, password }) {
    const normalizedIdentifier = String(identifier || '').trim().toLowerCase();

    const user = await this.User.findOne({
      $or: [
        { email: normalizedIdentifier },
        { username: normalizedIdentifier },
      ],
    }).select('+password_hash');

    if (!user) {
      await this.passwordService.dummyVerify(password);
      throw new InvalidCredentialsError('Invalid email or password.');
    }

    const isValid = await this.passwordService.verify(password, user.password_hash);
    if (!isValid) {
      throw new InvalidCredentialsError('Invalid email or password.');
    }

    if (!user.is_active) {
      throw new UserInactiveError('User account is inactive.');
    }

    const accessToken = this.tokenService.createAccessToken(user);
    const { rawToken: refreshToken, tokenHash: refreshTokenHash, expiresAt: refreshExpiresAt } =
      this.tokenService.createRefreshToken(user);

    const refreshTokenDoc = new this.RefreshToken({
      user_id: user.id,
      token_hash: refreshTokenHash,
      expires_at: refreshExpiresAt,
    });
    await refreshTokenDoc.save();

    return {
      user: user.toJSON(),
      access_token: accessToken,
      refresh_token: refreshToken,
      token_type: 'Bearer',
      expires_in: this.tokenService.expirationSeconds,
      refresh_expires_in: this.tokenService.refreshExpirationSeconds,
    };
  }

  /**
   * Refresh access token using a refresh token.
   *
   * Uses atomic conditional findOneAndUpdate to ensure strictly single-use
   * consumption even under concurrent requests:
   * - Query filter: { token_hash: tokenHash, revoked_at: null, expires_at: { $gt: now } }
   * - Update: { $set: { revoked_at: now, replaced_by_token_id: newTokenId } }
   *
   * If replacement creation fails, compensating rollback restores the token.
   *
   * @param {string} refreshToken Raw refresh token
   * @returns {Promise<object>} New tokens and user info
   */
  async refreshToken(refreshToken) {
    if (!refreshToken || typeof refreshToken !== 'string') {
      throw new InvalidRefreshTokenError('Invalid refresh token.');
    }

    const tokenHash = this.tokenService.hashRefreshToken(refreshToken);
    const now = new Date();

    // Atomic conditional update: find active, unexpired token and mark as revoked
    const existingToken = await this.RefreshToken.findOneAndUpdate(
      {
        token_hash: tokenHash,
        revoked_at: null,
        expires_at: { $gt: now },
      },
      {
        $set: {
          revoked_at: now,
          replaced_by_token_id: null, // Placeholder, will be updated after new token creation
        },
      },
      { new: true }
    );

    if (!existingToken) {
      // Distinguish between nonexistent, revoked, and expired
      const anyToken = await this.RefreshToken.findOne({ token_hash: tokenHash });
      if (!anyToken) {
        throw new InvalidRefreshTokenError('Invalid refresh token.');
      }
      if (anyToken.revoked_at) {
        throw new RefreshTokenRevokedError('Refresh token has been revoked.');
      }
      throw new RefreshTokenExpiredError('Refresh token has expired.');
    }

    // Get the user
    const user = await this.User.findById(existingToken.user_id);
    if (!user || !user.is_active) {
      // Compensating rollback: restore the token if user is gone or inactive
      await this.RefreshToken.findByIdAndUpdate(existingToken._id, {
        $unset: { revoked_at: 1, replaced_by_token_id: 1 },
      });
      throw new UserInactiveError('User account is inactive or not found.');
    }

    // Generate new token pair
    const newAccessToken = this.tokenService.createAccessToken(user);
    const {
      rawToken: newRefreshToken,
      tokenHash: newRefreshTokenHash,
      expiresAt: newRefreshExpiresAt,
    } = this.tokenService.createRefreshToken(user);

    const newTokenId = crypto.randomUUID();

    try {
      // Save new refresh token
      const newRefreshTokenDoc = new this.RefreshToken({
        _id: newTokenId,
        user_id: user.id,
        token_hash: newRefreshTokenHash,
        expires_at: newRefreshExpiresAt,
      });
      await newRefreshTokenDoc.save();

      // Update the old token with the replacement token ID
      await this.RefreshToken.findByIdAndUpdate(existingToken._id, {
        $set: { replaced_by_token_id: newTokenId },
      });
    } catch (err) {
      // Compensating rollback: restore the old token if new token creation fails
      await this.RefreshToken.findByIdAndUpdate(existingToken._id, {
        $unset: { revoked_at: 1, replaced_by_token_id: 1 },
      });
      throw err;
    }

    return {
      user: user.toJSON(),
      access_token: newAccessToken,
      refresh_token: newRefreshToken,
      token_type: 'Bearer',
      expires_in: this.tokenService.expirationSeconds,
      refresh_expires_in: this.tokenService.refreshExpirationSeconds,
    };
  }

  /**
   * Revoke a refresh token (logout).
   *
   * @param {string} refreshToken Raw refresh token
   * @returns {Promise<void>}
   */
  async logout(refreshToken) {
    if (!refreshToken || typeof refreshToken !== 'string') {
      // Silent success for logout - no error if token is malformed
      return;
    }

    const tokenHash = this.tokenService.hashRefreshToken(refreshToken);
    await this.RefreshToken.findOneAndUpdate(
      { token_hash: tokenHash, revoked_at: null },
      { $set: { revoked_at: new Date() } }
    );
  }

  /**
   * Get current user profile by ID.
   *
   * @param {string} userId User UUID v4
   * @returns {Promise<object|null>} User document or null if not found
   */
  async getCurrentUser(userId) {
    if (!userId || !UUID_V4_REGEX.test(userId)) {
      return null;
    }
    const user = await this.User.findById(userId);
    if (!user) {
      return null;
    }
    if (!user.is_active) {
      throw new UserInactiveError('User account is inactive.');
    }
    return user.toJSON();
  }
}

const authService = new AuthService();

module.exports = authService;
module.exports.AuthService = AuthService;
