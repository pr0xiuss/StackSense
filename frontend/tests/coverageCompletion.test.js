import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, '../src');

const storage = new Map();
globalThis.localStorage = {
  getItem: (key) => storage.get(key) || null,
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: (key) => storage.delete(key),
};
globalThis.window = { dispatchEvent: () => true };
globalThis.FormData = class FormData {};

const { tokenStorage } = await import('../src/services/apiClient.js');
const { projectService } = await import('../src/services/projectService.js');
const { projectAccessService } = await import('../src/services/projectAccessService.js');
const { userDirectoryService } = await import('../src/services/userDirectoryService.js');

tokenStorage.setTokens('access-token', 'refresh-token');

async function testServiceContracts() {
  const requests = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    if (options.method === 'DELETE') return new Response(null, { status: 204 });
    return new Response(JSON.stringify({ project_id: 'project-id', user_id: 'user-id', role: 'viewer' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  await projectService.updateProject('project-id', { name: 'Updated' });
  await projectAccessService.listAccess('project-id');
  await projectAccessService.grantAccess('project-id', ' user-id ', 'VIEWER');
  await projectAccessService.changeRole('project-id', 'user-id', 'DEVELOPER');
  await projectAccessService.revokeAccess('project-id', 'user-id');
  await userDirectoryService.searchByUsername(' ali ');

  assert.deepEqual(requests.map((request) => [request.options.method, request.url]), [
    ['PATCH', '/api/v1/projects/project-id'],
    ['GET', '/api/v1/projects/project-id/access'],
    ['POST', '/api/v1/projects/project-id/access'],
    ['PATCH', '/api/v1/projects/project-id/access/user-id'],
    ['DELETE', '/api/v1/projects/project-id/access/user-id'],
    ['GET', '/api/v1/users/lookup?username=ali&limit=8'],
  ]);
  assert.deepEqual(JSON.parse(requests[2].options.body), { user_id: 'user-id', role: 'viewer' });
  assert.deepEqual(JSON.parse(requests[3].options.body), { role: 'developer' });
}

function testRoleAndActionSafety() {
  const hook = fs.readFileSync(path.join(src, 'hooks/useProjectRole.js'), 'utf8');
  const card = fs.readFileSync(path.join(src, 'components/dashboard/ProjectCard.jsx'), 'utf8');
  assert.ok(hook.includes('item.user_id === user.id'), 'Role must be selected using authenticated user UUID');
  assert.ok(hook.includes('setRole(null)'), 'Unresolved roles must remain non-privileged');
  assert.ok(!card.includes("project.role || 'OWNER'"), 'Missing role must never default to OWNER');
  assert.ok(card.includes('hidden: !canCreateOrUpdate'), 'Create/update actions must be role-gated');
  assert.ok(card.includes('hidden: !canDelete'), 'Delete actions must be role-gated');
}

function testSharedMenuAccessibility() {
  const menu = fs.readFileSync(path.join(src, 'components/common/ActionMenu.jsx'), 'utf8');
  assert.ok(menu.includes('createPortal'), 'Menu must escape clipping containers through a portal');
  assert.ok(menu.includes("event.key === 'Escape'"), 'Menu must dismiss with Escape');
  assert.ok(menu.includes("event.key === 'ArrowDown'"), 'Menu must support arrow-key navigation');
  assert.ok(menu.includes("window.addEventListener('scroll'"), 'Menu must reposition while ancestors scroll');
  assert.ok(menu.includes('aria-haspopup="menu"'));
}

function testMutationAndCollaboratorUI() {
  const metadata = fs.readFileSync(path.join(src, 'components/common/MetadataEditModal.jsx'), 'utf8');
  const members = fs.readFileSync(path.join(src, 'components/dashboard/ProjectMembersModal.jsx'), 'utf8');
  assert.ok(metadata.includes('maxLength={255}') && metadata.includes('maxLength={2000}'));
  assert.ok(metadata.includes('disabled={loading || !name.trim()}'), 'Duplicate edit submission must be prevented');
  assert.ok(members.includes('projectAccessService.grantAccess'));
  assert.ok(members.includes('projectAccessService.changeRole'));
  assert.ok(members.includes('projectAccessService.revokeAccess'));
  assert.ok(members.includes('userDirectoryService.searchByUsername'), 'Collaborators must be searched by username');
  assert.ok(members.includes('selectedUser.id'), 'The resolved user ID must be submitted to project access');
  assert.ok(members.includes("member.username || 'Unknown user'"), 'Collaborator rows must render usernames');
  assert.ok(!members.includes('User UUID'), 'The UI must not request UUID input');
  assert.ok(members.includes('canManage && !isCurrentUser'), 'Self role changes and self revocation must not be rendered');
  assert.ok(members.includes("aria-label={isCurrentUser ? 'Your project role'"), 'The current user must receive a read-only role indicator');
}

function testIngestionAndPaginationContracts() {
  const page = fs.readFileSync(path.join(src, 'pages/RepositoryDetailPage.jsx'), 'utf8');
  const ingestion = fs.readFileSync(path.join(src, 'components/repository/IngestionTab.jsx'), 'utf8');
  const revisions = fs.readFileSync(path.join(src, 'components/repository/RevisionsTab.jsx'), 'utf8');
  const artifacts = fs.readFileSync(path.join(src, 'components/repository/ArtifactsTab.jsx'), 'utf8');
  assert.ok(page.includes('ingestionService.getIngestion'), 'Active polling must use the single-ingestion endpoint');
  assert.ok(page.includes("['pending', 'processing']"), 'Both active states must poll');
  assert.ok(page.includes('window.setTimeout(poll, 3000)'), 'Polling must serialize requests');
  assert.ok(page.includes('window.clearTimeout(timeoutId)'), 'Polling must clean up on navigation/state change');
  assert.ok(ingestion.includes('onPreviousPage') && ingestion.includes('onNextPage'));
  assert.ok(revisions.includes('ingestionService.getRevision'), 'Revision detail endpoint must be integrated');
  assert.ok(revisions.includes('offset + pageSize'), 'Revision pagination must request later offsets');
  assert.ok(artifacts.includes('artifactOffset + pageSize'), 'Artifact pagination must request later offsets');
  assert.ok(artifacts.includes('setRevisionError'), 'Revision selector errors must not be swallowed');
}

await testServiceContracts();
testRoleAndActionSafety();
testSharedMenuAccessibility();
testMutationAndCollaboratorUI();
testIngestionAndPaginationContracts();
console.log('Frontend API coverage completion tests passed.');
