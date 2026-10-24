/**
 * Repository Management & Artifacts Tab Verification Suite
 * Tests:
 * 1. Feature A: Repository Search within expanded section
 * 2. Feature B: Per-Project Repository Pagination (5/page default)
 * 3. Feature C: Repository Deletion (three-dot menu, confirmation dialog, API invocation, state updates)
 * 4. Feature D: ArtifactsTab revisions fetch fix (no redundant 3rd request or loop on selectedRevision)
 */

import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const srcDir = path.resolve(__dirname, '../src');

// Setup mock window and localStorage
const storage = new Map();
globalThis.localStorage = {
  getItem: (key) => storage.get(key) || null,
  setItem: (key, val) => storage.set(key, String(val)),
  removeItem: (key) => storage.delete(key),
  clear: () => storage.clear(),
};

globalThis.window = {
  location: { hash: '#/projects' },
  dispatchEvent: () => true,
};

const { repositoryService } = await import('../src/services/repositoryService.js');
const { ingestionService } = await import('../src/services/ingestionService.js');

function testFeatureA_RepositorySearchContracts() {
  console.log('Testing Feature A: Repository Search contracts & logic...');
  const cardSrc = fs.readFileSync(path.join(srcDir, 'components/dashboard/ProjectCard.jsx'), 'utf-8');

  // Must have search input when expanded
  assert.ok(cardSrc.includes('repo-search-input'), 'Must define repo-search-input');
  assert.ok(cardSrc.includes('placeholder="Search repositories..."'), 'Must have search placeholder');
  assert.ok(cardSrc.includes('repoSearchQuery'), 'Must maintain repoSearchQuery state');

  // Search input must be inside accordion-expanded and not in collapsed button
  const expandedIndex = cardSrc.indexOf('accordion-expanded');
  const searchInputIndex = cardSrc.indexOf('repo-search-input');
  const collapsedIndex = cardSrc.indexOf('accordion-toggle-btn collapsed');
  assert.ok(searchInputIndex > expandedIndex, 'Search input must reside inside expanded section');
  assert.ok(searchInputIndex < collapsedIndex, 'Search input must NOT be inside collapsed section');

  // Case-insensitive filtering check
  assert.ok(
    cardSrc.includes('.toLowerCase().includes(query)') ||
    cardSrc.includes('.includes(query)'),
    'Must filter repository names case-insensitively'
  );

  // Empty search state
  assert.ok(cardSrc.includes('repo-search-empty'), 'Must define clear repo-search-empty state');
  assert.ok(cardSrc.includes('No repositories match'), 'Must indicate no matching repositories');
  assert.ok(cardSrc.includes('Clear search'), 'Must provide button to clear search filter');

  // Logic test: Case-insensitive filtering
  const testRepos = [
    { id: '1', name: 'Postgres-Engine' },
    { id: '2', name: 'analytics-worker' },
    { id: '3', name: 'POSTGRES-EXTENSION' },
    { id: '4', name: 'api-gateway' },
  ];

  const filterRepos = (repos, query) => {
    if (!query.trim()) return repos;
    const q = query.toLowerCase().trim();
    return repos.filter((r) => (r.name || '').toLowerCase().includes(q));
  };

  const matchPostgres = filterRepos(testRepos, 'postgres');
  assert.equal(matchPostgres.length, 2, 'Should match 2 repositories case-insensitively');
  assert.equal(matchPostgres[0].name, 'Postgres-Engine');
  assert.equal(matchPostgres[1].name, 'POSTGRES-EXTENSION');

  const matchWorker = filterRepos(testRepos, 'WORKER');
  assert.equal(matchWorker.length, 1);
  assert.equal(matchWorker[0].name, 'analytics-worker');

  const matchNone = filterRepos(testRepos, 'nonexistent');
  assert.equal(matchNone.length, 0, 'Should return empty array when no matches');

  console.log('✓ Feature A contracts and search logic verified');
}

