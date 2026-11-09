const Repository = require('../models/Repository');
const RepositoryRevision = require('../models/RepositoryRevision');
const { RepositoryNotFoundError } = require('../errors/repositoryErrors');
const { RevisionNotFoundError } = require('../errors/ingestionErrors');

const UUID_V4_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const CANONICAL_STATUSES = new Set([
  'created',
  'queued',
  'running',
  'partial',
  'completed',
  'completed_with_warnings',
  'failed',
  'cancel_requested',
  'cancelled',
  'timeout',
]);

const DIAGNOSTIC_SEVERITIES = new Set(['info', 'warning', 'error', 'critical']);

function isUuid(val) {
  return typeof val === 'string' && UUID_V4_REGEX.test(val);
}

function validationError(res, message, details = {}) {
  return res.status(422).json({
    error: {
      code: 'validation_error',
      message,
      details,
    },
  });
}

function validateProjectQuery(req, res, next) {
  const { project_id } = req.query;
  if (!project_id || !isUuid(project_id)) {
    return validationError(res, 'Valid project_id query parameter is required.', {
      project_id,
    });
  }
  next();
}

function validateAnalysisIdParam(req, res, next) {
  const { analysisId } = req.params;
  if (!analysisId || !isUuid(analysisId)) {
    return validationError(res, 'Valid analysisId parameter is required.', {
      analysisId,
    });
  }
  next();
}

function validateVersionIdParam(req, res, next) {
  const { versionId } = req.params;
  if (!versionId || !isUuid(versionId)) {
    return validationError(res, 'Valid versionId parameter is required.', {
      versionId,
    });
  }
  next();
}

function validateEntityIdParam(req, res, next) {
  const { entityId } = req.params;
  if (!entityId || !isUuid(entityId)) {
    return validationError(res, 'Valid entityId parameter is required.', {
      entityId,
    });
  }
  next();
}

function validateCreateAnalysis(req, res, next) {
  const body = req.body;
  if (!body || typeof body !== 'object') {
    return validationError(res, 'Request body is required.');
  }

  const {
    project_id,
    repository_id,
    revision_id,
    include_paths,
    exclude_paths,
    max_file_size_bytes,
    timeout_seconds,
    idempotency_key,
  } = body;

  if (!project_id || !isUuid(project_id)) {
    return validationError(res, 'Valid project_id is required in request body.', {
      field: 'project_id',
    });
  }
  if (!repository_id || !isUuid(repository_id)) {
    return validationError(res, 'Valid repository_id is required in request body.', {
      field: 'repository_id',
    });
  }
  if (!revision_id || !isUuid(revision_id)) {
    return validationError(res, 'Valid revision_id is required in request body.', {
      field: 'revision_id',
    });
  }

  if (include_paths !== undefined) {
    if (!Array.isArray(include_paths) || include_paths.length > 1000) {
      return validationError(res, 'include_paths must be an array of at most 1000 paths.', {
        field: 'include_paths',
      });
    }
    for (const p of include_paths) {
      if (typeof p !== 'string' || p.length < 1 || p.length > 4096) {
        return validationError(res, 'Each path in include_paths must be 1 to 4096 characters.', {
          field: 'include_paths',
        });
      }
    }
  }

  if (exclude_paths !== undefined) {
    if (!Array.isArray(exclude_paths) || exclude_paths.length > 1000) {
      return validationError(res, 'exclude_paths must be an array of at most 1000 paths.', {
        field: 'exclude_paths',
      });
    }
    for (const p of exclude_paths) {
      if (typeof p !== 'string' || p.length < 1 || p.length > 4096) {
        return validationError(res, 'Each path in exclude_paths must be 1 to 4096 characters.', {
          field: 'exclude_paths',
        });
      }
    }
  }

  if (max_file_size_bytes !== undefined) {
    const size = parseInt(max_file_size_bytes, 10);
    if (isNaN(size) || size < 1 || size > 52428800) {
      return validationError(res, 'max_file_size_bytes must be between 1 and 52428800 (50 MiB).', {
        field: 'max_file_size_bytes',
      });
    }
  }

  if (timeout_seconds !== undefined) {
    const timeout = parseInt(timeout_seconds, 10);
    if (isNaN(timeout) || timeout < 1 || timeout > 1800) {
      return validationError(res, 'timeout_seconds must be an integer between 1 and 1800 seconds.', {
        field: 'timeout_seconds',
      });
    }
  }

  if (idempotency_key !== undefined) {
    if (typeof idempotency_key !== 'string' || !idempotency_key.trim() || idempotency_key.length > 255) {
      return validationError(res, 'idempotency_key must be a non-empty string of at most 255 characters.', {
        field: 'idempotency_key',
      });
    }
  }

  next();
}

/**
 * Verify repository and revision chain exist for the given project.
 */
