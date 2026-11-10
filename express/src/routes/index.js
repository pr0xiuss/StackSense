const express = require('express');
const projectRoutes = require('./projectRoutes');
const authRoutes = require('./authRoutes');
const userDirectoryRoutes = require('./userDirectoryRoutes');
const internalAnalysisSourceRoutes = require('./internalAnalysisSourceRoutes');
const analysisRoutes = require('./analysisRoutes');
const architectureRoutes = require('./architectureRoutes');

const router = express.Router();

/**
 * Health check endpoint.
 */
router.get('/health', (req, res) => {
  res.status(200).json({
    status: 'ok',
    service: 'stacksense-express',
  });
});

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
 * Analysis lifecycle and Architecture Model endpoints.
 */
router.use('/analyses', analysisRoutes);
router.use('/architecture-versions', architectureRoutes);

module.exports = router;