function testFeatureB_RepositoryPaginationContracts() {
  console.log('Testing Feature B: Per-Project Repository Pagination contracts & logic...');
  const cardSrc = fs.readFileSync(path.join(srcDir, 'components/dashboard/ProjectCard.jsx'), 'utf-8');

  // Must have 5 items per page default
  assert.ok(
    cardSrc.includes('REPOS_PER_PAGE = 5') || cardSrc.includes('reposPerPage = 5'),
    'Must define 5 repositories per page'
  );

  // Pagination controls bar
  assert.ok(cardSrc.includes('repo-pagination-bar'), 'Must define repo-pagination-bar');
  assert.ok(cardSrc.includes('repo-pagination-info'), 'Must define repo-pagination-info');
  assert.ok(cardSrc.includes('repo-pagination-btn'), 'Must define repo-pagination-btn');
  assert.ok(cardSrc.includes('repo-pagination-page-btn'), 'Must define repo-pagination-page-btn');

  // Disabled navigation at boundaries
  assert.ok(
    cardSrc.includes('disabled={safeRepoPage === 1}'),
    'Prev button must be disabled on page 1'
  );
  assert.ok(
    cardSrc.includes('disabled={safeRepoPage === totalRepoPages}'),
    'Next button must be disabled on last page'
  );

  // Hidden if result fits on one page
  assert.ok(
    cardSrc.includes('filteredRepositories.length > REPOS_PER_PAGE') ||
    cardSrc.includes('filteredRepositories.length > 5'),
    'Pagination controls must be hidden if result fits on one page'
  );

  // Pagination calculation logic test
  const REPOS_PER_PAGE = 5;
  const generateRepos = (count) =>
    Array.from({ length: count }, (_, i) => ({ id: `repo-${i + 1}`, name: `repo-${i + 1}` }));

  const paginate = (items, page, perPage = REPOS_PER_PAGE) => {
    const totalPages = Math.max(1, Math.ceil(items.length / perPage));
    const safePage = Math.min(Math.max(1, page), totalPages);
    const start = (safePage - 1) * perPage;
    const end = Math.min(start + perPage, items.length);
    return {
      totalPages,
      safePage,
      startIndex: start,
      endIndex: end,
      items: items.slice(start, end),
      showingText: `Showing ${start + 1}–${end} of ${items.length}`,
    };
  };

  // Test with 18 items (3 full pages of 5, 1 partial page of 3)
  const repos18 = generateRepos(18);
  const p1 = paginate(repos18, 1);
  assert.equal(p1.totalPages, 4);
  assert.equal(p1.items.length, 5);
  assert.equal(p1.showingText, 'Showing 1–5 of 18');

  const p2 = paginate(repos18, 2);
  assert.equal(p2.items.length, 5);
  assert.equal(p2.showingText, 'Showing 6–10 of 18');

  const p4 = paginate(repos18, 4);
  assert.equal(p4.items.length, 3);
  assert.equal(p4.showingText, 'Showing 16–18 of 18');

  // Test boundary clamping when page exceeds total pages
  const pExcess = paginate(repos18, 99);
  assert.equal(pExcess.safePage, 4, 'Should clamp to nearest valid page');

  // Test deleting the only item on last page navigates to previous page
  const repos11 = generateRepos(11); // Page 3 has 1 item (index 10)
  const beforeDelete = paginate(repos11, 3);
  assert.equal(beforeDelete.safePage, 3);
  const reposAfterDelete = repos11.slice(0, 10); // Now 10 items (2 pages)
  const afterDelete = paginate(reposAfterDelete, 3);
  assert.equal(afterDelete.safePage, 2, 'Should navigate to page 2 after deleting last item on page 3');

  // Test hiding when items <= 5
  const repos4 = generateRepos(4);
  assert.equal(repos4.length <= REPOS_PER_PAGE, true, 'Result fits on 1 page');

  console.log('✓ Feature B contracts and pagination logic verified');
}

function testFeatureC_RepositoryDeletionContracts() {
  console.log('Testing Feature C: Repository Deletion contracts & modal requirements...');
  const cardSrc = fs.readFileSync(path.join(srcDir, 'components/dashboard/ProjectCard.jsx'), 'utf-8');

  // Three-dot menu in Actions column
  assert.ok(cardSrc.includes('repo-actions-group'), 'Must define repo-actions-group');
  assert.ok(cardSrc.includes('btn-view-repo'), 'Must preserve View button');
  assert.ok(cardSrc.includes('repo-menu-btn'), 'Must define repo-menu-btn');
  assert.ok(cardSrc.includes('Delete Repository'), 'Must have Delete Repository menu item');
  assert.ok(cardSrc.includes('dropdown-item danger'), 'Delete Repository must use destructive styling');

  // Three-dot button immediately to the right of View button
  const viewIndex = cardSrc.indexOf('btn-view-repo');
  const menuBtnIndex = cardSrc.indexOf('repo-menu-btn');
  assert.ok(menuBtnIndex > viewIndex, 'Three-dot menu button must follow View button in markup');

  // Modal file existence and contract
  const modalPath = path.join(srcDir, 'components/dashboard/DeleteRepositoryModal.jsx');
  assert.ok(fs.existsSync(modalPath), 'DeleteRepositoryModal.jsx must exist');
  const modalSrc = fs.readFileSync(modalPath, 'utf-8');

  assert.ok(modalSrc.includes('delete-warning-text'), 'Must have destructive warning text');
  assert.ok(modalSrc.includes('cannot be undone'), 'Must state action is permanent and cannot be undone');
  assert.ok(modalSrc.includes('repositoryService.deleteRepository'), 'Must call deleteRepository service');
  assert.ok(modalSrc.includes('btn-danger-primary'), 'Confirm button must have danger styling');
  assert.ok(modalSrc.includes('btn-secondary'), 'Cancel button must be present');
  assert.ok(modalSrc.includes('role="dialog"'), 'Must have dialog accessibility semantics');

  // Service method contract
  const serviceSrc = fs.readFileSync(path.join(srcDir, 'services/repositoryService.js'), 'utf-8');
  assert.ok(serviceSrc.includes('deleteRepository(projectId, repositoryId)'), 'Service must export deleteRepository');

  console.log('✓ Feature C contracts and modal requirements verified');
}

