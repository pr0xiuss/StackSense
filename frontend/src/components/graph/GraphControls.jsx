/**
 * GraphControls component
 *
 * Provides query mode switching, traversal depth and direction selectors,
 * relationship kind filters with strict non-containment separation, path endpoint selectors,
 * pagination continuation (Load more), and canvas Fit/Clear buttons.
 */
import React, { useState } from 'react';
import {
  DEPENDENCY_RELATIONSHIP_KINDS,
  CONTAINMENT_RELATIONSHIP_KIND,
  NEIGHBORHOOD_DIRECTIONS,
  CONTAINMENT_DIRECTIONS,
  ARCHITECTURE_RELATIONSHIP_KIND_LABELS,
} from '../../contracts/graphContracts.js';

export const EXPLORER_MODES = Object.freeze({
  WINDOW: 'window',
  NEIGHBORHOOD: 'neighborhood',
  DEPENDENCIES: 'dependencies',
  DEPENDENTS: 'dependents',
  CONTAINMENT: 'containment',
  PATHS: 'paths',
});

export function GraphControls({
  mode = EXPLORER_MODES.WINDOW,
  onModeChange,
  selectedNode = null,
  loadedNodes = [],
  activeOperation = null, // { inFlight, cursor, mode }
  isCapReached = false,
  onLoadMore = null,
  onExecuteQuery = null,
  onClear = null,
  onFit = null,
}) {
  const [depth, setDepth] = useState(1);
  const [direction, setDirection] = useState('both');
  const [containmentDirection, setContainmentDirection] = useState('children');
  const [selectedKinds, setSelectedKinds] = useState([]);
  const [sourceNodeId, setSourceNodeId] = useState('');
  const [targetNodeId, setTargetNodeId] = useState('');

  const isInFlight = activeOperation?.inFlight || false;
  const hasCursor = Boolean(activeOperation?.cursor);

  // Relationship kinds available for the current mode
  const availableKinds =
    mode === EXPLORER_MODES.NEIGHBORHOOD
      ? [...DEPENDENCY_RELATIONSHIP_KINDS, CONTAINMENT_RELATIONSHIP_KIND]
      : DEPENDENCY_RELATIONSHIP_KINDS;

  const handleKindToggle = (kind) => {
    setSelectedKinds((prev) =>
      prev.includes(kind) ? prev.filter((k) => k !== kind) : [...prev, kind]
    );
  };

  const handleExecute = () => {
    if (!onExecuteQuery) return;
    if (mode === EXPLORER_MODES.PATHS) {
      if (!sourceNodeId || !targetNodeId) return;
      onExecuteQuery({
        mode,
        sourceEntityId: sourceNodeId,
        targetEntityId: targetNodeId,
        maxDepth: depth,
        relationshipKinds: selectedKinds.length > 0 ? selectedKinds : undefined,
      });
    } else if (mode === EXPLORER_MODES.CONTAINMENT) {
      if (!selectedNode) return;
      onExecuteQuery({
        mode,
        entityId: selectedNode.architecture_entity_id,
        direction: containmentDirection,
        depth,
      });
    } else if (
      mode === EXPLORER_MODES.NEIGHBORHOOD ||
      mode === EXPLORER_MODES.DEPENDENCIES ||
      mode === EXPLORER_MODES.DEPENDENTS
    ) {
      if (!selectedNode) return;
      onExecuteQuery({
        mode,
        entityId: selectedNode.architecture_entity_id,
        direction: mode === EXPLORER_MODES.NEIGHBORHOOD ? direction : undefined,
        depth,
        relationshipKinds: selectedKinds.length > 0 ? selectedKinds : undefined,
      });
    }
  };

  return (
    <div className="graph-controls-toolbar" role="toolbar" aria-label="Graph exploration controls">
      {/* 1. Exploration Mode Selector */}
      <div className="graph-control-group">
        <label htmlFor="graph-mode-select" className="graph-control-label">
          Mode:
        </label>
        <select
          id="graph-mode-select"
          className="graph-select"
          value={mode}
          onChange={(e) => {
            onModeChange?.(e.target.value);
            setSelectedKinds([]);
          }}
          disabled={isInFlight}
        >
          <option value={EXPLORER_MODES.WINDOW}>Overview (Window)</option>
          <option value={EXPLORER_MODES.NEIGHBORHOOD}>Neighborhood</option>
          <option value={EXPLORER_MODES.DEPENDENCIES}>Dependencies (Outgoing)</option>
          <option value={EXPLORER_MODES.DEPENDENTS}>Dependents (Incoming)</option>
          <option value={EXPLORER_MODES.CONTAINMENT}>Containment (Hierarchy)</option>
          <option value={EXPLORER_MODES.PATHS}>Directed Paths</option>
        </select>
      </div>

      {/* 2. Anchor Node Indicator (for entity-scoped traversals) */}
      {mode !== EXPLORER_MODES.WINDOW && mode !== EXPLORER_MODES.PATHS && (
        <div className="graph-control-group">
          <span className="graph-control-label">Anchor:</span>
          {selectedNode ? (
            <span className="graph-anchor-badge" title={selectedNode.architecture_entity_id}>
              {selectedNode.name}
            </span>
          ) : (
            <span className="graph-anchor-missing">Select a node in the graph</span>
          )}
        </div>
      )}

      {/* 3. Traversal Depth (1..5) */}
      {mode !== EXPLORER_MODES.WINDOW && (
        <div className="graph-control-group">
          <label htmlFor="graph-depth-select" className="graph-control-label">
            Depth:
          </label>
          <select
            id="graph-depth-select"
            className="graph-select graph-select-small"
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            disabled={isInFlight}
          >
            {[1, 2, 3, 4, 5].map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* 4. Direction Selector (Neighborhood) */}
      {mode === EXPLORER_MODES.NEIGHBORHOOD && (
        <div className="graph-control-group">
          <label htmlFor="graph-dir-select" className="graph-control-label">
            Direction:
          </label>
          <select
            id="graph-dir-select"
            className="graph-select"
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            disabled={isInFlight}
          >
            {NEIGHBORHOOD_DIRECTIONS.map((dir) => (
              <option key={dir} value={dir}>
                {dir}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* 5. Direction Selector (Containment) */}
      {mode === EXPLORER_MODES.CONTAINMENT && (
        <div className="graph-control-group">
          <label htmlFor="graph-containment-dir-select" className="graph-control-label">
            Direction:
          </label>
          <select
            id="graph-containment-dir-select"
            className="graph-select"
            value={containmentDirection}
            onChange={(e) => setContainmentDirection(e.target.value)}
            disabled={isInFlight}
          >
            {CONTAINMENT_DIRECTIONS.map((dir) => (
              <option key={dir} value={dir}>
                {dir}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* 6. Path Endpoint Selectors (Paths mode) */}
      {mode === EXPLORER_MODES.PATHS && (
        <>
          <div className="graph-control-group">
            <label htmlFor="graph-source-select" className="graph-control-label">
              Source:
            </label>
            <select
              id="graph-source-select"
              className="graph-select"
              value={sourceNodeId}
              onChange={(e) => setSourceNodeId(e.target.value)}
              disabled={isInFlight}
            >
              <option value="">Select source...</option>
              {loadedNodes.map((n) => (
                <option key={n.architecture_entity_id} value={n.architecture_entity_id}>
                  {n.name}
                </option>
              ))}
            </select>
          </div>
          <div className="graph-control-group">
            <label htmlFor="graph-target-select" className="graph-control-label">
              Target:
            </label>
            <select
              id="graph-target-select"
              className="graph-select"
              value={targetNodeId}
              onChange={(e) => setTargetNodeId(e.target.value)}
              disabled={isInFlight}
            >
              <option value="">Select target...</option>
              {loadedNodes.map((n) => (
                <option key={n.architecture_entity_id} value={n.architecture_entity_id}>
                  {n.name}
                </option>
              ))}
            </select>
          </div>
        </>
      )}

      {/* 6b. Relationship Kind Filters (Fieldset & Legend for Accessibility) */}
      {mode !== EXPLORER_MODES.WINDOW && mode !== EXPLORER_MODES.CONTAINMENT && (
        <fieldset className="graph-control-fieldset kind-filters-fieldset">
          <legend className="graph-control-legend">Filter by Relationship Kind</legend>
          <div className="kind-filters-grid">
            {availableKinds.map((kind) => {
              const inputId = `kind-filter-${kind}`;
              const isChecked = selectedKinds.includes(kind);
              return (
                <label key={kind} htmlFor={inputId} className="kind-filter-label">
                  <input
                    type="checkbox"
                    id={inputId}
                    checked={isChecked}
                    onChange={() => handleKindToggle(kind)}
                    disabled={isInFlight}
                    className="kind-filter-checkbox"
                  />
                  <span className="kind-filter-text">
                    {ARCHITECTURE_RELATIONSHIP_KIND_LABELS[kind] || kind}
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>
      )}

      {/* 7. Action Execution Button */}
      {mode !== EXPLORER_MODES.WINDOW && (
        <div className="graph-control-group">
          <button
            type="button"
            className="graph-btn graph-btn-primary"
            onClick={handleExecute}
            aria-label="Execute"
            disabled={
              isInFlight ||
              isCapReached ||
              (mode === EXPLORER_MODES.PATHS
                ? !sourceNodeId || !targetNodeId || sourceNodeId === targetNodeId
                : !selectedNode)
            }
          >
            {isInFlight ? 'Exploring...' : 'Execute'}
          </button>
        </div>
      )}

      {/* 8. Load More Continuation Button */}
      {hasCursor && onLoadMore && (
        <div className="graph-control-group">
          <button
            type="button"
            className="graph-btn graph-btn-secondary"
            onClick={onLoadMore}
            disabled={isInFlight || isCapReached}
            title={isCapReached ? 'Canvas limit reached' : 'Load next batch of nodes and edges'}
            aria-label="Load more"
          >
            {isInFlight ? 'Loading...' : 'Load more'}
          </button>
        </div>
      )}

      {/* 9. Canvas Controls (Fit, Clear) */}
      <div className="graph-control-actions">
        {onFit && (
          <button
            type="button"
            className="graph-btn graph-btn-ghost"
            onClick={onFit}
            title="Fit graph to view"
            aria-label="Fit View"
          >
            Fit View
          </button>
        )}
        {onClear && (
          <button
            type="button"
            className="graph-btn graph-btn-ghost text-danger"
            onClick={onClear}
            title="Clear loaded graph elements"
            aria-label="Clear"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}

