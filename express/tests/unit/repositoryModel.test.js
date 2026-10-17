const crypto = require('crypto');
const Repository = require('../../src/models/Repository');
const Ingestion = require('../../src/models/Ingestion');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe('Repository Model Unit Tests (M3 Batch 1)', () => {
  const sampleProjectId = crypto.randomUUID();

  it('creates a repository with a valid default UUID v4 identifier and registered status', async () => {
    const repository = new Repository({
      project_id: sampleProjectId,
      name: 'stacksense-core',
      description: 'Core platform repository',
    });

    await repository.save();

    expect(repository._id).toBeDefined();
    expect(repository._id).toMatch(UUID_V4_REGEX);
    expect(repository.project_id).toBe(sampleProjectId);
    expect(repository.name).toBe('stacksense-core');
    expect(repository.description).toBe('Core platform repository');
    expect(repository.status).toBe('registered');
    expect(repository.created_at).toBeInstanceOf(Date);
    expect(repository.updated_at).toBeInstanceOf(Date);
  });

  it('rejects creation when project_id is missing or invalid', async () => {
    const repoMissing = new Repository({ name: 'repo-1' });
    await expect(repoMissing.save()).rejects.toThrow(/project_id/);

    const repoInvalid = new Repository({ project_id: 'not-a-uuid', name: 'repo-2' });
    await expect(repoInvalid.save()).rejects.toThrow(/UUID/);
  });

  it('rejects creation when name is missing or empty', async () => {
    const repoMissing = new Repository({ project_id: sampleProjectId });
    await expect(repoMissing.save()).rejects.toThrow(/name/);

    const repoEmpty = new Repository({ project_id: sampleProjectId, name: '   ' });
    await expect(repoEmpty.save()).rejects.toThrow(/name/);
  });

  it('rejects name exceeding 255 characters', async () => {
    const longName = 'r'.repeat(256);
    const repository = new Repository({
      project_id: sampleProjectId,
      name: longName,
    });
    await expect(repository.save()).rejects.toThrow(/255/);
  });

  it('rejects description exceeding 2000 characters', async () => {
    const longDesc = 'd'.repeat(2001);
    const repository = new Repository({
      project_id: sampleProjectId,
      name: 'valid-repo',
      description: longDesc,
    });
    await expect(repository.save()).rejects.toThrow(/2000/);
  });

  it('trims leading and trailing whitespace from name and description', async () => {
    const repository = new Repository({
      project_id: sampleProjectId,
      name: '   trimmed-repo   ',
      description: '   trimmed description   ',
    });
    await repository.save();

    expect(repository.name).toBe('trimmed-repo');
    expect(repository.description).toBe('trimmed description');
  });

  it('enforces compound uniqueness of (project_id, name)', async () => {
    const repo1 = new Repository({
      project_id: sampleProjectId,
      name: 'unique-service',
    });
    await repo1.save();

    const repo2 = new Repository({
      project_id: sampleProjectId,
      name: 'unique-service',
    });
    await expect(repo2.save()).rejects.toThrow();

    // But identical name in different project is allowed
    const otherProjectId = crypto.randomUUID();
    const repoOther = new Repository({
      project_id: otherProjectId,
      name: 'unique-service',
    });
    await expect(repoOther.save()).resolves.toBeDefined();
  });

  it('serializes to JSON with id instead of _id and strips __v', async () => {
    const repository = new Repository({
      project_id: sampleProjectId,
      name: 'json-test-repo',
    });
    await repository.save();

    const json = repository.toJSON();
    expect(json.id).toBe(repository._id);
    expect(json._id).toBeUndefined();
    expect(json.__v).toBeUndefined();
  });

  it('cascades deletion to child Ingestion records on findOneAndDelete', async () => {
    const repository = new Repository({
      project_id: sampleProjectId,
      name: 'cascade-repo',
    });
    await repository.save();

    const ingestion = new Ingestion({
      project_id: sampleProjectId,
      repository_id: repository._id,
      source_type: 'archive',
      source_reference: 'data/test.zip',
    });
    await ingestion.save();

    await Repository.findOneAndDelete({ _id: repository._id });

    const remainingIngestion = await Ingestion.findById(ingestion._id);
    expect(remainingIngestion).toBeNull();
  });
});
