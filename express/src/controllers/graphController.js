/**
 * Controller for Architecture Graph routes.
 *
 * Enforces authoritative project access (requireAccess for reads, requireManageAccess
 * for rebuild mutations), constructs trusted delegated inputs, forwards to
 * analysisGatewayService in graph mode, and safely returns upstream status and body.
 */
const projectAuthorization = require('../services/projectAuthorization');
const { analysisGatewayService } = require('../services/analysisGatewayService');

const graphController = {
  /**
   * GET /api/v1/architecture-versions/:versionId/graph/status
   */
  async getStatus(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/graph/status`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'graph',
        clientReq: req,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * POST /api/v1/architecture-versions/:versionId/graph/rebuild
   */
  async requestRebuild(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      // Rebuild requires OWNER or ADMIN role
      const access = await projectAuthorization.requireManageAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'POST',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/graph/rebuild`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'graph',
        clientReq: req,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/architecture-versions/:versionId/graph/nodes/:entityId
   */
  async getNodeDetail(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/graph/nodes/${encodeURIComponent(req.params.entityId)}`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'graph',
        clientReq: req,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/architecture-versions/:versionId/graph/window
   */
  async getWindow(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/graph/window`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'graph',
        clientReq: req,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/architecture-versions/:versionId/graph/nodes/:entityId/neighborhood
   */
  async getNeighborhood(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/graph/nodes/${encodeURIComponent(req.params.entityId)}/neighborhood`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'graph',
        clientReq: req,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/architecture-versions/:versionId/graph/nodes/:entityId/dependencies
   */
  async getDependencies(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/graph/nodes/${encodeURIComponent(req.params.entityId)}/dependencies`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'graph',
        clientReq: req,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/architecture-versions/:versionId/graph/nodes/:entityId/dependents
   */
  async getDependents(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/graph/nodes/${encodeURIComponent(req.params.entityId)}/dependents`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'graph',
        clientReq: req,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/architecture-versions/:versionId/graph/nodes/:entityId/containment
   */
  async getContainment(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/graph/nodes/${encodeURIComponent(req.params.entityId)}/containment`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'graph',
        clientReq: req,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/architecture-versions/:versionId/graph/paths
   */
  async getBoundedPaths(req, res, next) {
    try {
      const projectId = req.validatedQuery.project_id;
      const access = await projectAuthorization.requireAccess(projectId, req.user.id);

      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: `/architecture-versions/${encodeURIComponent(req.params.versionId)}/graph/paths`,
        query: req.validatedQuery,
        user: req.user,
        role: String(access.role).toUpperCase(),
        projectId,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'graph',
        clientReq: req,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/health/graph/query
   */
  async getQueryHealth(req, res, next) {
    try {
      const { status, body } = await analysisGatewayService.request({
        method: 'GET',
        path: '/health/graph/query',
        query: {},
        user: req.user,
        correlationId: req.headers['x-correlation-id'],
        responseMode: 'graph',
        clientReq: req,
      });

      return res.status(status).json(body);
    } catch (err) {
      next(err);
    }
  },
};

module.exports = graphController;

