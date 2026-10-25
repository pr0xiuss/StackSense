const userDirectoryService = require('../services/userDirectoryService');

const userDirectoryController = {
  async lookupByUsername(req, res, next) {
    try {
      const users = await userDirectoryService.searchByUsername(
        req.userLookup.username,
        { limit: req.userLookup.limit }
      );
      res.status(200).json(users);
    } catch (err) {
      next(err);
    }
  },
};

module.exports = userDirectoryController;
