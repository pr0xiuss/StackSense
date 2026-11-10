/**
 * Architecture Model Domain Contracts and Vocabulary (Frontend)
 *
 * Defines canonical constants, types, labels, and badge classes
 * for published Architecture Version components, entities, relationships,
 * evidence, unresolved relationships, and model conflicts.
 */

/**
 * Canonical Architecture Entity kinds.
 * @readonly
 * @enum {string}
 */
export const ARCHITECTURE_ENTITY_KIND = Object.freeze({
  APPLICATION: 'application',
  FRONTEND_APPLICATION: 'frontend_application',
  SERVICE: 'service',
  COMPONENT: 'component',
  MODULE: 'module',
  CONTROLLER: 'controller',
  ENDPOINT: 'endpoint',
  WORKER: 'worker',
  DATA_REPOSITORY: 'data_repository',
  DATABASE: 'database',
  MESSAGE_BROKER: 'message_broker',
  QUEUE: 'queue',
  TOPIC: 'topic',
  EXTERNAL_SERVICE: 'external_service',
  EXTERNAL_API: 'external_api',
  LIBRARY: 'library',
  CONFIGURATION_COMPONENT: 'configuration_component',
  UNKNOWN: 'unknown',
});

/**
 * Friendly labels for Architecture Entity kinds.
 */
export const ARCHITECTURE_ENTITY_KIND_LABELS = Object.freeze({
  [ARCHITECTURE_ENTITY_KIND.APPLICATION]: 'Application',
  [ARCHITECTURE_ENTITY_KIND.FRONTEND_APPLICATION]: 'Frontend Application',
  [ARCHITECTURE_ENTITY_KIND.SERVICE]: 'Service',
  [ARCHITECTURE_ENTITY_KIND.COMPONENT]: 'Component',
  [ARCHITECTURE_ENTITY_KIND.MODULE]: 'Module',
  [ARCHITECTURE_ENTITY_KIND.CONTROLLER]: 'Controller',
  [ARCHITECTURE_ENTITY_KIND.ENDPOINT]: 'Endpoint',
  [ARCHITECTURE_ENTITY_KIND.WORKER]: 'Worker',
  [ARCHITECTURE_ENTITY_KIND.DATA_REPOSITORY]: 'Data Repository',
  [ARCHITECTURE_ENTITY_KIND.DATABASE]: 'Database',
  [ARCHITECTURE_ENTITY_KIND.MESSAGE_BROKER]: 'Message Broker',
  [ARCHITECTURE_ENTITY_KIND.QUEUE]: 'Message Queue',
  [ARCHITECTURE_ENTITY_KIND.TOPIC]: 'Topic',
  [ARCHITECTURE_ENTITY_KIND.EXTERNAL_SERVICE]: 'External Service',
  [ARCHITECTURE_ENTITY_KIND.EXTERNAL_API]: 'External API',
  [ARCHITECTURE_ENTITY_KIND.LIBRARY]: 'Library',
  [ARCHITECTURE_ENTITY_KIND.CONFIGURATION_COMPONENT]: 'Configuration',
  [ARCHITECTURE_ENTITY_KIND.UNKNOWN]: 'Unknown',
});

/**
 * Canonical Architecture Relationship kinds.
 * @readonly
 * @enum {string}
 */
export const ARCHITECTURE_RELATIONSHIP_KIND = Object.freeze({
  CONTAINS: 'contains',
  DEPENDS_ON: 'depends_on',
  IMPORTS: 'imports',
  CALLS: 'calls',
  EXPOSES: 'exposes',
  CONSUMES: 'consumes',
  PRODUCES: 'produces',
  CONNECTS_TO: 'connects_to',
  PERSISTS_TO: 'persists_to',
  USES: 'uses',
  EXTENDS: 'extends',
  IMPLEMENTS: 'implements',
  ROUTES_TO: 'routes_to',
});

/**
 * Friendly labels for Architecture Relationship kinds.
 */
