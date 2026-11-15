const express = require('express');
const authenticate = require('../middleware/authenticate');
const { validateNoQuery } = require('../middleware/graphValidate');
const graphController = require('../controllers/graphController');

const router = express.Router();

// Health relay requires authenticated user
router.use(authenticate);

/**
 * GET /api/v1/health/graph/query
 */
router.get('/query', validateNoQuery, graphController.getQueryHealth);

module.exports = router;

