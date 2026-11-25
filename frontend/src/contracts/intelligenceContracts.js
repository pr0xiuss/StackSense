/**
 * Intelligence Contracts, Vocabulary, and Validation Functions (Frontend)
 *
 * Defines C5 v1.0.0 wire schema contracts, runtime ingress validation,
 * enum vocabularies, and scope guards backing the Unified Intelligence Workspace.
 */
import { validatePreparedDiagram } from './diagramContracts.js';

export { validatePreparedDiagram };

export const INTELLIGENCE_CONTRACT_VERSION = '1.0.0';

export const DIAGRAM_TEMPLATES = Object.freeze([
  'system_overview',
  'component_architecture',
  'dependency_map',
  'data_flow',
]);

export const SEARCH_MODES = Object.freeze(['lexical', 'semantic', 'hybrid']);

export const EXPORT_FORMATS = Object.freeze(['json', 'svg']);

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(val) {
  return typeof val === 'string' && UUID_REGEX.test(val.trim());
}

export class ContractValidationError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = 'ContractValidationError';
    this.details = details;
  }
}

function fail(msg, details = {}) {
  throw new ContractValidationError(msg, details);
}

function assertObject(data, name) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    fail(`${name} must be a non-null object`);
  }
}

function assertUuid(val, name) {
  if (!isUuid(val)) {
    fail(`${name} must be a valid UUID, got: ${val}`);
  }
}

function assertString(val, name, allowEmpty = true) {
  if (typeof val !== 'string' || (!allowEmpty && val.trim().length === 0)) {
    fail(`${name} must be a ${allowEmpty ? '' : 'non-empty '}string`);
  }
}

function assertNumber(val, name) {
  if (typeof val !== 'number' || !Number.isFinite(val)) {
    fail(`${name} must be a finite number`);
  }
}

function assertBoolean(val, name) {
  if (typeof val !== 'boolean') {
    fail(`${name} must be a boolean`);
  }
}

function assertArray(val, name) {
  if (!Array.isArray(val)) {
    fail(`${name} must be an array`);
  }
}

/**
 * Validates C0 DeliverySummary.
 */
export function validateDeliverySummary(data) {
  assertObject(data, 'DeliverySummary');
  assertArray(data.slots || data.resources || [], 'DeliverySummary.slots');
  if (data.overall_state !== undefined) {
    assertString(data.overall_state, 'DeliverySummary.overall_state');
  }
  return data;
}

/**
 * Validates C0 RetryAccepted.
 */
export function validateRetryAccepted(data) {
  assertObject(data, 'RetryAccepted');
  assertBoolean(data.accepted, 'RetryAccepted.accepted');
  if (data.work_id !== undefined && data.work_id !== null) {
    assertUuid(data.work_id, 'RetryAccepted.work_id');
  }
  return data;
}

/**
 * Validates C1 SearchStatus.
 */
export function validateSearchStatus(data) {
  assertObject(data, 'SearchStatus');
  assertObject(data.capabilities || {}, 'SearchStatus.capabilities');
  return data;
}

/**
 * Validates C1 SearchPage.
 */
export function validateSearchPage(data) {
  assertObject(data, 'SearchPage');
  assertArray(data.items, 'SearchPage.items');
  assertNumber(data.total_hits, 'SearchPage.total_hits');
  assertBoolean(data.has_more, 'SearchPage.has_more');
  for (const item of data.items) {
    assertObject(item, 'SearchHit');
    assertString(item.entity_id || item.document_id || item.id, 'SearchHit.id');
    if (item.score !== undefined && item.score !== null) {
      assertNumber(item.score, 'SearchHit.score');
    }
  }
  return data;
}

/**
 * Validates C1 SearchReprojectionAccepted.
 */
export function validateSearchReprojectionAccepted(data) {
  assertObject(data, 'SearchReprojectionAccepted');
  assertBoolean(data.accepted, 'SearchReprojectionAccepted.accepted');
  return data;
}

/**
 * Validates C3 KnowledgeQueryResponse.
 */
export function validateKnowledgeQueryResponse(data) {
  assertObject(data, 'KnowledgeQueryResponse');
  assertArray(data.facts || [], 'KnowledgeQueryResponse.facts');
  assertArray(data.relationships || [], 'KnowledgeQueryResponse.relationships');
  assertArray(data.evidence || [], 'KnowledgeQueryResponse.evidence');
  assertArray(data.unresolved || [], 'KnowledgeQueryResponse.unresolved');
  assertArray(data.conflicts || [], 'KnowledgeQueryResponse.conflicts');
  assertObject(data.coverage || {}, 'KnowledgeQueryResponse.coverage');
  assertArray(data.source_observations || [], 'KnowledgeQueryResponse.source_observations');
  return data;
}

/**
 * Validates C3 ContextBundle.
 */
