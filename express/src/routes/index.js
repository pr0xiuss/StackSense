const express = require('express');
const projectRoutes = require('./projectRoutes');
const authRoutes = require('./authRoutes');
const userDirectoryRoutes = require('./userDirectoryRoutes');

const router = express.Router();

router.get('/health', (req, res) => {
  res.status(200).json({
    status: 'ok',
    service: 'stacksense-express',
  });
});

router.use('/auth', authRoutes);
router.use('/users', userDirectoryRoutes);
router.use('/projects', projectRoutes);

module.exports = router;

