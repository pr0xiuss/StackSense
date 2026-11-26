/**
 * useIntelligenceDelivery Hook
 *
 * Manages C0 delivery status polling and manual idempotent retries.
 * Enforces non-overlapping poll cycles, terminal completion detection,
 * document visibility pausing/resuming, and clean request abortion.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { deliveryService } from '../services/deliveryService.js';

const TERMINAL_STATES = new Set(['COMPLETED', 'FAILED', 'CANCELLED']);

export function useIntelligenceDelivery(versionId, {
  projectId,
  enabled = true,
  pollIntervalMs = 3000,
  initialDelivery = null,
} = {}) {
  const [delivery, setDelivery] = useState(initialDelivery);
  const [loading, setLoading] = useState(!initialDelivery && enabled && Boolean(versionId && projectId));
  const [error, setError] = useState(null);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState(null);

  const inFlightRef = useRef(false);
  const timerRef = useRef(null);
  const abortControllerRef = useRef(null);
  const isMountedRef = useRef(true);

  // Helper to test if a delivery summary is terminal
  const isTerminal = useCallback((summary) => {
    if (!summary) return false;
    const work = [...(summary.diagrams || []), summary.search, summary.report].filter(Boolean);
    return work.length > 0 && work.every((item) => TERMINAL_STATES.has(item.state));
  }, []);

  const fetchStatus = useCallback(async (isInitial = false) => {
    if (!enabled || !versionId || !projectId) return;
    if (inFlightRef.current) return;

    inFlightRef.current = true;
    if (isInitial && !delivery) {
      setLoading(true);
    }

    // Abort previous in-flight request if any
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const result = await deliveryService.getDelivery(versionId, {
        projectId,
        signal: controller.signal,
      });

      if (!isMountedRef.current || controller.signal.aborted) return;

      setDelivery(result);
      setError(null);

      // If not terminal and document is visible, schedule next poll
      if (!isTerminal(result) && !document.hidden && enabled) {
        timerRef.current = setTimeout(() => {
          fetchStatus(false);
        }, pollIntervalMs);
      }
    } catch (err) {
      if (!isMountedRef.current || controller.signal.aborted) return;
      // Do not schedule further polls on fatal auth/conflict errors (403, 404, 409, 410)
      const status = err?.status || err?.response?.status;
      setError(err?.message || 'Failed to fetch delivery status');
      if (status !== 403 && status !== 404 && status !== 409 && status !== 410) {
        if (!document.hidden && enabled) {
          timerRef.current = setTimeout(() => {
            fetchStatus(false);
          }, pollIntervalMs * 2); // Exponential backoff on transient errors
        }
      }
    } finally {
      inFlightRef.current = false;
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [enabled, versionId, projectId, pollIntervalMs, isTerminal, delivery]);

  // Main lifecycle effect
  useEffect(() => {
    isMountedRef.current = true;

    if (enabled && versionId && projectId) {
      fetchStatus(true);
    }

    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Tab hidden: pause polling timer
        if (timerRef.current) {
          clearTimeout(timerRef.current);
          timerRef.current = null;
        }
      } else {
        // Tab restored: resume polling if not terminal
        if (enabled && versionId && projectId && !isTerminal(delivery)) {
          fetchStatus(false);
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isMountedRef.current = false;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, [versionId, projectId, enabled]);

  // Trigger manual idempotent retry
  const retryWorkItem = useCallback(async (item) => {
    if (!versionId || !projectId || !item?.work_id || !item?.kind) {
      throw new Error('versionId, projectId, and workItemId are required to retry');
    }

    setRetrying(true);
    setRetryError(null);

    try {
      const idempotencyKey = typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `retry-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

      const payload = {
        resource_type: item.kind,
        resource_id: item.work_id,
        idempotency_key: idempotencyKey,
      };

      const response = await deliveryService.retryDelivery(versionId, payload, { projectId });

      // Immediate refresh after accepting retry
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      await fetchStatus(false);

      return response;
    } catch (err) {
      setRetryError(err?.message || 'Failed to retry delivery work item');
      throw err;
    } finally {
      if (isMountedRef.current) {
        setRetrying(false);
      }
    }
  }, [versionId, projectId, fetchStatus]);

  return {
    delivery,
    loading,
    error,
    retrying,
    retryError,
    refresh: () => fetchStatus(false),
    retryWorkItem,
    isTerminal: isTerminal(delivery),
  };
}
