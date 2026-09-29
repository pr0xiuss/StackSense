import React, { useState, useEffect, useCallback, useMemo } from 'react';
import DashboardHeader from '../components/dashboard/DashboardHeader.jsx';
import ProjectCard from '../components/dashboard/ProjectCard.jsx';
import CreateProjectModal from '../components/dashboard/CreateProjectModal.jsx';
import CreateRepositoryModal from '../components/dashboard/CreateRepositoryModal.jsx';
import { projectService } from '../services/projectService.js';

const PAGE_LIMIT = 100;
const PROJECTS_PER_PAGE = 8;

export default function ProjectsDashboardPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  // Search & Pagination state
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  // Modals & Repositories state
  const [createProjectOpen, setCreateProjectOpen] = useState(false);
  const [createRepoTarget, setCreateRepoTarget] = useState(null); // project object
  const [lastCreatedRepo, setLastCreatedRepo] = useState(null); // reactive new repo

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

  // Reset to page 1 whenever the user searches
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  const handleLoadMore = () => {
    const nextOffset = offset + PAGE_LIMIT;
    fetchProjects(nextOffset, true);
  };

  const handleProjectCreated = (newProject) => {
    setProjects((prev) => [newProject, ...prev]);
    setCurrentPage(1);
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
    setLastCreatedRepo(newRepo);
    setCreateRepoTarget(null);
  };

  // Filter projects by name or description
  const filteredProjects = useMemo(() => {
    if (!searchQuery.trim()) return projects;
    const query = searchQuery.toLowerCase().trim();
    return projects.filter((project) => {
      const name = (project.name || '').toLowerCase();
      const desc = (project.description || '').toLowerCase();
      return name.includes(query) || desc.includes(query);
    });
  }, [projects, searchQuery]);

  // Client-side pagination (8 per page)
  const totalPages = Math.max(1, Math.ceil(filteredProjects.length / PROJECTS_PER_PAGE));
  const safeCurrentPage = Math.min(Math.max(1, currentPage), totalPages);
  const startIndex = (safeCurrentPage - 1) * PROJECTS_PER_PAGE;
  const endIndex = Math.min(startIndex + PROJECTS_PER_PAGE, filteredProjects.length);
  const paginatedProjects = filteredProjects.slice(startIndex, endIndex);

  const handlePageChange = (newPage) => {
    if (newPage < 1 || newPage > totalPages) return;
    setCurrentPage(newPage);
    const mainGrid = document.querySelector('.dashboard-content');
    if (mainGrid) {
      mainGrid.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
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

        {/* Search & Filter Toolbar */}
        {!loading && !error && projects.length > 0 && (
          <div className="dashboard-toolbar">
            <div className="dashboard-search-wrap">
              <svg className="dashboard-search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                className="dashboard-search-input"
                placeholder="Search projects by name or description..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search projects"
              />
              {searchQuery && (
                <button
                  type="button"
                  className="dashboard-search-clear-btn"
                  onClick={() => setSearchQuery('')}
                  aria-label="Clear search"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              )}
            </div>

            {searchQuery.trim() && (
              <div className="dashboard-search-feedback">
                <span>
                  Found <strong>{filteredProjects.length}</strong> {filteredProjects.length === 1 ? 'project' : 'projects'}
                </span>
                <button
                  type="button"
                  className="btn-clear-query"
                  onClick={() => setSearchQuery('')}
                >
                  Clear filter
                </button>
              </div>
            )}
          </div>
        )}

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

        {/* Empty State (No Projects Created Yet) */}
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

        {/* Empty Search State (Projects Exist But None Match Query) */}
        {!loading && !error && projects.length > 0 && filteredProjects.length === 0 && (
          <div className="dashboard-search-empty">
            <div className="search-empty-icon-box">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
                <line x1="8" y1="11" x2="14" y2="11" />
              </svg>
            </div>
            <h3 className="empty-title">No matching projects found</h3>
            <p className="empty-subtitle">
              We couldn&apos;t find any projects matching &ldquo;<strong>{searchQuery}</strong>&rdquo;. Try searching with a different term.
            </p>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setSearchQuery('')}
            >
              Clear Search Filter
            </button>
          </div>
        )}

        {/* Projects Grid & Pagination */}
        {!loading && !error && filteredProjects.length > 0 && (
          <>
            <div className="projects-grid">
              {paginatedProjects.map((project, index) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  index={startIndex + index}
                  onOpenCreateRepo={handleOpenCreateRepo}
                  onDeleteProject={handleDeleteProject}
                  lastCreatedRepo={lastCreatedRepo}
                />
              ))}
            </div>

            {/* Pagination Controls Bar */}
            <div className="dashboard-pagination-bar">
              <div className="pagination-info">
                Showing <strong>{startIndex + 1}</strong>&ndash;<strong>{endIndex}</strong> of <strong>{filteredProjects.length}</strong> {filteredProjects.length === 1 ? 'project' : 'projects'}
              </div>

              {totalPages > 1 && (
                <div className="pagination-controls" role="navigation" aria-label="Projects pagination">
                  <button
                    type="button"
                    className="pagination-btn pagination-prev"
                    onClick={() => handlePageChange(safeCurrentPage - 1)}
                    disabled={safeCurrentPage === 1}
                    aria-label="Previous page"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="15 18 9 12 15 6" />
                    </svg>
                    <span>Previous</span>
                  </button>

                  <div className="pagination-pages">
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => (
                      <button
                        key={pageNum}
                        type="button"
                        className={`pagination-page-btn ${pageNum === safeCurrentPage ? 'active' : ''}`}
                        onClick={() => handlePageChange(pageNum)}
                        aria-label={`Page ${pageNum}`}
                        aria-current={pageNum === safeCurrentPage ? 'page' : undefined}
                      >
                        {pageNum}
                      </button>
                    ))}
                  </div>

                  <button
                    type="button"
                    className="pagination-btn pagination-next"
                    onClick={() => handlePageChange(safeCurrentPage + 1)}
                    disabled={safeCurrentPage === totalPages}
                    aria-label="Next page"
                  >
                    <span>Next</span>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  </button>
                </div>
              )}
            </div>

            {hasMore && (
              <div className="dashboard-loadmore-wrap">
                <button
                  type="button"
                  className="btn-load-more"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                >
                  {loadingMore ? 'Loading additional projects from server...' : 'Load More Projects from Server'}
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
