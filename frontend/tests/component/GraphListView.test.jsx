import React from 'react';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { GraphListView } from '../../src/components/graph/GraphListView.jsx';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('GraphListView component', () => {
  const entityId1 = '11111111-1111-1111-1111-111111111111';
  const entityId2 = '22222222-2222-2222-2222-222222222222';
  const relId1 = '33333333-3333-3333-3333-333333333333';

  const mockNodes = {
    [entityId1]: {
      architecture_entity_id: entityId1,
      logical_id: 'svc-inventory',
      name: 'InventoryService',
      canonical_kind: 'service',
      namespace: 'domain.warehouse',
      fact_status: 'CONFIRMED',
      evidence_logical_ids: ['ev-01'],
    },
    [entityId2]: {
      architecture_entity_id: entityId2,
      logical_id: 'db-inventory',
      name: 'InventoryDb',
      canonical_kind: 'database',
      namespace: 'infra.db',
      fact_status: 'CONFIRMED',
      evidence_logical_ids: [],
    },
  };

  const mockEdges = {
    [relId1]: {
      architecture_relationship_id: relId1,
      logical_id: 'rel-inv-db',
      canonical_kind: 'connects_to',
      source_entity_id: entityId1,
      target_entity_id: entityId2,
    },
  };

  it('renders loaded entities table by default', () => {
    render(<GraphListView nodes={mockNodes} edges={mockEdges} />);

    expect(screen.getByRole('table', { name: 'Loaded Architecture Entities Table' })).toBeInTheDocument();
    expect(screen.getByText('InventoryService')).toBeInTheDocument();
    expect(screen.getByText('InventoryDb')).toBeInTheDocument();
    expect(screen.getByText('svc-inventory')).toBeInTheDocument();
  });

  it('filters entities by search query', () => {
    render(<GraphListView nodes={mockNodes} edges={mockEdges} />);

    const filterInput = screen.getByLabelText(/filter loaded entities/i);
    fireEvent.change(filterInput, { target: { value: 'InventoryDb' } });

    expect(screen.getByText('InventoryDb')).toBeInTheDocument();
    expect(screen.queryByText('InventoryService')).not.toBeInTheDocument();
  });

  it('toggles to relationships table and displays edges', () => {
    render(<GraphListView nodes={mockNodes} edges={mockEdges} />);

    const relTabBtn = screen.getByRole('button', { name: /relationships/i });
    fireEvent.click(relTabBtn);

    expect(screen.getByRole('table', { name: 'Loaded Architecture Relationships Table' })).toBeInTheDocument();
    expect(screen.getByText('connects_to')).toBeInTheDocument();
    expect(screen.getByText('InventoryService')).toBeInTheDocument();
    expect(screen.getByText('InventoryDb')).toBeInTheDocument();
    expect(screen.getByText('rel-inv-db')).toBeInTheDocument();
  });

  it('triggers onSelectNode and onExpandNeighborhood callbacks', () => {
    const onSelectNode = vi.fn();
    const onExpandNeighborhood = vi.fn();

    render(
      <GraphListView
        nodes={mockNodes}
        edges={mockEdges}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
        onExpandNeighborhood={onExpandNeighborhood}
      />
    );

    const selectBtn = screen.getByRole('button', { name: 'Select InventoryService' });
    fireEvent.click(selectBtn);
    expect(onSelectNode).toHaveBeenCalledWith(entityId1);

    const neighborBtn = screen.getByRole('button', { name: 'Expand neighborhood of InventoryService' });
    fireEvent.click(neighborBtn);
    expect(onExpandNeighborhood).toHaveBeenCalledWith(entityId1);
  });

  it('displays layout error notification banner if layout failed', () => {
    render(
      <GraphListView
        nodes={mockNodes}
        edges={mockEdges}
        layoutError="ELK Worker timeout"
      />
    );

    expect(screen.getByText(/ELK Worker timeout/i)).toBeInTheDocument();
  });
});

