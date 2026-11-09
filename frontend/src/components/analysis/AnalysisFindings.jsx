import React, { useState, useEffect, useCallback } from 'react';
import { analysisService } from '../../services/analysisService.js';
import { architectureService } from '../../services/architectureService.js';
import {
  getSeverityBadgeClass,
  getStageLabel,
} from '../../contracts/analysisContracts.js';

export default function AnalysisFindings({ projectId, analysisId, publishedVersionId }) {
  // Active sub-tab: 'diagnostics' | 'unresolved' | 'conflicts'
  const [activeCategory, setActiveCategory] = useState('diagnostics');

  // Diagnostics State
  const [diagnostics, setDiagnostics] = useState([]);
  const [diagTotal, setDiagTotal] = useState(0);
  const [diagOffset, setDiagOffset] = useState(0);
  const [diagSeverity, setDiagSeverity] = useState('');
  const [diagLoading, setDiagLoading] = useState(false);
  const [diagError, setDiagError] = useState(null);

  // Unresolved State
  const [unresolved, setUnresolved] = useState([]);
  const [unresolvedTotal, setUnresolvedTotal] = useState(0);
  const [unresolvedOffset, setUnresolvedOffset] = useState(0);
  const [unresolvedLoading, setUnresolvedLoading] = useState(false);
  const [unresolvedError, setUnresolvedError] = useState(null);

  // Conflicts State
  const [conflicts, setConflicts] = useState([]);
  const [conflictsTotal, setConflictsTotal] = useState(0);
  const [conflictsOffset, setConflictsOffset] = useState(0);
  const [conflictsLoading, setConflictsLoading] = useState(false);
  const [conflictsError, setConflictsError] = useState(null);

  const limit = 20;

  // Load Diagnostics
  const loadDiagnostics = useCallback(
    async (nextOffset = 0) => {
      setDiagLoading(true);
      setDiagError(null);
      try {
        const data = await analysisService.listDiagnostics(analysisId, {
          projectId,
          limit,
          offset: nextOffset,
          severity: diagSeverity || undefined,
        });
        const items = Array.isArray(data?.items) ? data.items : [];
        setDiagnostics(items);
        setDiagTotal(typeof data?.total === 'number' ? data.total : items.length);
        setDiagOffset(nextOffset);
      } catch (err) {
        setDiagError(err.message || 'Failed to load diagnostics.');
      } finally {
        setDiagLoading(false);
      }
    },
    [analysisId, projectId, limit, diagSeverity]
  );

  // Load Unresolved
  const loadUnresolved = useCallback(
    async (nextOffset = 0) => {
      if (!publishedVersionId) return;
      setUnresolvedLoading(true);
      setUnresolvedError(null);
      try {
        const data = await architectureService.listUnresolved(publishedVersionId, {
          projectId,
          limit,
          offset: nextOffset,
        });
        const items = Array.isArray(data?.items) ? data.items : [];
        setUnresolved(items);
        setUnresolvedTotal(typeof data?.total === 'number' ? data.total : items.length);
        setUnresolvedOffset(nextOffset);
      } catch (err) {
        setUnresolvedError(err.message || 'Failed to load unresolved relationships.');
      } finally {
        setUnresolvedLoading(false);
      }
    },
    [publishedVersionId, projectId, limit]
  );

  // Load Conflicts
  const loadConflicts = useCallback(
    async (nextOffset = 0) => {
      if (!publishedVersionId) return;
      setConflictsLoading(true);
      setConflictsError(null);
      try {
        const data = await architectureService.listConflicts(publishedVersionId, {
          projectId,
          limit,
          offset: nextOffset,
        });
        const items = Array.isArray(data?.items) ? data.items : [];
        setConflicts(items);
        setConflictsTotal(typeof data?.total === 'number' ? data.total : items.length);
        setConflictsOffset(nextOffset);
      } catch (err) {
        setConflictsError(err.message || 'Failed to load architecture conflicts.');
      } finally {
        setConflictsLoading(false);
      }
    },
    [publishedVersionId, projectId, limit]
  );

  useEffect(() => {
    if (activeCategory === 'diagnostics') {
      loadDiagnostics(0);
    } else if (activeCategory === 'unresolved' && publishedVersionId) {
      loadUnresolved(0);
    } else if (activeCategory === 'conflicts' && publishedVersionId) {
      loadConflicts(0);
    }
  }, [activeCategory, loadDiagnostics, loadUnresolved, loadConflicts, publishedVersionId]);

  return (
    <div className="analysis-findings-card">
      {/* Sub-navigation categories */}
      <div className="findings-subnav" role="tablist" aria-label="Finding Categories">
        <button
          type="button"
          role="tab"
          aria-selected={activeCategory === 'diagnostics'}
          className={`findings-tab-btn ${activeCategory === 'diagnostics' ? 'active' : ''}`}
          onClick={() => setActiveCategory('diagnostics')}
        >
          <span>Diagnostics</span>
          {diagTotal > 0 && <span className="findings-count-badge">{diagTotal}</span>}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeCategory === 'unresolved'}
          className={`findings-tab-btn ${activeCategory === 'unresolved' ? 'active' : ''}`}
          onClick={() => setActiveCategory('unresolved')}
        >
          <span>Unresolved Relationships</span>
          {unresolvedTotal > 0 && <span className="findings-count-badge">{unresolvedTotal}</span>}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeCategory === 'conflicts'}
          className={`findings-tab-btn ${activeCategory === 'conflicts' ? 'active' : ''}`}
          onClick={() => setActiveCategory('conflicts')}
        >
          <span>Architecture Conflicts</span>
          {conflictsTotal > 0 && <span className="findings-count-badge">{conflictsTotal}</span>}
        </button>
      </div>

      {/* 1. Diagnostics Section */}
      {activeCategory === 'diagnostics' && (
        <div className="findings-content-pane">
          {/* Severity Filter Controls */}
          <div className="analyses-controls-bar">
            <div className="analyses-filters-group">
              <label htmlFor="diag-severity-filter" className="analyses-filter-label">
                Severity:
              </label>
              <select
                id="diag-severity-filter"
                className="analyses-select-filter"
                value={diagSeverity}
                onChange={(e) => setDiagSeverity(e.target.value)}
              >
                <option value="">All Severities</option>
                <option value="error">Error</option>
                <option value="warning">Warning</option>
                <option value="info">Info</option>
              </select>
            </div>

            <button
              type="button"
              className="btn-refresh-icon"
              onClick={() => loadDiagnostics(diagOffset)}
              disabled={diagLoading}
              title="Refresh diagnostics"
              aria-label="Refresh diagnostics"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="23 4 23 10 17 10" />
                <polyline points="1 20 1 14 7 14" />
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
              </svg>
            </button>
          </div>

          {diagLoading && (
            <div className="table-loading-wrap" style={{ padding: '2rem 0' }}>
              <span className="btn-spinner" aria-hidden="true" />
              <span>Loading diagnostics...</span>
            </div>
          )}

          {!diagLoading && diagError && (
            <div className="table-error-wrap" role="alert">
              <p>{diagError}</p>
              <button type="button" className="btn-table-view" onClick={() => loadDiagnostics(diagOffset)}>
                Retry
              </button>
            </div>
          )}

          {!diagLoading && !diagError && diagnostics.length === 0 && (
            <div className="analyses-empty-box">
              <p className="analyses-empty-title">No Diagnostics Recorded</p>
              <p className="analyses-empty-desc">
                {diagSeverity
                  ? `No diagnostic records found with severity "${diagSeverity}".`
                  : 'Clean execution without reported parser or lifecycle diagnostics.'}
              </p>
            </div>
          )}

          {!diagLoading && !diagError && diagnostics.length > 0 && (
            <>
              <div className="analyses-table-container">
                <table className="analyses-table">
                  <thead>
                    <tr>
                      <th scope="col">Severity</th>
                      <th scope="col">Code</th>
                      <th scope="col">Stage</th>
                      <th scope="col">Message</th>
                      <th scope="col">File / Location</th>
                    </tr>
                  </thead>
                  <tbody>
                    {diagnostics.map((diag) => (
                      <tr key={diag.id}>
                        <td>
                          <span className={`badge-status ${getSeverityBadgeClass(diag.severity)}`}>
                            {diag.severity?.toUpperCase()}
                          </span>
                        </td>
                        <td className="mono-cell">{diag.code}</td>
                        <td>{getStageLabel(diag.stage)}</td>
                        <td style={{ maxWidth: '320px', wordBreak: 'break-word' }}>
                          {diag.message}
                        </td>
                        <td className="mono-cell" style={{ maxWidth: '240px', wordBreak: 'break-all' }}>
                          {diag.artifact_path ? (
                            <span>
                              {diag.artifact_path}
                              {typeof diag.source_line === 'number' ? `:${diag.source_line}` : ''}
                            </span>
                          ) : (
                            <span style={{ color: '#64748B' }}>—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="history-footer" style={{ marginTop: '1rem' }}>
                <span className="footer-count">
                  Showing {diagOffset + 1}&ndash;{diagOffset + diagnostics.length} of {diagTotal} diagnostics
                </span>
                <div className="repo-pagination-controls" aria-label="Diagnostics pagination">
                  <button
                    type="button"
                    className="repo-pagination-btn"
                    onClick={() => loadDiagnostics(Math.max(0, diagOffset - limit))}
                    disabled={diagOffset === 0 || diagLoading}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className="repo-pagination-btn"
                    onClick={() => loadDiagnostics(diagOffset + limit)}
                    disabled={diagOffset + limit >= diagTotal || diagLoading}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* 2. Unresolved Relationships Section */}
      {activeCategory === 'unresolved' && (
        <div className="findings-content-pane">
          {!publishedVersionId ? (
            <div className="analyses-empty-box">
              <p className="analyses-empty-title">Architecture Model Not Published</p>
              <p className="analyses-empty-desc">
                Unresolved relationship findings are derived during the architecture build stage and published with the final Architecture Version.
              </p>
            </div>
          ) : unresolvedLoading ? (
            <div className="table-loading-wrap" style={{ padding: '2rem 0' }}>
              <span className="btn-spinner" aria-hidden="true" />
              <span>Loading unresolved items...</span>
            </div>
          ) : unresolvedError ? (
            <div className="table-error-wrap" role="alert">
              <p>{unresolvedError}</p>
              <button type="button" className="btn-table-view" onClick={() => loadUnresolved(unresolvedOffset)}>
                Retry
              </button>
            </div>
          ) : unresolved.length === 0 ? (
            <div className="analyses-empty-box">
              <p className="analyses-empty-title">No Unresolved Relationships</p>
              <p className="analyses-empty-desc">
                All relationship targets were successfully matched and resolved in this model version.
              </p>
            </div>
          ) : (
            <>
              <div className="analyses-table-container">
                <table className="analyses-table">
                  <thead>
                    <tr>
                      <th scope="col">Source Logical ID</th>
                      <th scope="col">Kind</th>
                      <th scope="col">Target Descriptor</th>
                      <th scope="col">Reason</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unresolved.map((item) => (
                      <tr key={item.id}>
                        <td className="mono-cell">{item.source_logical_id}</td>
                        <td>{item.kind}</td>
                        <td className="mono-cell">{item.target_descriptor}</td>
                        <td>{item.reason}</td>
                        <td>
                          <span className="badge-status badge-status-default">{item.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="history-footer" style={{ marginTop: '1rem' }}>
                <span className="footer-count">
                  Showing {unresolvedOffset + 1}&ndash;{unresolvedOffset + unresolved.length} of {unresolvedTotal} items
                </span>
                <div className="repo-pagination-controls" aria-label="Unresolved pagination">
                  <button
                    type="button"
                    className="repo-pagination-btn"
                    onClick={() => loadUnresolved(Math.max(0, unresolvedOffset - limit))}
                    disabled={unresolvedOffset === 0 || unresolvedLoading}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className="repo-pagination-btn"
                    onClick={() => loadUnresolved(unresolvedOffset + limit)}
                    disabled={unresolvedOffset + limit >= unresolvedTotal || unresolvedLoading}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* 3. Architecture Conflicts Section */}
      {activeCategory === 'conflicts' && (
        <div className="findings-content-pane">
          {!publishedVersionId ? (
            <div className="analyses-empty-box">
              <p className="analyses-empty-title">Architecture Model Not Published</p>
              <p className="analyses-empty-desc">
                Architecture conflicts are synthesized when the model version is compiled and published.
              </p>
            </div>
          ) : conflictsLoading ? (
            <div className="table-loading-wrap" style={{ padding: '2rem 0' }}>
              <span className="btn-spinner" aria-hidden="true" />
              <span>Loading conflicts...</span>
            </div>
          ) : conflictsError ? (
            <div className="table-error-wrap" role="alert">
              <p>{conflictsError}</p>
              <button type="button" className="btn-table-view" onClick={() => loadConflicts(conflictsOffset)}>
                Retry
              </button>
            </div>
          ) : conflicts.length === 0 ? (
            <div className="analyses-empty-box">
              <p className="analyses-empty-title">No Conflicts Detected</p>
              <p className="analyses-empty-desc">
                No identity or relationship conflicts were detected in this architecture version.
              </p>
            </div>
          ) : (
            <>
              <div className="analyses-table-container">
                <table className="analyses-table">
                  <thead>
                    <tr>
                      <th scope="col">Conflict Type</th>
                      <th scope="col">Subject Key</th>
                      <th scope="col">Evidence Count</th>
                      <th scope="col">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {conflicts.map((item) => (
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
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="history-footer" style={{ marginTop: '1rem' }}>
                <span className="footer-count">
                  Showing {conflictsOffset + 1}&ndash;{conflictsOffset + conflicts.length} of {conflictsTotal} conflicts
                </span>
                <div className="repo-pagination-controls" aria-label="Conflicts pagination">
                  <button
                    type="button"
                    className="repo-pagination-btn"
                    onClick={() => loadConflicts(Math.max(0, conflictsOffset - limit))}
                    disabled={conflictsOffset === 0 || conflictsLoading}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className="repo-pagination-btn"
                    onClick={() => loadConflicts(conflictsOffset + limit)}
                    disabled={conflictsOffset + limit >= conflictsTotal || conflictsLoading}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

