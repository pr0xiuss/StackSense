const express = require('express');
const projectRoutes = require('./projectRoutes');

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
 * Project resource endpoints.
 */
router.use('/projects', projectRoutes);

module.exports = router;

