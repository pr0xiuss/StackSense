const express = require('express');
const authenticate = require('../middleware/authenticate');
const {
  validateVersionIdParam,
  validateDiagramTemplateParam,
  validateGenerationIdParam,
  validateReportIdParam,
  validateExactProjectOnlyQuery,
  validateSearchQuery,
  validateEvidenceQuery,
  validateDiagramSummaryQuery,
  validateDiagramGenerationsQuery,
  validateDiagramMembersQuery,
  validateDiagramExportQuery,
  validateReportPageQuery,
  validateReportSummaryQuery,
  validateDeliveryRetryBody,
  validateSearchRebuildBody,
  validateKnowledgeQueryBody,
  validateContextBody,
  validateDiagramViewBody,
} = require('../middleware/intelligenceValidate');
const intelligenceController = require('../controllers/intelligenceController');

const router = express.Router({ mergeParams: true });

// All intelligence routes require authentication
router.use(authenticate);

/**
 * 1. GET /api/v1/architecture-versions/:versionId/delivery
 */
router.get(
  '/delivery',
  validateVersionIdParam,
  validateExactProjectOnlyQuery,
  intelligenceController.getDelivery
);

/**
 * 2. POST /api/v1/architecture-versions/:versionId/delivery/retry
 */
router.post(
  '/delivery/retry',
  validateVersionIdParam,
  validateExactProjectOnlyQuery,
  validateDeliveryRetryBody,
  intelligenceController.retryDelivery
);

/**
 * 3. GET /api/v1/architecture-versions/:versionId/search/status
 */
router.get(
  '/search/status',
  validateVersionIdParam,
  validateExactProjectOnlyQuery,
  intelligenceController.getSearchStatus
);

/**
 * 4. GET /api/v1/architecture-versions/:versionId/search
 */
router.get(
  '/search',
  validateVersionIdParam,
  validateSearchQuery,
  intelligenceController.search
);

/**
 * 5. POST /api/v1/architecture-versions/:versionId/search/rebuild
 */
router.post(
  '/search/rebuild',
  validateVersionIdParam,
  validateExactProjectOnlyQuery,
  validateSearchRebuildBody,
  intelligenceController.rebuildSearch
);

/**
 * 6. POST /api/v1/architecture-versions/:versionId/knowledge/query
 */
router.post(
  '/knowledge/query',
  validateVersionIdParam,
  validateExactProjectOnlyQuery,
  validateKnowledgeQueryBody,
  intelligenceController.queryKnowledge
);

/**
 * 7. POST /api/v1/architecture-versions/:versionId/knowledge/context
 */
router.post(
  '/knowledge/context',
  validateVersionIdParam,
  validateExactProjectOnlyQuery,
  validateContextBody,
  intelligenceController.getContext
);

/**
 * 8. GET /api/v1/architecture-versions/:versionId/knowledge/evidence
 */
router.get(
  '/knowledge/evidence',
  validateVersionIdParam,
  validateEvidenceQuery,
  intelligenceController.getEvidence
);

/**
 * 9. GET /api/v1/architecture-versions/:versionId/diagrams
 */
router.get(
  '/diagrams',
  validateVersionIdParam,
  validateExactProjectOnlyQuery,
  intelligenceController.getDiagrams
);

/**
 * 10. GET /api/v1/architecture-versions/:versionId/diagrams/:template
 */
router.get(
  '/diagrams/:template',
  validateVersionIdParam,
  validateDiagramTemplateParam,
  validateDiagramSummaryQuery,
  intelligenceController.getDiagramSummary
);

/**
 * 11. GET /api/v1/architecture-versions/:versionId/diagrams/:template/generations
 */
router.get(
  '/diagrams/:template/generations',
  validateVersionIdParam,
  validateDiagramTemplateParam,
  validateDiagramGenerationsQuery,
  intelligenceController.getDiagramGenerations
);

/**
 * 12. GET /api/v1/architecture-versions/:versionId/diagrams/:template/generations/:generationId/spec
 */
router.get(
  '/diagrams/:template/generations/:generationId/spec',
  validateVersionIdParam,
  validateDiagramTemplateParam,
  validateGenerationIdParam,
  validateExactProjectOnlyQuery,
  intelligenceController.getDiagramSpec
);

/**
 * 13. GET /api/v1/architecture-versions/:versionId/diagrams/:template/generations/:generationId/layout
 */
router.get(
  '/diagrams/:template/generations/:generationId/layout',
  validateVersionIdParam,
  validateDiagramTemplateParam,
  validateGenerationIdParam,
  validateExactProjectOnlyQuery,
  intelligenceController.getDiagramLayout
);

/**
 * 14. POST /api/v1/architecture-versions/:versionId/diagrams/:template/generations/:generationId/view
 */
router.post(
  '/diagrams/:template/generations/:generationId/view',
  validateVersionIdParam,
  validateDiagramTemplateParam,
  validateGenerationIdParam,
  validateExactProjectOnlyQuery,
  validateDiagramViewBody,
  intelligenceController.viewDiagram
);

/**
 * 15. GET /api/v1/architecture-versions/:versionId/diagrams/:template/generations/:generationId/members
 */
router.get(
  '/diagrams/:template/generations/:generationId/members',
  validateVersionIdParam,
  validateDiagramTemplateParam,
  validateGenerationIdParam,
  validateDiagramMembersQuery,
  intelligenceController.getDiagramMembers
);

/**
 * 16. GET /api/v1/architecture-versions/:versionId/diagrams/:template/generations/:generationId/export
 */
router.get(
  '/diagrams/:template/generations/:generationId/export',
  validateVersionIdParam,
  validateDiagramTemplateParam,
  validateGenerationIdParam,
  validateDiagramExportQuery,
  intelligenceController.exportDiagram
);

/**
 * 17. GET /api/v1/architecture-versions/:versionId/reports
 */
router.get(
  '/reports',
  validateVersionIdParam,
  validateReportPageQuery,
  intelligenceController.getReports
);

/**
 * 18. GET /api/v1/architecture-versions/:versionId/reports/:reportId
 */
router.get(
  '/reports/:reportId',
  validateVersionIdParam,
  validateReportIdParam,
  validateReportSummaryQuery,
  intelligenceController.getReportSummary
);

/**
 * 19. GET /api/v1/architecture-versions/:versionId/reports/:reportId/generations
 */
router.get(
  '/reports/:reportId/generations',
  validateVersionIdParam,
  validateReportIdParam,
  validateReportPageQuery,
  intelligenceController.getReportGenerations
);

/**
 * 20. GET /api/v1/architecture-versions/:versionId/reports/:reportId/generations/:generationId
 */
router.get(
  '/reports/:reportId/generations/:generationId',
  validateVersionIdParam,
  validateReportIdParam,
  validateGenerationIdParam,
  validateExactProjectOnlyQuery,
  intelligenceController.getReportGenerationDetail
);

/**
 * 21. GET /api/v1/architecture-versions/:versionId/reports/:reportId/generations/:generationId/download
 */
router.get(
  '/reports/:reportId/generations/:generationId/download',
  validateVersionIdParam,
  validateReportIdParam,
  validateGenerationIdParam,
  validateExactProjectOnlyQuery,
  intelligenceController.downloadReportGeneration
);

module.exports = router;
