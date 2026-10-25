import React, { useEffect, useState } from 'react';
import { repositoryService } from '../../services/repositoryService.js';

export default function DeleteRepositoryModal({
  isOpen,
  projectId,
  repository,
  onClose,
  onDeleted,
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleKey = (event) => {
      if (event.key === 'Escape' && !loading) onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [isOpen, loading, onClose]);

  if (!isOpen || !repository) return null;

  const handleConfirmDelete = async () => {
    if (loading) return;
    setLoading(true);
    setError(null);

    try {
      await repositoryService.deleteRepository(projectId, repository.id);
      onDeleted(repository.id);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to delete repository. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleBackdropClick = () => {
    if (!loading) {
      onClose();
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-repo-modal-title"
    >
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-icon danger">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" />
              <line x1="14" y1="11" x2="14" y2="17" />
            </svg>
          </div>
          <div>
            <h2 className="modal-title" id="delete-repo-modal-title">Delete Repository</h2>
            <p className="modal-subtitle">Permanently delete this repository registration.</p>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            disabled={loading}
            aria-label="Close modal"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
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

        <div className="delete-modal-body">
          <p className="delete-warning-text">
            Are you sure you want to delete <strong className="delete-repo-target-name">{repository.name}</strong>?
          </p>
          <p className="delete-detail-text">
            This action is destructive and cannot be undone. The repository registration and its metadata will be permanently deleted.
          </p>
        </div>

        <div className="modal-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn-danger-primary"
            onClick={handleConfirmDelete}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="btn-spinner" aria-hidden="true" />
                <span>Deleting...</span>
              </>
            ) : (
              <span>Delete Repository</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
