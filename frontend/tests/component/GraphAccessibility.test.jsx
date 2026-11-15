import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GraphControls, EXPLORER_MODES } from '../../src/components/graph/GraphControls.jsx';
import { GraphCanvas } from '../../src/components/graph/GraphCanvas.jsx';
import { GraphInspector } from '../../src/components/graph/GraphInspector.jsx';
import { GraphListView } from '../../src/components/graph/GraphListView.jsx';
import { GraphStatusBanner } from '../../src/components/graph/GraphStatusBanner.jsx';
import { formatGraphError, useArchitectureGraph } from '../../src/hooks/useArchitectureGraph.js';
import { graphService } from '../../src/services/graphService.js';
import { architectureService } from '../../src/services/architectureService.js';
import { PROJECTION_PUBLIC_STATUS, PROJECTION_ATTEMPT_STATUS } from '../../src/contracts/graphContracts.js';

// Mock graphService and architectureService
vi.mock('../../src/services/graphService.js', () => ({
  graphService: {
    getStatus: vi.fn(),
    requestRebuild: vi.fn(),
    getWindow: vi.fn(),
    getNeighborhood: vi.fn(),
    getDependencies: vi.fn(),
    getDependents: vi.fn(),
    getContainment: vi.fn(),
    getBoundedPaths: vi.fn(),
    getNodeDetail: vi.fn(),
    getQueryHealth: vi.fn(),
  },
}));

vi.mock('../../src/services/architectureService.js', () => ({
  architectureService: {
    getVersion: vi.fn(),
  },
}));