export const ARCHITECTURE_RELATIONSHIP_KIND_LABELS = Object.freeze({
  [ARCHITECTURE_RELATIONSHIP_KIND.CONTAINS]: 'Contains',
  [ARCHITECTURE_RELATIONSHIP_KIND.DEPENDS_ON]: 'Depends On',
  [ARCHITECTURE_RELATIONSHIP_KIND.IMPORTS]: 'Imports',
  [ARCHITECTURE_RELATIONSHIP_KIND.CALLS]: 'Calls',
  [ARCHITECTURE_RELATIONSHIP_KIND.EXPOSES]: 'Exposes',
  [ARCHITECTURE_RELATIONSHIP_KIND.CONSUMES]: 'Consumes',
  [ARCHITECTURE_RELATIONSHIP_KIND.PRODUCES]: 'Produces',
  [ARCHITECTURE_RELATIONSHIP_KIND.CONNECTS_TO]: 'Connects To',
  [ARCHITECTURE_RELATIONSHIP_KIND.PERSISTS_TO]: 'Persists To',
  [ARCHITECTURE_RELATIONSHIP_KIND.USES]: 'Uses',
  [ARCHITECTURE_RELATIONSHIP_KIND.EXTENDS]: 'Extends',
  [ARCHITECTURE_RELATIONSHIP_KIND.IMPLEMENTS]: 'Implements',
  [ARCHITECTURE_RELATIONSHIP_KIND.ROUTES_TO]: 'Routes To',
});

/**
 * Evidence strength levels.
 * @readonly
 * @enum {string}
 */
export const EVIDENCE_STRENGTH = Object.freeze({
  DIRECT_SOURCE: 'direct_source',
  FRAMEWORK_STRUCTURAL: 'framework_structural',
  CONFIGURATION: 'configuration',
  DEPENDENCY: 'dependency',
  DOCUMENTATION: 'documentation',
});

/**
 * Evidence polarity.
 * @readonly
 * @enum {string}
 */
export const EVIDENCE_POLARITY = Object.freeze({
  SUPPORTING: 'supporting',
  CONFLICTING: 'conflicting',
});

/**
 * Get friendly display label for an entity kind.
 * @param {string} [kind]
 * @returns {string}
 */
export function getEntityKindLabel(kind) {
  if (!kind) return 'Unknown Entity';
  const key = kind.toLowerCase();
  return ARCHITECTURE_ENTITY_KIND_LABELS[key] || kind;
}

/**
 * Get friendly display label for a relationship kind.
 * @param {string} [kind]
 * @returns {string}
 */
export function getRelationshipKindLabel(kind) {
  if (!kind) return 'Relates to';
  const key = kind.toLowerCase();
  return ARCHITECTURE_RELATIONSHIP_KIND_LABELS[key] || kind;
}

/**
 * CSS class generator for evidence strength badges.
 * @param {string} [strength]
 * @returns {string}
 */
export function getEvidenceStrengthBadgeClass(strength) {
  const norm = (strength || '').toLowerCase();
  switch (norm) {
    case EVIDENCE_STRENGTH.DIRECT_SOURCE:
    case EVIDENCE_STRENGTH.FRAMEWORK_STRUCTURAL:
      return 'badge-strength-strong';
    case EVIDENCE_STRENGTH.CONFIGURATION:
    case EVIDENCE_STRENGTH.DEPENDENCY:
      return 'badge-strength-medium';
    case EVIDENCE_STRENGTH.DOCUMENTATION:
      return 'badge-strength-weak';
    default:
      return 'badge-strength-default';
  }
}

/**
 * CSS class generator for evidence polarity badges.
 * @param {string} [polarity]
 * @returns {string}
 */
export function getEvidencePolarityBadgeClass(polarity) {
  const norm = (polarity || '').toLowerCase();
  switch (norm) {
    case EVIDENCE_POLARITY.SUPPORTING:
      return 'badge-polarity-positive';
    case EVIDENCE_POLARITY.CONFLICTING:
      return 'badge-polarity-negative';
    default:
      return 'badge-polarity-default';
  }
}

