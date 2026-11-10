/**
 * Error classes for Analysis Gateway and Proxy operations.
 */

class AnalysisGatewayError extends Error {
  constructor(message, code, status = 502, details = {}) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.status = status;
    this.statusCode = status;
    this.details = details;
    Error.captureStackTrace(this, this.constructor);
  }
}

class AnalysisServiceError extends AnalysisGatewayError {
  constructor(message = 'Analysis service encountered an unexpected error.', details = {}) {
    super(message, 'analysis_service_error', 502, details);
  }
}

class AnalysisServiceUnavailableError extends AnalysisGatewayError {
  constructor(message = 'Analysis service is currently unavailable.', details = {}) {
    super(message, 'analysis_service_unavailable', 503, details);
  }
}

class AnalysisServiceTimeoutError extends AnalysisGatewayError {
  constructor(message = 'Analysis service request timed out.', details = {}) {
    super(message, 'analysis_service_timeout', 504, details);
  }
}

class AnalysisValidationError extends AnalysisGatewayError {
  constructor(message = 'Validation failed.', details = {}) {
    super(message, 'validation_error', 422, details);
  }
}

class AnalysisNotFoundError extends AnalysisGatewayError {
  constructor(message = 'Resource not found.', details = {}) {
    super(message, 'not_found', 404, details);
  }
}

module.exports = {
  AnalysisGatewayError,
  AnalysisServiceError,
  AnalysisServiceUnavailableError,
  AnalysisServiceTimeoutError,
  AnalysisValidationError,
  AnalysisNotFoundError,
};

