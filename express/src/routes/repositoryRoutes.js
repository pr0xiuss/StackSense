const express = require('express');
const repositoryController = require('../controllers/repositoryController');
const {
  validateRepositoryId,
  validateRegisterRepository,
  validateUpdateRepository,
} = require('../middleware/repositoryValidate');
const { validatePagination } = require('../middleware/validate');

const router = express.Router({ mergeParams: true });

// Repository collection routes
router.post('/', validateRegisterRepository, repositoryController.registerRepository);
router.get('/', validatePagination, repositoryController.listRepositories);

// Repository individual resource routes
router.get('/:repositoryId', validateRepositoryId, repositoryController.getRepository);
router.patch(
  '/:repositoryId',
  validateRepositoryId,
  validateUpdateRepository,
  repositoryController.updateRepository
);
router.delete('/:repositoryId', validateRepositoryId, repositoryController.deleteRepository);

// Ingestion, revision, and artifact sub-resource routes
const ingestionRoutes = require('./ingestionRoutes');
router.use('/', ingestionRoutes);

module.exports = router;
