import React from 'react';

/**
 * DeliveryStatus Banner Component
 *
 * Visualizes C0 DeliverySummary state across all 6 projection work items:
 * - 4 Diagram projections
 * - 1 Search index projection
 * - 1 Automatic report projection
 *
 * Displays failure reasons, terminal states, and role-guarded manual retry actions.
 */
export function DeliveryStatus({
  delivery,
  loading,
  error,
  retrying,
  retryError,
  onRetry,
  userRole = 'VIEWER',
}) {
  const canRetry = userRole === 'OWNER' || userRole === 'ADMIN';

  if (loading && !delivery) {
    return (
      <div className="delivery-status-banner delivery-status-loading" role="status">
        <span className="spinner-dot" />
        <span>Loading delivery projection status…</span>
      </div>
    );
  }

  if (error && !delivery) {
    return (
      <div className="delivery-status-banner delivery-status-error" role="alert">
        <strong>Delivery Status Unavailable:</strong> {error}
      </div>
    );
  }

  if (!delivery) {
    return null;
  }

  const work = [...(delivery.diagrams || []), delivery.search, delivery.report].filter(Boolean);
  const completed = work.filter((item) => item.state === 'COMPLETED').length;
  const state = work.some((item) => item.state === 'FAILED') ? 'FAILED' :
    work.length && completed === work.length ? 'COMPLETED' : delivery.eligibility || 'PENDING';
  const stateClass = state.toLowerCase();

  return (
    <div className={`delivery-status-banner delivery-status-${stateClass}`} role="region" aria-label="Delivery Status">
      <div className="delivery-header-row">
        <div className="delivery-state-indicator">
          <span className={`status-pill status-${stateClass}`}>
            {state.replaceAll('_', ' ')}
          </span>
          <span className="delivery-summary-text">
            Projection Delivery: {completed} of {work.length} items completed
          </span>
        </div>

        {delivery.receipt_digest && (
          <div className="delivery-digest" title={`Receipt Digest: ${delivery.receipt_digest}`}>
            <code>{delivery.receipt_digest.slice(0, 16)}…</code>
          </div>
        )}
      </div>

      {retryError && (
        <div className="delivery-retry-error" role="alert">
          Retry failed: {retryError}
        </div>
      )}

      {work.length > 0 && (
        <div className="delivery-items-grid">
          {work.map((item) => {
            const itemStatusClass = item.state.toLowerCase();
            const isFailed = item.state === 'FAILED' && item.retry_allowed;

            return (
              <div key={item.work_id || item.kind} className={`delivery-item-card item-${itemStatusClass}`}>
                <div className="delivery-item-header">
                  <span className="item-kind" title={item.kind}>
                    {(item.template || item.kind).replace(/_/g, ' ')}
                  </span>
                  <span className={`status-badge status-${itemStatusClass}`}>
                    {item.state}
                  </span>
                </div>

                {item.reason && (
                  <p className="item-error-msg" title={item.reason}>
                    {item.reason}
                  </p>
                )}

                {isFailed && canRetry && onRetry && (
                  <div className="item-retry-action">
                    <button
                      type="button"
                      className="btn-retry-work"
                      disabled={retrying}
                      onClick={() => onRetry(item).catch(() => {})}
                      title={`Retry ${item.kind}`}
                    >
                      {retrying ? 'Retrying…' : 'Retry Item'}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
export default DeliveryStatus;
