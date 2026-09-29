import React, { useState, useEffect, useCallback } from 'react';
import DashboardHeader from '../components/dashboard/DashboardHeader.jsx';
import ProjectCard from '../components/dashboard/ProjectCard.jsx';
import CreateProjectModal from '../components/dashboard/CreateProjectModal.jsx';
import CreateRepositoryModal from '../components/dashboard/CreateRepositoryModal.jsx';
import { projectService } from '../services/projectService.js';

const PAGE_LIMIT = 50;

export default function ProjectsDashboardPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  // Modals state
  const [createProjectOpen, setCreateProjectOpen] = useState(false);
  const [createRepoTarget, setCreateRepoTarget] = useState(null); // project object

  const fetchProjects = useCallback(async (currentOffset = 0, append = false) => {
    if (append) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setError(null);
    }

    try {
      const data = await projectService.listProjects(PAGE_LIMIT, currentOffset);
      const list = Array.isArray(data) ? data : [];

      if (append) {
        setProjects((prev) => [...prev, ...list]);
      } else {
        setProjects(list);
      }

      setOffset(currentOffset);
      setHasMore(list.length === PAGE_LIMIT);
    } catch (err) {
      setError(err.message || 'Failed to load projects. Please check your connection.');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects(0);
  }, [fetchProjects]);

  const handleLoadMore = () => {
    const nextOffset = offset + PAGE_LIMIT;
    fetchProjects(nextOffset, true);
  };

  const handleProjectCreated = (newProject) => {
    setProjects((prev) => [newProject, ...prev]);
  };

  const handleDeleteProject = async (projectId) => {
    try {
      await projectService.deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
    } catch (err) {
      alert(err.message || 'Failed to delete project.');
    }
  };

  const handleOpenCreateRepo = (project) => {
    setCreateRepoTarget(project);
  };

  const handleRepositoryCreated = (newRepo) => {
    // Force refresh or trigger accordion update by reloading projects if needed,
    // or notify user
    setCreateRepoTarget(null);
  };

  return (
    <div className="dashboard-page-wrapper">
      <DashboardHeader />

      <main className="dashboard-content container">
        {/* Page Title & Action Banner */}
        <section className="dashboard-banner">
          <div className="banner-titles">
            <h1 className="dashboard-title">Projects</h1>
            <p className="dashboard-subtitle">Manage your projects and repositories.</p>
          </div>
          <button
            type="button"
            className="btn-create-project-primary"
            onClick={() => setCreateProjectOpen(true)}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Create Project</span>
          </button>
        </section>

        {/* Loading State */}
        {loading && (
          <div className="dashboard-skeleton-grid" aria-label="Loading projects">
            {[1, 2, 3, 4].map((n) => (
              <div key={n} className="skeleton-project-card" />
            ))}
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="dashboard-error-card" role="alert">
            <div className="error-icon-box">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <div className="error-content">
              <h3>Unable to load projects</h3>
              <p>{error}</p>
            </div>
            <button
              type="button"
              className="btn-retry"
              onClick={() => fetchProjects(0)}
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && projects.length === 0 && (
          <div className="dashboard-empty-card">
            <div className="empty-icon-box">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                <line x1="12" y1="22.08" x2="12" y2="12" />
              </svg>
            </div>
            <h2 className="empty-title">No projects yet</h2>
            <p className="empty-subtitle">
              Get started by creating your first project to register repositories and run architecture ingestion.
            </p>
            <button
              type="button"
              className="btn-create-project-primary"
              onClick={() => setCreateProjectOpen(true)}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>Create Project</span>
            </button>
          </div>
        )}

        {/* Projects Grid */}
        {!loading && !error && projects.length > 0 && (
          <>
            <div className="projects-grid">
              {projects.map((project, index) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  index={index}
                  onOpenCreateRepo={handleOpenCreateRepo}
                  onDeleteProject={handleDeleteProject}
                />
              ))}
            </div>

            {hasMore && (
              <div className="dashboard-pagination-wrap">
                <button
                  type="button"
                  className="btn-load-more"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                >
                  {loadingMore ? 'Loading more projects...' : 'Load More Projects'}
                </button>
              </div>
            )}
          </>
        )}
      </main>

      {/* Modals */}
      <CreateProjectModal
        isOpen={createProjectOpen}
        onClose={() => setCreateProjectOpen(false)}
        onProjectCreated={handleProjectCreated}
      />

      {createRepoTarget && (
        <CreateRepositoryModal
          isOpen={true}
          projectId={createRepoTarget.id}
          projectName={createRepoTarget.name}
          onClose={() => setCreateRepoTarget(null)}
          onRepositoryCreated={handleRepositoryCreated}
        />
      )}
    </div>
  );
}
