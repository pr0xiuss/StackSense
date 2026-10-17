const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const yauzl = require('yauzl');
const tar = require('tar');
const { pipeline } = require('stream/promises');

const {
  MAX_REPOSITORY_SIZE_BYTES,
  MAX_EXTRACTED_SIZE_BYTES,
  MAX_REPOSITORY_FILE_COUNT,
  MAX_DIRECTORY_DEPTH,
  MAX_PATH_LENGTH,
  MAX_ARCHIVE_NESTING_DEPTH,
  MAX_COMPRESSION_RATIO,
} = require('../../constants/ingestionConstants');

const {
  SourceValidationError,
  MaxFileCountExceededError,
} = require('../../errors/ingestionErrors');

const ARCHIVE_EXTENSIONS = new Set(['.zip', '.tar', '.gz', '.tgz', '.bz2', '.7z']);

const WINDOWS_RESERVED_NAMES = new Set([
  'CON', 'PRN', 'AUX', 'NUL',
  'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
  'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
]);

const WINDOWS_DRIVE_PATTERN = /^[a-zA-Z]:/;

/**
 * Validate archive member path against traversal, escaping, and device injection.
 *
 * @param {string} rawPath
 * @param {object} options
 * @param {boolean} options.isDir
 * @param {string} options.destinationDir
 * @param {string} options.destResolved
 * @returns {string|null} Resolved destination path or null if entry is root itself
 * @throws {SourceValidationError}
 */
function sanitizeAndValidateMemberPath(rawPath, { isDir, destinationDir, destResolved }) {
  if (typeof rawPath !== 'string') {
    throw new SourceValidationError(`Invalid archive member path type: ${typeof rawPath}`);
  }

  if (rawPath.includes('\x00')) {
    throw new SourceValidationError(
      `Path traversal detected in archive member (null byte): ${JSON.stringify(rawPath)}`
    );
  }

  // Check for absolute paths before any stripping
  if (rawPath.startsWith('/') || rawPath.startsWith('\\')) {
    throw new SourceValidationError(`Path traversal detected in archive member: ${rawPath}`);
  }

  // Check for UNC network share paths
  if (rawPath.startsWith('//') || rawPath.startsWith('\\\\')) {
    throw new SourceValidationError(`Path traversal detected in archive member: ${rawPath}`);
  }

  // Check for Windows drive-letter paths (e.g. C:, C:\, C:/, d:foo)
  if (WINDOWS_DRIVE_PATTERN.test(rawPath)) {
    throw new SourceValidationError(`Path traversal detected in archive member: ${rawPath}`);
  }

  // Normalize backslashes to forward slashes
  const normalized = rawPath.replace(/\\/g, '/');

  // Strip leading and trailing slashes for segment analysis
  let cleanName = normalized.replace(/^\/+|\/+$/g, '');
  if (!cleanName) {
    return null; // Root entry
  }

  // If path starts with './', strip prefix
  if (cleanName.startsWith('./')) {
    cleanName = cleanName.slice(2).replace(/^\/+/, '');
    if (!cleanName) {
      return null;
    }
  }

  if (cleanName.length > MAX_PATH_LENGTH) {
    throw new SourceValidationError(
      `Archive member path exceeds ${MAX_PATH_LENGTH} characters: ${cleanName}`
    );
  }

  const parts = cleanName.split('/');
  if (parts.includes('..') || parts.includes('') || parts.some((p) => p.includes(':'))) {
    throw new SourceValidationError(`Path traversal detected in archive member: ${rawPath}`);
  }

  for (const part of parts) {
    const stem = part.split('.')[0].toUpperCase();
    if (WINDOWS_RESERVED_NAMES.has(stem)) {
      throw new SourceValidationError(
        `Prohibited Windows reserved device name in archive member: ${rawPath}`
      );
    }
  }

  const depth = parts.length - (isDir ? 1 : 0);
  if (depth > MAX_DIRECTORY_DEPTH) {
    throw new SourceValidationError(
      `Directory depth (${depth}) exceeds limit of ${MAX_DIRECTORY_DEPTH}: ${cleanName}`
    );
  }

  const destPath = path.resolve(destinationDir, cleanName);
  const relative = path.relative(destResolved, destPath);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new SourceValidationError(`Member extraction escapes target: ${cleanName}`);
  }

  return destPath;
}

