/**
 * Abstract interface defining external content storage operations.
 * Decouples the application layer from filesystem, S3, or other concrete storage mechanisms.
 */
class StorageService {
  /**
   * Store content under a given key and return the stored canonical key.
   * @param {string} key
   * @param {Buffer|ReadableStream} data
   * @returns {Promise<string>}
   */
  async put(key, data) {
    throw new Error('StorageService.put() must be implemented by subclass.');
  }

  /**
   * Retrieve a readable stream for a given key.
   * @param {string} key
   * @returns {Promise<import('stream').Readable>}
   */
  async get(key) {
    throw new Error('StorageService.get() must be implemented by subclass.');
  }

  /**
   * Check if an object exists at the given key.
   * @param {string} key
   * @returns {Promise<boolean>}
   */
  async exists(key) {
    throw new Error('StorageService.exists() must be implemented by subclass.');
  }

  /**
   * Delete the object at the given key.
   * @param {string} key
   * @returns {Promise<void>}
   */
  async delete(key) {
    throw new Error('StorageService.delete() must be implemented by subclass.');
  }

  /**
   * Delete all objects sharing the given key prefix (compensating cleanup).
   * @param {string} prefix
   * @returns {Promise<void>}
   */
  async deletePrefix(prefix) {
    throw new Error('StorageService.deletePrefix() must be implemented by subclass.');
  }
}

module.exports = StorageService;
