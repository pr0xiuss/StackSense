import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useIntelligenceDelivery } from '../../src/hooks/useIntelligenceDelivery.js';
import { deliveryService } from '../../src/services/deliveryService.js';

vi.mock('../../src/services/deliveryService.js', () => ({
  deliveryService: {
    getDelivery: vi.fn(),
    retryDelivery: vi.fn(),
  },
}));

describe('useIntelligenceDelivery Hook', () => {
  const versionId = '44444444-4444-4444-8444-444444444444';
  const projectId = '11111111-1111-4111-8111-111111111111';

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('polls delivery status on non-overlapping intervals while in progress', async () => {
    const inProgressSummary = {
      state: 'IN_PROGRESS',
      completed_work_items: 2,
      total_work_items: 6,
      work_summary: [
        { work_id: 'w1', kind: 'CONTAINER_ISOLATION', status: 'SUCCEEDED' },
        { work_id: 'w2', kind: 'COMPONENT_COMMUNICATION', status: 'IN_PROGRESS' },
      ],
    };

    deliveryService.getDelivery.mockResolvedValue(inProgressSummary);

    const { result } = renderHook(() =>
      useIntelligenceDelivery(versionId, {
        projectId,
        pollIntervalMs: 1000,
      })
    );

    // Initial fetch
    await act(async () => {
      await Promise.resolve();
    });

    expect(deliveryService.getDelivery).toHaveBeenCalledTimes(1);
    expect(result.current.delivery).toEqual(inProgressSummary);
    expect(result.current.isTerminal).toBe(false);

    // Advance timer to trigger next poll
    await act(async () => {
      vi.advanceTimersByTime(1000);
      await Promise.resolve();
    });

    expect(deliveryService.getDelivery).toHaveBeenCalledTimes(2);
  });

  it('stops polling when terminal state is reached', async () => {
    const terminalSummary = {
      state: 'SUCCEEDED',
      completed_work_items: 6,
      total_work_items: 6,
      receipt_digest: 'abc123digest',
      work_summary: [
        { work_id: 'w1', kind: 'CONTAINER_ISOLATION', status: 'SUCCEEDED' },
        { work_id: 'w2', kind: 'COMPONENT_COMMUNICATION', status: 'SUCCEEDED' },
      ],
    };

    deliveryService.getDelivery.mockResolvedValue(terminalSummary);

    const { result } = renderHook(() =>
      useIntelligenceDelivery(versionId, {
        projectId,
        pollIntervalMs: 1000,
      })
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(deliveryService.getDelivery).toHaveBeenCalledTimes(1);
    expect(result.current.isTerminal).toBe(true);

    // Advance timer: should NOT poll again
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(deliveryService.getDelivery).toHaveBeenCalledTimes(1);
  });

  it('pauses polling when tab is hidden and resumes when visible', async () => {
    const inProgressSummary = {
      state: 'IN_PROGRESS',
      completed_work_items: 1,
      total_work_items: 6,
      work_summary: [],
    };

    deliveryService.getDelivery.mockResolvedValue(inProgressSummary);

    const { result } = renderHook(() =>
      useIntelligenceDelivery(versionId, {
        projectId,
        pollIntervalMs: 1000,
      })
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(deliveryService.getDelivery).toHaveBeenCalledTimes(1);

    // Simulate tab hidden
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    // Advance timers: should NOT poll while hidden
    await act(async () => {
      vi.advanceTimersByTime(3000);
      await Promise.resolve();
    });

    expect(deliveryService.getDelivery).toHaveBeenCalledTimes(1);

    // Simulate tab visible again
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
      await Promise.resolve();
    });

    expect(deliveryService.getDelivery).toHaveBeenCalledTimes(2);
  });

  it('triggers manual idempotent retry and immediately refreshes status', async () => {
    const failedSummary = {
      state: 'FAILED',
      completed_work_items: 3,
      total_work_items: 6,
      work_summary: [
        { work_id: 'w-failed', kind: 'CROSS_BOUNDARY', status: 'FAILED', error_message: 'Timeout' },
      ],
    };

    const retriedSummary = {
      state: 'IN_PROGRESS',
      completed_work_items: 3,
      total_work_items: 6,
      work_summary: [
        { work_id: 'w-failed', kind: 'CROSS_BOUNDARY', status: 'PENDING' },
      ],
    };

    deliveryService.getDelivery
      .mockResolvedValueOnce(failedSummary)
      .mockResolvedValueOnce(retriedSummary);

    deliveryService.retryDelivery.mockResolvedValue({
      accepted: true,
      work_id: 'w-failed',
    });

    const { result } = renderHook(() =>
      useIntelligenceDelivery(versionId, {
        projectId,
        pollIntervalMs: 1000,
      })
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.delivery).toEqual(failedSummary);

    // Trigger retry
    await act(async () => {
      await result.current.retryWorkItem('w-failed');
    });

    expect(deliveryService.retryDelivery).toHaveBeenCalledWith(
      versionId,
      expect.objectContaining({
        work_id: 'w-failed',
        idempotency_key: expect.any(String),
      }),
      { projectId }
    );

    expect(result.current.delivery).toEqual(retriedSummary);
  });
});
