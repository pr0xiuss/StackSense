/**
 * Request validation middleware for Platform Transport and Intelligence routes.
 *
 * Enforces strict query parameter allowlists, scalar checks, UUIDv4/v5 formats,
 * integer bounds, enum vocabularies, cursor bounds, query byte limits (<=32 KiB),
 * JSON body limits (<=128 KiB), and route/body scope matching mirroring frozen C0-C4 contracts.
 */

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const APPROVED_DIAGRAM_TEMPLATES = new Set([
  'system_overview',
  'component_architecture',
  'dependency_map',
  'data_flow',
]);

const SEARCH_MODES = new Set(['lexical', 'semantic', 'hybrid']);
const EXPORT_FORMATS = new Set(['json', 'svg']);

const MAX_QUERY_BYTES = 32768; // 32 KiB
const MAX_BODY_BYTES = 131072; // 128 KiB
const MAX_FILTER_ELEMENTS = 50;

function isUuid(val) {
  return typeof val === 'string' && UUID_REGEX.test(val.trim());
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

function limitError(res, message, details = {}) {
  return res.status(413).json({
    error: {
      code: 'intelligence_transport_limit',
      message,
      details,
    },
  });
}

function checkQueryByteLimit(req, res) {
  const url = req.url || '';
  const queryIndex = url.indexOf('?');
  if (queryIndex !== -1) {
    const rawQuery = url.slice(queryIndex + 1);
    const byteLength = Buffer.byteLength(rawQuery, 'utf8');
    if (byteLength > MAX_QUERY_BYTES) {
      limitError(
        res,
        `Query string size of ${byteLength} bytes exceeds limit of ${MAX_QUERY_BYTES} bytes.`,
        { max_bytes: MAX_QUERY_BYTES, actual_bytes: byteLength }
      );
      return false;
    }
  }
  return true;
}

function checkDisallowedQueryKeys(req, res, allowedKeys) {
  const allowedSet = new Set(allowedKeys);
  const receivedKeys = Object.keys(req.query || {});
  for (const key of receivedKeys) {
    if (key.includes('[') || key.includes(']')) {
      validationError(res, `Bracket query parameter notation is forbidden: "${key}".`, {
        forbidden_key: key,
      });
      return false;
    }
    if (!allowedSet.has(key)) {
      validationError(res, `Unrecognized query parameter: "${key}".`, {
        unrecognized_key: key,
      });
      return false;
    }
  }
  return true;
}

function parseArrayParam(val) {
  if (val === undefined || val === null) return [];
  if (Array.isArray(val)) return val;
  return [val];
}

/**
 * Validates versionId path parameter.
 */
function validateVersionIdParam(req, res, next) {
  const { versionId } = req.params;
  if (!versionId || !isUuid(versionId)) {
    return validationError(res, 'versionId path parameter must be a valid UUID.', {
      versionId,
    });
  }
  next();
}

/**
 * Validates template path parameter.
 */
function validateDiagramTemplateParam(req, res, next) {
  const { template } = req.params;
  if (!template || !APPROVED_DIAGRAM_TEMPLATES.has(template)) {
    return validationError(
      res,
      `template path parameter must be one of: ${Array.from(APPROVED_DIAGRAM_TEMPLATES).join(', ')}.`,
      { template }
    );
  }
  next();
}

/**
 * Validates generationId path parameter.
 */
function validateGenerationIdParam(req, res, next) {
  const { generationId } = req.params;
  if (!generationId || !isUuid(generationId)) {
    return validationError(res, 'generationId path parameter must be a valid UUID.', {
      generationId,
    });
  }
  next();
}

/**
 * Validates reportId path parameter.
 */
function validateReportIdParam(req, res, next) {
  const { reportId } = req.params;
  if (!reportId || !isUuid(reportId)) {
    return validationError(res, 'reportId path parameter must be a valid UUID.', {
      reportId,
    });
  }
  next();
}

/**
 * Validates standard project_id query parameter.
 */
function validateProjectQuery(req, res, next) {
  if (!checkQueryByteLimit(req, res)) return;
  const projectId = req.query.project_id;
  if (!projectId || !isUuid(projectId)) {
    return validationError(res, 'project_id query parameter is required and must be a valid UUID.', {
      project_id: projectId,
    });
  }
  req.validatedQuery = { project_id: projectId.trim() };
  next();
}

/**
 * Validates empty query besides project_id.
 */
function validateExactProjectOnlyQuery(req, res, next) {
  if (!checkQueryByteLimit(req, res)) return;
  if (!checkDisallowedQueryKeys(req, res, ['project_id'])) return;
  const projectId = req.query.project_id;
  if (!projectId || !isUuid(projectId)) {
    return validationError(res, 'project_id query parameter is required and must be a valid UUID.', {
      project_id: projectId,
    });
  }
  req.validatedQuery = { project_id: projectId.trim() };
  next();
}

/**
 * Validates C1 Search query parameters.
 */
function validateSearchQuery(req, res, next) {
  if (!checkQueryByteLimit(req, res)) return;
  const allowed = [
    'project_id',
    'q',
    'mode',
    'document_kinds',
    'entity_kinds',
    'statuses',
    'limit',
    'cursor',
    'timeout_seconds',
  ];
  if (!checkDisallowedQueryKeys(req, res, allowed)) return;

  const projectId = req.query.project_id;
  if (!projectId || !isUuid(projectId)) {
    return validationError(res, 'project_id query parameter is required and must be a valid UUID.', {
      project_id: projectId,
    });
  }

  const validated = { project_id: projectId.trim() };

  if (req.query.q !== undefined) {
    if (typeof req.query.q !== 'string' || req.query.q.length > 500) {
      return validationError(res, 'q must be a string up to 500 characters.', { q: req.query.q });
    }
    validated.q = req.query.q;
  }

  if (req.query.mode !== undefined) {
    if (typeof req.query.mode !== 'string' || !SEARCH_MODES.has(req.query.mode)) {
      return validationError(res, `mode must be one of: ${Array.from(SEARCH_MODES).join(', ')}.`, {
        mode: req.query.mode,
      });
    }
    validated.mode = req.query.mode;
  }

  for (const filterKey of ['document_kinds', 'entity_kinds', 'statuses']) {
    if (req.query[filterKey] !== undefined) {
      const arr = parseArrayParam(req.query[filterKey]);
      if (arr.length > MAX_FILTER_ELEMENTS) {
        return validationError(res, `${filterKey} exceeds maximum of ${MAX_FILTER_ELEMENTS} filter elements.`, {
          actual_count: arr.length,
          max_count: MAX_FILTER_ELEMENTS,
        });
      }
      for (const item of arr) {
        if (typeof item !== 'string' || item.length === 0 || item.length > 100) {
          return validationError(res, `${filterKey} elements must be non-empty strings up to 100 characters.`, {
            item,
          });
        }
      }
      validated[filterKey] = arr;
    }
  }

  if (req.query.limit !== undefined) {
    const parsed = parseInt(req.query.limit, 10);
    if (isNaN(parsed) || String(parsed) !== String(req.query.limit) || parsed < 1 || parsed > 100) {
      return validationError(res, 'limit must be an integer between 1 and 100.', { limit: req.query.limit });
    }
    validated.limit = parsed;
  }

  if (req.query.cursor !== undefined) {
    if (typeof req.query.cursor !== 'string' || req.query.cursor.length > 2048) {
      return validationError(res, 'cursor must be a string up to 2048 characters.', { cursor: req.query.cursor });
    }
    validated.cursor = req.query.cursor;
  }

  if (req.query.timeout_seconds !== undefined) {
    const parsed = parseFloat(req.query.timeout_seconds);
    if (isNaN(parsed) || parsed < 0.1 || parsed > 5.0) {
      return validationError(res, 'timeout_seconds must be a float between 0.1 and 5.0.', {
        timeout_seconds: req.query.timeout_seconds,
      });
    }
    validated.timeout_seconds = parsed;
  }

  req.validatedQuery = validated;
  next();
}

/**
 * Validates C3 Evidence query parameters: exactly one selector family must be present.
 */
function validateEvidenceQuery(req, res, next) {
  if (!checkQueryByteLimit(req, res)) return;
  const allowed = [
    'project_id',
    'entity_id',
    'relationship_id',
    'evidence_id',
    'limit',
    'cursor',
  ];
  if (!checkDisallowedQueryKeys(req, res, allowed)) return;

  const projectId = req.query.project_id;
  if (!projectId || !isUuid(projectId)) {
    return validationError(res, 'project_id query parameter is required and must be a valid UUID.', {
      project_id: projectId,
    });
  }

  const validated = { project_id: projectId.trim() };

  const familiesPresent = [
    req.query.entity_id !== undefined ? 'entity_id' : null,
    req.query.relationship_id !== undefined ? 'relationship_id' : null,
    req.query.evidence_id !== undefined ? 'evidence_id' : null,
  ].filter(Boolean);

  if (familiesPresent.length !== 1) {
    return validationError(
      res,
      'Exactly one evidence selector family must be provided: entity_id, relationship_id, or evidence_id.',
      { families_present: familiesPresent }
    );
  }

  const familyKey = familiesPresent[0];
  const items = parseArrayParam(req.query[familyKey]);
  if (items.length === 0 || items.length > MAX_FILTER_ELEMENTS) {
    return validationError(res, `${familyKey} must contain between 1 and ${MAX_FILTER_ELEMENTS} items.`, {
      actual_count: items.length,
      max_count: MAX_FILTER_ELEMENTS,
    });
  }

  for (const item of items) {
    if (familyKey === 'evidence_id') {
      if (typeof item !== 'string' || item.length === 0 || item.length > 256) {
        return validationError(res, 'evidence_id items must be strings up to 256 characters.', { item });
      }
    } else if (!isUuid(item)) {
      return validationError(res, `${familyKey} items must be valid UUIDs.`, { item });
    }
  }
  validated[familyKey] = items;

  if (req.query.limit !== undefined) {
    const parsed = parseInt(req.query.limit, 10);
    if (isNaN(parsed) || String(parsed) !== String(req.query.limit) || parsed < 1 || parsed > 100) {
      return validationError(res, 'limit must be an integer between 1 and 100.', { limit: req.query.limit });
    }
    validated.limit = parsed;
  }

  if (req.query.cursor !== undefined) {
    if (typeof req.query.cursor !== 'string' || req.query.cursor.length > 4096) {
      return validationError(res, 'cursor must be a string up to 4096 characters.', { cursor: req.query.cursor });
    }
    validated.cursor = req.query.cursor;
  }

  req.validatedQuery = validated;
  next();
}

/**
 * Validates C2 Diagram Summary query parameters (optional generation_id).
 */
function validateDiagramSummaryQuery(req, res, next) {
  if (!checkQueryByteLimit(req, res)) return;
  if (!checkDisallowedQueryKeys(req, res, ['project_id', 'generation_id'])) return;

  const projectId = req.query.project_id;
  if (!projectId || !isUuid(projectId)) {
    return validationError(res, 'project_id query parameter is required and must be a valid UUID.', {
      project_id: projectId,
    });
  }

  const validated = { project_id: projectId.trim() };
  if (req.query.generation_id !== undefined) {
    if (!isUuid(req.query.generation_id)) {
      return validationError(res, 'generation_id query parameter must be a valid UUID.', {
        generation_id: req.query.generation_id,
      });
    }
    validated.generation_id = req.query.generation_id.trim();
  }

  req.validatedQuery = validated;
  next();
}

/**
 * Validates C2 Diagram Generations query parameters.
 */
function validateDiagramGenerationsQuery(req, res, next) {
  if (!checkQueryByteLimit(req, res)) return;
  if (!checkDisallowedQueryKeys(req, res, ['project_id', 'limit', 'cursor'])) return;

  const projectId = req.query.project_id;
  if (!projectId || !isUuid(projectId)) {
    return validationError(res, 'project_id query parameter is required and must be a valid UUID.', {
      project_id: projectId,
    });
  }

  const validated = { project_id: projectId.trim() };

  if (req.query.limit !== undefined) {
    const parsed = parseInt(req.query.limit, 10);
    if (isNaN(parsed) || String(parsed) !== String(req.query.limit) || parsed < 1 || parsed > 200) {
      return validationError(res, 'limit must be an integer between 1 and 200.', { limit: req.query.limit });
    }
    validated.limit = parsed;
  }

  if (req.query.cursor !== undefined) {
    if (typeof req.query.cursor !== 'string' || req.query.cursor.length > 4096) {
      return validationError(res, 'cursor must be a string up to 4096 characters.', { cursor: req.query.cursor });
    }
    validated.cursor = req.query.cursor;
  }

  req.validatedQuery = validated;
  next();
}

/**
 * Validates C2 Diagram Members query parameters.
 */
function validateDiagramMembersQuery(req, res, next) {
  if (!checkQueryByteLimit(req, res)) return;
  const allowed = ['project_id', 'group_id', 'entity_id', 'limit', 'cursor'];
  if (!checkDisallowedQueryKeys(req, res, allowed)) return;

  const projectId = req.query.project_id;
  if (!projectId || !isUuid(projectId)) {
    return validationError(res, 'project_id query parameter is required and must be a valid UUID.', {
      project_id: projectId,
    });
  }

  const validated = { project_id: projectId.trim() };

  if (req.query.group_id !== undefined && req.query.entity_id !== undefined) {
    return validationError(res, 'group_id and entity_id cannot both be provided.', {});
  }

  if (req.query.group_id !== undefined) {
    if (typeof req.query.group_id !== 'string' || req.query.group_id.length > 67) {
      return validationError(res, 'group_id must be a string up to 67 characters.', {
        group_id: req.query.group_id,
      });
    }
    validated.group_id = req.query.group_id;
  }

  if (req.query.entity_id !== undefined) {
    if (!isUuid(req.query.entity_id)) {
      return validationError(res, 'entity_id must be a valid UUID.', {
        entity_id: req.query.entity_id,
      });
    }
    validated.entity_id = req.query.entity_id.trim();
  }

  if (req.query.limit !== undefined) {
    const parsed = parseInt(req.query.limit, 10);
    if (isNaN(parsed) || String(parsed) !== String(req.query.limit) || parsed < 1 || parsed > 200) {
      return validationError(res, 'limit must be an integer between 1 and 200.', { limit: req.query.limit });
    }
    validated.limit = parsed;
  }

  if (req.query.cursor !== undefined) {
    if (typeof req.query.cursor !== 'string' || req.query.cursor.length > 4096) {
      return validationError(res, 'cursor must be a string up to 4096 characters.', { cursor: req.query.cursor });
    }
    validated.cursor = req.query.cursor;
  }

  req.validatedQuery = validated;
  next();
}

/**
 * Validates C2 Diagram Export query parameters.
 */
function validateDiagramExportQuery(req, res, next) {
  if (!checkQueryByteLimit(req, res)) return;
  if (!checkDisallowedQueryKeys(req, res, ['project_id', 'format'])) return;

  const projectId = req.query.project_id;
  if (!projectId || !isUuid(projectId)) {
    return validationError(res, 'project_id query parameter is required and must be a valid UUID.', {
      project_id: projectId,
    });
  }

  const validated = { project_id: projectId.trim(), format: 'json' };

  if (req.query.format !== undefined) {
    if (!EXPORT_FORMATS.has(req.query.format)) {
      return validationError(res, 'format query parameter must be "json" or "svg".', {
        format: req.query.format,
      });
    }
    validated.format = req.query.format;
  }

  req.validatedQuery = validated;
  next();
}

/**
 * Validates C4 Report Collection & History query parameters.
 */
function validateReportPageQuery(req, res, next) {
  if (!checkQueryByteLimit(req, res)) return;
  if (!checkDisallowedQueryKeys(req, res, ['project_id', 'limit', 'cursor'])) return;

  const projectId = req.query.project_id;
  if (!projectId || !isUuid(projectId)) {
    return validationError(res, 'project_id query parameter is required and must be a valid UUID.', {
      project_id: projectId,
    });
  }

  const validated = { project_id: projectId.trim() };

  if (req.query.limit !== undefined) {
    const parsed = parseInt(req.query.limit, 10);
    if (isNaN(parsed) || String(parsed) !== String(req.query.limit) || parsed < 1 || parsed > 100) {
      return validationError(res, 'limit must be an integer between 1 and 100.', { limit: req.query.limit });
    }
    validated.limit = parsed;
  }

  if (req.query.cursor !== undefined) {
    if (typeof req.query.cursor !== 'string' || req.query.cursor.length > 4096) {
      return validationError(res, 'cursor must be a string up to 4096 characters.', { cursor: req.query.cursor });
    }
    validated.cursor = req.query.cursor;
  }

  req.validatedQuery = validated;
  next();
}

/**
 * Validates C4 Report Summary query parameters (optional generation_id).
 */
function validateReportSummaryQuery(req, res, next) {
  if (!checkQueryByteLimit(req, res)) return;
  if (!checkDisallowedQueryKeys(req, res, ['project_id', 'generation_id'])) return;

  const projectId = req.query.project_id;
  if (!projectId || !isUuid(projectId)) {
    return validationError(res, 'project_id query parameter is required and must be a valid UUID.', {
      project_id: projectId,
    });
  }

  const validated = { project_id: projectId.trim() };
  if (req.query.generation_id !== undefined) {
    if (!isUuid(req.query.generation_id)) {
      return validationError(res, 'generation_id query parameter must be a valid UUID.', {
        generation_id: req.query.generation_id,
      });
    }
    validated.generation_id = req.query.generation_id.trim();
  }

  req.validatedQuery = validated;
  next();
}

/**
 * Validates JSON request body size and scope agreement.
 */
function validateJsonBody(req, res) {
  if (req.body === undefined || req.body === null || typeof req.body !== 'object') {
    validationError(res, 'Request body must be a JSON object.', {});
    return false;
  }

  const strBody = JSON.stringify(req.body);
  const byteLength = Buffer.byteLength(strBody, 'utf8');
  if (byteLength > MAX_BODY_BYTES) {
    limitError(
      res,
      `Request body size of ${byteLength} bytes exceeds limit of ${MAX_BODY_BYTES} bytes.`,
      { max_bytes: MAX_BODY_BYTES, actual_bytes: byteLength }
    );
    return false;
  }

  // Check route-body scope agreement
  const queryProjectId = req.validatedQuery ? req.validatedQuery.project_id : req.query.project_id;
  if (req.body.project_id !== undefined && queryProjectId) {
    if (String(req.body.project_id).trim() !== String(queryProjectId).trim()) {
      validationError(res, 'Body project_id does not match route project_id.', {
        body_project_id: req.body.project_id,
        route_project_id: queryProjectId,
      });
      return false;
    }
  }

  const paramVersionId = req.params ? req.params.versionId : undefined;
  if (req.body.architecture_version_id !== undefined && paramVersionId) {
    if (String(req.body.architecture_version_id).trim() !== String(paramVersionId).trim()) {
      validationError(res, 'Body architecture_version_id does not match route versionId.', {
        body_version_id: req.body.architecture_version_id,
        route_version_id: paramVersionId,
      });
      return false;
    }
  }
  if (req.body.version_id !== undefined && paramVersionId) {
    if (String(req.body.version_id).trim() !== String(paramVersionId).trim()) {
      validationError(res, 'Body version_id does not match route versionId.', {
        body_version_id: req.body.version_id,
        route_version_id: paramVersionId,
      });
      return false;
    }
  }

  return true;
}

/**
 * Validates C0 Delivery Retry request body.
 */
function validateDeliveryRetryBody(req, res, next) {
  if (!validateJsonBody(req, res)) return;
  const { resource_type, resource_id, idempotency_key } = req.body;
  if (!resource_type || typeof resource_type !== 'string') {
    return validationError(res, 'resource_type is required and must be a string.', { resource_type });
  }
  if (!resource_id || !isUuid(resource_id)) {
    return validationError(res, 'resource_id is required and must be a valid UUID.', { resource_id });
  }
  if (!idempotency_key || !isUuid(idempotency_key)) {
    return validationError(res, 'idempotency_key is required and must be a valid UUID.', { idempotency_key });
  }
  next();
}

/**
 * Validates C1 Search Rebuild request body.
 */
function validateSearchRebuildBody(req, res, next) {
  if (!validateJsonBody(req, res)) return;
  const { idempotency_key } = req.body;
  if (!idempotency_key || !isUuid(idempotency_key)) {
    return validationError(res, 'idempotency_key is required and must be a valid UUID.', { idempotency_key });
  }
  next();
}

/**
 * Validates C3 Knowledge Query request body.
 */
function validateKnowledgeQueryBody(req, res, next) {
  if (!validateJsonBody(req, res)) return;
  next();
}

/**
 * Validates C3 Context request body.
 */
function validateContextBody(req, res, next) {
  if (!validateJsonBody(req, res)) return;
  next();
}

/**
 * Validates C2 Diagram View request body.
 */
function validateDiagramViewBody(req, res, next) {
  if (!validateJsonBody(req, res)) return;
  next();
}

module.exports = {
  isUuid,
  validationError,
  limitError,
  validateVersionIdParam,
  validateDiagramTemplateParam,
  validateGenerationIdParam,
  validateReportIdParam,
  validateProjectQuery,
  validateExactProjectOnlyQuery,
  validateSearchQuery,
  validateEvidenceQuery,
  validateDiagramSummaryQuery,
  validateDiagramGenerationsQuery,
  validateDiagramMembersQuery,
  validateDiagramExportQuery,
  validateReportPageQuery,
  validateReportSummaryQuery,
  validateDeliveryRetryBody,
  validateSearchRebuildBody,
  validateKnowledgeQueryBody,
  validateContextBody,
  validateDiagramViewBody,
};
