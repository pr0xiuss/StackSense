const User = require('../models/User');

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

class UserDirectoryService {
  constructor(options = {}) {
    this.User = options.User || User;
  }

  async searchByUsername(username, { limit = 8 } = {}) {
    const normalized = String(username || '').trim().toLowerCase();
    const users = await this.User.find({
      username: { $regex: `^${escapeRegex(normalized)}` },
      is_active: true,
    })
      .select('_id username')
      .sort({ username: 1 })
      .limit(limit)
      .lean();

    return users.map((user) => ({ id: user._id, username: user.username }));
  }

  async findUsernamesByIds(userIds) {
    const uniqueIds = [...new Set(userIds.filter(Boolean))];
    if (uniqueIds.length === 0) return new Map();
    const users = await this.User.find({ _id: { $in: uniqueIds } })
      .select('_id username')
      .lean();
    return new Map(users.map((user) => [user._id, user.username]));
  }
}

const userDirectoryService = new UserDirectoryService();

module.exports = userDirectoryService;
module.exports.UserDirectoryService = UserDirectoryService;
