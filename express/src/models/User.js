const crypto = require('crypto');
const mongoose = require('mongoose');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const USERNAME_REGEX = /^[a-zA-Z0-9_]{3,30}$/;

const userSchema = new mongoose.Schema(
  {
    _id: {
      type: String,
      default: () => crypto.randomUUID(),
      match: [UUID_V4_REGEX, 'User id must be a valid UUID v4'],
    },
    email: {
      type: String,
      required: [true, 'User email is required'],
      trim: true,
      lowercase: true,
      minlength: [1, 'User email cannot be empty'],
      maxlength: [255, 'User email cannot exceed 255 characters'],
    },
    username: {
      type: String,
      required: [true, 'User username is required'],
      trim: true,
      lowercase: true,
      match: [
        USERNAME_REGEX,
        'Username must be between 3 and 30 characters and contain only letters, numbers, and underscores',
      ],
    },
    password_hash: {
      type: String,
      required: [true, 'Password hash is required'],
      select: false,
    },
    is_active: {
      type: Boolean,
      default: true,
    },
  },
  {
    timestamps: { createdAt: 'created_at', updatedAt: 'updated_at' },
    versionKey: false,
    toJSON: {
      transform: (doc, ret) => {
        ret.id = ret._id;
        delete ret._id;
        delete ret.password_hash;
        return ret;
      },
    },
    toObject: {
      transform: (doc, ret) => {
        ret.id = ret._id;
        delete ret._id;
        delete ret.password_hash;
        return ret;
      },
    },
  }
);

userSchema.index({ email: 1 }, { unique: true });
userSchema.index({ username: 1 }, { unique: true });

const User = mongoose.model('User', userSchema, 'users');

module.exports = User;
