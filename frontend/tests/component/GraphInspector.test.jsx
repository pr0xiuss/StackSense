import React from 'react';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { GraphInspector } from '../../src/components/graph/GraphInspector.jsx';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('GraphInspector component', () => {
  const versionId = '44444444-4444-4444-4444-444444444444';
  const entityId = '11111111-1111-1111-1111-111111111111';
  const targetId = '22222222-2222-2222-2222-222222222222';
  const relId = '33333333-3333-3333-3333-333333333333';

  const mockVersion = {
    id: versionId,
    architecture_schema_version: '1.0.0',
    entity_count: 12,
    relationship_count: 8,
    evidence_count: 5,
    unresolved_relationship_count: 1,
    conflict_count: 0,
  };

  const mockSelectedNode = {
    architecture_entity_id: entityId,
    logical_id: 'svc-order',
    name: 'OrderService',
    canonical_kind: 'service',
    namespace: 'domain.orders',
    fact_status: 'CONFIRMED',
    evidence_logical_ids: ['ev-01', 'ev-02'],
  };

  const mockSelectedEdge = {
    architecture_relationship_id: relId,
    logical_id: 'rel-order-payment',
    canonical_kind: 'calls',
    source_entity_id: entityId,
    target_entity_id: targetId,
  };

  const mockNodes = {
    [entityId]: mockSelectedNode,
    [targetId]: {
      architecture_entity_id: targetId,
      name: 'PaymentGateway',
    },
  };

  it('renders Architecture Summary when neither node nor edge is selected', () => {
    render(<GraphInspector version={mockVersion} />);

    expect(screen.getByText('Architecture Summary')).toBeInTheDocument();
    expect(screen.getByText(versionId)).toBeInTheDocument();
    expect(screen.getByText('v1.0.0')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
  });

  it('renders selected node details with canonical metadata and evidence', () => {
    render(
      <GraphInspector
        selectedNode={mockSelectedNode}
        version={mockVersion}
        nodes={mockNodes}
      />
    );

    expect(screen.getByText('OrderService')).toBeInTheDocument();
    expect(screen.getByText('service')).toBeInTheDocument();
    expect(screen.getByText('domain.orders')).toBeInTheDocument();
    expect(screen.getByText('svc-order')).toBeInTheDocument();
    expect(screen.getByText(entityId)).toBeInTheDocument();
    expect(screen.getByText('CONFIRMED')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Attached Evidence \(2\)/ }));
    expect(screen.getByText('ev-01')).toBeInTheDocument();
    expect(screen.getByText('ev-02')).toBeInTheDocument();
  });

  it('triggers traversal callbacks from node inspector action buttons', () => {
    const onExpandNeighborhood = vi.fn();
    const onExpandDependencies = vi.fn();
    const onExpandDependents = vi.fn();
    const onExpandContainment = vi.fn();

    render(
      <GraphInspector
        selectedNode={mockSelectedNode}
        version={mockVersion}
        nodes={mockNodes}
        onExpandNeighborhood={onExpandNeighborhood}
        onExpandDependencies={onExpandDependencies}
        onExpandDependents={onExpandDependents}
        onExpandContainment={onExpandContainment}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /expand neighborhood/i }));
    expect(onExpandNeighborhood).toHaveBeenCalledWith(entityId);

    fireEvent.click(screen.getByRole('button', { name: /explore dependencies/i }));
    expect(onExpandDependencies).toHaveBeenCalledWith(entityId);

    fireEvent.click(screen.getByRole('button', { name: /explore dependents/i }));
    expect(onExpandDependents).toHaveBeenCalledWith(entityId);

    fireEvent.click(screen.getByRole('button', { name: /explore containment/i }));
    expect(onExpandContainment).toHaveBeenCalledWith(entityId);
  });

  it('triggers onDeselect when close button is clicked', () => {
    const onDeselect = vi.fn();

    render(
      <GraphInspector
        selectedNode={mockSelectedNode}
        version={mockVersion}
        nodes={mockNodes}
        onDeselect={onDeselect}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /close inspector/i }));
    expect(onDeselect).toHaveBeenCalledTimes(1);
  });

  it('renders selected edge details', () => {
    render(
      <GraphInspector
        selectedEdge={mockSelectedEdge}
        version={mockVersion}
        nodes={mockNodes}
      />
    );

    expect(screen.getByText('Relationship')).toBeInTheDocument();
    expect(screen.getByText('calls')).toBeInTheDocument();
    expect(screen.getByText('OrderService')).toBeInTheDocument();
    expect(screen.getByText('PaymentGateway')).toBeInTheDocument();
    expect(screen.getByText('rel-order-payment')).toBeInTheDocument();
  });

  it('keeps actions before bounded evidence and resets evidence on selection', () => {
    const node = { ...mockSelectedNode, evidence_logical_ids: Array.from({ length: 220 }, (_, i) => `reference-${i}`) };
    const { rerender } = render(<GraphInspector selectedNode={node} onExpandNeighborhood={vi.fn()} />);
    expect(screen.queryByText('reference-0')).not.toBeInTheDocument();
    const toggle = screen.getByRole('button', { name: /Attached Evidence \(220\)/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    const action = screen.getByRole('button', { name: /Expand Neighborhood of/ });
    expect(action.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.click(toggle);
    expect(screen.getAllByText('Evidence reference')).toHaveLength(5);
    expect(screen.queryByText('reference-5')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next evidence' }));
    expect(screen.queryByText('reference-0')).not.toBeInTheDocument();
    expect(screen.getByText('reference-5')).toBeInTheDocument();
    rerender(<GraphInspector selectedNode={{ ...mockSelectedNode, architecture_entity_id: targetId }} />);
    expect(screen.getByRole('button', { name: /Attached Evidence \(2\)/ })).toHaveAttribute('aria-expanded', 'false');
  });
});

