import React, { useState, useEffect, useRef } from 'react';
import { ingestionService } from '../../services/ingestionService.js';

const SUPPORTED_ARCHIVE_EXTENSIONS = ['.zip', '.tar', '.tar.gz', '.tgz'];

function isSupportedArchive(filename) {
  if (!filename) return false;
  const lower = filename.toLowerCase();
  return SUPPORTED_ARCHIVE_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export default function NewIngestionModal({
  isOpen,
  projectId,
  repositoryId,
  onClose,
  onIngestionTriggered,
}) {
  // Source mode: 'github' | 'archive' | 'server_path'
  const [selectedSource, setSelectedSource] = useState('github');

  // GitHub form state
  const [githubUrl, setGithubUrl] = useState('');
  const [githubRef, setGithubRef] = useState('');
  const [githubRevision, setGithubRevision] = useState('');

  // Upload Archive form state
  const [archiveFile, setArchiveFile] = useState(null);
  const [archiveRevision, setArchiveRevision] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  // Server Path form state
  const [serverPath, setServerPath] = useState('');
  const [serverSourceType, setServerSourceType] = useState('archive');
  const [serverRevision, setServerRevision] = useState('');

  // Submission & Error state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setSelectedSource('github');
      setGithubUrl('');
      setGithubRef('');
      setGithubRevision('');
      setArchiveFile(null);
      setArchiveRevision('');
      setDragActive(false);
      setServerPath('');
      setServerSourceType('archive');
      setServerRevision('');
      setError(null);
      setSubmitting(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [isOpen]);

  // Handle keyboard Escape to close modal
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !submitting) {
        handleClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, submitting]);

  if (!isOpen) return null;

  const handleClose = () => {
    if (submitting) return;
    setError(null);
    onClose();
  };

  // Drag & drop handlers for Archive Upload
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (isSupportedArchive(droppedFile.name)) {
        setArchiveFile(droppedFile);
        setError(null);
      } else {
        setError('Unsupported archive format. Supported formats: .zip, .tar, .tar.gz, .tgz');
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (isSupportedArchive(selectedFile.name)) {
        setArchiveFile(selectedFile);
        setError(null);
      } else {
        setError('Unsupported archive format. Supported formats: .zip, .tar, .tar.gz, .tgz');
      }
    }
  };

  // Form submission handler
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;

    setError(null);

    // 1. Validation per source
    if (selectedSource === 'github') {
      const trimmedUrl = githubUrl.trim();
      if (!trimmedUrl) {
        setError('Enter a valid public GitHub repository URL.');
        return;
      }
      if (!trimmedUrl.toLowerCase().includes('github.com')) {
        setError('Please enter a valid GitHub repository URL (e.g. https://github.com/owner/repo).');
        return;
      }
    } else if (selectedSource === 'archive') {
      if (!archiveFile) {
        setError('Please select a repository archive to upload (.zip, .tar, .tar.gz, .tgz).');
        return;
      }
      if (!isSupportedArchive(archiveFile.name)) {
        setError('Unsupported archive format. Supported formats: .zip, .tar, .tar.gz, .tgz');
        return;
      }
    } else if (selectedSource === 'server_path') {
      const trimmedPath = serverPath.trim();
      if (!trimmedPath) {
        setError('Please enter a server filesystem path.');
        return;
      }
    }

    setSubmitting(true);

    try {
      let ingestionResult;

      if (selectedSource === 'github') {
        ingestionResult = await ingestionService.triggerIngestion(projectId, repositoryId, {
          source_type: 'github',
          repository_url: githubUrl.trim(),
          ref: githubRef.trim() || undefined,
          revision_identifier: githubRevision.trim() || undefined,
        });
      } else if (selectedSource === 'archive') {
        ingestionResult = await ingestionService.uploadAndIngest(
          projectId,
          repositoryId,
          archiveFile,
          archiveRevision.trim() || undefined
        );
      } else if (selectedSource === 'server_path') {
        ingestionResult = await ingestionService.triggerIngestion(projectId, repositoryId, {
          source_type: serverSourceType,
          source_reference: serverPath.trim(),
          revision_identifier: serverRevision.trim() || undefined,
        });
      }

      onIngestionTriggered(ingestionResult);
      handleClose();
    } catch (err) {
      // Prefer specific, actionable backend error message when available
      const status = err.status || err.code;
      if (err.message && err.message !== `Request failed with status ${status}`) {
        setError(err.message);
      } else if (status === 403) {
        setError('Access denied. The specified path is outside the allowed server source roots, or permission is restricted.');
      } else if (status === 404) {
        setError('Repository or source not found. Please verify the URL or path exists.');
      } else if (status === 409) {
        setError('A revision with this identifier already exists, or an active ingestion is currently processing.');
      } else if (status === 422) {
        setError('Invalid ingestion parameters. Please check the inputs.');
      } else {
        setError('Failed to trigger repository ingestion.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={handleClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-ingestion-title"
    >
      <div
        className="modal-card modal-card-wide"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-header-icon blue">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </div>
          <div>
            <h2 className="modal-title" id="new-ingestion-title">New Ingestion</h2>
            <p className="modal-subtitle">Choose how to provide the repository source.</p>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={handleClose}
            aria-label="Close dialog"
            disabled={submitting}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Source Selection Cards */}
        <div className="source-selection-grid" role="tablist" aria-label="Ingestion Source Modes">
          {/* 1. GitHub Repository */}
          <button
            type="button"
            role="tab"
            aria-selected={selectedSource === 'github'}
            className={`source-option-card ${selectedSource === 'github' ? 'active' : ''}`}
            onClick={() => {
              if (!submitting) {
                setSelectedSource('github');
                setError(null);
              }
            }}
            disabled={submitting}
          >
            <div className="source-option-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                />
              </svg>
            </div>
            <div className="source-option-text">
              <span className="source-option-title">GitHub Repository</span>
              <span className="source-option-desc">Public GitHub repository URL</span>
            </div>
          </button>

          {/* 2. Upload Archive */}
          <button
            type="button"
            role="tab"
            aria-selected={selectedSource === 'archive'}
            className={`source-option-card ${selectedSource === 'archive' ? 'active' : ''}`}
            onClick={() => {
              if (!submitting) {
                setSelectedSource('archive');
                setError(null);
              }
            }}
            disabled={submitting}
          >
            <div className="source-option-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <div className="source-option-text">
              <span className="source-option-title">Upload Archive</span>
              <span className="source-option-desc">ZIP / TAR / TAR.GZ / TGZ</span>
            </div>
          </button>

          {/* 3. Server Path (Advanced) */}
          <button
            type="button"
            role="tab"
            aria-selected={selectedSource === 'server_path'}
            className={`source-option-card ${selectedSource === 'server_path' ? 'active' : ''}`}
            onClick={() => {
              if (!submitting) {
                setSelectedSource('server_path');
                setError(null);
              }
            }}
            disabled={submitting}
          >
            <div className="source-option-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
                <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
                <line x1="6" y1="6" x2="6.01" y2="6" />
                <line x1="6" y1="18" x2="6.01" y2="18" />
              </svg>
            </div>
            <div className="source-option-text">
              <div className="title-with-badge">
                <span className="source-option-title">Server Path</span>
                <span className="badge-advanced">Advanced</span>
              </div>
              <span className="source-option-desc">Already staged on server</span>
            </div>
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="modal-alert-error" role="alert">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{error}</span>
          </div>
        )}

        {/* Selected Source Form */}
        <form onSubmit={handleSubmit} className="modal-form">
          {/* ================= GITHUB FORM ================= */}
          {selectedSource === 'github' && (
            <div className="source-form-body">
              <div className="info-banner blue">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="16" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
                <span>
                  Connect a public GitHub repository. StackSense will clone and safely inspect the source code.
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="github-url" className="form-label">
                  Repository URL <span className="required-star">*</span>
                </label>
                <input
                  id="github-url"
                  type="url"
                  className="form-input"
                  value={githubUrl}
                  onChange={(e) => setGithubUrl(e.target.value)}
                  placeholder="https://github.com/owner/repository"
                  required
                  disabled={submitting}
                  autoFocus
                />
                <span className="field-hint">
                  Public GitHub repository URL (HTTPS). Private repositories are not currently supported.
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="github-ref" className="form-label">
                  Branch / Ref <span className="optional-tag">(optional)</span>
                </label>
                <input
                  id="github-ref"
                  type="text"
                  className="form-input"
                  value={githubRef}
                  onChange={(e) => setGithubRef(e.target.value)}
                  placeholder="e.g. main, v1.0.0, or commit SHA (defaults to default branch)"
                  maxLength={255}
                  disabled={submitting}
                />
              </div>

              <div className="form-group">
                <label htmlFor="github-revision" className="form-label">
                  Revision Identifier <span className="optional-tag">(optional)</span>
                </label>
                <input
                  id="github-revision"
                  type="text"
                  className="form-input"
                  value={githubRevision}
                  onChange={(e) => setGithubRevision(e.target.value)}
                  placeholder="e.g. v1.0.0 (leave blank to auto-generate)"
                  maxLength={255}
                  disabled={submitting}
                />
                <span className="field-hint">
                  Optional custom revision label. Leave blank to auto-generate from the Git commit or ref.
                </span>
              </div>
            </div>
          )}

          {/* ================= ARCHIVE UPLOAD FORM ================= */}
          {selectedSource === 'archive' && (
            <div className="source-form-body">
              <div className="info-banner blue">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="16" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
                <span>Supported archive formats: .zip, .tar, .tar.gz, .tgz</span>
              </div>

              {/* Drag & Drop File Zone */}
              <div
                className={`file-drop-zone ${dragActive ? 'active' : ''} ${archiveFile ? 'has-file' : ''}`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current && fileInputRef.current.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".zip,.tar,.tar.gz,.tgz,application/zip,application/gzip,application/x-tar,application/x-gzip"
                  style={{ display: 'none' }}
                  onChange={handleFileChange}
                  disabled={submitting}
                />

                <div className="drop-icon-box">
                  {archiveFile ? (
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  )}
                </div>

                {archiveFile ? (
                  <div className="selected-file-info">
                    <p className="file-name">{archiveFile.name}</p>
                    <p className="file-size">{formatFileSize(archiveFile.size)}</p>
                    <span className="file-change-prompt">Click or drag another archive to replace</span>
                  </div>
                ) : (
                  <div className="drop-prompt">
                    <p className="primary-text">Click or drag an archive here</p>
                    <p className="secondary-text">ZIP, TAR, TAR.GZ, or TGZ package containing source files</p>
                  </div>
                )}
              </div>

              <div className="form-group" style={{ marginTop: '1.25rem' }}>
                <label htmlFor="upload-revision" className="form-label">
                  Revision Identifier <span className="optional-tag">(optional)</span>
                </label>
                <input
                  id="upload-revision"
                  type="text"
                  className="form-input"
                  value={archiveRevision}
                  onChange={(e) => setArchiveRevision(e.target.value)}
                  placeholder="e.g. v1.1.0 (leave blank to auto-generate from hash)"
                  maxLength={255}
                  disabled={submitting}
                />
                <span className="field-hint">
                  Leave blank to automatically use the archive&apos;s unique SHA-256 hash.
                </span>
              </div>
            </div>
          )}

          {/* ================= SERVER PATH FORM ================= */}
          {selectedSource === 'server_path' && (
            <div className="source-form-body">
              <div className="info-banner amber">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
                <span>
                  <strong>Server Staging Only:</strong> Enter a path located on the StackSense host server filesystem (within configured allowed source roots).
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="server-source-type" className="form-label">
                  Source Type
                </label>
                <select
                  id="server-source-type"
                  className="form-select"
                  value={serverSourceType}
                  onChange={(e) => setServerSourceType(e.target.value)}
                  disabled={submitting}
                >
                  <option value="archive">Archive file (.zip, .tar, .tar.gz, .tgz)</option>
                  <option value="server_path">Directory Path</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="server-path" className="form-label">
                  Server Path <span className="required-star">*</span>
                </label>
                <input
                  id="server-path"
                  type="text"
                  className="form-input"
                  value={serverPath}
                  onChange={(e) => setServerPath(e.target.value)}
                  placeholder="e.g. /var/stacksense/staged/repository.zip or /var/staged/repo"
                  required
                  disabled={submitting}
                  autoFocus
                />
                <span className="field-hint">
                  Absolute path on the StackSense host server. Path traversal outside configured roots will be rejected.
                </span>
              </div>

              <div className="form-group">
                <label htmlFor="server-revision" className="form-label">
                  Revision Identifier <span className="optional-tag">(optional)</span>
                </label>
                <input
                  id="server-revision"
                  type="text"
                  className="form-input"
                  value={serverRevision}
                  onChange={(e) => setServerRevision(e.target.value)}
                  placeholder="e.g. v1.2.0 (optional)"
                  maxLength={255}
                  disabled={submitting}
                />
              </div>
            </div>
          )}

          {/* Modal Actions */}
          <div className="modal-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={handleClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-gradient-primary"
              disabled={
                submitting ||
                (selectedSource === 'github' && !githubUrl.trim()) ||
                (selectedSource === 'archive' && !archiveFile) ||
                (selectedSource === 'server_path' && !serverPath.trim())
              }
            >
              {submitting ? (
                <>
                  <span className="btn-spinner" aria-hidden="true" />
                  <span>
                    {selectedSource === 'archive'
                      ? 'Uploading & Ingesting...'
                      : 'Starting Ingestion...'}
                  </span>
                </>
              ) : (
                <span>
                  {selectedSource === 'archive'
                    ? 'Upload & Start Ingestion'
                    : 'Start Ingestion'}
                </span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
