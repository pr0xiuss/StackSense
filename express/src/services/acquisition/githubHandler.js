const fs = require('fs');
const path = require('path');
const { pipeline } = require('stream/promises');
const { Readable } = require('stream');
const storageConfig = require('../../config/storageConfig');
const { MAX_REPOSITORY_SIZE_BYTES } = require('../../constants/ingestionConstants');
const { ArchiveExtractor } = require('./archiveExtractor');

const {
  InvalidGitHubUrlError,
  InvalidGitHubRefError,
  GitHubRepositoryNotFoundError,
  GitHubRateLimitExceededError,
  GitHubAcquisitionError,
  GitHubNetworkError,
  GitHubTimeoutError,
  SourceValidationError,
} = require('../../errors/ingestionErrors');

const GITHUB_PATH_PATTERN =
  /^\/(?<owner>[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38})\/(?<repo>[a-zA-Z0-9_.-]{1,100}?)(?:\.git)?\/?$/;

const PROHIBITED_REF_CHARS = new Set("~^:?*[\\];&|<>$`\"'!()`{}".split(''));

/**
 * Validate and parse public GitHub repository URL.
 *
 * @param {string} url
 * @returns {{ canonicalUrl: string, owner: string, repo: string }}
 */
function parseGitHubUrl(url) {
  if (typeof url !== 'string' || !url.trim()) {
    throw new InvalidGitHubUrlError('GitHub repository URL must not be empty.');
  }

  const cleanUrl = url.trim();
  let parsed;
  try {
    parsed = new URL(cleanUrl);
  } catch (err) {
    throw new InvalidGitHubUrlError(`Malformed URL: ${err.message}`);
  }

  if (parsed.protocol.toLowerCase() !== 'https:') {
    throw new InvalidGitHubUrlError(
      `GitHub repository URL must use HTTPS scheme, got '${parsed.protocol.replace(':', '')}'.`
    );
  }

  if (parsed.username || parsed.password) {
    throw new InvalidGitHubUrlError(
      'GitHub repository URL must not contain embedded credentials.'
    );
  }

  const hostname = (parsed.hostname || '').toLowerCase();
  if (hostname !== 'github.com' && hostname !== 'www.github.com') {
    throw new InvalidGitHubUrlError(
      `Only public github.com repositories are supported. Host '${hostname}' is not allowed.`
    );
  }

  if (parsed.port && parsed.port !== '443') {
    throw new InvalidGitHubUrlError('Invalid port in GitHub repository URL.');
  }

  if (parsed.search || parsed.hash) {
    throw new InvalidGitHubUrlError(
      'GitHub repository URL must not contain query parameters or fragments.'
    );
  }

  const match = GITHUB_PATH_PATTERN.exec(parsed.pathname);
  if (!match || !match.groups) {
    throw new InvalidGitHubUrlError(
      `Invalid GitHub repository path: '${parsed.pathname}'. Expected format: 'https://github.com/<owner>/<repo>'.`
    );
  }

  const { owner, repo } = match.groups;
  if (repo === '.' || repo === '..' || repo.endsWith('.')) {
    throw new InvalidGitHubUrlError(`Invalid repository name: '${repo}'.`);
  }

  return {
    canonicalUrl: `https://github.com/${owner}/${repo}`,
    owner,
    repo,
  };
}

/**
 * Validate and normalize a Git reference (branch, tag, or commit hash).
 *
 * @param {string|null} ref
 * @returns {string|null}
 */
function validateGitHubRef(ref) {
  if (!ref) return null;

  const cleanRef = ref.trim();
  if (!cleanRef) return null;

  if (cleanRef.length > 255) {
    throw new InvalidGitHubRefError(
      `GitHub ref exceeds maximum 255 characters (length: ${cleanRef.length}).`
    );
  }

  if (cleanRef.includes('..')) {
    throw new InvalidGitHubRefError(
      `Path traversal ('..') is not permitted in Git ref: '${cleanRef}'.`
    );
  }

  for (let i = 0; i < cleanRef.length; i++) {
    const code = cleanRef.charCodeAt(i);
    if (code < 32 || code === 127) {
      throw new InvalidGitHubRefError(
        `Control characters are not permitted in Git ref: '${cleanRef}'.`
      );
    }
    const ch = cleanRef[i];
    if (/\s/.test(ch)) {
      throw new InvalidGitHubRefError(
        `Whitespace characters are not permitted in Git ref: '${cleanRef}'.`
      );
    }
    if (PROHIBITED_REF_CHARS.has(ch)) {
      throw new InvalidGitHubRefError(
        `Prohibited character '${ch}' detected in Git ref: '${cleanRef}'.`
      );
    }
  }

  if (cleanRef.startsWith('/') || cleanRef.endsWith('/')) {
    throw new InvalidGitHubRefError(
      `Git ref cannot start or end with a slash: '${cleanRef}'.`
    );
  }

  if (cleanRef.startsWith('.') || cleanRef.endsWith('.')) {
    throw new InvalidGitHubRefError(
      `Git ref cannot start or end with a dot: '${cleanRef}'.`
    );
  }

  if (cleanRef.includes('//')) {
    throw new InvalidGitHubRefError(
      `Git ref cannot contain consecutive slashes: '${cleanRef}'.`
    );
  }

  if (cleanRef.endsWith('.lock')) {
    throw new InvalidGitHubRefError(`Git ref cannot end with '.lock': '${cleanRef}'.`);
  }

  if (cleanRef.includes('@{')) {
    throw new InvalidGitHubRefError(`Git ref cannot contain '@{': '${cleanRef}'.`);
  }

  return cleanRef;
}

