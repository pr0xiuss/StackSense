import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useReportHistory } from '../../src/hooks/useReportHistory.js';
import { reportService } from '../../src/services/reportService.js';

vi.mock('../../src/services/reportService.js', () => ({
  reportService: {
    getReports: vi.fn(),
    getReportSummary: vi.fn(),
    getReportGenerations: vi.fn(),
    getReportGenerationDetail: vi.fn(),
    downloadReport: vi.fn(),
  },
}));

describe('useReportHistory Hook', () => {
  const versionId = '44444444-4444-4444-8444-444444444444';
  const projectId = '11111111-1111-4111-8111-111111111111';

  beforeEach(() => {
    vi.clearAllMocks();

    reportService.getReports.mockResolvedValue({
      reports: [
        { report_id: 'automatic', name: 'Architecture Executive Summary' },
      ],
    });

    reportService.getReportSummary.mockResolvedValue({
      report_id: 'automatic',
      name: 'Architecture Executive Summary',
      ready: true,
      active_generation_id: 'gen-rep-1',
      active_digest: 'sha256-digest-1',
      page_count: 14,
    });

    reportService.getReportGenerations.mockResolvedValue({
      items: [
        {
          generation_id: 'gen-rep-1',
          created_at: new Date().toISOString(),
          status: 'READY',
          digest: 'sha256-digest-1',
        },
      ],
      next_cursor: 'cursor-gen-2',
    });
  });

  it('loads report collection, summary, and initial generation page on mount', async () => {
    const { result } = renderHook(() =>
      useReportHistory(versionId, { projectId })
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(reportService.getReports).toHaveBeenCalledWith(versionId, { projectId });
    expect(result.current.reportId).toBe('automatic');

    await act(async () => {
      await Promise.resolve();
    });

    expect(reportService.getReportSummary).toHaveBeenCalledWith(versionId, 'automatic', { projectId });
    expect(result.current.summary?.ready).toBe(true);
    expect(result.current.selectedGenerationId).toBe('gen-rep-1');
    expect(result.current.hasMoreGenerations).toBe(true);
  });

  it('handles generation history forward and backward pagination', async () => {
    const page2 = {
      items: [
        {
          generation_id: 'gen-rep-2',
          created_at: new Date().toISOString(),
          status: 'READY',
          digest: 'sha256-digest-2',
        },
      ],
      next_cursor: null,
    };

    reportService.getReportGenerations
      .mockResolvedValueOnce({
        items: [{ generation_id: 'gen-rep-1' }],
        next_cursor: 'cursor-gen-2',
      })
      .mockResolvedValueOnce(page2);

    const { result } = renderHook(() =>
      useReportHistory(versionId, { projectId })
    );

    await act(async () => {
      await Promise.resolve();
    });

    // Advance to next page
    await act(async () => {
      result.current.nextGenerationsPage();
    });

    expect(reportService.getReportGenerations).toHaveBeenCalledWith(
      versionId,
      'automatic',
      expect.objectContaining({ cursor: 'cursor-gen-2' })
    );
    expect(result.current.cursorIndex).toBe(1);

    // Prev page
    reportService.getReportGenerations.mockResolvedValueOnce({
      items: [{ generation_id: 'gen-rep-1' }],
      next_cursor: 'cursor-gen-2',
    });

    await act(async () => {
      result.current.prevGenerationsPage();
    });

    expect(result.current.cursorIndex).toBe(0);
  });

  it('downloads exact PDF with digest validation', async () => {
    reportService.downloadReport.mockResolvedValue({
      status: 200,
      filename: 'report.pdf',
    });

    const { result } = renderHook(() =>
      useReportHistory(versionId, { projectId })
    );

    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await result.current.downloadPdf('gen-rep-1');
    });

    expect(reportService.downloadReport).toHaveBeenCalledWith(
      versionId,
      'automatic',
      'gen-rep-1',
      expect.objectContaining({
        projectId,
        expectedDigest: 'sha256-digest-1',
      })
    );
    expect(result.current.downloading).toBe(false);
    expect(result.current.downloadError).toBeNull();
  });

  it('handles download failure gracefully', async () => {
    reportService.downloadReport.mockRejectedValue(new Error('Digest verification failed'));

    const { result } = renderHook(() =>
      useReportHistory(versionId, { projectId })
    );

    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await result.current.downloadPdf('gen-rep-1');
    });

    expect(result.current.downloadError).toBe('Digest verification failed');
    expect(result.current.downloading).toBe(false);
  });
});
