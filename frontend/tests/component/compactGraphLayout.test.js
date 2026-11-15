import { describe, it, expect } from 'vitest';
import ELK from 'elkjs/lib/elk.bundled.js';
import { compactGraphLayers } from '../../src/workers/compactGraphLayout.js';

describe('compact graph layer presentation', () => {
  it('wraps a real ELK high-fanout graph without omitting or overlapping nodes', async () => {
    const children = Array.from({ length: 94 }, (_, i) => ({ id: String(i), width: 220, height: 80 }));
    const edges = children.slice(1).map((n) => ({ id: `edge-${n.id}`, sources: ['0'], targets: [n.id] }));
    const graph = await new ELK().layout({ id: 'root', layoutOptions: {
      'elk.algorithm': 'layered', 'elk.direction': 'DOWN', 'elk.randomSeed': '42',
    }, children, edges });
    const positions = compactGraphLayers(graph.children);
    expect(Object.keys(positions)).toHaveLength(94);
    const boxes = Object.values(positions);
    expect(Math.max(...boxes.map((p) => p.x + p.width))).toBeLessThanOrEqual(1024);
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i]; const b = boxes[j];
        expect(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y).toBe(true);
      }
    }
    expect(positions['0'].y).toBeLessThan(positions['1'].y);
    expect(compactGraphLayers([...graph.children].reverse())).toEqual(positions);
  });

  it('handles disconnected nodes, empty input and dimensions without mutation', () => {
    expect(compactGraphLayers([])).toEqual({});
    const nodes = Array.from({ length: 12 }, (_, i) => ({ id: String(i), x: i * 900, y: 0, width: 240, height: 100 }));
    const original = structuredClone(nodes);
    const positions = compactGraphLayers(nodes);
    expect(nodes).toEqual(original);
    expect(new Set(Object.values(positions).map((p) => p.y)).size).toBe(3);
  });
});
