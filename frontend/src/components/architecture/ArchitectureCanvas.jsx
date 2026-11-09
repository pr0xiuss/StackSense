import React, { useMemo } from 'react';
import {
  ARCHITECTURE_ENTITY_KIND,
  getEntityKindLabel,
} from '../../contracts/architectureContracts.js';

// Color mappings for entity kinds
const KIND_COLORS = {
  [ARCHITECTURE_ENTITY_KIND.SERVICE]: { bg: '#1E1B4B', stroke: '#6366F1', text: '#A5B4FC' },
  [ARCHITECTURE_ENTITY_KIND.COMPONENT]: { bg: '#082F49', stroke: '#0284C7', text: '#7DD3FC' },
  [ARCHITECTURE_ENTITY_KIND.MODULE]: { bg: '#2E1065', stroke: '#7C3AED', text: '#C4B5FD' },
  [ARCHITECTURE_ENTITY_KIND.DATABASE]: { bg: '#064E3B', stroke: '#059669', text: '#6EE7B7' },
  [ARCHITECTURE_ENTITY_KIND.DATA_STORE]: { bg: '#064E3B', stroke: '#10B981', text: '#A7F3D0' },
  [ARCHITECTURE_ENTITY_KIND.QUEUE]: { bg: '#451A03', stroke: '#D97706', text: '#FDE68A' },
  [ARCHITECTURE_ENTITY_KIND.API_ENDPOINT]: { bg: '#164E63', stroke: '#0891B2', text: '#67E8F9' },
  [ARCHITECTURE_ENTITY_KIND.EXTERNAL_SYSTEM]: { bg: '#1E293B', stroke: '#475569', text: '#CBD5E1' },
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

// Architectural tier classification
function getTierIndex(kind) {
  const norm = (kind || '').toLowerCase();
  if (norm === ARCHITECTURE_ENTITY_KIND.API_ENDPOINT || norm === ARCHITECTURE_ENTITY_KIND.EXTERNAL_SYSTEM) {
    return 0; // Ingress / Edge
  }
  if (
    norm === ARCHITECTURE_ENTITY_KIND.SERVICE ||
    norm === ARCHITECTURE_ENTITY_KIND.COMPONENT ||
    norm === ARCHITECTURE_ENTITY_KIND.MODULE
  ) {
    return 1; // Compute & Logic
  }
  if (
    norm === ARCHITECTURE_ENTITY_KIND.DATABASE ||
    norm === ARCHITECTURE_ENTITY_KIND.DATA_STORE ||
    norm === ARCHITECTURE_ENTITY_KIND.QUEUE
  ) {
    return 2; // Storage & Messaging
  }
  return 3; // Other
}

const TIER_NAMES = ['Ingress & Boundaries', 'Services & Components', 'Persistence & Messaging', 'Other Entities'];

const NODE_WIDTH = 170;
const NODE_HEIGHT = 60;
const H_GAP = 28;
const V_TIER_GAP = 95;
const PADDING = 40;

export default function ArchitectureCanvas({
  entities = [],
  relationships = [],
  totalEntities = 0,
  totalRelationships = 0,
  selectedEntity = null,
  onSelectEntity,
}) {
  // Deterministic layout calculations
  const { nodeMap, nodes, links, svgWidth, svgHeight } = useMemo(() => {
    // 1. Group entities into 4 tiers
    const tiers = [[], [], [], []];
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
    let maxCols = 1;

    tiers.forEach((tier, tierIdx) => {
      if (tier.length > maxCols) maxCols = tier.length;
      const y = PADDING + tierIdx * (NODE_HEIGHT + V_TIER_GAP);

      tier.forEach((ent, colIdx) => {
        const x = PADDING + colIdx * (NODE_WIDTH + H_GAP);
        const node = {
          entity: ent,
          x,
          y,
          tierIdx,
          colIdx,
        };
        map.set(ent.logical_id, node);
        map.set(ent.id, node);
        positionedNodes.push(node);
      });
    });

    const calculatedWidth = Math.max(760, PADDING * 2 + maxCols * (NODE_WIDTH + H_GAP));
    const calculatedHeight = Math.max(480, PADDING * 2 + tiers.length * (NODE_HEIGHT + V_TIER_GAP));

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
      nodeMap: map,
      nodes: positionedNodes,
      links: validLinks,
      svgWidth: calculatedWidth,
      svgHeight: calculatedHeight,
    };
  }, [entities, relationships]);

  const selectedLogicalId = selectedEntity?.logical_id;

  return (
    <div className="arch-canvas-container">
      {/* Canvas Toolbar & Bounded Window Indicator */}
      <div className="arch-canvas-toolbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <h3 className="tab-card-title" style={{ fontSize: '1rem', margin: 0 }}>
            Architecture Overview Map
          </h3>
          <span className="arch-window-label" title="Deterministic window of currently loaded entities">
            Bounded window: {entities.length} of {totalEntities || entities.length} entities
          </span>
        </div>

        <span style={{ fontSize: '0.775rem', color: '#94A3B8' }}>
          {links.length} visible connectors · Use Tab & Enter to select
        </span>
      </div>

      {/* SVG Canvas Viewport */}
      <div className="arch-canvas-viewport">
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
            style={{ width: svgWidth, height: svgHeight }}
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
            {TIER_NAMES.map((name, idx) => {
              const y = PADDING + idx * (NODE_HEIGHT + V_TIER_GAP) - 14;
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
                    textTransform="uppercase"
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
                    className={`arch-connector ${isConnectedToSelected ? 'active' : ''}`}
                    markerEnd={isConnectedToSelected ? 'url(#arch-arrow-active)' : 'url(#arch-arrow)'}
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

                return (
                  <g
                    key={entity.logical_id || entity.id}
                    className={`arch-node ${isSelected ? 'selected' : ''}`}
                    transform={`translate(${x}, ${y})`}
                    onClick={() => onSelectEntity && onSelectEntity(entity)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onSelectEntity && onSelectEntity(entity);
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-label={`Select ${entity.name || entity.logical_id} (${getEntityKindLabel(entity.kind)})`}
                    aria-pressed={isSelected}
                  >
                    <rect
                      width={NODE_WIDTH}
                      height={NODE_HEIGHT}
                      rx={8}
                      ry={8}
                      fill={style.bg}
                      stroke={isSelected ? '#38BDF8' : style.stroke}
                      strokeWidth={isSelected ? 2.5 : 1.25}
                    />

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
                      textTransform="uppercase"
                    >
                      {getEntityKindLabel(entity.kind)}
                    </text>

                    {/* Entity Name */}
                    <text
                      x={14}
                      y={40}
                      className="arch-node-title"
                    >
                      {(entity.name || entity.logical_id).length > 20
                        ? (entity.name || entity.logical_id).slice(0, 19) + '…'
                        : entity.name || entity.logical_id}
                    </text>

                    {/* Logical ID Subtext */}
                    <text
                      x={14}
                      y={52}
                      className="arch-node-subtitle"
                    >
                      {entity.logical_id.length > 24
                        ? entity.logical_id.slice(0, 23) + '…'
                        : entity.logical_id}
                    </text>
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

