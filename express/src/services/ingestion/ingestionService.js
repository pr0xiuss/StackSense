const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

const storageConfig = require('../../config/storageConfig');
const {
  INGESTION_STATUS,
  DEFAULT_STALE_INGESTION_TIMEOUT_MS,
  normalizeSourceType,
} = require('../../constants/ingestionConstants');

const projectAuthorization = require('../projectAuthorization');
const Repository = require('../../models/Repository');
const Ingestion = require('../../models/Ingestion');
const RepositoryRevision = require('../../models/RepositoryRevision');
const RepositoryArtifact = require('../../models/RepositoryArtifact');

const LocalStorageService = require('../storage/localStorageService');
const ArchiveAcquisitionHandler = require('../acquisition/archiveHandler');
const { GitHubAcquisitionHandler } = require('../acquisition/githubHandler');
const ServerPathAcquisitionHandler = require('../acquisition/serverPathHandler');
const SourceValidator = require('./sourceValidator');
const ArtifactClassifier = require('./artifactClassifier');

const {
  ActiveIngestionExistsError,
  IngestionNotFoundError,
  InvalidIngestionStateError,
  RevisionAlreadyExistsError,
  RevisionNotFoundError,
  SourceValidationError,
} = require('../../errors/ingestionErrors');

const { RepositoryNotFoundError } = require('../../errors/repositoryErrors');

/**
 * Computes streaming SHA-256 hash for a file on disk.
 * @param {string} filePath
 * @returns {Promise<string>}
 */
function computeFileHash(filePath) {
  return new Promise((resolve, reject) => {
    const hasher = crypto.createHash('sha256');
    const stream = fs.createReadStream(filePath, { highWaterMark: 65536 });
    stream.on('data', (chunk) => hasher.update(chunk));
    stream.on('error', (err) => reject(err));
    stream.on('end', () => resolve(hasher.digest('hex')));
  });
}

class IngestionService {
  /**
   * @param {object} [options]
   * @param {typeof projectAuthorization} [options.projectAuthorization]
   * @param {typeof Repository} [options.repositoryModel]
   * @param {typeof Ingestion} [options.ingestionModel]
   * @param {typeof RepositoryRevision} [options.revisionModel]
   * @param {typeof RepositoryArtifact} [options.artifactModel]
   * @param {import('../storage/storageService')} [options.storageService]
   * @param {Array<object>} [options.acquisitionHandlers]
   * @param {SourceValidator} [options.validator]
   * @param {ArtifactClassifier} [options.classifier]
   * @param {number} [options.staleTimeoutMs]
   */
  constructor(options = {}) {
    this._projectAuthorization = options.projectAuthorization || projectAuthorization;
    this._repositoryModel = options.repositoryModel || Repository;
    this._ingestionModel = options.ingestionModel || Ingestion;
    this._revisionModel = options.revisionModel || RepositoryRevision;
    this._artifactModel = options.artifactModel || RepositoryArtifact;
    this._storageService =
      options.storageService || new LocalStorageService(storageConfig.storageRoot);
    this._acquisitionHandlers = options.acquisitionHandlers || [
      new ArchiveAcquisitionHandler(),
      new GitHubAcquisitionHandler(),
      new ServerPathAcquisitionHandler(),
    ];
    this._validator = options.validator || new SourceValidator();
    this._classifier = options.classifier || new ArtifactClassifier();
    this._staleTimeoutMs = options.staleTimeoutMs || DEFAULT_STALE_INGESTION_TIMEOUT_MS;
  }

  /**
   * Ensure repository exists and belongs to the given project.
   *
   * @param {string} repositoryId
   * @param {string} projectId
   * @returns {Promise<import('mongoose').Document>}
   * @private
   */
  async _ensureRepoBelongsToProject(repositoryId, projectId) {
    const repository = await this._repositoryModel.findById(repositoryId);
    if (!repository || repository.project_id !== projectId) {
      throw new RepositoryNotFoundError();
    }
    return repository;
  }

