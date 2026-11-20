import { webcrypto } from 'node:crypto';
import { describe, it, expect, vi, beforeAll } from 'vitest';
import { diagramFixture, templates } from '../diagramFixtures.js';
import { validatePreparedDiagram, validateDiagramSpec, validateLayoutSpec, validateDescriptor, diagramDigest } from '../../src/contracts/diagramContracts.js';
beforeAll(() => vi.stubGlobal('crypto', webcrypto));
describe('C2 prepared contract and real ELK geometry', () => {
  for (const template of templates) it(`accepts and deeply freezes ${template}`, async () => {
    const data = diagramFixture(template);
    const result = await validatePreparedDiagram(data);
    expect(result.spec.template).toBe(template);
    expect(Object.isFrozen(result.layout.glyphs[0].commands[0])).toBe(true);
    expect(result.layout.nodes.length).toBeGreaterThan(0);
  });
  it('rejects modified semantic payload, schema and unknown fields', async () => {
    for (const change of [s => { s.nodes[0].name += 'forged'; }, s => { s.diagram_schema_version = '2.0.0'; }, s => { s.extra = true; }]) {
      const data = diagramFixture(); change(data.spec);
      await expect(validateDiagramSpec(data.spec)).rejects.toThrow('diagram_integrity_error');
    }
  });
  it('freezes mutable children even if the host already froze the root', async () => {
    const data=diagramFixture(); Object.freeze(data.spec);
    await validatePreparedDiagram(data);
    expect(Object.isFrozen(data.spec.nodes[0].entity)).toBe(true);
    expect(()=>{data.spec.nodes[0].entity.logical_id='changed';}).toThrow();
  });
  it('rejects layout/descriptor alterations and endpoint loss even with rehashed labels', async () => {
    const data = diagramFixture(); data.layout.nodes.pop();
    const { layout_digest, ...payload } = data.layout;
    data.layout.layout_digest = await diagramDigest('ss.diagram.layout', payload);
    await expect(validateLayoutSpec(data.layout, data.spec)).rejects.toThrow();
    const original = diagramFixture(); original.descriptor.reference.size_bytes++;
    await expect(validateDescriptor(original.descriptor, original.spec, original.layout)).rejects.toThrow();
  });
});
