import React, { useState, useEffect, useRef, useCallback } from 'react';
import { repositoryService } from '../../services/repositoryService.js';

const BADGE_COLORS = ['blue', 'red', 'green', 'purple', 'cyan'];

/**
 * Helper to compute friendly relative time string
 */
function formatRelativeTime(dateString) {
  if (!dateString) return 'Never';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

export const PROJECT_ROLES = ['OWNER', 'ADMIN', 'DEVELOPER', 'VIEWER'];

export default function ProjectCard({
  project,
  index = 0,
  onOpenCreateRepo,
  onDeleteProject,
  lastCreatedRepo = null,
}) {
  const [expanded, setExpanded] = useState(index === 0);
  const [repositories, setRepositories] = useState(null);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [reposError, setReposError] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const colorScheme = BADGE_COLORS[index % BADGE_COLORS.length];
  // Role matches ProjectRole contract: OWNER | ADMIN | DEVELOPER | VIEWER
  const rawRole = (project.role || 'OWNER').toUpperCase();
  const role = PROJECT_ROLES.includes(rawRole) ? rawRole : 'VIEWER';
  const canDelete = role === 'OWNER' || role === 'ADMIN';

  const fetchRepositories = useCallback(async () => {
    if (!project?.id) return;
    setLoadingRepos(true);
    setReposError(null);
    try {
      const data = await repositoryService.listRepositories(project.id, 50, 0);
      if (isMountedRef.current) {
        setRepositories(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setReposError(err.message || 'Failed to load repositories.');
      }
    } finally {
      if (isMountedRef.current) {
        setLoadingRepos(false);
      }
    }
  }, [project?.id]);

  // Fetch repositories on demand when expanded
  useEffect(() => {
    if (expanded && repositories === null && !loadingRepos) {
      fetchRepositories();
    }
  }, [expanded, repositories, loadingRepos, fetchRepositories]);

  // If a repository was created for this project, expand and reload
  useEffect(() => {
    if (lastCreatedRepo && lastCreatedRepo.project_id === project.id) {
      setExpanded(true);
      setRepositories((prev) => {
        if (!prev) return [lastCreatedRepo];
        if (prev.some((r) => r.id === lastCreatedRepo.id)) return prev;
        return [lastCreatedRepo, ...prev];
      });
      fetchRepositories();
    }
  }, [lastCreatedRepo, project.id, fetchRepositories]);

  // Close three-dot menu on outside click
  useEffect(() => {
    const handleOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  const repoCount = repositories ? repositories.length : null;

  const toggleExpand = () => {
    const nextState = !expanded;
    setExpanded(nextState);
    if (nextState && repositories === null && !loadingRepos) {
      fetchRepositories();
    }
  };

  const handleRepositoryClick = (repoId) => {
    window.location.hash = `#/projects/${project.id}/repositories/${repoId}`;
  };

  const handleDelete = () => {
    setMenuOpen(false);
    if (window.confirm(`Are you sure you want to delete "${project.name}"? This action cannot be undone.`)) {
      onDeleteProject(project.id);
    }
  };

  return (
    <div className="project-card">
      {/* Card Header */}
      <div className="project-card-header">
        <div className="project-card-identity">
          <div className={`project-cube-icon ${colorScheme}`} aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
              <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
              <line x1="12" y1="22.08" x2="12" y2="12" />
            </svg>
          </div>
          <div className="project-titles">
            <div className="project-title-row">
              <h3 className="project-name">{project.name}</h3>
              <span className={`role-badge role-${role.toLowerCase()}`}>{role}</span>
            </div>
            <p className="project-description">
              {project.description || 'No project description provided.'}
            </p>
          </div>
        </div>

        {/* Three-dot project actions menu */}
        <div className="project-menu-anchor" ref={menuRef}>
          <button
            type="button"
            className="project-menu-btn"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Project actions"
            aria-expanded={menuOpen}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="12" cy="5" r="2" />
              <circle cx="12" cy="12" r="2" />
              <circle cx="12" cy="19" r="2" />
            </svg>
          </button>

          {menuOpen && (
            <div className="project-dropdown-menu" role="menu">
              <button
                type="button"
                className="dropdown-item"
                onClick={() => {
                  setMenuOpen(false);
                  onOpenCreateRepo(project);
                }}
                role="menuitem"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                <span>Add Repository</span>
              </button>
              {canDelete && (
                <>
                  <div className="dropdown-divider" />
                  <button
                    type="button"
                    className="dropdown-item danger"
                    onClick={handleDelete}
                    role="menuitem"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                    <span>Delete Project</span>
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Card Action Strip */}
      <div className="project-action-strip">
        <div className="repo-count-indicator">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
            <line x1="8" y1="21" x2="16" y2="21" />
            <line x1="12" y1="17" x2="12" y2="21" />
          </svg>
          <span>
            {repoCount !== null
              ? `${repoCount} ${repoCount === 1 ? 'repository' : 'repositories'}`
              : 'Repositories'}
          </span>
        </div>

        <button
          type="button"
          className="btn-create-repo"
          onClick={() => onOpenCreateRepo(project)}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>Create Repository</span>
        </button>
      </div>

      {/* Repositories Accordion Area */}
      <div className="repositories-accordion">
        {expanded ? (
          <div className="accordion-expanded">
            <button
              type="button"
              className="accordion-toggle-btn expanded"
              onClick={toggleExpand}
              aria-expanded="true"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="18 15 12 9 6 15" />
              </svg>
              <span>Repositories</span>
            </button>

            {loadingRepos && (
              <div className="accordion-loading">
                <span className="btn-spinner" aria-hidden="true" />
                <span>Loading repositories...</span>
              </div>
            )}

            {reposError && (
              <div className="accordion-error">
                <span>{reposError}</span>
              </div>
            )}

            {!loadingRepos && !reposError && repositories && repositories.length === 0 && (
              <div className="accordion-empty">
                <p>No repositories registered yet.</p>
                <button
                  type="button"
                  className="btn-link-action"
                  onClick={() => onOpenCreateRepo(project)}
                >
                  + Add first repository
                </button>
              </div>
            )}

            {!loadingRepos && repositories && repositories.length > 0 && (
              <div className="repo-table-wrapper">
                <table className="repo-table">
                  <thead>
                    <tr>
                      <th scope="col">Repository</th>
                      <th scope="col">Status</th>
                      <th scope="col">Last ingestion</th>
                      <th scope="col">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {repositories.map((repo) => {
                      const repoStatus = (repo.status || 'Active').toLowerCase();
                      const statusClass =
                        repoStatus === 'completed'
                          ? 'status-completed'
                          : repoStatus === 'processing'
                            ? 'status-processing'
                            : repoStatus === 'failed'
                              ? 'status-failed'
                              : 'status-active';

                      const statusText =
                        repoStatus.charAt(0).toUpperCase() + repoStatus.slice(1);

                      return (
                        <tr key={repo.id} className="repo-row">
                          <td className="repo-name-cell">
                            <span className="repo-name">{repo.name}</span>
                          </td>
                          <td className="repo-status-cell">
                            <div className="status-indicator">
                              <span className={`status-dot ${statusClass}`} aria-hidden="true" />
                              <span className="status-text">{statusText}</span>
                            </div>
                          </td>
                          <td className="repo-time-cell">
                            <span className="time-text">
                              {formatRelativeTime(repo.updated_at || repo.created_at)}
                            </span>
                          </td>
                          <td className="repo-action-cell">
                            <button
                              type="button"
                              className="btn-view-repo"
                              onClick={() => handleRepositoryClick(repo.id)}
                            >
                              View
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <button
            type="button"
            className="accordion-toggle-btn collapsed"
            onClick={toggleExpand}
            aria-expanded="false"
          >
            <div className="toggle-label-wrap">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="6 9 12 15 18 9" />
              </svg>
              <span>View repositories</span>
            </div>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
