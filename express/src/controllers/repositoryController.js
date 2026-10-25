const repositoryService = require('../services/repositoryService');

const repositoryController = {
   //POST /api/v1/projects/:projectId/repositories
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

  //GET /api/v1/projects/:projectId/repositories
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

  //GET /api/v1/projects/:projectId/repositories/:repositoryId
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

  //PATCH /api/v1/projects/:projectId/repositories/:repositoryId
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

  //DELETE /api/v1/projects/:projectId/repositories/:repositoryId
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
