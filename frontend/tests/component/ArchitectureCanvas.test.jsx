import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ArchitectureCanvas from '../../src/components/architecture/ArchitectureCanvas.jsx';

const entities = [
  {
    id: 'app-id',
    logical_id: 'architecture://application/app',
    kind: 'application',
    name: 'express application',
  },
  {
    id: 'endpoint-id',
    logical_id: 'architecture://endpoint/users',
    kind: 'endpoint',
    name: 'GET /users',
    metadata: {
      qualified_name: 'backend/express/src/routes/users.routes.js::/users',
    },
  },
  {
    id: 'database-id',
    logical_id: 'architecture://database/postgresql',
    kind: 'database',
    name: 'PostgreSQL',
  },
];

const relationships = [
  {
    id: 'rel-id',
    kind: 'exposes',
    source_logical_id: entities[0].logical_id,
    target_logical_id: entities[1].logical_id,
  },
];

afterEach(cleanup);

describe('ArchitectureCanvas', () => {
  it('uses the canonical architecture vocabulary and an isolated node class', () => {
    const { container } = render(
      <ArchitectureCanvas
        entities={entities}
        relationships={relationships}
        totalEntities={147}
        totalRelationships={292}
      />,
    );

    expect(screen.getByText('Applications')).toBeInTheDocument();
    expect(screen.getByText('Interfaces & External Systems')).toBeInTheDocument();
    expect(screen.getByText('Persistence & Messaging')).toBeInTheDocument();
    expect(screen.getByText('Endpoint')).toBeInTheDocument();
    expect(screen.getByText('…ers.routes.js::/users')).toBeInTheDocument();
    expect(screen.getByText(/1 visible connectors/)).toBeInTheDocument();
    expect(screen.getByText('Backend-first view: 3 of 147 entities')).toBeInTheDocument();
    expect(container.querySelectorAll('.arch-map-node')).toHaveLength(3);
    expect(container.querySelectorAll('.arch-map-node-content')).toHaveLength(3);
    expect(container.querySelector('.arch-node')).not.toBeInTheDocument();
  });

  it('supports zoom controls and keyboard entity selection', () => {
    const onSelectEntity = vi.fn();
    const { container, rerender } = render(
      <ArchitectureCanvas
        entities={entities}
        relationships={relationships}
        selectedEntity={entities[0]}
        onSelectEntity={onSelectEntity}
      />,
    );

    expect(screen.getByText('85%')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Show all' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Zoom in architecture map' }));
    expect(screen.getByText('100%')).toBeInTheDocument();

    const endpoint = screen.getByRole('button', {
      name: 'Select GET /users (Endpoint)',
    });
    const viewport = container.querySelector('.arch-canvas-viewport');
    viewport.scrollTop = 240;
    viewport.scrollLeft = 80;
    fireEvent.keyDown(endpoint, { key: 'Enter' });
    expect(onSelectEntity).toHaveBeenCalledWith(entities[1]);

    rerender(
      <ArchitectureCanvas
        entities={entities}
        relationships={relationships}
        selectedEntity={entities[1]}
        onSelectEntity={onSelectEntity}
      />,
    );

    expect(viewport.scrollTop).toBe(240);
    expect(viewport.scrollLeft).toBe(80);
    expect(screen.getByText('1 direct connectors')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Show all' })).toBeEnabled();
    expect(
      screen.getByRole('button', { name: 'Select PostgreSQL (Database)' }),
    ).toHaveClass('muted');

    fireEvent.click(screen.getByRole('button', { name: 'Show all' }));
    expect(screen.getByText(/1 visible connectors/)).toBeInTheDocument();
  });
});
