import React, { useEffect, useRef, useState } from 'react';

export default function MetadataEditModal({
  isOpen,
  entity,
  entityLabel,
  onClose,
  onSave,
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const nameRef = useRef(null);

  useEffect(() => {
    if (!isOpen || !entity) return;
    setName(entity.name || '');
    setDescription(entity.description || '');
    setError(null);
    requestAnimationFrame(() => nameRef.current?.focus());
  }, [isOpen, entity]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleKey = (event) => {
      if (event.key === 'Escape' && !loading) onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [isOpen, loading, onClose]);

  if (!isOpen || !entity) return null;

  const handleSubmit = async (event) => {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError(`${entityLabel} name is required.`);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await onSave({
        name: trimmedName,
        description: description.trim() || null,
      });
      onClose();
    } catch (err) {
      setError(err.message || `Failed to update ${entityLabel.toLowerCase()}.`);
    } finally {
      setLoading(false);
    }
  };

  const titleId = `edit-${entityLabel.toLowerCase()}-title`;
  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={() => !loading && onClose()}
    >
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-icon blue" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" />
            </svg>
          </div>
          <div>
            <h2 className="modal-title" id={titleId}>Edit {entityLabel}</h2>
            <p className="modal-subtitle">Update the name and description.</p>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} disabled={loading} aria-label="Close modal">×</button>
        </div>

        {error && <div className="modal-alert-error" role="alert"><span>{error}</span></div>}

        <form className="modal-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor={`${titleId}-name`}>{entityLabel} Name <span className="required-star">*</span></label>
            <input
              ref={nameRef}
              id={`${titleId}-name`}
              className="form-input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={255}
              disabled={loading}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor={`${titleId}-description`}>Description <span className="optional-tag">(optional)</span></label>
            <textarea
              id={`${titleId}-description`}
              className="form-textarea"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={2000}
              rows={3}
              disabled={loading}
            />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>Cancel</button>
            <button type="submit" className="btn-gradient-primary" disabled={loading || !name.trim()}>
              {loading ? <><span className="btn-spinner" aria-hidden="true" /> Saving...</> : `Save ${entityLabel}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
