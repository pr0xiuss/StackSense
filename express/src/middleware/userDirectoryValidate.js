const USERNAME_PREFIX_REGEX = /^[a-zA-Z0-9_]{2,30}$/;

function validateUsernameLookup(req, res, next) {
  const rawUsername = req.query.username;
  const rawLimit = req.query.limit;

  if (typeof rawUsername !== 'string' || !USERNAME_PREFIX_REGEX.test(rawUsername.trim())) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Username search must be 2 to 30 letters, numbers, or underscores.',
        details: { field: 'username' },
      },
    });
  }

  let limit = 8;
  if (rawLimit !== undefined) {
    const parsed = Number(rawLimit);
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 10) {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Query parameter limit must be an integer between 1 and 10.',
          details: { field: 'limit' },
        },
      });
    }
    limit = parsed;
  }

  req.userLookup = {
    username: rawUsername.trim().toLowerCase(),
    limit,
  };
  next();
}

module.exports = { validateUsernameLookup };
