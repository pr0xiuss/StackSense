/** C2 v1 ingress. Schema is generated from the frozen Python PreparedDiagram. */
import schema from './diagramSchema.json';

const encoder = new TextEncoder();
const fail = () => { throw new Error('diagram_integrity_error'); };
const compare = (a, b) => {
  const x = encoder.encode(a), y = encoder.encode(b);
  for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] - y[i];
  return x.length - y.length;
};
export function canonicalJSON(value) {
  if (value === null || typeof value === 'boolean') return String(value);
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) fail();
    return String(value);
  }
  if (typeof value === 'string') {
    if (/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(value)) fail();
    return '"' + value.replace(/["\\\u0000-\u001f]/g, c => c === '"' ? '\\"' : c === '\\' ? '\\\\' : '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0')) + '"';
  }
  if (Array.isArray(value)) return '[' + value.map(canonicalJSON).join(',') + ']';
  if (value && Object.getPrototypeOf(value) === Object.prototype) return '{' + Object.keys(value).sort(compare).map(k => canonicalJSON(k) + ':' + canonicalJSON(value[k])).join(',') + '}';
  fail();
}
export async function sha256(value) {
  const bytes = typeof value === 'string' ? encoder.encode(value) : value;
  return Array.from(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('');
}
const sets = new Set('nodes edges groups ports labels routes annotations provenance legend counts reasons omitted root_ids selected_entity_ids entity_kinds statuses relationship_kinds boundary_ids multi_parent visible_member_ids subject_ids evidence records parents layers limitations members'.split(' '));
function orderKey(item) {
  if (item && typeof item === 'object') {
    for (const k of ['id', 'edge_id', 'group_id', 'key']) if (k in item) return String(item[k]);
    for (const k of ['record', 'relationship', 'child']) if (item[k]?.id) return item[k].id;
    if ('member' in item) return item.member;
  }
  return typeof item === 'string' ? item : canonicalJSON(item);
}
function normalize(value, owner = '') {
  if (Array.isArray(value)) {
    const result = value.map(v => normalize(v));
    if (sets.has(owner) || (owner === 'glyphs' && result[0]?.commands)) result.sort((a, b) => compare(orderKey(a), orderKey(b)));
    return result;
  }
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, normalize(v, k)]));
  return value;
}
export const diagramDigest = async (domain, value) => sha256(canonicalJSON([domain, '1.0.0', normalize(value)]));
export function deepFreeze(value) {
  if (value && typeof value === 'object') { Object.values(value).forEach(deepFreeze); if (!Object.isFrozen(value)) Object.freeze(value); }
  return value;
}
function check(value, rule, depth = 0) {
  if (depth > 64) fail();
  if (rule.$ref) return check(value, schema.$defs[rule.$ref.split('/').at(-1)], depth + 1);
  const variants = rule.anyOf || rule.oneOf;
  if (variants) {
    let matches = 0;
    for (const branch of variants) { try { check(value, branch, depth + 1); matches++; } catch { /* alternate */ } }
    if (!matches || (rule.oneOf && matches !== 1)) fail();
  }
  if ('const' in rule && value !== rule.const) fail();
  if (rule.enum && !rule.enum.includes(value)) fail();
  if (rule.type === 'null' && value !== null) fail();
  if (rule.type === 'boolean' && typeof value !== 'boolean') fail();
  if (rule.type === 'integer' && (!Number.isSafeInteger(value) || Object.is(value, -0) || value < (rule.minimum ?? -Number.MAX_SAFE_INTEGER) || value > (rule.maximum ?? Number.MAX_SAFE_INTEGER) || ('exclusiveMinimum' in rule && value <= rule.exclusiveMinimum))) fail();
  if (rule.type === 'string') {
    if (typeof value !== 'string' || value.length < (rule.minLength ?? 0) || value.length > (rule.maxLength ?? 16384) || encoder.encode(value).length > 16384 || (rule.pattern && !new RegExp(rule.pattern).test(value))) fail();
    if (rule.format === 'uuid' && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value)) fail();
    if (rule.format === 'date-time' && !Number.isFinite(Date.parse(value))) fail();
  }
  if (rule.type === 'array') {
    if (!Array.isArray(value) || value.length < (rule.minItems ?? 0) || value.length > (rule.maxItems ?? 100000)) fail();
    value.forEach(v => check(v, rule.items, depth + 1));
  }
  if (rule.type === 'object') {
    if (!value || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) fail();
    for (const key of rule.required || []) if (!Object.hasOwn(value, key)) fail();
    for (const [key, v] of Object.entries(value)) {
      const child = rule.properties?.[key];
      if (child) check(v, child, depth + 1);
      else if (rule.additionalProperties === false) fail();
      else if (typeof rule.additionalProperties === 'object') check(v, rule.additionalProperties, depth + 1);
      const cap = ['logical_id', 'source_fact_key'].includes(key) ? 8192 : key === 'font_notice' ? 16384 : 4096;
      if (typeof v === 'string' && encoder.encode(v).length > cap) fail();
    }
  }
}
function ingress(value, definition, maxBytes) {
  check(value, schema.$defs[definition]);
  if (definition === 'DiagramSpec' && (value.nodes.length > 1000 || value.edges.length > 4000 || value.groups.length > 256)) fail();
  if (definition === 'LayoutSpec') {
    if (value.nodes.length > 1000 || value.groups.length > 256 || value.routes.length > 4000 || value.glyphs.length > 1024 || value.glyphs.reduce((n,g) => n+g.commands.length,0) > 600000 || value.labels.reduce((n,l) => n+l.glyphs.length,0) > 200000) fail();
  }
  if (encoder.encode(canonicalJSON(value)).length > maxBytes) fail();
}
function unique(items, key = 'id') { const ids = items.map(x => x[key]); if (new Set(ids).size !== ids.length) fail(); }
export async function validateDiagramSpec(value) {
  ingress(value, 'DiagramSpec', 16 * 1024 * 1024);
  const { semantic_digest, ...payload } = value;
  if (await diagramDigest('ss.diagram.semantic', payload) !== semantic_digest || value.view.template !== value.template) fail();
  unique(value.nodes); unique(value.edges); unique(value.groups); unique(value.provenance.map(p => p.record));
  await Promise.all(value.nodes.map(async node => { if (node.id !== 'dn:' + await diagramDigest('ss.diagram.node', [value.diagram_id, node.entity])) fail(); }));
  await Promise.all(value.edges.map(async edge => {
    const refs = edge.members.map(m => m.relationship).sort((a,b) => compare(a.id,b.id));
    if (edge.id !== 'de:' + await diagramDigest('ss.diagram.edge', [value.diagram_id, refs, edge.source_visual_id, edge.target_visual_id])) fail();
  }));
  const nodes = new Map(value.nodes.map(n => [n.id, n])), groups = new Map(value.groups.map(g => [g.id, g]));
  const all = new Set([...nodes.keys(), ...groups.keys()]);
  if (all.size !== nodes.size + groups.size) fail();
  for (const node of nodes.values()) if (node.group_id && !groups.has(node.group_id)) fail();
  for (const group of groups.values()) {
    const seen = new Set([group.id]); let parent = group.parent_group_id;
    while (parent) { if (seen.has(parent) || !groups.has(parent)) fail(); seen.add(parent); parent = groups.get(parent).parent_group_id; }
    if (group.visible_member_ids.some(id => !all.has(id))) fail();
  }
  for (const edge of value.edges) {
    if (!all.has(edge.source_visual_id) || !all.has(edge.target_visual_id) || !edge.members.length) fail();
    for (const member of edge.members) {
      if (nodes.has(edge.source_visual_id) && canonicalJSON(nodes.get(edge.source_visual_id).entity) !== canonicalJSON(member.source)) fail();
      if (nodes.has(edge.target_visual_id) && canonicalJSON(nodes.get(edge.target_visual_id).entity) !== canonicalJSON(member.target)) fail();
    }
    if (edge.members.some(m => m.kind !== edge.members[0].kind || m.status !== edge.members[0].status) || edge.bundle !== (edge.members.length > 1)) fail();
  }
  const evidence = new Set(value.provenance.map(p => p.record.id));
  for (const node of value.nodes) if (node.evidence.some(e => !evidence.has(e.id))) fail();
  return deepFreeze(value);
}
export async function validateLayoutSpec(value, spec) {
  ingress(value, 'LayoutSpec', 32 * 1024 * 1024);
  const { layout_digest, ...payload } = value;
  if (await diagramDigest('ss.diagram.layout', payload) !== layout_digest || value.diagram_id !== spec.diagram_id || value.semantic_digest !== spec.semantic_digest) fail();
  for (const [items, expected] of [[value.nodes, spec.nodes], [value.groups, spec.groups], [value.routes, spec.edges]]) {
    const key = items === value.routes ? 'edge_id' : 'id'; unique(items, key);
    if (items.length !== expected.length || items.some(x => !expected.some(e => e.id === x[key]))) fail();
  }
  unique(value.labels); unique(value.ports); unique(value.glyphs);
  if (value.routes.reduce((n,r) => n+r.sections.length,0) > 50000 || value.glyphs.length > 1024 || value.labels.reduce((n,l) => n+l.glyphs.length,0) > 200000 || value.glyphs.reduce((n,g) => n+g.commands.length,0) > 600000) fail();
  for (const glyph of value.glyphs) for (const command of glyph.commands) if (command.operands.length !== { M:2,L:2,Q:4,C:6,Z:0 }[command.command]) fail();
  const owners = new Set([...spec.nodes, ...spec.groups, ...spec.edges].map(x => x.id));
  const glyphs = new Set(value.glyphs.map(g => g.id));
  const b = value.bounds;
  const inside = p => p.x >= b.x && p.y >= b.y && p.x <= b.x + b.width && p.y <= b.y + b.height;
  for (const row of [...value.nodes, ...value.groups, ...value.labels]) if (!inside(row.box) || !inside({ x: row.box.x + row.box.width, y: row.box.y + row.box.height })) fail();
  for (const label of value.labels) if (!owners.has(label.owner_id) || label.glyphs.some(g => !glyphs.has(g.glyph_id))) fail();
  const boxes = new Map([...value.nodes,...value.groups].map(row => [row.id,row.box]));
  const within = (p,box) => box && p.x >= box.x && p.y >= box.y && p.x <= box.x+box.width && p.y <= box.y+box.height;
  for (const port of value.ports) if (!within(port.point,boxes.get(port.owner_id))) fail();
  for (const route of value.routes) {
    const edge = spec.edges.find(e => e.id === route.edge_id);
    if (!route.sections.length || !within(route.sections[0].start,boxes.get(edge.source_visual_id)) || !within(route.sections.at(-1).end,boxes.get(edge.target_visual_id))) fail();
    for (let i=0;i<route.sections.length;i++) {
      const section=route.sections[i];
      if (![section.start,...section.bends,section.end].every(inside) || (i && canonicalJSON(route.sections[i-1].end)!==canonicalJSON(section.start))) fail();
    }
  }
  return deepFreeze(value);
}
export async function validateDescriptor(value, spec, layout) {
  ingress(value, 'DiagramArtifactDescriptor', 256 * 1024);
  const m = value.manifest, r = value.reference;
  if (m.diagram_id !== spec.diagram_id || m.semantic_digest !== spec.semantic_digest || m.membership_digest !== spec.membership_digest || m.layout_digest !== layout.layout_digest || m.binding.slot.template !== spec.template) fail();
  for (const k of ['scope', 'binding', 'input_fingerprint', 'generation_id', 'artifact_id']) if (canonicalJSON(m[k]) !== canonicalJSON(r[k])) fail();
  for (const k of Object.keys(spec.scope)) if (m.scope[k] !== spec.scope[k]) fail();
  const bytes = encoder.encode(canonicalJSON(m));
  if (r.size_bytes !== bytes.length || r.digests.content !== await sha256(bytes) || r.digests.spec !== spec.semantic_digest || r.digests.layout !== layout.layout_digest) fail();
  const names = { spec: ['spec.json', 'application/json'], layout: ['layout.json', 'application/json'], members: ['members.json', 'application/json'], svg: ['scene.svg', 'image/svg+xml'] };
  unique(m.members, 'member'); if (m.members.length !== 4) fail();
  if (m.members.reduce((n,member) => n+member.size_bytes,0)>128*1024*1024) fail();
  for (const member of m.members) {
    if (!names[member.member] || member.file_name !== names[member.member][0] || member.media_type !== names[member.member][1]) fail();
    if (member.member === 'spec' || member.member === 'layout') {
      const data = encoder.encode(canonicalJSON(normalize(member.member === 'spec' ? spec : layout)));
      if (member.size_bytes !== data.length || member.sha256 !== await sha256(data)) fail();
    }
  }
  return deepFreeze(value);
}
export async function validatePreparedDiagram(value) {
  if (!value || Object.keys(value).sort().join(',') !== 'descriptor,layout,spec') fail();
  await validateDiagramSpec(value.spec); await validateLayoutSpec(value.layout, value.spec);
  await validateDescriptor(value.descriptor, value.spec, value.layout); return deepFreeze(value);
}

export function validateMemberPage(value, generation, semanticDigest, maxItems = 200) {
  const keys = ['generation_id', 'semantic_digest', 'group_id', 'items', 'total', 'next_cursor'];
  if (!value || Object.keys(value).length !== keys.length || keys.some(k => !Object.hasOwn(value, k)) || value.generation_id !== generation || value.semantic_digest !== semanticDigest || !Array.isArray(value.items) || value.items.length > maxItems || !Number.isSafeInteger(value.total) || value.total < value.items.length || (value.next_cursor !== null && (typeof value.next_cursor !== 'string' || value.next_cursor.length > 4096))) fail();
  if (value.group_id !== null && !/^dg:[0-9a-f]{64}$/.test(value.group_id)) fail();
  for (const item of value.items) {
    if (!item || Object.keys(item).sort().join(',') !== 'reason,record') fail();
    check(item.record, schema.$defs.Ref);
    if (item.reason !== null && !['granularity','filter','depth','scene_budget','bundle','collapsed','unavailable_source','unsupported_detail','label_clipped'].includes(item.reason)) fail();
  }
  return deepFreeze(value);
}
