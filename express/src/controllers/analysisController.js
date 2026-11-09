const projectAuthorization = require('../services/projectAuthorization');
const { analysisGatewayService } = require('../services/analysisGatewayService');

const analysisController = {
  /**
   * POST /api/v1/analyses
   * Enqueue a new analysis job for project repository revision.
   */
  async createAnalysis(req, res, next) {
    try {
      const projectId = req.body.project_id;
      const access = await projectAuthorization.requireCreateAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'POST',
        path: '/analyses',
        body: req.body,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
      });

      res.status(202).json(result);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/analyses
   * Paginated list of analyses for a project with optional repository and status filters.
   */
  async listAnalyses(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'GET',
        path: '/analyses',
        query: req.query,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
      });

      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/analyses/:analysisId
   * Retrieve authoritative lifecycle state for an analysis run.
   */
  async getAnalysis(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'GET',
        path: `/analyses/${encodeURIComponent(req.params.analysisId)}`,
        query: { project_id: projectId },
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
      });

      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  },

  /**
   * POST /api/v1/analyses/:analysisId/cancel
   * Request cooperative cancellation for an active analysis.
   */
  async cancelAnalysis(req, res, next) {
    try {
      const projectId = req.query.project_id || (req.body && req.body.project_id);
      const access = await projectAuthorization.requireCreateAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'POST',
        path: `/analyses/${encodeURIComponent(req.params.analysisId)}/cancel`,
        query: { project_id: projectId },
        body: req.body || {},
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
      });

      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/analyses/:analysisId/events
   * Server-Sent Events notification stream with sequence replay.
   */
  async streamEvents(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      await analysisGatewayService.streamEvents({
        analysisId: req.params.analysisId,
        projectId,
        afterSequence: req.query.after_sequence || 0,
        lastEventId: req.headers['last-event-id'],
        user: req.user,
        role: String(access.role).toUpperCase(),
        correlationId: req.headers['x-correlation-id'],
        clientReq: req,
        clientRes: res,
      });
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/analyses/:analysisId/diagnostics
   * Paginated diagnostics for an analysis run.
   */
  async listDiagnostics(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'GET',
        path: `/analyses/${encodeURIComponent(req.params.analysisId)}/diagnostics`,
        query: req.query,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
      });

      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/analyses/:analysisId/architecture
   * Retrieve published Architecture Version summary for an analysis.
   */
  async getAnalysisArchitecture(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'GET',
        path: `/analyses/${encodeURIComponent(req.params.analysisId)}/architecture`,
        query: { project_id: projectId },
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
      });

      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  },
};

module.exports = analysisController;
