/**
 * Custom error classes for Repository domain and application operations.
 * Adheres to the StackSense error contract:
 * {
 *   "error": {
 *     "code": "...",
 *     "message": "...",
 *     "details": {}
 *   }
 * }
 */

class RepositoryError extends Error {
  constructor(message, code, status = 400, details = {}) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.status = status;
    this.statusCode = status;
    this.details = details;
    Error.captureStackTrace(this, this.constructor);
  }
}

class RepositoryNotFoundError extends RepositoryError {
  constructor(message = 'Repository not found in the specified project.', details = {}) {
    super(message, 'repository_not_found', 404, details);
  }
}

class RepositoryAlreadyExistsError extends RepositoryError {
  constructor(
    message = 'A repository with this name already exists in the project.',
    details = {}
  ) {
    super(message, 'repository_already_exists', 409, details);
  }
}

module.exports = {
  RepositoryError,
  RepositoryNotFoundError,
  RepositoryAlreadyExistsError,
};
