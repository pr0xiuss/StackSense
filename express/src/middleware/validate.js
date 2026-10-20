const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Validate that req.params.projectId is a valid UUID v4.
 */
function validateProjectId(req, res, next) {
  const { projectId } = req.params;

  if (!projectId || !UUID_V4_REGEX.test(projectId)) {
    return res.status(422).json({
      error: {
        code: 'invalid_project_id',
        message: 'Project ID must be a valid UUID v4.',
        details: { projectId },
      },
    });
  }

  next();
}

/**
 * Validate payload for project creation.
 */
function validateCreateProject(req, res, next) {
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

  const { name, description } = body;

  if (typeof name !== 'string' || !name.trim()) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Project name is required and cannot be empty.',
        details: { field: 'name' },
      },
    });
  }

  const trimmedName = name.trim();
  if (trimmedName.length > 255) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Project name cannot exceed 255 characters.',
        details: { field: 'name' },
      },
    });
  }

  if (description !== undefined && description !== null) {
    if (typeof description !== 'string') {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Project description must be a string or null.',
          details: { field: 'description' },
        },
      });
    }

    if (description.trim().length > 2000) {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Project description cannot exceed 2000 characters.',
          details: { field: 'description' },
        },
      });
    }
  }

  next();
}

/**
 * Validate payload for project updates.
 */
function validateUpdateProject(req, res, next) {
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

  const { name, description } = body;

  if (name === undefined && description === undefined) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'At least one field (name or description) must be provided for update.',
        details: {},
      },
    });
  }

  if (name !== undefined) {
    if (typeof name !== 'string' || !name.trim()) {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Project name cannot be empty.',
          details: { field: 'name' },
        },
      });
    }

    if (name.trim().length > 255) {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Project name cannot exceed 255 characters.',
          details: { field: 'name' },
        },
      });
    }
  }

  if (description !== undefined && description !== null) {
    if (typeof description !== 'string') {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Project description must be a string or null.',
          details: { field: 'description' },
        },
      });
    }

    if (description.trim().length > 2000) {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Project description cannot exceed 2000 characters.',
          details: { field: 'description' },
        },
      });
    }
  }

  next();
}

/**
 * Validate query parameters for pagination.
 */
function validatePagination(req, res, next) {
  const limitRaw = req.query.limit;
  const offsetRaw = req.query.offset;

  let limit = 50;
  let offset = 0;

  if (limitRaw !== undefined) {
    const parsedLimit = Number(limitRaw);
    if (!Number.isInteger(parsedLimit) || parsedLimit < 1) {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Query parameter limit must be an integer between 1 and 100.',
          details: { field: 'limit' },
        },
      });
    }
    limit = Math.min(100, parsedLimit);
  }

  if (offsetRaw !== undefined) {
    const parsedOffset = Number(offsetRaw);
    if (!Number.isInteger(parsedOffset) || parsedOffset < 0) {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Query parameter offset must be a non-negative integer.',
          details: { field: 'offset' },
        },
      });
    }
    offset = parsedOffset;
  }

  req.pagination = { limit, offset };
  next();
}

module.exports = {
  validateProjectId,
  validateCreateProject,
  validateUpdateProject,
  validatePagination,
};
