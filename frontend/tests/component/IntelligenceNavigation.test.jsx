import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { parseCurrentRoute } from '../../src/App.jsx';

describe('Intelligence Navigation & Route Parsing', () => {
  const originalHash = window.location.hash;
  const originalPathname = window.location.pathname;

  const projectId = '11111111-1111-4111-8111-111111111111';
  const repositoryId = '22222222-2222-4222-8222-222222222222';
  const analysisId = '33333333-3333-4333-8333-333333333333';
  const versionId = '44444444-4444-4444-8444-444444444444';

  beforeEach(() => {
    window.location.hash = '';
    window.history.pushState(null, '', '/');
  });

  afterEach(() => {
    window.location.hash = originalHash;
    window.history.pushState(null, '', originalPathname || '/');
  });

  it('correctly parses valid Intelligence hash route', () => {
    window.location.hash = `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/intelligence`;
    const route = parseCurrentRoute();
    expect(route).toEqual({
      view: 'intelligence',
      projectId,
      repositoryId,
      analysisId,
      versionId,
    });
  });

  it('correctly parses valid Intelligence pathname route', () => {
    window.location.hash = '';
    window.history.pushState(null, '', `/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/intelligence`);
    const route = parseCurrentRoute();
    expect(route).toEqual({
      view: 'intelligence',
      projectId,
      repositoryId,
      analysisId,
      versionId,
    });
  });

  it('preserves route precedence: intelligence is matched before exact-version architecture', () => {
    window.location.hash = `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/intelligence`;
    const route = parseCurrentRoute();
    expect(route.view).toBe('intelligence');
    expect(route.view).not.toBe('architecture');
  });

  it('permits trailing slash on intelligence route', () => {
    window.location.hash = `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/intelligence/`;
    const route = parseCurrentRoute();
    expect(route).toEqual({
      view: 'intelligence',
      projectId,
      repositoryId,
      analysisId,
      versionId,
    });
  });

  it('permits query parameters following intelligence path', () => {
    window.location.hash = `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/intelligence?tab=search&filter=canonical`;
    const route = parseCurrentRoute();
    expect(route).toEqual({
      view: 'intelligence',
      projectId,
      repositoryId,
      analysisId,
      versionId,
    });
  });

  it('rejects malformed UUID in projectId', () => {
    window.location.hash = `#/projects/not-a-uuid/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/intelligence`;
    const route = parseCurrentRoute();
    expect(route.view).toBe('route_error');
    expect(route.message).toMatch(/Malformed UUID in Intelligence route parameters/i);
  });

  it('rejects malformed UUID in repositoryId', () => {
    window.location.hash = `#/projects/${projectId}/repositories/invalid-repo/analyses/${analysisId}/architecture/${versionId}/intelligence`;
    const route = parseCurrentRoute();
    expect(route.view).toBe('route_error');
    expect(route.message).toMatch(/Malformed UUID in Intelligence route parameters/i);
  });

  it('rejects malformed UUID in analysisId', () => {
    window.location.hash = `#/projects/${projectId}/repositories/${repositoryId}/analyses/invalid-analysis/architecture/${versionId}/intelligence`;
    const route = parseCurrentRoute();
    expect(route.view).toBe('route_error');
    expect(route.message).toMatch(/Malformed UUID in Intelligence route parameters/i);
  });

  it('rejects malformed UUID in versionId', () => {
    window.location.hash = `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/invalid-version/intelligence`;
    const route = parseCurrentRoute();
    expect(route.view).toBe('route_error');
    expect(route.message).toMatch(/Malformed UUID in Intelligence route parameters/i);
  });

  it('rejects unmatched trailing path on intelligence route', () => {
    window.location.hash = `#/projects/${projectId}/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/intelligence/unsupported/tail`;
    const route = parseCurrentRoute();
    expect(route.view).toBe('route_error');
    expect(route.message).toMatch(/Unmatched trailing path on Intelligence route/i);
  });

  it('rejects malformed URL encoding in route identifiers', () => {
    window.location.hash = `#/projects/%E0%A4%A/repositories/${repositoryId}/analyses/${analysisId}/architecture/${versionId}/intelligence`;
    const route = parseCurrentRoute();
    expect(route.view).toBe('route_error');
    expect(route.message).toMatch(/Malformed URL encoding in route identifiers/i);
  });
});