/**
 * Result of safe archive extraction.
 * @typedef {object} ExtractedArchive
 * @property {string} rootPath
 * @property {string} sourceHash
 * @property {number} archiveSize
 */

class ArchiveExtractor {
  /**
   * Safely extract archive with resource limits and traversal defenses.
   *
   * @param {string} archivePath
   * @param {string} destinationDir
   * @param {object} [options]
   * @param {boolean} [options.unwrapSingleRoot=false]
   * @returns {Promise<ExtractedArchive>}
   */
  static async extract(archivePath, destinationDir, { unwrapSingleRoot = false } = {}) {
    const resolvedArchive = path.resolve(archivePath);

    let stat;
    try {
      stat = await fs.promises.stat(resolvedArchive);
    } catch {
      throw new SourceValidationError(`Archive source does not exist: ${archivePath}`);
    }

    if (!stat.isFile()) {
      throw new SourceValidationError(`Archive source is not a file: ${archivePath}`);
    }

    const archiveSize = stat.size;
    if (archiveSize > MAX_REPOSITORY_SIZE_BYTES) {
      throw new SourceValidationError(
        `Archive size (${archiveSize} bytes) exceeds limit (${MAX_REPOSITORY_SIZE_BYTES} bytes).`
      );
    }

    // Compute streaming SHA-256 hash in 64 KB chunks
    const sourceHash = await new Promise((resolve, reject) => {
      const hasher = crypto.createHash('sha256');
      const stream = fs.createReadStream(resolvedArchive, { highWaterMark: 65536 });
      stream.on('data', (chunk) => hasher.update(chunk));
      stream.on('error', (err) => reject(new SourceValidationError(`Hashing failed: ${err.message}`)));
      stream.on('end', () => resolve(hasher.digest('hex')));
    });

    const resolvedDest = path.resolve(destinationDir);
    await fs.promises.mkdir(resolvedDest, { recursive: true });

    const extLower = resolvedArchive.toLowerCase();
    const isZip = extLower.endsWith('.zip');
    const isTar =
      extLower.endsWith('.tar') || extLower.endsWith('.tar.gz') || extLower.endsWith('.tgz');

    if (isZip) {
      await ArchiveExtractor._extractZip(resolvedArchive, resolvedDest);
    } else if (isTar) {
      await ArchiveExtractor._extractTar(resolvedArchive, archiveSize, resolvedDest);
    } else {
      // Attempt zip inspection first, then tar
      let extracted = false;
      try {
        await ArchiveExtractor._extractZip(resolvedArchive, resolvedDest);
        extracted = true;
      } catch (err) {
        if (!(err instanceof SourceValidationError) && !(err instanceof MaxFileCountExceededError)) {
          // Non-zip, attempt tar
        } else {
          throw err;
        }
      }

      if (!extracted) {
        try {
          await ArchiveExtractor._extractTar(resolvedArchive, archiveSize, resolvedDest);
          extracted = true;
        } catch (err) {
          if (err instanceof SourceValidationError || err instanceof MaxFileCountExceededError) {
            throw err;
          }
          throw new SourceValidationError(
            `Source file '${path.basename(archivePath)}' is not a valid archive.`
          );
        }
      }
    }

    let rootPath = resolvedDest;
    if (unwrapSingleRoot) {
      const children = await fs.promises.readdir(resolvedDest, { withFileTypes: true });
      if (children.length === 1 && children[0].isDirectory()) {
        rootPath = path.join(resolvedDest, children[0].name);
      }
    }

    return {
      rootPath,
      sourceHash,
      archiveSize,
    };
  }

