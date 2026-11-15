import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useArchitectureGraph } from '../../src/hooks/useArchitectureGraph.js';
import { graphService } from '../../src/services/graphService.js';
import { architectureService } from '../../src/services/architectureService.js';

describe('useArchitectureGraph hook tests', () => {
  const projectId = 'a0000000-0000-0000-0000-000000000001';
  const repositoryId = 'b0000000-0000-0000-0000-000000000002';
  const analysisId = 'c0000000-0000-0000-0000-000000000003';
  const versionId = 'd0000000-0000-0000-0000-000000000004';
  const generationId = 'e0000000-0000-0000-0000-000000000010';
  const entityId1 = 'e0000000-0000-0000-0000-000000000011';

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('sets contextError when required IDs are missing or invalid', async () => {
    const { result } = renderHook(() =>
      useArchitectureGraph({
        projectId: null,
        repositoryId,
        analysisId,
        versionId,
      })
    );

    expect(result.current.state.contextValidated).toBe(false);
    expect(result.current.state.contextError).toContain('Missing required context IDs');
  });

  it('validates canonical version and fetches initial status and window', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValueOnce({
      id: versionId,
      project_id: projectId,
      version_number: 1,
    });

    vi.spyOn(graphService, 'getStatus').mockResolvedValueOnce({
      resource_id: 'res-1',
      project_id: projectId,
      architecture_version_id: versionId,
      status: 'COMPLETED',
      active_generation_id: generationId,
    });

    const mockSubgraph = {
      scope: {
        project_id: projectId,
        architecture_version_id: versionId,
        generation_id: generationId,
        resource_state: 'COMPLETED',
        graph_schema_version: '1.0.0',
        projector_version: '1.0.0',
        counts: {
          entities: 1,
          relationships: 0,
          evidence: 0,
          unresolved: 0,
          conflicts: 0,
        },
      },
      nodes: [
        {
          architecture_entity_id: entityId1,
          logical_id: 'log-1',
          canonical_kind: 'service',
          name: 'PaymentService',
          namespace: 'billing',
          fact_status: 'verified',
          semantic_signature: 'sig',
          evidence_logical_ids: [],
          metadata: {},
        },
      ],
      edges: [],
      total_manifest_nodes: 1,
      total_manifest_edges: 0,
      loaded_nodes: 1,
      loaded_edges: 0,
      truncated: false,
    };

    const windowSpy = vi.spyOn(graphService, 'getWindow').mockResolvedValueOnce(mockSubgraph);

    const { result } = renderHook(() =>
      useArchitectureGraph(
        {
          projectId,
          repositoryId,
          analysisId,
          versionId,
        },
        { pollIntervalMs: 50 }
      )
    );

    await waitFor(() => {
      expect(result.current.state.contextValidated).toBe(true);
      expect(result.current.state.status?.status).toBe('COMPLETED');
    });

    await waitFor(() => {
      expect(result.current.state.loadedNodeCount).toBe(1);
      expect(result.current.state.nodes[entityId1]?.name).toBe('PaymentService');
    });

    expect(windowSpy).toHaveBeenCalledWith(
      versionId,
      expect.objectContaining({
        projectId,
        nodeLimit: 50,
        edgeLimit: 100,
        pageSize: 50,
      })
    );
  });

  it('polls status every 2 seconds when status is PENDING or RUNNING', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue({
      id: versionId,
      project_id: projectId,
    });

    const statusSpy = vi
      .spyOn(graphService, 'getStatus')
      .mockResolvedValueOnce({
        status: 'RUNNING',
        active_attempt: { status: 'RUNNING', attempt_number: 1 },
      })
      .mockResolvedValueOnce({
        status: 'COMPLETED',
        active_generation_id: generationId,
      });

    const { result, unmount } = renderHook(() =>
      useArchitectureGraph(
        {
          projectId,
          repositoryId,
          analysisId,
          versionId,
        },
        { pollIntervalMs: 50 }
      )
    );

    await waitFor(() => {
      expect(result.current.state.status?.status).toBe('RUNNING');
    });

    await waitFor(() => {
      expect(result.current.state.status?.status).toBe('COMPLETED');
    });

    expect(statusSpy).toHaveBeenCalledTimes(2);
    unmount();
  });

  it('waits for publication discovery after the exact projection-not-found response, then loads the graph', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue({ id: versionId, project_id: projectId });
    const statusSpy = vi.spyOn(graphService, 'getStatus')
      .mockRejectedValueOnce({ status: 404, code: 'graph_projection_not_found' })
      .mockResolvedValueOnce({ status: 'RUNNING' })
      .mockResolvedValue({ status: 'COMPLETED', active_generation_id: generationId });
    const windowSpy = vi.spyOn(graphService, 'getWindow').mockResolvedValue({
      scope: { project_id: projectId, architecture_version_id: versionId, generation_id: generationId },
      nodes: [], edges: [], next_cursor: null,
    });
    const { result, unmount } = renderHook(() => useArchitectureGraph(
      { projectId, repositoryId, analysisId, versionId },
      { discoveryPollIntervalMs: 80, pollIntervalMs: 30 }
    ));
    await waitFor(() => expect(result.current.state.projectionDiscoveryPending).toBe(true));
    expect(result.current.state.status).toBeNull(); // no invented PENDING resource
    expect(result.current.state.error).toBeNull();
    expect(windowSpy).not.toHaveBeenCalled();
    await waitFor(() => expect(result.current.state.status?.status).toBe('COMPLETED'));
    expect(result.current.state.projectionDiscoveryPending).toBe(false);
    expect(windowSpy).toHaveBeenCalledTimes(1);
    expect(statusSpy).toHaveBeenCalledTimes(3);
    unmount();
  });

  it.each([
    { status: 404, code: 'not_found' },
    { status: 403, code: 'forbidden' },
  ])('does not mask or poll unrelated status errors: $code', async (error) => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue({ id: versionId, project_id: projectId });
    const statusSpy = vi.spyOn(graphService, 'getStatus').mockRejectedValue(error);
    const { result, unmount } = renderHook(() => useArchitectureGraph(
      { projectId, repositoryId, analysisId, versionId }, { discoveryPollIntervalMs: 10 }
    ));
    await waitFor(() => expect(result.current.state.error).toBeTruthy());
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 40)); });
    expect(result.current.state.projectionDiscoveryPending).toBe(false);
    expect(statusSpy).toHaveBeenCalledTimes(1);
    unmount();
  });

  it('bounds discovery polling and allows an explicit retry after timeout', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue({ id: versionId, project_id: projectId });
    const statusSpy = vi.spyOn(graphService, 'getStatus').mockRejectedValue({ status: 404, code: 'graph_projection_not_found' });
    const { result, unmount } = renderHook(() => useArchitectureGraph(
      { projectId, repositoryId, analysisId, versionId },
      { discoveryTimeoutMs: 60, discoveryPollIntervalMs: 20 }
    ));
    await waitFor(() => expect(result.current.state.error).toContain('Automatic checks paused'));
    const stoppedCount = statusSpy.mock.calls.length;
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)); });
    expect(statusSpy).toHaveBeenCalledTimes(stoppedCount);
    expect(result.current.state.projectionDiscoveryPending).toBe(false);
    statusSpy.mockResolvedValue({ status: 'FAILED', active_generation_id: null });
    await act(async () => { await result.current.refreshStatus(); });
    expect(result.current.state.status?.status).toBe('FAILED');
    expect(result.current.state.error).toBeNull();
    unmount();
  });

  it('pauses discovery while hidden, resumes on visibility and stops after unmount', async () => {
    let visibility = 'hidden';
    vi.spyOn(document, 'visibilityState', 'get').mockImplementation(() => visibility);
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue({ id: versionId, project_id: projectId });
    const statusSpy = vi.spyOn(graphService, 'getStatus')
      .mockRejectedValueOnce({ status: 404, code: 'graph_projection_not_found' })
      .mockResolvedValue({ status: 'RUNNING' });
    const { result, unmount } = renderHook(() => useArchitectureGraph(
      { projectId, repositoryId, analysisId, versionId }, { discoveryPollIntervalMs: 10, pollIntervalMs: 200 }
    ));
    await waitFor(() => expect(result.current.state.projectionDiscoveryPending).toBe(true));
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 40)); });
    expect(statusSpy).toHaveBeenCalledTimes(1);
    await act(async () => { visibility = 'visible'; document.dispatchEvent(new Event('visibilitychange')); });
    await waitFor(() => expect(result.current.state.status?.status).toBe('RUNNING'));
    expect(statusSpy).toHaveBeenCalledTimes(2);
    unmount();
    await new Promise((resolve) => setTimeout(resolve, 230));
    expect(statusSpy).toHaveBeenCalledTimes(2);
  });

  it('does not treat a disappearing established resource as initial publication discovery', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue({ id: versionId, project_id: projectId });
    vi.spyOn(graphService, 'getStatus').mockResolvedValueOnce({ status: 'FAILED' })
      .mockRejectedValue({ status: 404, code: 'graph_projection_not_found' });
    const { result, unmount } = renderHook(() => useArchitectureGraph(
      { projectId, repositoryId, analysisId, versionId }, { discoveryPollIntervalMs: 10 }
    ));
    await waitFor(() => expect(result.current.state.status?.status).toBe('FAILED'));
    await act(async () => { await result.current.refreshStatus(); });
    expect(result.current.state.error).toContain('not found');
    expect(result.current.state.projectionDiscoveryPending).toBe(false);
    unmount();
  });

  it('shares overlapping manual status refreshes rather than duplicating requests', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue({ id: versionId, project_id: projectId });
    const statusSpy = vi.spyOn(graphService, 'getStatus').mockResolvedValueOnce({ status: 'FAILED' });
    const { result, unmount } = renderHook(() => useArchitectureGraph({ projectId, repositoryId, analysisId, versionId }));
    await waitFor(() => expect(result.current.state.status?.status).toBe('FAILED'));
    let resolve;
    statusSpy.mockImplementation(() => new Promise((done) => { resolve = done; }));
    await act(async () => {
      const first = result.current.refreshStatus();
      const second = result.current.refreshStatus();
      resolve({ status: 'FAILED' });
      await Promise.all([first, second]);
    });
    expect(statusSpy).toHaveBeenCalledTimes(2);
    unmount();
  });

  it('executes rebuild mutation and refreshes status', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue({
      id: versionId,
      project_id: projectId,
    });

    vi.spyOn(graphService, 'getStatus').mockResolvedValue({
      status: 'FAILED',
      active_generation_id: null,
    });

    const rebuildSpy = vi
      .spyOn(graphService, 'requestRebuild')
      .mockResolvedValueOnce({ attempt_status: 'QUEUED' });

    const { result, unmount } = renderHook(() =>
      useArchitectureGraph(
        {
          projectId,
          repositoryId,
          analysisId,
          versionId,
        },
        { pollIntervalMs: 50 }
      )
    );

    await waitFor(() => {
      expect(result.current.state.contextValidated).toBe(true);
    });

    await act(async () => {
      await result.current.requestRebuild();
    });

    expect(rebuildSpy).toHaveBeenCalledWith(versionId, { projectId });
    unmount();
  });

  it('does not continuously refetch an empty window, and retries a failed window explicitly', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue({ id: versionId, project_id: projectId });
    vi.spyOn(graphService, 'getStatus').mockResolvedValue({ project_id: projectId, architecture_version_id: versionId, status: 'COMPLETED', active_generation_id: generationId });
    const windowSpy = vi.spyOn(graphService, 'getWindow')
      .mockRejectedValueOnce({ status: 503 })
      .mockResolvedValue({ scope: { project_id: projectId, architecture_version_id: versionId, generation_id: generationId, resource_state: 'COMPLETED' }, nodes: [], edges: [], truncated: false });
    const { result, unmount } = renderHook(() => useArchitectureGraph({ projectId, repositoryId, analysisId, versionId }));
    await waitFor(() => expect(result.current.state.operations.window?.error).toBeTruthy());
    expect(windowSpy).toHaveBeenCalledTimes(1);
    await act(async () => { await result.current.refreshStatus(); });
    await waitFor(() => expect(result.current.state.operations.window?.inFlight).toBe(false));
    expect(windowSpy).toHaveBeenCalledTimes(2);
    await act(async () => { await result.current.refreshStatus(); });
    expect(windowSpy).toHaveBeenCalledTimes(2);
    unmount();
  });

  it('continues dependency pagination with the original anchor, kinds and limits', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue({ id: versionId, project_id: projectId });
    vi.spyOn(graphService, 'getStatus').mockResolvedValue({ status: 'COMPLETED', active_generation_id: generationId });
    const page = { scope: { project_id: projectId, architecture_version_id: versionId, generation_id: generationId, resource_state: 'COMPLETED' }, nodes: [], edges: [], truncated: false };
    vi.spyOn(graphService, 'getWindow').mockResolvedValue(page);
    const dependencies = vi.spyOn(graphService, 'getDependencies').mockResolvedValueOnce({ ...page, truncated: true, next_cursor: 'opaque-continuation' }).mockResolvedValue(page);
    const { result, unmount } = renderHook(() => useArchitectureGraph({ projectId, repositoryId, analysisId, versionId }));
    await waitFor(() => expect(result.current.state.operations.window?.inFlight).toBe(false));
    await act(async () => { await result.current.expandDependencies(entityId1, { depth: 2, nodeLimit: 12, edgeLimit: 23, relationshipKinds: ['imports', 'calls'] }); });
    await act(async () => { await result.current.loadMore(`dependencies:${entityId1}`); });
    expect(dependencies).toHaveBeenLastCalledWith(versionId, entityId1, expect.objectContaining({ projectId, depth: 2, nodeLimit: 12, edgeLimit: 23, relationshipKinds: ['imports', 'calls'], cursor: 'opaque-continuation' }));
    unmount();
  });

  it('cleans up and aborts active requests on unmount', async () => {
    vi.spyOn(architectureService, 'getVersion').mockImplementation(
      (_v, { signal }) =>
        new Promise((_, reject) => {
          signal?.addEventListener('abort', () => {
            const err = new Error('Aborted');
            err.name = 'AbortError';
            reject(err);
          });
        })
    );

    const { unmount } = renderHook(() =>
      useArchitectureGraph({
        projectId,
        repositoryId,
        analysisId,
        versionId,
      })
    );

    unmount();
  });
});
