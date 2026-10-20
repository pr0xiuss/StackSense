const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

const Project = require('../../src/models/Project');
const ProjectAccess = require('../../src/models/ProjectAccess');
const Repository = require('../../src/models/Repository');
const Ingestion = require('../../src/models/Ingestion');
const RepositoryRevision = require('../../src/models/RepositoryRevision');
const RepositoryArtifact = require('../../src/models/RepositoryArtifact');

const { IngestionService } = require('../../src/services/ingestion/ingestionService');
const { INGESTION_STATUS } = require('../../src/constants/ingestionConstants');
const {
  ActiveIngestionExistsError,
  IngestionNotFoundError,
  RevisionAlreadyExistsError,
  RevisionNotFoundError,
  SourceValidationError,
} = require('../../src/errors/ingestionErrors');
const {
  ProjectAccessDeniedError,
} = require('../../src/errors/accessErrors');
const { RepositoryNotFoundError } = require('../../src/errors/repositoryErrors');
const { createTestZip } = require('../helpers/archiveHelper');

describe('IngestionService Orchestration & Lifecycle', () => {
  let tempStorageRoot;
  let tempFixtureDir;
  let service;

  const ownerId = crypto.randomUUID();
  const developerId = crypto.randomUUID();
  const viewerId = crypto.randomUUID();
  const outsiderId = crypto.randomUUID();

  let project;
  let repository;

  beforeEach(async () => {
    await Project.createIndexes();
    await ProjectAccess.createIndexes();
    await Repository.createIndexes();
    await Ingestion.createIndexes();
    await RepositoryRevision.createIndexes();
    await RepositoryArtifact.createIndexes();

    tempStorageRoot = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'ingest-storage-'));
    tempFixtureDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'ingest-fixtures-'));

    const LocalStorageService = require('../../src/services/storage/localStorageService');
    const storageService = new LocalStorageService(tempStorageRoot);

    service = new IngestionService({
      storageService,
    });

    project = await Project.create({
      name: 'Ingestion Service Test Project',
    });

    await ProjectAccess.create([
      { project_id: project.id, user_id: ownerId, role: 'owner' },
      { project_id: project.id, user_id: developerId, role: 'developer' },
      { project_id: project.id, user_id: viewerId, role: 'viewer' },
    ]);

    repository = await Repository.create({
      project_id: project.id,
      name: 'service-test-repo',
    });
  });

  afterEach(async () => {
    await fs.promises.rm(tempStorageRoot, { recursive: true, force: true });
    await fs.promises.rm(tempFixtureDir, { recursive: true, force: true });
  });

  describe('triggerIngestion', () => {
    test('successfully ingests archive source, builds revision and artifacts, and completes', async () => {
      const zipPath = path.join(tempFixtureDir, 'valid.zip');
      createTestZip(zipPath, {
        'src/index.js': "console.log('hello world');",
        'src/util.py': 'def foo(): pass',
        'README.md': '# Service Test',
      });

      const ingestion = await service.triggerIngestion({
        projectId: project.id,
        repositoryId: repository.id,
        sourceType: 'archive',
        sourceReference: zipPath,
        revisionIdentifier: 'v1.0.0',
        userId: developerId,
      });

      expect(ingestion.id).toBeDefined();
      expect(ingestion.status).toBe(INGESTION_STATUS.COMPLETED);
      expect(ingestion.started_at).toBeDefined();
      expect(ingestion.completed_at).toBeDefined();
      expect(ingestion.error_code).toBeNull();

      // Check persisted revision
      const revision = await RepositoryRevision.findOne({
        repository_id: repository.id,
        revision_identifier: 'v1.0.0',
      });
      expect(revision).toBeDefined();
      expect(revision.total_files).toBe(3);
      expect(revision.total_bytes).toBeGreaterThan(0);
      expect(revision.source_hash).toHaveLength(64);

      // Check persisted artifacts
      const artifacts = await RepositoryArtifact.find({ revision_id: revision.id }).sort({
        path: 1,
      });
      expect(artifacts).toHaveLength(3);
      expect(artifacts.map((a) => a.path)).toEqual([
        'README.md',
        'src/index.js',
        'src/util.py',
      ]);
    });

    test('rejects ingestion when user has only VIEWER role (403)', async () => {
      const zipPath = path.join(tempFixtureDir, 'valid.zip');
      createTestZip(zipPath, { 'file.txt': 'test' });

      await expect(
        service.triggerIngestion({
          projectId: project.id,
          repositoryId: repository.id,
          sourceType: 'archive',
          sourceReference: zipPath,
          userId: viewerId,
        })
      ).rejects.toThrow(ProjectAccessDeniedError);
    });

    test('rejects ingestion from outsider with no project access (403)', async () => {
      const zipPath = path.join(tempFixtureDir, 'valid.zip');
      createTestZip(zipPath, { 'file.txt': 'test' });

      await expect(
        service.triggerIngestion({
          projectId: project.id,
          repositoryId: repository.id,
          sourceType: 'archive',
          sourceReference: zipPath,
          userId: outsiderId,
        })
      ).rejects.toThrow(ProjectAccessDeniedError);
    });

    test('rejects cross-project access attempt with RepositoryNotFoundError (404)', async () => {
      const otherProject = await Project.create({ name: 'Other Project' });
      await ProjectAccess.create({
        project_id: otherProject.id,
        user_id: ownerId,
        role: 'owner',
      });
      const zipPath = path.join(tempFixtureDir, 'valid.zip');
      createTestZip(zipPath, { 'file.txt': 'test' });

      await expect(
        service.triggerIngestion({
          projectId: otherProject.id, // Repository belongs to project.id, not otherProject.id
          repositoryId: repository.id,
          sourceType: 'archive',
          sourceReference: zipPath,
          userId: ownerId,
        })
      ).rejects.toThrow(RepositoryNotFoundError);
    });

    test('recovers from stale processing ingestion older than threshold (IR-M4-017)', async () => {
      const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);
      const staleIngestion = await Ingestion.create({
        project_id: project.id,
        repository_id: repository.id,
        source_type: 'archive',
        source_reference: 'data/stale.zip',
        status: INGESTION_STATUS.PROCESSING,
        started_at: twoHoursAgo,
      });

      const zipPath = path.join(tempFixtureDir, 'stale_recover.zip');
      createTestZip(zipPath, { 'main.py': 'print(1)' });

      const newIngestion = await service.triggerIngestion({
        projectId: project.id,
        repositoryId: repository.id,
        sourceType: 'archive',
        sourceReference: zipPath,
        revisionIdentifier: 'v-recover',
        userId: developerId,
      });

      expect(newIngestion.status).toBe(INGESTION_STATUS.COMPLETED);

      const updatedStale = await Ingestion.findById(staleIngestion.id);
      expect(updatedStale.status).toBe(INGESTION_STATUS.FAILED);
      expect(updatedStale.error_code).toBe('stale_job_timeout');
    });

    test('rejects source_reference exceeding 1024 characters with SourceValidationError (IR-M4-013)', async () => {
      const longRef = 'a'.repeat(1025);
      await expect(
        service.triggerIngestion({
          projectId: project.id,
          repositoryId: repository.id,
          sourceType: 'archive',
          sourceReference: longRef,
          userId: developerId,
        })
      ).rejects.toThrow(SourceValidationError);
    });

    test('rejects concurrent active ingestion with ActiveIngestionExistsError (409)', async () => {
      // Simulate an active ingestion job
      await Ingestion.create({
        project_id: project.id,
        repository_id: repository.id,
        source_type: 'archive',
        source_reference: 'data/test.zip',
        status: INGESTION_STATUS.PROCESSING,
        started_at: new Date(),
      });

      const zipPath = path.join(tempFixtureDir, 'second.zip');
      createTestZip(zipPath, { 'file.txt': 'test' });

      await expect(
        service.triggerIngestion({
          projectId: project.id,
          repositoryId: repository.id,
          sourceType: 'archive',
          sourceReference: zipPath,
          userId: developerId,
        })
      ).rejects.toThrow(ActiveIngestionExistsError);
    });

    test('rejects duplicate revision upfront if identifier already exists (409)', async () => {
      await RepositoryRevision.create({
        project_id: project.id,
        repository_id: repository.id,
        revision_identifier: 'v1.0.0',
        source_hash: 'f'.repeat(64),
        total_files: 1,
        total_bytes: 10,
      });

      const zipPath = path.join(tempFixtureDir, 'dup.zip');
      createTestZip(zipPath, { 'file.txt': 'test' });

      await expect(
        service.triggerIngestion({
          projectId: project.id,
          repositoryId: repository.id,
          sourceType: 'archive',
          sourceReference: zipPath,
          revisionIdentifier: 'v1.0.0',
          userId: developerId,
        })
      ).rejects.toThrow(RevisionAlreadyExistsError);
    });

    test('handles failure compensation: marks ingestion as FAILED with error code and details', async () => {
      const nonExistent = path.join(tempFixtureDir, 'missing.zip');

      await expect(
        service.triggerIngestion({
          projectId: project.id,
          repositoryId: repository.id,
          sourceType: 'archive',
          sourceReference: nonExistent,
          userId: developerId,
        })
      ).rejects.toThrow(SourceValidationError);

      const failedJob = await Ingestion.findOne({ repository_id: repository.id });
      expect(failedJob).toBeDefined();
      expect(failedJob.status).toBe(INGESTION_STATUS.FAILED);
      expect(failedJob.error_code).toBe('source_validation_failed');
      expect(failedJob.completed_at).toBeDefined();
    });
  });

  describe('query methods', () => {
    let completedIngestion;
    let revision;

    beforeEach(async () => {
      completedIngestion = await Ingestion.create({
        project_id: project.id,
        repository_id: repository.id,
        source_type: 'archive',
        source_reference: 'data/done.zip',
        status: INGESTION_STATUS.COMPLETED,
        started_at: new Date(),
        completed_at: new Date(),
      });

      revision = await RepositoryRevision.create({
        project_id: project.id,
        repository_id: repository.id,
        ingestion_id: completedIngestion.id,
        revision_identifier: 'v2.0.0',
        source_hash: 'a'.repeat(64),
        total_files: 2,
        total_bytes: 200,
      });

      await RepositoryArtifact.create([
        {
          project_id: project.id,
          repository_id: repository.id,
          revision_id: revision.id,
          path: 'src/main.js',
          size_bytes: 100,
          content_hash: '1'.repeat(64),
          category: 'source_code',
          support_level: 'full',
          storage_key: 'content/11/1111',
        },
        {
          project_id: project.id,
          repository_id: repository.id,
          revision_id: revision.id,
          path: 'README.md',
          size_bytes: 100,
          content_hash: '2'.repeat(64),
          category: 'documentation',
          support_level: 'partial',
          storage_key: 'content/22/2222',
        },
      ]);
    });

    test('getIngestionById allows VIEWER to retrieve ingestion', async () => {
      const retrieved = await service.getIngestionById(
        project.id,
        repository.id,
        completedIngestion.id,
        viewerId
      );
      expect(retrieved.id).toBe(completedIngestion.id);
    });

    test('getIngestionById throws IngestionNotFoundError for non-existent ingestion', async () => {
      await expect(
        service.getIngestionById(
          project.id,
          repository.id,
          crypto.randomUUID(),
          viewerId
        )
      ).rejects.toThrow(IngestionNotFoundError);
    });

    test('listIngestions lists ingestions for repository with pagination', async () => {
      const list = await service.listIngestions(
        project.id,
        repository.id,
        { limit: 10, offset: 0 },
        viewerId
      );
      expect(list).toHaveLength(1);
      expect(list[0].id).toBe(completedIngestion.id);
    });

    test('getRevisionById retrieves revision', async () => {
      const retrieved = await service.getRevisionById(
        project.id,
        repository.id,
        revision.id,
        viewerId
      );
      expect(retrieved.revision_identifier).toBe('v2.0.0');
    });

    test('listRevisions lists repository revisions', async () => {
      const list = await service.listRevisions(
        project.id,
        repository.id,
        { limit: 10, offset: 0 },
        viewerId
      );
      expect(list).toHaveLength(1);
      expect(list[0].revision_identifier).toBe('v2.0.0');
    });

    test('listArtifacts lists revision artifacts ordered deterministically by path', async () => {
      const artifacts = await service.listArtifacts(
        project.id,
        repository.id,
        revision.id,
        { limit: 10, offset: 0 },
        viewerId
      );
      expect(artifacts).toHaveLength(2);
      expect(artifacts[0].path).toBe('README.md');
      expect(artifacts[1].path).toBe('src/main.js');
    });
  });
});
