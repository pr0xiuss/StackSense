import React, { useEffect } from 'react';
import '../../styles/graph.css';

/**
 * Graph Inspector Panel (Frontend)
 *
 * Displays detailed metadata for the selected entity node or relationship edge,
 * attached evidence references, and contextual traversal action buttons.
 * Supports Escape key to close without viewport movement.
 */
export function GraphInspector({
  selectedNode,
  selectedEdge,
  version,
  nodes = {},
  onDeselect,
  onExpandNeighborhood,
  onExpandDependencies,
  onExpandDependents,
  onExpandContainment,
  isOperationInFlight = false,
}) {
  // Listen for Escape key to close inspector without forced viewport movement
  useEffect(() => {
    if (!selectedNode && !selectedEdge) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onDeselect?.();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [selectedNode, selectedEdge, onDeselect]);
  if (selectedNode) {
    const isConfirmed = selectedNode.fact_status === 'CONFIRMED';
    const evidenceList = Array.isArray(selectedNode.evidence_logical_ids)
      ? selectedNode.evidence_logical_ids
      : [];

    return (
      <div className="graph-inspector-panel" data-testid="graph-inspector">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
          <div>
            <span className="arch-node-kind-badge" style={{ marginBottom: '0.25rem', display: 'inline-block' }}>
              {selectedNode.canonical_kind}
            </span>
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#f8fafc', wordBreak: 'break-word' }}>
              {selectedNode.name}
            </h3>
          </div>
          {onDeselect && (
            <button
              type="button"
              className="graph-btn graph-btn-ghost"
              style={{ padding: '2px 6px', fontSize: '0.9rem', color: '#94a3b8' }}
              onClick={onDeselect}
              title="Close inspector"
              aria-label="Close inspector"
            >
              &times;
            </button>
          )}
        </div>

        {/* Property attributes */}
        <div style={{ fontSize: '0.82rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div>
            <strong>Status:</strong>{' '}
            <span style={{ color: isConfirmed ? '#10b981' : '#f59e0b', fontWeight: 600 }}>
              {selectedNode.fact_status || 'UNKNOWN'}
            </span>
          </div>

          <div>
            <strong>Logical ID:</strong>{' '}
            <span className="mono-cell" style={{ display: 'block', marginTop: '2px', wordBreak: 'break-all' }}>
              {selectedNode.logical_id}
            </span>
          </div>

          <div>
            <strong>Entity ID:</strong>{' '}
            <span className="mono-cell" style={{ display: 'block', marginTop: '2px', wordBreak: 'break-all' }}>
              {selectedNode.architecture_entity_id}
            </span>
          </div>

          {selectedNode.namespace && (
            <div>
              <strong>Namespace:</strong>{' '}
              <span style={{ color: '#f8fafc' }}>{selectedNode.namespace}</span>
            </div>
          )}

          {/* Evidence references */}
          <div style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <strong>Attached Evidence ({evidenceList.length}):</strong>
            {evidenceList.length === 0 ? (
              <p style={{ margin: '4px 0 0 0', color: '#64748b', fontSize: '0.78rem' }}>
                No direct evidence records attached.
              </p>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                {evidenceList.map((evId) => (
                  <span
                    key={evId}
                    className="mono-cell"
                    style={{
                      fontSize: '0.72rem',
                      background: 'rgba(99, 102, 241, 0.1)',
                      color: '#a5b4fc',
                      border: '1px solid rgba(99, 102, 241, 0.25)',
                      padding: '1px 6px',
                      borderRadius: '4px',
                    }}
                  >
                    {evId}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Traversal Action Buttons */}
          <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#e2e8f0', display: 'block', marginBottom: '0.5rem' }}>
              Explore Relationships
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {onExpandNeighborhood && (
                <button
                  type="button"
                  className="graph-btn graph-btn-secondary"
                  style={{ width: '100%', justifyContent: 'center' }}
                  onClick={() => onExpandNeighborhood(selectedNode.architecture_entity_id)}
                  disabled={isOperationInFlight}
                  aria-label={`Expand Neighborhood of ${selectedNode.name}`}
                >
                  Expand Neighborhood (1 hop)
                </button>
              )}
              {onExpandDependencies && (
                <button
                  type="button"
                  className="graph-btn graph-btn-secondary"
                  style={{ width: '100%', justifyContent: 'center' }}
                  onClick={() => onExpandDependencies(selectedNode.architecture_entity_id)}
                  disabled={isOperationInFlight}
                  aria-label={`Explore Dependencies of ${selectedNode.name}`}
                >
                  Explore Dependencies (Outgoing)
                </button>
              )}
              {onExpandDependents && (
                <button
                  type="button"
                  className="graph-btn graph-btn-secondary"
                  style={{ width: '100%', justifyContent: 'center' }}
                  onClick={() => onExpandDependents(selectedNode.architecture_entity_id)}
                  disabled={isOperationInFlight}
                  aria-label={`Explore Dependents of ${selectedNode.name}`}
                >
                  Explore Dependents (Incoming)
                </button>
              )}
              {onExpandContainment && (
                <button
                  type="button"
                  className="graph-btn graph-btn-secondary"
                  style={{ width: '100%', justifyContent: 'center' }}
                  onClick={() => onExpandContainment(selectedNode.architecture_entity_id)}
                  disabled={isOperationInFlight}
                  aria-label={`Explore Containment of ${selectedNode.name}`}
                >
                  Explore Containment (Hierarchy)
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (selectedEdge) {
    const sourceNode = nodes[selectedEdge.source_entity_id];
    const targetNode = nodes[selectedEdge.target_entity_id];

    return (
      <div className="graph-inspector-panel" data-testid="graph-inspector">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
          <div>
            <span className="arch-node-kind-badge" style={{ background: '#3b0764', color: '#d8b4fe', borderColor: '#7e22ce' }}>
              Relationship
            </span>
            <h3 style={{ margin: '4px 0 0 0', fontSize: '1.05rem', color: '#f8fafc' }}>
              {selectedEdge.canonical_kind}
            </h3>
          </div>
          {onDeselect && (
            <button
              type="button"
              className="graph-btn graph-btn-ghost"
              style={{ padding: '2px 6px', fontSize: '0.9rem', color: '#94a3b8' }}
              onClick={onDeselect}
              title="Close inspector"
              aria-label="Close inspector"
            >
              &times;
            </button>
          )}
        </div>

        <div style={{ fontSize: '0.82rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div>
            <strong>Source:</strong>{' '}
            <span style={{ color: '#f8fafc' }}>{sourceNode?.name || selectedEdge.source_entity_id.slice(0, 8)}</span>
          </div>

          <div>
            <strong>Target:</strong>{' '}
            <span style={{ color: '#f8fafc' }}>{targetNode?.name || selectedEdge.target_entity_id.slice(0, 8)}</span>
          </div>

          <div>
            <strong>Logical ID:</strong>{' '}
            <span className="mono-cell" style={{ display: 'block', marginTop: '2px' }}>
              {selectedEdge.logical_id}
            </span>
          </div>

          <div>
            <strong>Relationship ID:</strong>{' '}
            <span className="mono-cell" style={{ display: 'block', marginTop: '2px' }}>
              {selectedEdge.architecture_relationship_id}
            </span>
          </div>
        </div>
      </div>
    );
  }

  // Summary state when no element is selected
  return (
    <div className="graph-inspector-panel" data-testid="graph-inspector">
      <h3 style={{ margin: '0 0 0.75rem 0', fontSize: '0.95rem', color: '#f8fafc' }}>
        Architecture Summary
      </h3>
      {version ? (
        <div style={{ fontSize: '0.82rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div>
            <strong>Version ID:</strong>{' '}
            <span className="mono-cell">{version.id}</span>
          </div>
          <div>
            <strong>Schema:</strong> v{version.architecture_schema_version || '1.0.0'}
          </div>
          <div>
            <strong>Entities:</strong> {version.entity_count ?? 0}
          </div>
          <div>
            <strong>Relationships:</strong> {version.relationship_count ?? 0}
          </div>
          <div>
            <strong>Evidence:</strong> {version.evidence_count ?? 0}
          </div>
          {typeof version.unresolved_relationship_count === 'number' && (
            <div>
              <strong>Unresolved:</strong> {version.unresolved_relationship_count}
            </div>
          )}
          {typeof version.conflict_count === 'number' && (
            <div>
              <strong>Conflicts:</strong> {version.conflict_count}
            </div>
          )}
          <div style={{ marginTop: '0.5rem', color: '#64748b', fontSize: '0.78rem', lineHeight: 1.4 }}>
            Click on any node in the graph map or select an item in the structured list to inspect detailed metadata and traverse connected relationships.
          </div>
        </div>
      ) : (
        <p style={{ color: '#64748b', fontSize: '0.82rem', margin: 0 }}>
          No architecture version loaded.
        </p>
      )}
    </div>
  );
}

export default GraphInspector;

