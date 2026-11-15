/**
 * Graph Layout Hook (Frontend)
 *
 * Manages the lifecycle of the ELK layout web worker, revision-based layout requests,
 * request watchdog timeout, cancellation, and stable node positioning.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { LAYOUT_WATCHDOG_TIMEOUT_MS, LAYOUT_PROTOCOL_VERSION } from '../contracts/graphContracts.js';

export function useGraphLayout({
  nodes = {},
  edges = {},
  graphRevision = 0,
  contextKey = '',
  generationId = '',
} = {}) {
  const [positions, setPositions] = useState({});
  const [isLayoutRunning, setIsLayoutRunning] = useState(false);
  const [layoutError, setLayoutError] = useState(null);

  const workerRef = useRef(null);
  const currentRequestIdRef = useRef(0);
  const watchdogTimerRef = useRef(null);

  // Initialize or terminate worker
  const initWorker = useCallback(() => {
    if (workerRef.current) {
      workerRef.current.terminate();
      workerRef.current = null;
    }

    if (typeof Worker === 'undefined') {
      return null;
    }

    try {
      const worker = new Worker(
        new URL('../workers/graphLayout.worker.js', import.meta.url),
        { type: 'module' }
      );

      worker.onmessage = (event) => {
        const msg = event.data;
        if (!msg) return;

        // Discard responses for older requests
        if (msg.requestId !== currentRequestIdRef.current) {
          return;
        }

        if (watchdogTimerRef.current) {
          clearTimeout(watchdogTimerRef.current);
          watchdogTimerRef.current = null;
        }

        setIsLayoutRunning(false);

        if (msg.type === 'layout-success') {
          setPositions(msg.positions || {});
          setLayoutError(null);
        } else if (msg.type === 'layout-error') {
          setLayoutError(msg.message || 'Layout computation failed');
        }
      };

      worker.onerror = (err) => {
        setIsLayoutRunning(false);
        setLayoutError(err.message || 'Worker thread error');
      };

      workerRef.current = worker;
      return worker;
    } catch (err) {
      setLayoutError('Failed to instantiate layout worker');
      return null;
    }
  }, []);

  // Request layout computation
  useEffect(() => {
    const nodeList = Object.values(nodes);
    if (nodeList.length === 0) {
      setPositions({});
      setIsLayoutRunning(false);
      setLayoutError(null);
      return;
    }

    let worker = workerRef.current;
    if (!worker) {
      worker = initWorker();
    }

    if (!worker) {
      // In non-worker environments (e.g. testing without worker polyfill), assign grid fallback
      const fallbackPositions = {};
      nodeList.forEach((n, idx) => {
        const col = idx % 5;
        const row = Math.floor(idx / 5);
        fallbackPositions[n.architecture_entity_id] = {
          x: col * 260,
          y: row * 140,
          width: 220,
          height: 80,
        };
      });
      setPositions(fallbackPositions);
      return;
    }

    const nextRequestId = currentRequestIdRef.current + 1;
    currentRequestIdRef.current = nextRequestId;

    setIsLayoutRunning(true);
    setLayoutError(null);

    // Arm 10-second watchdog
    if (watchdogTimerRef.current) {
      clearTimeout(watchdogTimerRef.current);
    }
    watchdogTimerRef.current = setTimeout(() => {
      if (currentRequestIdRef.current === nextRequestId) {
        setIsLayoutRunning(false);
        setLayoutError('Layout computation exceeded 10-second timeout. Worker terminated.');
        if (workerRef.current) {
          workerRef.current.terminate();
          workerRef.current = null;
        }
      }
    }, LAYOUT_WATCHDOG_TIMEOUT_MS);

    // Post layout message
    worker.postMessage({
      type: 'layout',
      protocolVersion: LAYOUT_PROTOCOL_VERSION,
      requestId: nextRequestId,
      contextKey,
      generationId,
      graphRevision,
      nodes: nodeList.map((n) => ({
        id: n.architecture_entity_id,
        width: 220,
        height: 80,
      })),
      edges: Object.values(edges).map((e) => ({
        id: e.architecture_relationship_id,
        source: e.source_entity_id,
        target: e.target_entity_id,
      })),
      options: {
        direction: 'DOWN',
      },
    });
  }, [graphRevision, contextKey, generationId, initWorker]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (watchdogTimerRef.current) {
        clearTimeout(watchdogTimerRef.current);
      }
      if (workerRef.current) {
        workerRef.current.terminate();
        workerRef.current = null;
      }
    };
  }, []);

  return {
    positions,
    isLayoutRunning,
    layoutError,
  };
}

