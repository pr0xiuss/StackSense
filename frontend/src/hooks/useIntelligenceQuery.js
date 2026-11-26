/**
 * useIntelligenceQuery Hook
 *
 * Manages C1 Lexical Search, C3 Knowledge Queries, Context Assembly, and Evidence resolution.
 * Enforces sequential request ordering, aborts stale requests, maintains cursor stacks
 * for forward/backward pagination, and gracefully handles 409/410 cursor expiration.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { knowledgeService } from '../services/knowledgeService.js';

export function useIntelligenceQuery(versionId, {
  projectId,
  initialSearchQuery = '',
} = {}) {
  // --- 1. Search State (C1) ---
  const [searchQuery, setSearchQuery] = useState(initialSearchQuery);
  const [searchFilters, setSearchFilters] = useState({
    entity_kinds: [],
    statuses: [],
    document_kinds: [],
  });
  const [searchStatus, setSearchStatus] = useState(null);
  const [searchPage, setSearchPage] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);

  // Search cursor stack for pagination: [null, "cursor1", "cursor2"]
  const [searchCursorStack, setSearchCursorStack] = useState([null]);
  const [searchCursorIndex, setSearchCursorIndex] = useState(0);

  const searchSeqRef = useRef(0);
  const searchAbortRef = useRef(null);
  const searchIdentityRef = useRef(null);

  // --- 2. Knowledge Query State (C3) ---
  const [selectorType, setSelectorType] = useState('entity_name'); // 'exact_id' | 'logical_id' | 'entity_name'
  const [selectorValue, setSelectorValue] = useState('');
  const [operation, setOperation] = useState('lookup');
  const [knowledgeResponse, setKnowledgeResponse] = useState(null);
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [knowledgeError, setKnowledgeError] = useState(null);

  // Context Assembly state
  const [contextBundle, setContextBundle] = useState(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextError, setContextError] = useState(null);

  const knowledgeSeqRef = useRef(0);
  const knowledgeAbortRef = useRef(null);

  // --- 3. Evidence State (C3) ---
  const [evidenceSubject, setEvidenceSubject] = useState(null); // { entity_id, relationship_id, name }
  const [evidencePage, setEvidencePage] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState(null);
  const [evidenceCursorStack, setEvidenceCursorStack] = useState([null]);
  const [evidenceCursorIndex, setEvidenceCursorIndex] = useState(0);

  const evidenceAbortRef = useRef(null);
  const isMountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      searchAbortRef.current?.abort();
      knowledgeAbortRef.current?.abort();
      evidenceAbortRef.current?.abort();
    };
  }, []);

  // Fetch search status & capabilities
  const fetchSearchStatus = useCallback(async () => {
    if (!versionId || !projectId) return;
    try {
      const status = await knowledgeService.getSearchStatus(versionId, { projectId });
      if (isMountedRef.current) {
        setSearchStatus(status);
      }
    } catch (err) {
      console.warn('Failed to fetch search capabilities:', err);
    }
  }, [versionId, projectId]);

  useEffect(() => {
    fetchSearchStatus();
  }, [fetchSearchStatus]);

  // Execute Search
  const executeSearch = useCallback(async (targetCursor = null, targetIndex = 0) => {
    if (!versionId || !projectId) return;
    if (!searchQuery.trim()) {
      setSearchError('Enter a search term.');
      return;
    }

    searchAbortRef.current?.abort();
    const controller = new AbortController();
    searchAbortRef.current = controller;

    const currentSeq = ++searchSeqRef.current;
    setSearchLoading(true);
    setSearchError(null);

    try {
      const params = {
        projectId,
        q: searchQuery || undefined,
        cursor: targetCursor || undefined,
        limit: 20,
        ...searchFilters,
      };

      const result = await knowledgeService.search(versionId, params, {
        signal: controller.signal,
      });

      if (!isMountedRef.current || controller.signal.aborted || currentSeq !== searchSeqRef.current) return;

      const identity = `${result.scope?.project_id}:${result.scope?.architecture_version_id}:${result.generation_id}:${result.index_uuid}`;
      if (targetCursor && searchIdentityRef.current !== identity) {
        throw new Error('Search generation changed. Start a new search.');
      }
      searchIdentityRef.current = identity;

      setSearchPage(result);
      setSearchCursorIndex(targetIndex);

      // If there's a next cursor and it's not already in stack
      if (targetIndex === 0) {
        setSearchCursorStack(result.next_cursor ? [null, result.next_cursor] : [null]);
      } else if (result.next_cursor && targetIndex === searchCursorStack.length - 1) {
        setSearchCursorStack((prev) => [...prev, result.next_cursor]);
      }
    } catch (err) {
      if (!isMountedRef.current || controller.signal.aborted || currentSeq !== searchSeqRef.current) return;
      const status = err?.status || err?.response?.status;
      if (status === 410) {
        setSearchError('Search cursor expired. Resetting search results.');
        setSearchCursorStack([null]);
        setSearchCursorIndex(0);
      } else if (status === 409) {
        setSearchError('Search index generation changed. Please refresh search capabilities.');
        fetchSearchStatus();
      } else {
        setSearchError(err?.message || 'Search failed.');
      }
    } finally {
      if (isMountedRef.current && currentSeq === searchSeqRef.current) {
        setSearchLoading(false);
      }
    }
  }, [versionId, projectId, searchQuery, searchFilters, searchCursorStack.length, fetchSearchStatus]);

  const nextSearchPage = useCallback(() => {
    if (!searchPage?.next_cursor) return;
    const nextIdx = searchCursorIndex + 1;
    executeSearch(searchPage.next_cursor, nextIdx);
  }, [searchPage?.next_cursor, searchCursorIndex, executeSearch]);

  const prevSearchPage = useCallback(() => {
    if (searchCursorIndex <= 0) return;
    const prevIdx = searchCursorIndex - 1;
    const prevCursor = searchCursorStack[prevIdx];
    executeSearch(prevCursor, prevIdx);
  }, [searchCursorIndex, searchCursorStack, executeSearch]);

  const resetSearch = useCallback(() => {
    setSearchCursorStack([null]);
    setSearchCursorIndex(0);
    setSearchPage(null);
    searchIdentityRef.current = null;
    executeSearch(null, 0);
  }, [executeSearch]);

  // Execute Knowledge Query
  const executeKnowledgeQuery = useCallback(async (override = null) => {
    const type = override?.type || selectorType;
    const value = override?.value || selectorValue;
    if (!versionId || !projectId || !value.trim()) return;

    knowledgeAbortRef.current?.abort();
    const controller = new AbortController();
    knowledgeAbortRef.current = controller;

    const currentSeq = ++knowledgeSeqRef.current;
    setKnowledgeLoading(true);
    setKnowledgeError(null);
    setKnowledgeResponse(null);

    try {
      const subject = {
        selector_type: type,
        record_kind: 'entity',
        [type === 'record_id' ? 'record_id' : type === 'logical_id' ? 'logical_id' : 'name']: value.trim(),
      };

      const body = {
        subject,
        operation,
        graph_depth: 1,
      };

      const result = await knowledgeService.queryKnowledge(versionId, body, {
        projectId,
        signal: controller.signal,
      });

      if (!isMountedRef.current || controller.signal.aborted || currentSeq !== knowledgeSeqRef.current) return;

      setKnowledgeResponse(result);
    } catch (err) {
      if (!isMountedRef.current || controller.signal.aborted || currentSeq !== knowledgeSeqRef.current) return;
      setKnowledgeError(err?.message || 'Knowledge query failed.');
    } finally {
      if (isMountedRef.current && currentSeq === knowledgeSeqRef.current) {
        setKnowledgeLoading(false);
      }
    }
  }, [versionId, projectId, selectorType, selectorValue, operation]);

  // Execute Context Assembly
  const assembleContext = useCallback(async (subjects) => {
    if (!versionId || !projectId || !subjects || subjects.length === 0) return;

    setContextLoading(true);
    setContextError(null);

    try {
      const body = {
        subjects,
        include_evidence: true,
      };

      const bundle = await knowledgeService.getContext(versionId, body, { projectId });

      if (isMountedRef.current) {
        setContextBundle(bundle);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setContextError(err?.message || 'Context assembly failed.');
      }
    } finally {
      if (isMountedRef.current) {
        setContextLoading(false);
      }
    }
  }, [versionId, projectId]);

  // Evidence Management
  const loadEvidence = useCallback(async (subject, targetCursor = null, targetIndex = 0) => {
    if (!versionId || !projectId || !subject) return;

    evidenceAbortRef.current?.abort();
    const controller = new AbortController();
    evidenceAbortRef.current = controller;

    setEvidenceLoading(true);
    setEvidenceError(null);

    try {
      const params = {
        projectId,
        limit: 20,
        cursor: targetCursor || undefined,
        ...(subject.entity_id ? { entity_id: [subject.entity_id] } : {}),
        ...(subject.relationship_id ? { relationship_id: [subject.relationship_id] } : {}),
        ...(subject.evidence_ids?.length ? { evidence_id: subject.evidence_ids } : {}),
      };

      const page = await knowledgeService.getEvidence(versionId, params, {
        signal: controller.signal,
      });

      if (!isMountedRef.current || controller.signal.aborted) return;

      setEvidencePage(page);
      setEvidenceCursorIndex(targetIndex);

      if (targetIndex === 0) {
        setEvidenceCursorStack(page.next_cursor ? [null, page.next_cursor] : [null]);
      } else if (page.next_cursor && targetIndex === evidenceCursorStack.length - 1) {
        setEvidenceCursorStack((prev) => [...prev, page.next_cursor]);
      }
    } catch (err) {
      if (!isMountedRef.current || controller.signal.aborted) return;
      setEvidenceError(err?.message || 'Failed to load evidence.');
    } finally {
      if (isMountedRef.current) {
        setEvidenceLoading(false);
      }
    }
  }, [versionId, projectId, evidenceCursorStack.length]);

  const openEvidence = useCallback((subject) => {
    setEvidenceSubject(subject);
    setEvidenceCursorStack([null]);
    setEvidenceCursorIndex(0);
    loadEvidence(subject, null, 0);
  }, [loadEvidence]);

  const closeEvidence = useCallback(() => {
    evidenceAbortRef.current?.abort();
    setEvidenceSubject(null);
    setEvidencePage(null);
    setEvidenceError(null);
  }, []);

  const nextEvidencePage = useCallback(() => {
    if (!evidencePage?.next_cursor || !evidenceSubject) return;
    const nextIdx = evidenceCursorIndex + 1;
    loadEvidence(evidenceSubject, evidencePage.next_cursor, nextIdx);
  }, [evidencePage?.next_cursor, evidenceSubject, evidenceCursorIndex, loadEvidence]);

  const prevEvidencePage = useCallback(() => {
    if (evidenceCursorIndex <= 0 || !evidenceSubject) return;
    const prevIdx = evidenceCursorIndex - 1;
    const prevCursor = evidenceCursorStack[prevIdx];
    loadEvidence(evidenceSubject, prevCursor, prevIdx);
  }, [evidenceCursorIndex, evidenceSubject, evidenceCursorStack, loadEvidence]);

  return {
    // Search
    searchQuery,
    setSearchQuery,
    searchFilters,
    setSearchFilters,
    searchStatus,
    searchPage,
    searchLoading,
    searchError,
    searchCursorIndex,
    hasMoreSearch: Boolean(searchPage?.next_cursor),
    executeSearch: () => resetSearch(),
    nextSearchPage,
    prevSearchPage,
    resetSearch,

    // Knowledge
    selectorType,
    setSelectorType,
    selectorValue,
    setSelectorValue,
    operation,
    setOperation,
    knowledgeResponse,
    knowledgeLoading,
    knowledgeError,
    executeKnowledgeQuery,
    contextBundle,
    contextLoading,
    contextError,
    assembleContext,

    // Evidence
    evidenceSubject,
    evidencePage,
    evidenceLoading,
    evidenceError,
    evidenceCursorIndex,
    hasMoreEvidence: Boolean(evidencePage?.next_cursor),
    openEvidence,
    closeEvidence,
    nextEvidencePage,
    prevEvidencePage,
  };
}
