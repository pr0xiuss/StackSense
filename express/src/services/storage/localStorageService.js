const fs = require('fs');
const path = require('path');
const { pipeline } = require('stream/promises');
const StorageService = require('./storageService');
const { StorageOperationError } = require('../../errors/ingestionErrors');

/**
 * Filesystem-backed implementation of StorageService.
 * Operates strictly within an isolated root directory, verifying that all
 * read, write, and delete operations remain contained.
 */
class LocalStorageService extends StorageService {
  /**
   * @param {string} rootPath Root filesystem directory for storage.
   */
  constructor(rootPath) {
    super();
    try {
      this._root = path.resolve(rootPath);
      fs.mkdirSync(this._root, { recursive: true });
    } catch (err) {
      throw new StorageOperationError(
        `Failed to initialize storage root at ${rootPath}: ${err.message}`
      );
    }
  }

  /**
   * Get resolved root path.
   * @returns {string}
   */
  get root() {
    return this._root;
  }

  /**
   * Normalize key and verify target path does not escape storage root.
   * @param {string} key
   * @returns {string} Absolute resolved file path
   * @throws {StorageOperationError}
   */
  _resolveKey(key) {
    if (typeof key !== 'string') {
      throw new StorageOperationError(`Invalid storage key type: ${typeof key}`);
    }

    const cleanKey = key.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
    if (!cleanKey || cleanKey.split('/').includes('..')) {
      throw new StorageOperationError(`Invalid storage key: ${key}`);
    }

    const target = path.resolve(this._root, cleanKey);
    // Relative path check to ensure containment
    const relative = path.relative(this._root, target);
    if (relative.startsWith('..') || path.isAbsolute(relative)) {
      throw new StorageOperationError(`Storage key escapes storage root: ${key}`);
    }

    return target;
  }

  /**
   * Store content under key and return the canonical key.
   * @param {string} key
   * @param {Buffer|import('stream').Readable} data
   * @returns {Promise<string>}
   */
  async put(key, data) {
    const target = this._resolveKey(key);
    try {
      await fs.promises.mkdir(path.dirname(target), { recursive: true });
      if (Buffer.isBuffer(data) || typeof data === 'string') {
        await fs.promises.writeFile(target, data);
      } else if (data && typeof data.pipe === 'function') {
        const writeStream = fs.createWriteStream(target);
        await pipeline(data, writeStream);
      } else {
        throw new Error('Unsupported data type for StorageService.put');
      }
      return key.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
    } catch (err) {
      throw new StorageOperationError(`Failed to write storage key ${key}: ${err.message}`);
    }
  }

  /**
   * Retrieve a readable stream for key.
   * @param {string} key
   * @returns {Promise<import('fs').ReadStream>}
   */
  async get(key) {
    const target = this._resolveKey(key);
    try {
      const stat = await fs.promises.stat(target);
      if (!stat.isFile()) {
        throw new StorageOperationError(`Object not found at storage key: ${key}`);
      }
      return fs.createReadStream(target);
    } catch (err) {
      if (err instanceof StorageOperationError) throw err;
      throw new StorageOperationError(`Failed to read storage key ${key}: ${err.message}`);
    }
  }

  /**
   * Return true if an object exists at key, false otherwise.
   * @param {string} key
   * @returns {Promise<boolean>}
   */
  async exists(key) {
    try {
      const target = this._resolveKey(key);
      const stat = await fs.promises.stat(target);
      return stat.isFile();
    } catch {
      return false;
    }
  }

  /**
   * Delete the object at key if it exists.
   * @param {string} key
   * @returns {Promise<void>}
   */
  async delete(key) {
    const target = this._resolveKey(key);
    try {
      await fs.promises.unlink(target);
    } catch (err) {
      if (err.code !== 'ENOENT') {
        throw new StorageOperationError(`Failed to delete storage key ${key}: ${err.message}`);
      }
    }
  }

  /**
   * Delete all objects sharing the given key prefix.
   * @param {string} prefix
   * @returns {Promise<void>}
   */
  async deletePrefix(prefix) {
    if (typeof prefix !== 'string') {
      throw new StorageOperationError(`Invalid storage prefix type: ${typeof prefix}`);
    }

    const cleanPrefix = prefix.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
    if (!cleanPrefix) {
      throw new StorageOperationError(
        'Cannot delete empty storage prefix (root deletion blocked)'
      );
    }

    const target = this._resolveKey(cleanPrefix);
    try {
      let stat;
      try {
        stat = await fs.promises.stat(target);
      } catch (err) {
        if (err.code !== 'ENOENT') throw err;
      }

      if (stat) {
        if (stat.isDirectory()) {
          await fs.promises.rm(target, { recursive: true, force: true });
          return;
        } else if (stat.isFile()) {
          await fs.promises.unlink(target);
          return;
        }
      }

      // Check parent directory for items starting with prefix pattern
      const parentDir = path.dirname(target);
      try {
        const parentStat = await fs.promises.stat(parentDir);
        if (parentStat.isDirectory()) {
          const files = await fs.promises.readdir(parentDir);
          const basePrefix = path.basename(target);
          for (const file of files) {
            if (file.startsWith(basePrefix)) {
              await fs.promises.rm(path.join(parentDir, file), { recursive: true, force: true });
            }
          }
        }
      } catch (err) {
        if (err.code !== 'ENOENT') throw err;
      }
    } catch (err) {
      throw new StorageOperationError(`Failed to delete storage prefix ${prefix}: ${err.message}`);
    }
  }
}

module.exports = LocalStorageService;
