const fs = require('fs');
const path = require('path');
const os = require('os');
const {
  GitHubAcquisitionHandler,
  parseGitHubUrl,
  validateGitHubRef,
} = require('../../src/services/acquisition/githubHandler');

const {
  InvalidGitHubUrlError,
  InvalidGitHubRefError,
  GitHubRepositoryNotFoundError,
  GitHubRateLimitExceededError,
  GitHubTimeoutError,
} = require('../../src/errors/ingestionErrors');

const { createTestTar } = require('../helpers/archiveHelper');

describe('GitHubAcquisitionHandler', () => {
  let tempWorkDir;

  beforeEach(async () => {
    tempWorkDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'github-test-'));
  });

  afterEach(async () => {
    await fs.promises.rm(tempWorkDir, { recursive: true, force: true });
  });

  describe('parseGitHubUrl', () => {
    test('accepts valid public GitHub repository URLs', () => {
      const parsed1 = parseGitHubUrl('https://github.com/torvalds/linux');
      expect(parsed1.canonicalUrl).toBe('https://github.com/torvalds/linux');
      expect(parsed1.owner).toBe('torvalds');
      expect(parsed1.repo).toBe('linux');

      const parsed2 = parseGitHubUrl('https://github.com/facebook/react.git');
      expect(parsed2.canonicalUrl).toBe('https://github.com/facebook/react');
      expect(parsed2.owner).toBe('facebook');
      expect(parsed2.repo).toBe('react');
    });

    test('rejects non-HTTPS schemes', () => {
      expect(() => parseGitHubUrl('http://github.com/owner/repo')).toThrow(
        InvalidGitHubUrlError
      );
      expect(() => parseGitHubUrl('git://github.com/owner/repo')).toThrow(
        InvalidGitHubUrlError
      );
      expect(() => parseGitHubUrl('ssh://git@github.com/owner/repo')).toThrow(
        InvalidGitHubUrlError
      );
    });

    test('rejects non-GitHub domains', () => {
      expect(() => parseGitHubUrl('https://gitlab.com/owner/repo')).toThrow(
        InvalidGitHubUrlError
      );
      expect(() => parseGitHubUrl('https://evil.com/owner/repo')).toThrow(
        InvalidGitHubUrlError
      );
      expect(() => parseGitHubUrl('https://192.168.1.1/owner/repo')).toThrow(
        InvalidGitHubUrlError
      );
    });

    test('rejects URLs with embedded credentials', () => {
      expect(() =>
        parseGitHubUrl('https://user:token@github.com/owner/repo')
      ).toThrow(InvalidGitHubUrlError);
    });

    test('rejects URLs with query parameters or fragments', () => {
      expect(() =>
        parseGitHubUrl('https://github.com/owner/repo?token=secret')
      ).toThrow(InvalidGitHubUrlError);
      expect(() => parseGitHubUrl('https://github.com/owner/repo#section')).toThrow(
        InvalidGitHubUrlError
      );
    });

    test('rejects malformed paths and path traversal', () => {
      expect(() => parseGitHubUrl('https://github.com/owner/..')).toThrow(
        InvalidGitHubUrlError
      );
      expect(() => parseGitHubUrl('https://github.com/owner')).toThrow(
        InvalidGitHubUrlError
      );
      expect(() => parseGitHubUrl('https://github.com//repo')).toThrow(
        InvalidGitHubUrlError
      );
    });
  });

  describe('validateGitHubRef', () => {
    test('accepts clean branch, tag, and commit identifiers', () => {
      expect(validateGitHubRef('main')).toBe('main');
      expect(validateGitHubRef('v1.0.0')).toBe('v1.0.0');
      expect(validateGitHubRef('release/v2.1')).toBe('release/v2.1');
      expect(validateGitHubRef('4b825dc642cb6eb9a060e54bf8d69288fbee4904')).toBe(
        '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
      );
    });

    test('rejects path traversal and prohibited metacharacters', () => {
      expect(() => validateGitHubRef('../escape')).toThrow(InvalidGitHubRefError);
      expect(() => validateGitHubRef('main^1')).toThrow(InvalidGitHubRefError);
      expect(() => validateGitHubRef('main~2')).toThrow(InvalidGitHubRefError);
      expect(() => validateGitHubRef('tag:1')).toThrow(InvalidGitHubRefError);
      expect(() => validateGitHubRef('branch with space')).toThrow(
        InvalidGitHubRefError
      );
      expect(() => validateGitHubRef('ref.lock')).toThrow(InvalidGitHubRefError);
      expect(() => validateGitHubRef('main@{1}')).toThrow(InvalidGitHubRefError);
    });
  });

  describe('acquire', () => {
    test('successfully acquires repository using mock fetchClient', async () => {
      // Create a valid tar.gz file to serve as mock response
      const tarPath = path.join(tempWorkDir, 'mock_repo.tar.gz');
      await createTestTar(
        tarPath,
        {
          'repo-root/index.js': "console.log('from github');",
          'repo-root/README.md': '# Hello GitHub',
        },
        { gzip: true }
      );
      const tarBytes = await fs.promises.readFile(tarPath);

      const mockFetch = async () => ({
        status: 200,
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(tarBytes);
            controller.close();
          },
        }),
      });

      const handler = new GitHubAcquisitionHandler({
        fetchClient: mockFetch,
        timeoutSeconds: 5,
      });

      expect(handler.canHandle('github')).toBe(true);
      expect(handler.canHandle('archive')).toBe(false);

      const tempRoot = path.join(tempWorkDir, 'gh_sandbox');
      const result = await handler.acquire(
        'https://github.com/my-org/my-repo@v1.0.0',
        null,
        tempRoot
      );

      expect(result.revisionIdentifier).toBe('v1.0.0');
      expect(result.sourceHash).toHaveLength(64);
      expect(
        fs.existsSync(path.join(result.rootPath, 'index.js'))
      ).toBe(true);

      await result.cleanup();
      expect(fs.existsSync(tempRoot)).toBe(false);
    });

    test('unifies 401, 403, and 404 to avoid leaking private repository existence', async () => {
      for (const status of [401, 403, 404]) {
        const mockFetch = async () => ({
          status,
          body: new ReadableStream({
            start(controller) {
              controller.close();
            },
          }),
        });

        const handler = new GitHubAcquisitionHandler({ fetchClient: mockFetch });
        const tempRoot = path.join(tempWorkDir, `gh_sandbox_${status}`);

        await expect(
          handler.acquire('https://github.com/private/repo', null, tempRoot)
        ).rejects.toThrow(GitHubRepositoryNotFoundError);
      }
    });

    test('maps 429 to GitHubRateLimitExceededError', async () => {
      const mockFetch = async () => ({
        status: 429,
        body: new ReadableStream({
          start(controller) {
            controller.close();
          },
        }),
      });

      const handler = new GitHubAcquisitionHandler({ fetchClient: mockFetch });
      const tempRoot = path.join(tempWorkDir, 'gh_sandbox_429');

      await expect(
        handler.acquire('https://github.com/busy/repo', null, tempRoot)
      ).rejects.toThrow(GitHubRateLimitExceededError);
    });

    test('maps timeout to GitHubTimeoutError', async () => {
      const mockFetch = async () => {
        const err = new Error('The operation was aborted');
        err.name = 'AbortError';
        throw err;
      };

      const handler = new GitHubAcquisitionHandler({ fetchClient: mockFetch });
      const tempRoot = path.join(tempWorkDir, 'gh_sandbox_timeout');

      await expect(
        handler.acquire('https://github.com/slow/repo', null, tempRoot)
      ).rejects.toThrow(GitHubTimeoutError);
    });
  });
});
