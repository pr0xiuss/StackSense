import React from 'react';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { GraphCanvas } from '../../src/components/graph/GraphCanvas.jsx';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('GraphCanvas component', () => {
  const entityId1 = '11111111-1111-1111-1111-111111111111';
  const entityId2 = '22222222-2222-2222-2222-222222222222';
  const relId1 = '33333333-3333-3333-3333-333333333333';

  const mockNodes = {
    [entityId1]: {
      architecture_entity_id: entityId1,
      logical_id: 'svc-auth-gw',
      name: 'AuthGatewayService',
      canonical_kind: 'service',
      namespace: 'backend.auth',
      fact_status: 'CONFIRMED',
      evidence_logical_ids: ['ev-01', 'ev-02'],
    },
    [entityId2]: {
      architecture_entity_id: entityId2,
      logical_id: 'db-users',
      name: 'UserDatabase',
      canonical_kind: 'database',
      namespace: 'storage.sql',
      fact_status: 'INFERRED',
      evidence_logical_ids: [],
    },
  };

  const mockEdges = {
    [relId1]: {
      architecture_relationship_id: relId1,
      logical_id: 'rel-auth-db',
      canonical_kind: 'calls',
      source_entity_id: entityId1,
      target_entity_id: entityId2,
      evidence_logical_ids: ['ev-rel-01'],
    },
  };

  const mockPositions = {
    [entityId1]: { x: 50, y: 50, width: 220, height: 80 },
    [entityId2]: { x: 50, y: 200, width: 220, height: 80 },
  };

  it('renders empty placeholder when no nodes are loaded', () => {
    render(
      <GraphCanvas
        nodes={{}}
        edges={{}}
        positions={{}}
        selectedNodeId={null}
      />
    );

    expect(screen.getByText('No entities in this window')).toBeInTheDocument();
    expect(screen.queryByText(/Projection is ready/i)).not.toBeInTheDocument();
  });

  it('renders custom ArchitectureNode cards with canonical metadata', () => {
    render(
      <GraphCanvas
        nodes={mockNodes}
        edges={mockEdges}
        positions={mockPositions}
        selectedNodeId={null}
      />
    );

    expect(screen.getByText('AuthGatewayService')).toBeInTheDocument();
    expect(screen.getByText('service')).toBeInTheDocument();
    expect(screen.getByText('backend.auth')).toBeInTheDocument();
    expect(screen.getByText('CONFIRMED')).toBeInTheDocument();
    expect(screen.getByText('ev:2')).toBeInTheDocument();

    expect(screen.getByText('UserDatabase')).toBeInTheDocument();
    expect(screen.getByText('database')).toBeInTheDocument();
    expect(screen.getByText('INFERRED')).toBeInTheDocument();
  });

  it('highlights the selected node card', () => {
    render(
      <GraphCanvas
        nodes={mockNodes}
        edges={mockEdges}
        positions={mockPositions}
        selectedNodeId={entityId1}
      />
    );

    const selectedNodeElement = screen.getByTestId(`arch-node-${entityId1}`);
    expect(selectedNodeElement).toHaveClass('selected');

    const otherNodeElement = screen.getByTestId(`arch-node-${entityId2}`);
    expect(otherNodeElement).not.toHaveClass('selected');
  });

  it('triggers onSelectNode when a node card is clicked', () => {
    const onSelectNode = vi.fn();

    render(
      <GraphCanvas
        nodes={mockNodes}
        edges={mockEdges}
        positions={mockPositions}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
      />
    );

    const node1 = screen.getByTestId(`arch-node-${entityId1}`);
    fireEvent.click(node1);

    expect(onSelectNode).toHaveBeenCalledWith(entityId1);
  });

  it('displays layout computation badge and layout error banner', () => {
    render(
      <GraphCanvas
        nodes={mockNodes}
        edges={mockEdges}
        positions={mockPositions}
        selectedNodeId={null}
        isLayoutRunning={true}
        layoutError="Layout watchdog timed out"
      />
    );

    expect(screen.getByText(/Computing layout.../i)).toBeInTheDocument();
    expect(screen.getByText(/Layout watchdog timed out/i)).toBeInTheDocument();
  });
});