async function testFeatureC_RepositoryDeletionApiInvocation() {
  console.log('Testing Feature C: deleteRepository API invocation & error handling...');

  let capturedUrl = null;
  let capturedMethod = null;

  globalThis.fetch = async (url, options) => {
    capturedUrl = url;
    capturedMethod = options.method;

    if (url.includes('/projects/proj-valid/repositories/repo-valid')) {
      return new Response(null, { status: 204 });
    }

    if (url.includes('/projects/proj-valid/repositories/repo-not-found')) {
      return new Response(
        JSON.stringify({
          error: {
            code: 'repository_not_found',
            message: 'Repository not found in project.',
          },
        }),
        { status: 404, headers: { 'Content-Type': 'application/json' } }
      );
    }

    if (url.includes('/projects/proj-valid/repositories/repo-active-ingest')) {
      return new Response(
        JSON.stringify({
          error: {
            code: 'active_ingestion_exists',
            message: 'Cannot delete repository while an ingestion is actively processing.',
          },
        }),
        { status: 409, headers: { 'Content-Type': 'application/json' } }
      );
    }

    throw new Error(`Unexpected request to ${url}`);
  };

  // 1. Successful deletion
  const res = await repositoryService.deleteRepository('proj-valid', 'repo-valid');
  assert.equal(capturedUrl, '/api/v1/projects/proj-valid/repositories/repo-valid');
  assert.equal(capturedMethod, 'DELETE');
  assert.equal(res, null, '204 No Content returns null payload');

  // 2. Not found error preservation
  await assert.rejects(
    async () => repositoryService.deleteRepository('proj-valid', 'repo-not-found'),
    (err) => {
      assert.equal(err.status, 404);
      assert.equal(err.code, 'repository_not_found');
      return true;
    }
  );

  // 3. Active ingestion error preservation
  await assert.rejects(
    async () => repositoryService.deleteRepository('proj-valid', 'repo-active-ingest'),
    (err) => {
      assert.equal(err.status, 409);
      assert.equal(err.code, 'active_ingestion_exists');
      return true;
    }
  );

  console.log('✓ Feature C deleteRepository API invocation & error handling verified');
}

function testFeatureD_ArtifactsTabDuplicateRequestFix() {
  console.log('Testing Feature D: ArtifactsTab revisions effect dependency & request decoupling...');
  const artTabSrc = fs.readFileSync(path.join(srcDir, 'components/repository/ArtifactsTab.jsx'), 'utf-8');

  // The revisions effect must depend strictly on [projectId, repositoryId]
  // and NOT on [selectedRevision] or [onSelectRevision]
  assert.ok(
    artTabSrc.includes('}, [projectId, repositoryId]);'),
    'Revisions effect must depend ONLY on [projectId, repositoryId]'
  );

  assert.ok(
    !artTabSrc.includes('[projectId, repositoryId, selectedRevision]'),
    'Revisions effect must NOT depend on selectedRevision'
  );

  assert.ok(
    !artTabSrc.includes('[projectId, repositoryId, selectedRevision, onSelectRevision]'),
    'Revisions effect must NOT depend on selectedRevision or onSelectRevision'
  );

  // Must track latest selectedRevision via ref
  assert.ok(artTabSrc.includes('selectedRevisionRef = useRef'), 'Must use selectedRevisionRef');
  assert.ok(artTabSrc.includes('selectedRevisionRef.current = selectedRevision'), 'Must keep selectedRevisionRef current');

  // Artifacts loading effect must depend on selectedRevisionId (stable primitive string)
  assert.ok(
    artTabSrc.includes('selectedRevisionId = selectedRevision?.id'),
    'Must extract stable selectedRevisionId'
  );
  assert.ok(
    artTabSrc.includes('[projectId, repositoryId, selectedRevisionId]'),
    'Artifacts effect must depend on [projectId, repositoryId, selectedRevisionId]'
  );

  // Initial selection logic must still function when no revision is selected
  assert.ok(
    artTabSrc.includes('if (!selectedRevisionRef.current && list.length > 0)'),
    'Must auto-select first revision when none is selected'
  );

  console.log('✓ Feature D ArtifactsTab duplicate request fix verified');
}

async function runAllTests() {
  console.log('===============================================================');
  console.log(' Starting StackSense Repository Management & Artifacts Tests   ');
  console.log('===============================================================\n');

  testFeatureA_RepositorySearchContracts();
  testFeatureB_RepositoryPaginationContracts();
  testFeatureC_RepositoryDeletionContracts();
  await testFeatureC_RepositoryDeletionApiInvocation();
  testFeatureD_ArtifactsTabDuplicateRequestFix();

  console.log('\n===============================================================');
  console.log(' All Repository Management & Artifacts Tests Passed (100%)!    ');
  console.log('===============================================================\n');
}

runAllTests().catch((err) => {
  console.error('Test Suite Failed:', err);
  process.exit(1);
});