export function validateContextBundle(data) {
  assertObject(data, 'ContextBundle');
  assertArray(data.rationales || [], 'ContextBundle.rationales');
  assertArray(data.omissions || [], 'ContextBundle.omissions');
  assertObject(data.usage || {}, 'ContextBundle.usage');
  assertString(data.outcome, 'ContextBundle.outcome');
  if (data.semantic_digest !== undefined && data.semantic_digest !== null) {
    assertString(data.semantic_digest, 'ContextBundle.semantic_digest');
  }
  return data;
}

/**
 * Validates C3 EvidencePage.
 */
export function validateEvidencePage(data) {
  assertObject(data, 'EvidencePage');
  assertArray(data.items, 'EvidencePage.items');
  assertBoolean(data.has_more, 'EvidencePage.has_more');
  if (data.total_count !== undefined && data.total_count !== null) {
    assertNumber(data.total_count, 'EvidencePage.total_count');
  }
  return data;
}

/**
 * Validates C2 DiagramCollection.
 */
export function validateDiagramCollection(data) {
  assertObject(data, 'DiagramCollection');
  assertObject(data.canonical_scope, 'DiagramCollection.canonical_scope');
  assertArray(data.items || data.diagrams || [], 'DiagramCollection.items');
  return data;
}

/**
 * Validates C2 DiagramSummary.
 */
export function validateDiagramSummary(data) {
  assertObject(data, 'DiagramSummary');
  assertObject(data.delivery_scope, 'DiagramSummary.delivery_scope');
  assertString(data.availability, 'DiagramSummary.availability');
  assertString(data.readability, 'DiagramSummary.readability');
  return data;
}

/**
 * Validates C2 GenerationPage.
 */
export function validateGenerationPage(data) {
  assertObject(data, 'GenerationPage');
  assertArray(data.items, 'GenerationPage.items');
  assertBoolean(data.has_more, 'GenerationPage.has_more');
  return data;
}

/**
 * Validates C2 DiagramSpec.
 */
export function validateDiagramSpec(data) {
  assertObject(data, 'DiagramSpec');
  assertObject(data.scope || {}, 'DiagramSpec.scope');
  return data;
}

/**
 * Validates C2 LayoutSpec.
 */
export function validateLayoutSpec(data) {
  assertObject(data, 'LayoutSpec');
  return data;
}

/**
 * Validates C2 DiagramViewResponse.
 */
export function validateDiagramViewResponse(data) {
  assertObject(data, 'DiagramViewResponse');
  return data;
}

/**
 * Validates C2 MemberPage.
 */
export function validateMemberPage(data) {
  assertObject(data, 'MemberPage');
  assertArray(data.items, 'MemberPage.items');
  assertBoolean(data.has_more, 'MemberPage.has_more');
  return data;
}

/**
 * Validates C4 ReportCollection.
 */
export function validateReportCollection(data) {
  assertObject(data, 'ReportCollection');
  assertArray(data.items || data.resources || [], 'ReportCollection.items');
  return data;
}

/**
 * Validates C4 ReportSummary.
 */
export function validateReportSummary(data) {
  assertObject(data, 'ReportSummary');
  assertUuid(data.report_id || data.id, 'ReportSummary.report_id');
  assertString(data.profile, 'ReportSummary.profile');
  assertString(data.readability, 'ReportSummary.readability');
  return data;
}

/**
 * Validates C4 ReportGenerationPage.
 */
export function validateReportGenerationPage(data) {
  assertObject(data, 'ReportGenerationPage');
  assertArray(data.items, 'ReportGenerationPage.items');
  assertBoolean(data.has_more, 'ReportGenerationPage.has_more');
  return data;
}

/**
 * Validates C4 ReportGenerationSummary.
 */
export function validateReportGenerationSummary(data) {
  assertObject(data, 'ReportGenerationSummary');
  assertUuid(data.generation_id || data.id, 'ReportGenerationSummary.generation_id');
  if (data.pdf_sha256 !== undefined && data.pdf_sha256 !== null) {
    assertString(data.pdf_sha256, 'ReportGenerationSummary.pdf_sha256');
  }
  return data;
}

/**
 * Verifies that a response payload's scope matches expected navigation scope.
 */
export function validateScopeMatch(payload, expectedScope = {}) {
  if (!payload || typeof payload !== 'object') return false;
  const scope = payload.scope || payload.canonical_scope || payload.delivery_scope || payload;

  if (expectedScope.projectId && scope.project_id) {
    if (String(scope.project_id).trim() !== String(expectedScope.projectId).trim()) {
      return false;
    }
  }

  if (expectedScope.versionId) {
    const vId = scope.architecture_version_id || scope.version_id || scope.id;
    if (vId && String(vId).trim() !== String(expectedScope.versionId).trim()) {
      return false;
    }
  }

  return true;
}
