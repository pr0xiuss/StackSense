const ProjectAccess = require('../models/ProjectAccess');
const {
  ProjectAccessAlreadyExistsError,
  ProjectAccessNotFoundError,
} = require('../errors/accessErrors');

/**
 * Service orchestrating ProjectAccess lifecycle operations and persistence.
 */
const projectAccessService = {
  /**
   * Retrieve a user's access record for a project.
   * @param {string} projectId
   * @param {string} userId
   * @returns {Promise<import('mongoose').Document | null>}
   */
  async getAccess(projectId, userId) {
    return await ProjectAccess.findOne({
      project_id: projectId,
      user_id: userId,
    });
  },

  /**
   * List all access records for a specific project.
   * @param {string} projectId
   * @returns {Promise<Array<import('mongoose').Document>>}
   */
  async listProjectAccess(projectId) {
    return await ProjectAccess.find({
      project_id: projectId,
    }).sort({ user_id: 1 });
  },

  /**
   * List all project access records for a specific user with pagination.
   * @param {string} userId
   * @param {{ limit?: number, offset?: number }} [options]
   * @returns {Promise<Array<import('mongoose').Document>>}
   */
  async listUserAccess(userId, { limit = 50, offset = 0 } = {}) {
    const parsedLimit = Math.max(1, Math.min(100, Number(limit) || 50));
    const parsedOffset = Math.max(0, Number(offset) || 0);

    return await ProjectAccess.find({
      user_id: userId,
    })
      .sort({ project_id: 1 })
      .skip(parsedOffset)
      .limit(parsedLimit);
  },

  /**
   * Grant a user access to a project.
   * @param {{ projectId: string, userId: string, role: string }} params
   * @returns {Promise<import('mongoose').Document>}
   */
  async grantAccess({ projectId, userId, role }) {
    const existing = await this.getAccess(projectId, userId);
    if (existing) {
      throw new ProjectAccessAlreadyExistsError(
        'User already has access to this project.',
        { projectId, userId }
      );
    }

    const access = new ProjectAccess({
      project_id: projectId,
      user_id: userId,
      role,
    });

    try {
      return await access.save();
    } catch (err) {
      // Concurrency race: handle MongoDB compound index duplicate key error (E11000)
      if (err.code === 11000) {
        throw new ProjectAccessAlreadyExistsError(
          'User already has access to this project.',
          { projectId, userId }
        );
      }
      throw err;
    }
  },

  /**
   * Update a user's role within a project.
   * @param {{ projectId: string, userId: string, role: string }} params
   * @returns {Promise<import('mongoose').Document>}
   */
  async changeRole({ projectId, userId, role }) {
    const access = await this.getAccess(projectId, userId);
    if (!access) {
      throw new ProjectAccessNotFoundError(
        'Project access record does not exist.',
        { projectId, userId }
      );
    }

    access.role = role;
    return await access.save();
  },

  /**
   * Revoke a user's access to a project.
   * @param {{ projectId: string, userId: string }} params
   * @returns {Promise<void>}
   */
  async revokeAccess({ projectId, userId }) {
    const access = await this.getAccess(projectId, userId);
    if (!access) {
      throw new ProjectAccessNotFoundError(
        'Project access record does not exist.',
        { projectId, userId }
      );
    }

    await ProjectAccess.deleteOne({ _id: access._id });
  },
};

module.exports = projectAccessService;
