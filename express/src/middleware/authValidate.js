const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const USERNAME_REGEX = /^[a-zA-Z0-9_]{3,30}$/;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Validate payload for user registration.
 */
function validateRegister(req, res, next) {
  const body = req.body;

  if (!body || typeof body !== 'object') {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Request body is required.',
        details: {},
      },
    });
  }

  const { email, username, password } = body;

  // Email validation
  if (typeof email !== 'string' || !email.trim()) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Email is required and cannot be empty.',
        details: { field: 'email' },
      },
    });
  }

  const trimmedEmail = email.trim().toLowerCase();
  if (trimmedEmail.length > 255) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Email cannot exceed 255 characters.',
        details: { field: 'email' },
      },
    });
  }

  if (!EMAIL_REGEX.test(trimmedEmail)) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Email format is invalid.',
        details: { field: 'email' },
      },
    });
  }

  // Username validation
  if (typeof username !== 'string' || !username.trim()) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Username is required and cannot be empty.',
        details: { field: 'username' },
      },
    });
  }

  const trimmedUsername = username.trim().toLowerCase();
  if (!USERNAME_REGEX.test(trimmedUsername)) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Username must be between 3 and 30 characters and contain only letters, numbers, and underscores.',
        details: { field: 'username' },
      },
    });
  }

  // Password validation (basic structural checks; full policy enforced in service)
  if (typeof password !== 'string') {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Password is required and must be a string.',
        details: { field: 'password' },
      },
    });
  }

  if (password.length < 8) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Password must be at least 8 characters long.',
        details: { field: 'password' },
      },
    });
  }

  if (password.length > 128) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Password cannot exceed 128 characters.',
        details: { field: 'password' },
      },
    });
  }

  // Normalize for downstream use
  req.body.email = trimmedEmail;
  req.body.username = trimmedUsername;

  next();
}

/**
 * Validate payload for user login.
 */
function validateLogin(req, res, next) {
  const body = req.body;

  if (!body || typeof body !== 'object') {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Request body is required.',
        details: {},
      },
    });
  }

  const { identifier, password } = body;

  if (typeof identifier !== 'string' || !identifier.trim()) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Identifier (email or username) is required and cannot be empty.',
        details: { field: 'identifier' },
      },
    });
  }

  if (typeof password !== 'string') {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Password is required and must be a string.',
        details: { field: 'password' },
      },
    });
  }

  // Normalize for downstream use
  req.body.identifier = identifier.trim().toLowerCase();

  next();
}

/**
 * Validate payload for token refresh.
 */
function validateRefresh(req, res, next) {
  const body = req.body;

  if (!body || typeof body !== 'object') {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Request body is required.',
        details: {},
      },
    });
  }

  const { refresh_token } = body;

  if (typeof refresh_token !== 'string' || !refresh_token.trim()) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Refresh token is required and cannot be empty.',
        details: { field: 'refresh_token' },
      },
    });
  }

  next();
}

/**
 * Validate payload for logout (optional refresh token).
 */
function validateLogout(req, res, next) {
  const body = req.body;

  // Logout body is optional - if provided, validate refresh_token
  if (body && typeof body === 'object' && body.refresh_token !== undefined) {
    const { refresh_token } = body;
    if (typeof refresh_token !== 'string') {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Refresh token must be a string if provided.',
          details: { field: 'refresh_token' },
        },
      });
    }
  }

  next();
}

module.exports = {
  validateRegister,
  validateLogin,
  validateRefresh,
  validateLogout,
};