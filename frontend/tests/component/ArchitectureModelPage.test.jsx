import React from 'react';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import ArchitectureModelPage from '../../src/pages/ArchitectureModelPage.jsx';
import { analysisService } from '../../src/services/analysisService.js';
import { architectureService } from '../../src/services/architectureService.js';
import { projectService } from '../../src/services/projectService.js';
import { repositoryService } from '../../src/services/repositoryService.js';
import * as overviewModule from '../../src/services/architectureOverview.js';

vi.mock('../../src/components/dashboard/DashboardHeader.jsx', () => ({
  default: () => <header data-testid="dashboard-header">Mock Header</header>,
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('ArchitectureModelPage', () => {
  const projectId = '11111111-1111-1111-1111-111111111111';
  const repositoryId = '22222222-2222-2222-2222-222222222222';
  const analysisId = '33333333-3333-3333-3333-333333333333';
  const versionId = '44444444-4444-4444-4444-444444444444';

  const mockVersion = {
    id: versionId,
    project_id: projectId,
    repository_id: repositoryId,
    analysis_id: analysisId,
    sequence_number: 2,
    content_digest: 'sha256-abcdef0123456789',
    architecture_schema_version: '1.0.0',
    published_at: '2026-11-15T10:00:00Z',
    entity_count: 12,
    relationship_count: 8,
    evidence_count: 5,
    unresolved_relationship_count: 1,
    conflict_count: 0,
  };

  it('preserves legacy behavior when versionId is not supplied', async () => {
    vi.spyOn(analysisService, 'getAnalysisArchitecture').mockResolvedValue(mockVersion);
    vi.spyOn(projectService, 'getProject').mockResolvedValue({ id: projectId, name: 'Test Proj' });
    vi.spyOn(repositoryService, 'getRepository').mockResolvedValue({ id: repositoryId, name: 'Test Repo' });
    vi.spyOn(overviewModule, 'loadArchitectureOverview').mockResolvedValue({ entities: [], relationships: [] });

    render(
      <ArchitectureModelPage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
      />
    );

    await waitFor(() => {
      expect(analysisService.getAnalysisArchitecture).toHaveBeenCalledWith(analysisId, { projectId });
    });

    expect(await screen.findByText('Architecture Model v2')).toBeInTheDocument();
    // Explore Graph link should be present and point to exact version
    const exploreBtn = screen.getByRole('link', { name: /explore graph/i });
    expect(exploreBtn).toHaveAttribute(
      'href',
      `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/graph`
    );
  });

  it('loads exact version via architectureService.getVersion when versionId is provided', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue(mockVersion);
    vi.spyOn(projectService, 'getProject').mockResolvedValue({ id: projectId, name: 'Test Proj' });
    vi.spyOn(repositoryService, 'getRepository').mockResolvedValue({ id: repositoryId, name: 'Test Repo' });
    vi.spyOn(overviewModule, 'loadArchitectureOverview').mockResolvedValue({ entities: [], relationships: [] });

    render(
      <ArchitectureModelPage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    await waitFor(() => {
      expect(architectureService.getVersion).toHaveBeenCalledWith(versionId, { projectId });
    });

    expect(await screen.findByText('Architecture Model v2')).toBeInTheDocument();
  });

  it('rejects version context chain mismatch with error screen', async () => {
    // Return version with different analysis_id
    const mismatchedVersion = {
      ...mockVersion,
      analysis_id: '99999999-9999-9999-9999-999999999999',
    };
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue(mismatchedVersion);
    vi.spyOn(projectService, 'getProject').mockResolvedValue({ id: projectId, name: 'Test Proj' });
    vi.spyOn(repositoryService, 'getRepository').mockResolvedValue({ id: repositoryId, name: 'Test Repo' });

    render(
      <ArchitectureModelPage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    expect(
      await screen.findByText('Architecture version does not match project, repository, or analysis context.')
    ).toBeInTheDocument();
  });
});

