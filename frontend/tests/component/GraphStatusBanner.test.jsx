import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { GraphStatusBanner } from '../../src/components/graph/GraphStatusBanner.jsx';

describe('GraphStatusBanner component tests', () => {
  it('renders Ready badge for COMPLETED status with active generation', () => {
    render(
      <GraphStatusBanner
        status={{
          status: 'COMPLETED',
          active_generation_id: 'a0000000-0000-0000-0000-000000000001',
        }}
      />
    );

    expect(screen.getByText(/Ready \(a0000000\)/)).toBeInTheDocument();
  });

  it('renders Historical badge for STALE status', () => {
    render(
      <GraphStatusBanner
        status={{
          status: 'STALE',
          active_generation_id: 'b0000000-0000-0000-0000-000000000002',
        }}
      />
    );

    expect(screen.getByText(/Historical \(b0000000\)/)).toBeInTheDocument();
  });

  it('renders active attempt progress with role="status"', () => {
    render(
      <GraphStatusBanner
        status={{
          status: 'RUNNING',
          active_attempt: {
            attempt_number: 2,
            status: 'RUNNING',
          },
        }}
      />
    );

    expect(screen.getByText(/Graph rebuild attempt #2 is/)).toBeInTheDocument();
    expect(screen.getByText('RUNNING')).toBeInTheDocument();
  });

  it('renders alert and Retry button on error', () => {
    const onRetry = vi.fn();
    render(<GraphStatusBanner error="Failed to fetch graph data" onRetry={onRetry} />);

    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Failed to fetch graph data');

    const retryBtn = screen.getByRole('button', { name: 'Retry' });
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('renders out-of-date banner with Reload button when generation changed', () => {
    const onReload = vi.fn();
    render(
      <GraphStatusBanner
        isOutOfDate={true}
        generationChangeMessage="New generation available"
        onReload={onReload}
      />
    );

    expect(screen.getByText('New generation available')).toBeInTheDocument();
    const reloadBtn = screen.getByRole('button', { name: 'Reload this version' });
    fireEvent.click(reloadBtn);
    expect(onReload).toHaveBeenCalledTimes(1);
  });

  it('renders capacity limit notice when isCapReached is true', () => {
    render(
      <GraphStatusBanner
        isCapReached={true}
        capMessage="Canvas cap reached (300 nodes / 600 edges)"
      />
    );

    expect(screen.getByText('Canvas cap reached (300 nodes / 600 edges)')).toBeInTheDocument();
  });

  it('renders Rebuild Graph button when canManage is true', () => {
    const onRebuild = vi.fn();
    render(
      <GraphStatusBanner
        status={{ status: 'FAILED' }}
        canManage={true}
        onRebuild={onRebuild}
      />
    );

    const rebuildBtn = screen.getByRole('button', { name: 'Rebuild Graph' });
    fireEvent.click(rebuildBtn);
    expect(onRebuild).toHaveBeenCalledTimes(1);
  });

  it('does not render Rebuild button when canManage is false', () => {
    render(<GraphStatusBanner status={{ status: 'FAILED' }} canManage={false} />);
    expect(screen.queryByRole('button', { name: 'Rebuild Graph' })).not.toBeInTheDocument();
  });
});

