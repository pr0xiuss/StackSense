import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ReportPanel } from '../../src/components/intelligence/ReportPanel.jsx';
import { reportService } from '../../src/services/reportService.js';

vi.mock('../../src/services/reportService.js', () => ({
  reportService: {
    getReports: vi.fn(),
    getReportSummary: vi.fn(),
    getReportGenerations: vi.fn(),
    downloadReport: vi.fn(),
  },
}));

describe('ReportPanel Component', () => {
  const versionId = '44444444-4444-4444-8444-444444444444';
  const projectId = '11111111-1111-4111-8111-111111111111';

  beforeEach(() => {
    vi.clearAllMocks();

    reportService.getReports.mockResolvedValue({
      reports: [
        { report_id: 'automatic', name: 'Comprehensive System Architecture' },
      ],
    });

    reportService.getReportSummary.mockResolvedValue({
      report_id: 'automatic',
      name: 'Comprehensive System Architecture',
      ready: true,
      active_generation_id: 'gen-rep-active-1',
      active_digest: 'digest-sha256-active',
      page_count: 24,
    });

    reportService.getReportGenerations.mockResolvedValue({
      items: [
        {
          generation_id: 'gen-rep-active-1',
          created_at: new Date().toISOString(),
          status: 'READY',
          digest: 'digest-sha256-active',
        },
        {
          generation_id: 'gen-rep-hist-2',
          created_at: new Date(Date.now() - 3600000).toISOString(),
          status: 'SUPERSEDED',
          digest: 'digest-sha256-hist',
        },
      ],
      next_cursor: null,
    });
  });

  it('renders report summary card with status, digest, and download button', async () => {
    render(<ReportPanel versionId={versionId} projectId={projectId} />);

    await waitFor(() => {
      expect(screen.getByText('Comprehensive System Architecture')).toBeInTheDocument();
    });

    expect(screen.getByText('READY FOR EXPORT')).toBeInTheDocument();
    expect(screen.getByText(/digest-sha256-ac…/i)).toBeInTheDocument();
    expect(screen.getByText('24')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download Verified PDF Report/i })).toBeInTheDocument();
  });

  it('renders generation publication history table with exact download actions', async () => {
    render(<ReportPanel versionId={versionId} projectId={projectId} />);

    await waitFor(() => {
      expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    });

    expect(screen.getByText('SUPERSEDED')).toBeInTheDocument();

    const downloadButtons = screen.getAllByRole('button', { name: /^Download$/i });
    expect(downloadButtons).toHaveLength(2);
  });

  it('triggers PDF download when primary download button is clicked', async () => {
    reportService.downloadReport.mockResolvedValue({ status: 200 });

    render(<ReportPanel versionId={versionId} projectId={projectId} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Download Verified PDF Report/i })).toBeInTheDocument();
    });

    const downloadBtn = screen.getByRole('button', { name: /Download Verified PDF Report/i });
    fireEvent.click(downloadBtn);

    await waitFor(() => {
      expect(reportService.downloadReport).toHaveBeenCalledWith(
        versionId,
        'automatic',
        'gen-rep-active-1',
        expect.objectContaining({
          projectId,
          expectedDigest: 'digest-sha256-active',
        })
      );
    });
  });

  it('renders error notice when download fails', async () => {
    reportService.downloadReport.mockRejectedValue(new Error('Network dropout during PDF relay'));

    render(<ReportPanel versionId={versionId} projectId={projectId} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Download Verified PDF Report/i })).toBeInTheDocument();
    });

    const downloadBtn = screen.getByRole('button', { name: /Download Verified PDF Report/i });
    fireEvent.click(downloadBtn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByText(/Network dropout during PDF relay/i)).toBeInTheDocument();
  });
});