  /**
   * Safe zip extraction using yauzl.
   * @param {string} archivePath
   * @param {string} destinationDir
   */
  static _extractZip(archivePath, destinationDir) {
    return new Promise((resolve, reject) => {
      yauzl.open(archivePath, { lazyEntries: true, autoClose: true }, (err, zipfile) => {
        if (err) {
          return reject(new SourceValidationError(`Corrupt zip archive: ${err.message}`));
        }

        if (zipfile.entryCount > MAX_REPOSITORY_FILE_COUNT) {
          zipfile.close();
          return reject(
            new MaxFileCountExceededError(
              `Archive contains ${zipfile.entryCount} files, exceeding limit of ${MAX_REPOSITORY_FILE_COUNT}.`
            )
          );
        }

        let totalUncompressed = 0;
        let entryCount = 0;

        zipfile.readEntry();

        zipfile.on('entry', async (entry) => {
          entryCount += 1;
          if (entryCount > MAX_REPOSITORY_FILE_COUNT) {
            zipfile.close();
            return reject(
              new MaxFileCountExceededError(
                `Archive contains ${entryCount} files, exceeding limit of ${MAX_REPOSITORY_FILE_COUNT}.`
              )
            );
          }

          try {
            // Check for symlinks in externalFileAttributes (Unix mode 0120000 = symlink)
            const mode = (entry.externalFileAttributes >> 16) & 0o170000;
            if (mode === 0o120000) {
              zipfile.close();
              return reject(
                new SourceValidationError(
                  `Archive member '${entry.fileName}' is a link. Symbolic and hard links are not permitted.`
                )
              );
            }

            const isDir = entry.fileName.endsWith('/');
            const destFile = sanitizeAndValidateMemberPath(entry.fileName, {
              isDir,
              destinationDir,
              destResolved: destinationDir,
            });

            if (!destFile) {
              return zipfile.readEntry();
            }

            // Check nested archive extensions in relative path
            const relPath = path.relative(destinationDir, destFile).replace(/\\/g, '/');
            const parts = relPath.split('/');
            const nestingCount = parts.reduce((cnt, part) => {
              const ext = path.extname(part).toLowerCase();
              return ARCHIVE_EXTENSIONS.has(ext) ? cnt + 1 : cnt;
            }, 0);

            if (nestingCount > MAX_ARCHIVE_NESTING_DEPTH) {
              zipfile.close();
              return reject(
                new SourceValidationError(
                  `Archive nesting depth exceeds limit of ${MAX_ARCHIVE_NESTING_DEPTH}: ${path.basename(destFile)}`
                )
              );
            }

            totalUncompressed += entry.uncompressedSize;
            if (totalUncompressed > MAX_EXTRACTED_SIZE_BYTES) {
              zipfile.close();
              return reject(
                new SourceValidationError(
                  `Uncompressed archive exceeds limit of ${MAX_EXTRACTED_SIZE_BYTES} bytes.`
                )
              );
            }

            // Compression bomb check for files > 1 MB
            if (entry.compressedSize > 0 && entry.uncompressedSize > 1024 * 1024) {
              const ratio = entry.uncompressedSize / entry.compressedSize;
              if (ratio > MAX_COMPRESSION_RATIO) {
                zipfile.close();
                return reject(
                  new SourceValidationError(
                    `High compression ratio (${ratio.toFixed(1)}:1) detected on ${path.basename(destFile)}, exceeding safety limit.`
                  )
                );
              }
            }

            if (isDir) {
              await fs.promises.mkdir(destFile, { recursive: true });
              zipfile.readEntry();
            } else {
              await fs.promises.mkdir(path.dirname(destFile), { recursive: true });
              zipfile.openReadStream(entry, async (streamErr, readStream) => {
                if (streamErr) {
                  zipfile.close();
                  return reject(new SourceValidationError(`Failed to extract ${entry.fileName}: ${streamErr.message}`));
                }

                const writeStream = fs.createWriteStream(destFile);
                try {
                  await pipeline(readStream, writeStream);
                  zipfile.readEntry();
                } catch (writeErr) {
                  zipfile.close();
                  reject(new SourceValidationError(`Write error on ${entry.fileName}: ${writeErr.message}`));
                }
              });
            }
          } catch (validateErr) {
            zipfile.close();
            reject(validateErr);
          }
        });

        zipfile.on('end', () => resolve());
        zipfile.on('error', (err) => reject(new SourceValidationError(`Corrupt zip archive: ${err.message}`)));
      });
    });
  }

