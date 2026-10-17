const crypto = require('crypto');
const mongoose = require('mongoose');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const repositorySchema = new mongoose.Schema(
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
    name: {
      type: String,
      required: [true, 'Repository name is required'],
      trim: true,
      minlength: [1, 'Repository name cannot be empty'],
      maxlength: [255, 'Repository name cannot exceed 255 characters'],
    },
    description: {
      type: String,
      trim: true,
      maxlength: [2000, 'Repository description cannot exceed 2000 characters'],
      default: null,
    },
    status: {
      type: String,
      required: [true, 'Repository status is required'],
      default: 'registered',
      trim: true,
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

// Compound unique index enforces that repository name is unique within owning project
repositorySchema.index({ project_id: 1, name: 1 }, { unique: true });

// Index for performant querying and pagination
repositorySchema.index({ project_id: 1, created_at: 1 });

// Defensively cascade-delete associated child resources if Repository is deleted via query
repositorySchema.post('findOneAndDelete', async function (doc) {
  if (doc) {
    const Ingestion = mongoose.models.Ingestion;
    if (Ingestion) {
      await Ingestion.deleteMany({ repository_id: doc._id });
    }
    const RepositoryRevision = mongoose.models.RepositoryRevision;
    if (RepositoryRevision) {
      await RepositoryRevision.deleteMany({ repository_id: doc._id });
    }
    const RepositoryArtifact = mongoose.models.RepositoryArtifact;
    if (RepositoryArtifact) {
      await RepositoryArtifact.deleteMany({ repository_id: doc._id });
    }
  }
});

const Repository = mongoose.model('Repository', repositorySchema);

module.exports = Repository;
