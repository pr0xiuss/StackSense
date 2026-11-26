/**
 * Controller for Platform Transport and Intelligence routes.
 *
 * Enforces authoritative project access (requireAccess for reads, requireManageAccess
 * for mutations), constructs trusted delegated inputs, forwards to
 * analysisGatewayService in intelligence responseMode, and streams binary artifacts.
 */
const projectAuthorization = require('../services/projectAuthorization');
const { analysisGatewayService } = require('../services/analysisGatewayService');
const { analysisConfig } = require('../config/analysisConfig');

const intelligenceController = {
  /**
   * 1. GET /api/v1/architecture-versions/:versionId/delivery
   */
  async getDelivery(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/delivery`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 2. POST /api/v1/architecture-versions/:versionId/delivery/retry
   */
  async retryDelivery(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireManageAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'POST',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/delivery/retry`,
        query: req.validatedQuery,
        body: req.body,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 3. GET /api/v1/architecture-versions/:versionId/search/status
   */
  async getSearchStatus(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/search/status`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 4. GET /api/v1/architecture-versions/:versionId/search
   */
  async search(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/search`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 5. POST /api/v1/architecture-versions/:versionId/search/rebuild
   */
  async rebuildSearch(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireManageAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'POST',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/search/rebuild`,
        query: req.validatedQuery,
        body: req.body,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 6. POST /api/v1/architecture-versions/:versionId/knowledge/query
   */
  async queryKnowledge(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'POST',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/knowledge/query`,
        query: req.validatedQuery,
        body: req.body,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        timeoutMs: analysisConfig.intelligenceLongTimeoutMs,
        maxBytes: analysisConfig.intelligenceC3ResponseMaxBytes,
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 7. POST /api/v1/architecture-versions/:versionId/knowledge/context
   */
  async getContext(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'POST',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/knowledge/context`,
        query: req.validatedQuery,
        body: req.body,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        timeoutMs: analysisConfig.intelligenceLongTimeoutMs,
        maxBytes: analysisConfig.intelligenceC3ResponseMaxBytes,
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 8. GET /api/v1/architecture-versions/:versionId/knowledge/evidence
   */
  async getEvidence(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/knowledge/evidence`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        maxBytes: analysisConfig.intelligenceC3ResponseMaxBytes,
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 9. GET /api/v1/architecture-versions/:versionId/diagrams
   */
  async getDiagrams(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/diagrams`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 10. GET /api/v1/architecture-versions/:versionId/diagrams/:template
   */
  async getLocalDiagramPreview(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);
      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/diagrams/${encodeURIComponent(req.params.template)}/local-preview`,
        query: req.validatedQuery, user: req.user, role: String(access.role).toUpperCase(),
        projectId, correlationId: req.headers['x-correlation-id'], responseMode: 'intelligence',
        clientReq: req, clientRes: res, timeoutMs: 180000, maxBytes: 45000000,
      });
      return res.status(status).json(body);
    } catch (err) { next(err); }
  },

  async getDiagramSummary(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/diagrams/${encodeURIComponent(req.params.template)}`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 11. GET /api/v1/architecture-versions/:versionId/diagrams/:template/generations
   */
  async getDiagramGenerations(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/diagrams/${encodeURIComponent(req.params.template)}/generations`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 12. GET /api/v1/architecture-versions/:versionId/diagrams/:template/generations/:generationId/spec
   */
  async getDiagramSpec(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/diagrams/${encodeURIComponent(req.params.template)}/generations/${encodeURIComponent(req.params.generationId)}/spec`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        maxBytes: analysisConfig.intelligenceDiagramSpecMaxBytes,
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 13. GET /api/v1/architecture-versions/:versionId/diagrams/:template/generations/:generationId/layout
   */
  async getDiagramLayout(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/diagrams/${encodeURIComponent(req.params.template)}/generations/${encodeURIComponent(req.params.generationId)}/layout`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        maxBytes: analysisConfig.intelligenceDiagramLayoutMaxBytes,
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 14. POST /api/v1/architecture-versions/:versionId/diagrams/:template/generations/:generationId/view
   */
  async viewDiagram(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'POST',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/diagrams/${encodeURIComponent(req.params.template)}/generations/${encodeURIComponent(req.params.generationId)}/view`,
        query: req.validatedQuery,
        body: req.body,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        timeoutMs: analysisConfig.intelligenceLongTimeoutMs,
        maxBytes: analysisConfig.intelligenceDiagramLayoutMaxBytes,
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 15. GET /api/v1/architecture-versions/:versionId/diagrams/:template/generations/:generationId/members
   */
  async getDiagramMembers(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/diagrams/${encodeURIComponent(req.params.template)}/generations/${encodeURIComponent(req.params.generationId)}/members`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 16. GET /api/v1/architecture-versions/:versionId/diagrams/:template/generations/:generationId/export
   */
  async exportDiagram(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);
      const format = req.validatedQuery.format || 'json';

      if (format === 'svg') {
        return await analysisGatewayService.streamArtifact({
          method: 'GET',
          path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/diagrams/${encodeURIComponent(req.params.template)}/generations/${encodeURIComponent(req.params.generationId)}/export`,
          query: req.validatedQuery,
          user: req.user,
          role: String(access.role).toUpperCase(),
          projectId,
          correlationId: req.headers['x-correlation-id'],
          clientReq: req,
          clientRes: res,
          expectedMediaType: 'image/svg+xml',
          maxBytes: analysisConfig.intelligenceDiagramSvgMaxBytes,
          attachmentFilename: `diagram-${req.params.template}-${req.params.generationId}.svg`,
        });
      }

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/diagrams/${encodeURIComponent(req.params.template)}/generations/${encodeURIComponent(req.params.generationId)}/export`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        maxBytes: analysisConfig.intelligenceDiagramExportMaxBytes,
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 17. GET /api/v1/architecture-versions/:versionId/reports
   */
  async getReports(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/reports`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 18. GET /api/v1/architecture-versions/:versionId/reports/:reportId
   */
  async getReportSummary(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/reports/${encodeURIComponent(req.params.reportId)}`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 19. GET /api/v1/architecture-versions/:versionId/reports/:reportId/generations
   */
  async getReportGenerations(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/reports/${encodeURIComponent(req.params.reportId)}/generations`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 20. GET /api/v1/architecture-versions/:versionId/reports/:reportId/generations/:generationId
   */
  async getReportGenerationDetail(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/reports/${encodeURIComponent(req.params.reportId)}/generations/${encodeURIComponent(req.params.generationId)}`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'intelligence',
        clientReq: req,
        clientRes: res,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * 21. GET /api/v1/architecture-versions/:versionId/reports/:reportId/generations/:generationId/download
   */
  async downloadReportGeneration(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      return await analysisGatewayService.streamArtifact({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/reports/${encodeURIComponent(req.params.reportId)}/generations/${encodeURIComponent(req.params.generationId)}/download`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        clientReq: req,
        clientRes: res,
        expectedMediaType: 'application/pdf',
        maxBytes: analysisConfig.intelligencePdfMaxBytes,
        attachmentFilename: `report-architecture-${req.params.versionId}-${req.params.generationId}.pdf`,
      });
    } catch (err) {
      next(err);
    }
  },
};

module.exports = intelligenceController;
