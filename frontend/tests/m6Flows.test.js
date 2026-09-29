/**
 * M6 Verification Test Suite
 * Tests:
 * 1. Centralized apiClient token attachment
 * 2. 401 Interception & Automatic Refresh with single retry
 * 3. Concurrent 401 requests sharing exactly ONE refresh promise (no token rotation storm)
 * 4. Refresh request loop protection & auth failure session clearing
 * 5. Services: authService, projectService, repositoryService, ingestionService
 * 6. Dashboard & Repository page contracts & component requirements
 */

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const srcDir = path.resolve(__dirname, '../src');

// Setup global mock localStorage and window events
const storage = new Map();
globalThis.localStorage = {
  getItem: (key) => storage.get(key) || null,
  setItem: (key, val) => storage.set(key, String(val)),
  removeItem: (key) => storage.delete(key),
  clear: () => storage.clear(),
};

const windowEvents = [];
globalThis.window = {
  dispatchEvent: (event) => {
    windowEvents.push(event);
    return true;
  },
  location: { hash: '#/projects', pathname: '/projects' },
  history: {
    pushState: () => {},
    replaceState: () => {},
  },
};
globalThis.CustomEvent = class CustomEvent {
  constructor(type, detail) {
    this.type = type;
    this.detail = detail;
  }
};
globalThis.HashChangeEvent = class HashChangeEvent {
  constructor(type) {
    this.type = type;
  }
};

// Import apiClient and services
const { apiClient, tokenStorage, ApiError, ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } =
  await import('../src/services/apiClient.js');
const { authService } = await import('../src/services/authService.js');
const { projectService } = await import('../src/services/projectService.js');
const { repositoryService } = await import('../src/services/repositoryService.js');
const { ingestionService } = await import('../src/services/ingestionService.js');

