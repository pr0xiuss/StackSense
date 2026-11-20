import React from 'react';
import { webcrypto } from 'node:crypto';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeAll } from 'vitest';
import { DiagramView } from '../../src/components/diagrams/DiagramView.jsx';
import { diagramFixture } from '../diagramFixtures.js';
beforeAll(() => vi.stubGlobal('crypto', webcrypto));
const camera = vi.hoisted(() => ({ fitView: vi.fn(), setCenter: vi.fn() }));
vi.mock('@xyflow/react', async () => {
  const React = await import('react');
  return {
    ReactFlowProvider: ({ children }) => children,
    ReactFlow: ({ nodes, nodeTypes, onInit, children }) => {
      React.useEffect(() => { onInit?.(); }, []);
      return <div>{nodes.filter(n => !n.hidden).map(n => React.createElement(nodeTypes[n.type], { key: n.id, data: n.data, selected: n.selected }))}{children}</div>;
    }, Controls: () => null, Handle: () => null, Position: { Top: 'top', Bottom: 'bottom' }, useReactFlow: () => camera,
  };
});
describe('injected-data diagram presentation', () => {
  it('keeps actions above bounded evidence and focuses the exact node without refit on selection', async () => {
    const prepared = diagramFixture(), requestMembers = vi.fn(async () => ({ generation_id: prepared.descriptor.reference.generation_id, semantic_digest: prepared.spec.semantic_digest, group_id: null, items: [], total: 0, next_cursor: null }));
    const onSelect = vi.fn(), onExport = vi.fn();
    const props = { prepared, requestMembers, requestView: vi.fn(), onSelect, onExport, onError: vi.fn() };
    render(<DiagramView {...props} />);
    await screen.findByRole('tab', { name: 'Diagram map' });
    // Wait for the mocked onInit effect and initial fit before measuring
    // additional camera calls. Late-init selection is covered separately.
    await waitFor(() => expect(camera.fitView).toHaveBeenCalled());
    const node = prepared.spec.nodes[0];
    const before = camera.fitView.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: `${node.kind}: ${node.name}; ${node.status}` }));
    expect(onSelect).toHaveBeenCalledWith(node.entity);
    expect(requestMembers).not.toHaveBeenCalled();
    expect(camera.fitView.mock.calls.length).toBe(before);
    fireEvent.click(screen.getByRole('button', { name: 'Focus on map' }));
    const box = prepared.layout.nodes.find(n => n.id === node.id).box;
    await waitFor(() => expect(camera.setCenter).toHaveBeenCalledWith((box.x + box.width / 2) / 1000, (box.y + box.height / 2) / 1000, expect.objectContaining({ zoom: 1 })));
    fireEvent.click(screen.getByRole('button', { name: /Load evidence/ }));
    await waitFor(() => expect(requestMembers).toHaveBeenCalledTimes(1));
    expect(requestMembers.mock.calls[0][0].limit).toBe(20);
    expect(await screen.findByText('No attached evidence.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Export SVG' }));
    expect(onExport).toHaveBeenCalledWith('svg');
    const retainedCanvas = screen.getByLabelText('Architecture diagram');
    const fitsBeforeTab = camera.fitView.mock.calls.length;
    fireEvent.click(screen.getByRole('tab', { name: 'Structured list' }));
    expect(screen.queryByRole('complementary', { name: 'Selected element' })).not.toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Diagram list pagination' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'View on map' }).length).toBeGreaterThan(0);
    fireEvent.click(screen.getAllByRole('button', { name: 'View on map' })[0]);
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Diagram map' })).toHaveAttribute('aria-selected', 'true'));
    expect(screen.getByLabelText('Architecture diagram')).toBe(retainedCanvas);
    expect(camera.fitView.mock.calls.length).toBe(fitsBeforeTab);
  });
  it('rejects corrupt props without mounting an unverified scene', async () => {
    const prepared = diagramFixture(); prepared.spec.nodes[0].name = 'corrupted';
    render(<DiagramView prepared={prepared} requestMembers={vi.fn()} requestView={vi.fn()} onError={vi.fn()} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be validated');
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
  });
});
