import { useState, useEffect, useRef, useCallback } from 'react';
import { analysisService } from '../services/analysisService.js';
import { isTerminalStatus } from '../contracts/analysisContracts.js';

const POLL_INTERVAL_MS = 3000;
const INITIAL_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 15000;

/**
 * Custom React hook managing the live lifecycle of an Analysis run.
 *
 * Enforces:
 * - Authoritative REST state (SSE invalidates and triggers REST refetch)
 * - Single in-flight REST request protection
 * - Single active SSE stream with reconnect backoff capped at 15s
 * - Serialized 3s polling fallback when SSE disconnects
 * - Immediate cessation of background streaming & polling when terminal state is reached
 * - Clean teardown on unmount
 *
 * @param {string} projectId - Project UUID
 * @param {string} analysisId - Analysis UUID
 * @returns {{
 *   analysis: object|null,
 *   loading: boolean,
 *   refreshing: boolean,
 *   error: string|null,
 *   errorCode: string|number|null,
 *   isLive: boolean,
 *   isTerminal: boolean,
 *   refetch: () => Promise<void>
 * }}
 */
export function useAnalysisLiveStatus(projectId, analysisId) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [errorCode, setErrorCode] = useState(null);
  const [isLive, setIsLive] = useState(false);

  const isMountedRef = useRef(true);
  const inFlightRef = useRef(false);
  const streamHandleRef = useRef(null);
  const pollTimerRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY_MS);
  const isTerminalRef = useRef(false);

  // Stop all background polling and streaming
  const stopLiveUpdates = useCallback(() => {
    if (streamHandleRef.current) {
      try {
        streamHandleRef.current.abort('terminal_or_unmount');
      } catch {
        // Ignored
      }
      streamHandleRef.current = null;
    }
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (isMountedRef.current) {
      setIsLive(false);
    }
  }, []);

  // Authoritative REST fetch
  const fetchAnalysis = useCallback(
    async (isManual = false) => {
      if (!projectId || !analysisId) return null;
      if (inFlightRef.current) return null;

      inFlightRef.current = true;
      if (!isManual && isMountedRef.current && analysis) {
        setRefreshing(true);
      }

      try {
        const data = await analysisService.getAnalysis(analysisId, { projectId });
        if (!isMountedRef.current) return null;

        setAnalysis(data);
        setError(null);
        setErrorCode(null);

        const terminal = isTerminalStatus(data?.status);
        isTerminalRef.current = terminal;

        if (terminal) {
          stopLiveUpdates();
        }

        return data;
      } catch (err) {
        if (!isMountedRef.current) return null;
        setError(err.message || 'Failed to load analysis details.');
        setErrorCode(err.status || err.code || null);
        return null;
      } finally {
        inFlightRef.current = false;
        if (isMountedRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [projectId, analysisId, analysis, stopLiveUpdates]
  );

  // Serialized polling fallback
  const schedulePoll = useCallback(() => {
    if (!isMountedRef.current || isTerminalRef.current) return;
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);

    pollTimerRef.current = setTimeout(async () => {
      if (!isMountedRef.current || isTerminalRef.current) return;
      const data = await fetchAnalysis(false);
      if (data && !isTerminalStatus(data.status) && !isLive) {
        schedulePoll();
      }
    }, POLL_INTERVAL_MS);
  }, [fetchAnalysis, isLive]);

  // Connect SSE with backoff
  const connectSSE = useCallback(() => {
    if (!isMountedRef.current || isTerminalRef.current) return;

    if (streamHandleRef.current) {
      try {
        streamHandleRef.current.abort('reconnecting');
      } catch {
        // Ignored
      }
      streamHandleRef.current = null;
    }

    try {
      const handle = analysisService.subscribeToEvents(analysisId, {
        projectId,
        onOpen: () => {
          if (!isMountedRef.current || isTerminalRef.current) return;
          setIsLive(true);
          reconnectDelayRef.current = INITIAL_RECONNECT_DELAY_MS;
          // Clear polling fallback when stream is established
          if (pollTimerRef.current) {
            clearTimeout(pollTimerRef.current);
            pollTimerRef.current = null;
          }
        },
        onMessage: () => {
          if (!isMountedRef.current || isTerminalRef.current) return;
          // Authoritative REST refetch triggered by SSE notification
          fetchAnalysis(false);
        },
        onError: () => {
          if (!isMountedRef.current) return;
          setIsLive(false);

          if (!isTerminalRef.current) {
            // Activate polling fallback immediately upon stream disconnect
            schedulePoll();

            // Schedule stream reconnect with bounded exponential backoff
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
            const delay = reconnectDelayRef.current;
            reconnectTimerRef.current = setTimeout(() => {
              if (isMountedRef.current && !isTerminalRef.current) {
                connectSSE();
              }
            }, delay);
            reconnectDelayRef.current = Math.min(
              MAX_RECONNECT_DELAY_MS,
              Math.floor(delay * 1.5)
            );
          }
        },
        onClose: () => {
          if (!isMountedRef.current) return;
          setIsLive(false);
          if (!isTerminalRef.current) {
            schedulePoll();
          }
        },
      });

      streamHandleRef.current = handle;
    } catch {
      setIsLive(false);
      schedulePoll();
    }
  }, [analysisId, projectId, fetchAnalysis, schedulePoll]);

  // Initial load and stream management
  useEffect(() => {
    isMountedRef.current = true;
    isTerminalRef.current = false;
    setLoading(true);
    setError(null);
    setErrorCode(null);

    let active = true;

    analysisService
      .getAnalysis(analysisId, { projectId })
      .then((data) => {
        if (!active || !isMountedRef.current) return;
        setAnalysis(data);
        const terminal = isTerminalStatus(data?.status);
        isTerminalRef.current = terminal;

        if (!terminal) {
          connectSSE();
        }
      })
      .catch((err) => {
        if (!active || !isMountedRef.current) return;
        setError(err.message || 'Failed to load analysis details.');
        setErrorCode(err.status || err.code || null);
      })
      .finally(() => {
        if (active && isMountedRef.current) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
      isMountedRef.current = false;
      stopLiveUpdates();
    };
  }, [projectId, analysisId, connectSSE, stopLiveUpdates]);

  const refetch = useCallback(() => fetchAnalysis(true), [fetchAnalysis]);

  return {
    analysis,
    loading,
    refreshing,
    error,
    errorCode,
    isLive,
    isTerminal: isTerminalStatus(analysis?.status),
    refetch,
  };
}

