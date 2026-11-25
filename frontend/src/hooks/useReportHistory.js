/**
 * useReportHistory Hook
 *
 * Manages C4 automated report collection, summary details, generation history pagination,
 * and authenticated, digest-verified PDF binary streaming and downloads.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { reportService } from '../services/reportService.js';

export function useReportHistory(versionId, {
  projectId,
  defaultReportId = null,
} = {}) {
  const [collection, setCollection] = useState(null);
  const [reportId, setReportId] = useState(defaultReportId);
  const [summary, setSummary] = useState(null);
  const [generationsPage, setGenerationsPage] = useState(null);
  const [selectedGenerationId, setSelectedGenerationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Pagination cursor stack: [null, "c1", "c2"]
  const [cursorStack, setCursorStack] = useState([null]);
  const [cursorIndex, setCursorIndex] = useState(0);

  // Download state
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState(null);
  const downloadAbortRef = useRef(null);

  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      downloadAbortRef.current?.abort();
    };
  }, []);

  // 1. Fetch ReportCollection
  const loadReports = useCallback(async () => {
    if (!versionId || !projectId) return;
    setLoading(true);
    setError(null);

    try {
      const col = await reportService.getReports(versionId, { projectId });
      if (!isMountedRef.current) return;
      setCollection(col);

      // Determine active reportId: provided, or first in collection, or default 'automatic'
      const activeId = defaultReportId || col.reports?.[0]?.report_id || col.items?.[0]?.report_id || 'automatic';
      setReportId(activeId);
    } catch (err) {
      if (!isMountedRef.current) return;
      setError(err?.message || 'Failed to load report collection.');
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [versionId, projectId, defaultReportId]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  // 2. Fetch ReportSummary and Generations for the resolved reportId
  const loadGenerations = useCallback(async (targetReportId, targetCursor = null, targetIndex = 0) => {
    if (!versionId || !projectId || !targetReportId) return;

    try {
      const [sum, genPage] = await Promise.all([
        reportService.getReportSummary(versionId, targetReportId, { projectId }),
        reportService.getReportGenerations(versionId, targetReportId, {
          projectId,
          cursor: targetCursor || undefined,
          limit: 10,
        }),
      ]);

      if (!isMountedRef.current) return;

      setSummary(sum);
      setGenerationsPage(genPage);
      setCursorIndex(targetIndex);

      if (genPage.next_cursor) {
        setCursorStack((prev) => (targetIndex === prev.length - 1 ? [...prev, genPage.next_cursor] : prev));
      }

      // Default selection to active generation if not set
      setSelectedGenerationId((prev) => prev || sum.active_generation_id || genPage.items?.[0]?.generation_id || null);
    } catch (err) {
      if (!isMountedRef.current) return;
      setError(err?.message || 'Failed to load report generations.');
    }
  }, [versionId, projectId]);

  useEffect(() => {
    if (reportId) {
      loadGenerations(reportId, null, 0);
    }
  }, [reportId, loadGenerations]);

  // Pagination navigation
  const nextGenerationsPage = useCallback(() => {
    if (!generationsPage?.next_cursor || !reportId) return;
    const nextIdx = cursorIndex + 1;
    loadGenerations(reportId, generationsPage.next_cursor, nextIdx);
  }, [generationsPage?.next_cursor, reportId, cursorIndex, loadGenerations]);

  const prevGenerationsPage = useCallback(() => {
    if (cursorIndex <= 0 || !reportId) return;
    const prevIdx = cursorIndex - 1;
    const prevCursor = cursorStack[prevIdx];
    loadGenerations(reportId, prevCursor, prevIdx);
  }, [cursorIndex, reportId, cursorStack, loadGenerations]);

  // Download PDF binary
  const downloadPdf = useCallback(async (targetGenId = null) => {
    const genId = targetGenId || selectedGenerationId || summary?.active_generation_id;
    if (!versionId || !projectId || !reportId || !genId) {
      setDownloadError('Missing version, report, or generation identifier for download.');
      return;
    }

    downloadAbortRef.current?.abort();
    const controller = new AbortController();
    downloadAbortRef.current = controller;

    setDownloading(true);
    setDownloadError(null);

    try {
      const selectedGen = generationsPage?.items?.find((g) => g.generation_id === genId);
      const expectedDigest = selectedGen?.digest || (genId === summary?.active_generation_id ? summary?.active_digest : null);

      await reportService.downloadReport(versionId, reportId, genId, {
        projectId,
        expectedDigest: expectedDigest || undefined,
        signal: controller.signal,
        filename: `stacksense-report-${reportId}-${genId.slice(0, 8)}.pdf`,
      });
    } catch (err) {
      if (!isMountedRef.current || controller.signal.aborted) return;
      setDownloadError(err?.message || 'PDF download failed.');
    } finally {
      if (isMountedRef.current) {
        setDownloading(false);
      }
    }
  }, [versionId, projectId, reportId, selectedGenerationId, summary, generationsPage]);

  const cancelDownload = useCallback(() => {
    if (downloadAbortRef.current) {
      downloadAbortRef.current.abort();
      setDownloading(false);
      setDownloadError('Download cancelled by user.');
    }
  }, []);

  return {
    collection,
    reportId,
    setReportId,
    summary,
    generationsPage,
    selectedGenerationId,
    selectGeneration: setSelectedGenerationId,
    loading,
    error,
    cursorIndex,
    hasMoreGenerations: Boolean(generationsPage?.next_cursor),
    nextGenerationsPage,
    prevGenerationsPage,
    downloading,
    downloadError,
    downloadPdf,
    cancelDownload,
    refresh: () => {
      setCursorStack([null]);
      setCursorIndex(0);
      loadReports();
    },
  };
}
