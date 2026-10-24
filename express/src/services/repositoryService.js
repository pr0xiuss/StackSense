const Repository = require('../models/Repository');
const Ingestion = require('../models/Ingestion');
const projectAuthorization = require('./projectAuthorization');
const {
  INGESTION_STATUS,
  DEFAULT_STALE_INGESTION_TIMEOUT_MS,
} = require('../constants/ingestionConstants');
const { ActiveIngestionExistsError } = require('../errors/ingestionErrors');
const {
  RepositoryNotFoundError,
  RepositoryAlreadyExistsError,
} = require('../errors/repositoryErrors');

/**
 * Service orchestrating Repository domain use cases within a Project boundary.
 */
const repositoryService = {
  /**
   * Register a new repository under a project.
   * Enforces that current user has create permission (Owner, Admin, Developer).
   *
   * @param {Object} params
   * @param {string} params.projectId
   * @param {string} params.name
   * @param {string|null} [params.description]
   * @param {string} params.userId
   * @returns {Promise<import('mongoose').Document>}
   */
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

  /**
   * Retrieve a repository by identifier within a project.
   * Enforces member access (Owner, Admin, Developer, Viewer).
   *
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {string} userId
   * @returns {Promise<import('mongoose').Document>}
   */
  async getRepositoryById(projectId, repositoryId, userId) {
    await projectAuthorization.requireAccess(projectId, userId);

    const repository = await Repository.findById(repositoryId);
    if (!repository || repository.project_id !== projectId) {
      throw new RepositoryNotFoundError();
    }

    return repository;
  },

  /**
   * List repositories belonging to a project with deterministic pagination.
   *
   * @param {string} projectId
   * @param {Object} [pagination]
   * @param {number} [pagination.limit=50]
   * @param {number} [pagination.offset=0]
   * @param {string} userId
   * @returns {Promise<Array<import('mongoose').Document>>}
   */
  async listRepositories(projectId, { limit = 50, offset = 0 } = {}, userId) {
    await projectAuthorization.requireAccess(projectId, userId);

    return await Repository.find({ project_id: projectId })
      .sort({ created_at: 1 })
      .skip(offset)
      .limit(limit);
  },

  /**
   * Update repository metadata (name, description).
   * Enforces update permission (Owner, Admin, Developer).
   *
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {Object} updates
   * @param {string} [updates.name]
   * @param {string|null} [updates.description]
   * @param {string} userId
   * @returns {Promise<import('mongoose').Document>}
   */
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

  /**
   * Delete a repository from a project.
   * Enforces delete permission (Owner, Admin).
   *
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {string} userId
   * @returns {Promise<void>}
   */
  async deleteRepository(projectId, repositoryId, userId) {
    await projectAuthorization.requireDeleteAccess(projectId, userId);

    const existing = await Repository.findById(repositoryId);
    if (!existing || existing.project_id !== projectId) {
      throw new RepositoryNotFoundError();
    }

    const activeIngestion = await Ingestion.findOne({
      repository_id: repositoryId,
      status: INGESTION_STATUS.PROCESSING,
    });
    if (activeIngestion) {
      const startedAt = activeIngestion.started_at
        ? new Date(activeIngestion.started_at).getTime()
        : 0;
      const isStale = Date.now() - startedAt > DEFAULT_STALE_INGESTION_TIMEOUT_MS;
      if (!isStale) {
        throw new ActiveIngestionExistsError(
          'Cannot delete repository while an ingestion is actively processing.'
        );
      }
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
