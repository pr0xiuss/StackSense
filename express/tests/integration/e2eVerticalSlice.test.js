const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const request = require('supertest');

const suiteRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'stacksense-e2e-'));
process.env.STORAGE_ROOT = path.join(suiteRoot, 'storage');

const app = require('../../src/app');
const { INGESTION_STATUS } = require('../../src/constants/ingestionConstants');
const { createTestZip } = require('../helpers/archiveHelper');

const TERMINAL_INGESTION_STATUSES = new Set([
  INGESTION_STATUS.COMPLETED,
  INGESTION_STATUS.FAILED,
]);

async function pollIngestionUntilTerminal({
  projectId,
  repositoryId,
  ingestionId,
  accessToken,
  timeoutMs = 5000,
  intervalMs = 25,
}) {
  const deadline = Date.now() + timeoutMs;
  let lastStatus = null;

  while (Date.now() <= deadline) {
    const response = await request(app)
      .get(
        `/api/v1/projects/${projectId}/repositories/${repositoryId}/ingestions/${ingestionId}`
      )
      .set('Authorization', `Bearer ${accessToken}`)
      .expect(200);

    lastStatus = response.body.status;
    if (TERMINAL_INGESTION_STATUSES.has(lastStatus)) {
      if (lastStatus === INGESTION_STATUS.FAILED) {
        throw new Error(
          `Ingestion ${ingestionId} failed: ${response.body.error_code || 'unknown_error'} - ` +
          `${response.body.error_message || 'No error message provided.'}`
        );
      }
      return response.body;
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error(
    `Timed out waiting for ingestion ${ingestionId}; last observed status: ` +
    `${lastStatus || 'unknown'}`
  );
}

describe('M6-B2 end-to-end product flow', () => {
  afterAll(async () => {
    await fs.promises.rm(suiteRoot, { recursive: true, force: true });
  });

  test('registers, authenticates, ingests, reads results, rotates, and logs out', async () => {
    const runId = crypto.randomUUID().replace(/-/g, '').slice(0, 16);
    const email = `m6e2e_${runId}@example.com`;
    const username = `m6e2e_${runId}`;
    const password = 'M6VerticalSlice123!';
    const revisionIdentifier = `m6-e2e-${runId}`;

    const registerResponse = await request(app)
      .post('/api/v1/auth/register')
      .send({ email, username, password })
      .expect(201);

    expect(registerResponse.body.user.id).toBeDefined();
    expect(registerResponse.body.user.email).toBe(email);

    const loginResponse = await request(app)
      .post('/api/v1/auth/login')
      .send({ identifier: email, password })
      .expect(200);

    const initialAccessToken = loginResponse.body.access_token;
    const initialRefreshToken = loginResponse.body.refresh_token;
    expect(initialAccessToken).toBeDefined();
    expect(initialRefreshToken).toBeDefined();

    const projectResponse = await request(app)
      .post('/api/v1/projects')
      .set('Authorization', `Bearer ${initialAccessToken}`)
      .send({
        name: `M6 E2E Project ${runId}`,
        description: 'Deterministic Phase 2 vertical-slice verification.',
      })
      .expect(201);

    const projectId = projectResponse.body.id;
    expect(projectId).toBeDefined();

    const repositoryResponse = await request(app)
      .post(`/api/v1/projects/${projectId}/repositories`)
      .set('Authorization', `Bearer ${initialAccessToken}`)
      .send({
        name: `m6-e2e-repository-${runId}`,
        description: 'Repository registered by the M6-B2 vertical slice.',
      })
      .expect(201);

    const repositoryId = repositoryResponse.body.id;
    expect(repositoryId).toBeDefined();
    expect(repositoryResponse.body.project_id).toBe(projectId);

    const archivePath = path.join(suiteRoot, `repository-${runId}.zip`);
    createTestZip(archivePath, {
      'src/index.js': "export const stackSense = 'm6-e2e';",
      'README.md': '# StackSense M6 end-to-end fixture',
      'package.json': JSON.stringify({ name: `m6-e2e-${runId}`, private: true }),
    });

    const ingestionResponse = await request(app)
      .post(
        `/api/v1/projects/${projectId}/repositories/${repositoryId}/ingestions`
      )
      .set('Authorization', `Bearer ${initialAccessToken}`)
      .send({
        source_type: 'archive',
        source_reference: archivePath,
        revision_identifier: revisionIdentifier,
      })
      .expect(201);

    const ingestionId = ingestionResponse.body.id;
    expect(ingestionId).toBeDefined();

    const completedIngestion = await pollIngestionUntilTerminal({
      projectId,
      repositoryId,
      ingestionId,
      accessToken: initialAccessToken,
    });
    expect(completedIngestion.status).toBe(INGESTION_STATUS.COMPLETED);
    expect(completedIngestion.error_code).toBeNull();
    expect(completedIngestion.error_message).toBeNull();

    const revisionsResponse = await request(app)
      .get(`/api/v1/projects/${projectId}/repositories/${repositoryId}/revisions`)
      .set('Authorization', `Bearer ${initialAccessToken}`)
      .expect(200);

    const revision = revisionsResponse.body.find(
      (candidate) => candidate.ingestion_id === ingestionId
    );
    expect(revision).toBeDefined();
    expect(revision.revision_identifier).toBe(revisionIdentifier);
    expect(revision.total_files).toBe(3);
    expect(revision.total_bytes).toBeGreaterThan(0);

    const revisionResponse = await request(app)
      .get(
        `/api/v1/projects/${projectId}/repositories/${repositoryId}/revisions/${revision.id}`
      )
      .set('Authorization', `Bearer ${initialAccessToken}`)
      .expect(200);

    expect(revisionResponse.body).toMatchObject({
      id: revision.id,
      ingestion_id: ingestionId,
      revision_identifier: revisionIdentifier,
      repository_id: repositoryId,
    });

    const artifactsResponse = await request(app)
      .get(
        `/api/v1/projects/${projectId}/repositories/${repositoryId}/revisions/${revision.id}/artifacts`
      )
      .set('Authorization', `Bearer ${initialAccessToken}`)
      .expect(200);

    expect(artifactsResponse.body).toHaveLength(3);
    const sourceArtifact = artifactsResponse.body.find(
      (artifact) => artifact.path === 'src/index.js'
    );
    expect(sourceArtifact).toMatchObject({
      category: 'source_code',
      support_level: 'full',
      repository_id: repositoryId,
      revision_id: revision.id,
    });
    expect(sourceArtifact.content_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(sourceArtifact.storage_key).toBeTruthy();

    const refreshResponse = await request(app)
      .post('/api/v1/auth/refresh')
      .send({ refresh_token: initialRefreshToken })
      .expect(200);

    const rotatedAccessToken = refreshResponse.body.access_token;
    const rotatedRefreshToken = refreshResponse.body.refresh_token;
    expect(rotatedAccessToken).toBeDefined();
    expect(rotatedRefreshToken).toBeDefined();
    expect(rotatedRefreshToken).not.toBe(initialRefreshToken);

    const meResponse = await request(app)
      .get('/api/v1/auth/me')
      .set('Authorization', `Bearer ${rotatedAccessToken}`)
      .expect(200);

    expect(meResponse.body.id).toBe(registerResponse.body.user.id);
    expect(meResponse.body.email).toBe(email);
    expect(meResponse.body.password_hash).toBeUndefined();

    await request(app)
      .post('/api/v1/auth/logout')
      .send({ refresh_token: rotatedRefreshToken })
      .expect(204);

    const revokedSessionResponse = await request(app)
      .post('/api/v1/auth/refresh')
      .send({ refresh_token: rotatedRefreshToken })
      .expect(401);

    expect(revokedSessionResponse.body.error.code).toBe('refresh_token_revoked');
  }, 30000);
});
