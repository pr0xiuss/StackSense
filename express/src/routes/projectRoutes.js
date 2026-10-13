const express = require('express');
const projectController = require('../controllers/projectController');
const {
  validateProjectId,
  validateCreateProject,
  validateUpdateProject,
  validatePagination,
} = require('../middleware/validate');

const router = express.Router();

// Project collection routes
router.post('/', validateCreateProject, projectController.createProject);
router.get('/', validatePagination, projectController.listProjects);

// Project individual resource routes
router.get('/:projectId', validateProjectId, projectController.getProject);
router.patch('/:projectId', validateProjectId, validateUpdateProject, projectController.updateProject);
router.delete('/:projectId', validateProjectId, projectController.deleteProject);

module.exports = router;
