const fs = require('fs');
const path = require('path');
const os = require('os');
const { ArchiveExtractor } = require('../../src/services/acquisition/archiveExtractor');
const { SourceValidationError } = require('../../src/errors/ingestionErrors');
const { createTestZip, createTestTar } = require('../helpers/archiveHelper');

describe('ArchiveExtractor Security & Extraction Defenses', () => {
  let tempWorkDir;

  beforeEach(async () => {
    tempWorkDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'extractor-test-'));
  });

  afterEach(async () => {
    await fs.promises.rm(tempWorkDir, { recursive: true, force: true });
  });

  test('successfully extracts valid zip archive with single-root unwrapping', async () => {
    const zipPath = path.join(tempWorkDir, 'valid.zip');
    createTestZip(zipPath, {
      'my-repo/src/index.js': "console.log('hello');",
      'my-repo/README.md': '# Valid Repo',
    });

    const destDir = path.join(tempWorkDir, 'extracted');
    const result = await ArchiveExtractor.extract(zipPath, destDir, {
      unwrapSingleRoot: true,
    });

    expect(result.sourceHash).toHaveLength(64);
    expect(result.archiveSize).toBeGreaterThan(0);
    expect(fs.existsSync(path.join(result.rootPath, 'src', 'index.js'))).toBe(true);
    expect(fs.existsSync(path.join(result.rootPath, 'README.md'))).toBe(true);
  });

  test('successfully extracts valid tar.gz archive', async () => {
    const tarPath = path.join(tempWorkDir, 'valid.tar.gz');
    await createTestTar(
      tarPath,
      {
        'app/main.py': 'print("hello")',
        'app/config.json': '{"env":"test"}',
      },
      { gzip: true }
    );

    const destDir = path.join(tempWorkDir, 'extracted_tar');
    const result = await ArchiveExtractor.extract(tarPath, destDir, {
      unwrapSingleRoot: true,
    });

    expect(result.sourceHash).toHaveLength(64);
    expect(fs.existsSync(path.join(result.rootPath, 'main.py'))).toBe(true);
    expect(fs.existsSync(path.join(result.rootPath, 'config.json'))).toBe(true);
  });

  test('rejects non-existent archive file with SourceValidationError', async () => {
    const badPath = path.join(tempWorkDir, 'does-not-exist.zip');
    const destDir = path.join(tempWorkDir, 'extracted');

    await expect(
      ArchiveExtractor.extract(badPath, destDir)
    ).rejects.toThrow(SourceValidationError);
  });

  test('rejects directory passed as archive with SourceValidationError', async () => {
    const dirAsArchive = path.join(tempWorkDir, 'dir_source');
    await fs.promises.mkdir(dirAsArchive);
    const destDir = path.join(tempWorkDir, 'extracted');

    await expect(
      ArchiveExtractor.extract(dirAsArchive, destDir)
    ).rejects.toThrow(SourceValidationError);
  });

  test('blocks relative path traversal attacks (../) in zip members', async () => {
    const zipPath = path.join(tempWorkDir, 'traversal.zip');
    createTestZip(zipPath, {
      '../escape.txt': 'evil content',
    });

    const destDir = path.join(tempWorkDir, 'extracted');
    await expect(
      ArchiveExtractor.extract(zipPath, destDir)
    ).rejects.toThrow(SourceValidationError);
  });

  test('blocks absolute path traversal (/etc/passwd) in zip members', async () => {
    const zipPath = path.join(tempWorkDir, 'abs_traversal.zip');
    createTestZip(zipPath, {
      '/etc/passwd': 'root:x:0:0',
    });

    const destDir = path.join(tempWorkDir, 'extracted');
    await expect(
      ArchiveExtractor.extract(zipPath, destDir)
    ).rejects.toThrow(SourceValidationError);
  });

  test('blocks Windows drive-letter paths (C:evil.txt) in zip members', async () => {
    const zipPath = path.join(tempWorkDir, 'drive_traversal.zip');
    createTestZip(zipPath, {
      'C:evil.txt': 'drive escape',
    });

    const destDir = path.join(tempWorkDir, 'extracted');
    await expect(
      ArchiveExtractor.extract(zipPath, destDir)
    ).rejects.toThrow(SourceValidationError);
  });

  test('blocks Windows reserved device names (CON, PRN, AUX, NUL, COM1) in zip members', async () => {
    const reservedNames = ['CON.txt', 'PRN.dat', 'AUX', 'NUL.log', 'COM1.bin'];
    for (const name of reservedNames) {
      const zipPath = path.join(tempWorkDir, `reserved_${name}.zip`);
      createTestZip(zipPath, {
        [name]: 'device content',
      });

      const destDir = path.join(tempWorkDir, `extracted_${name}`);
      await expect(
        ArchiveExtractor.extract(zipPath, destDir)
      ).rejects.toThrow(SourceValidationError);
    }
  });

  test('blocks null byte path injection via sanitizeAndValidateMemberPath', () => {
    const { sanitizeAndValidateMemberPath } = require('../../src/services/acquisition/archiveExtractor');
    expect(() =>
      sanitizeAndValidateMemberPath('safe.txt\x00evil.txt', {
        isDir: false,
        destinationDir: tempWorkDir,
        destResolved: tempWorkDir,
      })
    ).toThrow(SourceValidationError);
  });

  test('blocks path traversal in tar archives', async () => {
    const { createRawTarWithTraversal } = require('../helpers/archiveHelper');
    const tarPath = path.join(tempWorkDir, 'traversal.tar');
    createRawTarWithTraversal(tarPath, '../escape.txt');

    const destDir = path.join(tempWorkDir, 'extracted_tar_traversal');
    await expect(
      ArchiveExtractor.extract(tarPath, destDir)
    ).rejects.toThrow(SourceValidationError);
  });
});
