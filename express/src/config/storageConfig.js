const path = require('path');

/**
 * Storage and acquisition configuration.
 */
const storageConfig = {
  // Base directory for content-addressable storage
  storageRoot: process.env.STORAGE_ROOT || path.resolve(__dirname, '../../data/storage'),

  // Configured server filesystem source roots allowed for server_path ingestion
  allowedSourceRoots: process.env.ALLOWED_SOURCE_ROOTS
    ? process.env.ALLOWED_SOURCE_ROOTS.split(',').map((r) => path.resolve(r.trim()))
    : [path.resolve(__dirname, '../../data/staging'), path.resolve(__dirname, '../../data/sources')],

  // GitHub acquisition settings
  githubUserAgent: process.env.GITHUB_USER_AGENT || 'StackSense-Ingestion/0.1.0',
  githubTimeoutSeconds: parseInt(process.env.GITHUB_TIMEOUT_SECONDS || '60', 10),
};

module.exports = storageConfig;