async function testBearerAttachment() {
  console.log('Testing automatic Bearer token attachment...');
  tokenStorage.clearTokens();
  tokenStorage.setTokens('valid-jwt-token', 'valid-refresh-token');

  let capturedHeaders = null;
  globalThis.fetch = async (url, options) => {
    capturedHeaders = options.headers;
    return new Response(JSON.stringify([{ id: 'p1', name: 'Project 1' }]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  const res = await apiClient.get('/projects');
  assert.equal(capturedHeaders.get('Authorization'), 'Bearer valid-jwt-token');
  assert.equal(res[0].name, 'Project 1');
  console.log('✓ Bearer attachment verified');
}

async function testAutomaticRefreshAndRetry() {
  console.log('Testing automatic 401 refresh with single retry...');
  tokenStorage.setTokens('expired-access-token', 'refresh-token-initial');

  let callCount = 0;
  let refreshCalled = false;

  globalThis.fetch = async (url, options) => {
    callCount++;
    if (url.includes('/auth/refresh')) {
      refreshCalled = true;
      const body = JSON.parse(options.body);
      assert.equal(body.refresh_token, 'refresh-token-initial');
      return new Response(
        JSON.stringify({
          access_token: 'fresh-access-token',
          refresh_token: 'refresh-token-rotated',
          token_type: 'bearer',
          expires_in: 900,
          refresh_expires_in: 604800,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // First attempt with expired token -> return 401
    if (options.headers.get('Authorization') === 'Bearer expired-access-token') {
      return new Response(JSON.stringify({ detail: 'Token expired' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Retried request with fresh token -> succeed
    if (options.headers.get('Authorization') === 'Bearer fresh-access-token') {
      return new Response(JSON.stringify({ id: 'p1', name: 'Project Success' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    throw new Error(`Unexpected request to ${url}`);
  };

  const result = await apiClient.get('/projects/p1');
  assert.ok(refreshCalled, 'Refresh endpoint must be called');
  assert.equal(result.name, 'Project Success');
  assert.equal(tokenStorage.getAccessToken(), 'fresh-access-token');
  assert.equal(tokenStorage.getRefreshToken(), 'refresh-token-rotated');
  console.log('✓ 401 refresh and retry verified');
}

async function testConcurrent401Deduplication() {
  console.log('Testing concurrent 401 requests share a single refresh call...');
  tokenStorage.setTokens('expired-for-storm', 'refresh-token-storm');

  let refreshInvocationCount = 0;

  globalThis.fetch = async (url, options) => {
    if (url.includes('/auth/refresh')) {
      refreshInvocationCount++;
      // Simulate small async delay
      await new Promise((resolve) => setTimeout(resolve, 10));
      return new Response(
        JSON.stringify({
          access_token: 'storm-fresh-token',
          refresh_token: 'storm-rotated-refresh',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const auth = options.headers.get('Authorization');
    if (auth === 'Bearer expired-for-storm') {
      return new Response(JSON.stringify({ detail: 'Token expired' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (auth === 'Bearer storm-fresh-token') {
      return new Response(JSON.stringify({ url, ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    throw new Error(`Unexpected request: ${url}`);
  };

  // Launch 5 concurrent requests simultaneously
  const results = await Promise.all([
    apiClient.get('/projects/1'),
    apiClient.get('/projects/2'),
    apiClient.get('/projects/3'),
    apiClient.get('/projects/4'),
    apiClient.get('/projects/5'),
  ]);

  assert.equal(results.length, 5);
  assert.equal(
    refreshInvocationCount,
    1,
    `Expected exactly 1 refresh call for concurrent 401s, got ${refreshInvocationCount}`
  );
  assert.equal(tokenStorage.getAccessToken(), 'storm-fresh-token');
  console.log('✓ Concurrent 401 deduplication verified (0 refresh storms)');
}

async function testRefreshFailureSessionClear() {
  console.log('Testing refresh failure clears session and emits auth:expired...');
  tokenStorage.setTokens('expired-token', 'invalid-refresh');
  windowEvents.length = 0;

  globalThis.fetch = async (url) => {
    if (url.includes('/auth/refresh')) {
      return new Response(JSON.stringify({ detail: 'Invalid refresh token' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response(JSON.stringify({ detail: 'Token expired' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  let threw = false;
  try {
    await apiClient.get('/projects');
  } catch (err) {
    threw = true;
    assert.equal(err.status, 401);
  }

  assert.ok(threw, 'Should throw ApiError on refresh failure');
  assert.equal(tokenStorage.getAccessToken(), null, 'Access token must be cleared');
  assert.equal(tokenStorage.getRefreshToken(), null, 'Refresh token must be cleared');
  assert.ok(
    windowEvents.some((e) => e.type === 'auth:expired'),
    'auth:expired event must be dispatched'
  );
  console.log('✓ Refresh failure session cleanup verified');
}

async function testServicesContracts() {
  console.log('Testing Project, Repository, and Ingestion services...');
  tokenStorage.setTokens('test-token', 'test-refresh');

  let lastUrl = '';
  let lastMethod = '';
  let lastBody = null;

  globalThis.fetch = async (url, options) => {
    lastUrl = url;
    lastMethod = options.method;
    lastBody = options.body;

    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  // projectService
  await projectService.listProjects(50, 0);
  assert.equal(lastUrl, '/api/v1/projects?limit=50&offset=0');
  assert.equal(lastMethod, 'GET');

  await projectService.createProject('My App', 'Desc');
  assert.equal(lastUrl, '/api/v1/projects');
  assert.equal(lastMethod, 'POST');
  assert.deepEqual(JSON.parse(lastBody), { name: 'My App', description: 'Desc' });

  await projectService.deleteProject('proj-123');
  assert.equal(lastUrl, '/api/v1/projects/proj-123');
  assert.equal(lastMethod, 'DELETE');

  // repositoryService
  await repositoryService.listRepositories('proj-123', 50, 0);
  assert.equal(lastUrl, '/api/v1/projects/proj-123/repositories?limit=50&offset=0');

  await repositoryService.createRepository('proj-123', 'core-api', 'Core service');
  assert.equal(lastUrl, '/api/v1/projects/proj-123/repositories');
  assert.equal(lastMethod, 'POST');
  assert.deepEqual(JSON.parse(lastBody), { name: 'core-api', description: 'Core service' });

  // ingestionService
  await ingestionService.listIngestions('proj-123', 'repo-456', 20, 0);
  assert.equal(lastUrl, '/api/v1/projects/proj-123/repositories/repo-456/ingestions?limit=20&offset=0');

  // ingestionService - triggerIngestion with GitHub mode
  await ingestionService.triggerIngestion('proj-123', 'repo-456', {
    source_type: 'github',
    repository_url: 'https://github.com/owner/repo',
    ref: 'main',
    revision_identifier: 'v1.0.0',
  });
  assert.equal(lastUrl, '/api/v1/projects/proj-123/repositories/repo-456/ingestions');
  assert.equal(lastMethod, 'POST');
  assert.deepEqual(JSON.parse(lastBody), {
    repository_id: 'repo-456',
    source_type: 'github',
    repository_url: 'https://github.com/owner/repo',
    ref: 'main',
    revision_identifier: 'v1.0.0',
  });

  // ingestionService - triggerIngestion with Server Path mode
  await ingestionService.triggerIngestion('proj-123', 'repo-456', {
    source_type: 'server_path',
    source_reference: '/var/stacksense/staged/archive.tar.gz',
    revision_identifier: 'v1.2.0',
  });
  assert.equal(lastUrl, '/api/v1/projects/proj-123/repositories/repo-456/ingestions');
  assert.equal(lastMethod, 'POST');
  assert.deepEqual(JSON.parse(lastBody), {
    repository_id: 'repo-456',
    source_type: 'server_path',
    source_reference: '/var/stacksense/staged/archive.tar.gz',
    revision_identifier: 'v1.2.0',
  });

  await ingestionService.listRevisions('proj-123', 'repo-456', 20, 0);
  assert.equal(lastUrl, '/api/v1/projects/proj-123/repositories/repo-456/revisions?limit=20&offset=0');

  await ingestionService.listArtifacts('proj-123', 'repo-456', 'rev-789', 50, 0);
  assert.equal(
    lastUrl,
    '/api/v1/projects/proj-123/repositories/repo-456/revisions/rev-789/artifacts?limit=50&offset=0'
  );

  console.log('✓ Service endpoint contracts verified');
}

function testDashboardPageContracts() {
  console.log('Testing Dashboard page code and design requirements...');
  const dashSrc = fs.readFileSync(path.join(srcDir, 'pages/ProjectsDashboardPage.jsx'), 'utf-8');
  assert.ok(dashSrc.includes('DashboardHeader'), 'Must render DashboardHeader');
  assert.ok(dashSrc.includes('ProjectCard'), 'Must render ProjectCard');
  assert.ok(dashSrc.includes('CreateProjectModal'), 'Must support CreateProjectModal');
  assert.ok(dashSrc.includes('CreateRepositoryModal'), 'Must support CreateRepositoryModal');
  assert.ok(dashSrc.includes('No projects yet'), 'Must provide empty state for projects');
  assert.ok(dashSrc.includes('Load More Projects'), 'Must provide pagination load more');

  const cardSrc = fs.readFileSync(path.join(srcDir, 'components/dashboard/ProjectCard.jsx'), 'utf-8');
  assert.ok(cardSrc.includes('OWNER') && cardSrc.includes('ADMIN') && cardSrc.includes('DEVELOPER') && cardSrc.includes('VIEWER'), 'Must support role badges');
  assert.ok(cardSrc.includes('repositoryService.listRepositories'), 'Must lazily load repositories on expansion');
  console.log('✓ Dashboard page contracts passed');
}

function testRepositoryPageContracts() {
  console.log('Testing Repository detail page code and design requirements...');
  const repoPageSrc = fs.readFileSync(path.join(srcDir, 'pages/RepositoryDetailPage.jsx'), 'utf-8');
  assert.ok(repoPageSrc.includes('RepositoryHeader'), 'Must include RepositoryHeader');
  assert.ok(repoPageSrc.includes('IngestionTab'), 'Must include IngestionTab');
  assert.ok(repoPageSrc.includes('RevisionsTab'), 'Must include RevisionsTab');
  assert.ok(repoPageSrc.includes('ArtifactsTab'), 'Must include ArtifactsTab');
  assert.ok(repoPageSrc.includes('NewIngestionModal'), 'Must support unified NewIngestionModal');
  assert.ok(repoPageSrc.includes('UploadArchiveModal'), 'Must support archive upload');
  assert.ok(repoPageSrc.includes('TriggerIngestionModal'), 'Must support local path ingestion trigger');

  const modalSrc = fs.readFileSync(path.join(srcDir, 'components/repository/NewIngestionModal.jsx'), 'utf-8');
  assert.ok(modalSrc.includes('GitHub Repository'), 'NewIngestionModal must include GitHub option');
  assert.ok(modalSrc.includes('Upload Archive'), 'NewIngestionModal must include Upload Archive option');
  assert.ok(modalSrc.includes('Server Path'), 'NewIngestionModal must include Server Path option');
  assert.ok(modalSrc.includes('badge-advanced'), 'NewIngestionModal must visually mark Server Path as Advanced');
  assert.ok(modalSrc.includes('.zip') && modalSrc.includes('.tar.gz') && modalSrc.includes('.tgz'), 'NewIngestionModal must support .zip, .tar, .tar.gz, .tgz');
  assert.ok(modalSrc.includes('role="dialog"'), 'NewIngestionModal must have accessible dialog semantics');

  const ingTabSrc = fs.readFileSync(path.join(srcDir, 'components/repository/IngestionTab.jsx'), 'utf-8');
  assert.ok(ingTabSrc.includes('+ New Ingestion'), 'IngestionTab must feature unified + New Ingestion button');
  assert.ok(ingTabSrc.includes('Ingestion History'), 'Must show Ingestion History table');
  assert.ok(ingTabSrc.includes('Current Ingestion Status'), 'Must show Current Ingestion Status card');
  assert.ok(ingTabSrc.includes('Ingestion Details'), 'Must show Ingestion Details');
  assert.ok(ingTabSrc.includes('Recent Ingestion Logs'), 'Must show Ingestion Logs section');
  assert.ok(!ingTabSrc.includes('Extracting archive...'), 'Must NOT fake ingestion log text');

  const artTabSrc = fs.readFileSync(path.join(srcDir, 'components/repository/ArtifactsTab.jsx'), 'utf-8');
  assert.ok(artTabSrc.includes('Select a revision'), 'Must require/select revision for artifacts');
  console.log('✓ Repository detail page contracts passed');
}

function testCssFidelity() {
  console.log('Testing visual style rules for dark navy palette and glow...');
  const dashCss = fs.readFileSync(path.join(srcDir, 'styles/dashboard.css'), 'utf-8');
  assert.ok(
    dashCss.includes('#080C14') ||
    dashCss.includes('#080c14') ||
    dashCss.includes('#06090e') ||
    dashCss.includes('#0b101b'),
    'Dark navy theme background'
  );
  assert.ok(dashCss.includes('linear-gradient'), 'Gradients present');
  assert.ok(dashCss.includes('.role-badge'), 'Role badge styles defined');

  const repoCss = fs.readFileSync(path.join(srcDir, 'styles/repository.css'), 'utf-8');
  assert.ok(repoCss.includes('.repo-tab-btn'), 'Tab styles defined');
  assert.ok(
    repoCss.includes('.repo-status-pill') || repoCss.includes('.status-badge'),
    'Status badge/pill styles defined'
  );
  console.log('✓ CSS fidelity checks passed');
}

async function runM6Tests() {
  await testBearerAttachment();
  await testAutomaticRefreshAndRetry();
  await testConcurrent401Deduplication();
  await testRefreshFailureSessionClear();
  await testServicesContracts();
  testDashboardPageContracts();
  testRepositoryPageContracts();
  testCssFidelity();
  console.log('\n=============================================');
  console.log(' All M6 Product Flow Tests Passed with 100%! ');
  console.log('=============================================\n');
}

runM6Tests().catch((err) => {
  console.error('M6 Test Failed:', err);
  process.exit(1);
});
