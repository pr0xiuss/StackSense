import { webcrypto } from 'node:crypto';
import { describe, it, expect, vi, beforeAll } from 'vitest';
import { performance } from 'node:perf_hooks';
import { diagramFixture } from '../diagramFixtures.js';
import { validatePreparedDiagram } from '../../src/contracts/diagramContracts.js';
import { toReactFlow } from '../../src/services/diagramAdapter.js';
beforeAll(() => vi.stubGlobal('crypto', webcrypto));
describe('real labelled stress data; NOT browser interaction evidence', () => {
  for (const count of [150, 500]) it(`validates and maps ${count} real ELK nodes without relayout`, async () => {
    const prepared = diagramFixture(`stress${count}`);
    const started = performance.now(); await validatePreparedDiagram(prepared);
    const validationMs = performance.now() - started;
    const samples = [];
    for (let i=0;i<20;i++) {
      const start = performance.now();
      const mapped = toReactFlow(prepared.spec, prepared.layout, { selected_ref: prepared.spec.nodes[i].entity });
      expect(mapped.nodes).toHaveLength(count);
      expect(mapped.nodes.find(n => n.selected).data.item.entity).toEqual(prepared.spec.nodes[i].entity);
      samples.push(performance.now()-start);
    }
    samples.sort((a,b)=>a-b);
    console.info('M4_B4_ADAPTER_MEASUREMENT', JSON.stringify({ count, validationMs, minMs:samples[0], p95Ms:samples[18], maxMs:samples.at(-1), scope:'Node/jsdom pure adapter only, not browser rendering/selection/pan' }));
  });
});
