const crypto = require('crypto');
const mongoose = require('mongoose');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const refreshTokenSchema = new mongoose.Schema(
  {
    _id: {
      type: String,
      default: () => crypto.randomUUID(),
      match: [UUID_V4_REGEX, 'RefreshToken id must be a valid UUID v4'],
    },
    user_id: {
      type: String,
      required: [true, 'user_id is required'],
      match: [UUID_V4_REGEX, 'user_id must be a valid UUID v4'],
      ref: 'User',
    },
    token_hash: {
      type: String,
      required: [true, 'token_hash is required'],
    },
    expires_at: {
      type: Date,
      required: [true, 'expires_at is required'],
    },
    revoked_at: {
      type: Date,
      default: null,
    },
    replaced_by_token_id: {
      type: String,
      default: null,
      validate: {
        validator: function (v) {
          return v === null || v === undefined || UUID_V4_REGEX.test(v);
        },
        message: 'replaced_by_token_id must be a valid UUID v4',
      },
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

// Indexes
refreshTokenSchema.index({ token_hash: 1 }, { unique: true });
refreshTokenSchema.index({ user_id: 1 });

// Helper functions and virtuals (matching Python domain @property)
function checkIsActive(doc) {
  return !doc.revoked_at && doc.expires_at > new Date();
}

function checkIsExpired(doc) {
  return doc.expires_at <= new Date();
}

function checkIsRevoked(doc) {
  return doc.revoked_at !== null && doc.revoked_at !== undefined;
}

refreshTokenSchema.virtual('isActive').get(function () {
  return checkIsActive(this);
});

refreshTokenSchema.virtual('isExpired').get(function () {
  return checkIsExpired(this);
});

refreshTokenSchema.virtual('isRevoked').get(function () {
  return checkIsRevoked(this);
});

// Also support snake_case getters
refreshTokenSchema.virtual('is_active').get(function () {
  return checkIsActive(this);
});
refreshTokenSchema.virtual('is_expired').get(function () {
  return checkIsExpired(this);
});
refreshTokenSchema.virtual('is_revoked').get(function () {
  return checkIsRevoked(this);
});

const RefreshToken = mongoose.model('RefreshToken', refreshTokenSchema, 'refresh_tokens');

module.exports = RefreshToken;