async function verifyChainForCreate(req, res, next) {
  try {
    const { project_id, repository_id, revision_id } = req.body;
    const repo = await Repository.findOne({ _id: repository_id, project_id });
    if (!repo) {
      throw new RepositoryNotFoundError('Repository not found in the specified project.', {
        projectId: project_id,
        repositoryId: repository_id,
      });
    }

    const revision = await RepositoryRevision.findOne({
      _id: revision_id,
      project_id,
      repository_id,
    });
    if (!revision) {
      throw new RevisionNotFoundError('Revision not found for this repository.', {
        projectId: project_id,
        repositoryId: repository_id,
        revisionId: revision_id,
      });
    }

    next();
  } catch (err) {
    next(err);
  }
}

function validateCancelAnalysis(req, res, next) {
  const projectId = req.query.project_id || (req.body && req.body.project_id);
  if (!projectId || !isUuid(projectId)) {
    return validationError(res, 'Valid project_id is required.', { field: 'project_id' });
  }

  if (req.body && req.body.reason !== undefined && req.body.reason !== null) {
    if (typeof req.body.reason !== 'string' || req.body.reason.length > 1000) {
      return validationError(res, 'Cancellation reason must be a string of at most 1000 characters.', {
        field: 'reason',
      });
    }
  }

  next();
}

function validateListAnalysesQuery(req, res, next) {
  const { project_id, repository_id, limit, offset, status } = req.query;
  if (!project_id || !isUuid(project_id)) {
    return validationError(res, 'Valid project_id query parameter is required.', {
      project_id,
    });
  }

  if (repository_id && !isUuid(repository_id)) {
    return validationError(res, 'repository_id query parameter must be a valid UUID.', {
      repository_id,
    });
  }

  if (limit !== undefined) {
    const parsedLimit = parseInt(limit, 10);
    if (isNaN(parsedLimit) || parsedLimit < 1 || parsedLimit > 100) {
      return validationError(res, 'limit must be an integer between 1 and 100.', {
        limit,
      });
    }
  }

  if (offset !== undefined) {
    const parsedOffset = parseInt(offset, 10);
    if (isNaN(parsedOffset) || parsedOffset < 0) {
      return validationError(res, 'offset must be a non-negative integer.', {
        offset,
      });
    }
  }

  if (status && !CANONICAL_STATUSES.has(status.toLowerCase())) {
    return validationError(res, `status must be one of: ${[...CANONICAL_STATUSES].join(', ')}.`, {
      status,
    });
  }

  next();
}

function validateDiagnosticsQuery(req, res, next) {
  const { project_id, limit, offset, severity, stage } = req.query;
  if (!project_id || !isUuid(project_id)) {
    return validationError(res, 'Valid project_id query parameter is required.', {
      project_id,
    });
  }

  if (limit !== undefined) {
    const parsedLimit = parseInt(limit, 10);
    if (isNaN(parsedLimit) || parsedLimit < 1 || parsedLimit > 100) {
      return validationError(res, 'limit must be an integer between 1 and 100.', {
        limit,
      });
    }
  }

  if (offset !== undefined) {
    const parsedOffset = parseInt(offset, 10);
    if (isNaN(parsedOffset) || parsedOffset < 0) {
      return validationError(res, 'offset must be a non-negative integer.', {
        offset,
      });
    }
  }

  if (severity && !DIAGNOSTIC_SEVERITIES.has(severity.toLowerCase())) {
    return validationError(res, `severity must be one of: ${[...DIAGNOSTIC_SEVERITIES].join(', ')}.`, {
      severity,
    });
  }

  if (stage !== undefined && (typeof stage !== 'string' || stage.length > 100)) {
    return validationError(res, 'stage must be a string of at most 100 characters.', {
      stage,
    });
  }

  next();
}

function validateArchitectureCollectionQuery(req, res, next) {
  const { project_id, limit, offset, kind, status, entity_id } = req.query;
  if (!project_id || !isUuid(project_id)) {
    return validationError(res, 'Valid project_id query parameter is required.', {
      project_id,
    });
  }

  if (entity_id && !isUuid(entity_id)) {
    return validationError(res, 'entity_id query parameter must be a valid UUID.', {
      entity_id,
    });
  }

  if (limit !== undefined) {
    const parsedLimit = parseInt(limit, 10);
    if (isNaN(parsedLimit) || parsedLimit < 1 || parsedLimit > 100) {
      return validationError(res, 'limit must be an integer between 1 and 100.', {
        limit,
      });
    }
  }

  if (offset !== undefined) {
    const parsedOffset = parseInt(offset, 10);
    if (isNaN(parsedOffset) || parsedOffset < 0) {
      return validationError(res, 'offset must be a non-negative integer.', {
        offset,
      });
    }
  }

  if (kind !== undefined && (typeof kind !== 'string' || kind.length > 100)) {
    return validationError(res, 'kind must be a string of at most 100 characters.', {
      kind,
    });
  }

  if (status !== undefined && (typeof status !== 'string' || status.length > 100)) {
    return validationError(res, 'status must be a string of at most 100 characters.', {
      status,
    });
  }

  next();
}

module.exports = {
  isUuid,
  validateProjectQuery,
  validateAnalysisIdParam,
  validateVersionIdParam,
  validateEntityIdParam,
  validateCreateAnalysis,
  verifyChainForCreate,
  validateCancelAnalysis,
  validateListAnalysesQuery,
  validateDiagnosticsQuery,
  validateArchitectureCollectionQuery,
};

