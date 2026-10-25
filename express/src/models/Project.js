const crypto = require('crypto');
const mongoose = require('mongoose');

const projectSchema = new mongoose.Schema(
  {
    _id: {
      type: String,
      default: () => crypto.randomUUID(),
    },
    name: {
      type: String,
      required: [true, 'Project name is required'],
      trim: true,
      minlength: [1, 'Project name cannot be empty'],
      maxlength: [255, 'Project name cannot exceed 255 characters'],
    },
    description: {
      type: String,
      trim: true,
      maxlength: [2000, 'Project description cannot exceed 2000 characters'],
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

projectSchema.index({ created_at: -1 });
 
projectSchema.post('findOneAndDelete', async function (doc) {
  if (doc) {
    const ProjectAccess = mongoose.models.ProjectAccess;
    if (ProjectAccess) {
      await ProjectAccess.deleteMany({ project_id: doc._id });
    }
  }
});

const Project = mongoose.model('Project', projectSchema);

module.exports = Project;
