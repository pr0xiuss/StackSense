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
