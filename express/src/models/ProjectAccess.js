const crypto = require('crypto');
const mongoose = require('mongoose');
const { VALID_PROJECT_ROLES, PROJECT_ROLES } = require('../constants/projectRoles');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const projectAccessSchema = new mongoose.Schema(
  {
    _id: {
      type: String,
      default: () => crypto.randomUUID(),
    },
    project_id: {
      type: String,
      required: [true, 'project_id is required'],
      match: [UUID_V4_REGEX, 'project_id must be a valid UUID v4'],
      ref: 'Project',
    },
    user_id: {
      type: String,
      required: [true, 'user_id is required'],
      match: [UUID_V4_REGEX, 'user_id must be a valid UUID v4'],
    },
    role: {
      type: String,
      required: [true, 'role is required'],
      enum: {
        values: VALID_PROJECT_ROLES,
        message: 'Invalid project role',
      },
    },
  },
  {
    timestamps: { createdAt: 'created_at', updatedAt: 'updated_at' },
    versionKey: false,
    toJSON: {
      transform: (doc, ret) => {
        return {
          project_id: ret.project_id,
          user_id: ret.user_id,
          role: ret.role,
        };
      },
    },
    toObject: {
      transform: (doc, ret) => {
        return {
          project_id: ret.project_id,
          user_id: ret.user_id,
          role: ret.role,
        };
      },
    },
  }
);

projectAccessSchema.index({ project_id: 1, user_id: 1 }, { unique: true });

projectAccessSchema.index({ user_id: 1 });
projectAccessSchema.index({ project_id: 1 });

projectAccessSchema.methods.canRead = function () {
  return true;
};

projectAccessSchema.methods.canCreate = function () {
  return [
    PROJECT_ROLES.OWNER,
    PROJECT_ROLES.ADMIN,
    PROJECT_ROLES.DEVELOPER,
  ].includes(this.role);
};

projectAccessSchema.methods.canUpdate = function () {
  return [
    PROJECT_ROLES.OWNER,
    PROJECT_ROLES.ADMIN,
    PROJECT_ROLES.DEVELOPER,
  ].includes(this.role);
};

projectAccessSchema.methods.canDelete = function () {
  return [
    PROJECT_ROLES.OWNER,
    PROJECT_ROLES.ADMIN,
  ].includes(this.role);
};

const ProjectAccess = mongoose.model('ProjectAccess', projectAccessSchema, 'project_access');

module.exports = ProjectAccess;