  /**
   * Trigger the repository ingestion pipeline.
   *
   * @param {object} params
   * @param {string} params.projectId
   * @param {string} params.repositoryId
   * @param {string} params.sourceType
   * @param {string} params.sourceReference
   * @param {string} [params.revisionIdentifier]
   * @param {string} [params.credentialsRef]
   * @param {string} params.userId
   * @returns {Promise<import('mongoose').Document>}
   */
  async triggerIngestion({
    projectId,
    repositoryId,
    sourceType,
    sourceReference,
    revisionIdentifier,
    userId,
  }) {
    if (!sourceReference || typeof sourceReference !== 'string') {
      throw new SourceValidationError('Source reference is required for ingestion.');
    }

    // 1. Authorize user first (Developer+ required to trigger ingestion) (IR-M4-015)
    await this._projectAuthorization.requireCreateAccess(projectId, userId);

    // 2. Resolve repository and verify Project boundary
    const repository = await this._ensureRepoBelongsToProject(repositoryId, projectId);

    // 3. Concurrency guard: check active processing ingestion with staleness recovery (IR-M4-017)
    const active = await this._ingestionModel.findOne({
      repository_id: repositoryId,
      status: INGESTION_STATUS.PROCESSING,
    });
    if (active) {
      const startedAt = active.started_at ? new Date(active.started_at).getTime() : 0;
      const isStale = Date.now() - startedAt > this._staleTimeoutMs;
      if (isStale) {
        if (active.canTransitionTo(INGESTION_STATUS.FAILED)) {
          active.status = INGESTION_STATUS.FAILED;
        } else {
          active.status = INGESTION_STATUS.FAILED;
        }
        active.error_code = 'stale_job_timeout';
        active.error_message = 'Previous ingestion timed out or process terminated unexpectedly.';
        active.completed_at = new Date();
        await active.save();
      } else {
        throw new ActiveIngestionExistsError();
      }
    }

    // 4. Pre-check idempotency if revisionIdentifier is provided upfront
    if (revisionIdentifier && revisionIdentifier.trim()) {
      const existingRev = await this._revisionModel.findOne({
        repository_id: repositoryId,
        revision_identifier: revisionIdentifier.trim(),
      });
      if (existingRev) {
        throw new RevisionAlreadyExistsError(
          `A revision with identifier '${revisionIdentifier.trim()}' already exists for this repository.`
        );
      }
    }

    // 5. Normalize source type
    const normalizedSourceType = normalizeSourceType(sourceType);

    // 6. Create ingestion job in PENDING state (IR-M4-013)
    const ingestion = new this._ingestionModel({
      project_id: projectId,
      repository_id: repositoryId,
      source_type: normalizedSourceType,
      source_reference: sourceReference,
      status: INGESTION_STATUS.PENDING,
    });
    try {
      await ingestion.save();
    } catch (err) {
      if (err.name === 'ValidationError') {
        throw new SourceValidationError(err.message, { errors: err.errors });
      }
      throw err;
    }

    // 7. Transition to PROCESSING state using canTransitionTo (OBS-M4-01, IR-M4-016)
    if (!ingestion.canTransitionTo(INGESTION_STATUS.PROCESSING)) {
      throw new InvalidIngestionStateError(
        `Cannot transition ingestion from ${ingestion.status} to ${INGESTION_STATUS.PROCESSING}.`
      );
    }
    ingestion.status = INGESTION_STATUS.PROCESSING;
    ingestion.started_at = new Date();
    try {
      await ingestion.save();
    } catch (err) {
      // Clean up loser document on race or save failure (IR-M4-016)
      await this._ingestionModel.findByIdAndDelete(ingestion.id).catch(() => {});
      if (err.code === 11000) {
        throw new ActiveIngestionExistsError();
      }
      throw err;
    }

    // 8. Execute acquisition, validation, storage, and revision creation
    const tempWork = await fs.promises.mkdtemp(
      path.join(os.tmpdir(), `stacksense_ingest_${ingestion.id}_`)
    );

    let acquisitionResult = null;
    let revId = null;
    try {
      const handler = this._acquisitionHandlers.find((h) =>
        h.canHandle(normalizedSourceType)
      );
      if (!handler) {
        throw new SourceValidationError(
          `Unsupported repository source type: ${normalizedSourceType}`
        );
      }

      acquisitionResult = await handler.acquire(
        sourceReference,
        revisionIdentifier ? revisionIdentifier.trim() : null,
        tempWork
      );

      // Check revision uniqueness after acquisition has resolved final revisionIdentifier
      const existingRev = await this._revisionModel.findOne({
        repository_id: repositoryId,
        revision_identifier: acquisitionResult.revisionIdentifier,
      });
      if (existingRev) {
        throw new RevisionAlreadyExistsError(
          `A revision with identifier '${acquisitionResult.revisionIdentifier}' already exists for this repository.`
        );
      }

      // Validate extracted source tree against Section 7 limits
      const validatedSource = await this._validator.validate(acquisitionResult.rootPath);

      // Process artifacts: hash, classify, store via CAS, and prepare records
      const artifactDocs = [];
      revId = crypto.randomUUID();
      const now = new Date();

      for (const file of validatedSource.files) {
        const contentHash = await computeFileHash(file.absolutePath);

        const { category, supportLevel } = this._classifier.classify(
          file.relativePath,
          file.sizeBytes
        );

        const storageKey = `content/${contentHash.slice(0, 2)}/${contentHash}`;
        const alreadyStored = await this._storageService.exists(storageKey);
        if (!alreadyStored) {
          const readStream = fs.createReadStream(file.absolutePath);
          await this._storageService.put(storageKey, readStream);
        }

        artifactDocs.push({
          _id: crypto.randomUUID(),
          project_id: projectId,
          repository_id: repositoryId,
          revision_id: revId,
          path: file.relativePath,
          size_bytes: file.sizeBytes,
          content_hash: contentHash,
          category,
          support_level: supportLevel,
          storage_key: storageKey,
          created_at: now,
        });
      }

      // Create and persist RepositoryRevision
      const revision = new this._revisionModel({
        _id: revId,
        project_id: projectId,
        repository_id: repositoryId,
        ingestion_id: ingestion.id,
        revision_identifier: acquisitionResult.revisionIdentifier,
        source_hash: acquisitionResult.sourceHash,
        total_files: validatedSource.totalFiles,
        total_bytes: validatedSource.totalBytes,
        created_at: now,
      });

      try {
        await revision.save();
      } catch (err) {
        if (err.code === 11000) {
          throw new RevisionAlreadyExistsError(
            `A revision with identifier '${revision.revision_identifier}' already exists for this repository.`
          );
        }
        throw err;
      }

      // Batch insert artifacts with compensating cleanup on failure (IR-M4-018)
      try {
        if (artifactDocs.length > 0) {
          await this._artifactModel.insertMany(artifactDocs);
        }
      } catch (insertErr) {
        await this._artifactModel.deleteMany({ revision_id: revId }).catch(() => {});
        await this._revisionModel.findByIdAndDelete(revId).catch(() => {});
        throw insertErr;
      }

      // Transition ingestion to COMPLETED (OBS-M4-01)
      if (!ingestion.canTransitionTo(INGESTION_STATUS.COMPLETED)) {
        throw new InvalidIngestionStateError(
          `Cannot transition ingestion from ${ingestion.status} to ${INGESTION_STATUS.COMPLETED}.`
        );
      }
      ingestion.status = INGESTION_STATUS.COMPLETED;
      ingestion.completed_at = new Date();
      await ingestion.save();

      return ingestion;
    } catch (err) {
      // Compensating rollback of revision & artifacts if created (IR-M4-018)
      if (revId) {
        await this._artifactModel.deleteMany({ revision_id: revId }).catch(() => {});
        await this._revisionModel.findByIdAndDelete(revId).catch(() => {});
      }
      if (ingestion.canTransitionTo(INGESTION_STATUS.FAILED)) {
        ingestion.status = INGESTION_STATUS.FAILED;
      } else {
        ingestion.status = INGESTION_STATUS.FAILED;
      }
      ingestion.error_code = err.code || 'ingestion_failed';
      ingestion.error_message = err.message || 'Ingestion failed.';
      ingestion.completed_at = new Date();
      await ingestion.save().catch(() => {});
      throw err;
    } finally {
      if (acquisitionResult && typeof acquisitionResult.cleanup === 'function') {
        try {
          await acquisitionResult.cleanup();
        } catch {
          // Ignore cleanup error
        }
      }
      try {
        await fs.promises.rm(tempWork, { recursive: true, force: true });
      } catch {
        // Ignore sandbox removal error
      }
    }
  }

