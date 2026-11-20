import { renderHook, act, waitFor } from '@testing-library/react';
import { webcrypto } from 'node:crypto';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { useDiagramView } from '../../src/hooks/useDiagramView.js';
import { diagramDigest } from '../../src/contracts/diagramContracts.js';
import { diagramFixture } from '../diagramFixtures.js';
beforeAll(() => vi.stubGlobal('crypto', webcrypto));
const request = depth => ({ root_ids: [], entity_kinds: [], statuses: [], relationship_kinds: [], include_contains: false, depth, direction: 'outgoing', collapsed_group_ids: [], selected_entity_ids: [] });
describe('transient request guards', () => {
  it('aborts stale replies and preserves selection/camera across same-base refresh', async () => {
    const prepared = diagramFixture(), calls = [];
    const requestView = vi.fn((body, signal) => new Promise(resolve => calls.push({ body, signal, resolve })));
    const { result, rerender } = renderHook(({ value }) => useDiagramView(value, requestView, vi.fn()), { initialProps: { value: prepared } });
    await waitFor(() => expect(result.current.state.ready).toBe(true));
    act(() => result.current.select(prepared.spec.nodes[0].entity));
    act(() => result.current.focus(prepared.spec.nodes[0].id));
    const focus = result.current.state.focus_visual_id;
    rerender({ value: structuredClone(prepared) });
    await waitFor(() => expect(result.current.state.ready).toBe(true));
    expect(result.current.state.selected_ref).toEqual(prepared.spec.nodes[0].entity);
    expect(result.current.state.focus_visual_id).toEqual(focus);
    act(() => { void result.current.derive(request(1)); });
    await waitFor(() => expect(calls).toHaveLength(1));
    act(() => { void result.current.derive(request(2)); });
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[0].signal.aborted).toBe(true);
    async function resolve(call) {
      const reply = { base_generation_id: prepared.descriptor.reference.generation_id, base_semantic_digest: prepared.spec.semantic_digest, request_digest: await diagramDigest('ss.diagram.view', call.body), spec: prepared.spec, layout: prepared.layout };
      await act(async () => call.resolve(reply));
    }
    await resolve(calls[1]);
    await waitFor(() => expect(result.current.state.busy).toBe(false));
    await resolve(calls[0]);
    expect(result.current.state.filters.depth).toBe(2);
  });
});
