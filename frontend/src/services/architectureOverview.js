import {
  ARCHITECTURE_ENTITY_KIND,
  ARCHITECTURE_RELATIONSHIP_KIND,
} from '../contracts/architectureContracts.js';
import { architectureService } from './architectureService.js';

const MAX_ENTITY_CANDIDATES_PER_KIND = 100;
const ENTITY_CANDIDATE_MULTIPLIER = 4;

// A bounded, backend-first overview. Source modules, libraries, and the full
// frontend component inventory remain available in their collection tabs.
export const OVERVIEW_ENTITY_BUDGETS = Object.freeze([
  [ARCHITECTURE_ENTITY_KIND.APPLICATION, 6],
  [ARCHITECTURE_ENTITY_KIND.CONTROLLER, 18],
  [ARCHITECTURE_ENTITY_KIND.SERVICE, 16],
  [ARCHITECTURE_ENTITY_KIND.DATA_REPOSITORY, 10],
  [ARCHITECTURE_ENTITY_KIND.WORKER, 5],
  [ARCHITECTURE_ENTITY_KIND.ENDPOINT, 30],
  [ARCHITECTURE_ENTITY_KIND.DATABASE, 4],
  [ARCHITECTURE_ENTITY_KIND.MESSAGE_BROKER, 2],
  [ARCHITECTURE_ENTITY_KIND.QUEUE, 2],
  [ARCHITECTURE_ENTITY_KIND.TOPIC, 1],
  [ARCHITECTURE_ENTITY_KIND.EXTERNAL_SERVICE, 2],
  [ARCHITECTURE_ENTITY_KIND.EXTERNAL_API, 2],
  [ARCHITECTURE_ENTITY_KIND.FRONTEND_APPLICATION, 1],
  [ARCHITECTURE_ENTITY_KIND.COMPONENT, 1],
]);

// Relationships are loaded by semantic kind so one large, logical-ID-sorted
// import/containment group cannot consume the entire overview window. The
// limits remain explicit and bounded; this is not a full-model graph load.
export const OVERVIEW_RELATIONSHIP_CANDIDATE_LIMITS = Object.freeze([
  [ARCHITECTURE_RELATIONSHIP_KIND.CONTAINS, 300],
  [ARCHITECTURE_RELATIONSHIP_KIND.EXPOSES, 200],
  [ARCHITECTURE_RELATIONSHIP_KIND.ROUTES_TO, 200],
  [ARCHITECTURE_RELATIONSHIP_KIND.CALLS, 200],
  [ARCHITECTURE_RELATIONSHIP_KIND.DEPENDS_ON, 100],
  [ARCHITECTURE_RELATIONSHIP_KIND.PERSISTS_TO, 100],
  [ARCHITECTURE_RELATIONSHIP_KIND.USES, 100],
  [ARCHITECTURE_RELATIONSHIP_KIND.CONNECTS_TO, 100],
  [ARCHITECTURE_RELATIONSHIP_KIND.CONSUMES, 100],
  [ARCHITECTURE_RELATIONSHIP_KIND.PRODUCES, 100],
]);

function applicationScope(entity) {
  const metadata = entity?.metadata || {};
  if (typeof metadata.application_namespace === 'string') {
    return metadata.application_namespace;
  }
  if (typeof metadata.framework === 'string') return `framework:${metadata.framework}`;
  return 'unscoped';
}

function selectBalancedEntities(items, limit) {
  const groups = new Map();
  items.forEach((entity) => {
    const scope = applicationScope(entity);
    if (!groups.has(scope)) groups.set(scope, []);
    groups.get(scope).push(entity);
  });

  const orderedGroups = [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([, entities]) => entities);
  const selected = [];
  let index = 0;
  while (
    selected.length < limit &&
    orderedGroups.some((group) => index < group.length)
  ) {
    orderedGroups.forEach((group) => {
      if (selected.length < limit && index < group.length) selected.push(group[index]);
    });
    index += 1;
  }
  return selected;
}

async function loadRelationshipKind(versionId, projectId, service, kind, cap) {
  const items = [];
  let offset = 0;
  let total = 0;
  do {
    const limit = Math.min(100, cap - items.length);
    const page = await service.listRelationships(versionId, {
      projectId,
      kind,
      limit,
      offset,
    });
    const pageItems = Array.isArray(page?.items) ? page.items : [];
    total = typeof page?.total === 'number' ? page.total : pageItems.length;
    items.push(...pageItems);
    offset += pageItems.length;
    if (pageItems.length === 0) break;
  } while (offset < total && items.length < cap);
  return items.slice(0, cap);
}

async function loadRelationships(versionId, projectId, service) {
  const pages = await Promise.all(
    OVERVIEW_RELATIONSHIP_CANDIDATE_LIMITS.map(([kind, cap]) =>
      loadRelationshipKind(versionId, projectId, service, kind, cap),
    ),
  );
  const relationships = [];
  const seen = new Set();
  pages.flat().forEach((relationship) => {
    const key =
      relationship.logical_id ||
      relationship.id ||
      `${relationship.kind || 'relationship'}:${relationship.source_logical_id}:${relationship.target_logical_id}`;
    if (key && !seen.has(key)) {
      seen.add(key);
      relationships.push(relationship);
    }
  });
  return relationships;
}

export async function loadArchitectureOverview(
  versionId,
  projectId,
  service = architectureService,
) {
  const entityPages = await Promise.all(
    OVERVIEW_ENTITY_BUDGETS.map(([kind, budget]) =>
      service.listEntities(versionId, {
        projectId,
        kind,
        limit: Math.min(
          MAX_ENTITY_CANDIDATES_PER_KIND,
          Math.max(budget, budget * ENTITY_CANDIDATE_MULTIPLIER),
        ),
        offset: 0,
      }),
    ),
  );

  const entities = [];
  const seen = new Set();
  entityPages.forEach((page, pageIndex) => {
    const items = Array.isArray(page?.items) ? page.items : [];
    const [, budget] = OVERVIEW_ENTITY_BUDGETS[pageIndex];
    selectBalancedEntities(items, budget).forEach((entity) => {
      const key = entity.logical_id || entity.id;
      if (key && !seen.has(key)) {
        seen.add(key);
        entities.push(entity);
      }
    });
  });

  const relationships = await loadRelationships(versionId, projectId, service);
  const visible = new Set(entities.map((entity) => entity.logical_id));
  return {
    entities,
    relationships: relationships.filter(
      (relationship) =>
        visible.has(relationship.source_logical_id) &&
        visible.has(relationship.target_logical_id),
    ),
  };
}
