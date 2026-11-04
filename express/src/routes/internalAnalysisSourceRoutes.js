const express = require('express');
const authenticateInternalService = require('../middleware/internalServiceAuth');
const controller = require('../controllers/internalAnalysisSourceController');

const router = express.Router();
const UUID = '[0-9a-fA-F-]{36}';

router.use(authenticateInternalService);
router.get(
  `/projects/:projectId(${UUID})/repositories/:repositoryId(${UUID})/revisions/:revisionId(${UUID})/manifest`,
  controller.getManifest
);
router.get(
  `/projects/:projectId(${UUID})/repositories/:repositoryId(${UUID})/revisions/:revisionId(${UUID})/artifacts/:artifactId(${UUID})/content`,
  controller.getArtifactContent
);

module.exports = router;
