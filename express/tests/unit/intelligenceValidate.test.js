const {
  isUuid,
  validateVersionIdParam,
  validateDiagramTemplateParam,
  validateGenerationIdParam,
  validateReportIdParam,
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
} = require('../../src/middleware/intelligenceValidate');

describe('intelligenceValidate Middleware Unit Tests', () => {
  const validUuidV4 = '11111111-2222-4333-8444-555555555555';
  const validUuidV5 = 'c4627196-8575-52bb-81c8-f5424cf961e6'; // UUIDv5
  const invalidUuid = 'not-a-uuid-at-all';

  function mockReqRes(overrides = {}) {
    const req = {
      params: {},
      query: {},
      body: {},
      url: '/test',
      ...overrides,
    };
    const res = {
      status: vi.fn().mockReturnThis(),
      json: vi.fn().mockReturnThis(),
    };
    const next = vi.fn();
    return { req, res, next };
  }

  describe('isUuid helper', () => {
    it('accepts valid UUIDv4 and UUIDv5', () => {
      expect(isUuid(validUuidV4)).toBe(true);
      expect(isUuid(validUuidV5)).toBe(true);
    });

    it('rejects invalid UUID strings', () => {
      expect(isUuid(invalidUuid)).toBe(false);
      expect(isUuid('')).toBe(false);
      expect(isUuid(null)).toBe(false);
      expect(isUuid(12345)).toBe(false);
    });
  });

  describe('Route Param Validators', () => {
    it('validateVersionIdParam accepts valid UUID and rejects invalid', () => {
      const { req: req1, res: res1, next: next1 } = mockReqRes({ params: { versionId: validUuidV5 } });
      validateVersionIdParam(req1, res1, next1);
      expect(next1).toHaveBeenCalled();

      const { req: req2, res: res2, next: next2 } = mockReqRes({ params: { versionId: invalidUuid } });
      validateVersionIdParam(req2, res2, next2);
      expect(res2.status).toHaveBeenCalledWith(422);
      expect(next2).not.toHaveBeenCalled();
    });

    it('validateDiagramTemplateParam enforces template vocabulary', () => {
      const validTemplates = ['system_overview', 'component_architecture', 'dependency_map', 'data_flow'];
      for (const t of validTemplates) {
        const { req, res, next } = mockReqRes({ params: { template: t } });
        validateDiagramTemplateParam(req, res, next);
        expect(next).toHaveBeenCalled();
      }

      const { req, res, next } = mockReqRes({ params: { template: 'invalid_template' } });
      validateDiagramTemplateParam(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(next).not.toHaveBeenCalled();
    });

    it('validateGenerationIdParam accepts valid UUID and rejects invalid', () => {
      const { req: req1, res: res1, next: next1 } = mockReqRes({ params: { generationId: validUuidV4 } });
      validateGenerationIdParam(req1, res1, next1);
      expect(next1).toHaveBeenCalled();

      const { req: req2, res: res2, next: next2 } = mockReqRes({ params: { generationId: invalidUuid } });
      validateGenerationIdParam(req2, res2, next2);
      expect(res2.status).toHaveBeenCalledWith(422);
    });

    it('validateReportIdParam accepts valid UUID and rejects invalid', () => {
      const { req: req1, res: res1, next: next1 } = mockReqRes({ params: { reportId: validUuidV4 } });
      validateReportIdParam(req1, res1, next1);
      expect(next1).toHaveBeenCalled();

      const { req: req2, res: res2, next: next2 } = mockReqRes({ params: { reportId: invalidUuid } });
      validateReportIdParam(req2, res2, next2);
      expect(res2.status).toHaveBeenCalledWith(422);
    });
  });

  describe('Query Validation and Size Limits', () => {
    it('rejects query exceeding 32 KiB with 413', () => {
      const hugeQuery = 'q=' + 'a'.repeat(33000);
      const { req, res, next } = mockReqRes({
        url: `/test?${hugeQuery}`,
        query: { q: 'a'.repeat(33000) },
      });
      validateExactProjectOnlyQuery(req, res, next);
      expect(res.status).toHaveBeenCalledWith(413);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({ code: 'intelligence_transport_limit' }),
        })
      );
    });

    it('rejects bracket notation in query keys', () => {
      const { req, res, next } = mockReqRes({
        query: { project_id: validUuidV4, 'document_kinds[]': 'file' },
      });
      validateSearchQuery(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({ code: 'validation_error' }),
        })
      );
    });

    it('rejects unrecognized query parameters', () => {
      const { req, res, next } = mockReqRes({
        query: { project_id: validUuidV4, extra_param: 'bad' },
      });
      validateExactProjectOnlyQuery(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
    });
  });

  describe('C1 Search Query Validator', () => {
    it('accepts valid search parameters and serializes repeated array filters', () => {
      const { req, res, next } = mockReqRes({
        query: {
          project_id: validUuidV4,
          q: 'AuthService',
          mode: 'lexical',
          document_kinds: ['file', 'symbol'],
          limit: '25',
          cursor: 'opaque_cursor_token',
          timeout_seconds: '2.5',
        },
      });
      validateSearchQuery(req, res, next);
      expect(next).toHaveBeenCalled();
      expect(req.validatedQuery).toEqual({
        project_id: validUuidV4,
        q: 'AuthService',
        mode: 'lexical',
        document_kinds: ['file', 'symbol'],
        limit: 25,
        cursor: 'opaque_cursor_token',
        timeout_seconds: 2.5,
      });
    });

    it('rejects search q exceeding 500 characters', () => {
      const { req, res, next } = mockReqRes({
        query: { project_id: validUuidV4, q: 'a'.repeat(501) },
      });
      validateSearchQuery(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
    });

    it('rejects filter arrays exceeding 50 elements', () => {
      const elements = Array.from({ length: 51 }, (_, i) => `item_${i}`);
      const { req, res, next } = mockReqRes({
        query: { project_id: validUuidV4, document_kinds: elements },
      });
      validateSearchQuery(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
    });
  });

  describe('C3 Evidence Query Validator', () => {
    it('accepts exactly one selector family and sets validatedQuery', () => {
      const { req: req1, res: res1, next: next1 } = mockReqRes({
        query: { project_id: validUuidV4, entity_id: [validUuidV4, validUuidV5] },
      });
      validateEvidenceQuery(req1, res1, next1);
      expect(next1).toHaveBeenCalled();
      expect(req1.validatedQuery.entity_id).toEqual([validUuidV4, validUuidV5]);

      const { req: req2, res: res2, next: next2 } = mockReqRes({
        query: { project_id: validUuidV4, evidence_id: ['ev-1', 'ev-2'] },
      });
      validateEvidenceQuery(req2, res2, next2);
      expect(next2).toHaveBeenCalled();
      expect(req2.validatedQuery.evidence_id).toEqual(['ev-1', 'ev-2']);
    });

    it('rejects when multiple or zero selector families are provided', () => {
      // Zero families
      const { req: req1, res: res1, next: next1 } = mockReqRes({
        query: { project_id: validUuidV4 },
      });
      validateEvidenceQuery(req1, res1, next1);
      expect(res1.status).toHaveBeenCalledWith(422);

      // Multiple families
      const { req: req2, res: res2, next: next2 } = mockReqRes({
        query: {
          project_id: validUuidV4,
          entity_id: [validUuidV4],
          relationship_id: [validUuidV5],
        },
      });
      validateEvidenceQuery(req2, res2, next2);
      expect(res2.status).toHaveBeenCalledWith(422);
    });
  });

  describe('Diagram and Report Query Validators', () => {
    it('validateDiagramExportQuery accepts json and svg, defaults to json', () => {
      const { req: req1, res: res1, next: next1 } = mockReqRes({
        query: { project_id: validUuidV4 },
      });
      validateDiagramExportQuery(req1, res1, next1);
      expect(next1).toHaveBeenCalled();
      expect(req1.validatedQuery.format).toBe('json');

      const { req: req2, res: res2, next: next2 } = mockReqRes({
        query: { project_id: validUuidV4, format: 'svg' },
      });
      validateDiagramExportQuery(req2, res2, next2);
      expect(next2).toHaveBeenCalled();
      expect(req2.validatedQuery.format).toBe('svg');

      const { req: req3, res: res3, next: next3 } = mockReqRes({
        query: { project_id: validUuidV4, format: 'pdf' },
      });
      validateDiagramExportQuery(req3, res3, next3);
      expect(res3.status).toHaveBeenCalledWith(422);
    });

    it('validateDiagramMembersQuery accepts group_id or entity_id, rejects both', () => {
      const { req: req1, res: res1, next: next1 } = mockReqRes({
        query: { project_id: validUuidV4, group_id: 'group_abc' },
      });
      validateDiagramMembersQuery(req1, res1, next1);
      expect(next1).toHaveBeenCalled();

      const { req: req2, res: res2, next: next2 } = mockReqRes({
        query: { project_id: validUuidV4, entity_id: validUuidV5 },
      });
      validateDiagramMembersQuery(req2, res2, next2);
      expect(next2).toHaveBeenCalled();

      const { req: req3, res: res3, next: next3 } = mockReqRes({
        query: { project_id: validUuidV4, group_id: 'group_abc', entity_id: validUuidV5 },
      });
      validateDiagramMembersQuery(req3, res3, next3);
      expect(res3.status).toHaveBeenCalledWith(422);
    });
  });

  describe('Body Validators and Scope Agreement', () => {
    it('rejects body exceeding 128 KiB with 413', () => {
      const largePayload = { data: 'x'.repeat(135000) };
      const { req, res, next } = mockReqRes({
        query: { project_id: validUuidV4 },
        body: largePayload,
      });
      validateKnowledgeQueryBody(req, res, next);
      expect(res.status).toHaveBeenCalledWith(413);
    });

    it('rejects body when project_id conflicts with route query project_id', () => {
      const { req, res, next } = mockReqRes({
        query: { project_id: validUuidV4 },
        validatedQuery: { project_id: validUuidV4 },
        body: { project_id: validUuidV5 },
      });
      validateKnowledgeQueryBody(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({ message: expect.stringContaining('Body project_id does not match') }),
        })
      );
    });

    it('rejects body when architecture_version_id conflicts with route param versionId', () => {
      const { req, res, next } = mockReqRes({
        params: { versionId: validUuidV4 },
        query: { project_id: validUuidV4 },
        validatedQuery: { project_id: validUuidV4 },
        body: { architecture_version_id: validUuidV5 },
      });
      validateKnowledgeQueryBody(req, res, next);
      expect(res.status).toHaveBeenCalledWith(422);
      expect(res.json).toHaveBeenCalledWith(
        expect.objectContaining({
          error: expect.objectContaining({ message: expect.stringContaining('Body architecture_version_id does not match') }),
        })
      );
    });

    it('validateDeliveryRetryBody validates required fields', () => {
      const { req: req1, res: res1, next: next1 } = mockReqRes({
        query: { project_id: validUuidV4 },
        body: {
          resource_type: 'diagram',
          resource_id: validUuidV4,
          idempotency_key: validUuidV5,
        },
      });
      validateDeliveryRetryBody(req1, res1, next1);
      expect(next1).toHaveBeenCalled();

      const { req: req2, res: res2, next: next2 } = mockReqRes({
        query: { project_id: validUuidV4 },
        body: {
          resource_type: 'diagram',
          resource_id: 'invalid-id',
          idempotency_key: validUuidV5,
        },
      });
      validateDeliveryRetryBody(req2, res2, next2);
      expect(res2.status).toHaveBeenCalledWith(422);
    });

    it('validateSearchRebuildBody validates idempotency_key UUID', () => {
      const { req: req1, res: res1, next: next1 } = mockReqRes({
        query: { project_id: validUuidV4 },
        body: { idempotency_key: validUuidV4 },
      });
      validateSearchRebuildBody(req1, res1, next1);
      expect(next1).toHaveBeenCalled();

      const { req: req2, res: res2, next: next2 } = mockReqRes({
        query: { project_id: validUuidV4 },
        body: { idempotency_key: 'not-a-uuid' },
      });
      validateSearchRebuildBody(req2, res2, next2);
      expect(res2.status).toHaveBeenCalledWith(422);
    });
  });
});
