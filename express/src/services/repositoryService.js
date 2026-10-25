const Repository = require('../models/Repository');
const projectAuthorization = require('./projectAuthorization');
const {
  RepositoryNotFoundError,
  RepositoryAlreadyExistsError,
} = require('../errors/repositoryErrors');


const repositoryService = {
  async registerRepository({ projectId, name, description, userId }) {
    await projectAuthorization.requireCreateAccess(projectId, userId);

    const cleanName = name.trim();
    const cleanDesc = description && description.trim() ? description.trim() : null;

    const existing = await Repository.findOne({
      project_id: projectId,
      name: cleanName,
    });
    if (existing) {
      throw new RepositoryAlreadyExistsError();
    }

    try {
      const repository = new Repository({
        project_id: projectId,
        name: cleanName,
        description: cleanDesc,
        status: 'registered',
      });

      return await repository.save();
    } catch (err) {
      if (err.code === 11000) {
        throw new RepositoryAlreadyExistsError();
      }
      throw err;
    }
  },

  async getRepositoryById(projectId, repositoryId, userId) {
    await projectAuthorization.requireAccess(projectId, userId);

    const repository = await Repository.findById(repositoryId);
    if (!repository || repository.project_id !== projectId) {
      throw new RepositoryNotFoundError();
    }

    return repository;
  },

  async listRepositories(projectId, { limit = 50, offset = 0 } = {}, userId) {
    await projectAuthorization.requireAccess(projectId, userId);

    return await Repository.find({ project_id: projectId })
      .sort({ created_at: 1 })
      .skip(offset)
      .limit(limit);
  },

  async updateRepository(projectId, repositoryId, { name, description }, userId) {
    await projectAuthorization.requireUpdateAccess(projectId, userId);

    const repository = await Repository.findById(repositoryId);
    if (!repository || repository.project_id !== projectId) {
      throw new RepositoryNotFoundError();
    }

    if (name !== undefined) {
      const cleanName = name.trim();
      if (cleanName !== repository.name) {
        const conflict = await Repository.findOne({
          project_id: projectId,
          name: cleanName,
        });
        if (conflict && conflict._id !== repositoryId) {
          throw new RepositoryAlreadyExistsError();
        }
        repository.name = cleanName;
      }
    }

    if (description !== undefined) {
      repository.description =
        description && description.trim() ? description.trim() : null;
    }

    try {
      return await repository.save();
    } catch (err) {
      if (err.code === 11000) {
        throw new RepositoryAlreadyExistsError();
      }
      throw err;
    }
  },

  async deleteRepository(projectId, repositoryId, userId) {
    await projectAuthorization.requireDeleteAccess(projectId, userId);

    const existing = await Repository.findById(repositoryId);
    if (!existing || existing.project_id !== projectId) {
      throw new RepositoryNotFoundError();
    }

    const repository = await Repository.findOneAndDelete({
      _id: repositoryId,
      project_id: projectId,
    });

    if (!repository) {
      throw new RepositoryNotFoundError();
    }
  },
};

module.exports = repositoryService;
