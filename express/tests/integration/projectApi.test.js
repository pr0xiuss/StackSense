const request = require('supertest');
const app = require('../../src/app');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const NON_EXISTENT_UUID_V4 = '00000000-0000-4000-8000-000000000000';
const INVALID_UUID_V1 = '216fff40-98d9-11ef-b864-0242ac120002'; // Version 1, not 4

describe('Project API Integration Tests (Batch 3)', () => {
  describe('POST /api/v1/projects', () => {
    it('creates a new project and returns 201 with project payload', async () => {
      const res = await request(app)
        .post('/api/v1/projects')
        .send({
          name: 'StackSense Core',
          description: 'Core architectural understanding platform',
        });

      expect(res.status).toBe(201);
      expect(res.body).toHaveProperty('id');
      expect(res.body.id).toMatch(UUID_V4_REGEX);
      expect(res.body._id).toBeUndefined();
      expect(res.body.__v).toBeUndefined();
      expect(res.body.name).toBe('StackSense Core');
      expect(res.body.description).toBe('Core architectural understanding platform');
      expect(res.body).toHaveProperty('created_at');
      expect(res.body).toHaveProperty('updated_at');
    });

    it('rejects creation when name is missing or empty with 422', async () => {
      const resMissing = await request(app)
        .post('/api/v1/projects')
        .send({});

      expect(resMissing.status).toBe(422);
      expect(resMissing.body).toHaveProperty('error');
      expect(resMissing.body.error.code).toBe('validation_error');
      expect(resMissing.body.error.message).toContain('name is required');

      const resEmpty = await request(app)
        .post('/api/v1/projects')
        .send({ name: '   ' });

      expect(resEmpty.status).toBe(422);
      expect(resEmpty.body.error.code).toBe('validation_error');
    });

    it('rejects name exceeding 255 characters with 422', async () => {
      const res = await request(app)
        .post('/api/v1/projects')
        .send({ name: 'x'.repeat(256) });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
      expect(res.body.error.message).toContain('255');
    });

    it('rejects description exceeding 2000 characters with 422', async () => {
      const res = await request(app)
        .post('/api/v1/projects')
        .send({
          name: 'Valid Name',
          description: 'y'.repeat(2001),
        });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
      expect(res.body.error.message).toContain('2000');
    });

    it('rejects non-string description with 422', async () => {
      const res = await request(app)
        .post('/api/v1/projects')
        .send({
          name: 'Valid Name',
          description: 12345,
        });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    it('permits duplicate project names in accordance with architecture', async () => {
      const res1 = await request(app)
        .post('/api/v1/projects')
        .send({ name: 'Duplicate Name Allowed' });
      expect(res1.status).toBe(201);

      const res2 = await request(app)
        .post('/api/v1/projects')
        .send({ name: 'Duplicate Name Allowed' });
      expect(res2.status).toBe(201);
      expect(res1.body.id).not.toBe(res2.body.id);
    });
  });

  describe('GET /api/v1/projects/:projectId', () => {
    it('retrieves an existing project by UUID v4 with 200', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .send({ name: 'Retrieve Me', description: 'Test desc' });

      const res = await request(app).get(`/api/v1/projects/${created.body.id}`);

      expect(res.status).toBe(200);
      expect(res.body.id).toBe(created.body.id);
      expect(res.body.name).toBe('Retrieve Me');
      expect(res.body.description).toBe('Test desc');
    });

    it('returns 404 with structured error for non-existent UUID v4', async () => {
      const res = await request(app).get(`/api/v1/projects/${NON_EXISTENT_UUID_V4}`);

      expect(res.status).toBe(404);
      expect(res.body).toEqual({
        error: {
          code: 'project_not_found',
          message: 'Project not found.',
          details: { projectId: NON_EXISTENT_UUID_V4 },
        },
      });
    });

    it('returns 422 for malformed UUID string', async () => {
      const res = await request(app).get('/api/v1/projects/not-a-valid-uuid');

      expect(res.status).toBe(422);
      expect(res.body).toEqual({
        error: {
          code: 'invalid_project_id',
          message: 'Project ID must be a valid UUID v4.',
          details: { projectId: 'not-a-valid-uuid' },
        },
      });
    });

    it('returns 422 for non-v4 UUID (UUID v1 rejected)', async () => {
      const res = await request(app).get(`/api/v1/projects/${INVALID_UUID_V1}`);

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_project_id');
    });
  });

  describe('GET /api/v1/projects', () => {
    it('lists projects sorted by created_at desc with default pagination', async () => {
      const p1 = await request(app).post('/api/v1/projects').send({ name: 'Project 1' });
      await new Promise((r) => setTimeout(r, 10));
      const p2 = await request(app).post('/api/v1/projects').send({ name: 'Project 2' });
      await new Promise((r) => setTimeout(r, 10));
      const p3 = await request(app).post('/api/v1/projects').send({ name: 'Project 3' });

      const res = await request(app).get('/api/v1/projects');

      expect(res.status).toBe(200);
      expect(Array.isArray(res.body)).toBe(true);
      expect(res.body.length).toBe(3);
      // Newest first
      expect(res.body[0].id).toBe(p3.body.id);
      expect(res.body[1].id).toBe(p2.body.id);
      expect(res.body[2].id).toBe(p1.body.id);
    });

    it('respects limit and offset query parameters', async () => {
      await request(app).post('/api/v1/projects').send({ name: 'P1' });
      await new Promise((r) => setTimeout(r, 10));
      const p2 = await request(app).post('/api/v1/projects').send({ name: 'P2' });
      await new Promise((r) => setTimeout(r, 10));
      await request(app).post('/api/v1/projects').send({ name: 'P3' });

      const res = await request(app).get('/api/v1/projects?limit=1&offset=1');

      expect(res.status).toBe(200);
      expect(res.body.length).toBe(1);
      expect(res.body[0].id).toBe(p2.body.id);
    });

    it('rejects invalid limit parameter with 422', async () => {
      const res = await request(app).get('/api/v1/projects?limit=abc');

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    it('rejects negative offset parameter with 422', async () => {
      const res = await request(app).get('/api/v1/projects?offset=-1');

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });
  });

  describe('PATCH /api/v1/projects/:projectId', () => {
    it('updates project metadata and returns 200 with updated document', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .send({ name: 'Original Name', description: 'Original Description' });

      const res = await request(app)
        .patch(`/api/v1/projects/${created.body.id}`)
        .send({
          name: 'Updated Name',
          description: 'Updated Description',
        });

      expect(res.status).toBe(200);
      expect(res.body.id).toBe(created.body.id);
      expect(res.body.name).toBe('Updated Name');
      expect(res.body.description).toBe('Updated Description');
    });

    it('returns 404 when updating non-existent project', async () => {
      const res = await request(app)
        .patch(`/api/v1/projects/${NON_EXISTENT_UUID_V4}`)
        .send({ name: 'New Name' });

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('project_not_found');
    });

    it('returns 422 when update body has no valid fields', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .send({ name: 'Target Project' });

      const res = await request(app)
        .patch(`/api/v1/projects/${created.body.id}`)
        .send({});

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('validation_error');
    });

    it('returns 422 for invalid UUID v4 param on update', async () => {
      const res = await request(app)
        .patch('/api/v1/projects/invalid-id')
        .send({ name: 'New Name' });

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_project_id');
    });
  });

  describe('DELETE /api/v1/projects/:projectId', () => {
    it('deletes an existing project and returns 204 No Content', async () => {
      const created = await request(app)
        .post('/api/v1/projects')
        .send({ name: 'Delete Target' });

      const res = await request(app).delete(`/api/v1/projects/${created.body.id}`);

      expect(res.status).toBe(204);
      expect(res.text).toBe('');

      // Subsequent GET should return 404
      const getRes = await request(app).get(`/api/v1/projects/${created.body.id}`);
      expect(getRes.status).toBe(404);
    });

    it('returns 404 when deleting a non-existent project', async () => {
      const res = await request(app).delete(`/api/v1/projects/${NON_EXISTENT_UUID_V4}`);

      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe('project_not_found');
    });

    it('returns 422 for invalid UUID v4 param on delete', async () => {
      const res = await request(app).delete('/api/v1/projects/not-a-valid-uuid');

      expect(res.status).toBe(422);
      expect(res.body.error.code).toBe('invalid_project_id');
    });
  });
});
