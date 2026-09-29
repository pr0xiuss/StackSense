import React, { useState, useEffect, useRef } from 'react';
import { ingestionService } from '../../services/ingestionService.js';

export default function UploadArchiveModal({
  isOpen,
  projectId,
  repositoryId,
  onClose,
  onIngestionTriggered,
}) {
  const [file, setFile] = useState(null);
  const [revisionIdentifier, setRevisionIdentifier] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  // Reset form whenever the modal is opened
  useEffect(() => {
    if (isOpen) {
      setFile(null);
      setRevisionIdentifier('');
      setError(null);
      setDragActive(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleClose = () => {
    setFile(null);
    setRevisionIdentifier('');
    setError(null);
    setDragActive(false);
    onClose();
  };

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
      const isArchive = ['.zip', '.tar', '.tar.gz', '.tgz'].some((ext) => droppedFile.name.toLowerCase().endsWith(ext));
      if (isArchive) {
        setFile(droppedFile);
        setError(null);
      } else {
        setError('Please select a valid repository archive (.zip, .tar, .tar.gz, .tgz).');
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a .zip archive to upload.');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const ingestion = await ingestionService.uploadAndIngest(
        projectId,
        repositoryId,
        file,
        revisionIdentifier.trim() || undefined
      );
      setFile(null);
      setRevisionIdentifier('');
      onIngestionTriggered(ingestion);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to upload archive and trigger ingestion.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={handleClose} role="dialog" aria-modal="true" aria-labelledby="upload-title">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-icon blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <div>
            <h2 className="modal-title" id="upload-title">Upload Repository Archive</h2>
            <p className="modal-subtitle">Upload a .zip source bundle to trigger automated ingestion.</p>
          </div>
          <button type="button" className="modal-close-btn" onClick={handleClose} aria-label="Close modal">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* GitHub Guidance Notice */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.65rem',
          padding: '0.65rem 0.85rem',
          background: 'rgba(56, 189, 248, 0.08)',
          border: '1px solid rgba(56, 189, 248, 0.2)',
          borderRadius: '8px',
          fontSize: '0.82rem',
          color: '#93C5FD',
          marginBottom: '1rem',
          lineHeight: 1.4,
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style={{ flexShrink: 0 }}>
            <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
          </svg>
          <span><strong>Ingesting from GitHub?</strong> Download the repo ZIP from GitHub (<strong>Code &rarr; Download ZIP</strong>) and upload it here.</span>
        </div>

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

        <form onSubmit={handleSubmit} className="modal-form">
          {/* Drag & Drop File Zone */}
          <div
            className={`file-drop-zone ${dragActive ? 'active' : ''} ${file ? 'has-file' : ''}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current && fileInputRef.current.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip,.tar,.tar.gz,.tgz,application/zip,application/gzip,application/x-tar"
              style={{ display: 'none' }}
              onChange={handleFileChange}
              disabled={uploading}
            />

            <div className="drop-icon-box">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>

            {file ? (
              <div className="selected-file-info">
                <p className="file-name">{file.name}</p>
                <p className="file-size">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                <span className="file-change-prompt">Click or drag another .zip to replace</span>
              </div>
            ) : (
              <div className="drop-prompt">
                <p className="primary-text">Click or drag a .zip archive here</p>
                <p className="secondary-text">Standard zip package containing source files</p>
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
              value={revisionIdentifier}
              onChange={(e) => setRevisionIdentifier(e.target.value)}
              placeholder="e.g. v1.1.0 (leave blank to auto-generate from hash)"
              maxLength={255}
              disabled={uploading}
            />
            <span style={{ fontSize: '0.78rem', color: '#64748B', marginTop: '0.35rem', display: 'block' }}>
              Leave blank to automatically use the archive&apos;s unique SHA-256 hash. Revision names must be unique per repository.
            </span>
          </div>

          <div className="modal-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={handleClose}
              disabled={uploading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-gradient-primary"
              disabled={uploading || !file}
            >
              {uploading ? (
                <>
                  <span className="btn-spinner" aria-hidden="true" />
                  <span>Uploading & Ingesting...</span>
                </>
              ) : (
                <span>Upload & Trigger Ingestion</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
