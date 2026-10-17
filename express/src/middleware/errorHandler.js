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
  let status = err.status || err.statusCode;
  let code = err.code;
  let message = err.message || 'An internal server error occurred.';
  let details = err.details || {};

  // Multer error mapping (IR-M4-019)
  if (err.name === 'MulterError') {
    if (err.code === 'LIMIT_FILE_SIZE') {
      status = 413;
      code = 'max_repository_size_exceeded';
      message = 'Uploaded file exceeds the maximum permitted repository size limit of 500 MB.';
      details = { limit_bytes: 524288000 };
    } else {
      status = 422;
      code = 'upload_error';
      message = err.message || 'File upload failed.';
    }
  } else if (err.name === 'ValidationError') {
    // Mongoose schema validation mapping (IR-M4-013)
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
