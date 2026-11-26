import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SearchPanel } from '../../src/components/intelligence/SearchPanel.jsx';

describe('SearchPanel Component', () => {
  const defaultProps = {
    searchQuery: '',
    setSearchQuery: vi.fn(),
    searchFilters: { entity_kinds: [], statuses: [] },
    setSearchFilters: vi.fn(),
    searchStatus: {
      freshness: 'current',
      resource_state: 'READY',
      is_readable: true,
      indexed_documents_count: 50,
      active_generation_id: 'gen-12345678',
    },
    searchPage: null,
    searchLoading: false,
    searchError: null,
    searchCursorIndex: 0,
    hasMoreSearch: false,
    onSearch: vi.fn(),
    onNextPage: vi.fn(),
    onPrevPage: vi.fn(),
    onInspectSubject: vi.fn(),
    onOpenEvidence: vi.fn(),
  };

  it('renders search input, filter chips, and search capabilities', () => {
    render(<SearchPanel {...defaultProps} />);

    expect(screen.getByPlaceholderText(/Search entities, services/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Search$/i })).toBeInTheDocument();
    expect(screen.getByText('Indexed Documents:')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
    expect(screen.getByText(/READY · current · readable/)).toBeInTheDocument();
  });

  it('submits search when search button is clicked or form is submitted', () => {
    render(<SearchPanel {...defaultProps} searchQuery="Payment" />);

    const submitBtn = screen.getByRole('button', { name: /^Search$/i });
    fireEvent.click(submitBtn);

    expect(defaultProps.onSearch).toHaveBeenCalledTimes(1);
  });

  it('toggles entity kind filter chips', () => {
    render(<SearchPanel {...defaultProps} />);

    const serviceChip = screen.getByRole('button', { name: /^SERVICE$/i });
    fireEvent.click(serviceChip);

    expect(defaultProps.setSearchFilters).toHaveBeenCalledWith({
      entity_kinds: ['service'],
      statuses: [],
    });
  });

  it('renders search results with inspect and evidence actions', () => {
    const searchPage = {
      items: [
        {
          knowledge_key: 'key-1',
          canonical_reference: 'architecture://payment',
          document_kind: 'entity',
          title: 'PaymentGateway',
          evidence_ids: ['11111111-1111-4111-8111-111111111111'],
          kind: 'SERVICE',
          status: 'ACTIVE',
          score: 8.45,
          coordinates: { file_path: 'backend/payment.py', line_start: 12, line_end: 45 },
          highlight: 'Matches <em>Payment</em> class',
        },
      ],
    };

    render(<SearchPanel {...defaultProps} searchPage={searchPage} hasMoreSearch={true} />);

    expect(screen.getByText('PaymentGateway')).toBeInTheDocument();
    expect(screen.getAllByText('SERVICE').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Score: 8.45/i)).toBeInTheDocument();
    expect(screen.getByText('backend/payment.py')).toBeInTheDocument();

    const inspectBtn = screen.getByRole('button', { name: /Knowledge Query/i });
    fireEvent.click(inspectBtn);
    expect(defaultProps.onInspectSubject).toHaveBeenCalledWith({
      logical_id: 'architecture://payment',
    });

    const evidenceBtn = screen.getByRole('button', { name: /Evidence/i });
    fireEvent.click(evidenceBtn);
    expect(defaultProps.onOpenEvidence).toHaveBeenCalledWith({
      evidence_ids: ['11111111-1111-4111-8111-111111111111'],
      name: 'PaymentGateway',
    });
  });

  it('handles pagination next and previous clicks', () => {
    const searchPage = {
      items: [{ id: 'ent-1', name: 'Item 1' }],
    };

    render(
      <SearchPanel
        {...defaultProps}
        searchPage={searchPage}
        searchCursorIndex={1}
        hasMoreSearch={true}
      />
    );

    const prevBtn = screen.getByRole('button', { name: /Previous Page/i });
    const nextBtn = screen.getByRole('button', { name: /Next Page/i });

    fireEvent.click(prevBtn);
    expect(defaultProps.onPrevPage).toHaveBeenCalledTimes(1);

    fireEvent.click(nextBtn);
    expect(defaultProps.onNextPage).toHaveBeenCalledTimes(1);
  });
});
