import React from 'react';

const ENTITY_KINDS = ['SERVICE', 'DATABASE', 'API_ENDPOINT', 'QUEUE', 'MODULE', 'INTERFACE'];
const STATUSES = ['ACTIVE', 'DEPRECATED', 'PROPOSED'];

export function SearchPanel({
  searchQuery,
  setSearchQuery,
  searchFilters,
  setSearchFilters,
  searchStatus,
  searchPage,
  searchLoading,
  searchError,
  searchCursorIndex = 0,
  hasMoreSearch = false,
  onSearch,
  onNextPage,
  onPrevPage,
  onInspectSubject,
  onOpenEvidence,
}) {
  const handleQuerySubmit = (e) => {
    e.preventDefault();
    onSearch?.();
  };

  const toggleEntityKind = (kind) => {
    const current = searchFilters.entity_kinds || [];
    const next = current.includes(kind)
      ? current.filter((k) => k !== kind)
      : [...current, kind];
    setSearchFilters({ ...searchFilters, entity_kinds: next });
  };

  const toggleStatus = (status) => {
    const current = searchFilters.statuses || [];
    const next = current.includes(status)
      ? current.filter((s) => s !== status)
      : [...current, status];
    setSearchFilters({ ...searchFilters, statuses: next });
  };

  return (
    <div className="intelligence-search-panel" role="region" aria-label="Lexical Search">
      {/* Search Capabilities Header */}
      {searchStatus && (
        <div className="search-capabilities-bar">
          <div className="cap-item">
            <span className="cap-label">Search Index:</span>
            <span className={`cap-value freshness-${(searchStatus.freshness_state || 'fresh').toLowerCase()}`}>
              {searchStatus.freshness_state || 'READY'}
            </span>
          </div>
          <div className="cap-item">
            <span className="cap-label">Indexed Documents:</span>
            <span className="cap-value">
              {searchStatus.indexed_documents_count?.toLocaleString() ?? '—'}
            </span>
          </div>
          {searchStatus.active_generation_id && (
            <div className="cap-item">
              <span className="cap-label">Generation:</span>
              <span className="cap-value mono-cell">
                {searchStatus.active_generation_id.slice(0, 8)}…
              </span>
            </div>
          )}
        </div>
      )}

      {/* Search Form */}
      <form className="search-input-form" onSubmit={handleQuerySubmit}>
        <div className="search-input-row">
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search entities, services, endpoints, databases by name or keyword…"
            className="search-text-field"
            aria-label="Search query"
          />
          <button type="submit" className="btn-search-submit" disabled={searchLoading}>
            {searchLoading ? 'Searching…' : 'Search'}
          </button>
        </div>

        {/* Filter Chips */}
        <div className="search-filter-groups">
          <div className="filter-group">
            <span className="filter-label">Entity Kind:</span>
            <div className="filter-chips">
              {ENTITY_KINDS.map((kind) => {
                const active = searchFilters.entity_kinds?.includes(kind);
                return (
                  <button
                    key={kind}
                    type="button"
                    className={`filter-chip ${active ? 'active' : ''}`}
                    onClick={() => toggleEntityKind(kind)}
                  >
                    {kind.replace('_', ' ')}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="filter-group">
            <span className="filter-label">Status:</span>
            <div className="filter-chips">
              {STATUSES.map((status) => {
                const active = searchFilters.statuses?.includes(status);
                return (
                  <button
                    key={status}
                    type="button"
                    className={`filter-chip ${active ? 'active' : ''}`}
                    onClick={() => toggleStatus(status)}
                  >
                    {status}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </form>

      {/* Error Banner */}
      {searchError && (
        <div className="search-error-banner" role="alert">
          {searchError}
        </div>
      )}

      {/* Results Section */}
      <div className="search-results-container">
        {searchLoading && !searchPage && (
          <div className="search-loading-placeholder" role="status">
            <span className="spinner-dot" />
            <span>Executing lexical search across indexed projections…</span>
          </div>
        )}

        {!searchLoading && searchPage && searchPage.items?.length === 0 && (
          <div className="search-empty-state">
            <p>No architecture elements match your query and active filters.</p>
          </div>
        )}

        {searchPage && searchPage.items?.length > 0 && (
          <>
            <div className="search-results-meta">
              <span>Showing results for page {searchCursorIndex + 1}</span>
            </div>

            <div className="search-cards-list">
              {searchPage.items.map((item) => (
                <div key={item.id} className="search-result-card">
                  <div className="search-card-main">
                    <div className="search-card-header">
                      <h4 className="result-name">{item.name || item.logical_id || item.id}</h4>
                      <div className="result-badges">
                        {item.kind && <span className="kind-badge">{item.kind}</span>}
                        {item.status && <span className="status-badge">{item.status}</span>}
                        {item.score !== undefined && item.score !== null && (
                          <span className="score-badge" title="Lexical match score">
                            Score: {Number(item.score).toFixed(2)}
                          </span>
                        )}
                      </div>
                    </div>

                    {item.coordinates && (
                      <div className="result-coordinates">
                        <code>{item.coordinates.file_path || item.coordinates.path}</code>
                        {item.coordinates.line_start && (
                          <span> L{item.coordinates.line_start}–L{item.coordinates.line_end || item.coordinates.line_start}</span>
                        )}
                      </div>
                    )}

                    {item.highlight && (
                      <p
                        className="result-highlight"
                        dangerouslySetInnerHTML={{ __html: item.highlight }}
                      />
                    )}
                  </div>

                  <div className="search-card-actions">
                    {onInspectSubject && (
                      <button
                        type="button"
                        className="btn-card-action"
                        onClick={() => onInspectSubject({
                          type: 'exact_id',
                          id: item.id,
                          name: item.name || item.logical_id,
                        })}
                      >
                        Knowledge Query
                      </button>
                    )}
                    {onOpenEvidence && (
                      <button
                        type="button"
                        className="btn-card-action btn-evidence"
                        onClick={() => onOpenEvidence({
                          entity_id: item.id,
                          name: item.name || item.logical_id || item.id,
                        })}
                      >
                        Evidence
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination Controls */}
            <div className="search-pagination-row">
              <button
                type="button"
                className="btn-pagination"
                disabled={searchCursorIndex === 0 || searchLoading}
                onClick={onPrevPage}
              >
                &larr; Previous Page
              </button>
              <span className="pagination-current-label">
                Page {searchCursorIndex + 1}
              </span>
              <button
                type="button"
                className="btn-pagination"
                disabled={!hasMoreSearch || searchLoading}
                onClick={onNextPage}
              >
                Next Page &rarr;
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
export default SearchPanel;
