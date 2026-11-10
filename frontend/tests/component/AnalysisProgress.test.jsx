import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import AnalysisProgress from '../../src/components/analysis/AnalysisProgress.jsx';

afterEach(cleanup);

describe('AnalysisProgress', () => {
  it('preserves complete long stage labels and exposes their full title', () => {
    render(
      <AnalysisProgress
        analysis={{
          status: 'running',
          stages: [
            {
              stage_name: 'identity_resolution',
              status: 'running',
              order: 7,
              processed_items: 0,
              total_items: 1,
            },
            {
              stage_name: 'architecture_build',
              status: 'pending',
              order: 8,
              processed_items: 0,
              total_items: 0,
            },
          ],
        }}
      />,
    );

    expect(screen.getByText('Identity Resolution')).toHaveAttribute(
      'title',
      'Identity Resolution',
    );
    expect(screen.getByText('Architecture Build')).toHaveAttribute(
      'title',
      'Architecture Build',
    );
    expect(screen.getByText('(0/1)')).toBeInTheDocument();
  });
});
