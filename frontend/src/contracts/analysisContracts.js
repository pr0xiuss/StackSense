/**
 * Analysis Domain Contracts and Vocabulary (Frontend)
 *
 * Defines canonical constants, types, labels, and formatting utilities
 * for Analysis lifecycle states, stages, diagnostics, and SSE events.
 */

/**
 * Canonical lifecycle status for an Analysis run.
 * @readonly
 * @enum {string}
 */
export const ANALYSIS_STATUS = Object.freeze({
  CREATED: 'created',
  QUEUED: 'queued',
  RUNNING: 'running',
  PARTIAL: 'partial',
  COMPLETED: 'completed',
  COMPLETED_WITH_WARNINGS: 'completed_with_warnings',
  FAILED: 'failed',
  CANCEL_REQUESTED: 'cancel_requested',
  CANCELLED: 'cancelled',
  TIMEOUT: 'timeout',
});

/**
 * Terminal statuses where an analysis run will no longer make progress.
 * Live polling and SSE listeners should disconnect on terminal statuses.
 */
export const TERMINAL_ANALYSIS_STATUSES = Object.freeze([
  ANALYSIS_STATUS.COMPLETED,
  ANALYSIS_STATUS.COMPLETED_WITH_WARNINGS,
  ANALYSIS_STATUS.FAILED,
  ANALYSIS_STATUS.CANCELLED,
  ANALYSIS_STATUS.TIMEOUT,
]);

/**
 * Ordered pipeline stage identifiers.
 * @readonly
 * @enum {string}
 */
export const STAGE_NAME = Object.freeze({
  INPUT_VALIDATION: 'input_validation',
  INVENTORY: 'inventory',
  LANGUAGE_DETECTION: 'language_detection',
  FRAMEWORK_DETECTION: 'framework_detection',
  SYNTAX_EXTRACTION: 'syntax_extraction',
  IR_CONSTRUCTION: 'ir_construction',
  IDENTITY_RESOLUTION: 'identity_resolution',
  ARCHITECTURE_BUILD: 'architecture_build',
});

/**
 * Canonical lifecycle status for an individual stage.
 * @readonly
 * @enum {string}
 */
export const STAGE_STATUS = Object.freeze({
  PENDING: 'pending',
  QUEUED: 'queued',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  SKIPPED: 'skipped',
  CANCELLED: 'cancelled',
});

/**
 * Terminal stage statuses.
 */
export const TERMINAL_STAGE_STATUSES = Object.freeze([
  STAGE_STATUS.COMPLETED,
  STAGE_STATUS.FAILED,
  STAGE_STATUS.SKIPPED,
  STAGE_STATUS.CANCELLED,
]);

/**
 * Diagnostic severity levels.
 * @readonly
 * @enum {string}
 */
export const DIAGNOSTIC_SEVERITY = Object.freeze({
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
});

/**
 * Friendly labels for Analysis lifecycle statuses.
 */
export const ANALYSIS_STATUS_LABELS = Object.freeze({
  [ANALYSIS_STATUS.CREATED]: 'Created',
  [ANALYSIS_STATUS.QUEUED]: 'Queued',
  [ANALYSIS_STATUS.RUNNING]: 'Running',
  [ANALYSIS_STATUS.PARTIAL]: 'Partial',
  [ANALYSIS_STATUS.COMPLETED]: 'Completed',
  [ANALYSIS_STATUS.COMPLETED_WITH_WARNINGS]: 'Completed with Warnings',
  [ANALYSIS_STATUS.FAILED]: 'Failed',
  [ANALYSIS_STATUS.CANCEL_REQUESTED]: 'Cancelling…',
  [ANALYSIS_STATUS.CANCELLED]: 'Cancelled',
  [ANALYSIS_STATUS.TIMEOUT]: 'Timed Out',
});

/**
 * Friendly labels for pipeline stages.
 */
