/**
 * Architecture Graph Orchestrator Hook (Frontend)
 *
 * Coordinates:
 * - 4-ID chain validation (Project, Repository, Analysis, Version)
 * - Exact canonical version verification
 * - Projection lifecycle status polling (2-second interval when active)
 * - Initial bounded window query (50 nodes / 100 edges)
 * - Explicit expansion operations (neighborhood, dependencies, dependents, containment, paths)
 * - Atomic P4-U1 state reducer management with 300/600 cap and referential integrity guards
 * - Request epoch protection, abort signal cancellation, and clean StrictMode unmounting
 */
import { useReducer, useEffect, useRef, useCallback } from 'react';
import {
  createInitialGraphState,
  architectureGraphReducer,
  GRAPH_ACTION_TYPES,
} from './architectureGraphState.js';
import { graphService } from '../services/graphService.js';
import { architectureService } from '../services/architectureService.js';
import {
  isValidUuid,
  DEFAULT_NODE_LIMIT,
  DEFAULT_EDGE_LIMIT,
  DEFAULT_PAGE_SIZE,
  DEFAULT_DEPTH,
  DEFAULT_TIMEOUT_SECONDS,
  PROJECTION_PUBLIC_STATUS,
  PROJECTION_ATTEMPT_STATUS,
} from '../contracts/graphContracts.js';

const DEFAULT_STATUS_POLL_INTERVAL_MS = 2000;
const DEFAULT_DISCOVERY_POLL_INTERVAL_MS = 5000;
const DEFAULT_DISCOVERY_TIMEOUT_MS = 180000;

function shouldPollStatus(result) {
  return Boolean(result && (result.discoveryPending ||
    [PROJECTION_PUBLIC_STATUS.PENDING, PROJECTION_PUBLIC_STATUS.RUNNING].includes(result.status) ||
    [PROJECTION_ATTEMPT_STATUS.QUEUED, PROJECTION_ATTEMPT_STATUS.RUNNING,
      PROJECTION_ATTEMPT_STATUS.RETRYING].includes(result.active_attempt?.status)));
}

/**
 * Hardened error formatter for Architecture Graph operations.
 * Maps Express and gateway error codes to user-friendly messages, distinguishes
 * local permission denial from upstream unavailability, handles expired cursors,
 * and sanitizes output to prevent any credential or token leakage.
 *
 * @param {Error|object|string} err
 * @param {string} [fallbackMessage='Operation failed']
 * @returns {string}
 */
export function formatGraphError(err, fallbackMessage = 'Operation failed') {
  if (!err) return fallbackMessage;

  const status = err.status || err.statusCode || err.response?.status;
  const code = err.code || err.error_code;
  const message = typeof err === 'string' ? err : err.message || '';

  // 1. 403 Forbidden - Permission denied (No logout / No token eviction)
  if (status === 403) {
    return 'Access denied: You do not have permission to perform this graph operation.';
  }

  // 2. 404 Not Found - Projection or Version unavailable
  if (code === 'graph_node_not_found') return 'This entity is not available in the current graph window.';
  if (status === 404) {
    return 'Architecture graph projection not found or unavailable for this version.';
  }

  // 3. 409 Conflict - Active rebuild already in progress
  if (status === 409) {
    if (code === 'graph_generation_changed') return 'The graph generation changed. Reload this version to continue.';
    if (code === 'graph_projection_not_ready') return 'The graph projection is still being prepared. Refresh status to check its progress.';
    return 'A rebuild operation is already in progress for this architecture version.';
  }

  // 4. 410 Gone / 422 Unprocessable Entity - Expired or invalid pagination cursor
  if (
    status === 410 ||
    (status === 422 && (code === 'GRAPH_CURSOR_EXPIRED' || message.toLowerCase().includes('cursor')))
  ) {
    return 'Pagination cursor expired. Continuation stopped. Please restart your exploration query.';
  }

  // 5. 504 Gateway Timeout or client timeout
  if (status === 504 || message.toLowerCase().includes('timeout')) {
    return 'Graph query timed out. Loaded data is preserved. You may retry.';
  }

  // 6. 500, 502, 503 - Upstream graph service unavailable
  if (status === 503 || status === 502 || status === 500) {
    return 'Graph service is temporarily unavailable. Loaded data is preserved. You may retry.';
  }

  // Sanitize generic error message: redact bearer tokens, JWTs, and long cursor signatures
  const sanitized = message
    .replace(/(?:bearer\s+)?[a-zA-Z0-9_\-\.]{25,}/gi, '[REDACTED]')
    .replace(/cursor=[^&\s]+/gi, 'cursor=[REDACTED]');

  return sanitized || fallbackMessage;
}

