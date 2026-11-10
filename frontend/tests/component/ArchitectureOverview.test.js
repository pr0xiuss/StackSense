import { describe, expect, it, vi } from 'vitest';

import {
  loadArchitectureOverview,
  OVERVIEW_ENTITY_BUDGETS,
} from '../../src/services/architectureOverview.js';

describe('backend-first architecture overview loading', () => {
  it('uses kind budgets, limits frontend noise, and keeps visible relationships', async () => {
    const controller = {
      id: 'controller-id',
      logical_id: 'architecture://controller/documents',
      kind: 'controller',
    };
    const serviceEntity = {
      id: 'service-id',
      logical_id: 'architecture://service/documents',
      kind: 'service',
    };
    const hiddenModule = {
      id: 'module-id',
      logical_id: 'architecture://module/hidden',
      kind: 'module',
    };
    const service = {
      listEntities: vi.fn(async (_versionId, options) => ({
        items:
          options.kind === 'controller'
            ? [controller]
            : options.kind === 'service'
              ? [serviceEntity]
              : [],
      })),
      listRelationships: vi.fn(async () => ({
        items: [
          {
            source_logical_id: controller.logical_id,
            target_logical_id: serviceEntity.logical_id,
          },
          {
            source_logical_id: controller.logical_id,
            target_logical_id: hiddenModule.logical_id,
          },
        ],
        total: 2,
      })),
    };

    const result = await loadArchitectureOverview('version', 'project', service);

    expect(service.listEntities).toHaveBeenCalledTimes(OVERVIEW_ENTITY_BUDGETS.length);
    expect(
      service.listEntities.mock.calls.some(
        ([, options]) => options.kind === 'module' || options.kind === 'library',
      ),
    ).toBe(false);
    expect(result.entities).toEqual([controller, serviceEntity]);
    expect(result.relationships).toHaveLength(1);
    expect(result.relationships[0].target_logical_id).toBe(serviceEntity.logical_id);
  });

  it('balances endpoints and services across application namespaces', async () => {
    const scopedEntities = (kind, scope, count) =>
      Array.from({ length: count }, (_, index) => ({
        id: `${kind}-${scope}-${index}`,
        logical_id: `architecture://${kind}/${scope}/${index}`,
        kind,
        metadata: { application_namespace: `root:${scope}`, framework: scope },
      }));
    const expressEndpoints = scopedEntities('endpoint', 'express', 40);
    const fastapiEndpoints = scopedEntities('endpoint', 'fastapi', 40);
    const expressServices = scopedEntities('service', 'express', 20);
    const fastapiServices = scopedEntities('service', 'fastapi', 20);
    const service = {
      listEntities: vi.fn(async (_versionId, options) => ({
        items:
          options.kind === 'endpoint'
            ? [...expressEndpoints, ...fastapiEndpoints]
            : options.kind === 'service'
              ? [...expressServices, ...fastapiServices]
              : [],
      })),
      listRelationships: vi.fn(async () => ({ items: [], total: 0 })),
    };

    const result = await loadArchitectureOverview('version', 'project', service);
    const endpoints = result.entities.filter((entity) => entity.kind === 'endpoint');
    const services = result.entities.filter((entity) => entity.kind === 'service');

    expect(endpoints).toHaveLength(30);
    expect(endpoints.filter((entity) => entity.metadata.framework === 'express')).toHaveLength(15);
    expect(endpoints.filter((entity) => entity.metadata.framework === 'fastapi')).toHaveLength(15);
    expect(services).toHaveLength(16);
    expect(services.filter((entity) => entity.metadata.framework === 'express')).toHaveLength(8);
    expect(services.filter((entity) => entity.metadata.framework === 'fastapi')).toHaveLength(8);
    expect(
      service.listEntities.mock.calls.find(([, options]) => options.kind === 'endpoint')[1].limit,
    ).toBe(100);
    expect(
      service.listEntities.mock.calls.find(([, options]) => options.kind === 'service')[1].limit,
    ).toBe(64);
  });
});
