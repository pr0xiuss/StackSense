const fs = require('fs');
const path = require('path');
const { ArchiveExtractor } = require('./archiveExtractor');

/**
 * Result of source acquisition.
 * @typedef {object} AcquisitionResult
 * @property {string} rootPath
 * @property {string} revisionIdentifier
 * @property {string} sourceHash
 * @property {number} totalSourceBytes
 * @property {() => Promise<void> | null} cleanup
 */

class ArchiveAcquisitionHandler {
  /**
   * Check if this handler can process the given source type.
   * @param {string} sourceType
   * @returns {boolean}
   */
  canHandle(sourceType) {
    if (typeof sourceType !== 'string') return false;
    const val = sourceType.toLowerCase();
    return val === 'archive' || val === 'zip';
  }

  /**
   * Acquire and extract archive into tempRoot.
   *
   * @param {string} sourceReference Path to archive file on disk
   * @param {string|null} revisionIdentifier
   * @param {string} tempRoot
   * @returns {Promise<AcquisitionResult>}
   */
  async acquire(sourceReference, revisionIdentifier, tempRoot) {
    const destDir = path.join(tempRoot, 'extracted');
    const extracted = await ArchiveExtractor.extract(sourceReference, destDir, {
      unwrapSingleRoot: true,
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
          // Ignore cleanup errors
        }
      },
    };
  }
}

module.exports = ArchiveAcquisitionHandler;
