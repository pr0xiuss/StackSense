const request = require('supertest');
const mongoose = require('mongoose');
const app = require('../../src/app');

describe('Express Foundation & Health API (Batch 1)', () => {
  it('verifies MongoDB in-memory connection is active', () => {
    expect(mongoose.connection.readyState).toBe(1); // 1 = connected
  });

  it('GET /api/v1/health returns 200 with service status', async () => {
    const res = await request(app).get('/api/v1/health');

    expect(res.status).toBe(200);
    expect(res.body).toEqual({
      status: 'ok',
      service: 'stacksense-express',
    });
  });

  it('GET /unknown-route returns 404 with structured error contract', async () => {
    const res = await request(app).get('/api/v1/unknown-endpoint');

    expect(res.status).toBe(404);
    expect(res.body).toHaveProperty('error');
    expect(res.body.error.code).toBe('route_not_found');
    expect(res.body.error.message).toContain('GET /api/v1/unknown-endpoint');
    expect(res.body.error.details).toEqual({});
  });
});
