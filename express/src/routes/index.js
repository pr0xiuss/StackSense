const express = require('express');
const projectRoutes = require('./projectRoutes');
const authRoutes = require('./authRoutes');

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

/**
 * Project resource endpoints.
 */
router.use('/projects', projectRoutes);

module.exports = router;

