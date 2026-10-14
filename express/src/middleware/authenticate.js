const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Authentication middleware seam.
 * In production/M5, this extracts and validates authenticated user identity.
 * Architectural Invariant (master.txt §0.2): User resource identities are strictly UUID v4.
 * In development/testing, it accepts req.user (supporting either .id or ._id from Mongoose),
 * or resolves the current user identity via the 'x-user-id' header seam.
 */
function authenticate(req, res, next) {
  // 1. If req.user is already set by upstream/mock/M5 middleware
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

  // 2. Check for x-user-id header seam
  const headerUserId = req.header('x-user-id');
  if (headerUserId) {
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

  // 3. No authenticated credentials provided
  return res.status(401).json({
    error: {
      code: 'authentication_required',
      message: 'Authentication credentials were not provided.',
      details: {},
    },
  });
}

module.exports = authenticate;
