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
  SERVICE: 'service',
  COMPONENT: 'component',
  MODULE: 'module',
  DATABASE: 'database',
  QUEUE: 'queue',
  API_ENDPOINT: 'api_endpoint',
  EXTERNAL_SYSTEM: 'external_system',
  DATA_STORE: 'data_store',
});

/**
 * Friendly labels for Architecture Entity kinds.
 */
export const ARCHITECTURE_ENTITY_KIND_LABELS = Object.freeze({
  [ARCHITECTURE_ENTITY_KIND.SERVICE]: 'Service',
  [ARCHITECTURE_ENTITY_KIND.COMPONENT]: 'Component',
  [ARCHITECTURE_ENTITY_KIND.MODULE]: 'Module',
  [ARCHITECTURE_ENTITY_KIND.DATABASE]: 'Database',
  [ARCHITECTURE_ENTITY_KIND.QUEUE]: 'Message Queue',
  [ARCHITECTURE_ENTITY_KIND.API_ENDPOINT]: 'API Endpoint',
  [ARCHITECTURE_ENTITY_KIND.EXTERNAL_SYSTEM]: 'External System',
  [ARCHITECTURE_ENTITY_KIND.DATA_STORE]: 'Data Store',
});

/**
 * Canonical Architecture Relationship kinds.
 * @readonly
 * @enum {string}
 */
export const ARCHITECTURE_RELATIONSHIP_KIND = Object.freeze({
  CALLS: 'calls',
  READS_FROM: 'reads_from',
  WRITES_TO: 'writes_to',
  SUBSCRIBES_TO: 'subscribes_to',
  PUBLISHES_TO: 'publishes_to',
  DEPENDS_ON: 'depends_on',
  INCLUDES: 'includes',
});

/**
 * Friendly labels for Architecture Relationship kinds.
 */
export const ARCHITECTURE_RELATIONSHIP_KIND_LABELS = Object.freeze({
  [ARCHITECTURE_RELATIONSHIP_KIND.CALLS]: 'Calls',
  [ARCHITECTURE_RELATIONSHIP_KIND.READS_FROM]: 'Reads From',
  [ARCHITECTURE_RELATIONSHIP_KIND.WRITES_TO]: 'Writes To',
  [ARCHITECTURE_RELATIONSHIP_KIND.SUBSCRIBES_TO]: 'Subscribes To',
  [ARCHITECTURE_RELATIONSHIP_KIND.PUBLISHES_TO]: 'Publishes To',
  [ARCHITECTURE_RELATIONSHIP_KIND.DEPENDS_ON]: 'Depends On',
  [ARCHITECTURE_RELATIONSHIP_KIND.INCLUDES]: 'Includes',
});

/**
 * Evidence strength levels.
 * @readonly
 * @enum {string}
 */
export const EVIDENCE_STRENGTH = Object.freeze({
  STRONG: 'strong',
  MEDIUM: 'medium',
  WEAK: 'weak',
});

/**
 * Evidence polarity.
 * @readonly
 * @enum {string}
 */
export const EVIDENCE_POLARITY = Object.freeze({
  POSITIVE: 'positive',
  NEGATIVE: 'negative',
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
    case EVIDENCE_STRENGTH.STRONG:
      return 'badge-strength-strong';
    case EVIDENCE_STRENGTH.MEDIUM:
      return 'badge-strength-medium';
    case EVIDENCE_STRENGTH.WEAK:
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
    case EVIDENCE_POLARITY.POSITIVE:
      return 'badge-polarity-positive';
    case EVIDENCE_POLARITY.NEGATIVE:
      return 'badge-polarity-negative';
    default:
      return 'badge-polarity-default';
  }
}

