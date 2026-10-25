const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const tokenService = require('../services/auth/tokenService');
const authService = require('../services/auth/authService');
const { InvalidTokenError, TokenExpiredError, UserInactiveError } = require('../errors/authErrors');


async function authenticate(req, res, next) {
  const authHeader = req.header('authorization');
  if (authHeader) {
    const parts = authHeader.split(' ');
    if (parts.length === 2 && parts[0].toLowerCase() === 'bearer') {
      const token = parts[1];
      try {
        const payload = tokenService.verifyToken(token);
        const currentUser = await authService.getCurrentUser(payload.sub);
        if (!currentUser) {
          throw new InvalidTokenError('User associated with token does not exist.');
        }

        req.user = {
          id: currentUser.id,
          email: currentUser.email,
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
        if (err instanceof UserInactiveError) {
          return res.status(403).json({
            error: {
              code: 'user_inactive',
              message: err.message,
              details: {},
            },
          });
        }

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
      req.user.id = userId;
      return next();
    }
  }

  const headerUserId = req.header('x-user-id');
  if (headerUserId) {
    if (process.env.NODE_ENV === 'production' || process.env.NODE_ENV !== 'test') {
      return res.status(401).json({
        error: {
          code: 'authentication_required',
          message: 'Authentication credentials were not provided.',
          details: {},
        },
      });
    }

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

  return res.status(401).json({
    error: {
      code: 'authentication_required',
      message: 'Authentication credentials were not provided.',
      details: {},
    },
  });
}

module.exports = authenticate;
