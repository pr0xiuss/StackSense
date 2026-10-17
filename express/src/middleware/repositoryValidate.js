const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Validate that req.params.repositoryId is a valid UUID v4.
 */
function validateRepositoryId(req, res, next) {
  const { repositoryId } = req.params;

  if (!repositoryId || !UUID_V4_REGEX.test(repositoryId)) {
    return res.status(422).json({
      error: {
        code: 'invalid_repository_id',
        message: 'Repository ID must be a valid UUID v4.',
        details: { repositoryId },
      },
    });
  }

  next();
}

/**
 * Validate payload for registering a repository.
 */
function validateRegisterRepository(req, res, next) {
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
        message: 'Repository name is required and cannot be empty.',
        details: { field: 'name' },
      },
    });
  }

  const trimmedName = name.trim();
  if (trimmedName.length > 255) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'Repository name cannot exceed 255 characters.',
        details: { field: 'name' },
      },
    });
  }

  if (description !== undefined && description !== null) {
    if (typeof description !== 'string') {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Repository description must be a string.',
          details: { field: 'description' },
        },
      });
    }

    if (description.trim().length > 2000) {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Repository description cannot exceed 2000 characters.',
          details: { field: 'description' },
        },
      });
    }
  }

  next();
}

/**
 * Validate payload for updating repository metadata.
 */
function validateUpdateRepository(req, res, next) {
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
          message: 'Repository name cannot be empty when provided.',
          details: { field: 'name' },
        },
      });
    }

    if (name.trim().length > 255) {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Repository name cannot exceed 255 characters.',
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
          message: 'Repository description must be a string when provided.',
          details: { field: 'description' },
        },
      });
    }

    if (description.trim().length > 2000) {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'Repository description cannot exceed 2000 characters.',
          details: { field: 'description' },
        },
      });
    }
  }

  next();
}

module.exports = {
  validateRepositoryId,
  validateRegisterRepository,
  validateUpdateRepository,
};
