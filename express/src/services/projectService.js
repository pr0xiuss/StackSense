const Project = require('../models/Project');
const ProjectAccess = require('../models/ProjectAccess');
const projectAccessService = require('./projectAccessService');

const projectService = {
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

  async getProjectById(projectId) {
    return await Project.findById(projectId);
  },

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

  async listProjects({ limit = 50, offset = 0 } = {}) {
    const parsedLimit = Math.max(1, Math.min(100, Number(limit) || 50));
    const parsedOffset = Math.max(0, Number(offset) || 0);

    return await Project.find()
      .sort({ created_at: -1 })
      .skip(parsedOffset)
      .limit(parsedLimit);
  },

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

  async deleteProject(projectId) {
    const project = await Project.findByIdAndDelete(projectId);
    if (project) {
      await ProjectAccess.deleteMany({ project_id: projectId });
    }
    return project;
  },
};

module.exports = projectService;
