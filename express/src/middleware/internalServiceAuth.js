const crypto = require('crypto');
const { AuthenticationRequiredError, InvalidTokenError } = require('../errors/authErrors');

/** Authenticate Python-to-Express internal platform API calls. */
function authenticateInternalService(req, res, next) {
  const provided = req.get('X-Service-Token');
  const expected = process.env.PLATFORM_INTERNAL_API_SECRET_KEY;

  if (!provided) {
    return next(new AuthenticationRequiredError('Internal service credential is required.'));
  }
  if (!expected) {
    const error = new Error('PLATFORM_INTERNAL_API_SECRET_KEY is not configured.');
    error.code = 'internal_service_not_configured';
    error.status = 503;
    return next(error);
  }

  const providedBuffer = Buffer.from(provided);
  const expectedBuffer = Buffer.from(expected);
  if (
    providedBuffer.length !== expectedBuffer.length ||
    !crypto.timingSafeEqual(providedBuffer, expectedBuffer)
  ) {
    return next(new InvalidTokenError('Internal service credential is invalid.'));
  }

  req.internalService = { name: 'python-analysis' };
  return next();
}

module.exports = authenticateInternalService;
