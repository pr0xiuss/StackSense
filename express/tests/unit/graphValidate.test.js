/**
 * Unit tests for Architecture Graph validation middleware.
 */
const {
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
} = require('../../src/middleware/graphValidate');

function createMockReqRes({ params = {}, query = {}, body = null } = {}) {
  const req = {
    params,
    query,
    body,
    headers: {},
  };
  const res = {
    statusCode: 200,
    body: null,
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(payload) {
      this.body = payload;
      return this;
    },
  };
  const next = jest.fn();
  return { req, res, next };
}

describe('graphValidate middleware unit tests', () => {
  const VALID_UUID_1 = 'a0000000-0000-0000-0000-000000000001';
  const VALID_UUID_2 = 'b0000000-0000-0000-0000-000000000002';
  const VALID_UUID_3 = 'c0000000-0000-0000-0000-000000000003';

  describe('UUID and param validators', () => {
    it('validateProjectQuery accepts valid UUID and populates req.validatedQuery', () => {
      const { req, res, next } = createMockReqRes({ query: { project_id: VALID_UUID_1 } });
      validateProjectQuery(req, res, next);
      expect(next).toHaveBeenCalledTimes(1);
      expect(req.validatedQuery.project_id).toBe(VALID_UUID_1);
    });

    it('validateProjectQuery rejects missing or invalid project_id with 422', () => {
      const { req, res, next } = createMockReqRes({ query: {} });
      validateProjectQuery(req, res, next);
      expect(res.statusCode).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
      expect(next).not.toHaveBeenCalled();

      const invalid = createMockReqRes({ query: { project_id: 'not-a-uuid' } });
      validateProjectQuery(invalid.req, invalid.res, invalid.next);
      expect(invalid.res.statusCode).toBe(422);
    });

    it('validateProjectQuery rejects duplicate (array) project_id with 422', () => {
      const { req, res, next } = createMockReqRes({
        query: { project_id: [VALID_UUID_1, VALID_UUID_2] },
      });
      validateProjectQuery(req, res, next);
      expect(res.statusCode).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    it('validateVersionIdParam validates versionId path parameter', () => {
      const valid = createMockReqRes({ params: { versionId: VALID_UUID_1 } });
      validateVersionIdParam(valid.req, valid.res, valid.next);
      expect(valid.next).toHaveBeenCalledTimes(1);

      const invalid = createMockReqRes({ params: { versionId: 'invalid' } });
      validateVersionIdParam(invalid.req, invalid.res, invalid.next);
      expect(invalid.res.statusCode).toBe(422);
    });

    it('validateEntityIdParam validates entityId path parameter', () => {
      const valid = createMockReqRes({ params: { entityId: VALID_UUID_1 } });
      validateEntityIdParam(valid.req, valid.res, valid.next);
      expect(valid.next).toHaveBeenCalledTimes(1);

      const invalid = createMockReqRes({ params: { entityId: 'invalid' } });
      validateEntityIdParam(invalid.req, invalid.res, invalid.next);
      expect(invalid.res.statusCode).toBe(422);
    });
  });

  describe('validateStatusQuery', () => {
    it('accepts project_id and rejects unexpected query parameters', () => {
      const valid = createMockReqRes({ query: { project_id: VALID_UUID_1 } });
      validateStatusQuery(valid.req, valid.res, valid.next);
      expect(valid.next).toHaveBeenCalledTimes(1);

      const invalid = createMockReqRes({ query: { project_id: VALID_UUID_1, foo: 'bar' } });
      validateStatusQuery(invalid.req, invalid.res, invalid.next);
      expect(invalid.res.statusCode).toBe(422);
      expect(invalid.res.body.error.code).toBe('validation_error');
    });
  });

  describe('validateRebuild', () => {
    it('accepts empty body and rejects caller-supplied body payload', () => {
      const valid = createMockReqRes({ query: { project_id: VALID_UUID_1 }, body: {} });
      validateRebuild(valid.req, valid.res, valid.next);
      expect(valid.next).toHaveBeenCalledTimes(1);

      const invalidBody = createMockReqRes({
        query: { project_id: VALID_UUID_1 },
        body: { role: 'OWNER', actor_id: 'fake' },
      });
      validateRebuild(invalidBody.req, invalidBody.res, invalidBody.next);
      expect(invalidBody.res.statusCode).toBe(422);
      expect(invalidBody.res.body.error.code).toBe('validation_error');
    });
  });

  describe('validateNodeDetailQuery', () => {
    it('accepts valid timeout_seconds within bounds', () => {
      const valid = createMockReqRes({
        query: { project_id: VALID_UUID_1, timeout_seconds: '3.5' },
      });
      validateNodeDetailQuery(valid.req, valid.res, valid.next);
      expect(valid.next).toHaveBeenCalledTimes(1);
      expect(valid.req.validatedQuery.timeout_seconds).toBe(3.5);
    });

    it('rejects timeout_seconds outside bounds or non-numeric', () => {
      const tooHigh = createMockReqRes({
        query: { project_id: VALID_UUID_1, timeout_seconds: '6.0' },
      });
      validateNodeDetailQuery(tooHigh.req, tooHigh.res, tooHigh.next);
      expect(tooHigh.res.statusCode).toBe(422);

      const nonNum = createMockReqRes({
        query: { project_id: VALID_UUID_1, timeout_seconds: 'fast' },
      });
      validateNodeDetailQuery(nonNum.req, nonNum.res, nonNum.next);
      expect(nonNum.res.statusCode).toBe(422);
    });
  });

  describe('validateWindowQuery', () => {
    it('normalizes repeated canonical_kinds, limits, and cursor', () => {
      const valid = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          node_limit: '100',
          edge_limit: '200',
          page_size: '50',
          canonical_kinds: ['imports', 'calls', 'imports'], // duplicate imports
          cursor: 'opaque_cursor_value',
          timeout_seconds: '2.0',
        },
      });
      validateWindowQuery(valid.req, valid.res, valid.next);
      expect(valid.next).toHaveBeenCalledTimes(1);
      expect(valid.req.validatedQuery.node_limit).toBe(100);
      expect(valid.req.validatedQuery.edge_limit).toBe(200);
      expect(valid.req.validatedQuery.page_size).toBe(50);
      // Canonical kinds deduplicated and sorted
      expect(valid.req.validatedQuery.canonical_kinds).toEqual(['calls', 'imports']);
      expect(valid.req.validatedQuery.cursor).toBe('opaque_cursor_value');
    });

    it('rejects comma-separated canonical_kinds', () => {
      const invalid = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          canonical_kinds: 'calls,imports',
        },
      });
      validateWindowQuery(invalid.req, invalid.res, invalid.next);
      expect(invalid.res.statusCode).toBe(422);
    });

    it('rejects overlong cursor (> 2048 chars)', () => {
      const invalid = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          cursor: 'a'.repeat(2049),
        },
      });
      validateWindowQuery(invalid.req, invalid.res, invalid.next);
      expect(invalid.res.statusCode).toBe(422);
    });

    it('rejects negative or fractional node_limit', () => {
      const negative = createMockReqRes({
        query: { project_id: VALID_UUID_1, node_limit: '-5' },
      });
      validateWindowQuery(negative.req, negative.res, negative.next);
      expect(negative.res.statusCode).toBe(422);

      const fractional = createMockReqRes({
        query: { project_id: VALID_UUID_1, node_limit: '50.5' },
      });
      validateWindowQuery(fractional.req, fractional.res, fractional.next);
      expect(fractional.res.statusCode).toBe(422);
    });
  });

  describe('validateNeighborhoodQuery', () => {
    it('accepts valid direction, depth, limits, and relationship_kinds including contains', () => {
      const valid = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          direction: 'both',
          depth: '2',
          node_limit: '50',
          edge_limit: '100',
          relationship_kinds: ['calls', 'contains'],
        },
      });
      validateNeighborhoodQuery(valid.req, valid.res, valid.next);
      expect(valid.next).toHaveBeenCalledTimes(1);
      expect(valid.req.validatedQuery.direction).toBe('both');
      expect(valid.req.validatedQuery.depth).toBe(2);
      expect(valid.req.validatedQuery.relationship_kinds).toEqual(['calls', 'contains']);
    });

    it('rejects invalid direction', () => {
      const invalid = createMockReqRes({
        query: { project_id: VALID_UUID_1, direction: 'sideways' },
      });
      validateNeighborhoodQuery(invalid.req, invalid.res, invalid.next);
      expect(invalid.res.statusCode).toBe(422);
    });
  });

  describe('validateDependenciesQuery and validateDependentsQuery', () => {
    it('accepts approved dependency kinds (excluding contains)', () => {
      const valid = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          depth: '3',
          relationship_kinds: ['depends_on', 'calls'],
        },
      });
      validateDependenciesQuery(valid.req, valid.res, valid.next);
      expect(valid.next).toHaveBeenCalledTimes(1);
      expect(valid.req.validatedQuery.relationship_kinds).toEqual(['calls', 'depends_on']);
    });

    it('strictly forbids contains in dependencies with 422', () => {
      const invalid = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          relationship_kinds: ['calls', 'contains'],
        },
      });
      validateDependenciesQuery(invalid.req, invalid.res, invalid.next);
      expect(invalid.res.statusCode).toBe(422);
      expect(invalid.res.body.error.code).toBe('validation_error');
    });

    it('strictly forbids contains in dependents with 422', () => {
      const invalid = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          relationship_kinds: 'contains',
        },
      });
      validateDependentsQuery(invalid.req, invalid.res, invalid.next);
      expect(invalid.res.statusCode).toBe(422);
    });
  });

  describe('validateContainmentQuery', () => {
    it('accepts parents/children/both direction and rejects relationship_kinds', () => {
      const valid = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          direction: 'children',
          depth: '2',
        },
      });
      validateContainmentQuery(valid.req, valid.res, valid.next);
      expect(valid.next).toHaveBeenCalledTimes(1);
      expect(valid.req.validatedQuery.direction).toBe('children');

      const invalidWithKinds = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          direction: 'children',
          relationship_kinds: 'contains',
        },
      });
      validateContainmentQuery(invalidWithKinds.req, invalidWithKinds.res, invalidWithKinds.next);
      expect(invalidWithKinds.res.statusCode).toBe(422);
    });
  });

  describe('validatePathsQuery', () => {
    it('accepts valid source/target entity UUIDs, max_depth, path_limit, and non-containment kinds', () => {
      const valid = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          source_entity_id: VALID_UUID_2,
          target_entity_id: VALID_UUID_3,
          max_depth: '3',
          path_limit: '10',
          relationship_kinds: ['calls', 'imports'],
        },
      });
      validatePathsQuery(valid.req, valid.res, valid.next);
      expect(valid.next).toHaveBeenCalledTimes(1);
      expect(valid.req.validatedQuery.source_entity_id).toBe(VALID_UUID_2);
      expect(valid.req.validatedQuery.target_entity_id).toBe(VALID_UUID_3);
      expect(valid.req.validatedQuery.max_depth).toBe(3);
      expect(valid.req.validatedQuery.path_limit).toBe(10);
      expect(valid.req.validatedQuery.relationship_kinds).toEqual(['calls', 'imports']);
    });

    it('rejects contains in paths query with 422', () => {
      const invalid = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          source_entity_id: VALID_UUID_2,
          target_entity_id: VALID_UUID_3,
          relationship_kinds: 'contains',
        },
      });
      validatePathsQuery(invalid.req, invalid.res, invalid.next);
      expect(invalid.res.statusCode).toBe(422);
    });

    it('rejects missing or non-UUID source or target entity IDs', () => {
      const missingTarget = createMockReqRes({
        query: {
          project_id: VALID_UUID_1,
          source_entity_id: VALID_UUID_2,
        },
      });
      validatePathsQuery(missingTarget.req, missingTarget.res, missingTarget.next);
      expect(missingTarget.res.statusCode).toBe(422);
    });
  });

  describe('validateNoQuery', () => {
    it('accepts empty query and rejects any query parameters', () => {
      const valid = createMockReqRes({ query: {} });
      validateNoQuery(valid.req, valid.res, valid.next);
      expect(valid.next).toHaveBeenCalledTimes(1);

      const invalid = createMockReqRes({ query: { project_id: VALID_UUID_1 } });
      validateNoQuery(invalid.req, invalid.res, invalid.next);
      expect(invalid.res.statusCode).toBe(422);
    });
  });
});

