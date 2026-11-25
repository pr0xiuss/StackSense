/**
 * Report Service (Frontend)
 *
 * Interacts with C4 reports, generation history, and verified binary PDF download.
 */
import { apiClient } from './apiClient.js';
import {
  validateReportCollection,
  validateReportSummary,
  validateReportGenerationPage,
  validateReportGenerationSummary,
} from '../contracts/intelligenceContracts.js';

export const reportService = {
  /**
   * Retrieve ReportCollection.
   */
  async getReports(versionId, params = {}, { signal, ...options } = {}) {
    if (!versionId) throw new Error('versionId is required');
    if (!params.projectId) throw new Error('projectId is required');

    const qs = new URLSearchParams({ project_id: params.projectId });
    if (params.limit) qs.set('limit', String(params.limit));
    if (params.cursor) qs.set('cursor', params.cursor);

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/reports?${qs.toString()}`,
      { signal, ...options }
    );
    return validateReportCollection(data);
  },

  /**
   * Retrieve ReportSummary for a specific report.
   */
  async getReportSummary(versionId, reportId, { projectId, generationId, signal, ...options } = {}) {
    if (!versionId || !reportId) throw new Error('versionId and reportId are required');
    if (!projectId) throw new Error('projectId is required');

    const qs = new URLSearchParams({ project_id: projectId });
    if (generationId) qs.set('generation_id', generationId);

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/reports/${encodeURIComponent(reportId)}?${qs.toString()}`,
      { signal, ...options }
    );
    return validateReportSummary(data);
  },

  /**
   * Retrieve paginated ReportGenerationPage history.
   */
  async getReportGenerations(versionId, reportId, params = {}, { signal, ...options } = {}) {
    if (!versionId || !reportId) throw new Error('versionId and reportId are required');
    if (!params.projectId) throw new Error('projectId is required');

    const qs = new URLSearchParams({ project_id: params.projectId });
    if (params.limit) qs.set('limit', String(params.limit));
    if (params.cursor) qs.set('cursor', params.cursor);

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/reports/${encodeURIComponent(reportId)}/generations?${qs.toString()}`,
      { signal, ...options }
    );
    return validateReportGenerationPage(data);
  },

  /**
   * Retrieve ReportGenerationSummary metadata for an exact generation.
   */
  async getReportGenerationDetail(versionId, reportId, generationId, { projectId, signal, ...options } = {}) {
    if (!versionId || !reportId || !generationId) throw new Error('versionId, reportId, and generationId are required');
    if (!projectId) throw new Error('projectId is required');

    const data = await apiClient.get(
      `/architecture-versions/${encodeURIComponent(versionId)}/reports/${encodeURIComponent(reportId)}/generations/${encodeURIComponent(generationId)}?project_id=${encodeURIComponent(projectId)}`,
      { signal, ...options }
    );
    return validateReportGenerationSummary(data);
  },

  /**
   * Download verified exact historical report generation PDF.
   */
  async downloadReport(versionId, reportId, generationId, { projectId, expectedDigest, signal, filename, ...options } = {}) {
    if (!versionId || !reportId || !generationId) throw new Error('versionId, reportId, and generationId are required');
    if (!projectId) throw new Error('projectId is required');

    return apiClient.download(
      `/architecture-versions/${encodeURIComponent(versionId)}/reports/${encodeURIComponent(reportId)}/generations/${encodeURIComponent(generationId)}/download?project_id=${encodeURIComponent(projectId)}`,
      {
        expectedMediaType: 'application/pdf',
        expectedDigest,
        signal,
        filename: filename || `report-${versionId}-${generationId}.pdf`,
        ...options,
      }
    );
  },
};
