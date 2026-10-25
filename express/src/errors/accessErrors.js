class ProjectAccessError extends Error {
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

class ProjectAccessDeniedError extends ProjectAccessError {
  constructor(message = 'User does not have access to this project.', details = {}) {
    super(message, 'project_access_denied', 403, details);
  }
}

class ProjectAccessAlreadyExistsError extends ProjectAccessError {
  constructor(message = 'User already has access to this project.', details = {}) {
    super(message, 'project_access_already_exists', 409, details);
  }
}

class ProjectAccessNotFoundError extends ProjectAccessError {
  constructor(message = 'Project access record does not exist.', details = {}) {
    super(message, 'project_access_not_found', 404, details);
  }
}

module.exports = {
  ProjectAccessError,
  ProjectAccessDeniedError,
  ProjectAccessAlreadyExistsError,
  ProjectAccessNotFoundError,
};
