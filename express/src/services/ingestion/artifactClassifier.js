const path = require('path');
const {
  MAX_INDIVIDUAL_FILE_SIZE_BYTES,
  ARTIFACT_CATEGORIES,
  SUPPORT_LEVELS,
} = require('../../constants/ingestionConstants');

const BUILD_CACHE_DIRS = new Set([
  'node_modules',
  'vendor',
  '.git',
  '.svn',
  '.hg',
  '__pycache__',
  '.pytest_cache',
  '.venv',
  'venv',
  'dist',
  'build',
  'target',
  '.next',
  '.nuxt',
  '.gradle',
  '.idea',
  '.vscode',
]);

const DEPENDENCY_LOCK_FILES = new Set([
  'package-lock.json',
  'yarn.lock',
  'pnpm-lock.yaml',
  'poetry.lock',
  'cargo.lock',
  'go.sum',
  'requirements.txt',
]);

const CONFIG_FILES = new Set([
  'dockerfile',
  'compose.yml',
  'compose.yaml',
  'docker-compose.yml',
  'package.json',
  'tsconfig.json',
  'pyproject.toml',
  'cargo.toml',
  'pom.xml',
  'build.gradle',
]);

const SOURCE_EXTENSIONS = new Set([
  '.py',
  '.ts',
  '.tsx',
  '.js',
  '.jsx',
  '.java',
  '.kt',
  '.scala',
  '.go',
  '.rs',
  '.c',
  '.cpp',
  '.cc',
  '.h',
  '.hpp',
  '.cs',
  '.rb',
  '.php',
  '.swift',
]);

const MARKUP_EXTENSIONS = new Set([
  '.html',
  '.htm',
  '.css',
  '.scss',
  '.sass',
  '.less',
  '.vue',
  '.svelte',
]);

const CONFIG_EXTENSIONS = new Set([
  '.yaml',
  '.yml',
  '.json',
  '.toml',
  '.ini',
  '.cfg',
  '.xml',
]);

const DOC_EXTENSIONS = new Set([
  '.md',
  '.markdown',
  '.rst',
  '.txt',
  '.adoc',
]);

const IMAGE_EXTENSIONS = new Set([
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.svg',
  '.ico',
  '.webp',
  '.bmp',
  '.tiff',
]);

const ARCH_EXTENSIONS = new Set([
  '.drawio',
  '.puml',
  '.plantuml',
  '.mermaid',
]);

const INFRA_EXTENSIONS = new Set(['.tf', '.tfvars']);

const DB_EXTENSIONS = new Set(['.sql', '.prisma']);

const BINARY_EXTENSIONS = new Set([
  '.exe',
  '.dll',
  '.so',
  '.dylib',
  '.class',
  '.pyc',
  '.o',
  '.bin',
  '.wasm',
]);

const DATA_EXTENSIONS = new Set([
  '.csv',
  '.tsv',
  '.parquet',
  '.arrow',
]);

