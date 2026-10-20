const authService = require('../services/auth/authService');
const { InvalidCredentialsError, UserInactiveError } = require('../errors/authErrors');

/**
 * Controller handling HTTP requests for Authentication endpoints.
 */
const authController = {
  /**
   * POST /api/v1/auth/register
   * Register a new user account.
   */
  async register(req, res, next) {
    try {
      const { email, username, password } = req.body;
      const user = await authService.register({ email, username, password });

      res.status(201).json({
        ...user,
        user,
        message: 'User registered successfully.',
      });
    } catch (err) {
      next(err);
    }
  },

  /**
   * POST /api/v1/auth/login
   * Authenticate user and return access + refresh tokens.
   */
  async login(req, res, next) {
    try {
      const { identifier, password } = req.body;
      const result = await authService.login({ identifier, password });

      res.status(200).json(result);
    } catch (err) {
      // Map service errors to appropriate HTTP responses
      if (err instanceof InvalidCredentialsError || err instanceof UserInactiveError) {
        // These are already structured with correct status codes
        return next(err);
      }
      next(err);
    }
  },

  /**
   * POST /api/v1/auth/refresh
   * Refresh access token using a valid refresh token.
   */
  async refresh(req, res, next) {
    try {
      const { refresh_token } = req.body;
      const result = await authService.refreshToken(refresh_token);

      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  },

  /**
   * POST /api/v1/auth/logout
   * Revoke refresh token and end session.
   */
  async logout(req, res, next) {
    try {
      const { refresh_token } = req.body;
      await authService.logout(refresh_token);

      res.status(204).send();
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/auth/me
   * Get current authenticated user profile.
   */
  async me(req, res, next) {
    try {
      const userId = req.user.id;
      const user = await authService.getCurrentUser(userId);

      if (!user) {
        return res.status(404).json({
          error: {
            code: 'user_not_found',
            message: 'User not found.',
            details: { user_id: userId },
          },
        });
      }

      res.status(200).json(user);
    } catch (err) {
      next(err);
    }
  },
};

module.exports = authController;