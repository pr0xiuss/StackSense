const crypto = require('crypto');
const mongoose = require('mongoose');

const {
  VALID_ARTIFACT_CATEGORIES,
  VALID_SUPPORT_LEVELS,
} = require('../constants/ingestionConstants');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const repositoryArtifactSchema = new mongoose.Schema(
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
      index: true,
    },
    repository_id: {
      type: String,
      required: [true, 'repository_id is required'],
      match: [UUID_V4_REGEX, 'repository_id must be a valid UUID v4'],
      ref: 'Repository',
      index: true,
    },
    revision_id: {
      type: String,
      required: [true, 'revision_id is required'],
      match: [UUID_V4_REGEX, 'revision_id must be a valid UUID v4'],
      ref: 'RepositoryRevision',
      index: true,
    },
    path: {
      type: String,
      required: [true, 'path is required'],
      trim: true,
      maxlength: [4096, 'path cannot exceed 4096 characters'],
    },
    size_bytes: {
      type: Number,
      required: [true, 'size_bytes is required'],
      min: [0, 'size_bytes cannot be negative'],
    },
    content_hash: {
      type: String,
      required: [true, 'content_hash is required'],
      trim: true,
      maxlength: [64, 'content_hash cannot exceed 64 characters'],
    },
    category: {
      type: String,
      required: [true, 'category is required'],
      enum: {
        values: VALID_ARTIFACT_CATEGORIES,
        message: 'Invalid artifact category: {VALUE}',
      },
    },
    support_level: {
      type: String,
      required: [true, 'support_level is required'],
      enum: {
        values: VALID_SUPPORT_LEVELS,
        message: 'Invalid support level: {VALUE}',
      },
    },
    storage_key: {
      type: String,
      required: [true, 'storage_key is required'],
      trim: true,
      maxlength: [4096, 'storage_key cannot exceed 4096 characters'],
    },
    created_at: {
      type: Date,
      default: Date.now,
      immutable: true,
    },
  },
  {
    versionKey: false,
    toJSON: {
      transform: (doc, ret) => {
        ret.id = ret._id;
        delete ret._id;
        return ret;
      },
    },
    toObject: {
      transform: (doc, ret) => {
        ret.id = ret._id;
        delete ret._id;
        return ret;
      },
    },
  }
);

// Compound unique index prevents duplicate paths within the same revision
repositoryArtifactSchema.index(
  { revision_id: 1, path: 1 },
  { unique: true }
);

const RepositoryArtifact = mongoose.model('RepositoryArtifact', repositoryArtifactSchema);

module.exports = RepositoryArtifact;
