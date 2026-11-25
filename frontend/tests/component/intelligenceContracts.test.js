import { describe, it, expect } from 'vitest';
import {
  isUuid,
  validateDeliverySummary,
  validateRetryAccepted,
  validateSearchStatus,
  validateSearchPage,
  validateSearchReprojectionAccepted,
  validateKnowledgeQueryResponse,
  validateContextBundle,
  validateEvidencePage,
  validateDiagramCollection,
  validateDiagramSummary,
  validateGenerationPage,
  validateReportCollection,
  validateReportSummary,
  validateReportGenerationPage,
  validateReportGenerationSummary,
  validateScopeMatch,
  ContractValidationError,
} from '../../src/contracts/intelligenceContracts.js';

describe('intelligenceContracts Unit Tests', () => {
  const uuidV4 = '11111111-2222-4333-8444-555555555555';
  const uuidV5 = 'c4627196-8575-52bb-81c8-f5424cf961e6';

  describe('isUuid helper', () => {
    it('accepts UUIDv4 and UUIDv5', () => {
      expect(isUuid(uuidV4)).toBe(true);
      expect(isUuid(uuidV5)).toBe(true);
      expect(isUuid('invalid-uuid')).toBe(false);
    });
  });

  describe('C0 Delivery Contracts', () => {
    it('validates DeliverySummary', () => {
      const valid = { slots: [{ slot_kind: 'search', state: 'READY' }], overall_state: 'READY' };
      expect(validateDeliverySummary(valid)).toBe(valid);
      expect(() => validateDeliverySummary(null)).toThrow(ContractValidationError);
    });

    it('validates RetryAccepted', () => {
      const valid = { accepted: true, work_id: uuidV4 };
      expect(validateRetryAccepted(valid)).toBe(valid);
      expect(() => validateRetryAccepted({ accepted: 'not-bool' })).toThrow(ContractValidationError);
    });
  });

  describe('C1 Search Contracts', () => {
    it('validates SearchStatus and SearchReprojectionAccepted', () => {
      expect(validateSearchStatus({ capabilities: { lexical: true } })).toBeDefined();
      expect(validateSearchReprojectionAccepted({ accepted: true })).toBeDefined();
    });

    it('validates SearchPage with items and finite scores', () => {
      const valid = {
        items: [{ entity_id: uuidV4, score: 0.95, rank_tier: 1 }],
        total_hits: 1,
        has_more: false,
      };
      expect(validateSearchPage(valid)).toBe(valid);

      const invalidScore = {
        items: [{ entity_id: uuidV4, score: Infinity }],
        total_hits: 1,
        has_more: false,
      };
      expect(() => validateSearchPage(invalidScore)).toThrow(ContractValidationError);
    });
  });

  describe('C3 Knowledge and Evidence Contracts', () => {
    it('validates KnowledgeQueryResponse and ContextBundle', () => {
      const validQuery = {
        facts: [],
        relationships: [],
        evidence: [],
        unresolved: [],
        conflicts: [],
        coverage: { canonical_entity_count: 5 },
        source_observations: [],
      };
      expect(validateKnowledgeQueryResponse(validQuery)).toBe(validQuery);

      const validContext = {
        rationales: [],
        omissions: [],
        usage: { fact_count: 10 },
        outcome: 'SUCCESS',
        semantic_digest: 'sha256-abcdef123456',
      };
      expect(validateContextBundle(validContext)).toBe(validContext);
    });

    it('validates EvidencePage with nullable total_count', () => {
      const withTotal = { items: [{ id: uuidV4 }], has_more: false, total_count: 1 };
      expect(validateEvidencePage(withTotal)).toBe(withTotal);

      const withoutTotal = { items: [{ id: uuidV4 }], has_more: false, total_count: null };
      expect(validateEvidencePage(withoutTotal)).toBe(withoutTotal);
    });
  });

  describe('C2 Diagram Contracts', () => {
    it('validates DiagramCollection and DiagramSummary', () => {
      const validCol = { canonical_scope: { project_id: uuidV4 }, items: [] };
      expect(validateDiagramCollection(validCol)).toBe(validCol);

      const validSum = {
        delivery_scope: { project_id: uuidV4 },
        availability: 'READY',
        readability: 'COMPLETE',
      };
      expect(validateDiagramSummary(validSum)).toBe(validSum);
    });

    it('validates GenerationPage', () => {
      const valid = { items: [{ generation_id: uuidV4 }], has_more: false };
      expect(validateGenerationPage(valid)).toBe(valid);
    });
  });

  describe('C4 Report Contracts', () => {
    it('validates ReportCollection and ReportSummary', () => {
      const validCol = { items: [] };
      expect(validateReportCollection(validCol)).toBe(validCol);

      const validSum = {
        report_id: uuidV4,
        profile: 'overview',
        readability: 'COMPLETE',
      };
      expect(validateReportSummary(validSum)).toBe(validSum);
    });

    it('validates ReportGenerationPage and ReportGenerationSummary', () => {
      const validPage = { items: [{ generation_id: uuidV4 }], has_more: false };
      expect(validateReportGenerationPage(validPage)).toBe(validPage);

      const validSum = {
        generation_id: uuidV4,
        pdf_sha256: 'sha256-1234567890abcdef',
      };
      expect(validateReportGenerationSummary(validSum)).toBe(validSum);
    });
  });

  describe('validateScopeMatch helper', () => {
    it('returns true when scope matches expected', () => {
      const payload = { canonical_scope: { project_id: uuidV4, architecture_version_id: uuidV5 } };
      expect(validateScopeMatch(payload, { projectId: uuidV4, versionId: uuidV5 })).toBe(true);
    });

    it('returns false when scope conflicts', () => {
      const payload = { canonical_scope: { project_id: uuidV4, architecture_version_id: uuidV5 } };
      expect(validateScopeMatch(payload, { projectId: uuidV4, versionId: '99999999-9999-9999-9999-999999999999' })).toBe(false);
    });
  });
});
