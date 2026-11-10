const express = require('express');
const authenticate = require('../middleware/authenticate');
const {
  validateCreateAnalysis,
  verifyChainForCreate,
  validateCancelAnalysis,
  validateListAnalysesQuery,
  validateAnalysisIdParam,
  validateProjectQuery,
  validateDiagnosticsQuery,
} = require('../middleware/analysisValidate');
const analysisController = require('../controllers/analysisController');

const router = express.Router();

/**
 * All analysis routes require authentication.
 */
router.use(authenticate);

/**
 * POST /api/v1/analyses
 * Create and enqueue a new analysis run.
 */
router.post(
  '/',
  validateCreateAnalysis,
  analysisController.authorizeCreateAnalysis,
  verifyChainForCreate,
  analysisController.createAnalysis
);

/**
 * GET /api/v1/analyses
 * List analyses for a project with optional repository_id and status filters.
 */
router.get(
  '/',
  validateListAnalysesQuery,
  analysisController.listAnalyses
);

/**
 * GET /api/v1/analyses/:analysisId
 * Get detailed lifecycle status for an analysis run.
 */
router.get(
  '/:analysisId',
  validateAnalysisIdParam,
  validateProjectQuery,
  analysisController.getAnalysis
);

/**
 * POST /api/v1/analyses/:analysisId/cancel
 * Request cooperative cancellation of an active analysis run.
 */
router.post(
  '/:analysisId/cancel',
  validateAnalysisIdParam,
  validateCancelAnalysis,
  analysisController.cancelAnalysis
);

/**
 * GET /api/v1/analyses/:analysisId/events
 * Server-Sent Events notification stream with sequence replay.
 */
router.get(
  '/:analysisId/events',
  validateAnalysisIdParam,
  validateProjectQuery,
  analysisController.streamEvents
);

/**
 * GET /api/v1/analyses/:analysisId/diagnostics
 * Paginated diagnostics for an analysis run.
 */
router.get(
  '/:analysisId/diagnostics',
  validateAnalysisIdParam,
  validateDiagnosticsQuery,
  analysisController.listDiagnostics
);

/**
 * GET /api/v1/analyses/:analysisId/architecture
 * Retrieve published Architecture Version summary for an analysis run.
 */
router.get(
  '/:analysisId/architecture',
  validateAnalysisIdParam,
  validateProjectQuery,
  analysisController.getAnalysisArchitecture
);

module.exports = router;

