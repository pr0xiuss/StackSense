const {
  internalAnalysisSourceService,
} = require('../services/internalAnalysisSourceService');

const MAX_CONTENT_BYTES = 50 * 1024 * 1024;

const internalAnalysisSourceController = {
  async getManifest(req, res, next) {
    try {
      const { projectId, repositoryId, revisionId } = req.params;
      const manifest = await internalAnalysisSourceService.getManifest(
        projectId,
        repositoryId,
        revisionId
      );
      res.status(200).json(manifest);
    } catch (error) {
      next(error);
    }
  },

  async getArtifactContent(req, res, next) {
    try {
      const { projectId, repositoryId, revisionId, artifactId } = req.params;
      const requested = Number.parseInt(req.query.max_bytes, 10);
      const maxBytes = Number.isFinite(requested)
        ? Math.max(1, Math.min(requested, MAX_CONTENT_BYTES))
        : MAX_CONTENT_BYTES;
      const { stream } = await internalAnalysisSourceService.openArtifact(
        projectId,
        repositoryId,
        revisionId,
        artifactId
      );

      const chunks = [];
      let remaining = maxBytes;
      for await (const chunk of stream) {
        if (remaining <= 0) break;
        const bounded = chunk.subarray(0, remaining);
        chunks.push(bounded);
        remaining -= bounded.length;
      }
      const content = Buffer.concat(chunks);

      res.status(200);
      res.set('Content-Type', 'application/octet-stream');
      res.set('Content-Length', String(content.length));
      res.send(content);
    } catch (error) {
      next(error);
    }
  },
};

module.exports = internalAnalysisSourceController;
