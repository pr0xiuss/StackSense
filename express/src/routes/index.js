const express = require('express');
const projectRoutes = require('./projectRoutes');
const authRoutes = require('./authRoutes');
const userDirectoryRoutes = require('./userDirectoryRoutes');
const internalAnalysisSourceRoutes = require('./internalAnalysisSourceRoutes');
const analysisRoutes = require('./analysisRoutes');
const architectureRoutes = require('./architectureRoutes');
const graphRoutes = require('./graphRoutes');
const graphHealthRoutes = require('./graphHealthRoutes');
const intelligenceRoutes = require('./intelligenceRoutes');

const router = express.Router();

/**
 * Health check endpoints.
 */
router.get('/health', (req, res) => {
  res.status(200).json({
    status: 'ok',
    service: 'stacksense-express',
  });
});
router.use('/health/graph', graphHealthRoutes);

/**
 * Authentication endpoints.
 */
router.use('/auth', authRoutes);
router.use('/users', userDirectoryRoutes);
router.use('/internal', internalAnalysisSourceRoutes);

/**
 * Project resource endpoints.
 */
router.use('/projects', projectRoutes);

/**
 * Analysis lifecycle, Architecture Graph, Intelligence, and Architecture Model endpoints.
 */
router.use('/analyses', analysisRoutes);
router.use('/architecture-versions/:versionId', intelligenceRoutes);
router.use('/architecture-versions/:versionId/graph', graphRoutes);
router.use('/architecture-versions', architectureRoutes);

module.exports = router;

