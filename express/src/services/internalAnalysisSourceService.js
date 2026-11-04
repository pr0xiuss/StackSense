const Repository = require('../models/Repository');
const RepositoryRevision = require('../models/RepositoryRevision');
const RepositoryArtifact = require('../models/RepositoryArtifact');
const LocalStorageService = require('./storage/localStorageService');
const storageConfig = require('../config/storageConfig');
const { RepositoryNotFoundError } = require('../errors/repositoryErrors');
const {
  IngestionError,
  RevisionNotFoundError,
} = require('../errors/ingestionErrors');

class InternalAnalysisSourceService {
  constructor(options = {}) {
    this._repositoryModel = options.repositoryModel || Repository;
    this._revisionModel = options.revisionModel || RepositoryRevision;
    this._artifactModel = options.artifactModel || RepositoryArtifact;
    this._storageService =
      options.storageService || new LocalStorageService(storageConfig.storageRoot);
  }

  async _requireRevision(projectId, repositoryId, revisionId) {
    const repository = await this._repositoryModel.findById(repositoryId);
    if (!repository || repository.project_id !== projectId) {
      throw new RepositoryNotFoundError();
    }
    const revision = await this._revisionModel.findById(revisionId);
    if (
      !revision ||
      revision.project_id !== projectId ||
      revision.repository_id !== repositoryId
    ) {
      throw new RevisionNotFoundError();
    }
    return revision;
  }

  async getManifest(projectId, repositoryId, revisionId) {
    const revision = await this._requireRevision(projectId, repositoryId, revisionId);
    const artifacts = await this._artifactModel
      .find({ revision_id: revisionId })
      .sort({ path: 1 });

    return {
      revision: revision.toJSON(),
      artifacts: artifacts.map((artifact) => {
        const value = artifact.toJSON();
        delete value.storage_key;
        return value;
      }),
    };
  }

  async openArtifact(projectId, repositoryId, revisionId, artifactId) {
    await this._requireRevision(projectId, repositoryId, revisionId);
    const artifact = await this._artifactModel.findById(artifactId);
    if (
      !artifact ||
      artifact.project_id !== projectId ||
      artifact.repository_id !== repositoryId ||
      artifact.revision_id !== revisionId
    ) {
      throw new IngestionError(
        'Repository artifact not found.',
        'artifact_not_found',
        404
      );
    }
    return {
      artifact,
      stream: await this._storageService.get(artifact.storage_key),
    };
  }
}

module.exports = {
  InternalAnalysisSourceService,
  internalAnalysisSourceService: new InternalAnalysisSourceService(),
};
