const crypto = require('crypto');
const Repository = require('../../src/models/Repository');
const RepositoryRevision = require('../../src/models/RepositoryRevision');
const RepositoryArtifact = require('../../src/models/RepositoryArtifact');
const {
  ARTIFACT_CATEGORIES,
  SUPPORT_LEVELS,
} = require('../../src/constants/ingestionConstants');

describe('RepositoryRevision and RepositoryArtifact Models', () => {
  const projectId = crypto.randomUUID();
  let repository;

  beforeEach(async () => {
    await Repository.createIndexes();
    await RepositoryRevision.createIndexes();
    await RepositoryArtifact.createIndexes();
    repository = await Repository.create({
      project_id: projectId,
      name: 'model-test-repo',
    });
  });

  describe('RepositoryRevision', () => {
    test('creates valid revision document and transforms _id to id', async () => {
      const revision = await RepositoryRevision.create({
        project_id: projectId,
        repository_id: repository.id,
        revision_identifier: 'v1.0.0',
        source_hash: 'a'.repeat(64),
        total_files: 42,
        total_bytes: 10240,
      });

      const json = revision.toJSON();
      expect(json.id).toBeDefined();
      expect(json._id).toBeUndefined();
      expect(revision.revision_identifier).toBe('v1.0.0');
      expect(revision.total_files).toBe(42);
      expect(revision.total_bytes).toBe(10240);
    });

    test('enforces compound unique index on (repository_id, revision_identifier)', async () => {
      await RepositoryRevision.create({
        project_id: projectId,
        repository_id: repository.id,
        revision_identifier: 'v1.0.0',
        source_hash: 'a'.repeat(64),
        total_files: 10,
        total_bytes: 1000,
      });

      await expect(
        RepositoryRevision.create({
          project_id: projectId,
          repository_id: repository.id,
          revision_identifier: 'v1.0.0', // duplicate
          source_hash: 'b'.repeat(64),
          total_files: 20,
          total_bytes: 2000,
        })
      ).rejects.toThrow();
    });

    test('allows same revision_identifier across different repositories', async () => {
      const otherRepo = await Repository.create({
        project_id: projectId,
        name: 'other-repo',
      });

      const rev1 = await RepositoryRevision.create({
        project_id: projectId,
        repository_id: repository.id,
        revision_identifier: 'main',
        source_hash: '1'.repeat(64),
        total_files: 5,
        total_bytes: 500,
      });

      const rev2 = await RepositoryRevision.create({
        project_id: projectId,
        repository_id: otherRepo.id,
        revision_identifier: 'main', // same identifier, different repo
        source_hash: '2'.repeat(64),
        total_files: 8,
        total_bytes: 800,
      });

      expect(rev1.id).toBeDefined();
      expect(rev2.id).toBeDefined();
    });
  });

  describe('RepositoryArtifact', () => {
    let revision;

    beforeEach(async () => {
      revision = await RepositoryRevision.create({
        project_id: projectId,
        repository_id: repository.id,
        revision_identifier: 'v1.0.0',
        source_hash: 'a'.repeat(64),
        total_files: 1,
        total_bytes: 100,
      });
    });

    test('creates valid artifact document and transforms _id to id', async () => {
      const artifact = await RepositoryArtifact.create({
        project_id: projectId,
        repository_id: repository.id,
        revision_id: revision.id,
        path: 'src/index.js',
        size_bytes: 120,
        content_hash: 'f'.repeat(64),
        category: ARTIFACT_CATEGORIES.SOURCE_CODE,
        support_level: SUPPORT_LEVELS.FULL,
        storage_key: 'content/ff/ffff',
      });

      const json = artifact.toJSON();
      expect(json.id).toBeDefined();
      expect(json._id).toBeUndefined();
      expect(artifact.path).toBe('src/index.js');
      expect(artifact.category).toBe(ARTIFACT_CATEGORIES.SOURCE_CODE);
      expect(artifact.support_level).toBe(SUPPORT_LEVELS.FULL);
    });

    test('enforces compound unique index on (revision_id, path)', async () => {
      await RepositoryArtifact.create({
        project_id: projectId,
        repository_id: repository.id,
        revision_id: revision.id,
        path: 'src/dup.js',
        size_bytes: 100,
        content_hash: '1'.repeat(64),
        category: ARTIFACT_CATEGORIES.SOURCE_CODE,
        support_level: SUPPORT_LEVELS.FULL,
        storage_key: 'key1',
      });

      await expect(
        RepositoryArtifact.create({
          project_id: projectId,
          repository_id: repository.id,
          revision_id: revision.id,
          path: 'src/dup.js', // duplicate in same revision
          size_bytes: 200,
          content_hash: '2'.repeat(64),
          category: ARTIFACT_CATEGORIES.SOURCE_CODE,
          support_level: SUPPORT_LEVELS.FULL,
          storage_key: 'key2',
        })
      ).rejects.toThrow();
    });

    test('rejects invalid category and support_level enums', async () => {
      await expect(
        RepositoryArtifact.create({
          project_id: projectId,
          repository_id: repository.id,
          revision_id: revision.id,
          path: 'test.txt',
          size_bytes: 10,
          content_hash: '3'.repeat(64),
          category: 'invalid_category_xyz',
          support_level: SUPPORT_LEVELS.FULL,
          storage_key: 'key',
        })
      ).rejects.toThrow();

      await expect(
        RepositoryArtifact.create({
          project_id: projectId,
          repository_id: repository.id,
          revision_id: revision.id,
          path: 'test.txt',
          size_bytes: 10,
          content_hash: '3'.repeat(64),
          category: ARTIFACT_CATEGORIES.SOURCE_CODE,
          support_level: 'invalid_level_xyz',
          storage_key: 'key',
        })
      ).rejects.toThrow();
    });

    test('cascade delete: deleting repository deletes revisions and artifacts', async () => {
      await RepositoryArtifact.create({
        project_id: projectId,
        repository_id: repository.id,
        revision_id: revision.id,
        path: 'cascade.js',
        size_bytes: 50,
        content_hash: '4'.repeat(64),
        category: ARTIFACT_CATEGORIES.SOURCE_CODE,
        support_level: SUPPORT_LEVELS.FULL,
        storage_key: 'key',
      });

      expect(await RepositoryRevision.countDocuments({ repository_id: repository.id })).toBe(1);
      expect(await RepositoryArtifact.countDocuments({ repository_id: repository.id })).toBe(1);

      await Repository.findOneAndDelete({ _id: repository.id });

      expect(await RepositoryRevision.countDocuments({ repository_id: repository.id })).toBe(0);
      expect(await RepositoryArtifact.countDocuments({ repository_id: repository.id })).toBe(0);
    });
  });
});
