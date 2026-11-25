import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DiagramPanel } from '../../src/components/intelligence/DiagramPanel.jsx';
import { diagramService } from '../../src/services/diagramService.js';

vi.mock('../../src/services/diagramService.js', () => ({
  diagramService: {
    getDiagrams: vi.fn(),
    getDiagramSummary: vi.fn(),
    getDiagramSpec: vi.fn(),
    getDiagramLayout: vi.fn(),
    viewDiagram: vi.fn(),
    getDiagramMembers: vi.fn(),
    exportDiagramJson: vi.fn(),
    exportDiagramSvg: vi.fn(),
  },
}));

vi.mock('../../src/components/diagrams/DiagramView.jsx', () => ({
  DiagramView: ({ prepared, onExport, onSelect }) => (
    <div data-testid="mock-diagram-view">
      <h3>Mock DiagramView: {prepared.template}</h3>
      <button onClick={() => onExport?.('svg')}>Mock Export SVG</button>
      <button onClick={() => onSelect?.({ id: 'node-1', name: 'ServiceA' })}>Select Node</button>
    </div>
  ),
}));

describe('DiagramPanel Component', () => {
  const versionId = '44444444-4444-4444-8444-444444444444';
  const projectId = '11111111-1111-4111-8111-111111111111';

  beforeEach(() => {
    vi.clearAllMocks();

    diagramService.getDiagrams.mockResolvedValue({
      diagrams: {
        system_overview: { ready: true },
        component_architecture: { ready: true },
        dependency_map: { ready: true },
        data_flow: { ready: false },
      },
    });

    diagramService.getDiagramSummary.mockResolvedValue({
      template: 'system_overview',
      ready: true,
      active_generation_id: 'gen-123',
      generations: [
        { generation_id: 'gen-123', created_at: new Date().toISOString() },
      ],
    });

    diagramService.getDiagramSpec.mockResolvedValue({
      template: 'system_overview',
      digest: 'digest-123',
      nodes: [],
      edges: [],
      groups: [],
      legend: [],
      coverage: { view_state: 'COMPLETE', reasons: [] },
    });

    diagramService.getDiagramLayout.mockResolvedValue({
      width: 800,
      height: 600,
      font_notice: 'Standard metrics',
      limitations: [],
    });
  });

  it('renders all four template tabs and loads active diagram', async () => {
    render(<DiagramPanel versionId={versionId} projectId={projectId} />);

    expect(screen.getByRole('tab', { name: /System Overview/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Component Architecture/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Dependency Map/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Data Flow/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId('mock-diagram-view')).toBeInTheDocument();
    });

    expect(screen.getByText(/Mock DiagramView: system_overview/i)).toBeInTheDocument();
  });

  it('switches template when tab is clicked', async () => {
    diagramService.getDiagramSummary.mockResolvedValueOnce({
      template: 'component_architecture',
      ready: true,
      active_generation_id: 'gen-comm-1',
      generations: [{ generation_id: 'gen-comm-1', created_at: new Date().toISOString() }],
    });

    render(<DiagramPanel versionId={versionId} projectId={projectId} />);

    await waitFor(() => {
      expect(screen.getByTestId('mock-diagram-view')).toBeInTheDocument();
    });

    const commTab = screen.getByRole('tab', { name: /Component Architecture/i });
    fireEvent.click(commTab);

    await waitFor(() => {
      expect(diagramService.getDiagramSummary).toHaveBeenCalledWith(
        versionId,
        'component_architecture',
        expect.anything()
      );
    });
  });

  it('propagates onSelectSubject when entity is selected in DiagramView', async () => {
    const handleSelectSubject = vi.fn();

    render(
      <DiagramPanel
        versionId={versionId}
        projectId={projectId}
        onSelectSubject={handleSelectSubject}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('mock-diagram-view')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Select Node'));

    expect(handleSelectSubject).toHaveBeenCalledWith({
      id: 'node-1',
      name: 'ServiceA',
    });
  });

  it('shows error card without breaking when template diagram fails to load', async () => {
    diagramService.getDiagramSpec.mockRejectedValueOnce(new Error('Spec generation not found'));

    render(<DiagramPanel versionId={versionId} projectId={projectId} />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByText(/Spec generation not found/i)).toBeInTheDocument();
  });
});