class ArtifactClassifier {
  /**
   * Classify a repository file by path and byte size.
   *
   * @param {string} relativePath Forward-slash relative path
   * @param {number} sizeBytes
   * @returns {{ category: string, supportLevel: string }}
   */
  classify(relativePath, sizeBytes) {
    const cleanPath = relativePath.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
    const filename = path.posix.basename(cleanPath).toLowerCase();
    const parts = cleanPath.toLowerCase().split('/');
    const ext = path.posix.extname(cleanPath).toLowerCase();

    // 1. Build cache and ignored directories
    if (parts.some((p) => BUILD_CACHE_DIRS.has(p))) {
      return {
        category: ARTIFACT_CATEGORIES.BUILD_CACHE_ARTIFACTS,
        supportLevel: SUPPORT_LEVELS.IGNORED,
      };
    }

    // 2. Minified / generated artifacts
    if (
      filename.endsWith('.min.js') ||
      filename.endsWith('.min.css') ||
      filename.endsWith('.map')
    ) {
      return {
        category: ARTIFACT_CATEGORIES.GENERATED_ARTIFACTS,
        supportLevel: SUPPORT_LEVELS.IGNORED,
      };
    }

    // 3. Environment & secrets
    if (
      filename === '.env' ||
      filename.startsWith('.env.') ||
      ext === '.pem' ||
      ext === '.key' ||
      ext === '.pfx' ||
      filename.startsWith('id_rsa') ||
      filename.startsWith('secrets.')
    ) {
      return {
        category: ARTIFACT_CATEGORIES.ENVIRONMENT_SECRETS,
        supportLevel: SUPPORT_LEVELS.METADATA,
      };
    }

    // 4. Dependency metadata
    if (DEPENDENCY_LOCK_FILES.has(filename)) {
      return {
        category: ARTIFACT_CATEGORIES.DEPENDENCY_METADATA,
        supportLevel: SUPPORT_LEVELS.METADATA,
      };
    }

    // 5. Architecture assets
    if (ARCH_EXTENSIONS.has(ext)) {
      return this._withSizeCheck(
        ARTIFACT_CATEGORIES.ARCHITECTURE_ASSETS,
        SUPPORT_LEVELS.FULL,
        sizeBytes
      );
    }

    // 6. Tests
    if (
      parts.some((p) => ['test', 'tests', 'spec', 'specs'].includes(p)) ||
      filename.includes('test') ||
      filename.includes('spec')
    ) {
      return this._withSizeCheck(
        ARTIFACT_CATEGORIES.TESTS,
        SUPPORT_LEVELS.FULL,
        sizeBytes
      );
    }

    // 7. Source code
    if (SOURCE_EXTENSIONS.has(ext)) {
      return this._withSizeCheck(
        ARTIFACT_CATEGORIES.SOURCE_CODE,
        SUPPORT_LEVELS.FULL,
        sizeBytes
      );
    }

    // 8. Markup & UI
    if (MARKUP_EXTENSIONS.has(ext)) {
      return this._withSizeCheck(
        ARTIFACT_CATEGORIES.MARKUP_UI,
        SUPPORT_LEVELS.FULL,
        sizeBytes
      );
    }

    // 9. Infrastructure
    if (INFRA_EXTENSIONS.has(ext) || filename === 'vagrantfile' || filename === 'chart.yaml') {
      return this._withSizeCheck(
        ARTIFACT_CATEGORIES.INFRASTRUCTURE,
        SUPPORT_LEVELS.FULL,
        sizeBytes
      );
    }

    // 10. Database artifacts
    if (DB_EXTENSIONS.has(ext)) {
      return this._withSizeCheck(
        ARTIFACT_CATEGORIES.DATABASE_ARTIFACTS,
        SUPPORT_LEVELS.FULL,
        sizeBytes
      );
    }

    // 11. Configuration
    if (CONFIG_FILES.has(filename) || CONFIG_EXTENSIONS.has(ext)) {
      return this._withSizeCheck(
        ARTIFACT_CATEGORIES.CONFIGURATION,
        SUPPORT_LEVELS.FULL,
        sizeBytes
      );
    }

    // 12. Documentation
    if (
      DOC_EXTENSIONS.has(ext) ||
      filename === 'license' ||
      filename === 'notice' ||
      filename.startsWith('changelog')
    ) {
      return this._withSizeCheck(
        ARTIFACT_CATEGORIES.DOCUMENTATION,
        SUPPORT_LEVELS.PARTIAL,
        sizeBytes
      );
    }

    // 13. Images
    if (IMAGE_EXTENSIONS.has(ext)) {
      return {
        category: ARTIFACT_CATEGORIES.IMAGES,
        supportLevel: SUPPORT_LEVELS.METADATA,
      };
    }

    // 14. Data files
    if (DATA_EXTENSIONS.has(ext)) {
      return {
        category: ARTIFACT_CATEGORIES.DATA_FILES,
        supportLevel: SUPPORT_LEVELS.METADATA,
      };
    }

    // 15. Binaries
    if (BINARY_EXTENSIONS.has(ext)) {
      return {
        category: ARTIFACT_CATEGORIES.BINARY_ARTIFACTS,
        supportLevel: SUPPORT_LEVELS.UNSUPPORTED,
      };
    }

    // 16. Fallback
    return {
      category: ARTIFACT_CATEGORIES.UNKNOWN_UNSUPPORTED,
      supportLevel: SUPPORT_LEVELS.UNSUPPORTED,
    };
  }

  /**
   * Helper that downgrades support level to UNSUPPORTED if file exceeds 5 MB.
   *
   * @param {string} category
   * @param {string} baseSupport
   * @param {number} sizeBytes
   * @returns {{ category: string, supportLevel: string }}
   */
  _withSizeCheck(category, baseSupport, sizeBytes) {
    if (sizeBytes > MAX_INDIVIDUAL_FILE_SIZE_BYTES) {
      return {
        category,
        supportLevel: SUPPORT_LEVELS.UNSUPPORTED,
      };
    }
    return {
      category,
      supportLevel: baseSupport,
    };
  }
}

module.exports = ArtifactClassifier;
