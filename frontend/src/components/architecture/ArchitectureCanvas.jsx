import React, { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  ARCHITECTURE_ENTITY_KIND,
  getEntityKindLabel,
} from '../../contracts/architectureContracts.js';

// Color mappings for entity kinds
const KIND_COLORS = {
  [ARCHITECTURE_ENTITY_KIND.APPLICATION]: { bg: '#172554', stroke: '#3B82F6', text: '#BFDBFE' },
  [ARCHITECTURE_ENTITY_KIND.FRONTEND_APPLICATION]: { bg: '#312E81', stroke: '#6366F1', text: '#C7D2FE' },
  [ARCHITECTURE_ENTITY_KIND.SERVICE]: { bg: '#1E1B4B', stroke: '#6366F1', text: '#A5B4FC' },
  [ARCHITECTURE_ENTITY_KIND.COMPONENT]: { bg: '#082F49', stroke: '#0284C7', text: '#7DD3FC' },
  [ARCHITECTURE_ENTITY_KIND.MODULE]: { bg: '#2E1065', stroke: '#7C3AED', text: '#C4B5FD' },
  [ARCHITECTURE_ENTITY_KIND.CONTROLLER]: { bg: '#172554', stroke: '#2563EB', text: '#BFDBFE' },
  [ARCHITECTURE_ENTITY_KIND.ENDPOINT]: { bg: '#164E63', stroke: '#0891B2', text: '#67E8F9' },
  [ARCHITECTURE_ENTITY_KIND.WORKER]: { bg: '#422006', stroke: '#CA8A04', text: '#FDE68A' },
  [ARCHITECTURE_ENTITY_KIND.DATA_REPOSITORY]: { bg: '#052E16', stroke: '#16A34A', text: '#BBF7D0' },
  [ARCHITECTURE_ENTITY_KIND.DATABASE]: { bg: '#064E3B', stroke: '#059669', text: '#6EE7B7' },
  [ARCHITECTURE_ENTITY_KIND.MESSAGE_BROKER]: { bg: '#451A03', stroke: '#D97706', text: '#FDE68A' },
  [ARCHITECTURE_ENTITY_KIND.QUEUE]: { bg: '#451A03', stroke: '#D97706', text: '#FDE68A' },
  [ARCHITECTURE_ENTITY_KIND.TOPIC]: { bg: '#451A03', stroke: '#F59E0B', text: '#FEF3C7' },
  [ARCHITECTURE_ENTITY_KIND.EXTERNAL_SERVICE]: { bg: '#1E293B', stroke: '#64748B', text: '#CBD5E1' },
  [ARCHITECTURE_ENTITY_KIND.EXTERNAL_API]: { bg: '#1E293B', stroke: '#64748B', text: '#CBD5E1' },
  [ARCHITECTURE_ENTITY_KIND.LIBRARY]: { bg: '#292524', stroke: '#78716C', text: '#E7E5E4' },
  [ARCHITECTURE_ENTITY_KIND.CONFIGURATION_COMPONENT]: { bg: '#27272A', stroke: '#71717A', text: '#E4E4E7' },
};

function getKindStyle(kind) {
  const norm = (kind || '').toLowerCase();
  return (
    KIND_COLORS[norm] || {
      bg: '#162032',
      stroke: '#38BDF8',
      text: '#F8FAFC',
    }
  );
}

function getEntitySubtitle(entity) {
  const metadata = entity.metadata || {};
  const value =
    metadata.qualified_name ||
    metadata.dependency_name ||
    metadata.source_root ||
    metadata.application_namespace ||
    (Array.isArray(entity.namespace) ? entity.namespace.join('/') : null) ||
    entity.logical_id;
  const text = String(value || '');
  return text.length > 22 ? `…${text.slice(-21)}` : text;
}

// Architectural tier classification
function getTierIndex(kind) {
  const norm = (kind || '').toLowerCase();
  if (
    norm === ARCHITECTURE_ENTITY_KIND.APPLICATION ||
    norm === ARCHITECTURE_ENTITY_KIND.FRONTEND_APPLICATION
  ) {
    return 0;
  }
  if (
    norm === ARCHITECTURE_ENTITY_KIND.ENDPOINT ||
    norm === ARCHITECTURE_ENTITY_KIND.EXTERNAL_SERVICE ||
    norm === ARCHITECTURE_ENTITY_KIND.EXTERNAL_API
  ) {
    return 1;
  }
  if (
    norm === ARCHITECTURE_ENTITY_KIND.SERVICE ||
    norm === ARCHITECTURE_ENTITY_KIND.COMPONENT ||
    norm === ARCHITECTURE_ENTITY_KIND.CONTROLLER ||
    norm === ARCHITECTURE_ENTITY_KIND.WORKER ||
    norm === ARCHITECTURE_ENTITY_KIND.DATA_REPOSITORY
  ) {
    return 2;
  }
  if (
    norm === ARCHITECTURE_ENTITY_KIND.MODULE ||
    norm === ARCHITECTURE_ENTITY_KIND.LIBRARY ||
    norm === ARCHITECTURE_ENTITY_KIND.CONFIGURATION_COMPONENT
  ) {
    return 3;
  }
  if (
    norm === ARCHITECTURE_ENTITY_KIND.DATABASE ||
    norm === ARCHITECTURE_ENTITY_KIND.MESSAGE_BROKER ||
    norm === ARCHITECTURE_ENTITY_KIND.QUEUE ||
    norm === ARCHITECTURE_ENTITY_KIND.TOPIC
  ) {
    return 4;
  }
  return 5;
}

