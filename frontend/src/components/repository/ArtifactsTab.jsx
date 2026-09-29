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

export default function ArtifactsTab({
  projectId,
  repositoryId,
  selectedRevision,
  onSelectRevision,
}) {
  const [revisions, setRevisions] = useState([]);
  const [loadingRevisions, setLoadingRevisions] = useState(true);

  const [artifacts, setArtifacts] = useState([]);
  const [loadingArtifacts, setLoadingArtifacts] = useState(false);
  const [error, setError] = useState(null);

  // Load revisions on mount to populate revision selector dropdown
  useEffect(() => {
    let isMounted = true;
    setLoadingRevisions(true);
    ingestionService
      .listRevisions(projectId, repositoryId, 50, 0)
      .then((data) => {
        if (isMounted) {
          const list = Array.isArray(data) ? data : [];
          setRevisions(list);
          if (!selectedRevision && list.length > 0) {
            onSelectRevision(list[0]);
          }
        }
      })
      .catch(() => {})
      .finally(() => {
        if (isMounted) setLoadingRevisions(false);
      });

    return () => {
      isMounted = false;
    };
  }, [projectId, repositoryId, selectedRevision, onSelectRevision]);

  // Load artifacts whenever selectedRevision changes
  useEffect(() => {
    let isMounted = true;
    if (!selectedRevision?.id) {
      setArtifacts([]);
      return;
    }

    setLoadingArtifacts(true);
    setError(null);

    ingestionService
      .listArtifacts(projectId, repositoryId, selectedRevision.id, 50, 0)
      .then((data) => {
        if (isMounted) {
          setArtifacts(Array.isArray(data) ? data : []);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load artifacts for this revision.');
        }
      })
      .finally(() => {
        if (isMounted) setLoadingArtifacts(false);
      });

    return () => {
      isMounted = false;
    };
  }, [projectId, repositoryId, selectedRevision]);

  const handleRevisionChange = (e) => {
    const revId = e.target.value;
    const target = revisions.find((r) => r.id === revId);
    if (target) {
      onSelectRevision(target);
    }
  };

  return (
    <div className="artifacts-tab-content">
      <div className="artifacts-card">
        {/* Revision Selector Bar */}
        <div className="artifacts-control-bar">
          <div className="revision-select-group">
            <label htmlFor="artifact-revision-select" className="revision-select-label">
              Artifacts for Revision:
            </label>
            {loadingRevisions ? (
              <span className="loading-inline">Loading revisions...</span>
            ) : revisions.length > 0 ? (
              <select
                id="artifact-revision-select"
                className="revision-dropdown"
                value={selectedRevision?.id || ''}
                onChange={handleRevisionChange}
              >
                {!selectedRevision && (
                  <option value="" disabled>
                    Select a revision...
                  </option>
                )}
                {revisions.map((rev) => (
                  <option key={rev.id} value={rev.id}>
                    {rev.revision_identifier} ({new Date(rev.created_at).toLocaleDateString()})
                  </option>
                ))}
              </select>
            ) : (
              <span className="no-revisions-inline">No revisions available yet</span>
            )}
          </div>

          {selectedRevision && (
            <div className="revision-meta-capsule">
              <span className="meta-capsule-label">Total Files:</span>
              <span className="meta-capsule-val">{selectedRevision.total_files}</span>
              <span className="meta-divider">|</span>
              <span className="meta-capsule-label">Total Size:</span>
              <span className="meta-capsule-val">{formatBytes(selectedRevision.total_bytes)}</span>
            </div>
          )}
        </div>

        {loadingArtifacts && (
          <div className="table-loading-wrap">
            <span className="btn-spinner" aria-hidden="true" />
            <span>Discovering artifacts for revision...</span>
          </div>
        )}

        {error && (
          <div className="table-error-wrap">
            <p>{error}</p>
          </div>
        )}

        {!loadingArtifacts && !error && revisions.length === 0 && (
          <div className="table-empty-wrap">
            <p>No repository revisions found.</p>
            <span className="empty-subtext">
              Ingest an archive to create a captured revision before inspecting artifacts.
            </span>
          </div>
        )}

        {!loadingArtifacts && !error && selectedRevision && artifacts.length === 0 && (
          <div className="table-empty-wrap">
            <p>No artifacts discovered for revision {selectedRevision.revision_identifier}.</p>
          </div>
        )}

        {!loadingArtifacts && !error && artifacts.length > 0 && (
          <div className="history-table-wrapper">
            <table className="history-table">
              <thead>
                <tr>
                  <th scope="col">File Path</th>
                  <th scope="col">Size</th>
                  <th scope="col">Category</th>
                  <th scope="col">Support Level</th>
                  <th scope="col">Content Hash</th>
                </tr>
              </thead>
              <tbody>
                {artifacts.map((art) => (
                  <tr key={art.id} className="history-row">
                    <td className="cell-path">
                      <span className="mono-text code-path">{art.path}</span>
                    </td>
                    <td className="cell-size">
                      <span>{formatBytes(art.size_bytes)}</span>
                    </td>
                    <td className="cell-category">
                      <span className="category-pill">{art.category || 'source_code'}</span>
                    </td>
                    <td className="cell-support">
                      <span className="support-badge">{art.support_level || 'SUPPORTED'}</span>
                    </td>
                    <td className="cell-hash">
                      <span className="mono-text" title={art.content_hash}>
                        {art.content_hash ? art.content_hash.slice(0, 10) + '...' : '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {artifacts.length > 0 && (
          <div className="history-footer">
            <span className="footer-count">
              Showing {artifacts.length} {artifacts.length === 1 ? 'artifact' : 'artifacts'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
