import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useIntelligenceQuery } from '../../src/hooks/useIntelligenceQuery.js';
import { knowledgeService } from '../../src/services/knowledgeService.js';

vi.mock('../../src/services/knowledgeService.js', () => ({
  knowledgeService: {
    getSearchStatus: vi.fn(),
    search: vi.fn(),
    queryKnowledge: vi.fn(),
    getContext: vi.fn(),
    getEvidence: vi.fn(),
  },
}));

describe('useIntelligenceQuery Hook', () => {
  const versionId = '44444444-4444-4444-8444-444444444444';
  const projectId = '11111111-1111-4111-8111-111111111111';

  beforeEach(() => {
    vi.clearAllMocks();
    knowledgeService.getSearchStatus.mockResolvedValue({
      freshness_state: 'READY',
      indexed_documents_count: 142,
      active_generation_id: 'gen-search-1',
    });
  });

  it('loads search capabilities on mount and executes search with pagination', async () => {
    const page1 = {
      items: [{ id: 'ent-1', name: 'AuthService', kind: 'SERVICE' }],
      next_cursor: 'cursor-page-2',
      total_count: 2,
    };

    const page2 = {
      items: [{ id: 'ent-2', name: 'UserService', kind: 'SERVICE' }],
      next_cursor: null,
      total_count: 2,
    };

    knowledgeService.search
      .mockResolvedValueOnce(page1)
      .mockResolvedValueOnce(page2);

    const { result } = renderHook(() =>
      useIntelligenceQuery(versionId, { projectId })
    );

    // Initial capabilities fetch
    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.searchStatus).toEqual(
      expect.objectContaining({ freshness_state: 'READY' })
    );

    // Execute initial search
    act(() => {
      result.current.setSearchQuery('Service');
    });

    await act(async () => {
      result.current.executeSearch();
    });

    expect(result.current.searchPage).toEqual(page1);
    expect(result.current.hasMoreSearch).toBe(true);
    expect(result.current.searchCursorIndex).toBe(0);

    // Next page
    await act(async () => {
      result.current.nextSearchPage();
    });

    expect(result.current.searchPage).toEqual(page2);
    expect(result.current.hasMoreSearch).toBe(false);
    expect(result.current.searchCursorIndex).toBe(1);

    // Prev page
    knowledgeService.search.mockResolvedValueOnce(page1);
    await act(async () => {
      result.current.prevSearchPage();
    });

    expect(result.current.searchCursorIndex).toBe(0);
  });

  it('handles 410 cursor expired by resetting pagination and warning user', async () => {
    const err410 = new Error('Cursor expired');
    err410.status = 410;

    knowledgeService.search.mockRejectedValue(err410);

    const { result } = renderHook(() =>
      useIntelligenceQuery(versionId, { projectId })
    );

    await act(async () => {
      await result.current.executeSearch();
    });

    expect(result.current.searchError).toMatch(/Search cursor expired/i);
    expect(result.current.searchCursorIndex).toBe(0);
  });

  it('executes knowledge query and sets response', async () => {
    const queryResult = {
      resolution_state: 'RESOLVED',
      resolved_subject: { id: 'ent-1', name: 'DatabaseService', kind: 'DATABASE' },
      relationships: [
        { id: 'rel-1', kind: 'CONNECTS_TO', target_name: 'AuthService', direction: 'OUTGOING' },
      ],
    };

    knowledgeService.queryKnowledge.mockResolvedValue(queryResult);

    const { result } = renderHook(() =>
      useIntelligenceQuery(versionId, { projectId })
    );

    act(() => {
      result.current.setSelectorType('entity_name');
      result.current.setSelectorValue('DatabaseService');
      result.current.setOperation('RELATIONSHIPS');
    });

    await act(async () => {
      await result.current.executeKnowledgeQuery();
    });

    expect(knowledgeService.queryKnowledge).toHaveBeenCalledWith(
      versionId,
      {
        subject: { kind: 'entity_name', name: 'DatabaseService' },
        operation: 'RELATIONSHIPS',
        max_hops: 1,
      },
      expect.objectContaining({ projectId })
    );

    expect(result.current.knowledgeResponse).toEqual(queryResult);
  });

  it('opens evidence drawer and fetches paginated evidence records', async () => {
    const evidencePage = {
      items: [
        {
          id: 'ev-1',
          strength: 'CONFIRMED_DIRECT',
          coordinates: { file_path: 'src/auth.js', line_start: 10, line_end: 25 },
          snippet: 'function authenticate() {}',
        },
      ],
      next_cursor: null,
    };

    knowledgeService.getEvidence.mockResolvedValue(evidencePage);

    const { result } = renderHook(() =>
      useIntelligenceQuery(versionId, { projectId })
    );

    await act(async () => {
      result.current.openEvidence({ entity_id: 'ent-1', name: 'AuthService' });
    });

    expect(knowledgeService.getEvidence).toHaveBeenCalledWith(
      versionId,
      expect.objectContaining({
        projectId,
        entity_id: ['ent-1'],
      }),
      expect.anything()
    );

    expect(result.current.evidenceSubject).toEqual({ entity_id: 'ent-1', name: 'AuthService' });
    expect(result.current.evidencePage).toEqual(evidencePage);

    // Close evidence drawer
    act(() => {
      result.current.closeEvidence();
    });

    expect(result.current.evidenceSubject).toBeNull();
    expect(result.current.evidencePage).toBeNull();
  });
});
