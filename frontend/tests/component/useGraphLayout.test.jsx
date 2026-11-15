import React from 'react';
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useGraphLayout } from '../../src/hooks/useGraphLayout.js';

describe('useGraphLayout hook', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('returns empty positions when no nodes are provided', () => {
    const { result } = renderHook(() =>
      useGraphLayout({
        nodes: {},
        edges: {},
        graphRevision: 0,
      })
    );

    expect(result.current.positions).toEqual({});
    expect(result.current.isLayoutRunning).toBe(false);
    expect(result.current.layoutError).toBeNull();
  });

  it('assigns deterministic grid fallback in non-worker environment', () => {
    const origWorker = globalThis.Worker;
    delete globalThis.Worker;

    try {
      const nodes = {
        'n-1': { architecture_entity_id: 'n-1' },
        'n-2': { architecture_entity_id: 'n-2' },
      };

      const { result } = renderHook(() =>
        useGraphLayout({
          nodes,
          edges: {},
          graphRevision: 1,
        })
      );

      expect(result.current.positions['n-1']).toEqual({
        x: 0,
        y: 0,
        width: 220,
        height: 80,
      });
      expect(result.current.positions['n-2']).toEqual({
        x: 260,
        y: 0,
        width: 220,
        height: 80,
      });
      expect(result.current.isLayoutRunning).toBe(false);
      expect(result.current.layoutRevision).toBe(1);
    } finally {
      globalThis.Worker = origWorker;
    }
  });

  it('manages worker lifecycle and receives layout positions', async () => {
    let workerInstance = null;

    class MockWorker {
      constructor() {
        this.onmessage = null;
        this.onerror = null;
        workerInstance = this;
      }
      postMessage(msg) {
        // Echo layout success
        setTimeout(() => {
          if (this.onmessage) {
            this.onmessage({
              data: {
                type: 'layout-success',
                requestId: msg.requestId,
                positions: {
                  'node-1': { x: 100, y: 150, width: 220, height: 80 },
                },
              },
            });
          }
        }, 50);
      }
      terminate() {}
    }

    const origWorker = globalThis.Worker;
    globalThis.Worker = MockWorker;

    try {
      const { result } = renderHook(() =>
        useGraphLayout({
          nodes: { 'node-1': { architecture_entity_id: 'node-1' } },
          edges: {},
          graphRevision: 1,
        })
      );

      expect(result.current.isLayoutRunning).toBe(true);

      act(() => {
        vi.advanceTimersByTime(100);
      });

      expect(result.current.isLayoutRunning).toBe(false);
      expect(result.current.positions['node-1']).toEqual({
        x: 100,
        y: 150,
        width: 220,
        height: 80,
      });
      expect(result.current.layoutError).toBeNull();
    } finally {
      globalThis.Worker = origWorker;
    }
  });
});

