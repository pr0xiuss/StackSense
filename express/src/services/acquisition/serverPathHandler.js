const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const storageConfig = require('../../config/storageConfig');
const { MAX_REPOSITORY_SIZE_BYTES } = require('../../constants/ingestionConstants');
const { ArchiveExtractor } = require('./archiveExtractor');

const {
  ServerPathNotAllowedError,
  ServerPathNotFoundError,
  UnsupportedArchiveFormatError,
  SourceValidationError,
} = require('../../errors/ingestionErrors');

class ServerPathAcquisitionHandler {
  /**
   * @param {string[]} [allowedRoots]
   */
  constructor(allowedRoots) {
    this._customAllowedRoots = allowedRoots;
  }

  /**
   * @param {string} sourceType
   * @returns {boolean}
   */
  canHandle(sourceType) {
    if (typeof sourceType !== 'string') return false;
    const val = sourceType.toLowerCase();
    return (
      val === 'server_path' ||
      val === 'directory' ||
      val === 'dir' ||
      val === 'local'
    );
  }

  /**
   * Safely acquire repository source from host filesystem path.
   *
   * @param {string} sourceReference
   * @param {string|null} revisionIdentifier
   * @param {string} tempRoot
   * @returns {Promise<import('./archiveHandler').AcquisitionResult>}
   */
  async acquire(sourceReference, revisionIdentifier, tempRoot) {
    const rawRoots = this._customAllowedRoots || storageConfig.allowedSourceRoots;
    const allowedRoots = rawRoots.map((r) => path.resolve(r));

    const candidate = path.resolve(sourceReference);

    // Jail verification against allowed roots (also detects symlink escape)
    let isAllowed = false;
    for (const root of allowedRoots) {
      const rel = path.relative(root, candidate);
      if (!rel.startsWith('..') && !path.isAbsolute(rel)) {
        isAllowed = true;
        break;
      }
    }

    if (!isAllowed) {
      throw new ServerPathNotAllowedError(
        `Server path '${sourceReference}' is outside the allowed source roots.`
      );
    }

    let stat;
    try {
      stat = await fs.promises.stat(candidate);
    } catch {
      throw new ServerPathNotFoundError(
        `Server path does not exist: '${sourceReference}'.`
      );
    }

    // Handle file archives (.zip, .tar, .tar.gz, .tgz)
    if (stat.isFile()) {
      const nameLower = path.basename(candidate).toLowerCase();
      const isSupported =
        nameLower.endsWith('.zip') ||
        nameLower.endsWith('.tar') ||
        nameLower.endsWith('.tar.gz') ||
        nameLower.endsWith('.tgz');

      if (!isSupported) {
        throw new UnsupportedArchiveFormatError(
          `Server path file '${path.basename(candidate)}' is not a supported archive format (.zip, .tar, .tar.gz, .tgz).`
        );
      }

      const destDir = path.join(tempRoot, 'extracted');
      const extracted = await ArchiveExtractor.extract(candidate, destDir, {
        unwrapSingleRoot: false,
      });

      const resolvedRev = revisionIdentifier || extracted.sourceHash.slice(0, 12);
      return {
        rootPath: extracted.rootPath,
        revisionIdentifier: resolvedRev,
        sourceHash: extracted.sourceHash,
        totalSourceBytes: extracted.archiveSize,
        cleanup: async () => {
          try {
            await fs.promises.rm(tempRoot, { recursive: true, force: true });
          } catch {
            // Ignore cleanup error
          }
        },
      };
    }

    // Handle staged directories in-place (no copy, cleanup is null)
    if (stat.isDirectory()) {
      const hasher = crypto.createHash('sha256');
      let totalBytes = 0;

      const discoveredFiles = [];
      async function walk(dir) {
        const entries = await fs.promises.readdir(dir, { withFileTypes: true });
        for (const entry of entries) {
          const fullPath = path.join(dir, entry.name);
          if (entry.isDirectory()) {
            await walk(fullPath);
          } else if (entry.isFile()) {
            discoveredFiles.push(fullPath);
          }
        }
      }

      await walk(candidate);
      discoveredFiles.sort();

      for (const filePath of discoveredFiles) {
        const rel = path.relative(candidate, filePath).replace(/\\/g, '/');
        if (rel.startsWith('..') || path.isAbsolute(rel)) {
          throw new SourceValidationError(
            `File path escapes directory root: ${filePath}`
          );
        }

        hasher.update(Buffer.from(rel, 'utf8'));
        const fileStat = await fs.promises.stat(filePath);
        totalBytes += fileStat.size;

        if (totalBytes > MAX_REPOSITORY_SIZE_BYTES) {
          throw new SourceValidationError(
            `Total repository size (${totalBytes} bytes) exceeds limit (${MAX_REPOSITORY_SIZE_BYTES} bytes).`
          );
        }
      }

      const sourceHash = hasher.digest('hex');
      const resolvedRev = revisionIdentifier || sourceHash.slice(0, 12);

      return {
        rootPath: candidate,
        revisionIdentifier: resolvedRev,
        sourceHash,
        totalSourceBytes: totalBytes,
        cleanup: null, // Never delete persistent server directory
      };
    }

    throw new SourceValidationError(
      `Server path is neither a file nor a directory: '${sourceReference}'.`
    );
  }
}

module.exports = ServerPathAcquisitionHandler;
