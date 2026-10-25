const express = require('express');
const projectAccessController = require('../controllers/projectAccessController');
const authenticate = require('../middleware/authenticate');
const {
  validateUserIdParam,
  validateGrantAccessBody,
  validateChangeRoleBody,
} = require('../middleware/accessValidate');

const router = express.Router({ mergeParams: true });
router.use(authenticate);
router.post('/', validateGrantAccessBody, projectAccessController.grantAccess);
router.get('/', projectAccessController.listProjectAccess);
router.patch('/:userId', validateUserIdParam, validateChangeRoleBody, projectAccessController.changeRole);
router.delete('/:userId', validateUserIdParam, projectAccessController.revokeAccess);

module.exports = router;
