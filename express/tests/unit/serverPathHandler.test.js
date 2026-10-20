const fs = require('fs');
const path = require('path');
const os = require('os');
const ServerPathAcquisitionHandler = require('../../src/services/acquisition/serverPathHandler');
const {
  ServerPathNotAllowedError,
  ServerPathNotFoundError,
  UnsupportedArchiveFormatError,
  SourceValidationError,
} = require('../../src/errors/ingestionErrors');
const { createTestZip } = require('../helpers/archiveHelper');

describe('ServerPathAcquisitionHandler', () => {
  let tempRoot;
  let allowedStaging;
  let outsideDir;
  let handler;

  beforeEach(async () => {
    tempRoot = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'serverpath-test-'));
    allowedStaging = path.join(tempRoot, 'allowed_staging');
    outsideDir = path.join(tempRoot, 'forbidden_outside');

    await fs.promises.mkdir(allowedStaging, { recursive: true });
    await fs.promises.mkdir(outsideDir, { recursive: true });

    handler = new ServerPathAcquisitionHandler([allowedStaging]);
  });

  afterEach(async () => {
    await fs.promises.rm(tempRoot, { recursive: true, force: true });
  });

  test('canHandle recognizes server_path and legacy aliases', () => {
    expect(handler.canHandle('server_path')).toBe(true);
    expect(handler.canHandle('directory')).toBe(true);
    expect(handler.canHandle('dir')).toBe(true);
    expect(handler.canHandle('local')).toBe(true);
    expect(handler.canHandle('github')).toBe(false);
  });

  test('rejects server path outside allowed roots with ServerPathNotAllowedError', async () => {
    const unallowedFile = path.join(outsideDir, 'repo.zip');
    createTestZip(unallowedFile, { 'file.txt': 'hello' });

    const tempWork = path.join(tempRoot, 'work');
    await expect(
      handler.acquire(unallowedFile, null, tempWork)
    ).rejects.toThrow(ServerPathNotAllowedError);
  });

  test('rejects non-existent server path with ServerPathNotFoundError', async () => {
    const nonExistent = path.join(allowedStaging, 'missing.zip');
    const tempWork = path.join(tempRoot, 'work');

    await expect(
      handler.acquire(nonExistent, null, tempWork)
    ).rejects.toThrow(ServerPathNotFoundError);
  });

  test('rejects unsupported archive format with UnsupportedArchiveFormatError', async () => {
    const badFile = path.join(allowedStaging, 'repo.txt');
    await fs.promises.writeFile(badFile, 'not an archive');

    const tempWork = path.join(tempRoot, 'work');
    await expect(
      handler.acquire(badFile, null, tempWork)
    ).rejects.toThrow(UnsupportedArchiveFormatError);
  });

  test('acquires supported zip archive within allowed root', async () => {
    const zipPath = path.join(allowedStaging, 'valid.zip');
    createTestZip(zipPath, {
      'src/app.js': 'console.log("local");',
    });

    const tempWork = path.join(tempRoot, 'work');
    const result = await handler.acquire(zipPath, 'custom-rev', tempWork);

    expect(result.revisionIdentifier).toBe('custom-rev');
    expect(result.sourceHash).toHaveLength(64);
    expect(fs.existsSync(path.join(result.rootPath, 'src', 'app.js'))).toBe(true);

    if (result.cleanup) {
      await result.cleanup();
    }
  });

  test('acquires staged directory in-place and preserves directory on cleanup', async () => {
    const stagedRepo = path.join(allowedStaging, 'my_staged_repo');
    await fs.promises.mkdir(path.join(stagedRepo, 'lib'), { recursive: true });
    await fs.promises.writeFile(
      path.join(stagedRepo, 'lib', 'math.js'),
      'export const add = (a, b) => a + b;'
    );
    await fs.promises.writeFile(
      path.join(stagedRepo, 'package.json'),
      '{"name":"staged"}'
    );

    const tempWork = path.join(tempRoot, 'work');
    const result = await handler.acquire(stagedRepo, null, tempWork);

    expect(result.rootPath).toBe(stagedRepo);
    expect(result.sourceHash).toHaveLength(64);
    expect(result.totalSourceBytes).toBeGreaterThan(0);
    expect(result.cleanup).toBeNull(); // Must be null to avoid deleting server directory

    // Directory still exists
    expect(fs.existsSync(stagedRepo)).toBe(true);
  });
});
