const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const multer = require('multer');

const { MAX_REPOSITORY_SIZE_BYTES } = require('../constants/ingestionConstants');
const { UnsupportedArchiveFormatError } = require('../errors/ingestionErrors');

const SUPPORTED_ARCHIVE_SUFFIXES = ['.tar.gz', '.tgz', '.tar', '.zip'];

/**
 * Validates uploaded filename and returns canonical archive suffix.
 * Compound extensions ('.tar.gz') evaluated before single-part ('.tar').
 *
 * @param {string} filename
 * @returns {string} Suffix
 * @throws {UnsupportedArchiveFormatError}
 */
function getUploadSuffix(filename) {
  if (!filename || typeof filename !== 'string') {
    throw new UnsupportedArchiveFormatError(
      'Uploaded file must have a filename with a supported archive extension.'
    );
  }

  const fnLower = filename.toLowerCase();
  for (const ext of SUPPORTED_ARCHIVE_SUFFIXES) {
    if (fnLower.endsWith(ext)) {
      return ext;
    }
  }

  throw new UnsupportedArchiveFormatError(
    `Unsupported archive format for file '${filename}'. Supported formats: .zip, .tar, .tar.gz, .tgz.`
  );
}

const uploadsDir = path.join(os.tmpdir(), 'stacksense_uploads');
try {
  fs.mkdirSync(uploadsDir, { recursive: true });
} catch {
  // Ignore mkdir error
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, uploadsDir);
  },
  filename: (req, file, cb) => {
    try {
      const suffix = getUploadSuffix(file.originalname);
      const uniqueName = `upload_${Date.now()}_${crypto.randomUUID()}${suffix}`;
      cb(null, uniqueName);
    } catch (err) {
      cb(err);
    }
  },
});

const upload = multer({
  storage,
  limits: {
    fileSize: MAX_REPOSITORY_SIZE_BYTES,
  },
  fileFilter: (req, file, cb) => {
    try {
      getUploadSuffix(file.originalname);
      cb(null, true);
    } catch (err) {
      cb(err);
    }
  },
});

module.exports = {
  upload,
  getUploadSuffix,
  SUPPORTED_ARCHIVE_SUFFIXES,
};