  /**
   * Retrieve an ingestion by identifier.
   *
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {string} ingestionId
   * @param {string} userId
   * @returns {Promise<import('mongoose').Document>}
   */
  async getIngestionById(projectId, repositoryId, ingestionId, userId) {
    await this._projectAuthorization.requireAccess(projectId, userId);
    await this._ensureRepoBelongsToProject(repositoryId, projectId);

    const ingestion = await this._ingestionModel.findById(ingestionId);
    if (
      !ingestion ||
      ingestion.repository_id !== repositoryId ||
      ingestion.project_id !== projectId
    ) {
      throw new IngestionNotFoundError();
    }

    return ingestion;
  }

  /**
   * List ingestions for a repository with pagination.
   *
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {object} [pagination]
   * @param {number} [pagination.limit=50]
   * @param {number} [pagination.offset=0]
   * @param {string} userId
   * @returns {Promise<Array<import('mongoose').Document>>}
   */
  async listIngestions(
    projectId,
    repositoryId,
    { limit = 50, offset = 0 } = {},
    userId
  ) {
    await this._projectAuthorization.requireAccess(projectId, userId);
    await this._ensureRepoBelongsToProject(repositoryId, projectId);

    return await this._ingestionModel
      .find({ repository_id: repositoryId })
      .sort({ created_at: -1 })
      .skip(offset)
      .limit(limit);
  }