class GitHubAcquisitionHandler {
  /**
   * @param {object} [options]
   * @param {number} [options.timeoutSeconds]
   * @param {string} [options.userAgent]
   * @param {typeof fetch} [options.fetchClient]
   */
  constructor({ timeoutSeconds, userAgent, fetchClient } = {}) {
    this._timeoutSeconds = timeoutSeconds || storageConfig.githubTimeoutSeconds;
    this._userAgent = userAgent || storageConfig.githubUserAgent;
    this._fetchClient = fetchClient || global.fetch;
  }

  /**
   * @param {string} sourceType
   * @returns {boolean}
   */
  canHandle(sourceType) {
    if (typeof sourceType !== 'string') return false;
    return sourceType.toLowerCase() === 'github';
  }

  /**
   * Acquire public GitHub repository tarball.
   *
   * @param {string} sourceReference E.g. "https://github.com/owner/repo@v1.0"
   * @param {string|null} revisionIdentifier
   * @param {string} tempRoot
   * @returns {Promise<import('./archiveHandler').AcquisitionResult>}
   */
  async acquire(sourceReference, revisionIdentifier, tempRoot) {
    let rawUrl = sourceReference;
    let refPart = null;

    if (sourceReference.includes('@')) {
      const idx = sourceReference.indexOf('@');
      rawUrl = sourceReference.slice(0, idx);
      refPart = sourceReference.slice(idx + 1);
    }

    const { owner, repo } = parseGitHubUrl(rawUrl);
    const validatedRef = validateGitHubRef(refPart);
    const targetRef = validatedRef || 'HEAD';
    const encodedRef = encodeURIComponent(targetRef);

    const codeloadUrl = `https://codeload.github.com/${owner}/${repo}/tar.gz/${encodedRef}`;
    await fs.promises.mkdir(tempRoot, { recursive: true });
    const downloadPath = path.join(tempRoot, `github_${owner}_${repo}.tar.gz`);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this._timeoutSeconds * 1000);

    try {
      let response;
      try {
        response = await this._fetchClient(codeloadUrl, {
          headers: { 'User-Agent': this._userAgent },
          signal: controller.signal,
          redirect: 'follow',
        });
      } catch (err) {
        if (err.name === 'AbortError') {
          throw new GitHubTimeoutError(
            `GitHub repository download timed out after ${this._timeoutSeconds} seconds.`
          );
        }
        throw new GitHubNetworkError(`GitHub acquisition network failure: ${err.message}`);
      }

      // Unify 401, 403, and 404 to avoid leaking private repository existence
      if ([401, 403, 404].includes(response.status)) {
        throw new GitHubRepositoryNotFoundError('Repository not found or access denied.');
      }
      if (response.status === 429) {
        throw new GitHubRateLimitExceededError('Repository not found or access denied.');
      }
      if (response.status >= 400) {
        throw new GitHubAcquisitionError(
          `GitHub acquisition failed with HTTP status ${response.status}.`
        );
      }

      // Stream response body to disk, enforcing size limit
      const nodeStream = Readable.fromWeb(response.body);
      let totalDownloaded = 0;

      const sizeCheckTransform = async function* (source) {
        for await (const chunk of source) {
          totalDownloaded += chunk.length;
          if (totalDownloaded > MAX_REPOSITORY_SIZE_BYTES) {
            throw new SourceValidationError(
              `Downloaded repository archive exceeds limit of ${MAX_REPOSITORY_SIZE_BYTES} bytes.`
            );
          }
          yield chunk;
        }
      };

      const writeStream = fs.createWriteStream(downloadPath);
      await pipeline(nodeStream, sizeCheckTransform, writeStream);
    } finally {
      clearTimeout(timeoutId);
    }

    const destDir = path.join(tempRoot, 'extracted');
    const extracted = await ArchiveExtractor.extract(downloadPath, destDir, {
      unwrapSingleRoot: true,
    });

    const resolvedRev =
      revisionIdentifier || validatedRef || extracted.sourceHash.slice(0, 12);

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

module.exports = {
  GitHubAcquisitionHandler,
  parseGitHubUrl,
  validateGitHubRef,
};
