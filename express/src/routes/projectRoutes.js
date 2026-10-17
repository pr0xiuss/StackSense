const express = require('express');
const projectController = require('../controllers/projectController');
const projectAccessRoutes = require('./projectAccessRoutes');
const repositoryRoutes = require('./repositoryRoutes');
const authenticate = require('../middleware/authenticate');
const {
  validateProjectId,
  validateCreateProject,
  validateUpdateProject,
  validatePagination,
} = require('../middleware/validate');

const router = express.Router();

// All project endpoints require authentication
router.use(authenticate);

// Project Access sub-resource routes
router.use('/:projectId/access', validateProjectId, projectAccessRoutes);

// Repository sub-resource routes
router.use('/:projectId/repositories', validateProjectId, repositoryRoutes);

// Project collection routes
router.post('/', validateCreateProject, projectController.createProject);
router.get('/', validatePagination, projectController.listProjects);

// Project individual resource routes
router.get('/:projectId', validateProjectId, projectController.getProject);
router.patch('/:projectId', validateProjectId, validateUpdateProject, projectController.updateProject);
router.delete('/:projectId', validateProjectId, projectController.deleteProject);

module.exports = router;
