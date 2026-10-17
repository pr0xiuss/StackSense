const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const request = require('supertest');

const app = require('../../src/app');
const Project = require('../../src/models/Project');
const ProjectAccess = require('../../src/models/ProjectAccess');
const Repository = require('../../src/models/Repository');
const Ingestion = require('../../src/models/Ingestion');
const RepositoryRevision = require('../../src/models/RepositoryRevision');
const RepositoryArtifact = require('../../src/models/RepositoryArtifact');

const { INGESTION_STATUS } = require('../../src/constants/ingestionConstants');
const { createTestZip } = require('../helpers/archiveHelper');

describe('Ingestion & Revision API Integration Tests (M3 Batch 3)', () => {
  let tempFixtureDir;

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

    tempFixtureDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'api-fixtures-'));

    project = await Project.create({
      name: 'Ingestion API Project',
    });

    await ProjectAccess.create([
      { project_id: project.id, user_id: ownerId, role: 'owner' },
      { project_id: project.id, user_id: developerId, role: 'developer' },
      { project_id: project.id, user_id: viewerId, role: 'viewer' },
    ]);

    repository = await Repository.create({
      project_id: project.id,
      name: 'api-repo',
    });
  });

  afterEach(async () => {
    await fs.promises.rm(tempFixtureDir, { recursive: true, force: true });
  });

  describe('POST /ingestions (Trigger Ingestion)', () => {
    test('developer triggers ingestion for valid archive path (201 Created)', async () => {
      const zipPath = path.join(tempFixtureDir, 'valid.zip');
      createTestZip(zipPath, {
        'src/main.js': "console.log('api test');",
        'README.md': '# API Test',
      });

      const res = await request(app)
        .post(`/api/v1/projects/${project.id}/repositories/${repository.id}/ingestions`)
        .set('x-user-id', developerId)
        .send({
          source_type: 'archive',
          source_reference: zipPath,
          revision_identifier: 'v1.0.0',
        });

      expect(res.status).toBe(201);
      expect(res.body.id).toBeDefined();
      expect(res.body.status).toBe(INGESTION_STATUS.COMPLETED);
      expect(res.body.source_type).toBe('archive');
    });

    test('rejects trigger attempt from VIEWER with 403 project_access_denied', async () => {
      const zipPath = path.join(tempFixtureDir, 'test.zip');
      createTestZip(zipPath, { 'file.txt': 'hello' });

      const res = await request(app)
        .post(`/api/v1/projects/${project.id}/repositories/${repository.id}/ingestions`)
        .set('x-user-id', viewerId)
        .send({
          source_type: 'archive',
          source_reference: zipPath,
        });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });

    test('returns 422 when required fields are missing', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${project.id}/repositories/${repository.id}/ingestions`)
        .set('x-user-id', developerId)
        .send({
          // missing source_type and source_reference
        });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    test('returns 422 for unsupported source_type', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${project.id}/repositories/${repository.id}/ingestions`)
        .set('x-user-id', developerId)
        .send({
          source_type: 'unsupported_type_xyz',
          source_reference: 'some/path',
        });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_source_type');
    });

    test('returns 422 when source_reference exceeds 1024 characters (IR-M4-013)', async () => {
      const res = await request(app)
        .post(`/api/v1/projects/${project.id}/repositories/${repository.id}/ingestions`)
        .set('x-user-id', developerId)
        .send({
          source_type: 'archive',
          source_reference: 'a'.repeat(1025),
        });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    test('returns 404 when repository belongs to a different project', async () => {
      const otherProject = await Project.create({ name: 'Other Project' });
      await ProjectAccess.create({
        project_id: otherProject.id,
        user_id: ownerId,
        role: 'owner',
      });
      const zipPath = path.join(tempFixtureDir, 'test.zip');
      createTestZip(zipPath, { 'file.txt': 'hello' });

      const res = await request(app)
        .post(`/api/v1/projects/${otherProject.id}/repositories/${repository.id}/ingestions`)
        .set('x-user-id', ownerId)
        .send({
          source_type: 'archive',
          source_reference: zipPath,
        });

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('repository_not_found');
    });

    test('rejects trigger attempt from outsider with 403 project_access_denied (no existence oracle)', async () => {
      const nonExistentRepoId = crypto.randomUUID();
      const res = await request(app)
        .post(`/api/v1/projects/${project.id}/repositories/${nonExistentRepoId}/ingestions`)
        .set('x-user-id', outsiderId)
        .send({
          source_type: 'archive',
          source_reference: 'some/path.zip',
        });

      expect(res.status).toBe(403);
      expect(res.body.error.code).toBe('project_access_denied');
    });
  });

  describe('POST /ingestions/upload (Multipart Upload)', () => {
    test('successfully uploads zip archive and executes ingestion (201 Created)', async () => {
      const zipPath = path.join(tempFixtureDir, 'upload_sample.zip');
      createTestZip(zipPath, {
        'index.js': "console.log('uploaded');",
        'package.json': '{"name":"uploaded"}',
      });

      const res = await request(app)
        .post(`/api/v1/projects/${project.id}/repositories/${repository.id}/ingestions/upload`)
        .set('x-user-id', developerId)
        .attach('file', zipPath)
        .field('revision_identifier', 'upload-v1');

      expect(res.status).toBe(201);
      expect(res.body.id).toBeDefined();
      expect(res.body.status).toBe(INGESTION_STATUS.COMPLETED);

      // Verify revision was created
      const rev = await RepositoryRevision.findOne({
        repository_id: repository.id,
        revision_identifier: 'upload-v1',
      });
      expect(rev).toBeDefined();
      expect(rev.total_files).toBe(2);
    });

    test('rejects upload with unsupported file extension (.txt) with 422', async () => {
      const badFilePath = path.join(tempFixtureDir, 'test.txt');
      await fs.promises.writeFile(badFilePath, 'not an archive');

      const res = await request(app)
        .post(`/api/v1/projects/${project.id}/repositories/${repository.id}/ingestions/upload`)
        .set('x-user-id', developerId)
        .attach('file', badFilePath);

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('unsupported_archive_format');
    });
  });

  describe('GET /ingestions and /revisions endpoints', () => {
    let completedJob;
    let revision;

    beforeEach(async () => {
      completedJob = await Ingestion.create({
        project_id: project.id,
        repository_id: repository.id,
        source_type: 'archive',
        source_reference: 'data/test.zip',
        status: INGESTION_STATUS.COMPLETED,
        started_at: new Date(),
        completed_at: new Date(),
      });

      revision = await RepositoryRevision.create({
        project_id: project.id,
        repository_id: repository.id,
        ingestion_id: completedJob.id,
        revision_identifier: 'rev-query-v1',
        source_hash: 'c'.repeat(64),
        total_files: 2,
        total_bytes: 500,
      });

      await RepositoryArtifact.create([
        {
          project_id: project.id,
          repository_id: repository.id,
          revision_id: revision.id,
          path: 'src/main.js',
          size_bytes: 300,
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
          size_bytes: 200,
          content_hash: '2'.repeat(64),
          category: 'documentation',
          support_level: 'partial',
          storage_key: 'content/22/2222',
        },
      ]);
    });

    test('GET /ingestions/:ingestionId allows VIEWER to retrieve job status (200 OK)', async () => {
      const res = await request(app)
        .get(
          `/api/v1/projects/${project.id}/repositories/${repository.id}/ingestions/${completedJob.id}`
        )
        .set('x-user-id', viewerId);

      expect(res.status).toBe(200);
      expect(res.body.id).toBe(completedJob.id);
      expect(res.body.status).toBe(INGESTION_STATUS.COMPLETED);
    });

    test('GET /ingestions lists ingestion jobs for repository (200 OK)', async () => {
      const res = await request(app)
        .get(`/api/v1/projects/${project.id}/repositories/${repository.id}/ingestions`)
        .set('x-user-id', viewerId);

      expect(res.status).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
      expect(res.body).toHaveLength(1);
    });

    test('GET /revisions lists repository revisions (200 OK)', async () => {
      const res = await request(app)
        .get(`/api/v1/projects/${project.id}/repositories/${repository.id}/revisions`)
        .set('x-user-id', viewerId);

      expect(res.status).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
      expect(res.body).toHaveLength(1);
      expect(res.body[0].revision_identifier).toBe('rev-query-v1');
    });

    test('GET /revisions/:revisionId retrieves specific revision (200 OK)', async () => {
      const res = await request(app)
        .get(
          `/api/v1/projects/${project.id}/repositories/${repository.id}/revisions/${revision.id}`
        )
        .set('x-user-id', viewerId);

      expect(res.status).toBe(200);
      expect(res.body.id).toBe(revision.id);
      expect(res.body.revision_identifier).toBe('rev-query-v1');
    });

    test('GET /revisions/:revisionId/artifacts lists artifacts ordered by path ASC (200 OK)', async () => {
      const res = await request(app)
        .get(
          `/api/v1/projects/${project.id}/repositories/${repository.id}/revisions/${revision.id}/artifacts`
        )
        .set('x-user-id', viewerId);

      expect(res.status).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
      expect(res.body).toHaveLength(2);
      expect(res.body[0].path).toBe('README.md');
      expect(res.body[1].path).toBe('src/main.js');
    });
  });
});
