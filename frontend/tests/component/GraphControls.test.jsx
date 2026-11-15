import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { GraphControls, EXPLORER_MODES } from '../../src/components/graph/GraphControls.jsx';

describe('GraphControls component tests', () => {
  const mockNode1 = { architecture_entity_id: 'n1', name: 'AuthService' };
  const mockNode2 = { architecture_entity_id: 'n2', name: 'DatabaseService' };
  const loadedNodes = [mockNode1, mockNode2];

  it('renders mode selector and triggers onModeChange', () => {
    const onModeChange = vi.fn();
    render(
      <GraphControls
        mode={EXPLORER_MODES.WINDOW}
        onModeChange={onModeChange}
      />
    );

    const modeSelect = screen.getByLabelText('Mode:');
    expect(modeSelect).toHaveValue(EXPLORER_MODES.WINDOW);

    fireEvent.change(modeSelect, { target: { value: EXPLORER_MODES.NEIGHBORHOOD } });
    expect(onModeChange).toHaveBeenCalledWith(EXPLORER_MODES.NEIGHBORHOOD);
  });

  it('renders anchor indicator and depth for Neighborhood mode', () => {
    render(
      <GraphControls
        mode={EXPLORER_MODES.NEIGHBORHOOD}
        selectedNode={mockNode1}
      />
    );

    expect(screen.getByText('AuthService')).toBeInTheDocument();
    expect(screen.getByLabelText('Depth:')).toBeInTheDocument();
    expect(screen.getByLabelText('Direction:')).toBeInTheDocument();
  });

  it('executes Neighborhood query with direction and depth', () => {
    const onExecute = vi.fn();
    render(
      <GraphControls
        mode={EXPLORER_MODES.NEIGHBORHOOD}
        selectedNode={mockNode1}
        onExecuteQuery={onExecute}
      />
    );

    const execBtn = screen.getByRole('button', { name: 'Execute' });
    fireEvent.click(execBtn);

    expect(onExecute).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: EXPLORER_MODES.NEIGHBORHOOD,
        entityId: 'n1',
        direction: 'both',
        depth: 1,
      })
    );
  });

  it('renders containment directions and executes Containment query without relationship kinds', () => {
    const onExecute = vi.fn();
    render(
      <GraphControls
        mode={EXPLORER_MODES.CONTAINMENT}
        selectedNode={mockNode1}
        onExecuteQuery={onExecute}
      />
    );

    const dirSelect = screen.getByLabelText('Direction:');
    expect(dirSelect).toHaveValue('children');

    fireEvent.change(dirSelect, { target: { value: 'parents' } });

    const execBtn = screen.getByRole('button', { name: 'Execute' });
    fireEvent.click(execBtn);

    expect(onExecute).toHaveBeenCalledWith({
      mode: EXPLORER_MODES.CONTAINMENT,
      entityId: 'n1',
      direction: 'parents',
      depth: 1,
    });
  });

  it('renders path source and target selectors and executes Paths query', () => {
    const onExecute = vi.fn();
    render(
      <GraphControls
        mode={EXPLORER_MODES.PATHS}
        loadedNodes={loadedNodes}
        onExecuteQuery={onExecute}
      />
    );

    const sourceSelect = screen.getByLabelText('Source:');
    const targetSelect = screen.getByLabelText('Target:');

    fireEvent.change(sourceSelect, { target: { value: 'n1' } });
    fireEvent.change(targetSelect, { target: { value: 'n2' } });

    const execBtn = screen.getByRole('button', { name: 'Execute' });
    fireEvent.click(execBtn);

    expect(onExecute).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: EXPLORER_MODES.PATHS,
        sourceEntityId: 'n1',
        targetEntityId: 'n2',
        maxDepth: 1,
      })
    );
  });

  it('renders Load more button when cursor exists and triggers onLoadMore', () => {
    const onLoadMore = vi.fn();
    render(
      <GraphControls
        mode={EXPLORER_MODES.WINDOW}
        activeOperation={{ inFlight: false, cursor: 'next_page_token' }}
        onLoadMore={onLoadMore}
      />
    );

    const loadMoreBtn = screen.getByRole('button', { name: 'Load more' });
    expect(loadMoreBtn).toBeInTheDocument();

    fireEvent.click(loadMoreBtn);
    expect(onLoadMore).toHaveBeenCalledTimes(1);
  });

  it('triggers onFit and onClear callbacks', () => {
    const onFit = vi.fn();
    const onClear = vi.fn();
    render(<GraphControls onFit={onFit} onClear={onClear} />);

    fireEvent.click(screen.getByRole('button', { name: 'Fit View' }));
    expect(onFit).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});

