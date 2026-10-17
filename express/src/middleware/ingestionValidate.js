const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const {
  normalizeSourceType,
} = require('../constants/ingestionConstants');

/**
 * Validate that req.params.ingestionId is a valid UUID v4.
 */
function validateIngestionId(req, res, next) {
  const { ingestionId } = req.params;

  if (!ingestionId || !UUID_V4_REGEX.test(ingestionId)) {
    return res.status(422).json({
      error: {
        code: 'invalid_ingestion_id',
        message: 'Ingestion ID must be a valid UUID v4.',
        details: { ingestionId },
      },
    });
  }

  next();
}

/**
 * Validate that req.params.revisionId is a valid UUID v4.
 */
function validateRevisionId(req, res, next) {
  const { revisionId } = req.params;

  if (!revisionId || !UUID_V4_REGEX.test(revisionId)) {
    return res.status(422).json({
      error: {
        code: 'invalid_revision_id',
        message: 'Revision ID must be a valid UUID v4.',
        details: { revisionId },
      },
    });
  }

  next();
}

/**
 * Validate payload for triggering repository ingestion.
 */
function validateStartIngestion(req, res, next) {
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

  const { source_type, source_reference, revision_identifier } = body;

  if (typeof source_type !== 'string' || !source_type.trim()) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'source_type is required and cannot be empty.',
        details: { field: 'source_type' },
      },
    });
  }

  try {
    normalizeSourceType(source_type);
  } catch (err) {
    return res.status(422).json({
      error: {
        code: 'invalid_source_type',
        message: err.message,
        details: { source_type },
      },
    });
  }

  if (typeof source_reference !== 'string' || !source_reference.trim()) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'source_reference is required and cannot be empty.',
        details: { field: 'source_reference' },
      },
    });
  }

  if (source_reference.trim().length > 1024) {
    return res.status(422).json({
      error: {
        code: 'validation_error',
        message: 'source_reference cannot exceed 1024 characters.',
        details: { field: 'source_reference' },
      },
    });
  }

  if (revision_identifier !== undefined && revision_identifier !== null) {
    if (typeof revision_identifier !== 'string') {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'revision_identifier must be a string when provided.',
          details: { field: 'revision_identifier' },
        },
      });
    }

    if (revision_identifier.trim().length > 255) {
      return res.status(422).json({
        error: {
          code: 'validation_error',
          message: 'revision_identifier cannot exceed 255 characters.',
          details: { field: 'revision_identifier' },
        },
      });
    }
  }

  next();
}

module.exports = {
  validateIngestionId,
  validateRevisionId,
  validateStartIngestion,
};
