const express = require('express');
const ingestionController = require('../controllers/ingestionController');
const { validateRepositoryId } = require('../middleware/repositoryValidate');
const {
  validateIngestionId,
  validateRevisionId,
  validateStartIngestion,
} = require('../middleware/ingestionValidate');
const { validatePagination } = require('../middleware/validate');
const { upload } = require('../middleware/uploadMiddleware');

const router = express.Router({ mergeParams: true });

// Ingestion operations
router.post(
  '/:repositoryId/ingestions',
  validateRepositoryId,
  validateStartIngestion,
  ingestionController.triggerIngestion
);

router.post(
  '/:repositoryId/ingestions/upload',
  validateRepositoryId,
  upload.single('file'),
  ingestionController.uploadAndIngest
);

router.get(
  '/:repositoryId/ingestions/:ingestionId',
  validateRepositoryId,
  validateIngestionId,
  ingestionController.getIngestion
);

router.get(
  '/:repositoryId/ingestions',
  validateRepositoryId,
  validatePagination,
  ingestionController.listIngestions
);

// Revision and artifact operations
router.get(
  '/:repositoryId/revisions',
  validateRepositoryId,
  validatePagination,
  ingestionController.listRevisions
);

router.get(
  '/:repositoryId/revisions/:revisionId',
  validateRepositoryId,
  validateRevisionId,
  ingestionController.getRevision
);

router.get(
  '/:repositoryId/revisions/:revisionId/artifacts',
  validateRepositoryId,
  validateRevisionId,
  validatePagination,
  ingestionController.listArtifacts
);

module.exports = router;
