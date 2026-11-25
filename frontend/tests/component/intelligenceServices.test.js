import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient } from '../../src/services/apiClient.js';
import { deliveryService } from '../../src/services/deliveryService.js';
import { knowledgeService } from '../../src/services/knowledgeService.js';
import { diagramService } from '../../src/services/diagramService.js';
import { reportService } from '../../src/services/reportService.js';

vi.mock('../../src/services/apiClient.js', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    download: vi.fn(),
  },
}));

describe('Intelligence Services Tests', () => {
  const projectId = '11111111-1111-1111-1111-111111111111';
  const versionId = '22222222-2222-2222-2222-222222222222';
  const reportId = '33333333-3333-3333-3333-333333333333';
  const generationId = '44444444-4444-4444-4444-444444444444';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('deliveryService', () => {
    it('calls getDelivery and validates summary', async () => {
      apiClient.get.mockResolvedValueOnce({ slots: [], overall_state: 'READY' });
      const res = await deliveryService.getDelivery(versionId, { projectId });
      expect(res).toEqual({ slots: [], overall_state: 'READY' });
      expect(apiClient.get).toHaveBeenCalledWith(
        `/architecture-versions/${versionId}/delivery?project_id=${projectId}`,
        expect.any(Object)
      );
    });

    it('calls retryDelivery and validates accepted', async () => {
      apiClient.post.mockResolvedValueOnce({ accepted: true, work_id: versionId });
      const res = await deliveryService.retryDelivery(
        versionId,
        { resource_type: 'diagram', resource_id: versionId, idempotency_key: versionId },
        { projectId }
      );
      expect(res.accepted).toBe(true);
      expect(apiClient.post).toHaveBeenCalledWith(
        `/architecture-versions/${versionId}/delivery/retry?project_id=${projectId}`,
        expect.any(Object),
        expect.any(Object)
      );
    });
  });

  describe('knowledgeService', () => {
    it('serializes repeated array parameters for search()', async () => {
      apiClient.get.mockResolvedValueOnce({ items: [], total_hits: 0, has_more: false });
      await knowledgeService.search(versionId, {
        projectId,
        document_kinds: ['file', 'symbol'],
        q: 'auth',
      });

      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('document_kinds=file'),
        expect.any(Object)
      );
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('document_kinds=symbol'),
        expect.any(Object)
      );
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('q=auth'),
        expect.any(Object)
      );
    });

    it('calls queryKnowledge and getContext', async () => {
      apiClient.post.mockResolvedValueOnce({ facts: [], relationships: [], coverage: {} });
      await knowledgeService.queryKnowledge(versionId, { project_id: projectId }, { projectId });

      apiClient.post.mockResolvedValueOnce({ rationales: [], omissions: [], outcome: 'SUCCESS' });
      await knowledgeService.getContext(versionId, { project_id: projectId }, { projectId });

      expect(apiClient.post).toHaveBeenCalledTimes(2);
    });

    it('calls getEvidence with repeated entity_id parameters', async () => {
      apiClient.get.mockResolvedValueOnce({ items: [], has_more: false });
      await knowledgeService.getEvidence(versionId, {
        projectId,
        entity_id: [versionId, reportId],
      });

      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining(`entity_id=${versionId}`),
        expect.any(Object)
      );
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining(`entity_id=${reportId}`),
        expect.any(Object)
      );
    });
  });

  describe('diagramService', () => {
    it('calls getDiagrams and getDiagramSummary', async () => {
      apiClient.get.mockResolvedValueOnce({ canonical_scope: { project_id: projectId }, items: [] });
      await diagramService.getDiagrams(versionId, { projectId });

      apiClient.get.mockResolvedValueOnce({
        delivery_scope: { project_id: projectId },
        availability: 'READY',
        readability: 'COMPLETE',
      });
      await diagramService.getDiagramSummary(versionId, 'system_overview', { projectId });

      expect(apiClient.get).toHaveBeenCalledTimes(2);
    });

    it('delegates exportDiagramSvg to apiClient.download', async () => {
      apiClient.download.mockResolvedValueOnce({ filename: 'diagram.svg' });
      await diagramService.exportDiagramSvg(versionId, 'system_overview', generationId, { projectId });

      expect(apiClient.download).toHaveBeenCalledWith(
        expect.stringContaining('/export?project_id='),
        expect.objectContaining({ expectedMediaType: 'image/svg+xml' })
      );
    });
  });

  describe('reportService', () => {
    it('calls getReports and getReportSummary', async () => {
      apiClient.get.mockResolvedValueOnce({ items: [] });
      await reportService.getReports(versionId, { projectId });

      apiClient.get.mockResolvedValueOnce({
        report_id: reportId,
        profile: 'overview',
        readability: 'COMPLETE',
      });
      await reportService.getReportSummary(versionId, reportId, { projectId });

      expect(apiClient.get).toHaveBeenCalledTimes(2);
    });

    it('delegates downloadReport to apiClient.download', async () => {
      apiClient.download.mockResolvedValueOnce({ filename: 'report.pdf' });
      await reportService.downloadReport(versionId, reportId, generationId, {
        projectId,
        expectedDigest: 'sha256-abc',
      });

      expect(apiClient.download).toHaveBeenCalledWith(
        expect.stringContaining('/download?project_id='),
        expect.objectContaining({
          expectedMediaType: 'application/pdf',
          expectedDigest: 'sha256-abc',
        })
      );
    });
  });
});
