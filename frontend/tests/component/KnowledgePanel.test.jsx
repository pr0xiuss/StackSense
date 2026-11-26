import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { KnowledgePanel } from '../../src/components/intelligence/KnowledgePanel.jsx';

describe('KnowledgePanel Component', () => {
  const defaultProps = {
    selectorType: 'entity_name',
    setSelectorType: vi.fn(),
    selectorValue: '',
    setSelectorValue: vi.fn(),
    operation: 'lookup',
    setOperation: vi.fn(),
    knowledgeResponse: null,
    knowledgeLoading: false,
    knowledgeError: null,
    onExecuteQuery: vi.fn(),
    contextBundle: null,
    contextLoading: false,
    contextError: null,
    onAssembleContext: vi.fn(),
    onOpenEvidence: vi.fn(),
  };

  it('renders selector type, target input, operation, and execute button', () => {
    render(<KnowledgePanel {...defaultProps} selectorValue="AuthService" />);

    expect(screen.getByLabelText(/Selector Type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Target Identifier/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Operation/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Execute Query/i })).toBeInTheDocument();
  });

  it('submits query on form submission', () => {
    render(<KnowledgePanel {...defaultProps} selectorValue="AuthService" />);

    fireEvent.click(screen.getByRole('button', { name: /Execute Query/i }));
    expect(defaultProps.onExecuteQuery).toHaveBeenCalledTimes(1);
  });

  it('renders ambiguity card when response state is AMBIGUOUS', () => {
    const ambiguousResponse = {
      resolved_subject: { state: 'ambiguous',
      candidates: [
        { record_id: 'cand-1', name: 'UserService', kind: 'SERVICE', coordinates: { file_path: 'user.py' } },
        { record_id: 'cand-2', name: 'UserServiceTest', kind: 'TEST', coordinates: { file_path: 'test_user.py' } },
      ],
      },
    };

    render(
      <KnowledgePanel
        {...defaultProps}
        selectorValue="UserService"
        knowledgeResponse={ambiguousResponse}
      />
    );

    expect(screen.getByText(/Multiple Matching Elements Found/i)).toBeInTheDocument();
    expect(screen.getByText('UserServiceTest')).toBeInTheDocument();

    const selectButtons = screen.getAllByRole('button', { name: /Select Exact/i });
    expect(selectButtons).toHaveLength(2);
    fireEvent.click(selectButtons[0]);

    expect(defaultProps.setSelectorType).toHaveBeenCalledWith('record_id');
    expect(defaultProps.setSelectorValue).toHaveBeenCalledWith('cand-1');
  });

  it('renders resolved subject with connected relationships and evidence actions', () => {
    const resolvedResponse = {
      resolution_state: 'RESOLVED',
      resolved_subject: {
        state: 'resolved',
        selected_id: '11111111-1111-4111-8111-111111111111',
        selected_kind: 'SERVICE',
        status: 'ACTIVE',
      },
      relationships: [
        {
          record_id: 'rel-99',
          kind: 'DEPENDS_ON',
          target_logical_id: 'InventoryService',
          direction: 'OUTGOING',
        },
      ],
    };

    render(
      <KnowledgePanel
        {...defaultProps}
        selectorValue="OrdersService"
        knowledgeResponse={resolvedResponse}
      />
    );

    expect(screen.getByText('OrdersService')).toBeInTheDocument();
    expect(screen.getByText('DEPENDS_ON')).toBeInTheDocument();
    expect(screen.getByText('InventoryService')).toBeInTheDocument();

    const evidenceBtn = screen.getByRole('button', { name: /View Subject Evidence/i });
    fireEvent.click(evidenceBtn);
    expect(defaultProps.onOpenEvidence).toHaveBeenCalledWith({
      entity_id: '11111111-1111-4111-8111-111111111111',
      name: 'OrdersService',
    });

    const contextBtn = screen.getByRole('button', { name: /Assemble Context Bundle/i });
    fireEvent.click(contextBtn);
    expect(defaultProps.onAssembleContext).toHaveBeenCalledWith([
      { selector_type: 'record_id', record_kind: 'entity', record_id: '11111111-1111-4111-8111-111111111111' },
    ]);
  });

  it('renders assembled context bundle metadata and digest', () => {
    const bundle = {
      semantic_digest: '998877665544332211aabbcc',
      subjects: [{ id: 's1' }],
      relationships: [{ id: 'r1' }, { id: 'r2' }],
      evidence: [{ id: 'e1' }],
      coverage: { completeness_state: 'COMPLETE' },
    };

    render(<KnowledgePanel {...defaultProps} contextBundle={bundle} />);

    expect(screen.getByText(/Assembled Semantic Context Bundle/i)).toBeInTheDocument();
    expect(screen.getByText(/9988776655443322…/i)).toBeInTheDocument();
    expect(screen.getByText('COMPLETE')).toBeInTheDocument();
  });
});
