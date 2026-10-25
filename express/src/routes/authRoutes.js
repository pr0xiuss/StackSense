const express = require('express');
const authController = require('../controllers/authController');
const {
  validateRegister,
  validateLogin,
  validateRefresh,
  validateLogout,
} = require('../middleware/authValidate');

const authenticate = require('../middleware/authenticate');
const router = express.Router();

router.post('/register', validateRegister, authController.register);
router.post('/login', validateLogin, authController.login);
router.post('/refresh', validateRefresh, authController.refresh);
router.post('/logout', validateLogout, authController.logout);
router.get('/me', authenticate, authController.me);

module.exports = router;