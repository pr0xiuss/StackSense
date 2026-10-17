const crypto = require('crypto');
const Ingestion = require('../../src/models/Ingestion');
const { INGESTION_STATUS } = require('../../src/constants/ingestionConstants');

const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe('Ingestion Model Unit Tests (M3 Batch 1)', () => {
  const sampleProjectId = crypto.randomUUID();
  const sampleRepositoryId = crypto.randomUUID();

  beforeEach(async () => {
    await Ingestion.createIndexes();
  });

  it('creates an ingestion job with valid default UUID and pending status', async () => {
    const ingestion = new Ingestion({
      project_id: sampleProjectId,
      repository_id: sampleRepositoryId,
      source_type: 'archive',
      source_reference: 'data/sample.zip',
    });

    await ingestion.save();

    expect(ingestion._id).toMatch(UUID_V4_REGEX);
    expect(ingestion.project_id).toBe(sampleProjectId);
    expect(ingestion.repository_id).toBe(sampleRepositoryId);
    expect(ingestion.source_type).toBe('archive');
    expect(ingestion.source_reference).toBe('data/sample.zip');
    expect(ingestion.status).toBe(INGESTION_STATUS.PENDING);
    expect(ingestion.error_code).toBeNull();
    expect(ingestion.error_message).toBeNull();
    expect(ingestion.started_at).toBeNull();
    expect(ingestion.completed_at).toBeNull();
    expect(ingestion.created_at).toBeInstanceOf(Date);
    expect(ingestion.updated_at).toBeInstanceOf(Date);
  });

  it('rejects creation when required fields are missing', async () => {
    const missingSource = new Ingestion({
      project_id: sampleProjectId,
      repository_id: sampleRepositoryId,
    });
    await expect(missingSource.save()).rejects.toThrow();
  });

  it('rejects unsupported source_type', async () => {
    const invalidType = new Ingestion({
      project_id: sampleProjectId,
      repository_id: sampleRepositoryId,
      source_type: 'gitlab',
      source_reference: 'https://gitlab.com/repo',
    });
    await expect(invalidType.save()).rejects.toThrow();
  });

  it('rejects invalid status enum value', async () => {
    const invalidStatus = new Ingestion({
      project_id: sampleProjectId,
      repository_id: sampleRepositoryId,
      source_type: 'github',
      source_reference: 'https://github.com/owner/repo',
      status: 'unknown_state',
    });
    await expect(invalidStatus.save()).rejects.toThrow();
  });

  it('evaluates status transition validity correctly via canTransitionTo', async () => {
    const ingestion = new Ingestion({
      project_id: sampleProjectId,
      repository_id: sampleRepositoryId,
      source_type: 'archive',
      source_reference: 'data/test.zip',
      status: INGESTION_STATUS.PENDING,
    });

    expect(ingestion.canTransitionTo(INGESTION_STATUS.PROCESSING)).toBe(true);
    expect(ingestion.canTransitionTo(INGESTION_STATUS.FAILED)).toBe(true);
    expect(ingestion.canTransitionTo(INGESTION_STATUS.COMPLETED)).toBe(false);

    ingestion.status = INGESTION_STATUS.PROCESSING;
    expect(ingestion.canTransitionTo(INGESTION_STATUS.COMPLETED)).toBe(true);
    expect(ingestion.canTransitionTo(INGESTION_STATUS.FAILED)).toBe(true);
    expect(ingestion.canTransitionTo(INGESTION_STATUS.PENDING)).toBe(false);

    ingestion.status = INGESTION_STATUS.COMPLETED;
    expect(ingestion.canTransitionTo(INGESTION_STATUS.PROCESSING)).toBe(false);
    expect(ingestion.canTransitionTo(INGESTION_STATUS.FAILED)).toBe(false);

    ingestion.status = INGESTION_STATUS.FAILED;
    expect(ingestion.canTransitionTo(INGESTION_STATUS.PROCESSING)).toBe(false);
    expect(ingestion.canTransitionTo(INGESTION_STATUS.COMPLETED)).toBe(false);
  });

  it('enforces partial unique index: at most one processing ingestion per repository', async () => {
    const job1 = new Ingestion({
      project_id: sampleProjectId,
      repository_id: sampleRepositoryId,
      source_type: 'archive',
      source_reference: 'data/job1.zip',
      status: INGESTION_STATUS.PROCESSING,
    });
    await job1.save();

    const job2 = new Ingestion({
      project_id: sampleProjectId,
      repository_id: sampleRepositoryId,
      source_type: 'archive',
      source_reference: 'data/job2.zip',
      status: INGESTION_STATUS.PROCESSING,
    });
    await expect(job2.save()).rejects.toThrow();

    // Multiple completed or pending jobs for same repository are permitted
    const jobCompleted = new Ingestion({
      project_id: sampleProjectId,
      repository_id: sampleRepositoryId,
      source_type: 'archive',
      source_reference: 'data/job3.zip',
      status: INGESTION_STATUS.COMPLETED,
    });
    await expect(jobCompleted.save()).resolves.toBeDefined();
  });
});
