import React from 'react';
import { render, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { GraphCanvas } from '../../src/components/graph/GraphCanvas.jsx';

const camera = vi.hoisted(() => ({ setCenter: vi.fn(), setViewport: vi.fn(), fitView: vi.fn() }));
vi.mock('@xyflow/react', async () => {
  const React = await import('react');
  return {
    ReactFlowProvider: ({ children }) => children,
    ReactFlow: ({ children, onInit }) => {
      React.useEffect(() => { onInit?.(); }, [onInit]);
      return <div>{children}</div>;
    },
    Background: () => null, Controls: () => null, MiniMap: () => null, Handle: () => null,
    Position: { Top: 'top', Bottom: 'bottom' }, MarkerType: { ArrowClosed: 'arrowclosed' },
    useReactFlow: () => camera,
  };
});

afterEach(() => { cleanup(); vi.clearAllMocks(); });

const nodes = { target: { architecture_entity_id: 'target', name: 'Target', canonical_kind: 'service' } };
const positions = { target: { x: 1000, y: 2000, width: 220, height: 80 } };

describe('explicit list-to-map camera navigation', () => {
  it('centers the exact node at readable zoom without a competing initial fit or old fit trigger', async () => {
    const { rerender } = render(<GraphCanvas nodes={nodes} edges={{}} positions={positions}
      focusRequest={{ nodeId: 'target', sequence: 1 }} fitViewTrigger={5} />);
    await waitFor(() => expect(camera.setCenter).toHaveBeenCalledWith(1110, 2040, { zoom: 1, duration: 250 }));
    expect(camera.setViewport).not.toHaveBeenCalled();
    expect(camera.fitView).not.toHaveBeenCalled();
    rerender(<GraphCanvas nodes={nodes} edges={{}} positions={positions}
      focusRequest={{ nodeId: 'target', sequence: 1 }} fitViewTrigger={6} />);
    expect(camera.fitView).toHaveBeenCalledTimes(1);
  });

  it('waits for query and layout completion, and never recenters on ordinary selection or later relayout', async () => {
    const request = { nodeId: 'target', sequence: 1, pending: true };
    const { rerender } = render(<GraphCanvas nodes={nodes} edges={{}} positions={{}} focusRequest={request} />);
    expect(camera.setCenter).not.toHaveBeenCalled();
    rerender(<GraphCanvas nodes={nodes} edges={{}} positions={positions} focusRequest={request} isLayoutRunning />);
    expect(camera.setCenter).not.toHaveBeenCalled();
    const finished = { ...request, pending: false };
    // A query can settle before the layout effect sets isLayoutRunning. Old
    // positions must not consume the navigation request during that render.
    rerender(<GraphCanvas nodes={nodes} edges={{}} positions={positions} focusRequest={finished} layoutReady={false} />);
    expect(camera.setCenter).not.toHaveBeenCalled();
    rerender(<GraphCanvas nodes={nodes} edges={{}} positions={positions} focusRequest={finished} />);
    await waitFor(() => expect(camera.setCenter).toHaveBeenCalledTimes(1));
    rerender(<GraphCanvas nodes={nodes} edges={{}} positions={{ target: { ...positions.target, y: 4000 } }}
      selectedNodeId="another-node" focusRequest={finished} />);
    expect(camera.setCenter).toHaveBeenCalledTimes(1);
    rerender(<GraphCanvas nodes={nodes} edges={{}} positions={positions}
      focusRequest={{ nodeId: 'target', sequence: 2 }} />);
    await waitFor(() => expect(camera.setCenter).toHaveBeenCalledTimes(2));
  });
});
