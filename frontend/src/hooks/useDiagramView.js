import { useCallback, useEffect, useRef, useState } from 'react';
import { validateDiagramSpec, validateLayoutSpec, validatePreparedDiagram, diagramDigest, canonicalJSON } from '../contracts/diagramContracts.js';

const errorCodes = new Set('diagram_authentication_required diagram_forbidden diagram_not_found diagram_not_ready diagram_scope_mismatch diagram_generation_changed diagram_cursor_invalid diagram_cursor_expired diagram_generation_unavailable diagram_input_invalid diagram_contract_unsupported diagram_limit_exceeded diagram_range_unsupported diagram_runtime_unavailable diagram_store_unavailable diagram_source_unavailable diagram_timeout diagram_integrity_error diagram_internal_error'.split(' '));
const safeError = error => ({ error: { code: errorCodes.has(error?.error?.code) ? error.error.code : 'diagram_internal_error', message: 'Diagram operation could not be completed.', details: { dimension: null, actual: null, limit: null, request_id: null } } });
export function useDiagramView(prepared, requestView, onError) {
  const base = prepared?.descriptor?.reference;
  const key = base ? `${base.generation_id}:${prepared.spec.semantic_digest}` : '';
  const current = useRef(key), loaded = useRef(null); current.current = key;
  const sequence = useRef(0), pending = useRef(null), membersPending = useRef(null);
  const [state, setState] = useState({ ready: false, busy: false, error: null, selected_ref: null, focus_visual_id: null, collapsed_groups: [], filters: {}, camera: null, request_id: 0, base_generation_id: null, base_digest: null, spec: null, layout: null });
  useEffect(() => {
    let alive = true; const id = ++sequence.current;
    pending.current?.abort(); membersPending.current?.abort();
    const changed = loaded.current !== key;
    if (changed) setState(s => ({ ...s, ready: false, busy: false, error: null, selected_ref: null, focus_visual_id: null, collapsed_groups: [], camera: null, filters: {}, spec: null, layout: null }));
    if (!prepared) return () => { alive = false; };
    validatePreparedDiagram(prepared).then(value => {
      if (!alive || sequence.current !== id || current.current !== key) return;
      loaded.current = key;
      setState(s => ({ ...s, ready: true, spec: changed ? value.spec : s.spec, layout: changed ? value.layout : s.layout, base_generation_id: base.generation_id, base_digest: value.spec.semantic_digest, collapsed_groups: changed ? value.spec.groups.filter(g => g.collapsed_default).map(g => g.id) : s.collapsed_groups }));
    }).catch(error => { if (alive && current.current === key) { const result = safeError(error); setState(s => ({ ...s, ready: false, error: result })); onError?.(result); } });
    return () => { alive = false; pending.current?.abort(); membersPending.current?.abort(); };
  }, [key, prepared]); // immutable props: same identity refresh cannot trigger camera effects
  const select = useCallback(ref => setState(s => ({ ...s, selected_ref: ref })), []);
  const focus = useCallback(id => setState(s => {
    const groups = new Map((s.spec?.groups || []).map(g => [g.id, g]));
    const ancestors = new Set(); let parent = groups.get(id)?.parent_group_id || s.spec?.nodes.find(n => n.id === id)?.group_id;
    while (parent) { ancestors.add(parent); parent = groups.get(parent)?.parent_group_id; }
    return { ...s, collapsed_groups: s.collapsed_groups.filter(g => !ancestors.has(g)), focus_visual_id: { id, sequence: (s.focus_visual_id?.sequence || 0) + 1 } };
  }), []);
  const toggleGroup = useCallback(id => setState(s => ({ ...s, collapsed_groups: s.collapsed_groups.includes(id) ? s.collapsed_groups.filter(g => g !== id) : [...s.collapsed_groups, id] })), []);
  const derive = useCallback(async request => {
    pending.current?.abort(); const controller = new AbortController(); pending.current = controller;
    const id = ++sequence.current, expected = current.current;
    setState(s => ({ ...s, busy: true, error: null, request_id: id }));
    try {
      const requestHash = await diagramDigest('ss.diagram.view', request);
      const reply = await requestView(request, controller.signal);
      if (controller.signal.aborted || id !== sequence.current || expected !== current.current) return;
      if (reply.base_generation_id !== base.generation_id || reply.base_semantic_digest !== prepared.spec.semantic_digest || reply.request_digest !== requestHash) throw new Error('diagram_generation_changed');
      await validateDiagramSpec(reply.spec); await validateLayoutSpec(reply.layout, reply.spec);
      if (canonicalJSON(reply.spec.scope) !== canonicalJSON(prepared.spec.scope) || reply.spec.template !== prepared.spec.template) throw new Error('diagram_scope_mismatch');
      if (controller.signal.aborted || id !== sequence.current || expected !== current.current) return;
      setState(s => ({ ...s, spec: reply.spec, layout: reply.layout, busy: false, collapsed_groups: request.collapsed_group_ids, filters: request }));
    } catch (error) {
      if (!controller.signal.aborted && id === sequence.current && expected === current.current) { const result = safeError(error); setState(s => ({ ...s, busy: false, error: result })); onError?.(result); }
    }
  }, [base, prepared, requestView, onError]);
  return { state, select, focus, toggleGroup, derive, membersPending };
}
