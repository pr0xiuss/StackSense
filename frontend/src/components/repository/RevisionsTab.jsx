import React, { useState, useEffect } from 'react';
import { ingestionService } from '../../services/ingestionService.js';

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  if (!bytes) return '—';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export default function RevisionsTab({
  projectId,
  repositoryId,
  onSelectRevisionForArtifacts,
}) {
  const [revisions, setRevisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const pageSize = 50;

  const loadRevisions = (nextOffset = 0) => {
    let active = true;
    setLoading(true);
    setError(null);
    ingestionService
      .listRevisions(projectId, repositoryId, pageSize, nextOffset)
      .then((data) => {
        if (active) {
          const list = Array.isArray(data) ? data : [];
          setRevisions(list);
          setOffset(nextOffset);
          setHasMore(list.length === pageSize);
        }
      })
      .catch((err) => active && setError(err.message || 'Failed to load repository revisions.'))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  };

  useEffect(() => {
    setSelectedDetail(null);
    return loadRevisions(0);
  }, [projectId, repositoryId]);

  const showDetails = async (revisionId) => {
    setDetailLoading(true);
    setError(null);
    try {
      setSelectedDetail(await ingestionService.getRevision(projectId, repositoryId, revisionId));
    } catch (err) {
      setError(err.message || 'Failed to load revision details.');
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="revisions-tab-content">
      <div className="revisions-card">
        <div className="tab-card-header">
          <div>
            <h3 className="tab-card-title">Repository Revisions</h3>
            <p className="tab-card-subtitle">
              Captured source snapshots created from successful ingestion runs.
            </p>
          </div>
        </div>

        {loading && (
          <div className="table-loading-wrap">
            <span className="btn-spinner" aria-hidden="true" />
            <span>Loading revisions...</span>
          </div>
        )}

        {error && (
          <div className="table-error-wrap">
            <p>{error}</p>
            <button type="button" className="btn-table-view" onClick={() => loadRevisions(offset)}>Retry</button>
          </div>
        )}

        {!loading && !error && revisions.length === 0 && (
          <div className="table-empty-wrap">
            <p>No source revisions recorded yet.</p>
            <span className="empty-subtext">
              Run an archive ingestion on the Ingestion tab to create a captured revision.
            </span>
          </div>
        )}

        {!loading && !error && (revisions.length > 0 || offset > 0) && (
          <div className="history-table-wrapper">
            <table className="history-table">
              <thead>
                <tr>
                  <th scope="col">Revision Identifier</th>
                  <th scope="col">Total Files</th>
                  <th scope="col">Total Size</th>
                  <th scope="col">Source Hash</th>
                  <th scope="col">Created At</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {revisions.map((rev) => (
                  <tr key={rev.id} className="history-row">
                    <td className="cell-id">
                      <div className="revision-tag-badge">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
                          <line x1="7" y1="7" x2="7.01" y2="7" />
                        </svg>
                        <span className="mono-text">{rev.revision_identifier || 'unspecified'}</span>
                      </div>
                    </td>
                    <td className="cell-count">
                      <span>{rev.total_files.toLocaleString()} files</span>
                    </td>
                    <td className="cell-size">
                      <span>{formatBytes(rev.total_bytes)}</span>
                    </td>
                    <td className="cell-hash">
                      <span className="mono-text" title={rev.source_hash}>
                        {rev.source_hash ? rev.source_hash.slice(0, 10) + '...' : '—'}
                      </span>
                    </td>
                    <td className="cell-time">
                      <span>{new Date(rev.created_at).toLocaleString()}</span>
                    </td>
                    <td className="cell-actions">
                      <button
                        type="button"
                        className="btn-table-view"
                        onClick={() => onSelectRevisionForArtifacts(rev)}
                      >
                        View Artifacts &rarr;
                      </button>
                      <button type="button" className="btn-table-view" onClick={() => showDetails(rev.id)}>Details</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && !error && revisions.length > 0 && (
          <div className="history-footer">
            <span className="footer-count">{revisions.length === 0 ? `No revisions on this page (offset ${offset})` : <>Showing {offset + 1}&ndash;{offset + revisions.length} revisions</>}</span>
            <div className="repo-pagination-controls" aria-label="Revision pagination">
              <button type="button" className="repo-pagination-btn" onClick={() => loadRevisions(Math.max(0, offset - pageSize))} disabled={offset === 0}>Previous</button>
              <button type="button" className="repo-pagination-btn" onClick={() => loadRevisions(offset + pageSize)} disabled={!hasMore}>Next</button>
            </div>
          </div>
        )}
        {(detailLoading || selectedDetail) && (
          <div className="revision-detail-panel" aria-live="polite">
            {detailLoading ? <span>Loading revision details…</span> : (
              <>
                <strong>{selectedDetail.revision_identifier}</strong>
                <span>{selectedDetail.total_files.toLocaleString()} files · {formatBytes(selectedDetail.total_bytes)}</span>
                <span className="mono-text">{selectedDetail.source_hash}</span>
                <button type="button" className="btn-table-view" onClick={() => setSelectedDetail(null)}>Close details</button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
