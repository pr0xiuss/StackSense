const express = require('express');
const authenticate = require('../middleware/authenticate');
const userDirectoryController = require('../controllers/userDirectoryController');
const { validateUsernameLookup } = require('../middleware/userDirectoryValidate');

const router = express.Router();

router.use(authenticate);
router.get('/lookup', validateUsernameLookup, userDirectoryController.lookupByUsername);

module.exports = router;
