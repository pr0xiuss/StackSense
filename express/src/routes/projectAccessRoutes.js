const express = require('express');
const projectAccessController = require('../controllers/projectAccessController');
const authenticate = require('../middleware/authenticate');
const {
  validateUserIdParam,
  validateGrantAccessBody,
  validateChangeRoleBody,
} = require('../middleware/accessValidate');

const router = express.Router({ mergeParams: true });

// All project access endpoints require authentication
router.use(authenticate);

// Collection routes
router.post('/', validateGrantAccessBody, projectAccessController.grantAccess);
router.get('/', projectAccessController.listProjectAccess);

// Member individual routes
router.patch('/:userId', validateUserIdParam, validateChangeRoleBody, projectAccessController.changeRole);
router.delete('/:userId', validateUserIdParam, projectAccessController.revokeAccess);

module.exports = router;
