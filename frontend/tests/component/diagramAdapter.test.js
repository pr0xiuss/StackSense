import { describe, it, expect } from 'vitest';
import { diagramFixture, templates } from '../diagramFixtures.js';
import { toReactFlow } from '../../src/services/diagramAdapter.js';
describe('pure supplied-geometry adapter', () => {
  for (const template of templates) it(`maps ${template} without moving inputs`, () => {
    const value = diagramFixture(template), before = JSON.stringify(value);
    const result = toReactFlow(value.spec, value.layout);
    expect(result.nodes).toHaveLength(value.spec.nodes.length + value.spec.groups.length);
    expect(result.edges.map(e => e.id)).toEqual(value.spec.edges.map(e => e.id));
    const boxes = new Map([...value.layout.nodes, ...value.layout.groups].map(n => [n.id, n.box]));
    for (const node of result.nodes) {
      const parent = boxes.get(node.parentId) || { x: 0, y: 0 };
      expect(node.position.x).toBe((boxes.get(node.id).x - parent.x) / 1000);
      expect(node.position.y).toBe((boxes.get(node.id).y - parent.y) / 1000);
      expect(node.draggable).toBe(false);
    }
    expect(JSON.stringify(value)).toBe(before);
  });
  it('collapse hides descendants without synthetic edges or changing canonical refs', () => {
    const value = diagramFixture('component_architecture');
    const group = value.spec.groups.find(g => g.visible_member_ids.length);
    if (!group) throw new Error('fixture must have a real group');
    const result = toReactFlow(value.spec, value.layout, { collapsed_groups: [group.id] });
    expect(result.nodes.some(n => n.hidden)).toBe(true);
    expect(result.edges).toHaveLength(value.spec.edges.length);
  });
});
