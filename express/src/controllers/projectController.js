const projectService = require('../services/projectService');

/**
 * Controller handling HTTP requests for Project endpoints.
 */
const projectController = {
  /**
   * POST /api/v1/projects
   * Create a new project.
   */
  async createProject(req, res, next) {
    try {
      const { name, description } = req.body;
      const project = await projectService.createProject({
        name: name.trim(),
        description: description ? description.trim() : null,
      });

      res.status(201).json(project.toJSON());
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/projects/:projectId
   * Retrieve a project by UUID v4.
   */
  async getProject(req, res, next) {
    try {
      const { projectId } = req.params;
      const project = await projectService.getProjectById(projectId);

      if (!project) {
        return res.status(404).json({
          error: {
            code: 'project_not_found',
            message: 'Project not found.',
            details: { projectId },
          },
        });
      }

      res.status(200).json(project.toJSON());
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/projects
   * List projects with pagination.
   */
  async listProjects(req, res, next) {
    try {
      const { limit, offset } = req.pagination || { limit: 50, offset: 0 };
      const projects = await projectService.listProjects({ limit, offset });

      res.status(200).json(projects.map((p) => p.toJSON()));
    } catch (err) {
      next(err);
    }
  },

  /**
   * PATCH /api/v1/projects/:projectId
   * Update project name and/or description.
   */
  async updateProject(req, res, next) {
    try {
      const { projectId } = req.params;
      const updateData = {};

      if (req.body.name !== undefined) {
        updateData.name = req.body.name.trim();
      }
      if (req.body.description !== undefined) {
        updateData.description = req.body.description ? req.body.description.trim() : null;
      }

      const project = await projectService.updateProject(projectId, updateData);

      if (!project) {
        return res.status(404).json({
          error: {
            code: 'project_not_found',
            message: 'Project not found.',
            details: { projectId },
          },
        });
      }

      res.status(200).json(project.toJSON());
    } catch (err) {
      next(err);
    }
  },

  /**
   * DELETE /api/v1/projects/:projectId
   * Hard delete a project.
   */
  async deleteProject(req, res, next) {
    try {
      const { projectId } = req.params;
      const deleted = await projectService.deleteProject(projectId);

      if (!deleted) {
        return res.status(404).json({
          error: {
            code: 'project_not_found',
            message: 'Project not found.',
            details: { projectId },
          },
        });
      }

      res.status(204).send();
    } catch (err) {
      next(err);
    }
  },
};

module.exports = projectController;
