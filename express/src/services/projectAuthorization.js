const projectAccessService = require('./projectAccessService');
const { PROJECT_ROLES } = require('../constants/projectRoles');
const { ProjectAccessDeniedError } = require('../errors/accessErrors');

const projectAuthorization = {
  async getAccess(projectId, userId) {
    return await projectAccessService.getAccess(projectId, userId);
  },

  async requireAccess(projectId, userId) {
    const access = await this.getAccess(projectId, userId);
    if (!access) {
      throw new ProjectAccessDeniedError(
        'User does not have access to this project.',
        { projectId, userId }
      );
    }
    return access;
  },

  async requireCreateAccess(projectId, userId) {
    const access = await this.requireAccess(projectId, userId);
    if (!access.canCreate()) {
      throw new ProjectAccessDeniedError(
        'User does not have permission to create resources in this project.',
        { projectId, userId, role: access.role }
      );
    }
    return access;
  },

  async requireUpdateAccess(projectId, userId) {
    const access = await this.requireAccess(projectId, userId);
    if (!access.canUpdate()) {
      throw new ProjectAccessDeniedError(
        'User does not have permission to update resources in this project.',
        { projectId, userId, role: access.role }
      );
    }
    return access;
  },

  async requireDeleteAccess(projectId, userId) {
    const access = await this.requireAccess(projectId, userId);
    if (!access.canDelete()) {
      throw new ProjectAccessDeniedError(
        'User does not have permission to delete this project.',
        { projectId, userId, role: access.role }
      );
    }
    return access;
  },

  async requireManageAccess(projectId, userId) {
    const access = await this.requireAccess(projectId, userId);
    if (![PROJECT_ROLES.OWNER, PROJECT_ROLES.ADMIN].includes(access.role)) {
      throw new ProjectAccessDeniedError(
        'User does not have permission to manage access for this project.',
        { projectId, userId, role: access.role }
      );
    }
    return access;
  },

  async requireManageOtherUserAccess(projectId, currentUserId, targetUserId) {
    const access = await this.requireManageAccess(projectId, currentUserId);
    if (currentUserId === targetUserId) {
      throw new ProjectAccessDeniedError(
        'Users cannot change or revoke their own project access.',
        { projectId, userId: currentUserId }
      );
    }
    return access;
  },
};

module.exports = projectAuthorization;