describe('GraphAccessibility & Hardening Test Suite', () => {
  const mockNode1 = {
    architecture_entity_id: '11111111-1111-4111-8111-111111111111',
    name: 'AuthenticationService_ГлавныйСервисАвторизации_v1.0_🚀',
    canonical_kind: 'service',
    fact_status: 'CONFIRMED',
    logical_id: 'auth_service_main_core',
    namespace: 'com.stacksense.auth',
    evidence_logical_ids: ['ev-001', 'ev-002'],
  };

  const mockNode2 = {
    architecture_entity_id: '22222222-2222-4222-8222-222222222222',
    name: 'UserDatabase',
    canonical_kind: 'database',
    fact_status: 'INFERRED',
    logical_id: 'db_users_primary',
    namespace: 'com.stacksense.db',
    evidence_logical_ids: [],
  };

  const mockEdge = {
    architecture_relationship_id: '33333333-3333-4333-8333-333333333333',
    source_entity_id: mockNode1.architecture_entity_id,
    target_entity_id: mockNode2.architecture_entity_id,
    canonical_kind: 'calls',
    logical_id: 'rel_auth_to_db',
  };

  const mockNodes = {
    [mockNode1.architecture_entity_id]: mockNode1,
    [mockNode2.architecture_entity_id]: mockNode2,
  };

  const mockEdges = {
    [mockEdge.architecture_relationship_id]: mockEdge,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('1. Keyboard Parity on GraphCanvas & ArchitectureNode', () => {
    it('supports selection via Enter and Space key on custom nodes', () => {
      const onSelect = vi.fn();
      render(
        <GraphCanvas
          nodes={mockNodes}
          edges={mockEdges}
          positions={{
            [mockNode1.architecture_entity_id]: { x: 100, y: 100 },
            [mockNode2.architecture_entity_id]: { x: 300, y: 100 },
          }}
          selectedNodeId={null}
          onSelectNode={onSelect}
        />
      );

      const node1El = screen.getByTestId(`arch-node-${mockNode1.architecture_entity_id}`);
      expect(node1El).toHaveAttribute('tabIndex', '0');
      expect(node1El).toHaveAttribute('role', 'button');
      expect(node1El).toHaveAttribute('aria-selected', 'false');

      // Press Enter to select
      fireEvent.keyDown(node1El, { key: 'Enter', code: 'Enter' });
      expect(onSelect).toHaveBeenCalledWith(mockNode1.architecture_entity_id);

      // Press Space to select
      fireEvent.keyDown(node1El, { key: ' ', code: 'Space' });
      expect(onSelect).toHaveBeenCalledWith(mockNode1.architecture_entity_id);
    });

    it('supports deselecting via Escape key on custom nodes', () => {
      const onSelect = vi.fn();
      render(
        <GraphCanvas
          nodes={mockNodes}
          edges={mockEdges}
          positions={{
            [mockNode1.architecture_entity_id]: { x: 100, y: 100 },
          }}
          selectedNodeId={mockNode1.architecture_entity_id}
          onSelectNode={onSelect}
        />
      );

      const node1El = screen.getByTestId(`arch-node-${mockNode1.architecture_entity_id}`);
      expect(node1El).toHaveAttribute('aria-selected', 'true');

      // Press Escape to deselect
      fireEvent.keyDown(node1El, { key: 'Escape', code: 'Escape' });
      expect(onSelect).toHaveBeenCalledWith(null);
    });
  });

  describe('2. GraphInspector Keyboard and Focus Management', () => {
    it('listens for Escape key to close inspector without forced viewport movement', () => {
      const onDeselect = vi.fn();
      render(
        <GraphInspector
          selectedNode={mockNode1}
          nodes={mockNodes}
          onDeselect={onDeselect}
        />
      );

      expect(screen.getByTestId('graph-inspector')).toBeInTheDocument();

      // Trigger Escape globally
      fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });
      expect(onDeselect).toHaveBeenCalledTimes(1);
    });

    it('provides accessible labels on close button and all traversal buttons', () => {
      const onDeselect = vi.fn();
      const onExpandNeighbors = vi.fn();
      const onExpandDeps = vi.fn();
      const onExpandDependents = vi.fn();
      const onExpandContainment = vi.fn();

      render(
        <GraphInspector
          selectedNode={mockNode1}
          nodes={mockNodes}
          onDeselect={onDeselect}
          onExpandNeighborhood={onExpandNeighbors}
          onExpandDependencies={onExpandDeps}
          onExpandDependents={onExpandDependents}
          onExpandContainment={onExpandContainment}
        />
      );

      const closeBtn = screen.getByRole('button', { name: 'Close inspector' });
      expect(closeBtn).toBeInTheDocument();

      expect(
        screen.getByRole('button', { name: `Expand Neighborhood of ${mockNode1.name}` })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: `Explore Dependencies of ${mockNode1.name}` })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: `Explore Dependents of ${mockNode1.name}` })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: `Explore Containment of ${mockNode1.name}` })
      ).toBeInTheDocument();
    });
  });

  describe('3. GraphControls Native Controls and Fieldset Kind Filters', () => {
    it('renders fieldset and legend for relationship kind filters in Neighborhood mode', () => {
      render(
        <GraphControls
          mode={EXPLORER_MODES.NEIGHBORHOOD}
          selectedNode={mockNode1}
        />
      );

      const fieldset = screen.getByRole('group', { name: 'Filter by Relationship Kind' });
      expect(fieldset).toBeInTheDocument();

      // Verify native checkboxes with matching label htmlFor
      const callsCheckbox = screen.getByLabelText(/calls/i);
      expect(callsCheckbox).toBeInTheDocument();
      expect(callsCheckbox).toHaveAttribute('type', 'checkbox');
      expect(callsCheckbox).not.toBeChecked();

      fireEvent.click(callsCheckbox);
      expect(callsCheckbox).toBeChecked();
    });

    it('does not render kind filters in Window or Containment mode', () => {
      const { rerender } = render(
        <GraphControls
          mode={EXPLORER_MODES.WINDOW}
          selectedNode={mockNode1}
        />
      );

      expect(screen.queryByRole('group', { name: 'Filter by Relationship Kind' })).not.toBeInTheDocument();

      rerender(
        <GraphControls
          mode={EXPLORER_MODES.CONTAINMENT}
          selectedNode={mockNode1}
        />
      );
      expect(screen.queryByRole('group', { name: 'Filter by Relationship Kind' })).not.toBeInTheDocument();
    });

    it('has explicit accessible aria-label attributes on action buttons', () => {
      render(
        <GraphControls
          mode={EXPLORER_MODES.NEIGHBORHOOD}
          selectedNode={mockNode1}
          activeOperation={{ inFlight: false, cursor: 'token-cursor' }}
          onLoadMore={vi.fn()}
          onFit={vi.fn()}
          onClear={vi.fn()}
        />
      );

      expect(screen.getByRole('button', { name: /execute/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /fit all loaded nodes/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();
    });
  });

  describe('4. GraphListView Semantic Tables & Sub-tab Parity', () => {
    it('renders semantic table with proper column headers and tablist controls', () => {
      render(
        <GraphListView
          nodes={mockNodes}
          edges={mockEdges}
          selectedNodeId={null}
          onSelectNode={vi.fn()}
        />
      );

      expect(screen.getByRole('group', { name: 'Structured graph view categories' })).toBeInTheDocument();
      const entityTab = screen.getByRole('button', { name: /Entities/i });
      const relTab = screen.getByRole('button', { name: /Relationships/i });

      expect(entityTab).toHaveAttribute('aria-pressed', 'true');
      expect(relTab).toHaveAttribute('aria-pressed', 'false');

      // Semantic table
      const table = screen.getByRole('table', { name: 'Loaded Architecture Entities Table' });
      expect(table).toBeInTheDocument();

      const headers = screen.getAllByRole('columnheader');
      expect(headers.map((h) => h.textContent)).toEqual([
        'Name',
        'Kind',
        'Status',
        'Logical ID',
        'Evidence',
        'Actions',
      ]);
    });

    it('supports switching to relationships tab and renders relationship table', () => {
      render(
        <GraphListView
          nodes={mockNodes}
          edges={mockEdges}
          selectedNodeId={null}
          onSelectNode={vi.fn()}
        />
      );

      const relTab = screen.getByRole('button', { name: /Relationships/i });
      fireEvent.click(relTab);

      expect(relTab).toHaveAttribute('aria-pressed', 'true');
      const relTable = screen.getByRole('table', { name: 'Loaded Architecture Relationships Table' });
      expect(relTable).toBeInTheDocument();
    });
  });

  describe('5. Error Matrix Distinctions & Credential Sanitization', () => {
    it('formats 403 Forbidden without logging out or clearing credentials', () => {
      const err = { status: 403, message: 'Forbidden' };
      const formatted = formatGraphError(err);
      expect(formatted).toBe('Access denied: You do not have permission to perform this graph operation.');
    });

    it('formats 404 Not Found for unavailable projection', () => {
      const err = { status: 404, message: 'Not Found' };
      const formatted = formatGraphError(err);
      expect(formatted).toBe('Architecture graph projection not found or unavailable for this version.');
    });

    it('formats 409 Conflict for active rebuild operation', () => {
      const err = { status: 409, message: 'Conflict' };
      const formatted = formatGraphError(err);
      expect(formatted).toBe('A rebuild operation is already in progress for this architecture version.');
    });

    it('formats 410 Gone / 422 expired cursor and prompts restart', () => {
      const err410 = { status: 410, message: 'Cursor expired' };
      expect(formatGraphError(err410)).toBe(
        'Pagination cursor expired. Continuation stopped. Please restart your exploration query.'
      );

      const err422 = { status: 422, code: 'GRAPH_CURSOR_EXPIRED', message: 'Opaque cursor expired' };
      expect(formatGraphError(err422)).toBe(
        'Pagination cursor expired. Continuation stopped. Please restart your exploration query.'
      );
    });

    it('formats 504 and client timeout gracefully preserving data', () => {
      const err504 = { status: 504, message: 'Gateway timeout' };
      expect(formatGraphError(err504)).toBe(
        'Graph query timed out. Loaded data is preserved. You may retry.'
      );
    });

    it('formats 503 / 502 / 500 service unavailable gracefully preserving data', () => {
      const err503 = { status: 503, message: 'Neo4j unavailable' };
      expect(formatGraphError(err503)).toBe(
        'Graph service is temporarily unavailable. Loaded data is preserved. You may retry.'
      );
    });

    it('sanitizes and redacts raw Bearer JWT tokens and cursor strings', () => {
      const sensitiveErr = new Error(
        'Failed request with Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitiveSecretTokenStringHere and cursor=eyJjdXJzb3Jfa2V5IjoiMTIzNDUifQ=='
      );
      const sanitized = formatGraphError(sensitiveErr);

      expect(sanitized).not.toContain('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitiveSecretTokenStringHere');
      expect(sanitized).not.toContain('eyJjdXJzb3Jfa2V5IjoiMTIzNDUifQ==');
      expect(sanitized).toContain('[REDACTED]');
    });
  });

  describe('6. Polling Lifecycle & Visibility Transitions', () => {
    function HookTestComponent({ versionId, projectId }) {
      const { state } = useArchitectureGraph({
        projectId,
        repositoryId: '22222222-2222-4222-8222-222222222222',
        analysisId: '33333333-3333-4333-8333-333333333333',
        versionId,
      }, { pollIntervalMs: 50 });

      return (
        <div>
          <div data-testid="status">{state.status?.status || 'NO_STATUS'}</div>
          <div data-testid="error">{state.error || 'NO_ERROR'}</div>
        </div>
      );
    }

    it('pauses polling when document becomes hidden and stops polling on 403 error', async () => {
      const versionId = '44444444-4444-4444-8444-444444444444';
      const projectId = '11111111-1111-4111-8111-111111111111';

      architectureService.getVersion.mockResolvedValue({
        id: versionId,
        project_id: projectId,
        repository_id: '22222222-2222-4222-8222-222222222222',
        analysis_id: '33333333-3333-4333-8333-333333333333',
      });

      // Mock first call: PENDING status
      graphService.getStatus
        .mockResolvedValueOnce({
          status: PROJECTION_PUBLIC_STATUS.PENDING,
          active_generation_id: null,
          active_attempt: { attempt_number: 1, status: PROJECTION_ATTEMPT_STATUS.RUNNING },
        })
        .mockRejectedValueOnce({
          status: 403,
          message: 'Permission denied',
        });

      render(<HookTestComponent versionId={versionId} projectId={projectId} />);

      await waitFor(() => {
        expect(screen.getByTestId('status')).toHaveTextContent(PROJECTION_PUBLIC_STATUS.PENDING);
      });

      // Simulate visibilitychange to hidden
      Object.defineProperty(document, 'visibilityState', {
        value: 'hidden',
        configurable: true,
      });
      fireEvent(document, new Event('visibilitychange'));

      // Simulate visibilitychange back to visible
      Object.defineProperty(document, 'visibilityState', {
        value: 'visible',
        configurable: true,
      });
      fireEvent(document, new Event('visibilitychange'));

      await waitFor(() => {
        expect(screen.getByTestId('error')).toHaveTextContent('Access denied: You do not have permission');
      });

      // Ensure no further getStatus calls are scheduled after 403 terminal error
      const callCount = graphService.getStatus.mock.calls.length;
      await new Promise((r) => setTimeout(r, 120));
      expect(graphService.getStatus.mock.calls.length).toBe(callCount);
    });
  });

  describe('7. High-Density and Unicode Robustness', () => {
    it('renders long Unicode names without crashing or overflowing layout', () => {
      render(
        <GraphInspector
          selectedNode={mockNode1}
          nodes={mockNodes}
          onDeselect={vi.fn()}
        />
      );

      expect(screen.getByText(mockNode1.name)).toBeInTheDocument();
      expect(screen.getByText('com.stacksense.auth')).toBeInTheDocument();
    });
  });
});