  /**
   * Retrieve a repository revision by identifier.
   *
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {string} revisionId
   * @param {string} userId
   * @returns {Promise<import('mongoose').Document>}
   */
  async getRevisionById(projectId, repositoryId, revisionId, userId) {
    await this._projectAuthorization.requireAccess(projectId, userId);
    await this._ensureRepoBelongsToProject(repositoryId, projectId);

    const revision = await this._revisionModel.findById(revisionId);
    if (
      !revision ||
      revision.repository_id !== repositoryId ||
      revision.project_id !== projectId
    ) {
      throw new RevisionNotFoundError();
    }

    return revision;
  }

  /**
   * List revisions for a repository with pagination.
   *
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {object} [pagination]
   * @param {number} [pagination.limit=50]
   * @param {number} [pagination.offset=0]
   * @param {string} userId
   * @returns {Promise<Array<import('mongoose').Document>>}
   */
  async listRevisions(
    projectId,
    repositoryId,
    { limit = 50, offset = 0 } = {},
    userId
  ) {
    await this._projectAuthorization.requireAccess(projectId, userId);
    await this._ensureRepoBelongsToProject(repositoryId, projectId);

    return await this._revisionModel
      .find({ repository_id: repositoryId })
      .sort({ created_at: -1 })
      .skip(offset)
      .limit(limit);
  }

  /**
   * List artifacts belonging to a revision with deterministic pagination.
   *
   * @param {string} projectId
   * @param {string} repositoryId
   * @param {string} revisionId
   * @param {object} [pagination]
   * @param {number} [pagination.limit=50]
   * @param {number} [pagination.offset=0]
   * @param {string} userId
   * @returns {Promise<Array<import('mongoose').Document>>}
   */
  async listArtifacts(
    projectId,
    repositoryId,
    revisionId,
    { limit = 50, offset = 0 } = {},
    userId
  ) {
    await this._projectAuthorization.requireAccess(projectId, userId);
    await this._ensureRepoBelongsToProject(repositoryId, projectId);

    // Verify revision exists and belongs to repository
    const revision = await this._revisionModel.findById(revisionId);
    if (
      !revision ||
      revision.repository_id !== repositoryId ||
      revision.project_id !== projectId
    ) {
      throw new RevisionNotFoundError();
    }

    return await this._artifactModel
      .find({ revision_id: revisionId })
      .sort({ path: 1 })
      .skip(offset)
      .limit(limit);
  }
}

const defaultIngestionService = new IngestionService();

module.exports = {
  IngestionService,
  ingestionService: defaultIngestionService,
};
