const projectAccessService = require('./projectAccessService');
const { PROJECT_ROLES } = require('../constants/projectRoles');
const { ProjectAccessDeniedError } = require('../errors/accessErrors');

/**
 * Service centralizing project-scoped authorization policies.
 */
const projectAuthorization = {
  /**
   * Return user's access record for a project.
   * @param {string} projectId
   * @param {string} userId
   * @returns {Promise<import('mongoose').Document | null>}
   */
  async getAccess(projectId, userId) {
    return await projectAccessService.getAccess(projectId, userId);
  },

  /**
   * Require the user to hold access to the project.
   * Throws ProjectAccessDeniedError if user is not a member.
   * @param {string} projectId
   * @param {string} userId
   * @returns {Promise<import('mongoose').Document>}
   */
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

  /**
   * Require the user to have project creation permission (owner, admin, developer).
   * @param {string} projectId
   * @param {string} userId
   * @returns {Promise<import('mongoose').Document>}
   */
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

  /**
   * Require the user to have project update permission (owner, admin, developer).
   * @param {string} projectId
   * @param {string} userId
   * @returns {Promise<import('mongoose').Document>}
   */
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

  /**
   * Require the user to have project deletion permission (owner, admin).
   * @param {string} projectId
   * @param {string} userId
   * @returns {Promise<import('mongoose').Document>}
   */
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

  /**
   * Require permission to manage project access (owner, admin).
   * @param {string} projectId
   * @param {string} userId
   * @returns {Promise<import('mongoose').Document>}
   */
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

  /**
   * Require permission to manage another user's project access.
   * Self role changes and self revocation are intentionally forbidden so a
   * manager cannot accidentally remove or downgrade their own access.
   * @param {string} projectId
   * @param {string} currentUserId
   * @param {string} targetUserId
   * @returns {Promise<import('mongoose').Document>}
   */
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
