/**
 * Centralized API error handling middleware.
 * Ensures all responses strictly adhere to the StackSense error contract:
 * {
 *   "error": {
 *     "code": "...",
 *     "message": "...",
 *     "details": {}
 *   }
 * }
 */
function errorHandler(err, req, res, next) {
  const status = err.status || err.statusCode || 500;
  const code = err.code || (status === 404 ? 'not_found' : status === 422 || status === 400 ? 'validation_error' : 'internal_error');
  const message = err.message || 'An internal server error occurred.';
  const details = err.details || {};

  if (status >= 500 && process.env.NODE_ENV !== 'test') {
    console.error(`[InternalError] ${req.method} ${req.originalUrl}:`, err);
  }

  res.status(status).json({
    error: {
      code,
      message,
      details,
    },
  });
}

module.exports = errorHandler;
