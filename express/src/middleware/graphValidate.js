/**
 * Request validation middleware for Architecture Graph routes.
 *
 * Enforces strict parameter allowlists, scalar checks, UUID formats,
 * integer bounds, direction vocabularies, kind allowlists, and cursor bounds
 * mirroring frozen FastAPI P4-Q1/P4-D1 contracts.
 * Populates req.validatedQuery with sanitized values.
 */

const UUID_V4_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const APPROVED_DEPENDENCY_RELATIONSHIP_KINDS = new Set([
  'depends_on',
  'imports',
  'calls',
  'exposes',
  'consumes',
  'produces',
  'connects_to',
  'persists_to',
  'uses',
  'extends',
  'implements',
  'routes_to',
]);

const ALL_APPROVED_RELATIONSHIP_KINDS = new Set([
  'contains',
  ...APPROVED_DEPENDENCY_RELATIONSHIP_KINDS,
]);

const TRAVERSAL_DIRECTIONS = new Set(['incoming', 'outgoing', 'both']);
const CONTAINMENT_DIRECTIONS = new Set(['parents', 'children', 'both']);

const MAX_DEPTH = 5;
const MAX_NODES = 500;
const MAX_EDGES = 1000;
const MAX_PATHS = 25;
const MAX_PAGE_SIZE = 100;
const MAX_TIMEOUT_SECONDS = 5.0;
const MAX_CURSOR_LENGTH = 2048;

