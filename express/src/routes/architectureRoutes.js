const express = require('express');
const authenticate = require('../middleware/authenticate');
const {
  validateVersionIdParam,
  validateEntityIdParam,
  validateProjectQuery,
  validateArchitectureCollectionQuery,
} = require('../middleware/analysisValidate');
const architectureController = require('../controllers/architectureController');

const router = express.Router();

/**
 * All architecture model routes require authentication.
 */
router.use(authenticate);

/**
 * GET /api/v1/architecture-versions/:versionId
 */
router.get(
  '/:versionId',
  validateVersionIdParam,
  validateProjectQuery,
  architectureController.getArchitectureVersion
);

/**
 * GET /api/v1/architecture-versions/:versionId/entities
 */
router.get(
  '/:versionId/entities',
  validateVersionIdParam,
  validateArchitectureCollectionQuery,
  architectureController.listArchitectureEntities
);

/**
 * GET /api/v1/architecture-versions/:versionId/entities/:entityId
 */
router.get(
  '/:versionId/entities/:entityId',
  validateVersionIdParam,
  validateEntityIdParam,
  validateProjectQuery,
  architectureController.getArchitectureEntity
);

/**
 * GET /api/v1/architecture-versions/:versionId/relationships
 */
router.get(
  '/:versionId/relationships',
  validateVersionIdParam,
  validateArchitectureCollectionQuery,
  architectureController.listArchitectureRelationships
);

/**
 * GET /api/v1/architecture-versions/:versionId/evidence
 */
router.get(
  '/:versionId/evidence',
  validateVersionIdParam,
  validateArchitectureCollectionQuery,
  architectureController.listArchitectureEvidence
);

/**
 * GET /api/v1/architecture-versions/:versionId/unresolved
 */
router.get(
  '/:versionId/unresolved',
  validateVersionIdParam,
  validateArchitectureCollectionQuery,
  architectureController.listArchitectureUnresolved
);

/**
 * GET /api/v1/architecture-versions/:versionId/conflicts
 */
router.get(
  '/:versionId/conflicts',
  validateVersionIdParam,
  validateArchitectureCollectionQuery,
  architectureController.listArchitectureConflicts
);

module.exports = router;

