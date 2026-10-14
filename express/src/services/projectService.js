const Project = require('../models/Project');
const ProjectAccess = require('../models/ProjectAccess');
const projectAccessService = require('./projectAccessService');

/**
 * Service orchestrating Project CRUD and data operations.
 */
const projectService = {
  /**
   * Create a new project and optionally grant creator OWNER access.
   * @param {{ name: string, description?: string | null, ownerId?: string | null }} data
   * @returns {Promise<import('mongoose').Document>}
   */
  async createProject({ name, description = null, ownerId = null }) {
    const project = new Project({
      name,
      description,
    });
    const savedProject = await project.save();

    if (ownerId) {
      await projectAccessService.grantAccess({
        projectId: savedProject._id,
        userId: ownerId,
        role: 'owner',
      });
    }

    return savedProject;
  },

  /**
   * Retrieve a project by its unique UUID v4 identifier.
   * @param {string} projectId
   * @returns {Promise<import('mongoose').Document | null>}
   */
  async getProjectById(projectId) {
    return await Project.findById(projectId);
  },

  /**
   * List projects accessible to a specific user with pagination.
   * @param {string} userId
   * @param {{ limit?: number, offset?: number }} [options]
   * @returns {Promise<Array<import('mongoose').Document>>}
   */
  async listUserProjects(userId, { limit = 50, offset = 0 } = {}) {
    const accessRecords = await projectAccessService.listUserAccess(userId, {
      limit,
      offset,
    });

    const projectIds = accessRecords.map((a) => a.project_id);
    if (projectIds.length === 0) {
      return [];
    }

    const projects = await Project.find({ _id: { $in: projectIds } });
    const projectMap = new Map(projects.map((p) => [p._id, p]));

    return projectIds.map((id) => projectMap.get(id)).filter(Boolean);
  },

  /**
   * List projects with deterministic sorting and pagination (unscoped).
   * @param {{ limit?: number, offset?: number }} [options]
   * @returns {Promise<Array<import('mongoose').Document>>}
   */
  async listProjects({ limit = 50, offset = 0 } = {}) {
    const parsedLimit = Math.max(1, Math.min(100, Number(limit) || 50));
    const parsedOffset = Math.max(0, Number(offset) || 0);

    return await Project.find()
      .sort({ created_at: -1 })
      .skip(parsedOffset)
      .limit(parsedLimit);
  },

  /**
   * Update project metadata.
   * @param {string} projectId
   * @param {{ name?: string, description?: string | null }} data
   * @returns {Promise<import('mongoose').Document | null>}
   */
  async updateProject(projectId, data) {
    const project = await Project.findById(projectId);
    if (!project) {
      return null;
    }

    if (data.name !== undefined) {
      project.name = data.name;
    }
    if (data.description !== undefined) {
      project.description = data.description;
    }

    return await project.save();
  },

  /**
   * Hard delete a project by ID and cascade delete associated access records.
   * @param {string} projectId
   * @returns {Promise<import('mongoose').Document | null>}
   */
  async deleteProject(projectId) {
    const project = await Project.findByIdAndDelete(projectId);
    if (project) {
      await ProjectAccess.deleteMany({ project_id: projectId });
    }
    return project;
  },
};

module.exports = projectService;
