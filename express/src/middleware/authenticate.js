const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const tokenService = require('../services/auth/tokenService');
const { InvalidTokenError, TokenExpiredError } = require('../errors/authErrors');

/**
 * Authentication middleware.
 * Extracts and validates Bearer JWT access tokens.
 * In production, only Bearer tokens are accepted. x-user-id header is strictly rejected.
 * In test environments, x-user-id header fallback is allowed for isolated unit/integration suites.
 */
function authenticate(req, res, next) {
  // 1. Check for Authorization: Bearer <token>
  const authHeader = req.header('authorization');
  if (authHeader) {
    const parts = authHeader.split(' ');
    if (parts.length === 2 && parts[0].toLowerCase() === 'bearer') {
      const token = parts[1];
      try {
        const payload = tokenService.verifyToken(token);
        // payload contains: sub, userId, email, tokenId, tokenType, issuedAt, expiresAt
        req.user = {
          id: payload.sub,
          email: payload.email,
        };
        return next();
      } catch (err) {
        if (err instanceof TokenExpiredError) {
          return res.status(401).json({
            error: {
              code: 'token_expired',
              message: err.message,
              details: {},
            },
          });
        }
        if (err instanceof InvalidTokenError) {
          return res.status(401).json({
            error: {
              code: 'invalid_token',
              message: err.message,
              details: {},
            },
          });
        }
        // Unexpected error
        return res.status(401).json({
          error: {
            code: 'invalid_token',
            message: 'Authentication token is invalid.',
            details: {},
          },
        });
      }
    } else {
      return res.status(401).json({
        error: {
          code: 'invalid_token',
          message: 'Malformed authorization header. Format must be Bearer <token>.',
          details: {},
        },
      });
    }
  }

  // 2. If req.user is already set by upstream/mock (e.g., from other middleware)
  if (req.user) {
    const rawUserId = req.user.id || req.user._id;
    if (rawUserId) {
      const userId = String(rawUserId);
      if (!UUID_V4_REGEX.test(userId)) {
        return res.status(422).json({
          error: {
            code: 'invalid_user_id',
            message: 'User ID must be a valid UUID v4.',
            details: { user_id: userId },
          },
        });
      }
      // Ensure req.user.id is canonically set to string UUID
      req.user.id = userId;
      return next();
    }
  }

  // 3. Check for x-user-id header seam (TEST ENVIRONMENTS ONLY)
  const headerUserId = req.header('x-user-id');
  if (headerUserId) {
    // Security Guard: In production and non-test environments, strictly reject x-user-id header
    if (process.env.NODE_ENV === 'production' || process.env.NODE_ENV !== 'test') {
      return res.status(401).json({
        error: {
          code: 'authentication_required',
          message: 'Authentication credentials were not provided.',
          details: {},
        },
      });
    }

    // Test environment: allow x-user-id header
    if (!UUID_V4_REGEX.test(headerUserId)) {
      return res.status(422).json({
        error: {
          code: 'invalid_user_id',
          message: 'User ID in x-user-id header must be a valid UUID v4.',
          details: { user_id: headerUserId },
        },
      });
    }

    req.user = { id: headerUserId };
    return next();
  }

  // 4. No authenticated credentials provided
  return res.status(401).json({
    error: {
      code: 'authentication_required',
      message: 'Authentication credentials were not provided.',
      details: {},
    },
  });
}

module.exports = authenticate;