export function useArchitectureGraph(
  { projectId, repositoryId, analysisId, versionId },
  { pollIntervalMs = DEFAULT_STATUS_POLL_INTERVAL_MS,
    discoveryPollIntervalMs = DEFAULT_DISCOVERY_POLL_INTERVAL_MS,
    discoveryTimeoutMs = DEFAULT_DISCOVERY_TIMEOUT_MS } = {}
) {
  const [state, dispatch] = useReducer(
    architectureGraphReducer,
    { projectId, repositoryId, analysisId, versionId },
    createInitialGraphState
  );

  const epochRef = useRef(0);
  const activeControllerRef = useRef(null);
  const pollTimerRef = useRef(null);
  const discoveryRef = useRef({ deadline: null, waiting: false, seen: false });
  const statusRequestRef = useRef(null);

  // Clear any existing poll timer
  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  // Cancel any active network request
  const cancelActiveRequests = useCallback(() => {
    if (activeControllerRef.current) {
      activeControllerRef.current.abort();
      activeControllerRef.current = null;
    }
  }, []);

  // Fetch projection status
  const fetchStatus = useCallback(
    (epoch, signal = activeControllerRef.current?.signal) => {
      if (statusRequestRef.current?.epoch === epoch) return statusRequestRef.current.promise;
      const request = { epoch, promise: null };
      request.promise = (async () => {
        if (!versionId || !projectId) return null;
        try {
          const statusRes = await graphService.getStatus(versionId, { projectId, signal });
          if (epochRef.current === epoch) {
            discoveryRef.current = { deadline: null, waiting: false, seen: true };
            dispatch({
              type: GRAPH_ACTION_TYPES.UPDATE_PROJECTION_STATUS,
              payload: { status: statusRes },
            });
            return statusRes;
          }
        } catch (err) {
          if (!signal?.aborted && err.name !== 'AbortError' && epochRef.current === epoch) {
            const status = err.status || err.statusCode || err.response?.status;
            const code = err.code || err.error_code;
            // Canonical context was validated before this call. A not-yet-created
            // projection is expected until M1's periodic publication discovery runs.
            // Never mask unrelated 404s, authorization errors or a disappearing graph.
            if (status === 404 && code === 'graph_projection_not_found' && !discoveryRef.current.seen) {
              const discovery = discoveryRef.current;
              discovery.deadline ??= Date.now() + discoveryTimeoutMs;
              if (Date.now() < discovery.deadline) {
                discovery.waiting = true;
                dispatch({ type: GRAPH_ACTION_TYPES.WAIT_FOR_PROJECTION });
                return { discoveryPending: true }; // internal control result, not public status
              }
              discovery.waiting = false;
              dispatch({ type: GRAPH_ACTION_TYPES.FAIL_OPERATION, payload: { opKey: 'status',
                error: 'The graph scheduler has not created this projection yet. Automatic checks paused after three minutes. Refresh status to try again; if this persists, check graph worker health.' } });
              stopPolling();
              return null;
            }
            discoveryRef.current.waiting = false;
            const formatted = formatGraphError(err, 'Failed to fetch projection status');
            dispatch({
              type: GRAPH_ACTION_TYPES.FAIL_OPERATION,
              payload: { opKey: 'status', error: formatted },
            });
            if (status === 403 || status === 404) {
              stopPolling();
            }
          }
        }
        return null;
      })().finally(() => {
        if (statusRequestRef.current === request) statusRequestRef.current = null;
      });
      statusRequestRef.current = request;
      return request.promise;
    },
    [versionId, projectId, stopPolling, discoveryTimeoutMs]
  );

  // Poll status while attempt is running or projection is pending
  const scheduleStatusPoll = useCallback(
    (epoch) => {
      stopPolling();
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        return;
      }
      pollTimerRef.current = setTimeout(async () => {
        if (epochRef.current !== epoch) return;
        if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
        const res = await fetchStatus(epoch);
        if (res && epochRef.current === epoch) {
          if (shouldPollStatus(res) && (typeof document === 'undefined' || document.visibilityState !== 'hidden')) {
            scheduleStatusPoll(epoch);
          }
        }
      }, discoveryRef.current.waiting ? discoveryPollIntervalMs : pollIntervalMs);
    },
    [fetchStatus, stopPolling, pollIntervalMs, discoveryPollIntervalMs]
  );

  // 1. Validate context and canonical version on mount or ID changes
  useEffect(() => {
    stopPolling();
    cancelActiveRequests();

    const currentEpoch = ++epochRef.current;
    discoveryRef.current = { deadline: null, waiting: false, seen: false };
    const controller = new AbortController();
    activeControllerRef.current = controller;

    // Validate 4-ID chain syntax
    const ids = { projectId, repositoryId, analysisId, versionId };
    const missing = Object.entries(ids).filter(([_, v]) => !v);
    if (missing.length > 0) {
      dispatch({
        type: GRAPH_ACTION_TYPES.SET_CONTEXT_ERROR,
        payload: { error: `Missing required context IDs: ${missing.map(([k]) => k).join(', ')}` },
      });
      return;
    }

    const invalid = Object.entries(ids).filter(([_, v]) => !isValidUuid(v));
    if (invalid.length > 0) {
      dispatch({
        type: GRAPH_ACTION_TYPES.SET_CONTEXT_ERROR,
        payload: { error: `Invalid UUID format for IDs: ${invalid.map(([k]) => k).join(', ')}` },
      });
      return;
    }

    // Initialize clean state for the valid context
    dispatch({
      type: GRAPH_ACTION_TYPES.INITIALIZE_CONTEXT,
      payload: { projectId, repositoryId, analysisId, versionId },
    });

    // Validate canonical version through existing architectureService
    (async () => {
      try {
        const canonicalVersion = await architectureService.getVersion(versionId, { projectId });
        if (epochRef.current !== currentEpoch) return;

        // Verify loaded version matches requested chain
        if (!canonicalVersion || canonicalVersion.id !== versionId) {
          dispatch({
            type: GRAPH_ACTION_TYPES.SET_CONTEXT_ERROR,
            payload: { error: 'Loaded architecture version does not match requested route version.' },
          });
          return;
        }

        if (
          (canonicalVersion.project_id && canonicalVersion.project_id !== projectId) ||
          (canonicalVersion.repository_id && canonicalVersion.repository_id !== repositoryId) ||
          (canonicalVersion.analysis_id && canonicalVersion.analysis_id !== analysisId)
        ) {
          dispatch({
            type: GRAPH_ACTION_TYPES.SET_CONTEXT_ERROR,
            payload: { error: 'Architecture version does not match project, repository, or analysis context.' },
          });
          return;
        }

        dispatch({
          type: GRAPH_ACTION_TYPES.SET_VERSION_VALIDATED,
          payload: { version: canonicalVersion },
        });

        // Immediately fetch projection status
        const statusRes = await fetchStatus(currentEpoch, controller.signal);
        if (statusRes && epochRef.current === currentEpoch) {
          if (shouldPollStatus(statusRes)) {
            scheduleStatusPoll(currentEpoch);
          }
        }
      } catch (err) {
        if (err.name !== 'AbortError' && epochRef.current === currentEpoch) {
          dispatch({
            type: GRAPH_ACTION_TYPES.SET_CONTEXT_ERROR,
            payload: { error: err.message || 'Failed to validate canonical architecture version.' },
          });
        }
      }
    })();

    return () => {
      stopPolling();
      controller.abort();
      if (epochRef.current === currentEpoch) epochRef.current += 1;
    };
  }, [projectId, repositoryId, analysisId, versionId, fetchStatus, scheduleStatusPoll, stopPolling, cancelActiveRequests]);

  // 1b. Tab visibility listener: pause polling when hidden, resume single refresh and poll when visible
  useEffect(() => {
    if (typeof document === 'undefined') return;

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        stopPolling();
      } else if (document.visibilityState === 'visible') {
        const currentStatus = state.status?.status;
        const currentAttempt = state.status?.active_attempt?.status;
        const isPending =
          currentStatus === PROJECTION_PUBLIC_STATUS.PENDING ||
          currentStatus === PROJECTION_PUBLIC_STATUS.RUNNING;
        const attemptRunning =
          currentAttempt === PROJECTION_ATTEMPT_STATUS.QUEUED ||
          currentAttempt === PROJECTION_ATTEMPT_STATUS.RUNNING ||
          currentAttempt === PROJECTION_ATTEMPT_STATUS.RETRYING;

        if (isPending || attemptRunning || discoveryRef.current.waiting) {
          const epoch = epochRef.current;
          fetchStatus(epoch).then((res) => {
            if (res && epochRef.current === epoch) {
              if (shouldPollStatus(res)) {
                scheduleStatusPoll(epoch);
              }
            }
          });
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [state.status, stopPolling, fetchStatus, scheduleStatusPoll]);

  // 2. Initial window load when projection is COMPLETED or STALE with active generation
  useEffect(() => {
    if (!state.contextValidated || !state.status) return;

    const isReadable =
      state.status.status === PROJECTION_PUBLIC_STATUS.COMPLETED ||
      state.status.status === PROJECTION_PUBLIC_STATUS.STALE;
    const hasActiveGen = Boolean(state.status.active_generation_id);

    // Only trigger initial window if readable, has active gen, and zero nodes currently loaded
    if (isReadable && hasActiveGen && !state.isOutOfDate && state.loadedNodeCount === 0 && !state.operations.window) {
      const currentEpoch = epochRef.current;
      const opKey = 'window';

      dispatch({
        type: GRAPH_ACTION_TYPES.START_OPERATION,
        payload: { opKey, mode: 'window', fingerprint: `window:${DEFAULT_NODE_LIMIT}:${DEFAULT_EDGE_LIMIT}` },
      });

      graphService
        .getWindow(versionId, {
          projectId,
          nodeLimit: DEFAULT_NODE_LIMIT,
          edgeLimit: DEFAULT_EDGE_LIMIT,
          pageSize: DEFAULT_PAGE_SIZE,
          timeoutSeconds: DEFAULT_TIMEOUT_SECONDS,
          signal: activeControllerRef.current?.signal,
        })
        .then((subgraph) => {
          if (epochRef.current === currentEpoch) {
            dispatch({
              type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
              payload: { subgraph, opKey },
            });
          }
        })
        .catch((err) => {
          if (epochRef.current === currentEpoch) {
            const formatted = formatGraphError(err, 'Failed to load initial graph window');
            dispatch({
              type: GRAPH_ACTION_TYPES.FAIL_OPERATION,
              payload: { opKey, error: formatted },
            });
          }
        });
    }
  }, [
    state.contextValidated,
    state.status,
    state.loadedNodeCount,
    state.operations.window?.inFlight,
    state.isOutOfDate,
    state.requestEpoch,
    projectId,
    versionId,
  ]);

  // 3. User Actions

  // Refresh status manually
  const refreshStatus = useCallback(async () => {
    stopPolling();
    discoveryRef.current.deadline = null; // explicit manual retry starts a new bounded wait
    const currentEpoch = epochRef.current;
    const statusRes = await fetchStatus(currentEpoch);
    if (statusRes && state.loadedNodeCount === 0 && state.operations.window?.error) {
      dispatch({ type: GRAPH_ACTION_TYPES.CLEAR_EXPLORATION });
    }
    if (statusRes && epochRef.current === currentEpoch) {
      if (shouldPollStatus(statusRes)) {
        scheduleStatusPoll(currentEpoch);
      }
    }
    return statusRes;
  }, [fetchStatus, scheduleStatusPoll, stopPolling, state.loadedNodeCount, state.operations.window?.error]);

  // Request rebuild mutation (requires OWNER/ADMIN role)
  const requestRebuild = useCallback(async () => {
    const currentEpoch = epochRef.current;
    try {
      const result = await graphService.requestRebuild(versionId, { projectId });
      await refreshStatus();
      return result;
    } catch (err) {
      if (epochRef.current === currentEpoch) {
        const formatted = formatGraphError(err, 'Rebuild request failed');
        dispatch({
          type: GRAPH_ACTION_TYPES.FAIL_OPERATION,
          payload: { opKey: 'rebuild', error: formatted },
        });
      }
      throw err;
    }
  }, [versionId, projectId, refreshStatus]);

  // Expand neighborhood around anchor
  const expandNeighborhood = useCallback(
    async (entityId, options = {}) => {
      if (!entityId || state.isCapReached) return;
      const currentEpoch = epochRef.current;
      const opKey = `neighborhood:${entityId}`;
      const direction = options.direction || 'both';
      const depth = options.depth || DEFAULT_DEPTH;

      dispatch({
        type: GRAPH_ACTION_TYPES.START_OPERATION,
        payload: { opKey, mode: 'neighborhood', fingerprint: `${entityId}:${direction}:${depth}`, request: { ...options, entityId, direction, depth } },
      });

      try {
        const subgraph = await graphService.getNeighborhood(versionId, entityId, {
          projectId,
          direction,
          depth,
          nodeLimit: options.nodeLimit || DEFAULT_NODE_LIMIT,
          edgeLimit: options.edgeLimit || DEFAULT_EDGE_LIMIT,
          relationshipKinds: options.relationshipKinds,
          cursor: options.cursor,
          timeoutSeconds: DEFAULT_TIMEOUT_SECONDS,
        });

        if (epochRef.current === currentEpoch) {
          dispatch({
            type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
            payload: { subgraph, opKey },
          });
        }
      } catch (err) {
        if (epochRef.current === currentEpoch) {
          const formatted = formatGraphError(err, 'Neighborhood expansion failed');
          dispatch({
            type: GRAPH_ACTION_TYPES.FAIL_OPERATION,
            payload: { opKey, error: formatted },
          });
        }
      }
    },
    [versionId, projectId, state.isCapReached]
  );

  // Expand dependencies from anchor
  const expandDependencies = useCallback(
    async (entityId, options = {}) => {
      if (!entityId || state.isCapReached) return;
      const currentEpoch = epochRef.current;
      const opKey = `dependencies:${entityId}`;
      const depth = options.depth || DEFAULT_DEPTH;

      dispatch({
        type: GRAPH_ACTION_TYPES.START_OPERATION,
        payload: { opKey, mode: 'dependencies', fingerprint: `${entityId}:${depth}`, request: { ...options, entityId, depth } },
      });

      try {
        const subgraph = await graphService.getDependencies(versionId, entityId, {
          projectId,
          depth,
          nodeLimit: options.nodeLimit || DEFAULT_NODE_LIMIT,
          edgeLimit: options.edgeLimit || DEFAULT_EDGE_LIMIT,
          relationshipKinds: options.relationshipKinds,
          cursor: options.cursor,
          timeoutSeconds: DEFAULT_TIMEOUT_SECONDS,
        });

        if (epochRef.current === currentEpoch) {
          dispatch({
            type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
            payload: { subgraph, opKey },
          });
        }
      } catch (err) {
        if (epochRef.current === currentEpoch) {
          const formatted = formatGraphError(err, 'Dependencies expansion failed');
          dispatch({
            type: GRAPH_ACTION_TYPES.FAIL_OPERATION,
            payload: { opKey, error: formatted },
          });
        }
      }
    },
    [versionId, projectId, state.isCapReached]
  );

  // Expand dependents to anchor
  const expandDependents = useCallback(
    async (entityId, options = {}) => {
      if (!entityId || state.isCapReached) return;
      const currentEpoch = epochRef.current;
      const opKey = `dependents:${entityId}`;
      const depth = options.depth || DEFAULT_DEPTH;

      dispatch({
        type: GRAPH_ACTION_TYPES.START_OPERATION,
        payload: { opKey, mode: 'dependents', fingerprint: `${entityId}:${depth}`, request: { ...options, entityId, depth } },
      });

      try {
        const subgraph = await graphService.getDependents(versionId, entityId, {
          projectId,
          depth,
          nodeLimit: options.nodeLimit || DEFAULT_NODE_LIMIT,
          edgeLimit: options.edgeLimit || DEFAULT_EDGE_LIMIT,
          relationshipKinds: options.relationshipKinds,
          cursor: options.cursor,
          timeoutSeconds: DEFAULT_TIMEOUT_SECONDS,
        });

        if (epochRef.current === currentEpoch) {
          dispatch({
            type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
            payload: { subgraph, opKey },
          });
        }
      } catch (err) {
        if (epochRef.current === currentEpoch) {
          const formatted = formatGraphError(err, 'Dependents expansion failed');
          dispatch({
            type: GRAPH_ACTION_TYPES.FAIL_OPERATION,
            payload: { opKey, error: formatted },
          });
        }
      }
    },
    [versionId, projectId, state.isCapReached]
  );

  // Expand containment hierarchy
  const expandContainment = useCallback(
    async (entityId, options = {}) => {
      if (!entityId || state.isCapReached) return;
      const currentEpoch = epochRef.current;
      const opKey = `containment:${entityId}`;
      const direction = options.direction || 'children';
      const depth = options.depth || DEFAULT_DEPTH;

      dispatch({
        type: GRAPH_ACTION_TYPES.START_OPERATION,
        payload: { opKey, mode: 'containment', fingerprint: `${entityId}:${direction}:${depth}`, request: { ...options, entityId, direction, depth } },
      });

      try {
        const subgraph = await graphService.getContainment(versionId, entityId, {
          projectId,
          direction,
          depth,
          nodeLimit: options.nodeLimit || DEFAULT_NODE_LIMIT,
          edgeLimit: options.edgeLimit || DEFAULT_EDGE_LIMIT,
          cursor: options.cursor,
          timeoutSeconds: DEFAULT_TIMEOUT_SECONDS,
        });

        if (epochRef.current === currentEpoch) {
          dispatch({
            type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
            payload: { subgraph, opKey },
          });
        }
      } catch (err) {
        if (epochRef.current === currentEpoch) {
          const formatted = formatGraphError(err, 'Containment expansion failed');
          dispatch({
            type: GRAPH_ACTION_TYPES.FAIL_OPERATION,
            payload: { opKey, error: formatted },
          });
        }
      }
    },
    [versionId, projectId, state.isCapReached]
  );

  // Search bounded paths between two nodes
  const findPaths = useCallback(
    async (sourceEntityId, targetEntityId, options = {}) => {
      if (!sourceEntityId || !targetEntityId || state.isCapReached) return;
      const currentEpoch = epochRef.current;
      const opKey = `paths:${sourceEntityId}:${targetEntityId}`;
      const maxDepth = options.maxDepth || 3;
      const pathLimit = options.pathLimit || 5;

      dispatch({
        type: GRAPH_ACTION_TYPES.SET_PATH_ENDPOINTS,
        payload: { sourceEntityId, targetEntityId },
      });

      dispatch({
        type: GRAPH_ACTION_TYPES.START_OPERATION,
        payload: { opKey, mode: 'paths', fingerprint: `${sourceEntityId}:${targetEntityId}:${maxDepth}:${pathLimit}` },
      });

      try {
        const pathResult = await graphService.getBoundedPaths(versionId, {
          projectId,
          sourceEntityId,
          targetEntityId,
          maxDepth,
          pathLimit,
          relationshipKinds: options.relationshipKinds,
          timeoutSeconds: DEFAULT_TIMEOUT_SECONDS,
        });

        if (epochRef.current === currentEpoch) {
          dispatch({
            type: GRAPH_ACTION_TYPES.MERGE_PATHS,
            payload: { pathResult, opKey },
          });
        }
      } catch (err) {
        if (epochRef.current === currentEpoch) {
          const formatted = formatGraphError(err, 'Path search failed');
          dispatch({
            type: GRAPH_ACTION_TYPES.FAIL_OPERATION,
            payload: { opKey, error: formatted },
          });
        }
      }
    },
    [versionId, projectId, state.isCapReached]
  );

  // Load more continuation for an operation with an opaque next cursor
  const loadMore = useCallback(
    async (opKey) => {
      const op = state.operations[opKey];
      if (!op || !op.cursor || op.inFlight || state.isCapReached) return;

      const currentEpoch = epochRef.current;
      dispatch({
        type: GRAPH_ACTION_TYPES.START_OPERATION,
        payload: { opKey, mode: op.mode, fingerprint: op.fingerprint },
      });

      try {
        let subgraph;
        if (op.mode === 'window') {
          subgraph = await graphService.getWindow(versionId, {
            projectId,
            nodeLimit: DEFAULT_NODE_LIMIT,
            edgeLimit: DEFAULT_EDGE_LIMIT,
            pageSize: DEFAULT_PAGE_SIZE,
            cursor: op.cursor,
            timeoutSeconds: DEFAULT_TIMEOUT_SECONDS,
          });
        } else if (op.request) {
          const { entityId, ...requestOptions } = op.request;
          const method = {
            neighborhood: 'getNeighborhood',
            dependencies: 'getDependencies',
            dependents: 'getDependents',
            containment: 'getContainment',
          }[op.mode];
          if (method) {
            subgraph = await graphService[method](versionId, entityId, {
              ...requestOptions,
              projectId,
              nodeLimit: requestOptions.nodeLimit || DEFAULT_NODE_LIMIT,
              edgeLimit: requestOptions.edgeLimit || DEFAULT_EDGE_LIMIT,
              cursor: op.cursor,
              timeoutSeconds: DEFAULT_TIMEOUT_SECONDS,
              signal: activeControllerRef.current?.signal,
            });
          }
        }

        if (subgraph && epochRef.current === currentEpoch) {
          dispatch({
            type: GRAPH_ACTION_TYPES.MERGE_SUBGRAPH,
            payload: { subgraph, opKey },
          });
        }
      } catch (err) {
        if (epochRef.current === currentEpoch) {
          const formatted = formatGraphError(err, 'Continuation load failed');
          dispatch({
            type: GRAPH_ACTION_TYPES.FAIL_OPERATION,
            payload: { opKey, error: formatted },
          });
        }
      }
    },
    [state.operations, state.isCapReached, versionId, projectId]
  );

  // Select node
  const selectNode = useCallback(
    (nodeId) => {
      dispatch({
        type: GRAPH_ACTION_TYPES.SELECT_NODE,
        payload: { nodeId },
      });
      if (nodeId) {
        const currentEpoch = epochRef.current;
        graphService
          .getNodeDetail(versionId, nodeId, { projectId, timeoutSeconds: DEFAULT_TIMEOUT_SECONDS })
          .then((detail) => {
            if (epochRef.current !== currentEpoch) return;
            dispatch({
              type: GRAPH_ACTION_TYPES.SET_NODE_DETAIL,
              payload: { detail },
            });
          })
          .catch(() => {});
      }
    },
    [versionId, projectId]
  );

  // Select edge
  const selectEdge = useCallback((edgeId) => {
    dispatch({
      type: GRAPH_ACTION_TYPES.SELECT_EDGE,
      payload: { edgeId },
    });
  }, []);

  // Clear exploration
  const clearExploration = useCallback(() => {
    dispatch({ type: GRAPH_ACTION_TYPES.CLEAR_EXPLORATION });
  }, []);

  // Reload version when out-of-date banner is clicked
  const reloadVersion = useCallback(() => {
    dispatch({ type: GRAPH_ACTION_TYPES.RELOAD_VERSION });
    refreshStatus();
  }, [refreshStatus]);

  return {
    state,
    dispatch,
    refreshStatus,
    requestRebuild,
    loadMore,
    expandNeighborhood,
    expandDependencies,
    expandDependents,
    expandContainment,
    findPaths,
    selectNode,
    selectEdge,
    clearExploration,
    reloadVersion,
  };
}
