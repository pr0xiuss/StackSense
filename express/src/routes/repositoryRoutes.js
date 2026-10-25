const express = require('express');
const repositoryController = require('../controllers/repositoryController');
const {
  validateRepositoryId,
  validateRegisterRepository,
  validateUpdateRepository,
} = require('../middleware/repositoryValidate');
const { validatePagination } = require('../middleware/validate');

const router = express.Router({ mergeParams: true });

router.post('/', validateRegisterRepository, repositoryController.registerRepository);
router.get('/', validatePagination, repositoryController.listRepositories);
router.get('/:repositoryId', validateRepositoryId, repositoryController.getRepository);
router.patch(
  '/:repositoryId',
  validateRepositoryId,
  validateUpdateRepository,
  repositoryController.updateRepository
);
router.delete('/:repositoryId', validateRepositoryId, repositoryController.deleteRepository);

module.exports = router;
