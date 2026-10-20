const fs = require('fs');
const path = require('path');
const os = require('os');
const { Readable } = require('stream');
const LocalStorageService = require('../../src/services/storage/localStorageService');
const { StorageOperationError } = require('../../src/errors/ingestionErrors');

describe('LocalStorageService', () => {
  let tempStorageDir;
  let storage;

  beforeEach(async () => {
    tempStorageDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'storage-test-'));
    storage = new LocalStorageService(tempStorageDir);
  });

  afterEach(async () => {
    await fs.promises.rm(tempStorageDir, { recursive: true, force: true });
  });

  test('successfully stores and retrieves binary buffer', async () => {
    const key = 'projects/p1/artifacts/file.txt';
    const content = Buffer.from('Hello StackSense Storage');

    const canonicalKey = await storage.put(key, content);
    expect(canonicalKey).toBe('projects/p1/artifacts/file.txt');

    const exists = await storage.exists(key);
    expect(exists).toBe(true);

    const stream = await storage.get(key);
    const chunks = [];
    for await (const chunk of stream) {
      chunks.push(chunk);
    }
    const retrieved = Buffer.concat(chunks);
    expect(retrieved.toString()).toBe('Hello StackSense Storage');
  });

  test('stores content from readable stream', async () => {
    const key = 'streamed/data.bin';
    const stream = Readable.from([Buffer.from('chunk1-'), Buffer.from('chunk2')]);

    await storage.put(key, stream);

    const exists = await storage.exists(key);
    expect(exists).toBe(true);

    const readStream = await storage.get(key);
    const chunks = [];
    for await (const chunk of readStream) {
      chunks.push(chunk);
    }
    expect(Buffer.concat(chunks).toString()).toBe('chunk1-chunk2');
  });

  test('blocks path traversal attacks on put, get, delete', async () => {
    const attackKeys = [
      '../escape.txt',
      '../../etc/passwd',
      '..\\windows\\system32',
      'foo/../../bar',
    ];

    for (const key of attackKeys) {
      await expect(storage.put(key, Buffer.from('bad'))).rejects.toThrow(
        StorageOperationError
      );
      await expect(storage.get(key)).rejects.toThrow(StorageOperationError);
      await expect(storage.delete(key)).rejects.toThrow(StorageOperationError);
      const exists = await storage.exists(key);
      expect(exists).toBe(false);
    }
  });

  test('blocks empty prefix deletion to prevent root wipe', async () => {
    await expect(storage.deletePrefix('')).rejects.toThrow(StorageOperationError);
    await expect(storage.deletePrefix('/')).rejects.toThrow(StorageOperationError);
    await expect(storage.deletePrefix('///')).rejects.toThrow(StorageOperationError);
  });

  test('deletes prefix cleanly for compensating cleanup', async () => {
    await storage.put('jobs/job-123/a.txt', Buffer.from('a'));
    await storage.put('jobs/job-123/b.txt', Buffer.from('b'));
    await storage.put('jobs/job-456/keep.txt', Buffer.from('keep'));

    expect(await storage.exists('jobs/job-123/a.txt')).toBe(true);
    expect(await storage.exists('jobs/job-123/b.txt')).toBe(true);

    await storage.deletePrefix('jobs/job-123');

    expect(await storage.exists('jobs/job-123/a.txt')).toBe(false);
    expect(await storage.exists('jobs/job-123/b.txt')).toBe(false);
    expect(await storage.exists('jobs/job-456/keep.txt')).toBe(true);
  });

  test('deletes single object', async () => {
    await storage.put('single.txt', Buffer.from('content'));
    expect(await storage.exists('single.txt')).toBe(true);

    await storage.delete('single.txt');
    expect(await storage.exists('single.txt')).toBe(false);
  });
});
