import { describe, it, expect, vi, beforeEach } from 'vitest';
import { graphService } from '../../src/services/graphService.js';
import { apiClient } from '../../src/services/apiClient.js';

describe('graphService unit tests', () => {
  const versionId = 'a0000000-0000-0000-0000-000000000001';
  const projectId = 'p0000000-0000-0000-0000-000000000001';
  const entityId = 'e0000000-0000-0000-0000-000000000001';
  const targetId = 'e0000000-0000-0000-0000-000000000002';

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('getStatus calls /status with project_id', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ status: 'COMPLETED' });
    const result = await graphService.getStatus(versionId, { projectId });

    expect(result).toEqual({ status: 'COMPLETED' });
    expect(spy).toHaveBeenCalledWith(
      `/architecture-versions/${versionId}/graph/status?project_id=${projectId}`,
      { signal: undefined }
    );
  });

  it('requestRebuild calls POST /rebuild with project_id and empty body', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ attempt_status: 'QUEUED' });
    const result = await graphService.requestRebuild(versionId, { projectId });

    expect(result).toEqual({ attempt_status: 'QUEUED' });
    expect(spy).toHaveBeenCalledWith(
      `/architecture-versions/${versionId}/graph/rebuild?project_id=${projectId}`,
      {},
      { signal: undefined }
    );
  });

  it('getWindow serializes repeated canonical_kinds and options', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ nodes: [], edges: [] });
    await graphService.getWindow(versionId, {
      projectId,
      nodeLimit: 50,
      edgeLimit: 100,
      pageSize: 50,
      canonicalKinds: ['calls', 'imports'],
      cursor: 'cur123',
      timeoutSeconds: 2,
    });

    const calledPath = spy.mock.calls[0][0];
    expect(calledPath).toContain(`/architecture-versions/${versionId}/graph/window?`);
    expect(calledPath).toContain(`project_id=${projectId}`);
    expect(calledPath).toContain('node_limit=50');
    expect(calledPath).toContain('edge_limit=100');
    expect(calledPath).toContain('page_size=50');
    expect(calledPath).toContain('canonical_kinds=calls');
    expect(calledPath).toContain('canonical_kinds=imports');
    expect(calledPath).toContain('cursor=cur123');
    expect(calledPath).toContain('timeout_seconds=2');
  });

  it('getNodeDetail calls /nodes/:entityId', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ architecture_entity_id: entityId });
    await graphService.getNodeDetail(versionId, entityId, { projectId, timeoutSeconds: 3 });

    expect(spy).toHaveBeenCalledWith(
      `/architecture-versions/${versionId}/graph/nodes/${entityId}?project_id=${projectId}&timeout_seconds=3`,
      { signal: undefined }
    );
  });

  it('getNeighborhood passes direction, depth, and repeated relationship_kinds', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ nodes: [], edges: [] });
    await graphService.getNeighborhood(versionId, entityId, {
      projectId,
      direction: 'both',
      depth: 2,
      relationshipKinds: ['calls', 'contains'],
    });

    const calledPath = spy.mock.calls[0][0];
    expect(calledPath).toContain(`/architecture-versions/${versionId}/graph/nodes/${entityId}/neighborhood?`);
    expect(calledPath).toContain('direction=both');
    expect(calledPath).toContain('depth=2');
    expect(calledPath).toContain('relationship_kinds=calls');
    expect(calledPath).toContain('relationship_kinds=contains');
  });

  it('getDependencies calls /dependencies', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ nodes: [], edges: [] });
    await graphService.getDependencies(versionId, entityId, {
      projectId,
      depth: 1,
      relationshipKinds: ['calls'],
    });

    const calledPath = spy.mock.calls[0][0];
    expect(calledPath).toContain(`/architecture-versions/${versionId}/graph/nodes/${entityId}/dependencies?`);
    expect(calledPath).toContain('relationship_kinds=calls');
  });

  it('getDependents calls /dependents', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ nodes: [], edges: [] });
    await graphService.getDependents(versionId, entityId, {
      projectId,
      depth: 1,
      relationshipKinds: ['calls'],
    });

    const calledPath = spy.mock.calls[0][0];
    expect(calledPath).toContain(`/architecture-versions/${versionId}/graph/nodes/${entityId}/dependents?`);
  });

  it('getContainment calls /containment with direction', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ nodes: [], edges: [] });
    await graphService.getContainment(versionId, entityId, {
      projectId,
      direction: 'children',
      depth: 2,
    });

    const calledPath = spy.mock.calls[0][0];
    expect(calledPath).toContain(`/architecture-versions/${versionId}/graph/nodes/${entityId}/containment?`);
    expect(calledPath).toContain('direction=children');
    expect(calledPath).toContain('depth=2');
  });

  it('getBoundedPaths passes source and target entity IDs', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ paths: [] });
    await graphService.getBoundedPaths(versionId, {
      projectId,
      sourceEntityId: entityId,
      targetEntityId: targetId,
      maxDepth: 3,
      pathLimit: 5,
    });

    const calledPath = spy.mock.calls[0][0];
    expect(calledPath).toContain(`/architecture-versions/${versionId}/graph/paths?`);
    expect(calledPath).toContain(`source_entity_id=${entityId}`);
    expect(calledPath).toContain(`target_entity_id=${targetId}`);
  });

  it('getQueryHealth calls /health/graph/query', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ status: 'ready' });
    const result = await graphService.getQueryHealth();

    expect(result).toEqual({ status: 'ready' });
    expect(spy).toHaveBeenCalledWith('/health/graph/query', { signal: undefined });
  });

  it('rejects with descriptive errors when required IDs are missing', async () => {
    await expect(graphService.getStatus(null, { projectId })).rejects.toThrow('versionId is required');
    await expect(graphService.getStatus(versionId, {})).rejects.toThrow('projectId is required');
    await expect(graphService.getNodeDetail(versionId, null, { projectId })).rejects.toThrow('entityId is required');
    await expect(graphService.getBoundedPaths(versionId, { projectId, sourceEntityId: entityId })).rejects.toThrow(
      'targetEntityId is required'
    );
  });
});

