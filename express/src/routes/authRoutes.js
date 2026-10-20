const express = require('express');
const authController = require('../controllers/authController');
const {
  validateRegister,
  validateLogin,
  validateRefresh,
  validateLogout,
} = require('../middleware/authValidate');
const authenticate = require('../middleware/authenticate');

const router = express.Router();

/**
 * POST /api/v1/auth/register
 * Public self-registration endpoint.
 * Returns 201 Created with user info on success.
 * Returns 422 on validation error, 409 on duplicate email/username.
 */
router.post('/register', validateRegister, authController.register);

/**
 * POST /api/v1/auth/login
 * User authentication endpoint.
 * Supports identifier (email OR username).
 * Returns 200 OK with access_token, refresh_token, token_type, expires_in, refresh_expires_in.
 * Returns 401 on invalid credentials, 403 on inactive account.
 */
router.post('/login', validateLogin, authController.login);

/**
 * POST /api/v1/auth/refresh
 * Atomic refresh-token rotation endpoint.
 * Uses atomic conditional update for single-use consumption under concurrency.
 * Returns 200 OK with new token pair.
 * Returns 401 for invalid, revoked, or expired refresh tokens.
 */
router.post('/refresh', validateRefresh, authController.refresh);

/**
 * POST /api/v1/auth/logout
 * Session revocation endpoint.
 * Revokes the provided refresh token.
 * Returns 204 No Content.
 */
router.post('/logout', validateLogout, authController.logout);

/**
 * GET /api/v1/auth/me
 * Current user profile endpoint.
 * Requires Bearer JWT authentication.
 * Returns 200 OK with user profile.
 * Returns 401 if authentication required.
 */
router.get('/me', authenticate, authController.me);

module.exports = router;