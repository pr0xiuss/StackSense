import React, { useMemo, useCallback, useEffect, useRef } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import '../../styles/graph.css';

/**
 * Custom Architecture Node renderer for React Flow.
 * Strictly conforms to fixed 220x80 geometry and canonical vocabulary.
 * Supports keyboard selection parity (Enter/Space to select, Escape to deselect).
 */
function ArchitectureNode({ data, selected }) {
  const node = data?.node || {};
  const isConfirmed = node.fact_status === 'CONFIRMED';
  const onSelectNode = data?.onSelectNode;

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelectNode?.(node.architecture_entity_id);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onSelectNode?.(null);
    }
  };

  return (
    <div
      className={`arch-graph-node ${selected ? 'selected' : ''}`}
      tabIndex={0}
      role="button"
      aria-label={`${node.canonical_kind || 'element'}: ${node.name || 'unnamed'}`}
      aria-selected={Boolean(selected)}
      data-testid={`arch-node-${node.architecture_entity_id}`}
      onKeyDown={handleKeyDown}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: '#6366f1', width: 8, height: 8 }}
      />

      <div className="arch-node-header">
        <span className="arch-node-kind-badge">
          {node.canonical_kind || 'entity'}
        </span>
        {node.fact_status && (
          <span
            style={{
              fontSize: '0.65rem',
              fontWeight: 600,
              color: isConfirmed ? '#10b981' : '#f59e0b',
            }}
          >
            {node.fact_status}
          </span>
        )}
      </div>

      <div className="arch-node-name" title={node.name}>
        {node.name || 'Unnamed Element'}
      </div>

      <div className="arch-node-footer">
        <span
          style={{
            maxWidth: '130px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={node.namespace || node.logical_id}
        >
          {node.namespace || node.logical_id || ''}
        </span>
        {Array.isArray(node.evidence_logical_ids) && node.evidence_logical_ids.length > 0 && (
          <span title={`${node.evidence_logical_ids.length} attached evidence records`}>
            ev:{node.evidence_logical_ids.length}
          </span>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: '#6366f1', width: 8, height: 8 }}
      />
    </div>
  );
}

const nodeTypes = {
  architectureNode: ArchitectureNode,
};

/**
 * Inner component to access React Flow instance hooks (fitView, zoom).
 */
function GraphCanvasInner({
  nodes,
  edges,
  positions,
  selectedNodeId,
  onSelectNode,
  fitViewTrigger,
  isLayoutRunning,
  layoutError,
}) {
  const { fitView } = useReactFlow();
  const hasFittedInitialRef = useRef(false);

  // Fit view once when positions are first populated
  useEffect(() => {
    const hasPositions = Object.keys(positions).length > 0;
    if (hasPositions && !hasFittedInitialRef.current) {
      hasFittedInitialRef.current = true;
      requestAnimationFrame(() => {
        fitView({ padding: 0.2, duration: 250 });
      });
    }
  }, [positions, fitView]);

  // Fit view on explicit user trigger from toolbar controls
  useEffect(() => {
    if (fitViewTrigger > 0) {
      fitView({ padding: 0.2, duration: 250 });
    }
  }, [fitViewTrigger, fitView]);

  // Convert normalized dictionary nodes to React Flow node format
  const rfNodes = useMemo(() => {
    return Object.values(nodes).map((n) => {
      const pos = positions[n.architecture_entity_id] || { x: 0, y: 0 };
      const isSelected = selectedNodeId === n.architecture_entity_id;
      return {
        id: n.architecture_entity_id,
        type: 'architectureNode',
        position: { x: pos.x, y: pos.y },
        data: { node: n, onSelectNode },
        selected: isSelected,
        draggable: false,
        selectable: true,
      };
    });
  }, [nodes, positions, selectedNodeId, onSelectNode]);

  // Convert normalized dictionary edges to React Flow edge format
  const rfEdges = useMemo(() => {
    return Object.values(edges).map((e) => {
      const isContainment = e.canonical_kind === 'contains';
      return {
        id: e.architecture_relationship_id,
        source: e.source_entity_id,
        target: e.target_entity_id,
        label: e.canonical_kind,
        animated: false,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 14,
          height: 14,
          color: isContainment ? '#a855f7' : '#6366f1',
        },
        style: {
          stroke: isContainment ? '#a855f7' : '#6366f1',
          strokeWidth: 1.5,
          strokeDasharray: isContainment ? '4 3' : undefined,
        },
        labelStyle: {
          fill: '#94a3b8',
          fontSize: 10,
          fontWeight: 500,
        },
        labelBgStyle: {
          fill: '#131b2e',
          fillOpacity: 0.85,
        },
      };
    });
  }, [edges]);

  const handleNodeClick = useCallback(
    (_, node) => {
      if (onSelectNode) {
        onSelectNode(node.id);
      }
    },
    [onSelectNode]
  );

  const handlePaneClick = useCallback(() => {
    if (onSelectNode) {
      onSelectNode(null);
    }
  }, [onSelectNode]);

  if (rfNodes.length === 0) {
    return (
      <div
        className="graph-canvas-empty"
        style={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem',
          textAlign: 'center',
        }}
      >
        <div style={{ marginBottom: '1rem', color: '#818cf8' }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="6" cy="6" r="3" />
            <circle cx="18" cy="6" r="3" />
            <circle cx="12" cy="18" r="3" />
            <line x1="8.5" y1="7" x2="15.5" y2="7" />
            <line x1="7.5" y1="8.5" x2="10.5" y2="15.5" />
            <line x1="16.5" y1="8.5" x2="13.5" y2="15.5" />
          </svg>
        </div>
        <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', color: '#f8fafc' }}>
          No Elements In Active Window
        </h3>
        <p style={{ fontSize: '0.85rem', color: '#94a3b8', lineHeight: 1.5, margin: 0, maxWidth: '420px' }}>
          Projection is ready. Select an exploration mode or trigger a traversal above to populate graph nodes.
        </p>
      </div>
    );
  }

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      {isLayoutRunning && (
        <div
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            zIndex: 10,
            background: 'rgba(19, 27, 46, 0.9)',
            border: '1px solid #374151',
            borderRadius: 6,
            padding: '4px 10px',
            fontSize: '0.75rem',
            color: '#93c5fd',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <span className="btn-spinner" style={{ width: 12, height: 12 }} />
          Computing layout...
        </div>
      )}

      {layoutError && (
        <div
          style={{
            position: 'absolute',
            top: 12,
            left: 12,
            zIndex: 10,
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: 6,
            padding: '4px 10px',
            fontSize: '0.75rem',
            color: '#fca5a5',
          }}
        >
          ⚠️ {layoutError} (using fallback layout)
        </div>
      )}

      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
        zoomOnScroll={true}
        panOnScroll={false}
        panOnDrag={true}
        minZoom={0.1}
        maxZoom={2.5}
      >
        <Background color="#1e293b" gap={20} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

/**
 * GraphCanvas component wrapped in ReactFlowProvider.
 */
export function GraphCanvas(props) {
  return (
    <ReactFlowProvider>
      <GraphCanvasInner {...props} />
    </ReactFlowProvider>
  );
}

export default GraphCanvas;

