import React from 'react';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import ArchitectureExplorerPage from '../../src/pages/ArchitectureExplorerPage.jsx';
import { architectureService } from '../../src/services/architectureService.js';
import { projectService } from '../../src/services/projectService.js';
import { repositoryService } from '../../src/services/repositoryService.js';
import { graphService } from '../../src/services/graphService.js';
import { parseCurrentRoute } from '../../src/App.jsx';

vi.mock('../../src/components/dashboard/DashboardHeader.jsx', () => ({
  default: () => <header data-testid="dashboard-header">Mock Header</header>,
}));

vi.mock('../../src/hooks/useProjectRole.js', () => ({
  useProjectRole: vi.fn(() => ({
    role: 'OWNER',
    loading: false,
    error: null,
    canCreateOrUpdate: true,
    canDelete: true,
    canManageAccess: true,
  })),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.location.hash = '';
  window.history.replaceState(null, '', '/');
});

describe('ArchitectureExplorerPage & Explorer Routing', () => {
  const projectId = '11111111-1111-1111-1111-111111111111';
  const repositoryId = '22222222-2222-2222-2222-222222222222';
  const analysisId = '33333333-3333-3333-3333-333333333333';
  const versionId = '44444444-4444-4444-4444-444444444444';
  const generationId = '55555555-5555-5555-5555-555555555555';
  const entityId = '66666666-6666-6666-6666-666666666666';

  const mockVersion = {
    id: versionId,
    project_id: projectId,
    repository_id: repositoryId,
    analysis_id: analysisId,
    sequence_number: 1,
    content_digest: 'sha256-1122334455667788',
    architecture_schema_version: '1.0.0',
    entity_count: 8,
    relationship_count: 6,
    evidence_count: 4,
    unresolved_relationship_count: 0,
    conflict_count: 0,
  };

  const mockStatus = {
    project_id: projectId,
    architecture_version_id: versionId,
    status: 'COMPLETED',
    active_generation_id: generationId,
    schema_version: '1.0.0',
    counts: {
      entities: 8,
      relationships: 6,
      evidence: 4,
      unresolved: 0,
      conflicts: 0,
    },
    is_out_of_date: false,
    active_attempt: null,
  };

  const mockWindow = {
    scope: {
      project_id: projectId,
      architecture_version_id: versionId,
      generation_id: generationId,
      resource_state: 'COMPLETED',
      counts: {
        entities: 8,
        relationships: 6,
        evidence: 4,
        unresolved: 0,
        conflicts: 0,
      },
    },
    nodes: [
      {
        architecture_entity_id: entityId,
        logical_id: 'svc-auth-gw',
        name: 'AuthGatewayService',
        canonical_kind: 'service',
        namespace: 'backend.auth',
        fact_status: 'CONFIRMED',
        evidence_logical_ids: ['ev-01'],
      },
    ],
    edges: [],
    truncated: false,
    next_cursor: null,
  };

  it('validates context chain and renders Explorer shell with graph components', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue(mockVersion);
    vi.spyOn(projectService, 'getProject').mockResolvedValue({ id: projectId, name: 'Proj Alpha' });
    vi.spyOn(repositoryService, 'getRepository').mockResolvedValue({ id: repositoryId, name: 'Repo Beta' });
    vi.spyOn(graphService, 'getStatus').mockResolvedValue(mockStatus);
    vi.spyOn(graphService, 'getWindow').mockResolvedValue(mockWindow);

    render(
      <ArchitectureExplorerPage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    await waitFor(() => {
      expect(architectureService.getVersion).toHaveBeenCalledWith(versionId, { projectId });
    });

    expect(await screen.findByRole('heading', { name: 'Architecture Explorer' }, { timeout: 8000 })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Architecture Explorer Breadcrumb' })).toBeInTheDocument();

    const backLink = screen.getByRole('link', { name: /^← Architecture Model$/i });
    expect(backLink).toHaveAttribute(
      'href',
      `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}`
    );

    // Wait for initial graph window to load node
    expect(await screen.findByText('AuthGatewayService', undefined, { timeout: 8000 })).toBeInTheDocument();
    expect(screen.getByText('backend.auth')).toBeInTheDocument();

    // Node card click triggers inspector update
    const nodeCard = screen.getByText('AuthGatewayService').closest('.arch-graph-node');
    fireEvent.click(nodeCard);
    expect(screen.getByText('svc-auth-gw')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Attached Evidence \(1\)/ })).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(screen.getByRole('button', { name: /Structured List/ }));
    expect(screen.queryByTestId('graph-inspector')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Fit all loaded nodes' })).not.toBeInTheDocument();
    expect(screen.getByTestId('graph-list-view')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'View on map' }));
    expect(screen.getByTestId('graph-inspector')).toBeInTheDocument();

    // Toggle structured list tab
    const listTabBtn = screen.getByRole('button', { name: /structured list/i });
    fireEvent.click(listTabBtn);
    expect(listTabBtn).toHaveClass('active');
    expect(screen.getByTestId('graph-list-view')).toBeInTheDocument();
  }, 15000);

  it('list Neighbors selects its anchor, executes the request and opens neighborhood mode even when nodes were already loaded', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue(mockVersion);
    vi.spyOn(projectService, 'getProject').mockResolvedValue({ id: projectId, name: 'Project' });
    vi.spyOn(repositoryService, 'getRepository').mockResolvedValue({ id: repositoryId, name: 'Repository' });
    vi.spyOn(graphService, 'getStatus').mockResolvedValue(mockStatus);
    vi.spyOn(graphService, 'getWindow').mockResolvedValue(mockWindow);
    vi.spyOn(graphService, 'getNodeDetail').mockResolvedValue(mockWindow.nodes[0]);
    const neighbors = vi.spyOn(graphService, 'getNeighborhood').mockResolvedValue(mockWindow);
    render(<ArchitectureExplorerPage projectId={projectId} repositoryId={repositoryId} analysisId={analysisId} versionId={versionId} />);
    await screen.findByText('AuthGatewayService');
    fireEvent.click(screen.getByRole('button', { name: /Structured List/ }));
    const button = screen.getByRole('button', { name: 'Expand neighborhood of AuthGatewayService' });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    await waitFor(() => expect(neighbors).toHaveBeenCalledWith(versionId, entityId, expect.objectContaining({ projectId, depth: 1, direction: 'both' })));
    expect(screen.queryByTestId('graph-list-view')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Mode:')).toHaveValue('neighborhood');
    expect(screen.getByTestId(`arch-node-${entityId}`)).toHaveClass('selected');
    expect(neighbors).toHaveBeenCalledTimes(1);
  });

  it('exercises complete live journey: initial window -> select -> expand -> continuation -> list -> rebuild -> generation reload', async () => {
    const node1 = {
      architecture_entity_id: '11111111-1111-1111-1111-111111111111',
      logical_id: 'svc-auth',
      name: 'AuthService',
      canonical_kind: 'service',
      namespace: 'stacksense.auth',
      fact_status: 'CONFIRMED',
      evidence_logical_ids: ['ev-01'],
    };
    const node2 = {
      architecture_entity_id: '22222222-2222-2222-2222-222222222222',
      logical_id: 'db-auth',
      name: 'AuthDb',
      canonical_kind: 'database',
      namespace: 'stacksense.db',
      fact_status: 'CONFIRMED',
      evidence_logical_ids: [],
    };
    const node3 = {
      architecture_entity_id: '33333333-3333-3333-3333-333333333333',
      logical_id: 'svc-cache',
      name: 'RedisCache',
      canonical_kind: 'cache',
      namespace: 'stacksense.cache',
      fact_status: 'CONFIRMED',
      evidence_logical_ids: [],
    };
    const edge1 = {
      architecture_relationship_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      source_entity_id: node1.architecture_entity_id,
      target_entity_id: node2.architecture_entity_id,
      canonical_kind: 'calls',
      logical_id: 'rel-auth-db',
      evidence_logical_ids: [],
    };
    const edge2 = {
      architecture_relationship_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      source_entity_id: node1.architecture_entity_id,
      target_entity_id: node3.architecture_entity_id,
      canonical_kind: 'uses',
      logical_id: 'rel-auth-cache',
      evidence_logical_ids: [],
    };

    const initialWindowWithCursor = {
      scope: {
        project_id: projectId,
        architecture_version_id: versionId,
        generation_id: generationId,
        resource_state: 'COMPLETED',
        counts: { entities: 2, relationships: 1, evidence: 1, unresolved: 0, conflicts: 0 },
      },
      nodes: [node1, node2],
      edges: [edge1],
      truncated: true,
      next_cursor: 'cursor-page-2',
    };

    const page2Window = {
      scope: {
        project_id: projectId,
        architecture_version_id: versionId,
        generation_id: generationId,
        resource_state: 'COMPLETED',
        counts: { entities: 3, relationships: 2, evidence: 1, unresolved: 0, conflicts: 0 },
      },
      nodes: [node1, node3],
      edges: [edge2],
      truncated: false,
      next_cursor: null,
    };

    vi.spyOn(architectureService, 'getVersion').mockResolvedValue(mockVersion);
    vi.spyOn(projectService, 'getProject').mockResolvedValue({ id: projectId, name: 'Proj Alpha' });
    vi.spyOn(repositoryService, 'getRepository').mockResolvedValue({ id: repositoryId, name: 'Repo Beta' });
    vi.spyOn(graphService, 'getStatus').mockResolvedValue(mockStatus);
    vi.spyOn(graphService, 'getWindow').mockImplementation((vId, opts) => {
      if (opts?.cursor === 'cursor-page-2') {
        return Promise.resolve(page2Window);
      }
      return Promise.resolve(initialWindowWithCursor);
    });
    vi.spyOn(graphService, 'requestRebuild').mockResolvedValue({ status: 'accepted', attempt_number: 2 });

    render(
      <ArchitectureExplorerPage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    // 1. Initial window loads
    expect(await screen.findByText('AuthService', undefined, { timeout: 8000 })).toBeInTheDocument();
    expect(screen.getByText('AuthDb')).toBeInTheDocument();

    // 2. Select node
    const nodeCard = screen.getByText('AuthService').closest('.arch-graph-node');
    fireEvent.click(nodeCard);
    expect(screen.getByText('svc-auth')).toBeInTheDocument();

    // 3. Continuation: Load more
    const loadMoreBtn = screen.getByRole('button', { name: /load more/i });
    expect(loadMoreBtn).toBeInTheDocument();
    fireEvent.click(loadMoreBtn);

    // Wait for page 2 node to merge
    expect(await screen.findByText('RedisCache', undefined, { timeout: 8000 })).toBeInTheDocument();

    // 4. Structured list toggle
    const listTabBtn = screen.getByRole('button', { name: /structured list/i });
    fireEvent.click(listTabBtn);
    expect(screen.getByTestId('graph-list-view')).toBeInTheDocument();

    // 5. Trigger Rebuild Graph
    const rebuildBtn = screen.getByRole('button', { name: /rebuild graph/i });
    fireEvent.click(rebuildBtn);

    await waitFor(() => {
      expect(graphService.requestRebuild).toHaveBeenCalledWith(versionId, { projectId });
    });
  }, 15000);

  it('handles historical STALE version and displays STALE indicator', async () => {
    const staleStatus = {
      ...mockStatus,
      status: 'STALE',
    };
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue(mockVersion);
    vi.spyOn(projectService, 'getProject').mockResolvedValue({ id: projectId, name: 'Proj Alpha' });
    vi.spyOn(repositoryService, 'getRepository').mockResolvedValue({ id: repositoryId, name: 'Repo Beta' });
    vi.spyOn(graphService, 'getStatus').mockResolvedValue(staleStatus);
    vi.spyOn(graphService, 'getWindow').mockResolvedValue(mockWindow);

    render(
      <ArchitectureExplorerPage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    expect(await screen.findByText(/Historical/i, undefined, { timeout: 8000 })).toBeInTheDocument();
  }, 15000);

  it('handles graph unavailable 503 gracefully preserving loaded view and offering retry', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue(mockVersion);
    vi.spyOn(projectService, 'getProject').mockResolvedValue({ id: projectId, name: 'Proj Alpha' });
    vi.spyOn(repositoryService, 'getRepository').mockResolvedValue({ id: repositoryId, name: 'Repo Beta' });
    vi.spyOn(graphService, 'getStatus').mockRejectedValue({ status: 503, message: 'Service unavailable' });

    render(
      <ArchitectureExplorerPage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    // A failed projection is not presented as ready, and query controls stay disabled.
    expect(await screen.findByRole('alert', undefined, { timeout: 8000 })).toBeInTheDocument();
    expect(screen.getByText(/Graph service is temporarily unavailable. Loaded data is preserved./i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    expect(screen.queryByText(/Projection is ready/i)).not.toBeInTheDocument();
    expect(screen.getByText('Graph unavailable')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /mode/i })).toBeDisabled();
  }, 15000);

  it('rejects version chain mismatch in Explorer page', async () => {
    const mismatchedVersion = {
      ...mockVersion,
      project_id: '99999999-9999-9999-9999-999999999999',
    };
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue(mismatchedVersion);

    render(
      <ArchitectureExplorerPage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    expect(
      await screen.findByText(
        'Architecture version does not match project, repository, or analysis context.',
        undefined,
        { timeout: 8000 }
      )
    ).toBeInTheDocument();
  });

  it('correctly parses valid Explorer route', () => {
    window.location.hash = `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/graph`;
    const route = parseCurrentRoute();
    expect(route).toEqual({
      view: 'explorer',
      projectId,
      repositoryId,
      analysisId,
      versionId,
    });
  });

  it('correctly parses exact-version Architecture Model route', () => {
    window.location.hash = `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}`;
    const route = parseCurrentRoute();
    expect(route).toEqual({
      view: 'architecture',
      projectId,
      repositoryId,
      analysisId,
      versionId,
    });
  });

  it('correctly parses legacy Architecture Model route without versionId', () => {
    window.location.hash = `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture`;
    const route = parseCurrentRoute();
    expect(route).toEqual({
      view: 'architecture',
      projectId,
      repositoryId,
      analysisId,
      versionId: undefined,
    });
  });

  it('rejects malformed UUIDs in Explorer route with Route Error', () => {
    window.location.hash = `#/projects/not-a-uuid/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/graph`;
    const route = parseCurrentRoute();
    expect(route.view).toBe('route_error');
    expect(route.message).toMatch(/Malformed UUID in Graph Explorer route parameters/i);
  });

  it('rejects unmatched trailing path on Explorer route with Route Error', () => {
    window.location.hash = `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/graph/unsupported/tail`;
    const route = parseCurrentRoute();
    expect(route.view).toBe('route_error');
    expect(route.message).toMatch(/Unmatched trailing path on Graph Explorer route/i);
  });
});


