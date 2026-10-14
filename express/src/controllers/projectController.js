const projectService = require('../services/projectService');
const projectAuthorization = require('../services/projectAuthorization');

/**
 * Controller handling HTTP requests for Project endpoints.
 */
const projectController = {
  /**
   * POST /api/v1/projects
   * Create a new project and grant creator OWNER access.
   */
  async createProject(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { name, description } = req.body;
      const project = await projectService.createProject({
        name: name.trim(),
        description: description ? description.trim() : null,
        ownerId: currentUserId,
      });

      res.status(201).json(project.toJSON());
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/projects/:projectId
   * Retrieve a project by UUID v4 accessible to the current user.
   */
  async getProject(req, res, next) {
    try {
      const currentUserId = req.user.id;
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

      // Enforce project isolation: outsider access returns 404 to avoid enumeration
      try {
        await projectAuthorization.requireAccess(projectId, currentUserId);
      } catch (err) {
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
   * List projects accessible to the current user with pagination.
   */
  async listProjects(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { limit, offset } = req.pagination || { limit: 50, offset: 0 };
      const projects = await projectService.listUserProjects(currentUserId, { limit, offset });

      res.status(200).json(projects.map((p) => p.toJSON()));
    } catch (err) {
      next(err);
    }
  },

  /**
   * PATCH /api/v1/projects/:projectId
   * Update project name and/or description when authorized.
   */
  async updateProject(req, res, next) {
    try {
      const currentUserId = req.user.id;
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

      // Authorize update: requires OWNER, ADMIN, or DEVELOPER
      await projectAuthorization.requireUpdateAccess(projectId, currentUserId);

      const updateData = {};
      if (req.body.name !== undefined) {
        updateData.name = req.body.name.trim();
      }
      if (req.body.description !== undefined) {
        updateData.description = req.body.description ? req.body.description.trim() : null;
      }

      const updated = await projectService.updateProject(projectId, updateData);
      res.status(200).json(updated.toJSON());
    } catch (err) {
      next(err);
    }
  },

  /**
   * DELETE /api/v1/projects/:projectId
   * Hard delete a project when authorized.
   */
  async deleteProject(req, res, next) {
    try {
      const currentUserId = req.user.id;
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

      // Authorize deletion: requires OWNER or ADMIN
      await projectAuthorization.requireDeleteAccess(projectId, currentUserId);

      await projectService.deleteProject(projectId);
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  },
};

module.exports = projectController;
