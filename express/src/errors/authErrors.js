/**
 * Custom error classes for Identity & Authentication domain operations.
 * Adheres to the StackSense error contract:
 * {
 *   "error": {
 *     "code": "...",
 *     "message": "...",
 *     "details": {}
 *   }
 * }
 */

class AuthError extends Error {
  constructor(message, code, status = 400, details = {}) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.status = status;
    this.statusCode = status;
    this.details = details;
    Error.captureStackTrace(this, this.constructor);
  }
}

class InvalidCredentialsError extends AuthError {
  constructor(message = 'Invalid email or password.', details = {}) {
    super(message, 'invalid_credentials', 401, details);
  }
}

class AuthenticationRequiredError extends AuthError {
  constructor(message = 'Authentication credentials were not provided.', details = {}) {
    super(message, 'authentication_required', 401, details);
  }
}

class UserAlreadyExistsError extends AuthError {
  constructor(message = 'A user with this email address already exists.', details = {}) {
    super(message, 'user_already_exists', 409, details);
  }
}

class UsernameAlreadyExistsError extends AuthError {
  constructor(message = 'A user with this username already exists.', details = {}) {
    super(message, 'username_already_exists', 409, details);
  }
}

class UserInactiveError extends AuthError {
  constructor(message = 'User account is inactive.', details = {}) {
    super(message, 'user_inactive', 403, details);
  }
}

class InvalidRefreshTokenError extends AuthError {
  constructor(message = 'Invalid refresh token.', details = {}) {
    super(message, 'invalid_refresh_token', 401, details);
  }
}

class RefreshTokenExpiredError extends AuthError {
  constructor(message = 'Refresh token has expired.', details = {}) {
    super(message, 'refresh_token_expired', 401, details);
  }
}

class RefreshTokenRevokedError extends AuthError {
  constructor(message = 'Refresh token has been revoked.', details = {}) {
    super(message, 'refresh_token_revoked', 401, details);
  }
}

class InvalidTokenError extends AuthError {
  constructor(message = 'Authentication token is invalid.', details = {}) {
    super(message, 'invalid_token', 401, details);
  }
}

class TokenExpiredError extends AuthError {
  constructor(message = 'Authentication token has expired.', details = {}) {
    super(message, 'token_expired', 401, details);
  }
}

class PasswordPolicyError extends AuthError {
  constructor(message = 'Password does not meet policy requirements.', details = {}) {
    super(message, 'password_policy_violation', 422, details);
  }
}

module.exports = {
  AuthError,
  InvalidCredentialsError,
  AuthenticationRequiredError,
  UserAlreadyExistsError,
  UsernameAlreadyExistsError,
  UserInactiveError,
  InvalidRefreshTokenError,
  RefreshTokenExpiredError,
  RefreshTokenRevokedError,
  InvalidTokenError,
  TokenExpiredError,
  PasswordPolicyError,
};
