import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { analysisService } from '../../src/services/analysisService.js';
import { useAnalysisLiveStatus } from '../../src/hooks/useAnalysisLiveStatus.js';
import { isTerminalStatus } from '../../src/contracts/analysisContracts.js';

vi.mock('../../src/services/analysisService.js', () => ({
  analysisService: {
    getAnalysis: vi.fn(),
    subscribeToEvents: vi.fn(),
  },
}));

describe('useAnalysisLiveStatus', () => {
  let streamCallbacks;
  let abortStream;

  beforeEach(() => {
    streamCallbacks = null;
    abortStream = vi.fn();
    analysisService.getAnalysis.mockReset();
    analysisService.subscribeToEvents.mockReset();
    analysisService.subscribeToEvents.mockImplementation((_analysisId, callbacks) => {
      streamCallbacks = callbacks;
      return { abort: abortStream };
    });
  });

  it('keeps polling through the transitional timeout state until failed', () => {
    expect(isTerminalStatus('timeout')).toBe(false);
    expect(isTerminalStatus('failed')).toBe(true);
  });

  it('keeps one SSE subscription when an event refreshes analysis state', async () => {
    analysisService.getAnalysis.mockResolvedValue({
      id: 'analysis-1',
      status: 'running',
    });

    const { result, unmount } = renderHook(() =>
      useAnalysisLiveStatus('project-1', 'analysis-1')
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(analysisService.getAnalysis).toHaveBeenCalledTimes(1);
    expect(analysisService.subscribeToEvents).toHaveBeenCalledTimes(1);

    await act(async () => {
      streamCallbacks.onMessage({ event: 'analysis.progressed' });
    });

    await waitFor(() => expect(analysisService.getAnalysis).toHaveBeenCalledTimes(2));
    expect(analysisService.subscribeToEvents).toHaveBeenCalledTimes(1);
    expect(abortStream).not.toHaveBeenCalled();

    unmount();
    expect(abortStream).toHaveBeenCalledTimes(1);
  });

  it('stops the stream immediately when a refresh reaches a terminal state', async () => {
    analysisService.getAnalysis
      .mockResolvedValueOnce({ id: 'analysis-1', status: 'running' })
      .mockResolvedValueOnce({ id: 'analysis-1', status: 'completed' });

    const { result } = renderHook(() =>
      useAnalysisLiveStatus('project-1', 'analysis-1')
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      streamCallbacks.onMessage({ event: 'analysis.completed' });
    });

    await waitFor(() => expect(result.current.isTerminal).toBe(true));
    expect(abortStream).toHaveBeenCalledTimes(1);
    expect(analysisService.subscribeToEvents).toHaveBeenCalledTimes(1);
  });
});