function isUuid(val) {
  return typeof val === 'string' && UUID_V4_REGEX.test(val.trim());
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

function checkDisallowedQueryKeys(req, res, allowedKeys) {
  const allowedSet = new Set(allowedKeys);
  const receivedKeys = Object.keys(req.query || {});
  const disallowed = receivedKeys.filter((key) => !allowedSet.has(key));
  if (disallowed.length > 0) {
    validationError(res, `Unexpected query parameters: ${disallowed.join(', ')}`, {
      unexpected_parameters: disallowed,
      allowed_parameters: allowedKeys,
    });
    return false;
  }
  return true;
}

function parseIntegerParam(val, name, min, max, res) {
  if (val === undefined || val === null) {
    return { ok: true, value: undefined };
  }
  if (Array.isArray(val) || typeof val !== 'string') {
    validationError(res, `Parameter ${name} must be a single scalar integer.`, { field: name });
    return { ok: false };
  }
  const trimmed = val.trim();
  if (!/^-?\d+$/.test(trimmed)) {
    validationError(res, `Parameter ${name} must be an integer.`, { field: name, value: val });
    return { ok: false };
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    validationError(
      res,
      `Parameter ${name} must be an integer between ${min} and ${max}.`,
      { field: name, min, max, value: parsed }
    );
    return { ok: false };
  }
  return { ok: true, value: parsed };
}

function parseFloatParam(val, name, minExcl, maxIncl, res) {
  if (val === undefined || val === null) {
    return { ok: true, value: undefined };
  }
  if (Array.isArray(val) || typeof val !== 'string') {
    validationError(res, `Parameter ${name} must be a single scalar number.`, { field: name });
    return { ok: false };
  }
  const parsed = Number(val.trim());
  if (!Number.isFinite(parsed) || parsed <= minExcl || parsed > maxIncl) {
    validationError(
      res,
      `Parameter ${name} must be a number greater than ${minExcl} and at most ${maxIncl}.`,
      { field: name, minExcl, maxIncl, value: val }
    );
    return { ok: false };
  }
  return { ok: true, value: parsed };
}

function parseCursorParam(val, res) {
  if (val === undefined || val === null) {
    return { ok: true, value: undefined };
  }
  if (Array.isArray(val) || typeof val !== 'string') {
    validationError(res, 'Cursor must be a single scalar string.', { field: 'cursor' });
    return { ok: false };
  }
  if (val.length > MAX_CURSOR_LENGTH) {
    validationError(
      res,
      `Cursor length exceeds maximum of ${MAX_CURSOR_LENGTH} characters.`,
      { field: 'cursor', length: val.length, max_length: MAX_CURSOR_LENGTH }
    );
    return { ok: false };
  }
  return { ok: true, value: val };
}

function parseKindsParam(val, paramName, allowedSet, res) {
  if (val === undefined || val === null) {
    return { ok: true, value: undefined };
  }
  let rawList = [];
  if (Array.isArray(val)) {
    rawList = val;
  } else if (typeof val === 'string') {
    rawList = [val];
  } else {
    validationError(res, `${paramName} must be a string or array of strings.`, { field: paramName });
    return { ok: false };
  }

  const result = [];
  for (const item of rawList) {
    if (typeof item !== 'string') {
      validationError(res, `Each item in ${paramName} must be a string.`, { field: paramName });
      return { ok: false };
    }
    if (item.includes(',')) {
      validationError(
        res,
        `${paramName} items must not be comma-separated strings; pass repeated query parameters instead.`,
        { field: paramName, value: item }
      );
      return { ok: false };
    }
    const cleanItem = item.trim();
    if (!allowedSet.has(cleanItem)) {
      validationError(res, `Invalid kind in ${paramName}: ${cleanItem}.`, {
        field: paramName,
        invalid_kind: cleanItem,
        allowed_kinds: Array.from(allowedSet),
      });
      return { ok: false };
    }
    result.push(cleanItem);
  }
  // Deduplicate and sort canonically
  const deduped = Array.from(new Set(result)).sort();
  return { ok: true, value: deduped };
}

function validateProjectQuery(req, res, next) {
  const { project_id } = req.query;
  if (!project_id || !isUuid(project_id) || Array.isArray(project_id)) {
    return validationError(res, 'Valid project_id query parameter is required.', {
      project_id,
    });
  }
  req.validatedQuery = req.validatedQuery || {};
  req.validatedQuery.project_id = project_id.trim();
  next();
}

function validateVersionIdParam(req, res, next) {
  const { versionId } = req.params;
  if (!versionId || !isUuid(versionId)) {
    return validationError(res, 'Valid versionId path parameter is required.', {
      versionId,
    });
  }
  next();
}

function validateEntityIdParam(req, res, next) {
  const { entityId } = req.params;
  if (!entityId || !isUuid(entityId)) {
    return validationError(res, 'Valid entityId path parameter is required.', {
      entityId,
    });
  }
  next();
}

function validateStatusQuery(req, res, next) {
  if (!checkDisallowedQueryKeys(req, res, ['project_id'])) return;
  next();
}

function validateRebuild(req, res, next) {
  if (!checkDisallowedQueryKeys(req, res, ['project_id'])) return;
  // Rebuild has no business payload: reject caller-supplied fields
  if (req.body && typeof req.body === 'object' && Object.keys(req.body).length > 0) {
    return validationError(res, 'Rebuild request must not contain a request body.', {
      unexpected_fields: Object.keys(req.body),
    });
  }
  next();
}

function validateNodeDetailQuery(req, res, next) {
  if (!checkDisallowedQueryKeys(req, res, ['project_id', 'timeout_seconds'])) return;

  const timeoutResult = parseFloatParam(req.query.timeout_seconds, 'timeout_seconds', 0, MAX_TIMEOUT_SECONDS, res);
  if (!timeoutResult.ok) return;

  req.validatedQuery = req.validatedQuery || {};
  if (timeoutResult.value !== undefined) {
    req.validatedQuery.timeout_seconds = timeoutResult.value;
  }
  next();
}

function validateWindowQuery(req, res, next) {
  const allowed = [
    'project_id',
    'node_limit',
    'edge_limit',
    'page_size',
    'canonical_kinds',
    'cursor',
    'timeout_seconds',
  ];
  if (!checkDisallowedQueryKeys(req, res, allowed)) return;

  const nodeResult = parseIntegerParam(req.query.node_limit, 'node_limit', 1, MAX_NODES, res);
  if (!nodeResult.ok) return;

  const edgeResult = parseIntegerParam(req.query.edge_limit, 'edge_limit', 1, MAX_EDGES, res);
  if (!edgeResult.ok) return;

  const pageResult = parseIntegerParam(req.query.page_size, 'page_size', 1, MAX_PAGE_SIZE, res);
  if (!pageResult.ok) return;

  const kindsResult = parseKindsParam(
    req.query.canonical_kinds,
    'canonical_kinds',
    ALL_APPROVED_RELATIONSHIP_KINDS,
    res
  );
  if (!kindsResult.ok) return;

  const cursorResult = parseCursorParam(req.query.cursor, res);
  if (!cursorResult.ok) return;

  const timeoutResult = parseFloatParam(req.query.timeout_seconds, 'timeout_seconds', 0, MAX_TIMEOUT_SECONDS, res);
  if (!timeoutResult.ok) return;

  req.validatedQuery = req.validatedQuery || {};
  if (nodeResult.value !== undefined) req.validatedQuery.node_limit = nodeResult.value;
  if (edgeResult.value !== undefined) req.validatedQuery.edge_limit = edgeResult.value;
  if (pageResult.value !== undefined) req.validatedQuery.page_size = pageResult.value;
  if (kindsResult.value !== undefined) req.validatedQuery.canonical_kinds = kindsResult.value;
  if (cursorResult.value !== undefined) req.validatedQuery.cursor = cursorResult.value;
  if (timeoutResult.value !== undefined) req.validatedQuery.timeout_seconds = timeoutResult.value;

  next();
}

function validateNeighborhoodQuery(req, res, next) {
  const allowed = [
    'project_id',
    'direction',
    'depth',
    'node_limit',
    'edge_limit',
    'relationship_kinds',
    'cursor',
    'timeout_seconds',
  ];
  if (!checkDisallowedQueryKeys(req, res, allowed)) return;

  const { direction } = req.query;
  if (direction !== undefined) {
    if (Array.isArray(direction) || typeof direction !== 'string' || !TRAVERSAL_DIRECTIONS.has(direction.trim())) {
      return validationError(
        res,
        `Invalid direction: ${direction}. Allowed directions: ${Array.from(TRAVERSAL_DIRECTIONS).join(', ')}.`,
        { field: 'direction', value: direction, allowed: Array.from(TRAVERSAL_DIRECTIONS) }
      );
    }
  }

  const depthResult = parseIntegerParam(req.query.depth, 'depth', 1, MAX_DEPTH, res);
  if (!depthResult.ok) return;

  const nodeResult = parseIntegerParam(req.query.node_limit, 'node_limit', 1, MAX_NODES, res);
  if (!nodeResult.ok) return;

  const edgeResult = parseIntegerParam(req.query.edge_limit, 'edge_limit', 1, MAX_EDGES, res);
  if (!edgeResult.ok) return;

  const kindsResult = parseKindsParam(
    req.query.relationship_kinds,
    'relationship_kinds',
    ALL_APPROVED_RELATIONSHIP_KINDS,
    res
  );
  if (!kindsResult.ok) return;

  const cursorResult = parseCursorParam(req.query.cursor, res);
  if (!cursorResult.ok) return;

  const timeoutResult = parseFloatParam(req.query.timeout_seconds, 'timeout_seconds', 0, MAX_TIMEOUT_SECONDS, res);
  if (!timeoutResult.ok) return;

  req.validatedQuery = req.validatedQuery || {};
  if (direction !== undefined) req.validatedQuery.direction = direction.trim();
  if (depthResult.value !== undefined) req.validatedQuery.depth = depthResult.value;
  if (nodeResult.value !== undefined) req.validatedQuery.node_limit = nodeResult.value;
  if (edgeResult.value !== undefined) req.validatedQuery.edge_limit = edgeResult.value;
  if (kindsResult.value !== undefined) req.validatedQuery.relationship_kinds = kindsResult.value;
  if (cursorResult.value !== undefined) req.validatedQuery.cursor = cursorResult.value;
  if (timeoutResult.value !== undefined) req.validatedQuery.timeout_seconds = timeoutResult.value;

  next();
}

function validateDependenciesQuery(req, res, next) {
  const allowed = [
    'project_id',
    'depth',
    'node_limit',
    'edge_limit',
    'relationship_kinds',
    'cursor',
    'timeout_seconds',
  ];
  if (!checkDisallowedQueryKeys(req, res, allowed)) return;

  const depthResult = parseIntegerParam(req.query.depth, 'depth', 1, MAX_DEPTH, res);
  if (!depthResult.ok) return;

  const nodeResult = parseIntegerParam(req.query.node_limit, 'node_limit', 1, MAX_NODES, res);
  if (!nodeResult.ok) return;

  const edgeResult = parseIntegerParam(req.query.edge_limit, 'edge_limit', 1, MAX_EDGES, res);
  if (!edgeResult.ok) return;

  const kindsResult = parseKindsParam(
    req.query.relationship_kinds,
    'relationship_kinds',
    APPROVED_DEPENDENCY_RELATIONSHIP_KINDS,
    res
  );
  if (!kindsResult.ok) return;

  const cursorResult = parseCursorParam(req.query.cursor, res);
  if (!cursorResult.ok) return;

  const timeoutResult = parseFloatParam(req.query.timeout_seconds, 'timeout_seconds', 0, MAX_TIMEOUT_SECONDS, res);
  if (!timeoutResult.ok) return;

  req.validatedQuery = req.validatedQuery || {};
  if (depthResult.value !== undefined) req.validatedQuery.depth = depthResult.value;
  if (nodeResult.value !== undefined) req.validatedQuery.node_limit = nodeResult.value;
  if (edgeResult.value !== undefined) req.validatedQuery.edge_limit = edgeResult.value;
  if (kindsResult.value !== undefined) req.validatedQuery.relationship_kinds = kindsResult.value;
  if (cursorResult.value !== undefined) req.validatedQuery.cursor = cursorResult.value;
  if (timeoutResult.value !== undefined) req.validatedQuery.timeout_seconds = timeoutResult.value;

  next();
}

function validateDependentsQuery(req, res, next) {
  // Same rules as dependencies
  return validateDependenciesQuery(req, res, next);
}

function validateContainmentQuery(req, res, next) {
  const allowed = [
    'project_id',
    'direction',
    'depth',
    'node_limit',
    'edge_limit',
    'cursor',
    'timeout_seconds',
  ];
  if (!checkDisallowedQueryKeys(req, res, allowed)) return;

  const { direction } = req.query;
  if (direction !== undefined) {
    if (Array.isArray(direction) || typeof direction !== 'string' || !CONTAINMENT_DIRECTIONS.has(direction.trim())) {
      return validationError(
        res,
        `Invalid direction: ${direction}. Allowed containment directions: ${Array.from(CONTAINMENT_DIRECTIONS).join(', ')}.`,
        { field: 'direction', value: direction, allowed: Array.from(CONTAINMENT_DIRECTIONS) }
      );
    }
  }

  const depthResult = parseIntegerParam(req.query.depth, 'depth', 1, MAX_DEPTH, res);
  if (!depthResult.ok) return;

  const nodeResult = parseIntegerParam(req.query.node_limit, 'node_limit', 1, MAX_NODES, res);
  if (!nodeResult.ok) return;

  const edgeResult = parseIntegerParam(req.query.edge_limit, 'edge_limit', 1, MAX_EDGES, res);
  if (!edgeResult.ok) return;

  const cursorResult = parseCursorParam(req.query.cursor, res);
  if (!cursorResult.ok) return;

  const timeoutResult = parseFloatParam(req.query.timeout_seconds, 'timeout_seconds', 0, MAX_TIMEOUT_SECONDS, res);
  if (!timeoutResult.ok) return;

  req.validatedQuery = req.validatedQuery || {};
  if (direction !== undefined) req.validatedQuery.direction = direction.trim();
  if (depthResult.value !== undefined) req.validatedQuery.depth = depthResult.value;
  if (nodeResult.value !== undefined) req.validatedQuery.node_limit = nodeResult.value;
  if (edgeResult.value !== undefined) req.validatedQuery.edge_limit = edgeResult.value;
  if (cursorResult.value !== undefined) req.validatedQuery.cursor = cursorResult.value;
  if (timeoutResult.value !== undefined) req.validatedQuery.timeout_seconds = timeoutResult.value;

  next();
}

function validatePathsQuery(req, res, next) {
  const allowed = [
    'project_id',
    'source_entity_id',
    'target_entity_id',
    'max_depth',
    'path_limit',
    'relationship_kinds',
    'timeout_seconds',
  ];
  if (!checkDisallowedQueryKeys(req, res, allowed)) return;

  const { source_entity_id, target_entity_id } = req.query;
  if (!source_entity_id || !isUuid(source_entity_id) || Array.isArray(source_entity_id)) {
    return validationError(res, 'Valid source_entity_id UUID query parameter is required.', {
      field: 'source_entity_id',
      value: source_entity_id,
    });
  }
  if (!target_entity_id || !isUuid(target_entity_id) || Array.isArray(target_entity_id)) {
    return validationError(res, 'Valid target_entity_id UUID query parameter is required.', {
      field: 'target_entity_id',
      value: target_entity_id,
    });
  }

  const depthResult = parseIntegerParam(req.query.max_depth, 'max_depth', 1, MAX_DEPTH, res);
  if (!depthResult.ok) return;

  const pathResult = parseIntegerParam(req.query.path_limit, 'path_limit', 1, MAX_PATHS, res);
  if (!pathResult.ok) return;

  const kindsResult = parseKindsParam(
    req.query.relationship_kinds,
    'relationship_kinds',
    APPROVED_DEPENDENCY_RELATIONSHIP_KINDS,
    res
  );
  if (!kindsResult.ok) return;

  const timeoutResult = parseFloatParam(req.query.timeout_seconds, 'timeout_seconds', 0, MAX_TIMEOUT_SECONDS, res);
  if (!timeoutResult.ok) return;

  req.validatedQuery = req.validatedQuery || {};
  req.validatedQuery.source_entity_id = source_entity_id.trim();
  req.validatedQuery.target_entity_id = target_entity_id.trim();
  if (depthResult.value !== undefined) req.validatedQuery.max_depth = depthResult.value;
  if (pathResult.value !== undefined) req.validatedQuery.path_limit = pathResult.value;
  if (kindsResult.value !== undefined) req.validatedQuery.relationship_kinds = kindsResult.value;
  if (timeoutResult.value !== undefined) req.validatedQuery.timeout_seconds = timeoutResult.value;

  next();
}

function validateNoQuery(req, res, next) {
  if (!checkDisallowedQueryKeys(req, res, [])) return;
  req.validatedQuery = {};
  next();
}

module.exports = {
  APPROVED_DEPENDENCY_RELATIONSHIP_KINDS,
  ALL_APPROVED_RELATIONSHIP_KINDS,
  TRAVERSAL_DIRECTIONS,
  CONTAINMENT_DIRECTIONS,
  validateProjectQuery,
  validateVersionIdParam,
  validateEntityIdParam,
  validateStatusQuery,
  validateRebuild,
  validateNodeDetailQuery,
  validateWindowQuery,
  validateNeighborhoodQuery,
  validateDependenciesQuery,
  validateDependentsQuery,
  validateContainmentQuery,
  validatePathsQuery,
  validateNoQuery,
};

