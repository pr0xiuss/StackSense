const crypto = require('crypto');
const repositoryService = require('../../src/services/repositoryService');
const projectService = require('../../src/services/projectService');
const projectAccessService = require('../../src/services/projectAccessService');
const { PROJECT_ROLES } = require('../../src/constants/projectRoles');
const {
  RepositoryNotFoundError,
  RepositoryAlreadyExistsError,
} = require('../../src/errors/repositoryErrors');
const { ProjectAccessDeniedError } = require('../../src/errors/accessErrors');

describe('Repository Service Unit Tests (M3 Batch 1)', () => {
  let ownerId;
  let devId;
  let viewerId;
  let outsiderId;
  let project;

  beforeEach(async () => {
    ownerId = crypto.randomUUID();
    devId = crypto.randomUUID();
    viewerId = crypto.randomUUID();
    outsiderId = crypto.randomUUID();

    project = await projectService.createProject({
      name: 'Repo-Test-Project',
      description: 'Testing repository service',
      ownerId,
    });

    await projectAccessService.grantAccess({
      projectId: project._id,
      userId: devId,
      role: PROJECT_ROLES.DEVELOPER,
      actorUserId: ownerId,
    });

    await projectAccessService.grantAccess({
      projectId: project._id,
      userId: viewerId,
      role: PROJECT_ROLES.VIEWER,
      actorUserId: ownerId,
    });
  });

  describe('registerRepository', () => {
    it('registers a new repository when user has create permission (Owner or Developer)', async () => {
      const repo = await repositoryService.registerRepository({
        projectId: project._id,
        name: 'web-frontend',
        description: 'Frontend React application',
        userId: devId,
      });

      expect(repo).toBeDefined();
      expect(repo.name).toBe('web-frontend');
      expect(repo.description).toBe('Frontend React application');
      expect(repo.project_id).toBe(project._id);
      expect(repo.status).toBe('registered');
    });

    it('rejects registration when user has VIEWER role', async () => {
      await expect(
        repositoryService.registerRepository({
          projectId: project._id,
          name: 'viewer-repo',
          userId: viewerId,
        })
      ).rejects.toThrow(ProjectAccessDeniedError);
    });

    it('rejects registration when user is an outsider', async () => {
      await expect(
        repositoryService.registerRepository({
          projectId: project._id,
          name: 'outsider-repo',
          userId: outsiderId,
        })
      ).rejects.toThrow(ProjectAccessDeniedError);
    });

    it('rejects registration with duplicate name in the same project', async () => {
      await repositoryService.registerRepository({
        projectId: project._id,
        name: 'duplicate-service',
        userId: ownerId,
      });

      await expect(
        repositoryService.registerRepository({
          projectId: project._id,
          name: 'duplicate-service',
          userId: devId,
        })
      ).rejects.toThrow(RepositoryAlreadyExistsError);
    });

    it('allows same repository name in a different project', async () => {
      const project2 = await projectService.createProject({
        name: 'Project 2',
        ownerId,
      });

      await repositoryService.registerRepository({
        projectId: project._id,
        name: 'shared-name',
        userId: ownerId,
      });

      const repo2 = await repositoryService.registerRepository({
        projectId: project2._id,
        name: 'shared-name',
        userId: ownerId,
      });

      expect(repo2.name).toBe('shared-name');
      expect(repo2.project_id).toBe(project2._id);
    });
  });

  describe('getRepositoryById', () => {
    it('retrieves a repository by ID when user has access', async () => {
      const created = await repositoryService.registerRepository({
        projectId: project._id,
        name: 'api-service',
        userId: ownerId,
      });

      const retrieved = await repositoryService.getRepositoryById(
        project._id,
        created._id,
        viewerId
      );

      expect(retrieved._id).toBe(created._id);
      expect(retrieved.name).toBe('api-service');
    });

    it('throws RepositoryNotFoundError if repository does not exist', async () => {
      await expect(
        repositoryService.getRepositoryById(
          project._id,
          crypto.randomUUID(),
          ownerId
        )
      ).rejects.toThrow(RepositoryNotFoundError);
    });

    it('throws RepositoryNotFoundError if repository belongs to another project', async () => {
      const project2 = await projectService.createProject({
        name: 'Project 2',
        ownerId,
      });

      const repoInP2 = await repositoryService.registerRepository({
        projectId: project2._id,
        name: 'p2-repo',
        userId: ownerId,
      });

      await expect(
        repositoryService.getRepositoryById(
          project._id,
          repoInP2._id,
          ownerId
        )
      ).rejects.toThrow(RepositoryNotFoundError);
    });

    it('throws ProjectAccessDeniedError if user does not have project access', async () => {
      const created = await repositoryService.registerRepository({
        projectId: project._id,
        name: 'secret-repo',
        userId: ownerId,
      });

      await expect(
        repositoryService.getRepositoryById(
          project._id,
          created._id,
          outsiderId
        )
      ).rejects.toThrow(ProjectAccessDeniedError);
    });
  });

  describe('listRepositories', () => {
    it('lists repositories with pagination and created_at ascending ordering', async () => {
      await repositoryService.registerRepository({
        projectId: project._id,
        name: 'repo-1',
        userId: ownerId,
      });
      await repositoryService.registerRepository({
        projectId: project._id,
        name: 'repo-2',
        userId: ownerId,
      });
      await repositoryService.registerRepository({
        projectId: project._id,
        name: 'repo-3',
        userId: ownerId,
      });

      const page1 = await repositoryService.listRepositories(
        project._id,
        { limit: 2, offset: 0 },
        viewerId
      );
      expect(page1).toHaveLength(2);
      expect(page1[0].name).toBe('repo-1');
      expect(page1[1].name).toBe('repo-2');

      const page2 = await repositoryService.listRepositories(
        project._id,
        { limit: 2, offset: 2 },
        viewerId
      );
      expect(page2).toHaveLength(1);
      expect(page2[0].name).toBe('repo-3');
    });
  });

  describe('updateRepository', () => {
    it('updates repository name and description when authorized', async () => {
      const repo = await repositoryService.registerRepository({
        projectId: project._id,
        name: 'old-name',
        description: 'old desc',
        userId: ownerId,
      });

      const updated = await repositoryService.updateRepository(
        project._id,
        repo._id,
        { name: 'new-name', description: 'new desc' },
        devId
      );

      expect(updated.name).toBe('new-name');
      expect(updated.description).toBe('new desc');
    });

    it('rejects update when user has only VIEWER role', async () => {
      const repo = await repositoryService.registerRepository({
        projectId: project._id,
        name: 'view-only-test',
        userId: ownerId,
      });

      await expect(
        repositoryService.updateRepository(
          project._id,
          repo._id,
          { name: 'renamed' },
          viewerId
        )
      ).rejects.toThrow(ProjectAccessDeniedError);
    });

    it('rejects update when renamed name collides with another repo in project', async () => {
      await repositoryService.registerRepository({
        projectId: project._id,
        name: 'service-a',
        userId: ownerId,
      });
      const repoB = await repositoryService.registerRepository({
        projectId: project._id,
        name: 'service-b',
        userId: ownerId,
      });

      await expect(
        repositoryService.updateRepository(
          project._id,
          repoB._id,
          { name: 'service-a' },
          ownerId
        )
      ).rejects.toThrow(RepositoryAlreadyExistsError);
    });
  });

  describe('deleteRepository', () => {
    it('deletes repository when user has delete permission (Owner)', async () => {
      const repo = await repositoryService.registerRepository({
        projectId: project._id,
        name: 'to-delete',
        userId: ownerId,
      });

      await repositoryService.deleteRepository(project._id, repo._id, ownerId);

      await expect(
        repositoryService.getRepositoryById(project._id, repo._id, ownerId)
      ).rejects.toThrow(RepositoryNotFoundError);
    });

    it('rejects deletion when user has only DEVELOPER role', async () => {
      const repo = await repositoryService.registerRepository({
        projectId: project._id,
        name: 'dev-delete-test',
        userId: ownerId,
      });

      await expect(
        repositoryService.deleteRepository(project._id, repo._id, devId)
      ).rejects.toThrow(ProjectAccessDeniedError);
    });
  });
});
