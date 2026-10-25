import React, { useEffect, useRef, useState } from 'react';
import { PROJECT_ROLES, projectAccessService } from '../../services/projectAccessService.js';
import { userDirectoryService } from '../../services/userDirectoryService.js';

const USERNAME_PREFIX = /^[a-zA-Z0-9_]{2,30}$/;

export default function ProjectMembersModal({ isOpen, project, canManage, currentUserId, onClose, onAccessChanged }) {
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mutationKey, setMutationKey] = useState(null);
  const [usernameQuery, setUsernameQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);
  const [role, setRole] = useState('viewer');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const firstFieldRef = useRef(null);
  const closeRef = useRef(null);
  const searchSequenceRef = useRef(0);

  const loadMembers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await projectAccessService.listAccess(project.id);
      setMembers(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || 'Failed to load project collaborators.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadMembers();
      requestAnimationFrame(() => (canManage ? firstFieldRef.current : closeRef.current)?.focus());
    }
  }, [isOpen, project?.id, canManage]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleKey = (event) => {
      if (event.key === 'Escape' && !mutationKey) onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [isOpen, mutationKey, onClose]);

  useEffect(() => {
    const query = usernameQuery.trim();
    const sequence = ++searchSequenceRef.current;

    if (!isOpen || !canManage || selectedUser?.username === query) {
      setSearchResults([]);
      setSearchLoading(false);
      setSearchError(null);
      return undefined;
    }

    if (query.length < 2) {
      setSearchResults([]);
      setSearchLoading(false);
      setSearchError(null);
      return undefined;
    }

    if (!USERNAME_PREFIX.test(query)) {
      setSearchResults([]);
      setSearchLoading(false);
      setSearchError('Use 2 to 30 letters, numbers, or underscores.');
      return undefined;
    }

    setSearchLoading(true);
    setSearchError(null);
    const timerId = window.setTimeout(async () => {
      try {
        const data = await userDirectoryService.searchByUsername(query);
        if (searchSequenceRef.current !== sequence) return;
        setSearchResults(Array.isArray(data) ? data : []);
      } catch (err) {
        if (searchSequenceRef.current !== sequence) return;
        setSearchResults([]);
        setSearchError(err.message || 'Failed to search users.');
      } finally {
        if (searchSequenceRef.current === sequence) setSearchLoading(false);
      }
    }, 300);

    return () => window.clearTimeout(timerId);
  }, [canManage, isOpen, selectedUser, usernameQuery]);

  if (!isOpen || !project) return null;

  const mutate = async (key, operation, message) => {
    if (mutationKey) return false;
    setMutationKey(key);
    setError(null);
    setSuccess(null);
    try {
      await operation();
      await loadMembers();
      setSuccess(message);
      onAccessChanged?.();
      return true;
    } catch (err) {
      setError(err.message || 'Project access update failed.');
      return false;
    } finally {
      setMutationKey(null);
    }
  };

  const handleGrant = async (event) => {
    event.preventDefault();
    if (!selectedUser) {
      setError('Select a user from the username search results.');
      return;
    }
    const succeeded = await mutate(
      `grant:${selectedUser.id}`,
      () => projectAccessService.grantAccess(project.id, selectedUser.id, role),
      'Collaborator added.'
    );
    if (succeeded) {
      setUsernameQuery('');
      setSelectedUser(null);
      setRole('viewer');
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="project-members-title" onClick={() => !mutationKey && onClose()}>
      <div className="modal-card modal-card-wide" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-icon purple" aria-hidden="true">👥</div>
          <div>
            <h2 className="modal-title" id="project-members-title">Project Collaborators</h2>
            <p className="modal-subtitle">{project.name} · search and manage collaborators by username.</p>
          </div>
          <button ref={closeRef} type="button" className="modal-close-btn" onClick={onClose} disabled={Boolean(mutationKey)} aria-label="Close modal">×</button>
        </div>

        {error && <div className="modal-alert-error" role="alert"><span>{error}</span><button type="button" className="btn-link-action" onClick={loadMembers}>Retry</button></div>}
        {success && <div className="repo-feedback-banner success" role="status">{success}</div>}

        {canManage && (
          <form className="collaborator-form" onSubmit={handleGrant}>
            <div className="form-group collaborator-search-field">
              <label className="form-label" htmlFor="collaborator-username">Username</label>
              <div className="collaborator-search-control">
                <input
                  ref={firstFieldRef}
                  id="collaborator-username"
                  className="form-input"
                  value={usernameQuery}
                  onChange={(event) => {
                    setUsernameQuery(event.target.value);
                    setSelectedUser(null);
                    setError(null);
                  }}
                  placeholder="Search username"
                  autoComplete="off"
                  aria-autocomplete="list"
                  aria-controls="collaborator-user-results"
                  aria-expanded={searchLoading || searchResults.length > 0 || Boolean(searchError)}
                  disabled={Boolean(mutationKey)}
                />
                {(searchLoading || searchResults.length > 0 || searchError || (USERNAME_PREFIX.test(usernameQuery.trim()) && !selectedUser)) && (
                  <div id="collaborator-user-results" className="collaborator-search-results" role="listbox" aria-label="Username search results">
                    {searchLoading ? (
                      <div className="collaborator-search-status"><span className="btn-spinner" /> Searching...</div>
                    ) : searchError ? (
                      <div className="collaborator-search-status error" role="alert">{searchError}</div>
                    ) : searchResults.length === 0 ? (
                      <div className="collaborator-search-status">No matching active users.</div>
                    ) : searchResults.map((user) => {
                      const alreadyAdded = members.some((member) => member.user_id === user.id);
                      return (
                        <button
                          key={user.id}
                          type="button"
                          role="option"
                          aria-selected={selectedUser?.id === user.id}
                          className="collaborator-search-option"
                          disabled={alreadyAdded || Boolean(mutationKey)}
                          onClick={() => {
                            setSelectedUser(user);
                            setUsernameQuery(user.username);
                            setSearchResults([]);
                            setSearchError(null);
                          }}
                        >
                          <span>@{user.username}</span>
                          {alreadyAdded && <span className="collaborator-search-note">Already added</span>}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="collaborator-role">Role</label>
              <select id="collaborator-role" className="form-input" value={role} onChange={(event) => setRole(event.target.value)} disabled={Boolean(mutationKey)}>
                {PROJECT_ROLES.map((value) => <option key={value} value={value}>{value.toUpperCase()}</option>)}
              </select>
            </div>
            <button type="submit" className="btn-gradient-primary" disabled={Boolean(mutationKey) || !selectedUser}>Add Collaborator</button>
          </form>
        )}

        {loading ? (
          <div className="accordion-loading"><span className="btn-spinner" /> Loading collaborators...</div>
        ) : members.length === 0 ? (
          <div className="accordion-empty"><p>No access records found.</p></div>
        ) : (
          <div className="collaborator-list">
            {members.map((member) => {
              const isCurrentUser = member.user_id === currentUserId;
              const username = member.username || 'Unknown user';
              return (
                <div className="collaborator-row" key={member.user_id}>
                  <div><span className="collaborator-username">@{username}</span>{isCurrentUser && <span className="current-user-tag">You</span>}</div>
                  {canManage && !isCurrentUser ? (
                    <div className="collaborator-actions">
                      <select
                        className="form-input compact-select"
                        value={member.role}
                        disabled={Boolean(mutationKey)}
                        aria-label={`Role for ${username}`}
                        onChange={(event) => mutate(`role:${member.user_id}`, () => projectAccessService.changeRole(project.id, member.user_id, event.target.value), 'Collaborator role updated.')}
                      >
                        {PROJECT_ROLES.map((value) => <option key={value} value={value}>{value.toUpperCase()}</option>)}
                      </select>
                      <button
                        type="button"
                        className="btn-danger-text"
                        disabled={Boolean(mutationKey)}
                        onClick={() => {
                          if (window.confirm(`Revoke access for @${username}?`)) {
                            mutate(`revoke:${member.user_id}`, () => projectAccessService.revokeAccess(project.id, member.user_id), 'Collaborator access revoked.');
                          }
                        }}
                      >Revoke</button>
                    </div>
                  ) : <span className={`role-badge role-${member.role}`} aria-label={isCurrentUser ? 'Your project role' : undefined}>{member.role.toUpperCase()}</span>}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
