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

  const stateClass = (delivery.state || 'PENDING').toLowerCase();

  return (
    <div className={`delivery-status-banner delivery-status-${stateClass}`} role="region" aria-label="Delivery Status">
      <div className="delivery-header-row">
        <div className="delivery-state-indicator">
          <span className={`status-pill status-${stateClass}`}>
            {delivery.state || 'PENDING'}
          </span>
          <span className="delivery-summary-text">
            Projection Delivery: {delivery.completed_work_items ?? 0} of {delivery.total_work_items ?? 0} items completed
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

      {Array.isArray(delivery.work_summary) && delivery.work_summary.length > 0 && (
        <div className="delivery-items-grid">
          {delivery.work_summary.map((item) => {
            const itemStatusClass = (item.status || 'PENDING').toLowerCase();
            const isFailed = item.status === 'FAILED';

            return (
              <div key={item.work_id || item.kind} className={`delivery-item-card item-${itemStatusClass}`}>
                <div className="delivery-item-header">
                  <span className="item-kind" title={item.kind}>
                    {item.kind ? item.kind.replace(/_/g, ' ') : 'WORK ITEM'}
                  </span>
                  <span className={`status-badge status-${itemStatusClass}`}>
                    {item.status}
                  </span>
                </div>

                {item.error_message && (
                  <p className="item-error-msg" title={item.error_message}>
                    {item.error_message}
                  </p>
                )}

                {isFailed && canRetry && onRetry && (
                  <div className="item-retry-action">
                    <button
                      type="button"
                      className="btn-retry-work"
                      disabled={retrying}
                      onClick={() => onRetry(item.work_id)}
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
