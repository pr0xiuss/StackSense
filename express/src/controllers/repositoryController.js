const repositoryService = require('../services/repositoryService');

/**
 * Controller handling HTTP requests for Repository endpoints.
 */
const repositoryController = {
  /**
   * POST /api/v1/projects/:projectId/repositories
   * Register a new repository within a project.
   */
  async registerRepository(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId } = req.params;
      const { name, description } = req.body;

      const repository = await repositoryService.registerRepository({
        projectId,
        name,
        description,
        userId: currentUserId,
      });

      res.status(201).json(repository.toJSON());
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/projects/:projectId/repositories
   * List repositories belonging to a project with pagination.
   */
  async listRepositories(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId } = req.params;
      const { limit, offset } = req.pagination || { limit: 50, offset: 0 };

      const repositories = await repositoryService.listRepositories(
        projectId,
        { limit, offset },
        currentUserId
      );

      res.status(200).json(repositories.map((r) => r.toJSON()));
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /api/v1/projects/:projectId/repositories/:repositoryId
   * Retrieve a specific repository within a project.
   */
  async getRepository(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId, repositoryId } = req.params;

      const repository = await repositoryService.getRepositoryById(
        projectId,
        repositoryId,
        currentUserId
      );

      res.status(200).json(repository.toJSON());
    } catch (err) {
      next(err);
    }
  },

  /**
   * PATCH /api/v1/projects/:projectId/repositories/:repositoryId
   * Update repository metadata.
   */
  async updateRepository(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId, repositoryId } = req.params;
      const { name, description } = req.body;

      const repository = await repositoryService.updateRepository(
        projectId,
        repositoryId,
        { name, description },
        currentUserId
      );

      res.status(200).json(repository.toJSON());
    } catch (err) {
      next(err);
    }
  },

  /**
   * DELETE /api/v1/projects/:projectId/repositories/:repositoryId
   * Delete a repository from a project.
   */
  async deleteRepository(req, res, next) {
    try {
      const currentUserId = req.user.id;
      const { projectId, repositoryId } = req.params;

      await repositoryService.deleteRepository(
        projectId,
        repositoryId,
        currentUserId
      );

      res.status(204).send();
    } catch (err) {
      next(err);
    }
  },
};

module.exports = repositoryController;
