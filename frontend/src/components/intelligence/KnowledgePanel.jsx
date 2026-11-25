import React from 'react';

const SELECTOR_TYPES = [
  { value: 'entity_name', label: 'Entity Name' },
  { value: 'logical_id', label: 'Logical Identifier' },
  { value: 'exact_id', label: 'Canonical UUID' },
];

const OPERATIONS = [
  { value: 'LOOKUP', label: 'Lookup' },
  { value: 'RELATIONSHIPS', label: 'Relationships' },
  { value: 'NEIGHBORHOOD', label: 'Neighborhood (2-hop)' },
  { value: 'PATH', label: 'Dependency Paths' },
];

export function KnowledgePanel({
  selectorType,
  setSelectorType,
  selectorValue,
  setSelectorValue,
  operation,
  setOperation,
  knowledgeResponse,
  knowledgeLoading,
  knowledgeError,
  onExecuteQuery,
  contextBundle,
  contextLoading,
  contextError,
  onAssembleContext,
  onOpenEvidence,
}) {
  const handleSubmit = (e) => {
    e.preventDefault();
    onExecuteQuery?.();
  };

  const handleSelectCandidate = (candidate) => {
    setSelectorType('exact_id');
    setSelectorValue(candidate.id || candidate.entity_id);
    onExecuteQuery?.();
  };

  const isAmbiguous = knowledgeResponse?.resolution_state === 'AMBIGUOUS';
  const resolved = knowledgeResponse?.resolved_subject || knowledgeResponse?.subject;

  return (
    <div className="intelligence-knowledge-panel" role="region" aria-label="Knowledge & Context">
      {/* Query Form */}
      <form className="knowledge-query-form" onSubmit={handleSubmit}>
        <div className="knowledge-form-grid">
          <div className="form-field-group">
            <label htmlFor="selector-type-select">Selector Type:</label>
            <select
              id="selector-type-select"
              value={selectorType}
              onChange={(e) => setSelectorType(e.target.value)}
              className="knowledge-dropdown"
            >
              {SELECTOR_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-field-group flex-grow">
            <label htmlFor="selector-value-input">Target Identifier:</label>
            <input
              id="selector-value-input"
              type="text"
              value={selectorValue}
              onChange={(e) => setSelectorValue(e.target.value)}
              placeholder="e.g. AuthService, backend.users, or canonical UUID…"
              className="knowledge-text-input"
            />
          </div>

          <div className="form-field-group">
            <label htmlFor="operation-select">Operation:</label>
            <select
              id="operation-select"
              value={operation}
              onChange={(e) => setOperation(e.target.value)}
              className="knowledge-dropdown"
            >
              {OPERATIONS.map((op) => (
                <option key={op.value} value={op.value}>
                  {op.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-submit-group">
            <button
              type="submit"
              className="btn-query-submit"
              disabled={knowledgeLoading || !selectorValue.trim()}
            >
              {knowledgeLoading ? 'Executing…' : 'Execute Query'}
            </button>
          </div>
        </div>
      </form>

      {/* Error Banners */}
      {knowledgeError && (
        <div className="knowledge-error-banner" role="alert">
          <strong>Query Error:</strong> {knowledgeError}
        </div>
      )}

      {contextError && (
        <div className="knowledge-error-banner" role="alert">
          <strong>Context Assembly Error:</strong> {contextError}
        </div>
      )}

      {/* Results Viewport */}
      <div className="knowledge-results-container">
        {knowledgeLoading && (
          <div className="knowledge-loading-state" role="status">
            <span className="spinner-dot" />
            <span>Resolving target subject and querying canonical context…</span>
          </div>
        )}

        {/* Ambiguity Resolution */}
        {isAmbiguous && knowledgeResponse?.candidates && (
          <div className="ambiguity-warning-card" role="region" aria-label="Multiple Candidates Found">
            <h4>Multiple Matching Elements Found</h4>
            <p className="ambiguity-desc">
              Identifier &ldquo;{selectorValue}&rdquo; matches multiple architecture elements.
              Select a specific candidate to continue:
            </p>
            <div className="candidates-list">
              {knowledgeResponse.candidates.map((cand) => (
                <div key={cand.id || cand.logical_id} className="candidate-row">
                  <div className="candidate-info">
                    <span className="candidate-name">{cand.name || cand.logical_id}</span>
                    <span className="candidate-kind">{cand.kind}</span>
                    {cand.coordinates?.file_path && (
                      <span className="candidate-path">{cand.coordinates.file_path}</span>
                    )}
                  </div>
                  <button
                    type="button"
                    className="btn-select-candidate"
                    onClick={() => handleSelectCandidate(cand)}
                  >
                    Select Exact
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Resolved Target Detail */}
        {!knowledgeLoading && resolved && (
          <div className="resolved-subject-card">
            <div className="resolved-card-header">
              <div>
                <h3 className="resolved-name">{resolved.name || resolved.logical_id || resolved.id}</h3>
                <div className="resolved-meta-badges">
                  {resolved.kind && <span className="kind-badge">{resolved.kind}</span>}
                  {resolved.status && <span className="status-badge">{resolved.status}</span>}
                  <span className="mono-cell" title={`Exact UUID: ${resolved.id}`}>
                    {resolved.id ? resolved.id.slice(0, 12) + '…' : ''}
                  </span>
                </div>
              </div>

              <div className="resolved-actions">
                {onOpenEvidence && (
                  <button
                    type="button"
                    className="btn-action btn-evidence"
                    onClick={() => onOpenEvidence({
                      entity_id: resolved.id,
                      name: resolved.name || resolved.logical_id,
                    })}
                  >
                    View Subject Evidence
                  </button>
                )}
                {onAssembleContext && (
                  <button
                    type="button"
                    className="btn-action btn-context"
                    disabled={contextLoading}
                    onClick={() => onAssembleContext([
                      { kind: 'exact_id', id: resolved.id },
                    ])}
                  >
                    {contextLoading ? 'Assembling…' : 'Assemble Context Bundle'}
                  </button>
                )}
              </div>
            </div>

            {/* Relationships Table */}
            {Array.isArray(knowledgeResponse.relationships) && knowledgeResponse.relationships.length > 0 && (
              <div className="relationships-section">
                <h4>Connected Relationships ({knowledgeResponse.relationships.length})</h4>
                <div className="relationships-table-wrapper">
                  <table className="knowledge-table">
                    <thead>
                      <tr>
                        <th>Relationship Kind</th>
                        <th>Target Element</th>
                        <th>Direction</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {knowledgeResponse.relationships.map((rel, idx) => (
                        <tr key={rel.id || idx}>
                          <td><code>{rel.kind || rel.type}</code></td>
                          <td>{rel.target_name || rel.target_id || '—'}</td>
                          <td><span className="direction-badge">{rel.direction || 'OUTGOING'}</span></td>
                          <td>
                            {onOpenEvidence && rel.id && (
                              <button
                                type="button"
                                className="btn-table-action"
                                onClick={() => onOpenEvidence({
                                  relationship_id: rel.id,
                                  name: `${rel.kind} -> ${rel.target_name || rel.target_id}`,
                                })}
                              >
                                Evidence
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Assembled Context Bundle Display */}
        {contextBundle && (
          <div className="context-bundle-card" role="region" aria-label="Assembled Context Bundle">
            <div className="bundle-header">
              <h4>Assembled Semantic Context Bundle</h4>
              {contextBundle.semantic_digest && (
                <span className="bundle-digest" title={`C3 Semantic Digest: ${contextBundle.semantic_digest}`}>
                  Digest: <code>{contextBundle.semantic_digest.slice(0, 16)}…</code>
                </span>
              )}
            </div>

            <div className="bundle-stats-strip">
              <div className="bundle-stat">
                <span className="stat-label">Subjects:</span>
                <span className="stat-val">{contextBundle.subjects?.length ?? 0}</span>
              </div>
              <div className="bundle-stat">
                <span className="stat-label">Relationships:</span>
                <span className="stat-val">{contextBundle.relationships?.length ?? 0}</span>
              </div>
              <div className="bundle-stat">
                <span className="stat-label">Evidence Records:</span>
                <span className="stat-val">{contextBundle.evidence?.length ?? 0}</span>
              </div>
              {contextBundle.coverage && (
                <div className="bundle-stat">
                  <span className="stat-label">Coverage:</span>
                  <span className="stat-val">{contextBundle.coverage.completeness_state || 'COMPLETE'}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
export default KnowledgePanel;
