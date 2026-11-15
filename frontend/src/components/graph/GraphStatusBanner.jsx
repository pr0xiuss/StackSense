/**
 * GraphStatusBanner component
 *
 * Renders projection public lifecycle state badges, active rebuild attempt summaries,
 * generation update (out-of-date) notifications, 300/600 capacity limit alerts,
 * and actionable retry/rebuild/reload triggers.
 */
import React from 'react';
import {
  PROJECTION_PUBLIC_STATUS,
  PROJECTION_ATTEMPT_STATUS,
} from '../../contracts/graphContracts.js';

export function GraphStatusBanner({
  status,
  isOutOfDate = false,
  generationChangeMessage = null,
  isCapReached = false,
  capMessage = null,
  error = null,
  canManage = false, // OWNER or ADMIN role
  onRetry = null,
  onRebuild = null,
  onReload = null,
  isRebuilding = false,
}) {
  const publicState = status?.status || null;
  const activeAttempt = status?.active_attempt || null;
  const activeGen = status?.active_generation_id || null;

  return (
    <div className="graph-status-container" role="region" aria-label="Graph projection status">
      {/* 1. Critical Errors */}
      {error && (
        <div className="graph-banner graph-banner-error" role="alert">
          <div className="graph-banner-content">
            <span className="graph-banner-icon" aria-hidden="true">⚠️</span>
            <span className="graph-banner-text">{error}</span>
          </div>
          {onRetry && (
            <button
              type="button"
              className="graph-btn graph-btn-secondary"
              onClick={onRetry}
            >
              Retry
            </button>
          )}
        </div>
      )}

      {/* 2. Out-of-date Banner (generation changed on server) */}
      {isOutOfDate && (
        <div className="graph-banner graph-banner-warning" role="alert">
          <div className="graph-banner-content">
            <span className="graph-banner-icon" aria-hidden="true">🔄</span>
            <span className="graph-banner-text">
              {generationChangeMessage || 'A newer graph generation is available for this version. Current view is frozen.'}
            </span>
          </div>
          {onReload && (
            <button
              type="button"
              className="graph-btn graph-btn-primary"
              onClick={onReload}
            >
              Reload this version
            </button>
          )}
        </div>
      )}

      {/* 3. Canvas Capacity Limit Notice */}
      {isCapReached && (
        <div className="graph-banner graph-banner-info" role="status" aria-live="polite">
          <div className="graph-banner-content">
            <span className="graph-banner-icon" aria-hidden="true">ℹ️</span>
            <span className="graph-banner-text">
              {capMessage || 'Canvas limit reached (300 nodes / 600 edges). Additional items withheld.'}
            </span>
          </div>
        </div>
      )}

      {/* 4. Active Background Attempt Notification */}
      {activeAttempt &&
        (activeAttempt.status === PROJECTION_ATTEMPT_STATUS.QUEUED ||
          activeAttempt.status === PROJECTION_ATTEMPT_STATUS.RUNNING ||
          activeAttempt.status === PROJECTION_ATTEMPT_STATUS.RETRYING) && (
          <div className="graph-banner graph-banner-pending" role="status" aria-live="polite">
            <div className="graph-banner-content">
              <span className="graph-spinner" aria-hidden="true" />
              <span className="graph-banner-text">
                Graph rebuild attempt #{activeAttempt.attempt_number} is{' '}
                <strong>{activeAttempt.status}</strong>...
              </span>
            </div>
          </div>
        )}

      {/* 5. Lifecycle Summary Header */}
      <div className="graph-status-bar">
        <div className="graph-status-badges">
          {publicState === PROJECTION_PUBLIC_STATUS.COMPLETED && (
            <span className="graph-badge graph-badge-success">
              Ready {activeGen ? `(${activeGen.slice(0, 8)})` : ''}
            </span>
          )}
          {publicState === PROJECTION_PUBLIC_STATUS.STALE && (
            <span className="graph-badge graph-badge-warning">
              Historical {activeGen ? `(${activeGen.slice(0, 8)})` : ''}
            </span>
          )}
          {(publicState === PROJECTION_PUBLIC_STATUS.PENDING ||
            publicState === PROJECTION_PUBLIC_STATUS.RUNNING) && (
            <span className="graph-badge graph-badge-pending">
              {publicState}...
            </span>
          )}
          {publicState === PROJECTION_PUBLIC_STATUS.FAILED && (
            <span className="graph-badge graph-badge-error">
              Projection Failed
            </span>
          )}
        </div>

        {/* Action button: Rebuild available when authorized */}
        {canManage && onRebuild && (
          <div className="graph-status-actions">
            <button
              type="button"
              className="graph-btn graph-btn-secondary"
              onClick={onRebuild}
              disabled={isRebuilding || (activeAttempt && activeAttempt.status === PROJECTION_ATTEMPT_STATUS.RUNNING)}
              title="Request a durable re-projection in Neo4j"
            >
              {isRebuilding ? 'Rebuilding...' : 'Rebuild Graph'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

