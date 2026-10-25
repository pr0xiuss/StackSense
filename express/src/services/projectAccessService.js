const ProjectAccess = require('../models/ProjectAccess');
const {
  ProjectAccessAlreadyExistsError,
  ProjectAccessNotFoundError,
} = require('../errors/accessErrors');

const projectAccessService = {
  async getAccess(projectId, userId) {
    return await ProjectAccess.findOne({
      project_id: projectId,
      user_id: userId,
    });
  },

  async listProjectAccess(projectId) {
    return await ProjectAccess.find({
      project_id: projectId,
    }).sort({ user_id: 1 });
  },

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
      if (err.code === 11000) {
        throw new ProjectAccessAlreadyExistsError(
          'User already has access to this project.',
          { projectId, userId }
        );
      }
      throw err;
    }
  },

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
