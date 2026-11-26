import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DiagramPanel } from '../../src/components/intelligence/DiagramPanel.jsx';
import { diagramService } from '../../src/services/diagramService.js';
import { diagramFixture } from '../diagramFixtures.js';

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
    getLocalPreview: vi.fn(),
  },
}));

vi.mock('../../src/components/diagrams/DiagramView.jsx', () => ({
  DiagramView: ({ prepared, onExport, onSelect }) => (
    <div data-testid="mock-diagram-view">
      <h3>Mock DiagramView: {prepared.spec.template}</h3>
      <button onClick={() => onExport?.('svg')}>Mock Export SVG</button>
      <button onClick={() => onSelect?.({ id: 'node-1', name: 'ServiceA' })}>Select Node</button>
    </div>
  ),
}));

vi.mock('../../src/components/diagrams/DiagramCanvas.jsx', () => ({
  DiagramCanvas: ({ spec, onSelect }) => <div data-testid="local-canvas">{spec.template}<button onClick={() => onSelect(spec.nodes[0].entity)}>Select local node</button></div>,
}));

describe('DiagramPanel Component', () => {
  const fixture = diagramFixture();
  const versionId = fixture.descriptor.reference.scope.architecture_version_id;
  const projectId = fixture.descriptor.reference.scope.project_id;

  beforeEach(() => {
    vi.clearAllMocks();
    diagramService.getLocalPreview.mockImplementation(async (_version, template) => ({ mode: 'local_unpublished', svg_base64: 'PHN2Zz4=', ...diagramFixture(template) }));

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
      availability: 'READY',
      reference: fixture.descriptor.reference,
    });
    diagramService.exportDiagramJson.mockImplementation(async (_version, template) => diagramFixture(template));

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
    diagramService.exportDiagramJson.mockRejectedValueOnce(new Error('Spec generation not found'));

    render(<DiagramPanel versionId={versionId} projectId={projectId} />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByText(/Spec generation not found/i)).toBeInTheDocument();
  });

  it('reports a diagram that is not scheduled without attempting an export', async () => {
    diagramService.getDiagramSummary.mockResolvedValueOnce({
      template: 'system_overview', availability: 'NOT_SCHEDULED',
      canonical_scope: {}, delivery_scope: null, reference: null,
    });
    render(<DiagramPanel versionId={versionId} projectId={projectId} />);
    expect(await screen.findByTestId('local-canvas')).toHaveTextContent('system_overview');
    expect(diagramService.getLocalPreview).toHaveBeenCalledWith(versionId, 'system_overview', expect.objectContaining({ projectId }));
    expect(screen.getByText(/not a published artifact/i)).toBeInTheDocument();
    expect(diagramService.exportDiagramJson).not.toHaveBeenCalled();
  });

  it('does not mask an authorization or integrity failure with a preview', async () => {
    diagramService.getDiagramSummary.mockRejectedValueOnce(new Error('Access denied'));
    render(<DiagramPanel versionId={versionId} projectId={projectId} />);
    expect(await screen.findByText('Access denied')).toBeInTheDocument();
    expect(diagramService.getLocalPreview).not.toHaveBeenCalled();
  });

  it('starts local generation if the published status request times out', async () => {
    const error = Object.assign(new Error('Upstream request timed out.'), { status: 504 });
    diagramService.getDiagramSummary.mockRejectedValueOnce(error);
    render(<DiagramPanel versionId={versionId} projectId={projectId} />);
    expect(await screen.findByTestId('local-canvas')).toHaveTextContent('system_overview');
    expect(diagramService.getLocalPreview).toHaveBeenCalledWith(versionId, 'system_overview', expect.objectContaining({ projectId }));
  });

  it('shows the canonical preview when diagram storage is unavailable', async () => {
    diagramService.getDiagramSummary.mockResolvedValueOnce({
      template: 'system_overview', availability: 'UNAVAILABLE',
      reason: 'diagram_store_unavailable', reference: null,
    });
    render(<DiagramPanel versionId={versionId} projectId={projectId} />);
    expect(await screen.findByTestId('local-canvas')).toHaveTextContent('system_overview');
    expect(diagramService.exportDiagramJson).not.toHaveBeenCalled();
  });

  it('generates the selected template locally when storage is unavailable', async () => {
    diagramService.getDiagramSummary.mockImplementation(async (_id, template) => ({
      template, availability: 'UNAVAILABLE', reason: 'diagram_store_unavailable', reference: null,
    }));
    render(<DiagramPanel versionId={versionId} projectId={projectId} />);
    await screen.findByTestId('local-canvas');
    expect(screen.getByRole('link', { name: 'Download SVG' })).toHaveAttribute('download', 'local-system_overview.svg');
    expect(screen.getByRole('button', { name: 'Download JSON' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: 'Select local node' }));
    expect(screen.getByLabelText('Selected element')).toHaveTextContent(fixture.spec.nodes[0].name);
    fireEvent.click(screen.getByRole('tab', { name: /Dependency Map/i }));
    await waitFor(() => expect(screen.getByTestId('local-canvas')).toHaveTextContent('dependency_map'));
    expect(diagramService.getLocalPreview).toHaveBeenCalledWith(versionId, 'dependency_map', expect.objectContaining({ projectId }));
    fireEvent.click(screen.getByRole('tab', { name: /System Overview/i }));
    await waitFor(() => expect(screen.getByTestId('local-canvas')).toHaveTextContent('system_overview'));
    expect(diagramService.getLocalPreview).toHaveBeenCalledTimes(2);
  });

  it('downloads the local JSON without claiming a published generation', async () => {
    diagramService.getDiagramSummary.mockResolvedValueOnce({
      template: 'system_overview', availability: 'UNAVAILABLE', reason: 'diagram_store_unavailable', reference: null,
    });
    const create = vi.fn(() => 'blob:local-diagram');
    const revoke = vi.fn();
    const originalCreate = Object.getOwnPropertyDescriptor(URL, 'createObjectURL');
    const originalRevoke = Object.getOwnPropertyDescriptor(URL, 'revokeObjectURL');
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: create });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revoke });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    try {
      render(<DiagramPanel versionId={versionId} projectId={projectId} />);
      fireEvent.click(await screen.findByRole('button', { name: 'Download JSON' }));
      expect(create).toHaveBeenCalledWith(expect.any(Blob));
      expect(click).toHaveBeenCalled();
    } finally {
      click.mockRestore();
      if (originalCreate) Object.defineProperty(URL, 'createObjectURL', originalCreate); else delete URL.createObjectURL;
      if (originalRevoke) Object.defineProperty(URL, 'revokeObjectURL', originalRevoke); else delete URL.revokeObjectURL;
    }
  });
});