  /**
   * Safe tar extraction using streaming parser.
   * @param {string} archivePath
   * @param {number} archiveSize
   * @param {string} destinationDir
   */
  static _extractTar(archivePath, archiveSize, destinationDir) {
    return new Promise((resolve, reject) => {
      let fileCount = 0;
      let totalUncompressed = 0;
      let settled = false;

      function fail(err) {
        if (!settled) {
          settled = true;
          reject(err);
        }
      }

      const parser = new tar.Parser({
        onReadEntry(entry) {
          if (settled) {
            entry.resume();
            return;
          }

          fileCount += 1;
          if (fileCount > MAX_REPOSITORY_FILE_COUNT) {
            entry.resume();
            fail(
              new MaxFileCountExceededError(
                `Archive contains ${fileCount} files, exceeding limit of ${MAX_REPOSITORY_FILE_COUNT}.`
              )
            );
            return;
          }

          // Reject symbolic and hard links
          if (entry.type === 'SymbolicLink' || entry.type === 'Link') {
            entry.resume();
            fail(
              new SourceValidationError(
                `Archive member '${entry.path}' is a link. Symbolic and hard links are not permitted.`
              )
            );
            return;
          }

          // Strictly allow only files and directories (reject FIFOs, devices, sockets)
          if (entry.type !== 'File' && entry.type !== 'Directory') {
            entry.resume();
            fail(
              new SourceValidationError(
                `Prohibited special device, FIFO, or socket entry: ${entry.path}`
              )
            );
            return;
          }

          const isDir = entry.type === 'Directory';
          let destEntry;
          try {
            destEntry = sanitizeAndValidateMemberPath(entry.path, {
              isDir,
              destinationDir,
              destResolved: destinationDir,
            });
          } catch (err) {
            entry.resume();
            fail(err);
            return;
          }

          if (!destEntry) {
            entry.resume();
            return;
          }

          const relPath = path.relative(destinationDir, destEntry).replace(/\\/g, '/');
          const parts = relPath.split('/');
          const nestingCount = parts.reduce((cnt, part) => {
            const ext = path.extname(part).toLowerCase();
            return ARCHIVE_EXTENSIONS.has(ext) ? cnt + 1 : cnt;
          }, 0);

          if (nestingCount > MAX_ARCHIVE_NESTING_DEPTH) {
            entry.resume();
            fail(
              new SourceValidationError(
                `Archive nesting depth exceeds limit of ${MAX_ARCHIVE_NESTING_DEPTH}: ${path.basename(destEntry)}`
              )
            );
            return;
          }

          totalUncompressed += entry.size || 0;
          if (totalUncompressed > MAX_EXTRACTED_SIZE_BYTES) {
            entry.resume();
            fail(
              new SourceValidationError(
                `Uncompressed archive exceeds limit of ${MAX_EXTRACTED_SIZE_BYTES} bytes.`
              )
            );
            return;
          }

          if (archiveSize > 0 && entry.size > 1024 * 1024) {
            const ratio = totalUncompressed / archiveSize;
            if (ratio > MAX_COMPRESSION_RATIO) {
              entry.resume();
              fail(
                new SourceValidationError(
                  `High compression ratio (${ratio.toFixed(1)}:1) detected on ${path.basename(destEntry)}, exceeding safety limit.`
                )
              );
              return;
            }
          }

          if (isDir) {
            try {
              fs.mkdirSync(destEntry, { recursive: true });
            } catch (err) {
              entry.resume();
              fail(new SourceValidationError(`Failed to create directory: ${err.message}`));
              return;
            }
            entry.resume();
          } else {
            try {
              fs.mkdirSync(path.dirname(destEntry), { recursive: true });
              const writeStream = fs.createWriteStream(destEntry);
              entry.pipe(writeStream);
              writeStream.on('error', (err) => {
                fail(new SourceValidationError(`Write error on ${entry.path}: ${err.message}`));
              });
            } catch (err) {
              entry.resume();
              fail(new SourceValidationError(`Extraction error on ${entry.path}: ${err.message}`));
            }
          }
        },
      });

      const fileStream = fs.createReadStream(archivePath);
      fileStream.on('error', (err) => fail(new SourceValidationError(`Corrupt tar archive: ${err.message}`)));
      parser.on('error', (err) => fail(new SourceValidationError(`Corrupt tar archive: ${err.message}`)));
      parser.on('finish', () => {
        if (!settled) {
          settled = true;
          resolve();
        }
      });

      fileStream.pipe(parser);
    });
  }
}

module.exports = {
  ArchiveExtractor,
  sanitizeAndValidateMemberPath,
};
