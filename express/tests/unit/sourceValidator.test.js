const fs = require('fs');
const path = require('path');
const os = require('os');
const SourceValidator = require('../../src/services/ingestion/sourceValidator');
const { SourceValidationError } = require('../../src/errors/ingestionErrors');

describe('SourceValidator Resource Limits & Bounds', () => {
  let tempRoot;

  beforeEach(async () => {
    tempRoot = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'validator-test-'));
  });

  afterEach(async () => {
    await fs.promises.rm(tempRoot, { recursive: true, force: true });
  });

  test('validates clean directory structure and computes totals', async () => {
    const srcDir = path.join(tempRoot, 'src');
    await fs.promises.mkdir(srcDir, { recursive: true });
    await fs.promises.writeFile(path.join(srcDir, 'a.js'), 'const a = 1;');
    await fs.promises.writeFile(path.join(srcDir, 'b.js'), 'const b = 2;');
    await fs.promises.writeFile(path.join(tempRoot, 'README.md'), '# Doc');

    const validator = new SourceValidator();
    const result = await validator.validate(tempRoot);

    expect(result.totalFiles).toBe(3);
    expect(result.totalBytes).toBeGreaterThan(0);
    expect(result.files).toHaveLength(3);
    expect(result.files.map((f) => f.relativePath).sort()).toEqual([
      'README.md',
      'src/a.js',
      'src/b.js',
    ]);
  });

  test('rejects non-directory target with SourceValidationError', async () => {
    const filePath = path.join(tempRoot, 'file.txt');
    await fs.promises.writeFile(filePath, 'not a dir');

    const validator = new SourceValidator();
    await expect(validator.validate(filePath)).rejects.toThrow(
      SourceValidationError
    );
  });

  test('rejects path exceeding max path length', async () => {
    const longName = 'a'.repeat(50);
    await fs.promises.writeFile(path.join(tempRoot, longName), 'test');

    const validator = new SourceValidator({ maxPathLength: 20 });
    await expect(validator.validate(tempRoot)).rejects.toThrow(
      SourceValidationError
    );
  });

  test('rejects directory tree exceeding max depth', async () => {
    const deepDir = path.join(tempRoot, 'l1', 'l2', 'l3', 'l4');
    await fs.promises.mkdir(deepDir, { recursive: true });
    await fs.promises.writeFile(path.join(deepDir, 'deep.txt'), 'deep');

    const validator = new SourceValidator({ maxDirectoryDepth: 2 });
    await expect(validator.validate(tempRoot)).rejects.toThrow(
      SourceValidationError
    );
  });

  test('rejects repository exceeding max file count', async () => {
    for (let i = 0; i < 5; i++) {
      await fs.promises.writeFile(path.join(tempRoot, `file_${i}.txt`), `f${i}`);
    }

    const validator = new SourceValidator({ maxFileCount: 3 });
    await expect(validator.validate(tempRoot)).rejects.toThrow(
      SourceValidationError
    );
  });

  test('rejects repository exceeding total extracted size bytes', async () => {
    await fs.promises.writeFile(
      path.join(tempRoot, 'big.bin'),
      Buffer.alloc(1024 * 1024)
    );

    const validator = new SourceValidator({
      maxExtractedSizeBytes: 512 * 1024,
    });
    await expect(validator.validate(tempRoot)).rejects.toThrow(
      SourceValidationError
    );
  });
});