export const STAGE_NAME_LABELS = Object.freeze({
  [STAGE_NAME.INPUT_VALIDATION]: 'Input Validation',
  [STAGE_NAME.INVENTORY]: 'File Inventory',
  [STAGE_NAME.LANGUAGE_DETECTION]: 'Language Detection',
  [STAGE_NAME.FRAMEWORK_DETECTION]: 'Framework Detection',
  [STAGE_NAME.SYNTAX_EXTRACTION]: 'Syntax Extraction',
  [STAGE_NAME.IR_CONSTRUCTION]: 'IR Construction',
  [STAGE_NAME.IDENTITY_RESOLUTION]: 'Identity Resolution',
  [STAGE_NAME.ARCHITECTURE_BUILD]: 'Architecture Build',
});

/**
 * Check if an analysis status is terminal.
 * @param {string} [status]
 * @returns {boolean}
 */
export function isTerminalStatus(status) {
  if (!status) return false;
  return TERMINAL_ANALYSIS_STATUSES.includes(status.toLowerCase());
}

/**
 * Check if a stage status is terminal.
 * @param {string} [status]
 * @returns {boolean}
 */
export function isTerminalStage(status) {
  if (!status) return false;
  return TERMINAL_STAGE_STATUSES.includes(status.toLowerCase());
}

/**
 * Get friendly display label for an analysis status.
 * @param {string} [status]
 * @returns {string}
 */
export function getStatusLabel(status) {
  if (!status) return 'Unknown';
  const key = status.toLowerCase();
  return ANALYSIS_STATUS_LABELS[key] || status;
}

/**
 * Get friendly display label for a stage name.
 * @param {string} [stageName]
 * @returns {string}
 */
export function getStageLabel(stageName) {
  if (!stageName) return 'Unknown Stage';
  const key = stageName.toLowerCase();
  return STAGE_NAME_LABELS[key] || stageName;
}

/**
 * CSS class generator for analysis status badges.
 * @param {string} [status]
 * @returns {string}
 */
export function getStatusBadgeClass(status) {
  const norm = (status || '').toLowerCase();
  switch (norm) {
    case ANALYSIS_STATUS.COMPLETED:
      return 'badge-status-completed';
    case ANALYSIS_STATUS.COMPLETED_WITH_WARNINGS:
      return 'badge-status-warning';
    case ANALYSIS_STATUS.RUNNING:
      return 'badge-status-running';
    case ANALYSIS_STATUS.QUEUED:
    case ANALYSIS_STATUS.CREATED:
      return 'badge-status-queued';
    case ANALYSIS_STATUS.FAILED:
    case ANALYSIS_STATUS.TIMEOUT:
      return 'badge-status-failed';
    case ANALYSIS_STATUS.CANCEL_REQUESTED:
    case ANALYSIS_STATUS.CANCELLED:
      return 'badge-status-cancelled';
    case ANALYSIS_STATUS.PARTIAL:
      return 'badge-status-partial';
    default:
      return 'badge-status-default';
  }
}

/**
 * CSS class generator for diagnostic severity badges.
 * @param {string} [severity]
 * @returns {string}
 */
export function getSeverityBadgeClass(severity) {
  const norm = (severity || '').toLowerCase();
  switch (norm) {
    case DIAGNOSTIC_SEVERITY.ERROR:
      return 'badge-severity-error';
    case DIAGNOSTIC_SEVERITY.WARNING:
      return 'badge-severity-warning';
    case DIAGNOSTIC_SEVERITY.INFO:
      return 'badge-severity-info';
    default:
      return 'badge-severity-default';
  }
}

/**
 * Calculate human-readable duration between two dates.
 * @param {string|Date} [startedAt]
 * @param {string|Date} [completedAt]
 * @returns {string}
 */
export function formatDuration(startedAt, completedAt) {
  if (!startedAt) return '—';
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  if (isNaN(start) || isNaN(end) || end < start) return '—';

  const totalSeconds = Math.floor((end - start) / 1000);
  if (totalSeconds < 1) return '< 1s';
  if (totalSeconds < 60) return `${totalSeconds}s`;

  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;
  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

