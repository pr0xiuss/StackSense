import React, { useState } from 'react';
import { repositoryService } from '../../services/repositoryService.js';

export default function CreateRepositoryModal({
  isOpen,
  projectId,
  projectName,
  onClose,
  onRepositoryCreated,
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Repository name is required.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const newRepo = await repositoryService.createRepository(projectId, {
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setName('');
      setDescription('');
      onRepositoryCreated(newRepo);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to register repository. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="modal-repo-title">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-icon purple">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="16 18 22 12 16 6" />
              <polyline points="8 6 2 12 8 18" />
            </svg>
          </div>
          <div>
            <h2 className="modal-title" id="modal-repo-title">Add Repository</h2>
            <p className="modal-subtitle">
              Register a repository under <strong style={{ color: '#F8FAFC' }}>{projectName}</strong>.
            </p>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close modal">
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

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label htmlFor="repo-name" className="form-label">
              Repository Name <span className="required-star">*</span>
            </label>
            <input
              id="repo-name"
              type="text"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. backend-api or service-auth"
              maxLength={255}
              required
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="repo-desc" className="form-label">
              Description <span className="optional-tag">(optional)</span>
            </label>
            <textarea
              id="repo-desc"
              className="form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Main backend API service and database models..."
              maxLength={2000}
              rows={3}
              disabled={loading}
            />
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
              type="submit"
              className="btn-gradient-primary"
              disabled={loading || !name.trim()}
            >
              {loading ? (
                <>
                  <span className="btn-spinner" aria-hidden="true" />
                  <span>Registering...</span>
                </>
              ) : (
                <span>Register Repository</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
