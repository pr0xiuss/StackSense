/**
 * Constants, resource limits, and classification enums for repository ingestion.
 * Governed by master.txt Section 7 and Appendix G.
 */

// --- Section 7 Baseline Resource Limits ---
const MAX_REPOSITORY_SIZE_BYTES = 500 * 1024 * 1024; // 500 MB (Section 7.4)
const MAX_EXTRACTED_SIZE_BYTES = 1024 * 1024 * 1024; // 1 GB (Section 7.5)
const MAX_INDIVIDUAL_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB (Section 7.6)
const MAX_REPOSITORY_FILE_COUNT = 50000; // 50,000 files (Section 7.7)
const MAX_DIRECTORY_DEPTH = 100; // 100 levels (Section 7.8)
const MAX_PATH_LENGTH = 4096; // 4,096 characters (Section 7.9)
const MAX_ARCHIVE_NESTING_DEPTH = 2; // 2 levels (Section 7.10)
const MAX_COMPRESSION_RATIO = 100.0; // 100:1 ratio (Section 7.11)
const DEFAULT_STALE_INGESTION_TIMEOUT_MS = 60 * 60 * 1000; // 1 hour staleness recovery threshold (IR-M4-017)

// --- Canonical Source Types ---
const SOURCE_TYPES = Object.freeze({
  GITHUB: 'github',
  ARCHIVE: 'archive',
  SERVER_PATH: 'server_path',
});

const VALID_SOURCE_TYPES = Object.freeze(Object.values(SOURCE_TYPES));

// --- Ingestion Lifecycle States ---
const INGESTION_STATUS = Object.freeze({
  PENDING: 'pending',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
});

const VALID_INGESTION_STATUSES = Object.freeze(Object.values(INGESTION_STATUS));

// --- Artifact Support Levels per master.txt Appendix G.4 ---
const SUPPORT_LEVELS = Object.freeze({
  FULL: 'full',
  PARTIAL: 'partial',
  METADATA: 'metadata',
  IGNORED: 'ignored',
  UNSUPPORTED: 'unsupported',
});

const VALID_SUPPORT_LEVELS = Object.freeze(Object.values(SUPPORT_LEVELS));

// --- Artifact Categories per master.txt Appendix G.3 ---
const ARTIFACT_CATEGORIES = Object.freeze({
  SOURCE_CODE: 'source_code',
  MARKUP_UI: 'markup_ui',
  CONFIGURATION: 'configuration',
  DOCUMENTATION: 'documentation',
  IMAGES: 'images',
  ARCHITECTURE_ASSETS: 'architecture_assets',
  INFRASTRUCTURE: 'infrastructure',
  DATABASE_ARTIFACTS: 'database_artifacts',
  DEPENDENCY_METADATA: 'dependency_metadata',
  TESTS: 'tests',
  GENERATED_ARTIFACTS: 'generated_artifacts',
  BINARY_ARTIFACTS: 'binary_artifacts',
  DATA_FILES: 'data_files',
  ENVIRONMENT_SECRETS: 'environment_secrets',
  BUILD_CACHE_ARTIFACTS: 'build_cache_artifacts',
  UNKNOWN_UNSUPPORTED: 'unknown_unsupported',
});

const VALID_ARTIFACT_CATEGORIES = Object.freeze(Object.values(ARTIFACT_CATEGORIES));

/**
 * Normalizes input source type string or legacy aliases to canonical SourceType.
 * Supported legacy aliases:
 * - 'zip' -> 'archive'
 * - 'directory', 'dir', 'local' -> 'server_path'
 *
 * @param {string} sourceType
 * @returns {string} Canonical SourceType
 * @throws {Error} If unsupported or invalid type
 */
function normalizeSourceType(sourceType) {
  if (typeof sourceType !== 'string') {
    const err = new Error(`Expected source_type string, got ${typeof sourceType}.`);
    err.code = 'invalid_source_type';
    err.status = 422;
    throw err;
  }

  const val = sourceType.trim().toLowerCase();
  const mapping = {
    github: SOURCE_TYPES.GITHUB,
    archive: SOURCE_TYPES.ARCHIVE,
    zip: SOURCE_TYPES.ARCHIVE,
    server_path: SOURCE_TYPES.SERVER_PATH,
    directory: SOURCE_TYPES.SERVER_PATH,
    dir: SOURCE_TYPES.SERVER_PATH,
    local: SOURCE_TYPES.SERVER_PATH,
  };

  if (!mapping[val]) {
    const err = new Error(
      `Unsupported repository source type '${sourceType}'. Supported source types: github, archive, server_path.`
    );
    err.code = 'invalid_source_type';
    err.status = 422;
    throw err;
  }

  return mapping[val];
}

module.exports = {
  MAX_REPOSITORY_SIZE_BYTES,
  MAX_EXTRACTED_SIZE_BYTES,
  MAX_INDIVIDUAL_FILE_SIZE_BYTES,
  MAX_REPOSITORY_FILE_COUNT,
  MAX_DIRECTORY_DEPTH,
  MAX_PATH_LENGTH,
  MAX_ARCHIVE_NESTING_DEPTH,
  MAX_COMPRESSION_RATIO,
  DEFAULT_STALE_INGESTION_TIMEOUT_MS,
  SOURCE_TYPES,
  VALID_SOURCE_TYPES,
  INGESTION_STATUS,
  VALID_INGESTION_STATUSES,
  SUPPORT_LEVELS,
  VALID_SUPPORT_LEVELS,
  ARTIFACT_CATEGORIES,
  VALID_ARTIFACT_CATEGORIES,
  normalizeSourceType,
};
