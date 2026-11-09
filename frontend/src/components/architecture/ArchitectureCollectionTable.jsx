import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { architectureService } from '../../services/architectureService.js';
import {
  getEntityKindLabel,
  getRelationshipKindLabel,
  getEvidenceStrengthBadgeClass,
  getEvidencePolarityBadgeClass,
} from '../../contracts/architectureContracts.js';

export default function ArchitectureCollectionTable({
  type,
  versionId,
  projectId,
  selectedEntityForEvidence = null,
  onSelectEntity,
  onClearEntityFilter,
}) {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filter states
  const [kindFilter, setKindFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [pageSearch, setPageSearch] = useState('');

  const limit = 25;

  const loadData = useCallback(
    async (nextOffset = 0) => {
      if (!versionId || !projectId) return;

      setLoading(true);
      setError(null);

      try {
        let res = null;
        if (type === 'entities') {
          res = await architectureService.listEntities(versionId, {
            projectId,
            limit,
            offset: nextOffset,
            kind: kindFilter || undefined,
            status: statusFilter || undefined,
          });
        } else if (type === 'relationships') {
          res = await architectureService.listRelationships(versionId, {
            projectId,
            limit,
            offset: nextOffset,
            kind: kindFilter || undefined,
            status: statusFilter || undefined,
          });
        } else if (type === 'evidence') {
          res = await architectureService.listEvidence(versionId, {
            projectId,
            limit,
            offset: nextOffset,
            entityId: selectedEntityForEvidence?.id || undefined,
          });
        } else if (type === 'unresolved') {
          res = await architectureService.listUnresolved(versionId, {
            projectId,
            limit,
            offset: nextOffset,
          });
        } else if (type === 'conflicts') {
          res = await architectureService.listConflicts(versionId, {
            projectId,
            limit,
            offset: nextOffset,
          });
        }

        const list = Array.isArray(res?.items) ? res.items : [];
        setItems(list);
        setTotal(typeof res?.total === 'number' ? res.total : list.length);
        setOffset(nextOffset);
      } catch (err) {
        setError(err.message || `Failed to load ${type} collection.`);
      } finally {
        setLoading(false);
      }
    },
    [type, versionId, projectId, limit, kindFilter, statusFilter, selectedEntityForEvidence]
  );

  useEffect(() => {
    setOffset(0);
    setPageSearch('');
    loadData(0);
  }, [loadData]);

  // Client-side search within loaded page
  const filteredItems = useMemo(() => {
    if (!pageSearch.trim()) return items;
    const q = pageSearch.toLowerCase();
    return items.filter((item) => {
      const str = JSON.stringify(item).toLowerCase();
      return str.includes(q);
    });
  }, [items, pageSearch]);

  const hasNext = offset + limit < total;
  const hasPrev = offset > 0;

  return (
    <div className="arch-table-card">
      {/* Table Control Bar */}
      <div className="analyses-controls-bar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Active Entity Filter for Evidence */}
          {type === 'evidence' && selectedEntityForEvidence && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                background: 'rgba(56, 189, 248, 0.15)',
                border: '1px solid rgba(56, 189, 248, 0.35)',
                borderRadius: '6px',
                padding: '0.35rem 0.65rem',
                fontSize: '0.8rem',
                color: '#38BDF8',
              }}
            >
              <span>Entity: {selectedEntityForEvidence.name || selectedEntityForEvidence.logical_id}</span>
              <button
                type="button"
                onClick={onClearEntityFilter}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#38BDF8',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                }}
                aria-label="Clear entity filter"
              >
                ×
              </button>
            </div>
          )}

          {/* Kind Filter for Entities and Relationships */}
          {(type === 'entities' || type === 'relationships') && (
            <div className="analyses-filters-group">
              <label htmlFor="arch-kind-filter" className="analyses-filter-label">
                Kind:
              </label>
              <select
                id="arch-kind-filter"
                className="analyses-select-filter"
                value={kindFilter}
                onChange={(e) => setKindFilter(e.target.value)}
              >
                <option value="">All Kinds</option>
                {type === 'entities' ? (
                  <>
                    <option value="service">Service</option>
                    <option value="component">Component</option>
                    <option value="module">Module</option>
                    <option value="database">Database</option>
                    <option value="queue">Queue</option>
                    <option value="api_endpoint">API Endpoint</option>
                    <option value="external_system">External System</option>
                    <option value="data_store">Data Store</option>
                  </>
                ) : (
                  <>
                    <option value="calls">Calls</option>
                    <option value="reads_from">Reads From</option>
                    <option value="writes_to">Writes To</option>
                    <option value="subscribes_to">Subscribes To</option>
                    <option value="publishes_to">Publishes To</option>
                    <option value="depends_on">Depends On</option>
                    <option value="includes">Includes</option>
                  </>
                )}
              </select>
            </div>
          )}

          {/* Status Filter for Entities and Relationships */}
          {(type === 'entities' || type === 'relationships') && (
            <div className="analyses-filters-group">
              <label htmlFor="arch-status-filter" className="analyses-filter-label">
                Status:
              </label>
              <select
                id="arch-status-filter"
                className="analyses-select-filter"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">All Statuses</option>
                <option value="active">Active</option>
                <option value="deprecated">Deprecated</option>
              </select>
            </div>
          )}
        </div>

        {/* Client-side Search on current page */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <input
            type="search"
            className="arch-search-input"
            placeholder={`Filter loaded ${type}…`}
            value={pageSearch}
            onChange={(e) => setPageSearch(e.target.value)}
            aria-label={`Search loaded ${type}`}
          />

          <button
            type="button"
            className="btn-refresh-icon"
            onClick={() => loadData(offset)}
            disabled={loading}
            title="Refresh table"
            aria-label="Refresh collection table"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          </button>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="table-loading-wrap" style={{ padding: '3rem 0' }}>
          <span className="btn-spinner" aria-hidden="true" />
          <span>Loading {type}...</span>
        </div>
      )}

      {/* Error State */}
      {!loading && error && (
        <div className="table-error-wrap" role="alert">
          <p>{error}</p>
          <button type="button" className="btn-table-view" onClick={() => loadData(offset)}>
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && filteredItems.length === 0 && (
        <div className="analyses-empty-box">
          <p className="analyses-empty-title">No {type} found</p>
          <p className="analyses-empty-desc">
            {pageSearch
              ? `No records on this page match "${pageSearch}".`
              : `No ${type} records available for this query.`}
          </p>
        </div>
      )}

      {/* Data Table */}
      {!loading && !error && filteredItems.length > 0 && (
        <>
          <div className="analyses-table-container">
            <table className="analyses-table">
              {/* Table Headers */}
              {type === 'entities' && (
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Logical ID</th>
                    <th scope="col">Kind</th>
                    <th scope="col">Status</th>
                    <th scope="col">Namespace</th>
                    <th scope="col">Action</th>
                  </tr>
                </thead>
              )}

              {type === 'relationships' && (
                <thead>
                  <tr>
                    <th scope="col">Kind</th>
                    <th scope="col">Source Logical ID</th>
                    <th scope="col">Target Logical ID</th>
                    <th scope="col">Status</th>
                    <th scope="col">Evidence</th>
                  </tr>
                </thead>
              )}

              {type === 'evidence' && (
                <thead>
                  <tr>
                    <th scope="col">Record Type</th>
                    <th scope="col">Source Path</th>
                    <th scope="col">Strength</th>
                    <th scope="col">Polarity</th>
                    <th scope="col">Producer</th>
                  </tr>
                </thead>
              )}

              {type === 'unresolved' && (
                <thead>
                  <tr>
                    <th scope="col">Kind</th>
                    <th scope="col">Source Logical ID</th>
                    <th scope="col">Target Descriptor</th>
                    <th scope="col">Reason</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
              )}

              {type === 'conflicts' && (
                <thead>
                  <tr>
                    <th scope="col">Conflict Type</th>
                    <th scope="col">Subject Key</th>
                    <th scope="col">Evidence</th>
                    <th scope="col">Details</th>
                  </tr>
                </thead>
              )}

              {/* Table Rows */}
              <tbody>
                {filteredItems.map((item) => {
                  if (type === 'entities') {
                    return (
                      <tr key={item.id}>
                        <td style={{ fontWeight: 600 }}>{item.name || item.logical_id}</td>
                        <td className="mono-cell">{item.logical_id}</td>
                        <td>
                          <span className="badge-status badge-status-default">
                            {getEntityKindLabel(item.kind)}
                          </span>
                        </td>
                        <td>
                          <span className="badge-status badge-status-completed">
                            {item.status || 'Active'}
                          </span>
                        </td>
                        <td>
                          {Array.isArray(item.namespace) ? item.namespace.join(' / ') : item.namespace || 'Root'}
                        </td>
                        <td>
                          {onSelectEntity && (
                            <button
                              type="button"
                              className="btn-table-view"
                              onClick={() => onSelectEntity(item)}
                            >
                              Inspect &rarr;
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  }

                  if (type === 'relationships') {
                    return (
                      <tr key={item.id}>
                        <td>
                          <span className="badge-status badge-status-default">
                            {getRelationshipKindLabel(item.kind)}
                          </span>
                        </td>
                        <td className="mono-cell">{item.source_logical_id}</td>
                        <td className="mono-cell">{item.target_logical_id}</td>
                        <td>{item.status || 'Active'}</td>
                        <td>{Array.isArray(item.evidence_ids) ? item.evidence_ids.length : 0} records</td>
                      </tr>
                    );
                  }

                  if (type === 'evidence') {
                    return (
                      <tr key={item.id}>
                        <td className="mono-cell">{item.source_record_type}</td>
                        <td className="mono-cell" style={{ maxWidth: '280px', wordBreak: 'break-all' }}>
                          {item.path}
                        </td>
                        <td>
                          <span className={`badge-status ${getEvidenceStrengthBadgeClass(item.strength)}`}>
                            {item.strength?.toUpperCase()}
                          </span>
                        </td>
                        <td>
                          <span className={`badge-status ${getEvidencePolarityBadgeClass(item.polarity)}`}>
                            {item.polarity?.toUpperCase()}
                          </span>
                        </td>
                        <td>{item.producer_id || 'Static Analyzer'}</td>
                      </tr>
                    );
                  }

                  if (type === 'unresolved') {
                    return (
                      <tr key={item.id}>
                        <td>{item.kind}</td>
                        <td className="mono-cell">{item.source_logical_id}</td>
                        <td className="mono-cell">{item.target_descriptor}</td>
                        <td>{item.reason}</td>
                        <td>
                          <span className="badge-status badge-status-default">{item.status}</span>
                        </td>
                      </tr>
                    );
                  }

                  if (type === 'conflicts') {
                    return (
                      <tr key={item.id}>
                        <td>
                          <span className="badge-severity-warning">{item.conflict_type}</span>
                        </td>
                        <td className="mono-cell">{item.subject_key}</td>
                        <td>{Array.isArray(item.evidence_ids) ? item.evidence_ids.length : 0}</td>
                        <td className="mono-cell" style={{ maxWidth: '300px', fontSize: '0.75rem' }}>
                          {item.details ? JSON.stringify(item.details) : '—'}
                        </td>
                      </tr>
                    );
                  }

                  return null;
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="history-footer" style={{ marginTop: '1rem' }}>
            <span className="footer-count">
              Showing {offset + 1}&ndash;{offset + filteredItems.length} of {total} {type}
            </span>
            <div className="repo-pagination-controls" aria-label={`${type} pagination`}>
              <button
                type="button"
                className="repo-pagination-btn"
                onClick={() => loadData(Math.max(0, offset - limit))}
                disabled={!hasPrev || loading}
              >
                Previous
              </button>
              <button
                type="button"
                className="repo-pagination-btn"
                onClick={() => loadData(offset + limit)}
                disabled={!hasNext || loading}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

