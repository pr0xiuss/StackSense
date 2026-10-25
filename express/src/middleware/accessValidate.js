const { VALID_PROJECT_ROLES } = require('../constants/projectRoles');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function validateUserIdParam(req, res, next) {
  const { userId } = req.params;

  if (!userId || !UUID_V4_REGEX.test(userId)) {
    return res.status(422).json({
      error: {
        code: 'invalid_user_id',
        message: 'User ID must be a valid UUID v4.',
        details: { userId },
      },
    });
  }

  next();
}


function validateGrantAccessBody(req, res, next) {
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

  const { user_id, role } = body;

  if (!user_id || typeof user_id !== 'string' || !user_id.trim()) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'user_id is required.',
        details: { field: 'user_id' },
      },
    });
  }

  if (!UUID_V4_REGEX.test(user_id.trim())) {
    return res.status(422).json({
      error: {
        code: 'invalid_user_id',
        message: 'user_id must be a valid UUID v4.',
        details: { user_id },
      },
    });
  }

  if (!role || typeof role !== 'string' || !role.trim()) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'role is required.',
        details: { field: 'role' },
      },
    });
  }

  const normalizedRole = role.trim().toLowerCase();
  if (!VALID_PROJECT_ROLES.includes(normalizedRole)) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: `Invalid project role '${role}'. Must be one of: ${VALID_PROJECT_ROLES.join(', ')}.`,
        details: { field: 'role', valid_roles: VALID_PROJECT_ROLES },
      },
    });
  }

  req.body.user_id = user_id.trim();
  req.body.role = normalizedRole;

  next();
}


function validateChangeRoleBody(req, res, next) {
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

  const { role } = body;

  if (!role || typeof role !== 'string' || !role.trim()) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'role is required.',
        details: { field: 'role' },
      },
    });
  }

  const normalizedRole = role.trim().toLowerCase();
  if (!VALID_PROJECT_ROLES.includes(normalizedRole)) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: `Invalid project role '${role}'. Must be one of: ${VALID_PROJECT_ROLES.join(', ')}.`,
        details: { field: 'role', valid_roles: VALID_PROJECT_ROLES },
      },
    });
  }

  req.body.role = normalizedRole;

  next();
}

module.exports = {
  validateUserIdParam,
  validateGrantAccessBody,
  validateChangeRoleBody,
};
