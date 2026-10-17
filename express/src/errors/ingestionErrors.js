/**
 * Custom error classes for Ingestion, Revision, and Storage operations.
 * Adheres to the StackSense error contract:
 * {
 *   "error": {
 *     "code": "...",
 *     "message": "...",
 *     "details": {}
 *   }
 * }
 */

class IngestionError extends Error {
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

class IngestionNotFoundError extends IngestionError {
  constructor(message = 'Ingestion not found for this repository.', details = {}) {
    super(message, 'ingestion_not_found', 404, details);
  }
}

class ActiveIngestionExistsError extends IngestionError {
  constructor(
    message = 'An active ingestion is already running for this repository.',
    details = {}
  ) {
    super(message, 'active_ingestion_exists', 409, details);
  }
}

class InvalidIngestionStateError extends IngestionError {
  constructor(message = 'Invalid ingestion state transition.', details = {}) {
    super(message, 'invalid_ingestion_state', 409, details);
  }
}

class RevisionAlreadyExistsError extends IngestionError {
  constructor(
    message = 'A revision with this identifier already exists for this repository.',
    details = {}
  ) {
    super(message, 'revision_already_exists', 409, details);
  }
}

class RevisionNotFoundError extends IngestionError {
  constructor(message = 'Repository revision not found.', details = {}) {
    super(message, 'revision_not_found', 404, details);
  }
}

class SourceValidationError extends IngestionError {
  constructor(message = 'Repository source validation failed.', details = {}) {
    super(message, 'source_validation_failed', 422, details);
  }
}

class MaxFileCountExceededError extends IngestionError {
  constructor(
    message = 'Repository archive exceeds maximum permitted file count.',
    details = {}
  ) {
    super(message, 'max_file_count_exceeded', 422, details);
  }
}

class UnsupportedArchiveFormatError extends IngestionError {
  constructor(
    message = 'Unsupported archive format. Supported formats: .zip, .tar, .tar.gz, .tgz.',
    details = {}
  ) {
    super(message, 'unsupported_archive_format', 422, details);
  }
}

class InvalidSourceTypeError extends IngestionError {
  constructor(
    message = 'Unsupported or invalid repository source type.',
    details = {}
  ) {
    super(message, 'invalid_source_type', 422, details);
  }
}

class InvalidGitHubUrlError extends IngestionError {
  constructor(message = 'Invalid GitHub repository URL.', details = {}) {
    super(message, 'invalid_github_url', 422, details);
  }
}

class InvalidGitHubRefError extends IngestionError {
  constructor(message = 'Invalid GitHub ref (branch, tag, or commit).', details = {}) {
    super(message, 'invalid_github_ref', 422, details);
  }
}

class GitHubRepositoryNotFoundError extends IngestionError {
  constructor(message = 'Repository not found or access denied.', details = {}) {
    super(message, 'github_repository_not_found', 404, details);
  }
}

class GitHubAcquisitionError extends IngestionError {
  constructor(message = 'Failed to acquire GitHub repository.', details = {}) {
    super(message, 'github_acquisition_failed', 502, details);
  }
}

class GitHubRateLimitExceededError extends GitHubAcquisitionError {
  constructor(message = 'Repository not found or access denied.', details = {}) {
    super(message, details);
    this.code = 'github_rate_limit_exceeded';
    this.status = 429;
    this.statusCode = 429;
  }
}

class GitHubAccessDeniedError extends GitHubAcquisitionError {
  constructor(message = 'Repository not found or access denied.', details = {}) {
    super(message, details);
    this.code = 'github_access_denied';
    this.status = 403;
    this.statusCode = 403;
  }
}

class GitHubNetworkError extends GitHubAcquisitionError {
  constructor(
    message = 'GitHub repository acquisition failed due to network error.',
    details = {}
  ) {
    super(message, details);
    this.code = 'github_network_error';
    this.status = 503;
    this.statusCode = 503;
  }
}

class GitHubTimeoutError extends GitHubAcquisitionError {
  constructor(message = 'GitHub repository download timed out.', details = {}) {
    super(message, details);
    this.code = 'github_timeout';
    this.status = 504;
    this.statusCode = 504;
  }
}

class ServerPathNotAllowedError extends IngestionError {
  constructor(
    message = 'Server filesystem path is outside the allowed source roots.',
    details = {}
  ) {
    super(message, 'server_path_not_allowed', 403, details);
  }
}

class ServerPathNotFoundError extends IngestionError {
  constructor(message = 'Server filesystem path not found.', details = {}) {
    super(message, 'server_path_not_found', 404, details);
  }
}

class StorageOperationError extends IngestionError {
  constructor(message = 'Storage operation failed.', details = {}) {
    super(message, 'storage_operation_failed', 500, details);
  }
}

module.exports = {
  IngestionError,
  IngestionNotFoundError,
  ActiveIngestionExistsError,
  InvalidIngestionStateError,
  RevisionAlreadyExistsError,
  RevisionNotFoundError,
  SourceValidationError,
  MaxFileCountExceededError,
  UnsupportedArchiveFormatError,
  InvalidSourceTypeError,
  InvalidGitHubUrlError,
  InvalidGitHubRefError,
  GitHubRepositoryNotFoundError,
  GitHubAcquisitionError,
  GitHubRateLimitExceededError,
  GitHubAccessDeniedError,
  GitHubNetworkError,
  GitHubTimeoutError,
  ServerPathNotAllowedError,
  ServerPathNotFoundError,
  StorageOperationError,
};
