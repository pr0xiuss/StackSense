const projectService = require('../services/projectService');
const projectAuthorization = require('../services/projectAuthorization');

const projectController = {
  //POST /api/v1/projects
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

  //GET /api/v1/projects/:projectId
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

      // Enforce project isolation
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

  //GET /api/v1/projects
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

  //PATCH /api/v1/projects/:projectId
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

      // Authorize update requires OWNER, ADMIN, DEVELOPER
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

  //DELETE /api/v1/projects/:projectId
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

      // Authorize deletion requires OWNER, ADMIN
      await projectAuthorization.requireDeleteAccess(projectId, currentUserId);

      await projectService.deleteProject(projectId);
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  },
};

module.exports = projectController;
