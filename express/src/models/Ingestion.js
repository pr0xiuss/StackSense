const crypto = require('crypto');
const mongoose = require('mongoose');
const {
  VALID_SOURCE_TYPES,
  VALID_INGESTION_STATUSES,
  INGESTION_STATUS,
} = require('../constants/ingestionConstants');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const ingestionSchema = new mongoose.Schema(
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
    },
    source_type: {
      type: String,
      required: [true, 'source_type is required'],
      enum: {
        values: VALID_SOURCE_TYPES,
        message: 'Unsupported repository source type',
      },
    },
    source_reference: {
      type: String,
      required: [true, 'source_reference is required'],
      trim: true,
      maxlength: [1024, 'source_reference cannot exceed 1024 characters'],
    },
    status: {
      type: String,
      required: [true, 'status is required'],
      enum: {
        values: VALID_INGESTION_STATUSES,
        message: 'Invalid ingestion status',
      },
      default: INGESTION_STATUS.PENDING,
      index: true,
    },
    error_code: {
      type: String,
      default: null,
      trim: true,
      maxlength: [100, 'error_code cannot exceed 100 characters'],
    },
    error_message: {
      type: String,
      default: null,
      trim: true,
      maxlength: [2000, 'error_message cannot exceed 2000 characters'],
    },
    started_at: {
      type: Date,
      default: null,
    },
    completed_at: {
      type: Date,
      default: null,
    },
  },
  {
    timestamps: { createdAt: 'created_at', updatedAt: 'updated_at' },
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

// Partial unique index enforces that at most one active ('processing') ingestion runs per repository
ingestionSchema.index(
  { repository_id: 1 },
  {
    unique: true,
    partialFilterExpression: { status: INGESTION_STATUS.PROCESSING },
  }
);

// Index for query pagination sorted by creation date
ingestionSchema.index({ repository_id: 1, created_at: -1 });

/**
 * Validates whether transition to target status is permitted.
 * @param {string} targetStatus
 * @returns {boolean}
 */
ingestionSchema.methods.canTransitionTo = function (targetStatus) {
  const allowed = {
    [INGESTION_STATUS.PENDING]: [INGESTION_STATUS.PROCESSING, INGESTION_STATUS.FAILED],
    [INGESTION_STATUS.PROCESSING]: [INGESTION_STATUS.COMPLETED, INGESTION_STATUS.FAILED],
    [INGESTION_STATUS.COMPLETED]: [],
    [INGESTION_STATUS.FAILED]: [],
  };

  const validTransitions = allowed[this.status] || [];
  return validTransitions.includes(targetStatus);
};

const Ingestion = mongoose.model('Ingestion', ingestionSchema);

module.exports = Ingestion;
