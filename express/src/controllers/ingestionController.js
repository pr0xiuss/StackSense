const fs = require('fs');
const { ingestionService } = require('../services/ingestion/ingestionService');
const { UnsupportedArchiveFormatError } = require('../errors/ingestionErrors');

const ingestionController = {
  /**
   * POST /projects/:projectId/repositories/:repositoryId/ingestions
   */
  async triggerIngestion(req, res, next) {
    try {
      const { projectId, repositoryId } = req.params;
      const {
        source_type,
        source_reference,
        revision_identifier,
      } = req.body;
      const userId = req.user.id;

      const ingestion = await ingestionService.triggerIngestion({
        projectId,
        repositoryId,
        sourceType: source_type,
        sourceReference: source_reference,
        revisionIdentifier: revision_identifier,
        userId,
      });

      res.status(201).json(ingestion);
    } catch (err) {
      next(err);
    }
  },

  /**
   * POST /projects/:projectId/repositories/:repositoryId/ingestions/upload
   */
  async uploadAndIngest(req, res, next) {
    if (!req.file) {
      return next(
        new UnsupportedArchiveFormatError(
          'Uploaded archive file is required.'
        )
      );
    }

    try {
      const { projectId, repositoryId } = req.params;
      const { revision_identifier } = req.body;
      const userId = req.user.id;

      const ingestion = await ingestionService.triggerIngestion({
        projectId,
        repositoryId,
        sourceType: 'archive',
        sourceReference: req.file.path,
        revisionIdentifier: revision_identifier,
        userId,
      });

      res.status(201).json(ingestion);
    } catch (err) {
      next(err);
    } finally {
      if (req.file && req.file.path) {
        try {
          if (fs.existsSync(req.file.path)) {
            await fs.promises.unlink(req.file.path);
          }
        } catch {
          // Ignore staging cleanup error
        }
      }
    }
  },

  /**
   * GET /projects/:projectId/repositories/:repositoryId/ingestions/:ingestionId
   */
  async getIngestion(req, res, next) {
    try {
      const { projectId, repositoryId, ingestionId } = req.params;
      const userId = req.user.id;

      const ingestion = await ingestionService.getIngestionById(
        projectId,
        repositoryId,
        ingestionId,
        userId
      );

      res.status(200).json(ingestion);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /projects/:projectId/repositories/:repositoryId/ingestions
   */
  async listIngestions(req, res, next) {
    try {
      const { projectId, repositoryId } = req.params;
      const { limit, offset } = req.pagination || {};
      const userId = req.user.id;

      const ingestions = await ingestionService.listIngestions(
        projectId,
        repositoryId,
        { limit, offset },
        userId
      );

      res.status(200).json(ingestions);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /projects/:projectId/repositories/:repositoryId/revisions
   */
  async listRevisions(req, res, next) {
    try {
      const { projectId, repositoryId } = req.params;
      const { limit, offset } = req.pagination || {};
      const userId = req.user.id;

      const revisions = await ingestionService.listRevisions(
        projectId,
        repositoryId,
        { limit, offset },
        userId
      );

      res.status(200).json(revisions);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /projects/:projectId/repositories/:repositoryId/revisions/:revisionId
   */
  async getRevision(req, res, next) {
    try {
      const { projectId, repositoryId, revisionId } = req.params;
      const userId = req.user.id;

      const revision = await ingestionService.getRevisionById(
        projectId,
        repositoryId,
        revisionId,
        userId
      );

      res.status(200).json(revision);
    } catch (err) {
      next(err);
    }
  },

  /**
   * GET /projects/:projectId/repositories/:repositoryId/revisions/:revisionId/artifacts
   */
  async listArtifacts(req, res, next) {
    try {
      const { projectId, repositoryId, revisionId } = req.params;
      const { limit, offset } = req.pagination || {};
      const userId = req.user.id;

      const artifacts = await ingestionService.listArtifacts(
        projectId,
        repositoryId,
        revisionId,
        { limit, offset },
        userId
      );

      res.status(200).json(artifacts);
    } catch (err) {
      next(err);
    }
  },
};

module.exports = ingestionController;
