const projectAccessService = require('../services/projectAccessService');
const projectAuthorization = require('../services/projectAuthorization');
const userDirectoryService = require('../services/userDirectoryService');

const projectAccessController = {
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

  async listProjectAccess(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId } = req.params;

      await projectAuthorization.requireAccess(projectId, currentUserId);

      const accessList = await projectAccessService.listProjectAccess(projectId);
      const serialized = accessList.map((access) => access.toJSON());
      const usernames = await userDirectoryService.findUsernamesByIds(
        serialized.map((access) => access.user_id)
      );
      return res.status(200).json(serialized.map((access) => ({
        ...access,
        username: usernames.get(access.user_id) || null,
      })));
    } catch (err) {
      next(err);
    }
  },

  async changeRole(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId, userId } = req.params;
      const { role } = req.body;

      await projectAuthorization.requireManageOtherUserAccess(projectId, currentUserId, userId);

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

  async revokeAccess(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId, userId } = req.params;

      await projectAuthorization.requireManageOtherUserAccess(projectId, currentUserId, userId);

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
