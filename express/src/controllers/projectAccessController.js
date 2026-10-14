const projectAccessService = require('../services/projectAccessService');
const projectAuthorization = require('../services/projectAuthorization');

/**
 * Controller handling ProjectAccess HTTP requests.
 */
const projectAccessController = {
  /**
   * Grant a user access to a project.
   * Requires: Manage access (owner or admin).
   * Status: 201 Created.
   */
  async grantAccess(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId } = req.params;
      const { user_id, role } = req.body;

      await projectAuthorization.requireManageAccess(projectId, currentUserId);

      const access = await projectAccessService.grantAccess({
        projectId,
        userId: user_id,
        role,
      });

      return res.status(201).json(access);
    } catch (err) {
      next(err);
    }
  },

  /**
   * List all access records for a project.
   * Requires: Read access (owner, admin, developer, or viewer).
   * Status: 200 OK.
   */
  async listProjectAccess(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId } = req.params;

      await projectAuthorization.requireAccess(projectId, currentUserId);

      const accessList = await projectAccessService.listProjectAccess(projectId);
      return res.status(200).json(accessList);
    } catch (err) {
      next(err);
    }
  },

  /**
   * Change a project member's role.
   * Requires: Manage access (owner or admin).
   * Status: 200 OK.
   */
  async changeRole(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId, userId } = req.params;
      const { role } = req.body;

      await projectAuthorization.requireManageAccess(projectId, currentUserId);

      const updated = await projectAccessService.changeRole({
        projectId,
        userId,
        role,
      });

      return res.status(200).json(updated);
    } catch (err) {
      next(err);
    }
  },

  /**
   * Revoke a user's access to a project.
   * Requires: Manage access (owner or admin).
   * Status: 204 No Content.
   */
  async revokeAccess(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId, userId } = req.params;

      await projectAuthorization.requireManageAccess(projectId, currentUserId);

      await projectAccessService.revokeAccess({
        projectId,
        userId,
      });

      return res.status(204).send();
    } catch (err) {
      next(err);
    }
  },
};

module.exports = projectAccessController;
