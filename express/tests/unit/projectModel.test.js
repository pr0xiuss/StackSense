const Project = require('../../src/models/Project');
const projectService = require('../../src/services/projectService');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe('Project Model & Service Unit Tests (Batch 2)', () => {
  describe('Project Schema & Model Validation', () => {
    it('creates a project with a valid default UUID v4 identifier', async () => {
      const project = new Project({
        name: 'StackSense Platform',
        description: 'Core analysis workspace',
      });

      await project.save();

      expect(project._id).toBeDefined();
      expect(project._id).toMatch(UUID_V4_REGEX);
      expect(project.name).toBe('StackSense Platform');
      expect(project.description).toBe('Core analysis workspace');
      expect(project.created_at).toBeInstanceOf(Date);
      expect(project.updated_at).toBeInstanceOf(Date);
    });

    it('rejects creation when name is missing or empty', async () => {
      const projectMissing = new Project({});
      await expect(projectMissing.save()).rejects.toThrow();

      const projectEmpty = new Project({ name: '   ' });
      await expect(projectEmpty.save()).rejects.toThrow();
    });

    it('rejects name exceeding 255 characters', async () => {
      const longName = 'a'.repeat(256);
      const project = new Project({ name: longName });
      await expect(project.save()).rejects.toThrow(/255/);
    });

    it('rejects description exceeding 2000 characters', async () => {
      const longDesc = 'd'.repeat(2001);
      const project = new Project({ name: 'Valid Name', description: longDesc });
      await expect(project.save()).rejects.toThrow(/2000/);
    });

    it('trims leading and trailing whitespace from name and description', async () => {
      const project = new Project({
        name: '   Trimmed Project   ',
        description: '   Trimmed Description   ',
      });
      await project.save();

      expect(project.name).toBe('Trimmed Project');
      expect(project.description).toBe('Trimmed Description');
    });

    it('serializes to JSON with id instead of _id and strips __v', async () => {
      const project = new Project({
        name: 'JSON Test Project',
      });
      await project.save();

      const json = project.toJSON();

      expect(json.id).toBe(project._id);
      expect(json._id).toBeUndefined();
      expect(json.__v).toBeUndefined();
      expect(json.name).toBe('JSON Test Project');
      expect(json.created_at).toBeDefined();
      expect(json.updated_at).toBeDefined();
    });

    it('enforces architecture invariants: no owner_id or organization_id in schema', () => {
      const paths = Object.keys(Project.schema.paths);
      expect(paths).not.toContain('owner_id');
      expect(paths).not.toContain('organization_id');
      expect(paths).not.toContain('org_id');
    });
  });

  describe('Project Service Operations', () => {
    it('createProject saves a new project and returns the document', async () => {
      const created = await projectService.createProject({
        name: 'Service Created Project',
        description: 'Testing service creation',
      });

      expect(created._id).toMatch(UUID_V4_REGEX);
      expect(created.name).toBe('Service Created Project');
      expect(created.description).toBe('Testing service creation');

      const found = await Project.findById(created._id);
      expect(found).not.toBeNull();
      expect(found.name).toBe('Service Created Project');
    });

    it('getProjectById retrieves an existing project and returns null for non-existent id', async () => {
      const created = await projectService.createProject({ name: 'Lookup Project' });

      const found = await projectService.getProjectById(created._id);
      expect(found).not.toBeNull();
      expect(found._id).toBe(created._id);

      const notFound = await projectService.getProjectById('00000000-0000-4000-8000-000000000000');
      expect(notFound).toBeNull();
    });

    it('listProjects returns projects sorted by created_at desc with pagination', async () => {
      const p1 = await projectService.createProject({ name: 'Project 1' });
      // Small artificial delay to ensure distinct created_at timestamps
      await new Promise((r) => setTimeout(r, 10));
      const p2 = await projectService.createProject({ name: 'Project 2' });
      await new Promise((r) => setTimeout(r, 10));
      const p3 = await projectService.createProject({ name: 'Project 3' });

      const all = await projectService.listProjects({ limit: 10, offset: 0 });
      expect(all.length).toBe(3);
      // Sorted desc: p3 should be first
      expect(all[0]._id).toBe(p3._id);
      expect(all[1]._id).toBe(p2._id);
      expect(all[2]._id).toBe(p1._id);

      // Pagination check: offset 1, limit 1
      const paged = await projectService.listProjects({ limit: 1, offset: 1 });
      expect(paged.length).toBe(1);
      expect(paged[0]._id).toBe(p2._id);
    });

    it('updateProject modifies metadata and returns updated document or null if not found', async () => {
      const created = await projectService.createProject({
        name: 'Initial Name',
        description: 'Initial Description',
      });

      const updated = await projectService.updateProject(created._id, {
        name: 'Updated Name',
        description: 'Updated Description',
      });

      expect(updated).not.toBeNull();
      expect(updated.name).toBe('Updated Name');
      expect(updated.description).toBe('Updated Description');

      const notFound = await projectService.updateProject('00000000-0000-4000-8000-000000000000', {
        name: 'Does Not Exist',
      });
      expect(notFound).toBeNull();
    });

    it('deleteProject hard deletes the project from database and returns deleted doc or null', async () => {
      const created = await projectService.createProject({ name: 'To Be Deleted' });

      const deleted = await projectService.deleteProject(created._id);
      expect(deleted).not.toBeNull();
      expect(deleted._id).toBe(created._id);

      const foundAfter = await projectService.getProjectById(created._id);
      expect(foundAfter).toBeNull();

      const deleteAgain = await projectService.deleteProject(created._id);
      expect(deleteAgain).toBeNull();
    });
  });
});
