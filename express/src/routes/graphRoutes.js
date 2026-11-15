const express = require('express');
const authenticate = require('../middleware/authenticate');
const {
  validateVersionIdParam,
  validateEntityIdParam,
  validateProjectQuery,
  validateStatusQuery,
  validateRebuild,
  validateNodeDetailQuery,
  validateWindowQuery,
  validateNeighborhoodQuery,
  validateDependenciesQuery,
  validateDependentsQuery,
  validateContainmentQuery,
  validatePathsQuery,
} = require('../middleware/graphValidate');
const graphController = require('../controllers/graphController');

const router = express.Router({ mergeParams: true });

// All graph routes require authentication
router.use(authenticate);

/**
 * GET /api/v1/architecture-versions/:versionId/graph/status
 */
router.get(
  '/status',
  validateVersionIdParam,
  validateProjectQuery,
  validateStatusQuery,
  graphController.getStatus
);

/**
 * POST /api/v1/architecture-versions/:versionId/graph/rebuild
 */
router.post(
  '/rebuild',
  validateVersionIdParam,
  validateProjectQuery,
  validateRebuild,
  graphController.requestRebuild
);

/**
 * GET /api/v1/architecture-versions/:versionId/graph/window
 */
router.get(
  '/window',
  validateVersionIdParam,
  validateProjectQuery,
  validateWindowQuery,
  graphController.getWindow
);

/**
 * GET /api/v1/architecture-versions/:versionId/graph/paths
 */
router.get(
  '/paths',
  validateVersionIdParam,
  validateProjectQuery,
  validatePathsQuery,
  graphController.getBoundedPaths
);

/**
 * GET /api/v1/architecture-versions/:versionId/graph/nodes/:entityId
 */
router.get(
  '/nodes/:entityId',
  validateVersionIdParam,
  validateEntityIdParam,
  validateProjectQuery,
  validateNodeDetailQuery,
  graphController.getNodeDetail
);

/**
 * GET /api/v1/architecture-versions/:versionId/graph/nodes/:entityId/neighborhood
 */
router.get(
  '/nodes/:entityId/neighborhood',
  validateVersionIdParam,
  validateEntityIdParam,
  validateProjectQuery,
  validateNeighborhoodQuery,
  graphController.getNeighborhood
);

/**
 * GET /api/v1/architecture-versions/:versionId/graph/nodes/:entityId/dependencies
 */
router.get(
  '/nodes/:entityId/dependencies',
  validateVersionIdParam,
  validateEntityIdParam,
  validateProjectQuery,
  validateDependenciesQuery,
  graphController.getDependencies
);

/**
 * GET /api/v1/architecture-versions/:versionId/graph/nodes/:entityId/dependents
 */
router.get(
  '/nodes/:entityId/dependents',
  validateVersionIdParam,
  validateEntityIdParam,
  validateProjectQuery,
  validateDependentsQuery,
  graphController.getDependents
);

/**
 * GET /api/v1/architecture-versions/:versionId/graph/nodes/:entityId/containment
 */
router.get(
  '/nodes/:entityId/containment',
  validateVersionIdParam,
  validateEntityIdParam,
  validateProjectQuery,
  validateContainmentQuery,
  graphController.getContainment
);

module.exports = router;

