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

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    ingestionService
      .listRevisions(projectId, repositoryId, 50, 0)
      .then((data) => {
        if (isMounted) {
          setRevisions(Array.isArray(data) ? data : []);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load repository revisions.');
        }
      })
      .finally(() => {
        if (isMounted) {
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [projectId, repositoryId]);

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

        {!loading && !error && revisions.length > 0 && (
          <div className="history-table-wrapper">
            <table className="history-table">
              <thead>
                <tr>
                  <th scope="col">Revision Identifier</th>
                  <th scope="col">Total Files</th>
                  <th scope="col">Total Size</th>
                  <th scope="col">Source Hash</th>
                  <th scope="col">Created At</th>
                  <th scope="col">Artifacts</th>
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
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
