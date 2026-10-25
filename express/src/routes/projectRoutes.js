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

router.use(authenticate);
router.use('/:projectId/access', validateProjectId, projectAccessRoutes);
router.use('/:projectId/repositories', validateProjectId, repositoryRoutes);
router.post('/', validateCreateProject, projectController.createProject);
router.get('/', validatePagination, projectController.listProjects);
router.get('/:projectId', validateProjectId, projectController.getProject);
router.patch('/:projectId', validateProjectId, validateUpdateProject, projectController.updateProject);
router.delete('/:projectId', validateProjectId, projectController.deleteProject);

module.exports = router;
