import React from 'react';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
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

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.location.hash = '';
});

describe('RepositoryIntelligencePage Component Tests', () => {
  const projectId = '11111111-1111-1111-1111-111111111111';
  const repositoryId = '22222222-2222-2222-2222-222222222222';
  const analysisId = '33333333-3333-3333-3333-333333333333';
  const versionId = '44444444-4444-4444-4444-444444444444';

  const mockProject = { id: projectId, name: 'Sample Project' };
  const mockRepo = { id: repositoryId, name: 'Sample Repo' };
  const mockAnalysis = {
    id: analysisId,
    repository_id: repositoryId,
    snapshot_id: '55555555-5555-5555-5555-555555555555',
  };
  const mockVersion = {
    id: versionId,
    project_id: projectId,
    repository_id: repositoryId,
    analysis_id: analysisId,
    sequence_number: 1,
    snapshot_id: '55555555-5555-5555-5555-555555555555',
  };

  const mockDelivery = {
    state: 'SUCCEEDED',
    completed_work_items: 6,
    total_work_items: 6,
    receipt_digest: 'digest-receipt-1234',
    work_summary: [
      { work_id: 'w1', kind: 'CONTAINER_ISOLATION', status: 'SUCCEEDED' },
      { work_id: 'w2', kind: 'SEARCH_INDEX', status: 'SUCCEEDED' },
    ],
  };

  beforeEach(() => {
    vi.spyOn(projectService, 'getProject').mockResolvedValue(mockProject);
    vi.spyOn(repositoryService, 'getRepository').mockResolvedValue(mockRepo);
    vi.spyOn(analysisService, 'getAnalysis').mockResolvedValue(mockAnalysis);
    vi.spyOn(architectureService, 'getVersion').mockResolvedValue(mockVersion);
    vi.spyOn(deliveryService, 'getDelivery').mockResolvedValue(mockDelivery);
    vi.spyOn(diagramService, 'getDiagrams').mockResolvedValue({ diagrams: {} });
    vi.spyOn(diagramService, 'getDiagramSummary').mockResolvedValue({
      template: 'CONTAINER_ISOLATION',
      ready: true,
      active_generation_id: 'gen-1',
      generations: [],
    });
    vi.spyOn(diagramService, 'getDiagramSpec').mockResolvedValue({
      template: 'CONTAINER_ISOLATION',
      digest: 'digest-spec',
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
    vi.spyOn(knowledgeService, 'getSearchStatus').mockResolvedValue({
      freshness_state: 'READY',
      indexed_documents_count: 88,
    });
    vi.spyOn(reportService, 'getReports').mockResolvedValue({
      reports: [{ id: 'automatic', name: 'Executive Architecture Report' }],
      next_cursor: null,
    });
    vi.spyOn(reportService, 'getReportSummary').mockResolvedValue({
      report_id: 'automatic',
      name: 'Executive Architecture Report',
      ready: true,
      active_generation_id: 'gen-1',
    });
    vi.spyOn(reportService, 'getReportGenerations').mockResolvedValue({
      generations: [
        {
          generation_id: 'gen-1',
          created_at: '2026-03-30T10:00:00Z',
          format: 'pdf',
          status: 'SUCCEEDED',
        },
      ],
      next_cursor: null,
    });
  });

  it('renders loading state initially', () => {
    render(
      <RepositoryIntelligencePage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    expect(screen.getByText(/loading repository intelligence/i)).toBeInTheDocument();
  });

  it('renders header, title, and default Diagrams tab when metadata resolves', async () => {
    render(
      <RepositoryIntelligencePage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/repository intelligence/i)).toBeInTheDocument();
    });

    expect(screen.getByText('Sample Project')).toBeInTheDocument();
    expect(screen.getByText('Sample Repo')).toBeInTheDocument();
    expect(screen.getByText('v1')).toBeInTheDocument();

    const diagramsTab = screen.getByRole('tab', { name: 'Diagrams' });
    expect(diagramsTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('region', { name: 'Architecture Diagrams' })).toBeInTheDocument();
  });

  it('switches tabs and activates corresponding panel', async () => {
    render(
      <RepositoryIntelligencePage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/repository intelligence/i)).toBeInTheDocument();
    });

    // 1. Search Tab
    const searchTab = screen.getByRole('tab', { name: 'Search' });
    fireEvent.click(searchTab);

    expect(searchTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('region', { name: 'Lexical Search' })).toBeInTheDocument();

    // 2. Knowledge Tab
    const knowledgeTab = screen.getByRole('tab', { name: 'Knowledge' });
    fireEvent.click(knowledgeTab);
    expect(knowledgeTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('region', { name: 'Knowledge & Context' })).toBeInTheDocument();

    // 3. Reports Tab
    const reportsTab = screen.getByRole('tab', { name: 'Reports' });
    fireEvent.click(reportsTab);
    expect(reportsTab).toHaveAttribute('aria-selected', 'true');
    await waitFor(() => {
      expect(screen.getByRole('region', { name: 'Architecture Reports' })).toBeInTheDocument();
    });
  });

  it('renders error state when scope validation detects cross-resource mismatch', async () => {
    vi.spyOn(architectureService, 'getVersion').mockResolvedValueOnce({
      ...mockVersion,
      repository_id: '99999999-9999-9999-9999-999999999999', // Mismatched repository!
    });

    render(
      <RepositoryIntelligencePage
        projectId={projectId}
        repositoryId={repositoryId}
        analysisId={analysisId}
        versionId={versionId}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(
      screen.getByText(/architecture version does not belong to the selected repository/i)
    ).toBeInTheDocument();
  });
});
