const fs = require('fs');
const path = require('path');

const {
  MAX_DIRECTORY_DEPTH,
  MAX_EXTRACTED_SIZE_BYTES,
  MAX_PATH_LENGTH,
  MAX_REPOSITORY_FILE_COUNT,
} = require('../../constants/ingestionConstants');

const { SourceValidationError } = require('../../errors/ingestionErrors');

/**
 * @typedef {object} DiscoveredFile
 * @property {string} relativePath Normalized forward-slash relative path
 * @property {string} absolutePath Full filesystem path
 * @property {number} sizeBytes Size of file in bytes
 */

/**
 * @typedef {object} ValidatedSource
 * @property {DiscoveredFile[]} files
 * @property {number} totalFiles
 * @property {number} totalBytes
 */

class SourceValidator {
  /**
   * @param {object} [options]
   * @param {number} [options.maxPathLength=MAX_PATH_LENGTH]
   * @param {number} [options.maxDirectoryDepth=MAX_DIRECTORY_DEPTH]
   * @param {number} [options.maxFileCount=MAX_REPOSITORY_FILE_COUNT]
   * @param {number} [options.maxExtractedSizeBytes=MAX_EXTRACTED_SIZE_BYTES]
   */
  constructor({
    maxPathLength = MAX_PATH_LENGTH,
    maxDirectoryDepth = MAX_DIRECTORY_DEPTH,
    maxFileCount = MAX_REPOSITORY_FILE_COUNT,
    maxExtractedSizeBytes = MAX_EXTRACTED_SIZE_BYTES,
  } = {}) {
    this._maxPathLength = maxPathLength;
    this._maxDirectoryDepth = maxDirectoryDepth;
    this._maxFileCount = maxFileCount;
    this._maxExtractedSizeBytes = maxExtractedSizeBytes;
  }

  /**
   * Validates repository file structure, path lengths, depth, and resource bounds.
   *
   * @param {string} rootPath Root path to scan
   * @returns {Promise<ValidatedSource>}
   */
  async validate(rootPath) {
    let resolvedRoot;
    try {
      resolvedRoot = path.resolve(rootPath);
      const stat = await fs.promises.stat(resolvedRoot);
      if (!stat.isDirectory()) {
        throw new SourceValidationError(`Validation target is not a directory: ${resolvedRoot}`);
      }
    } catch (err) {
      if (err instanceof SourceValidationError) throw err;
      throw new SourceValidationError(`Failed to resolve repository path ${rootPath}: ${err.message}`);
    }

    const discovered = [];
    let totalBytes = 0;

    // Recursively collect all file paths
    const filePaths = [];
    async function walk(currentDir) {
      const entries = await fs.promises.readdir(currentDir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(currentDir, entry.name);
        if (entry.isDirectory()) {
          await walk(fullPath);
        } else if (entry.isFile()) {
          filePaths.push(fullPath);
        }
      }
    }

    try {
      await walk(resolvedRoot);
    } catch (err) {
      throw new SourceValidationError(`Failed to scan repository files: ${err.message}`);
    }

    // Sort paths deterministically
    filePaths.sort();

    for (const item of filePaths) {
      let resolvedItem;
      try {
        resolvedItem = await fs.promises.realpath(item);
      } catch (err) {
        throw new SourceValidationError(`Filesystem access error validating path ${item}: ${err.message}`);
      }

      // Prevent symlink escapes
      const relToRoot = path.relative(resolvedRoot, resolvedItem);
      if (relToRoot.startsWith('..') || path.isAbsolute(relToRoot)) {
        throw new SourceValidationError(`Symlink or path escapes repository root: ${item}`);
      }

      const relPath = path.relative(resolvedRoot, item).replace(/\\/g, '/');

      if (relPath.length > this._maxPathLength) {
        throw new SourceValidationError(
          `Path length (${relPath.length}) exceeds limit of ${this._maxPathLength}: ${relPath}`
        );
      }

      const parts = relPath.split('/');
      const depth = parts.length - 1;
      if (depth > this._maxDirectoryDepth) {
        throw new SourceValidationError(
          `Directory depth (${depth}) exceeds limit of ${this._maxDirectoryDepth}: ${relPath}`
        );
      }

      let fileSize;
      try {
        const stat = await fs.promises.stat(item);
        fileSize = stat.size;
      } catch (err) {
        throw new SourceValidationError(`Filesystem access error validating path ${item}: ${err.message}`);
      }

      totalBytes += fileSize;

      discovered.push({
        relativePath: relPath,
        absolutePath: item,
        sizeBytes: fileSize,
      });

      if (discovered.length > this._maxFileCount) {
        throw new SourceValidationError(
          `File count exceeds maximum repository file limit of ${this._maxFileCount}.`
        );
      }

      if (totalBytes > this._maxExtractedSizeBytes) {
        throw new SourceValidationError(
          `Total extracted size (${totalBytes} bytes) exceeds maximum repository size of ${this._maxExtractedSizeBytes} bytes.`
        );
      }
    }

    return {
      files: discovered,
      totalFiles: discovered.length,
      totalBytes,
    };
  }
}

module.exports = SourceValidator;
