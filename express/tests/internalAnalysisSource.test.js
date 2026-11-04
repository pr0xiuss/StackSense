const { Readable } = require('stream');

const authenticateInternalService = require('../src/middleware/internalServiceAuth');
const {
  InternalAnalysisSourceService,
} = require('../src/services/internalAnalysisSourceService');

describe('internal analysis source boundary', () => {
  const originalSecret = process.env.PLATFORM_INTERNAL_API_SECRET_KEY;

  afterEach(() => {
    if (originalSecret === undefined) {
      delete process.env.PLATFORM_INTERNAL_API_SECRET_KEY;
    } else {
      process.env.PLATFORM_INTERNAL_API_SECRET_KEY = originalSecret;
    }
  });

  test('requires and validates the service credential', () => {
    process.env.PLATFORM_INTERNAL_API_SECRET_KEY = 'test-platform-secret';
    const next = jest.fn();

    authenticateInternalService({ get: () => undefined }, {}, next);
    expect(next.mock.calls[0][0]).toMatchObject({
      code: 'authentication_required',
      status: 401,
    });

    authenticateInternalService({ get: () => 'wrong-secret' }, {}, next);
    expect(next.mock.calls[1][0]).toMatchObject({
      code: 'invalid_token',
      status: 401,
    });

    const request = { get: () => 'test-platform-secret' };
    authenticateInternalService(request, {}, next);
    expect(next.mock.calls[2]).toEqual([]);
    expect(request.internalService).toEqual({ name: 'python-analysis' });
  });

  test('manifest is project scoped and never exposes storage keys', async () => {
    const revision = {
      project_id: 'project-a',
      repository_id: 'repository-a',
      toJSON: () => ({ id: 'revision-a', project_id: 'project-a' }),
    };
    const artifact = {
      toJSON: () => ({ id: 'artifact-a', path: 'src/app.py', storage_key: 'secret' }),
    };
    const sort = jest.fn().mockResolvedValue([artifact]);
    const service = new InternalAnalysisSourceService({
      repositoryModel: { findById: jest.fn().mockResolvedValue({ project_id: 'project-a' }) },
      revisionModel: { findById: jest.fn().mockResolvedValue(revision) },
      artifactModel: { find: jest.fn(() => ({ sort })) },
      storageService: { get: jest.fn() },
    });

    const manifest = await service.getManifest(
      'project-a',
      'repository-a',
      'revision-a'
    );

    expect(manifest.artifacts[0]).toEqual({ id: 'artifact-a', path: 'src/app.py' });
    await expect(
      service.getManifest('project-b', 'repository-a', 'revision-a')
    ).rejects.toMatchObject({ code: 'repository_not_found', status: 404 });
  });

  test('artifact content lookup verifies the complete ownership chain', async () => {
    const storageService = {
      get: jest.fn().mockResolvedValue(Readable.from([Buffer.from('content')])),
    };
    const service = new InternalAnalysisSourceService({
      repositoryModel: { findById: jest.fn().mockResolvedValue({ project_id: 'p' }) },
      revisionModel: {
        findById: jest.fn().mockResolvedValue({ project_id: 'p', repository_id: 'r' }),
      },
      artifactModel: {
        findById: jest.fn().mockResolvedValue({
          project_id: 'p',
          repository_id: 'r',
          revision_id: 'v',
          storage_key: 'owned/key',
        }),
      },
      storageService,
    });

    const result = await service.openArtifact('p', 'r', 'v', 'a');
    expect(result.stream).toBeDefined();
    expect(storageService.get).toHaveBeenCalledWith('owned/key');
    await expect(service.openArtifact('p', 'r', 'other', 'a')).rejects.toMatchObject({
      code: 'artifact_not_found',
      status: 404,
    });
  });
});
