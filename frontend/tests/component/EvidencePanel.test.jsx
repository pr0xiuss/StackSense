import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EvidencePanel } from '../../src/components/intelligence/EvidencePanel.jsx';

describe('EvidencePanel Component', () => {
  const defaultProps = {
    evidenceSubject: {
      entity_id: 'ent-123',
      name: 'AuthenticationService',
    },
    evidencePage: null,
    evidenceLoading: false,
    evidenceError: null,
    evidenceCursorIndex: 0,
    hasMoreEvidence: false,
    onNextPage: vi.fn(),
    onPrevPage: vi.fn(),
    onClose: vi.fn(),
  };

  it('renders null when evidenceSubject is null', () => {
    const { container } = render(
      <EvidencePanel {...defaultProps} evidenceSubject={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders drawer header with subject name and close button', () => {
    render(<EvidencePanel {...defaultProps} />);

    expect(screen.getByText('AuthenticationService')).toBeInTheDocument();
    expect(screen.getByText('ent-123')).toBeInTheDocument();

    const closeBtn = screen.getByRole('button', { name: /Close evidence drawer/i });
    fireEvent.click(closeBtn);
    expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
  });

  it('renders evidence records with strength badge, opposing indicator, coordinates, and snippet', () => {
    const evidencePage = {
      items: [
        {
          id: 'ev-1',
          strength: 'CONFIRMED_DIRECT',
          is_opposing: false,
          producer_id: 'AstParser',
          path: 'backend/auth.py',
          snippet: 'def verify_token(token): ...',
        },
        {
          id: 'ev-2',
          strength: 'HEURISTIC',
          polarity: 'opposing',
          coordinates: { file_path: 'legacy/auth.py', line_start: 10, line_end: 15 },
          description: 'Deprecated authentication route found',
        },
      ],
    };

    render(<EvidencePanel {...defaultProps} evidencePage={evidencePage} />);

    expect(screen.getByText('Confirmed (Direct)')).toBeInTheDocument();
    expect(screen.getByText('Opposing Evidence')).toBeInTheDocument();
    expect(screen.getByText('AstParser')).toBeInTheDocument();
    expect(screen.getByText('backend/auth.py')).toBeInTheDocument();
    expect(screen.getByText('def verify_token(token): ...')).toBeInTheDocument();
    expect(screen.getByText('Deprecated authentication route found')).toBeInTheDocument();
  });

  it('handles pagination next and prev clicks', () => {
    const evidencePage = {
      items: [{ id: 'ev-1', strength: 'HEURISTIC' }],
    };

    render(
      <EvidencePanel
        {...defaultProps}
        evidencePage={evidencePage}
        evidenceCursorIndex={1}
        hasMoreEvidence={true}
      />
    );

    const prevBtn = screen.getByRole('button', { name: /Prev/i });
    const nextBtn = screen.getByRole('button', { name: /Next/i });

    fireEvent.click(prevBtn);
    expect(defaultProps.onPrevPage).toHaveBeenCalledTimes(1);

    fireEvent.click(nextBtn);
    expect(defaultProps.onNextPage).toHaveBeenCalledTimes(1);
  });
});