const TIER_NAMES = [
  'Applications',
  'Interfaces & External Systems',
  'Services & Components',
  'Modules & Libraries',
  'Persistence & Messaging',
  'Other Entities',
];

const NODE_WIDTH = 170;
const NODE_HEIGHT = 60;
const H_GAP = 28;
const ROW_GAP = 28;
const TIER_GAP = 54;
const PADDING = 40;
const MAX_COLUMNS = 6;

export default function ArchitectureCanvas({
  entities = [],
  relationships = [],
  totalEntities = 0,
  totalRelationships = 0,
  selectedEntity = null,
  onSelectEntity,
}) {
  const [zoom, setZoom] = useState(0.85);
  const [focusedLogicalId, setFocusedLogicalId] = useState(null);
  const viewportRef = useRef(null);
  const pendingScrollPosition = useRef(null);
  const scrollRestoreFrame = useRef(null);
  // Deterministic layout calculations
  const { nodes, links, svgWidth, svgHeight, tierLayouts } = useMemo(() => {
    // 1. Group entities into architectural tiers.
    const tiers = TIER_NAMES.map(() => []);
    entities.forEach((ent) => {
      const tierIdx = getTierIndex(ent.kind);
      tiers[tierIdx].push(ent);
    });

    // 2. Sort stably by logical_id within each tier
    tiers.forEach((tier) => {
      tier.sort((a, b) => (a.logical_id || a.id || '').localeCompare(b.logical_id || b.id || ''));
    });

    // 3. Position nodes deterministically
    const map = new Map();
    const positionedNodes = [];
    let currentY = PADDING + 20;
    let maxCols = 1;
    const layouts = [];

    tiers.forEach((tier, tierIdx) => {
      if (tier.length === 0) return;
      const columns = Math.max(1, Math.min(MAX_COLUMNS, tier.length));
      const rows = Math.max(1, Math.ceil(tier.length / MAX_COLUMNS));
      maxCols = Math.max(maxCols, columns);
      const tierStartY = currentY;

      tier.forEach((ent, colIdx) => {
        const column = colIdx % MAX_COLUMNS;
        const row = Math.floor(colIdx / MAX_COLUMNS);
        const x = PADDING + column * (NODE_WIDTH + H_GAP);
        const y = tierStartY + row * (NODE_HEIGHT + ROW_GAP);
        const node = {
          entity: ent,
          x,
          y,
          tierIdx,
          colIdx: column,
        };
        map.set(ent.logical_id, node);
        map.set(ent.id, node);
        positionedNodes.push(node);
      });
      const contentHeight = rows * NODE_HEIGHT + (rows - 1) * ROW_GAP;
      layouts.push({ name: TIER_NAMES[tierIdx], y: tierStartY - 18 });
      currentY += contentHeight + TIER_GAP;
    });

    const calculatedWidth = Math.max(
      760,
      PADDING * 2 + maxCols * NODE_WIDTH + (maxCols - 1) * H_GAP,
    );
    const calculatedHeight = Math.max(480, currentY + PADDING - TIER_GAP);

    // 4. Connect relationships: only connect if both endpoints are in the loaded entity window
    const validLinks = [];
    relationships.forEach((rel) => {
      const srcNode = map.get(rel.source_logical_id);
      const tgtNode = map.get(rel.target_logical_id);

      if (srcNode && tgtNode) {
        validLinks.push({
          relationship: rel,
          src: srcNode,
          tgt: tgtNode,
        });
      }
    });

    return {
      nodes: positionedNodes,
      links: validLinks,
      svgWidth: calculatedWidth,
      svgHeight: calculatedHeight,
      tierLayouts: layouts,
    };
  }, [entities, relationships]);

  const selectedLogicalId = selectedEntity?.logical_id;
  const focusedLinks = useMemo(
    () =>
      focusedLogicalId
        ? links.filter(
            ({ relationship }) =>
              relationship.source_logical_id === focusedLogicalId ||
              relationship.target_logical_id === focusedLogicalId,
          )
        : links,
    [focusedLogicalId, links],
  );
  const focusedEntityIds = useMemo(() => {
    if (!focusedLogicalId) return null;
    const values = new Set([focusedLogicalId]);
    focusedLinks.forEach(({ relationship }) => {
      values.add(relationship.source_logical_id);
      values.add(relationship.target_logical_id);
    });
    return values;
  }, [focusedLinks, focusedLogicalId]);

  const captureScrollPosition = useCallback(() => {
    if (viewportRef.current) {
      pendingScrollPosition.current = {
        left: viewportRef.current.scrollLeft,
        top: viewportRef.current.scrollTop,
      };
    }
  }, []);

  const selectEntity = (entity) => {
    captureScrollPosition();
    setFocusedLogicalId(entity.logical_id || entity.id);
    onSelectEntity?.(entity);
  };

  useLayoutEffect(() => {
    const position = pendingScrollPosition.current;
    if (!position || !viewportRef.current) return;

    const restore = () => {
      if (!viewportRef.current) return;
      viewportRef.current.scrollLeft = position.left;
      viewportRef.current.scrollTop = position.top;
    };

    // Restore before paint and once more on the next frame. The second pass
    // wins over the browser's deferred focus/scroll-into-view behavior.
    restore();
    scrollRestoreFrame.current = window.requestAnimationFrame(() => {
      restore();
      pendingScrollPosition.current = null;
      scrollRestoreFrame.current = null;
    });

    return () => {
      if (scrollRestoreFrame.current !== null) {
        window.cancelAnimationFrame(scrollRestoreFrame.current);
        scrollRestoreFrame.current = null;
      }
    };
  }, [selectedLogicalId]);

  return (
    <div className="arch-canvas-container">
      {/* Canvas Toolbar & Bounded Window Indicator */}
      <div className="arch-canvas-toolbar">
        <div className="arch-canvas-heading">
          <h3 className="tab-card-title" style={{ fontSize: '1rem', margin: 0 }}>
            Architecture Overview Map
          </h3>
          <span className="arch-window-label" title="Deterministic window of currently loaded entities">
            Backend-first view: {entities.length} of {totalEntities || entities.length} entities
          </span>
        </div>

        <div className="arch-canvas-controls">
          <div className="arch-focus-controls">
            <span className="arch-connector-count" aria-live="polite">
              {focusedLogicalId
                ? `${focusedLinks.length} direct connectors`
                : `${links.length} visible connectors`}
              {totalRelationships > relationships.length
                ? ` · ${relationships.length} of ${totalRelationships} loaded`
                : ''}
            </span>
            <button
              type="button"
              className="arch-focus-reset"
              onClick={() => setFocusedLogicalId(null)}
              disabled={!focusedLogicalId}
            >
              Show all
            </button>
          </div>
          <div className="arch-zoom-controls">
            <button type="button" onClick={() => setZoom((value) => Math.max(0.55, value - 0.15))} aria-label="Zoom out architecture map">−</button>
            <span className="arch-zoom-value">{Math.round(zoom * 100)}%</span>
            <button type="button" onClick={() => setZoom((value) => Math.min(1.45, value + 0.15))} aria-label="Zoom in architecture map">+</button>
            <button type="button" onClick={() => setZoom(0.85)}>Reset</button>
          </div>
        </div>
      </div>

      {/* SVG Canvas Viewport */}
      <div className="arch-canvas-viewport" ref={viewportRef}>
        {entities.length === 0 ? (
          <div className="analyses-empty-box" style={{ marginTop: '4rem' }}>
            <p className="analyses-empty-title">No Entities in Model</p>
            <p className="analyses-empty-desc">
              This architecture version contains no published entities.
            </p>
          </div>
        ) : (
          <svg
            className="arch-svg-canvas"
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            style={{ width: svgWidth * zoom, height: svgHeight * zoom }}
          >
            <defs>
              <marker
                id="arch-arrow"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="rgba(148, 163, 184, 0.6)" />
              </marker>
              <marker
                id="arch-arrow-active"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill="#38BDF8" />
              </marker>
            </defs>

            {/* Tier Background Guidelines */}
            {tierLayouts.map(({ name, y }) => {
              return (
                <g key={name}>
                  <text
                    x={PADDING}
                    y={y}
                    fill="#475569"
                    fontSize="10"
                    fontWeight="600"
                    fontFamily="sans-serif"
                    letterSpacing="0.06em"
                  >
                    {name}
                  </text>
                  <line
                    x1={PADDING}
                    y1={y + 5}
                    x2={svgWidth - PADDING}
                    y2={y + 5}
                    stroke="rgba(255, 255, 255, 0.04)"
                    strokeDasharray="4 4"
                  />
                </g>
              );
            })}

            {/* Connectors / Links */}
            <g className="arch-connectors-group">
              {links.map(({ relationship, src, tgt }) => {
                const isConnectedToSelected =
                  selectedLogicalId &&
                  (relationship.source_logical_id === selectedLogicalId ||
                    relationship.target_logical_id === selectedLogicalId);

                // Start from center-bottom of src, end at center-top of tgt
                const startX = src.x + NODE_WIDTH / 2;
                const startY = src.y + (src.tierIdx <= tgt.tierIdx ? NODE_HEIGHT : 0);
                const endX = tgt.x + NODE_WIDTH / 2;
                const endY = tgt.y + (src.tierIdx <= tgt.tierIdx ? 0 : NODE_HEIGHT);

                const midY = (startY + endY) / 2;
                const pathData = `M ${startX} ${startY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}`;

                return (
                  <path
                    key={relationship.id || `${relationship.source_logical_id}->${relationship.target_logical_id}`}
                    d={pathData}
                    className={`arch-connector ${
                      isConnectedToSelected ? 'active' : ''
                    } ${
                      focusedLogicalId && !isConnectedToSelected ? 'muted' : ''
                    }`}
                    markerEnd={isConnectedToSelected ? 'url(#arch-arrow-active)' : 'url(#arch-arrow)'}
                    vectorEffect="non-scaling-stroke"
                  >
                    <title>
                      {relationship.kind} ({relationship.source_logical_id} &rarr; {relationship.target_logical_id})
                    </title>
                  </path>
                );
              })}
            </g>

            {/* Deterministic Nodes */}
            <g className="arch-nodes-group">
              {nodes.map(({ entity, x, y }) => {
                const isSelected =
                  selectedEntity &&
                  (selectedEntity.logical_id === entity.logical_id || selectedEntity.id === entity.id);
                const style = getKindStyle(entity.kind);
                const isMuted = focusedEntityIds && !focusedEntityIds.has(entity.logical_id);
                const subtitle = getEntitySubtitle(entity);

                return (
                  <g
                    key={entity.logical_id || entity.id}
                    className={`arch-map-node ${isSelected ? 'selected' : ''} ${isMuted ? 'muted' : ''}`}
                    transform={`translate(${x}, ${y})`}
                    onPointerDown={(event) => {
                      captureScrollPosition();
                      event.preventDefault();
                    }}
                    onClick={() => selectEntity(entity)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        selectEntity(entity);
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-label={`Select ${entity.name || entity.logical_id} (${getEntityKindLabel(entity.kind)})`}
                    aria-pressed={isSelected}
                  >
                    <title>
                      {entity.name || entity.logical_id} — {subtitle}
                    </title>
                    <rect
                      width={NODE_WIDTH}
                      height={NODE_HEIGHT}
                      rx={8}
                      ry={8}
                      fill={style.bg}
                      stroke={isSelected ? '#38BDF8' : style.stroke}
                      strokeWidth={isSelected ? 2.5 : 1.25}
                      vectorEffect="non-scaling-stroke"
                    />

                    {/* A nested viewport clips every label to the card's inner
                        width. SVG text does not honor CSS overflow by itself. */}
                    <svg
                      className="arch-map-node-content"
                      width={NODE_WIDTH - 8}
                      height={NODE_HEIGHT}
                      overflow="hidden"
                      aria-hidden="true"
                    >
                      {/* Kind Indicator Pill */}
                      <rect
                        x={8}
                        y={8}
                        width={NODE_WIDTH - 16}
                        height={16}
                        rx={4}
                        fill="rgba(0, 0, 0, 0.25)"
                      />
                      <text
                        x={14}
                        y={19}
                        fill={style.text}
                        fontSize="9"
                        fontWeight="600"
                        fontFamily="sans-serif"
                        letterSpacing="0.04em"
                      >
                        {getEntityKindLabel(entity.kind)}
                      </text>

                      {/* Entity Name */}
                      <text x={14} y={40} className="arch-map-node-title">
                        {(entity.name || entity.logical_id).length > 20
                          ? (entity.name || entity.logical_id).slice(0, 19) + '…'
                          : entity.name || entity.logical_id}
                      </text>

                      {/* Logical ID Subtext */}
                      <text x={14} y={52} className="arch-map-node-subtitle">
                        {subtitle}
                      </text>
                    </svg>
                  </g>
                );
              })}
            </g>
          </svg>
        )}
      </div>
    </div>
  );
}

