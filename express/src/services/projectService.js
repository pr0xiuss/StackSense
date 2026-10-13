const Project = require('../models/Project');

/**
 * Service orchestrating Project CRUD and data operations.
 */
const projectService = {
  /**
   * Create a new project.
   * @param {{ name: string, description?: string | null }} data
   * @returns {Promise<import('mongoose').Document>}
   */
  async createProject({ name, description = null }) {
    const project = new Project({
      name,
      description,
    });
    return await project.save();
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
   * List projects with deterministic sorting and pagination.
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
   * Hard delete a project by ID.
   * @param {string} projectId
   * @returns {Promise<import('mongoose').Document | null>}
   */
  async deleteProject(projectId) {
    return await Project.findByIdAndDelete(projectId);
  },
};

module.exports = projectService;
