function errorHandler(err, req, res, next) {
  let status = err.status || err.statusCode;
  let code = err.code;
  let message = err.message || 'An internal server error occurred.';
  let details = err.details || {};

  if (err.name === 'ValidationError') {
    status = 422;
    code = 'validation_error';
    message = 'Validation failed.';
    details = {};
    if (err.errors) {
      for (const [field, val] of Object.entries(err.errors)) {
        details[field] = val.message;
      }
    }
  } else if (err.name === 'CastError') {
    status = 422;
    code = 'validation_error';
    message = `Invalid format for field ${err.path}.`;
  } else if (err.name === 'TokenExpiredError') {
    status = 401;
    code = 'token_expired';
    message = 'Authentication token has expired.';
  } else if (err.name === 'JsonWebTokenError') {
    status = 401;
    code = 'invalid_token';
    message = 'Authentication token is invalid.';
  }

  status = status || 500;
  code =
    code ||
    (status === 404
      ? 'not_found'
      : status === 422 || status === 400 || status === 413
      ? 'validation_error'
      : 'internal_error');

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
