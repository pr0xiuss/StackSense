/**
 * Analysis API Service (Frontend)
 *
 * Provides typed operations for Analysis creation, listing, cancellation,
 * diagnostics, published architecture retrieval, and SSE event streaming.
 */
import { apiClient } from './apiClient.js';

export const analysisService = {
  /**
   * Create and trigger an analysis run for a repository revision.
   *
   * @param {object} payload
   * @param {string} payload.project_id - Project UUID
   * @param {string} payload.repository_id - Repository UUID
   * @param {string} payload.revision_id - Repository Revision UUID
   * @param {string[]} [payload.include_paths] - Optional path filters
   * @param {string[]} [payload.exclude_paths] - Optional path excludes
   * @param {number} [payload.max_file_size_bytes] - Max file size in bytes (1..50 MiB)
   * @param {number} [payload.timeout_seconds] - Analysis timeout (1..1800s)
   * @param {string} [payload.idempotency_key] - Client-generated UUID for retry safety
   * @returns {Promise<object>} AnalysisResponse
   */
  async createAnalysis(payload) {
    const body = {
      project_id: payload.project_id,
      repository_id: payload.repository_id,
      revision_id: payload.revision_id,
    };

    if (Array.isArray(payload.include_paths) && payload.include_paths.length > 0) {
      body.include_paths = payload.include_paths;
    }
    if (Array.isArray(payload.exclude_paths) && payload.exclude_paths.length > 0) {
      body.exclude_paths = payload.exclude_paths;
    }
    if (typeof payload.max_file_size_bytes === 'number' && payload.max_file_size_bytes > 0) {
      body.max_file_size_bytes = payload.max_file_size_bytes;
    }
    if (typeof payload.timeout_seconds === 'number' && payload.timeout_seconds > 0) {
      body.timeout_seconds = payload.timeout_seconds;
    }
    if (payload.idempotency_key && typeof payload.idempotency_key === 'string') {
      body.idempotency_key = payload.idempotency_key.trim();
    }

    return apiClient.post('/analyses', body);
  },

  /**
   * List analysis runs for a project, optionally filtered by repository and status.
   *
   * @param {object} params
   * @param {string} params.projectId - Project UUID
   * @param {string} [params.repositoryId] - Optional Repository UUID filter
   * @param {number} [params.limit=50] - Number of items to return
   * @param {number} [params.offset=0] - Pagination offset
   * @param {string} [params.status] - Optional Analysis status filter
   * @returns {Promise<{ items: object[], total: number, limit: number, offset: number }>}
   */
  async listAnalyses({ projectId, repositoryId, limit = 50, offset = 0, status } = {}) {
    if (!projectId) {
      throw new Error('projectId is required to list analyses.');
    }
    const params = new URLSearchParams();
    params.set('project_id', projectId);
    if (repositoryId) {
      params.set('repository_id', repositoryId);
    }
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (status && status !== 'all') {
      params.set('status', status);
    }

    return apiClient.get(`/analyses?${params.toString()}`);
  },

  /**
   * Retrieve details and current progress of an analysis run.
   *
   * @param {string} analysisId - Analysis UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @returns {Promise<object>} AnalysisResponse
   */
  async getAnalysis(analysisId, { projectId } = {}) {
    if (!analysisId) throw new Error('analysisId is required');
    if (!projectId) throw new Error('projectId is required');
    return apiClient.get(`/analyses/${analysisId}?project_id=${encodeURIComponent(projectId)}`);
  },

  /**
   * Request cancellation of a queued or running analysis.
   *
   * @param {string} analysisId - Analysis UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @param {string} [options.reason] - Optional cancellation reason
   * @returns {Promise<object>} AnalysisResponse
   */
  async cancelAnalysis(analysisId, { projectId, reason } = {}) {
    if (!analysisId) throw new Error('analysisId is required');
    if (!projectId) throw new Error('projectId is required');
    const body = {};
    if (reason && typeof reason === 'string') {
      body.reason = reason.trim();
    }
    return apiClient.post(`/analyses/${analysisId}/cancel?project_id=${encodeURIComponent(projectId)}`, body);
  },

  /**
   * List diagnostics recorded during an analysis run.
   *
   * @param {string} analysisId - Analysis UUID
   * @param {object} params
   * @param {string} params.projectId - Project UUID
   * @param {number} [params.limit=50]
   * @param {number} [params.offset=0]
   * @param {string} [params.severity] - Optional severity filter (error, warning, info)
   * @param {string} [params.stage] - Optional stage filter
   * @returns {Promise<{ items: object[], total: number, limit: number, offset: number }>}
   */
  async listDiagnostics(analysisId, { projectId, limit = 50, offset = 0, severity, stage } = {}) {
    if (!analysisId) throw new Error('analysisId is required');
    if (!projectId) throw new Error('projectId is required');
    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (severity) params.set('severity', severity);
    if (stage) params.set('stage', stage);

    return apiClient.get(`/analyses/${analysisId}/diagnostics?${params.toString()}`);
  },

  /**
   * Retrieve the published architecture version associated with an analysis run.
   *
   * @param {string} analysisId - Analysis UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @returns {Promise<object>} ArchitectureVersionResponse
   */
  async getAnalysisArchitecture(analysisId, { projectId } = {}) {
    if (!analysisId) throw new Error('analysisId is required');
    if (!projectId) throw new Error('projectId is required');
    return apiClient.get(`/analyses/${analysisId}/architecture?project_id=${encodeURIComponent(projectId)}`);
  },

  /**
   * Subscribe to server-sent events (SSE) for an analysis run.
   *
   * @param {string} analysisId - Analysis UUID
   * @param {object} options
   * @param {string} options.projectId - Project UUID
   * @param {number} [options.afterSequence] - Sequence number to resume from
   * @param {string} [options.lastEventId] - Last event ID header for resumption
   * @param {function(Response): void} [options.onOpen] - Connection opened callback
   * @param {function({ event: string, id: string|null, data: any }): void} [options.onMessage] - Event callback
   * @param {function(Error): void} [options.onError] - Error callback
   * @param {function(): void} [options.onClose] - Close callback
   * @param {AbortSignal} [options.signal] - Abort signal for unmounting/cancelling
   * @returns {{ abort: () => void }}
   */
  subscribeToEvents(
    analysisId,
    { projectId, afterSequence, lastEventId, onOpen, onMessage, onError, onClose, signal } = {}
  ) {
    if (!analysisId) throw new Error('analysisId is required');
    if (!projectId) throw new Error('projectId is required');

    const params = new URLSearchParams();
    params.set('project_id', projectId);
    if (typeof afterSequence === 'number') {
      params.set('after_sequence', String(afterSequence));
    }

    const headers = {};
    if (lastEventId) {
      headers['Last-Event-ID'] = String(lastEventId);
    }

    return apiClient.stream(`/analyses/${analysisId}/events?${params.toString()}`, {
      headers,
      signal,
      onOpen,
      onMessage,
      onError,
      onClose,
    });
  },
};

