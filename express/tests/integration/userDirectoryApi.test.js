const crypto = require('crypto');
const request = require('supertest');
const app = require('../../src/app');
const User = require('../../src/models/User');

describe('Authenticated user directory API', () => {
  let requesterId;

  beforeEach(async () => {
    requesterId = crypto.randomUUID();
    await User.create([
      { _id: requesterId, email: 'requester@example.com', username: 'requester', password_hash: 'hash', is_active: true },
      { email: 'alice@example.com', username: 'alice', password_hash: 'hash', is_active: true },
      { email: 'alicia@example.com', username: 'alicia', password_hash: 'hash', is_active: true },
      { email: 'allen@example.com', username: 'allen', password_hash: 'hash', is_active: false },
      { email: 'bob@example.com', username: 'bob', password_hash: 'hash', is_active: true },
    ]);
  });

  test('requires authentication', async () => {
    const response = await request(app).get('/api/v1/users/lookup?username=ali');
    expect(response.status).toBe(401);
    expect(response.body.error.code).toBe('authentication_required');
  });

  test('returns active prefix matches with only id and username', async () => {
    const response = await request(app)
      .get('/api/v1/users/lookup?username=ALI&limit=8')
      .set('x-user-id', requesterId)
      .expect(200);

    expect(response.body.map((user) => user.username)).toEqual(['alice', 'alicia']);
    for (const user of response.body) {
      expect(Object.keys(user).sort()).toEqual(['id', 'username']);
      expect(user.email).toBeUndefined();
    }
  });

  test.each([
    ['/api/v1/users/lookup', 'username'],
    ['/api/v1/users/lookup?username=a', 'username'],
    ['/api/v1/users/lookup?username=bad-name', 'username'],
    ['/api/v1/users/lookup?username=alice&limit=0', 'limit'],
    ['/api/v1/users/lookup?username=alice&limit=11', 'limit'],
  ])('validates lookup query %s', async (url, field) => {
    const response = await request(app).get(url).set('x-user-id', requesterId).expect(422);
    expect(response.body.error.code).toBe('validation_error');
    expect(response.body.error.details.field).toBe(field);
  });
});
