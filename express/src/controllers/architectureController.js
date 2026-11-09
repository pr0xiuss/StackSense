const projectAuthorization = require('../services/projectAuthorization');
const { analysisGatewayService } = require('../services/analysisGatewayService');

const architectureController = {
  /**
   * GET /api/v1/architecture-versions/:versionId
   */
  async getArchitectureVersion(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}`,
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
   * GET /api/v1/architecture-versions/:versionId/entities
   */
  async listArchitectureEntities(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/entities`,
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
   * GET /api/v1/architecture-versions/:versionId/entities/:entityId
   */
  async getArchitectureEntity(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/entities/${encodeURIComponent(req.params.entityId)}`,
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
   * GET /api/v1/architecture-versions/:versionId/relationships
   */
  async listArchitectureRelationships(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/relationships`,
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
   * GET /api/v1/architecture-versions/:versionId/evidence
   */
  async listArchitectureEvidence(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/evidence`,
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
   * GET /api/v1/architecture-versions/:versionId/unresolved
   */
  async listArchitectureUnresolved(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/unresolved`,
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
   * GET /api/v1/architecture-versions/:versionId/conflicts
   */
  async listArchitectureConflicts(req, res, next) {
    try {
      const projectId = req.query.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const result = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/conflicts`,
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
};

module.exports = architectureController;
