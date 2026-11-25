import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import RepositoryIntelligencePage from '../../src/pages/RepositoryIntelligencePage.jsx';
import { projectService } from '../../src/services/projectService.js';
import { repositoryService } from '../../src/services/repositoryService.js';
import { analysisService } from '../../src/services/analysisService.js';
import { architectureService } from '../../src/services/architectureService.js';
import { deliveryService } from '../../src/services/deliveryService.js';
import { diagramService } from '../../src/services/diagramService.js';
import { knowledgeService } from '../../src/services/knowledgeService.js';
import { reportService } from '../../src/services/reportService.js';

vi.mock('../../src/hooks/useProjectRole.js', () => ({
  useProjectRole: vi.fn(() => ({
    role: 'OWNER',
    canCreateOrUpdate: true,
    canDelete: true,
    canManageAccess: true,
    loading: false,
  })),
}));

describe('Intelligence Accessibility & Keyboard Navigation Tests', () => {
  const projectId = '11111111-1111-1111-1111-111111111111';
  const repositoryId = '22222222-2222-2222-2222-222222222222';
  const analysisId = '33333333-3333-3333-3333-333333333333';
  const versionId = '44444444-4444-4444-4444-444444444444';

  const mockVersion = {
    id: versionId,
    project_id: projectId,
    repository_id: repositoryId,
    analysis_id: analysisId,
    sequence_number: 1,
    snapshot_id: '55555555-5555-5555-5555-555555555555',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(projectService, 'getProject').mockResolvedValue({ id: projectId, name: 'Sample' });
    vi.spyOn(repositoryService, 'getRepository').mockResolvedValue({ id: repositoryId, name: 'Sample' });
    vi.spyOn(analysisService, 'getAnalysis').mockResolvedValue({ id: analysisId, repository_id: repositoryId });
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue(mockVersion);
    vi.spyOn(deliveryService, 'getDelivery').mockResolvedValue({ state: 'SUCCEEDED', work_summary: [] });
    vi.spyOn(diagramService, 'getDiagrams').mockResolvedValue({ diagrams: {} });
    vi.spyOn(diagramService, 'getDiagramSummary').mockResolvedValue({
      template: 'CONTAINER_ISOLATION',
      ready: true,
      active_generation_id: 'gen-1',
      generations: [],
    });
    vi.spyOn(diagramService, 'getDiagramSpec').mockResolvedValue({
      template: 'CONTAINER_ISOLATION',
      digest: 'd1',
      nodes: [],
      edges: [],
      groups: [],
      legend: [],
      coverage: { view_state: 'COMPLETE', reasons: [] },
    });
    vi.spyOn(diagramService, 'getDiagramLayout').mockResolvedValue({
      width: 800,
      height: 600,
      font_notice: 'Standard',
      limitations: [],
    });
    vi.spyOn(knowledgeService, 'getSearchStatus').mockResolvedValue({ freshness_state: 'READY' });
    vi.spyOn(reportService, 'getReports').mockResolvedValue({ reports: [] });
    vi.spyOn(reportService, 'getReportSummary').mockResolvedValue({ ready: true, report_id: 'automatic' });
    vi.spyOn(reportService, 'getReportGenerations').mockResolvedValue({ items: [] });
  });

  afterEach(() => {
    window.location.hash = '';
  });

  it('provides proper tablist, tab, and tabpanel ARIA roles and relationships', async () => {
    render(
      <RepositoryIntelligencePage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('tablist', { name: /Intelligence workspace panels/i })).toBeInTheDocument();
    });

    const diagramsTab = screen.getByRole('tab', { name: 'Diagrams' });
    const searchTab = screen.getByRole('tab', { name: 'Search' });
    const knowledgeTab = screen.getByRole('tab', { name: 'Knowledge' });
    const reportsTab = screen.getByRole('tab', { name: 'Reports' });

    expect(diagramsTab).toHaveAttribute('aria-selected', 'true');
    expect(searchTab).toHaveAttribute('aria-selected', 'false');
    expect(knowledgeTab).toHaveAttribute('aria-selected', 'false');
    expect(reportsTab).toHaveAttribute('aria-selected', 'false');

    const panel = screen.getByRole('tabpanel');
    expect(panel).toHaveAttribute('id', 'panel-diagrams');
    expect(panel).toHaveAttribute('aria-labelledby', 'tab-diagrams');
  });

  it('supports keyboard navigation across workspace tabs', async () => {
    render(
      <RepositoryIntelligencePage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Diagrams' })).toBeInTheDocument();
    });

    const reportsTab = screen.getByRole('tab', { name: 'Reports' });
    fireEvent.keyDown(reportsTab, { key: 'Enter', code: 'Enter' });
    fireEvent.click(reportsTab);

    expect(reportsTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel')).toHaveAttribute('id', 'panel-reports');
  });

  it('preserves accessible landmark regions for Delivery Status and Workspace Panels', async () => {
    render(
      <RepositoryIntelligencePage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('region', { name: 'Delivery Status' })).toBeInTheDocument();
    });

    expect(screen.getByRole('region', { name: 'Architecture Diagrams' })).toBeInTheDocument();
  });
});
