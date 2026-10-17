const crypto = require('crypto');
const mongoose = require('mongoose');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const repositoryRevisionSchema = new mongoose.Schema(
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
    repository_id: {
      type: String,
      required: [true, 'repository_id is required'],
      match: [UUID_V4_REGEX, 'repository_id must be a valid UUID v4'],
      ref: 'Repository',
    },
    ingestion_id: {
      type: String,
      default: null,
      ref: 'Ingestion',
    },
    revision_identifier: {
      type: String,
      required: [true, 'revision_identifier is required'],
      trim: true,
      maxlength: [255, 'revision_identifier cannot exceed 255 characters'],
    },
    source_hash: {
      type: String,
      required: [true, 'source_hash is required'],
      trim: true,
      maxlength: [64, 'source_hash cannot exceed 64 characters'],
    },
    total_files: {
      type: Number,
      required: [true, 'total_files is required'],
      min: [0, 'total_files cannot be negative'],
    },
    total_bytes: {
      type: Number,
      required: [true, 'total_bytes is required'],
      min: [0, 'total_bytes cannot be negative'],
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

// Compound unique index prevents duplicate revisions for the same repository
repositoryRevisionSchema.index(
  { repository_id: 1, revision_identifier: 1 },
  { unique: true }
);

// Query optimization index
repositoryRevisionSchema.index({ project_id: 1, created_at: -1 });

// Cascade delete artifacts when a revision is removed
repositoryRevisionSchema.post('findOneAndDelete', async function (doc) {
  if (doc) {
    const RepositoryArtifact = mongoose.models.RepositoryArtifact;
    if (RepositoryArtifact) {
      await RepositoryArtifact.deleteMany({ revision_id: doc._id });
    }
  }
});

const RepositoryRevision = mongoose.model('RepositoryRevision', repositoryRevisionSchema);

module.exports = RepositoryRevision;
