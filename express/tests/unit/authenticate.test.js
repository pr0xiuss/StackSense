const authenticate = require('../../src/middleware/authenticate');

describe('Authenticate Middleware Unit Tests', () => {
  const validUuid = '11111111-1111-4111-8111-111111111111';
  const invalidUuid = 'not-a-valid-uuid';

  it('calls next() when req.user.id is a valid UUID v4', () => {
    const req = { user: { id: validUuid } };
    const res = {};
    const next = jest.fn();

    authenticate(req, res, next);
    expect(next).toHaveBeenCalledTimes(1);
    expect(req.user.id).toBe(validUuid);
  });

  it('normalizes req.user.id and calls next() when req.user._id is provided (M5 Mongoose doc)', () => {
    const req = { user: { _id: validUuid } };
    const res = {};
    const next = jest.fn();

    authenticate(req, res, next);
    expect(next).toHaveBeenCalledTimes(1);
    expect(req.user.id).toBe(validUuid);
  });

  it('returns 422 when req.user contains an invalid UUID', () => {
    const req = { user: { id: invalidUuid } };
    const json = jest.fn();
    const status = jest.fn().mockReturnValue({ json });
    const res = { status };
    const next = jest.fn();

    authenticate(req, res, next);
    expect(status).toHaveBeenCalledWith(422);
    expect(json).toHaveBeenCalledWith(
      expect.objectContaining({
        error: expect.objectContaining({
          code: 'invalid_user_id',
        }),
      })
    );
    expect(next).not.toHaveBeenCalled();
  });

  it('sets req.user from x-user-id header when valid UUID v4', () => {
    const req = {
      header: jest.fn().mockReturnValue(validUuid),
    };
    const res = {};
    const next = jest.fn();

    authenticate(req, res, next);
    expect(next).toHaveBeenCalledTimes(1);
    expect(req.user).toEqual({ id: validUuid });
  });

  it('returns 422 when x-user-id header is not a valid UUID v4', () => {
    const req = {
      header: jest.fn().mockReturnValue(invalidUuid),
    };
    const json = jest.fn();
    const status = jest.fn().mockReturnValue({ json });
    const res = { status };
    const next = jest.fn();

    authenticate(req, res, next);
    expect(status).toHaveBeenCalledWith(422);
    expect(json).toHaveBeenCalledWith(
      expect.objectContaining({
        error: expect.objectContaining({
          code: 'invalid_user_id',
        }),
      })
    );
    expect(next).not.toHaveBeenCalled();
  });

  it('returns 401 authentication_required when neither req.user nor header is provided', () => {
    const req = {
      header: jest.fn().mockReturnValue(undefined),
    };
    const json = jest.fn();
    const status = jest.fn().mockReturnValue({ json });
    const res = { status };
    const next = jest.fn();

    authenticate(req, res, next);
    expect(status).toHaveBeenCalledWith(401);
    expect(json).toHaveBeenCalledWith(
      expect.objectContaining({
        error: expect.objectContaining({
          code: 'authentication_required',
        }),
      })
    );
    expect(next).not.toHaveBeenCalled();
  });
});
